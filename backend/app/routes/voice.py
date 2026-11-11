"""Voice WebSocket endpoint — real-time STT/TTS via Deepgram."""

import json
import re
import asyncio
import base64
import random
import logging
import traceback
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
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
    system_prompt = """You are Kaia — sharp, warm, a little witty. This is voice — talk like a real person.

## Voice rules
- One to two sentences max. This is spoken aloud.
- Never use markdown, lists, numbering, bold, code blocks, or asterisks.
- Don't read URLs aloud. Say "Done, check the link in the chat."
- No sign-offs: "Happy driving!", "Enjoy!", "Have a great day!" — just stop.
- No hedging: "Unfortunately", "I'm sorry but" — be straight.
- Speak naturally. A brief "okay" or "one sec" before a slow lookup is fine —
  just don't open every single answer with one.
- Match their energy. Rushed → quick. Chatting → chat.

## How you work
- ACT FIRST. "Meeting at 11am" → done. Today if no date, 30min default. Smart defaults, not questions.
- Only ask when you genuinely can't guess.
- Never "shall I proceed?" — just do it.
- If it fails, say so straight. Never fake results.
- Past dates: tell them, suggest the next one.
- Typos (gmial.com → gmail.com): fix silently.

## Tools
Calendar, email, CRM, weather, maps, memory. Use them — don't describe them."""

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

    # Pre-cache backchannel fillers in background (ready by the time user speaks)
    _FILLERS = [
        "Okay, let me check.",
        "One sec.",
        "Mm-hmm, checking.",
        "Okay.",
        "Right, give me a moment.",
    ]
    filler_cache: list[str] = []

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

    async def _cache_fillers():
        for f in _FILLERS:
            audio = await _tts_one(f)
            if audio:
                filler_cache.append(base64.b64encode(audio).decode())
    asyncio.create_task(_cache_fillers())

    # Connect to Deepgram STT (streaming)
    dg_url = "wss://api.deepgram.com/v1/listen"
    dg_params = "?model=nova-3&language=en&smart_format=true&endpointing=700&interim_results=true&utterance_end_ms=2000"

    messages_history: list[dict] = []
    is_speaking = False
    current_tts_task: asyncio.Task | None = None

    async def _stream_and_speak(messages, prompt, tools_defs, tool_exec, first_audio=None):
        """Stream LLM → sentence queue → TTS concurrently. Returns reply text.

        `first_audio` is set the moment real speech goes out, so the
        backchannel watchdog knows it is no longer needed.
        """
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
                    try:
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "format": "mp3"})
                        if first_audio is not None:
                            first_audio.set()
                    except Exception:
                        return

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

        # Backchannel only rescues an awkward silence. If the real answer
        # starts speaking first, the filler never plays.
        first_audio = asyncio.Event()

        async def _backchannel():
            try:
                await asyncio.wait_for(first_audio.wait(), timeout=s.voice_backchannel_after_s)
            except asyncio.TimeoutError:
                if filler_cache and not first_audio.is_set():
                    try:
                        await ws.send_json({
                            "type": "audio",
                            "data": random.choice(filler_cache),
                            "format": "mp3",
                        })
                    except Exception:
                        pass

        bc_task = asyncio.create_task(_backchannel())

        async def _run():
            try:
                reply, model_used = await _stream_and_speak(
                    messages_history, full_prompt,
                    registry.list_definitions(), tool_executor,
                    first_audio=first_audio,
                )
            finally:
                bc_task.cancel()
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
    logger.info("call-media: WebSocket accepted")

    s = get_settings()
    if not s.deepgram_api_key:
        logger.error("call-media: no Deepgram API key")
        await ws.close(1011, "Deepgram not configured")
        return

    db = get_supabase()
    stream_sid: str | None = None
    call_sid: str | None = None
    messages_history: list[dict] = []
    current_tts_task: asyncio.Task | None = None

    # Resolve org_id and user_id — same as browser voice handler
    _row = db.table("users").select("id, org_id").limit(1).execute()
    org_id: str | None = _row.data[0]["org_id"] if _row.data else None
    user_id: str | None = _row.data[0]["id"] if _row.data else None
    logger.info("call-media: org_id=%s user_id=%s", org_id, user_id)

    # Load memories — same as browser voice
    memories_result = db.table("memories") \
        .select("content") \
        .eq("org_id", org_id) \
        .eq("is_active", True) \
        .order("importance", desc=True) \
        .limit(10) \
        .execute()
    memory_lines = [m["content"] for m in memories_result.data]

    # Use same system prompt as browser voice
    system_prompt = build_system_prompt("""You are Kaia — sharp, warm, a little witty. This is a phone call. Talk like a person.

## Phone rules
- One to two sentences max. Snappy.
- Don't read URLs aloud. Say "Done, I'll drop the link in the app."
- Never use markdown, lists, numbering, bold, code blocks, or asterisks.
- No sign-offs: "Happy driving!", "Enjoy!", "Have a great day!" — just stop.
- No filler: "Sure thing!", "Absolutely!", "Of course!" — just do the thing.
- No hedging: "Unfortunately", "I'm sorry but" — be straight.
- Match their energy. Rushed → snappy. Chatty → chat.

## How you work
- ACT FIRST. "Meeting at 11am" → done. Today if no date, 30min default. Smart defaults, not questions.
- Only ask when you genuinely can't guess.
- Never "shall I proceed?" — just do it.
- If it fails, say so straight. Never fake results.
- Past dates: tell them, suggest the next one.
- Typos (gmial.com → gmail.com): fix silently.

## Tools
Calendar, email, CRM, weather, maps, memory. Use them — don't describe them.""", memory_lines)

    # Create a conversation for this call
    conversation_id: str = ""
    try:
        conv = db.table("conversations").insert({
            "org_id": org_id, "user_id": user_id,
            "mode": "voice", "title": "Phone call",
        }).execute()
        conversation_id = conv.data[0]["id"]
        logger.info("call-media: conversation_id=%s", conversation_id)
    except Exception:
        logger.exception("call-media: failed to create conversation")

    async def send_tts_to_call(text: str):
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
                    audio_b64 = base64.b64encode(tts_resp.content).decode()
                    await ws.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": audio_b64},
                    })
                    if org_id:
                        await track_tts_usage(org_id, len(text))
                else:
                    logger.error("call-media: TTS failed status=%s", tts_resp.status_code)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("call-media: TTS send failed")

    async def process_phone_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task

        if not is_final or not transcript.strip():
            return

        logger.info("call-media: transcript: '%s'", transcript)

        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()

        messages_history.append({"role": "user", "content": transcript})
        if len(messages_history) > 10:
            messages_history = messages_history[-10:]

        # Save to DB like browser voice does
        if conversation_id:
            try:
                db.table("messages").insert({
                    "conversation_id": conversation_id,
                    "role": "user", "content": transcript,
                }).execute()
            except Exception:
                pass

        async def tool_executor(name, args):
            logger.info("call-media: tool call: %s(%s)", name, list(args.keys()))
            args["user_id"] = user_id or ""
            args["org_id"] = org_id or ""
            args["conversation_id"] = conversation_id
            result = await registry.execute(name, args, org_id=org_id or "", conversation_id=conversation_id)
            logger.info("call-media: tool result: %s", str(result)[:200])
            return result

        try:
            resp = await chat_with_tools(
                messages=messages_history,
                system_prompt=system_prompt,
                tools_definitions=registry.list_definitions(),
                tool_executor=tool_executor,
                org_id=org_id or "",
                tier=ModelTier.FAST,
            )
            reply = resp.content
            logger.info("call-media: reply: '%s'", reply[:200])
        except Exception:
            logger.exception("call-media: LLM/tool call failed")
            reply = "Sorry, something went wrong on my end."

        messages_history.append({"role": "assistant", "content": reply})

        # Save assistant reply to DB
        if conversation_id:
            try:
                db.table("messages").insert({
                    "conversation_id": conversation_id,
                    "role": "assistant", "content": reply,
                }).execute()
            except Exception:
                pass

        current_tts_task = asyncio.create_task(send_tts_to_call(reply))

    try:
        import websockets as ws_lib
        dg_stt_url = (
            "wss://api.deepgram.com/v1/listen"
            "?model=nova-3&language=en"
            "&encoding=mulaw&sample_rate=8000"
            "&endpointing=300&utterance_end_ms=1000"
            "&interim_results=true"
        )
        logger.info("call-media: connecting to Deepgram STT…")
        async with ws_lib.connect(
            dg_stt_url,
            additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
        ) as dg_ws:
            logger.info("call-media: Deepgram connected")

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
                media_count = 0
                while True:
                    msg = await ws.receive()
                    msg_type = msg.get("type", "")
                    if msg_type == "websocket.disconnect":
                        logger.info("call-media: WS disconnected after %d media packets", media_count)
                        break
                    if "text" in msg:
                        data = json.loads(msg["text"])
                        event = data.get("event", "")
                        if event == "start":
                            stream_sid = data.get("streamSid")
                            call_sid = data.get("start", {}).get("callSid")
                            logger.info("call-media: stream started sid=%s call=%s", stream_sid, call_sid)
                            if call_sid:
                                log = db.table("call_logs") \
                                    .select("org_id") \
                                    .eq("telnyx_call_control_id", call_sid) \
                                    .execute()
                                if log.data:
                                    org_id = log.data[0]["org_id"]
                        elif event == "media":
                            payload = data.get("media", {}).get("payload", "")
                            if payload:
                                media_count += 1
                                if media_count <= 3 or media_count % 100 == 0:
                                    logger.info("call-media: forwarding packet #%d (%d bytes)", media_count, len(payload))
                                await dg_ws.send(base64.b64decode(payload))
                        elif event == "stop":
                            logger.info("call-media: stream stopped after %d media packets", media_count)
                            break
                    elif "bytes" in msg:
                        logger.info("call-media: got binary frame (unexpected)")
                    else:
                        logger.info("call-media: unknown msg type=%s", msg_type)

            await asyncio.gather(receive_dg_phone(), forward_twilio_audio())

    except WebSocketDisconnect:
        logger.info("call-media: Twilio disconnected normally")
    except Exception as exc:
        logger.exception("call-media: handler crashed")
        if hasattr(exc, "response"):
            resp = exc.response
            logger.error("call-media: rejection status=%s headers=%s body=%s",
                         resp.status_code if hasattr(resp, "status_code") else "?",
                         dict(resp.headers) if hasattr(resp, "headers") else "?",
                         resp.body.decode(errors="replace") if hasattr(resp, "body") and resp.body else "?")
    finally:
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
