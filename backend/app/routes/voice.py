"""Voice WebSocket endpoint — real-time STT/TTS via Deepgram."""

import json
import re
import asyncio
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import get_settings
from app.database import get_supabase
from app.services.ai_brain import chat_with_tools, build_system_prompt, ModelTier, get_async_openai, get_model_id, _convert_tools_for_openai
from app.services.tool_registry import registry
from app.services.usage_tracker import track_stt_usage, track_tts_usage
import httpx

router = APIRouter(tags=["voice"])


@router.websocket("/ws/voice")
async def voice_ws(ws: WebSocket):
    await ws.accept()

    s = get_settings()
    if not s.deepgram_api_key:
        await ws.send_json({"type": "error", "message": "Deepgram not configured"})
        await ws.close()
        return

    # Expect auth message first
    try:
        auth_msg = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        await ws.close(1008, "Auth timeout")
        return

    token = auth_msg.get("token", "")
    user_id = auth_msg.get("user_id")
    org_id = auth_msg.get("org_id")
    agent_id = auth_msg.get("agent_id")
    conversation_id = auth_msg.get("conversation_id")

    if not user_id:
        await ws.close(1008, "Missing auth")
        return

    db = get_supabase()

    if not org_id:
        row = db.table("users").select("org_id").eq("id", user_id).execute()
        org_id = row.data[0]["org_id"] if row.data else None
        if not org_id:
            await ws.close(1008, "No org found")
            return
    system_prompt = """You are Kaia, a voice-first personal AI assistant.
Rules: Reply in 1-2 short sentences max. Sound natural and warm. Never use markdown, lists, code blocks, or asterisks.
You have tools for calendar, email, CRM, weather, maps, and memory. Use them when helpful but keep answers brief."""

    if agent_id:
        agent = db.table("agents").select("system_prompt").eq("id", agent_id).single().execute()
        if agent.data and agent.data.get("system_prompt"):
            system_prompt = agent.data["system_prompt"]

    memories_result = db.table("memories") \
        .select("content") \
        .eq("org_id", org_id) \
        .eq("is_active", True) \
        .order("importance", desc=True) \
        .limit(10) \
        .execute()
    memory_lines = [m["content"] for m in memories_result.data]
    full_prompt = build_system_prompt(system_prompt, memory_lines)

    # Create conversation if needed
    if not conversation_id:
        conv = db.table("conversations").insert({
            "org_id": org_id, "user_id": user_id,
            "agent_id": agent_id, "mode": "voice",
            "title": "Voice conversation",
        }).execute()
        conversation_id = conv.data[0]["id"]

    await ws.send_json({"type": "ready", "conversation_id": conversation_id})

    # Connect to Deepgram STT (streaming)
    dg_url = "wss://api.deepgram.com/v1/listen"
    dg_params = "?model=nova-3&language=en&smart_format=true&endpointing=700&interim_results=true&utterance_end_ms=2000"

    messages_history: list[dict] = []
    is_speaking = False
    current_tts_task: asyncio.Task | None = None

    async def _tts_one(sentence: str) -> bytes | None:
        """TTS a single sentence, return raw mp3 bytes."""
        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://api.deepgram.com/v1/speak",
                    params={"model": "aura-2-theia-en", "encoding": "mp3"},
                    headers={"Authorization": f"Token {s.deepgram_api_key}", "Content-Type": "application/json"},
                    json={"text": sentence},
                )
                return r.content if r.status_code == 200 else None
        except Exception:
            return None

    async def _stream_and_speak(messages, prompt, tools_defs, tool_exec):
        """Stream LLM → sentence queue → TTS concurrently. Returns reply text."""
        client = get_async_openai()
        model = get_model_id(ModelTier.FAST)
        oai_tools = _convert_tools_for_openai(tools_defs) if tools_defs else None

        oai_msgs: list[dict] = [{"role": "system", "content": prompt}]
        for m in messages:
            if isinstance(m.get("content"), str):
                oai_msgs.append({"role": m["role"], "content": m["content"]})

        sq: asyncio.Queue[str | None] = asyncio.Queue()
        reply_parts: list[str] = []

        async def tts_worker():
            while True:
                sentence = await sq.get()
                if sentence is None:
                    break
                audio = await _tts_one(sentence)
                if audio:
                    await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "format": "mp3"})

        tts_task = asyncio.create_task(tts_worker())

        try:
            for _turn in range(5):
                stream = await client.chat.completions.create(
                    model=model, messages=oai_msgs, max_tokens=256,
                    tools=oai_tools, stream=True,
                )

                text = ""
                sbuf = ""
                tc_map: dict[int, dict] = {}
                finish = None

                async for chunk in stream:
                    c = chunk.choices[0] if chunk.choices else None
                    if not c:
                        continue
                    if c.finish_reason:
                        finish = c.finish_reason
                    d = c.delta
                    if d and d.content:
                        text += d.content
                        reply_parts.append(d.content)
                        sbuf += d.content
                        if re.search(r'[.!?]\s*$', sbuf):
                            await sq.put(sbuf.strip())
                            sbuf = ""
                    if d and d.tool_calls:
                        for tcd in d.tool_calls:
                            idx = tcd.index
                            if idx not in tc_map:
                                tc_map[idx] = {"id": "", "name": "", "args": ""}
                            if tcd.id:
                                tc_map[idx]["id"] = tcd.id
                            if tcd.function:
                                if tcd.function.name:
                                    tc_map[idx]["name"] = tcd.function.name
                                if tcd.function.arguments:
                                    tc_map[idx]["args"] += tcd.function.arguments

                if sbuf.strip():
                    await sq.put(sbuf.strip())

                if finish != "tool_calls" or not tc_map:
                    break

                # Execute tool calls
                asst_msg: dict = {"role": "assistant", "content": text or None, "tool_calls": [
                    {"id": tc_map[i]["id"], "type": "function",
                     "function": {"name": tc_map[i]["name"], "arguments": tc_map[i]["args"]}}
                    for i in sorted(tc_map)
                ]}
                oai_msgs.append(asst_msg)

                for i in sorted(tc_map):
                    tc = tc_map[i]
                    try:
                        args = json.loads(tc["args"])
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = await tool_exec(tc["name"], args)
                        content = json.dumps(result) if not isinstance(result, str) else result
                    except Exception as e:
                        content = f"Error: {e}"
                    oai_msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": content})

        except asyncio.CancelledError:
            tts_task.cancel()
            raise
        finally:
            await sq.put(None)
            try:
                await tts_task
            except asyncio.CancelledError:
                pass

        full_reply = "".join(reply_parts)
        await track_tts_usage(org_id, len(full_reply))
        await ws.send_json({"type": "audio_done"})
        return full_reply, model

    async def process_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task

        if not is_final or not transcript.strip():
            if transcript.strip():
                await ws.send_json({"type": "transcript_interim", "text": transcript})
            return

        await ws.send_json({"type": "transcript_final", "text": transcript})

        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
            await ws.send_json({"type": "tts_cancelled"})

        db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "user", "content": transcript,
        }).execute()

        messages_history.append({"role": "user", "content": transcript})
        if len(messages_history) > 10:
            messages_history = messages_history[-10:]

        async def tool_executor(name, args):
            args["user_id"] = user_id
            args["org_id"] = org_id
            args["conversation_id"] = conversation_id
            return await registry.execute(name, args, org_id=org_id, conversation_id=conversation_id)

        await ws.send_json({"type": "thinking"})

        async def _run():
            reply, model_used = await _stream_and_speak(
                messages_history, full_prompt,
                registry.list_definitions(), tool_executor,
            )
            messages_history.append({"role": "assistant", "content": reply})
            db.table("messages").insert({
                "conversation_id": conversation_id,
                "role": "assistant", "content": reply,
                "model_used": model_used,
            }).execute()
            await ws.send_json({"type": "response_text", "text": reply, "model": model_used})

        current_tts_task = asyncio.create_task(_run())

    # Main loop: receive audio from client, forward to Deepgram
    try:
        async with httpx.AsyncClient() as http_client:
            # Use Deepgram WebSocket for STT
            import websockets
            async with websockets.connect(
                f"{dg_url}{dg_params}",
                additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
            ) as dg_ws:

                async def receive_dg():
                    """Receive transcription results from Deepgram."""
                    async for msg in dg_ws:
                        data = json.loads(msg)
                        if data.get("type") == "Results":
                            alt = data.get("channel", {}).get("alternatives", [{}])[0]
                            transcript = alt.get("transcript", "")
                            is_final = data.get("is_final", False)
                            if transcript:
                                await process_transcript(transcript, is_final)

                async def forward_audio():
                    """Forward audio from browser to Deepgram."""
                    while True:
                        msg = await ws.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        if "bytes" in msg:
                            await dg_ws.send(msg["bytes"])
                        elif "text" in msg:
                            data = json.loads(msg["text"])
                            if data.get("type") == "stop":
                                break

                await asyncio.gather(receive_dg(), forward_audio())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()


