"""Voice WebSocket endpoint — real-time STT/TTS via Deepgram."""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import get_settings
from app.database import get_supabase
from app.services.ai_brain import chat_with_tools, build_system_prompt, ModelTier
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
    system_prompt = """You are Kaia, a voice-first personal AI assistant. Keep responses concise and natural for speech.
You have tools for calendar, email, CRM, weather, and memory. Use them when helpful.
For voice: be brief, use natural language, avoid markdown or code blocks."""

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
    dg_params = "?model=nova-3&language=en&smart_format=true&endpointing=300&interim_results=true&utterance_end_ms=1000"

    messages_history: list[dict] = []
    is_speaking = False
    current_tts_task: asyncio.Task | None = None

    async def process_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task

        if not is_final or not transcript.strip():
            if transcript.strip():
                await ws.send_json({"type": "transcript_interim", "text": transcript})
            return

        await ws.send_json({"type": "transcript_final", "text": transcript})

        # Cancel any ongoing TTS
        if current_tts_task and not current_tts_task.done():
            current_tts_task.cancel()
            await ws.send_json({"type": "tts_cancelled"})

        # Store user message
        db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "user", "content": transcript,
        }).execute()

        messages_history.append({"role": "user", "content": transcript})

        # Keep only last 10 messages for voice context
        if len(messages_history) > 10:
            messages_history = messages_history[-10:]

        async def tool_executor(name, args):
            args["user_id"] = user_id
            args["org_id"] = org_id
            args["conversation_id"] = conversation_id
            return await registry.execute(name, args, org_id=org_id, conversation_id=conversation_id)

        await ws.send_json({"type": "thinking"})

        resp = await chat_with_tools(
            messages=messages_history,
            system_prompt=full_prompt,
            tools_definitions=registry.list_definitions(),
            tool_executor=tool_executor,
            org_id=org_id,
            tier=ModelTier.FAST,
        )

        reply = resp.content
        messages_history.append({"role": "assistant", "content": reply})

        db.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant", "content": reply,
            "model_used": resp.model,
            "tokens_in": resp.tokens_in, "tokens_out": resp.tokens_out,
        }).execute()

        await ws.send_json({
            "type": "response_text",
            "text": reply,
            "model": resp.model,
            "tokens_in": resp.tokens_in,
            "tokens_out": resp.tokens_out,
            "cost": resp.estimated_cost_usd,
        })

        # TTS: stream audio back
        current_tts_task = asyncio.create_task(stream_tts(ws, reply, org_id, s))

    async def stream_tts(ws: WebSocket, text: str, org_id: str, s):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.deepgram.com/v1/speak",
                    params={"model": "aura-2-theia-en", "encoding": "mp3"},
                    headers={
                        "Authorization": f"Token {s.deepgram_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                )
                if resp.status_code == 200:
                    import base64
                    audio_b64 = base64.b64encode(resp.content).decode()
                    await ws.send_json({
                        "type": "audio",
                        "data": audio_b64,
                        "format": "mp3",
                    })
                    await track_tts_usage(org_id, len(text))
                    await ws.send_json({"type": "audio_done"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await ws.send_json({"type": "tts_error", "message": str(e)})

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