@router.websocket("/ws/call-media")
async def call_media_ws(ws: WebSocket):
    """Twilio media stream WebSocket — bridges phone audio to Deepgram STT/TTS."""
    await ws.accept()

    s = get_settings()
    if not s.deepgram_api_key:
        await ws.close(1011, "Deepgram not configured")
        return

    db = get_supabase()
    stream_sid: str | None = None
    call_sid: str | None = None
    messages_history: list[dict] = []
    current_tts_task: asyncio.Task | None = None
    org_id: str | None = None

    system_prompt = (
        "You are Kaia, an AI assistant on a phone call. Be concise and conversational. "
        "Do not use markdown, code blocks, or long lists. Speak naturally."
    )

    async def send_tts_to_call(text: str):
        nonlocal org_id
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                tts_resp = await client.post(
                    "https://api.deepgram.com/v1/speak",
                    params={"model": "aura-2-theia-en", "encoding": "mulaw", "sample_rate": "8000"},
                    headers={
                        "Authorization": f"Token {s.deepgram_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                )
                if tts_resp.status_code == 200 and stream_sid:
                    import base64
                    audio_b64 = base64.b64encode(tts_resp.content).decode()
                    await ws.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": audio_b64},
                    })
                    if org_id:
                        await track_tts_usage(org_id, len(text))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def process_phone_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task

        if not is_final or not transcript.strip():
            return

        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()

        messages_history.append({"role": "user", "content": transcript})
        if len(messages_history) > 10:
            messages_history = messages_history[-10:]

        async def tool_executor(name, args):
            args["org_id"] = org_id or ""
            return await registry.execute(name, args, org_id=org_id or "", conversation_id="")

        resp = await chat_with_tools(
            messages=messages_history,
            system_prompt=system_prompt,
            tools_definitions=registry.list_definitions(),
            tool_executor=tool_executor,
            org_id=org_id or "",
            tier=ModelTier.FAST,
        )

        reply = resp.content
        messages_history.append({"role": "assistant", "content": reply})
        current_tts_task = asyncio.create_task(send_tts_to_call(reply))

    try:
        import websockets as ws_lib
        async with ws_lib.connect(
            "wss://api.deepgram.com/v1/listen?model=nova-3&language=en&encoding=mulaw&sample_rate=8000&endpointing=300&utterance_end_ms=1000",
            additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
        ) as dg_ws:

            async def receive_dg_phone():
                async for msg in dg_ws:
                    data = json.loads(msg)
                    if data.get("type") == "Results":
                        alt = data.get("channel", {}).get("alternatives", [{}])[0]
                        transcript = alt.get("transcript", "")
                        is_final = data.get("is_final", False)
                        if transcript:
                            await process_phone_transcript(transcript, is_final)

            async def forward_twilio_audio():
                nonlocal stream_sid, call_sid, org_id
                while True:
                    msg = await ws.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    if "text" in msg:
                        data = json.loads(msg["text"])
                        event = data.get("event", "")
                        if event == "start":
                            stream_sid = data.get("streamSid")
                            call_sid = data.get("start", {}).get("callSid")
                            if call_sid:
                                log = db.table("call_logs") \
                                    .select("org_id") \
                                    .eq("telnyx_call_control_id", call_sid) \
                                    .execute()
                                if log.data:
                                    org_id = log.data[0]["org_id"]
                        elif event == "media":
                            import base64
                            payload = data.get("media", {}).get("payload", "")
                            if payload:
                                await dg_ws.send(base64.b64decode(payload))
                        elif event == "stop":
                            break

            await asyncio.gather(receive_dg_phone(), forward_twilio_audio())

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
