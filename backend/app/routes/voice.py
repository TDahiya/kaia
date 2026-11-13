"""Voice WebSocket endpoint — real-time STT/TTS via Deepgram."""

import json
import re
import asyncio
import base64
import random
import logging
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
from app.config import get_settings
from app.database import get_supabase
from app.services.ai_brain import (
    chat_with_tools, build_system_prompt, ModelTier, get_async_openai,
    get_model_id, _convert_tools_for_openai, completion_params,
)
from app.services.tool_registry import registry
from app.services.usage_tracker import track_stt_usage, track_tts_usage
import httpx
import websockets

router = APIRouter(tags=["voice"])

# Streaming TTS only emits raw PCM — there is no mp3 option on the socket.
# The client plays everything through one scheduler at this rate.
TTS_VOICE = "aura-2-theia-en"
TTS_RATE = 24000

# Voice stays on the fast model: time-to-first-token is what you hear as
# lag. Bump to STANDARD if you want a sharper Kaia and can accept the wait.
VOICE_TIER = ModelTier.FAST
VOICE_MAX_TOKENS = 600

# Phone leg: Twilio media streams are 8kHz mulaw in 20ms frames.
PHONE_TTS_WS_URL = (
    f"wss://api.deepgram.com/v1/speak"
    f"?model={TTS_VOICE}&encoding=mulaw&sample_rate=8000"
)
TWILIO_FRAME_BYTES = 160  # 20ms of 8kHz mulaw

# Backstop against a runaway call. Answering-machine detection should stop
# voicemail before it starts, but if anything else ever feeds Kaia a stream
# of prompts she will answer every one, at a model call and TTS each time.
MAX_PHONE_TURNS = 25
TTS_WS_URL = (
    f"wss://api.deepgram.com/v1/speak"
    f"?model={TTS_VOICE}&encoding=linear16&sample_rate={TTS_RATE}"
)


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
- Keep it short — usually a sentence or two. Take longer only when the
  answer genuinely needs it, and never pad to fill space.
- Never use markdown, lists, numbering, bold, code blocks, or asterisks.
- Don't read URLs aloud. Say "Done, check the link in the chat."
- No sign-offs: "Happy driving!", "Enjoy!", "Have a great day!" — just stop.
- No hedging: "Unfortunately", "I'm sorry but" — be straight.
- Speak naturally. A brief "okay" or "one sec" before a slow lookup is fine —
  just don't open every single answer with one.
- Match their energy. Rushed → quick. Chatting → chat.

## How you work
- ACT FIRST. "Meeting at 11am" → call the tool. Today if no date, 30min default. Smart defaults, not questions.
- Only ask when you genuinely can't guess.
- Never "shall I proceed?" — just do it.
- Something is done ONLY if a tool call succeeded. Never say "scheduled",
  "sent" or "saved" unless the tool ran and came back clean — saying it
  does not make it so.
- If a tool errors, say what failed in one line. If it mentions an expired
  token, tell them to reconnect Google in Settings.
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

    # Create conversation if needed. Placeholder title is replaced by the
    # first thing actually said, so the history list stays scannable.
    is_new_conversation = not conversation_id
    if not conversation_id:
        conv = db.table("conversations").insert({
            "org_id": org_id, "user_id": user_id,
            "agent_id": agent_id, "mode": "voice",
            "title": f"Voice · {datetime.now(timezone.utc).strftime('%H:%M')}",
        }).execute()
        conversation_id = conv.data[0]["id"]

    await ws.send_json({"type": "ready", "conversation_id": conversation_id})

    _FILLERS = [
        "Okay, let me check.",
        "One sec.",
        "Mm-hmm, checking.",
        "Right, give me a moment.",
    ]

    # Connect to Deepgram STT (streaming)
    dg_url = "wss://api.deepgram.com/v1/listen"
    dg_params = "?model=nova-3&language=en&smart_format=true&endpointing=700&interim_results=true&utterance_end_ms=2000"

    messages_history: list[dict] = []
    is_speaking = False
    current_tts_task: asyncio.Task | None = None

    # One TTS socket for the whole session. Reconnecting per sentence was
    # costing a TLS handshake each time and resetting prosody mid-answer.
    tts_sock = None

    async def _tts_socket():
        nonlocal tts_sock
        if tts_sock is not None:
            return tts_sock
        tts_sock = await websockets.connect(
            TTS_WS_URL,
            additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
            max_size=None,
        )
        return tts_sock

    async def _drop_tts_socket():
        nonlocal tts_sock
        if tts_sock is not None:
            try:
                await tts_sock.close()
            except Exception:
                pass
            tts_sock = None

    async def _stream_and_speak(messages, prompt, tools_defs, tool_exec, first_audio=None):
        """Stream LLM text straight into a live TTS socket. Returns reply text.

        Text deltas are pushed as they arrive, so speech starts before the
        model has finished writing. `first_audio` is set on the first audio
        frame so the backchannel watchdog knows it is no longer needed.
        """
        client = get_async_openai()
        model = get_model_id(VOICE_TIER)
        oai_tools = _convert_tools_for_openai(tools_defs) if tools_defs else None

        oai_msgs: list[dict] = [{"role": "system", "content": prompt}]
        for m in messages:
            if isinstance(m.get("content"), str):
                oai_msgs.append({"role": m["role"], "content": m["content"]})

        reply_parts: list[str] = []

        try:
            sock = await _tts_socket()
        except Exception:
            logger.exception("voice: TTS socket connect failed")
            sock = None

        async def pump_audio():
            """Forward synthesised audio until Deepgram confirms the flush."""
            if sock is None:
                return
            sent = 0
            try:
                async for frame in sock:
                    if isinstance(frame, bytes):
                        await ws.send_json({
                            "type": "audio",
                            "data": base64.b64encode(frame).decode(),
                            "format": "pcm16",
                            "rate": TTS_RATE,
                        })
                        sent += len(frame)
                        if first_audio is not None:
                            first_audio.set()
                    else:
                        evt = json.loads(frame)
                        if evt.get("type") == "Flushed":
                            logger.info("voice: spoke %.2fs of audio", sent / 2 / TTS_RATE)
                            return
                        if evt.get("type") == "Warning":
                            logger.warning("voice: Deepgram TTS — %s", evt.get("description"))
            except Exception:
                logger.exception("voice: TTS pump ended")

        async def speak(text: str):
            if sock is None or not text.strip():
                return
            try:
                await sock.send(json.dumps({"type": "Speak", "text": text}))
            except Exception:
                logger.exception("TTS send failed")

        pump_task = asyncio.create_task(pump_audio())

        try:
            for _turn in range(5):
                stream = await client.chat.completions.create(
                    model=model, messages=oai_msgs,
                    tools=oai_tools, stream=True,
                    **completion_params(model, VOICE_MAX_TOKENS, has_tools=bool(oai_tools)),
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
                        # Emit text as it is written, so the transcript keeps
                        # pace with the speech instead of landing after it.
                        try:
                            await ws.send_json({"type": "response_delta", "text": d.content})
                        except Exception:
                            pass
                        # Push at clause boundaries: enough context for the
                        # synthesiser to phrase well, far sooner than a full
                        # sentence. Prosody is continuous either way now.
                        if re.search(r"[.!?,;:]\s$|[.!?]$", sbuf) and len(sbuf) >= 12:
                            await speak(sbuf)
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
                    await speak(sbuf)
                    sbuf = ""

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
            pump_task.cancel()
            await _drop_tts_socket()
            raise
        finally:
            # Flush tells Deepgram to synthesise the tail; the pump then sees
            # "Flushed" and finishes. If the socket died, rebuild it next turn.
            if sock is not None:
                try:
                    await sock.send(json.dumps({"type": "Flush"}))
                    await asyncio.wait_for(pump_task, timeout=30)
                except Exception:
                    pump_task.cancel()
                    await _drop_tts_socket()
            else:
                pump_task.cancel()

        full_reply = "".join(reply_parts)
        await track_tts_usage(org_id, len(full_reply))
        await ws.send_json({"type": "audio_done"})
        return full_reply, model

    async def process_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task, is_new_conversation

        if not is_final or not transcript.strip():
            if transcript.strip():
                await ws.send_json({"type": "transcript_interim", "text": transcript})
            return

        await ws.send_json({"type": "transcript_final", "text": transcript})

        if is_new_conversation:
            is_new_conversation = False
            try:
                db.table("conversations").update({"title": transcript[:80]}) \
                    .eq("id", conversation_id).execute()
            except Exception:
                pass

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

        # Backchannel only rescues an awkward silence. It goes through the
        # same live socket as the answer, so it is one continuous synthesis
        # rather than a pre-rendered clip spliced in front — that splice was
        # what made Kaia sound like two different voices.
        first_audio = asyncio.Event()

        async def _backchannel():
            try:
                await asyncio.wait_for(first_audio.wait(), timeout=s.voice_backchannel_after_s)
            except asyncio.TimeoutError:
                if first_audio.is_set():
                    return
                try:
                    sock = await _tts_socket()
                    await sock.send(json.dumps({"type": "Speak", "text": random.choice(_FILLERS)}))
                except Exception:
                    logger.exception("backchannel failed")

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

                logger.info("voice: Deepgram STT connected")

                async def receive_dg():
                    """Receive transcription results from Deepgram."""
                    async for msg in dg_ws:
                        data = json.loads(msg)
                        if data.get("type") == "Results":
                            alt = data.get("channel", {}).get("alternatives", [{}])[0]
                            transcript = alt.get("transcript", "")
                            # speech_final marks the end of an utterance;
                            # is_final only means that chunk won't be revised,
                            # which fires mid-sentence and answers fragments.
                            ended = data.get("speech_final", False) or (
                                data.get("is_final", False) and data.get("from_finalize", False)
                            )
                            if transcript:
                                logger.info(
                                    "voice: transcript%s '%s'",
                                    " FINAL" if ended else " interim", transcript[:120],
                                )
                                await process_transcript(transcript, ended)

                async def forward_audio():
                    """Forward audio from browser to Deepgram."""
                    total = 0
                    chunks = 0
                    while True:
                        msg = await ws.receive()
                        if msg.get("type") == "websocket.disconnect":
                            logger.info("voice: client disconnected after %d chunks / %d bytes", chunks, total)
                            break
                        if "bytes" in msg:
                            await dg_ws.send(msg["bytes"])
                            total += len(msg["bytes"])
                            chunks += 1
                            # Enough to confirm the mic is live without
                            # writing a line per 250ms chunk.
                            if chunks in (1, 10) or chunks % 100 == 0:
                                logger.info("voice: mic audio %d chunks / %d bytes", chunks, total)
                        elif "text" in msg:
                            data = json.loads(msg["text"])
                            if data.get("type") == "stop":
                                logger.info("voice: client sent stop")
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

    # A guest call gets the restricted registry and prompt. Decided here from
    # the URL Twilio was given, never from anything said on the call.
    guest_pass_id = (ws.query_params.get("guest") or "").strip()
    is_guest = bool(guest_pass_id)
    if is_guest:
        from app.services.tools.guest_tools import guest_registry as active_registry
        logger.info("call-media: GUEST call, pass=%s", guest_pass_id)
    else:
        from app.services.tool_registry import registry as active_registry

    db = get_supabase()
    stream_sid: str | None = None
    call_sid: str | None = None
    messages_history: list[dict] = []
    current_tts_task: asyncio.Task | None = None
    turns = 0

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

    # A guest hears a different Kaia: no memories about the owner, no
    # personal context, and only the guest tools.
    if is_guest:
        memory_lines = []

    GUEST_CALL_PROMPT = """You are Kaia, Tanishq Dahiya's assistant. You rang \
someone he gave an access code to — most likely a recruiter. You called them, \
so open by saying who you are and why in one short sentence.

## Phone rules
- One or two sentences at a time. This is spoken aloud.
- Never read out URLs, markdown, lists or code.
- No sign-offs. Just stop when you're done.
- If they go quiet, ask one short question rather than filling the silence.

## What you can do
Answer questions about Tanishq's work from your tools, email them his CV if \
they give you an address, or take a message for him.

## Rules you do not break
- Everything factual must come from a tool result. Never invent an employer, \
a date, or a technology he has used.
- You have no access to his calendar, his files, or his email beyond sending \
his CV to the address they give you.
- The call ends automatically after about two minutes. If you're close, say \
so and offer to email instead."""

    system_prompt = build_system_prompt(GUEST_CALL_PROMPT if is_guest else """You are Kaia — sharp, warm, a little witty. This is a phone call. Talk like a person.

## Phone rules
- One to two sentences max. Snappy.
- Don't read URLs aloud. Say "Done, I'll drop the link in the app."
- Never use markdown, lists, numbering, bold, code blocks, or asterisks.
- No sign-offs: "Happy driving!", "Enjoy!", "Have a great day!" — just stop.
- No filler: "Sure thing!", "Absolutely!", "Of course!" — just do the thing.
- No hedging: "Unfortunately", "I'm sorry but" — be straight.
- Match their energy. Rushed → snappy. Chatty → chat.

## How you work
- ACT FIRST. "Meeting at 11am" → call the tool. Today if no date, 30min default. Smart defaults, not questions.
- Only ask when you genuinely can't guess.
- Never "shall I proceed?" — just do it.
- Something is done ONLY if a tool call succeeded. Never say "scheduled",
  "sent" or "saved" unless the tool ran and came back clean — saying it
  does not make it so.
- If a tool errors, say what failed in one line. If it mentions an expired
  token, tell them to reconnect Google in Settings.
- Past dates: tell them, suggest the next one.
- Typos (gmial.com → gmail.com): fix silently.

## Tools
Calendar, email, CRM, weather, maps, memory. Use them — don't describe them.""", memory_lines)

    # Create a conversation for this call. The time makes calls tellable
    # apart straight away; the first thing said replaces it below.
    conversation_id: str = ""
    try:
        conv = db.table("conversations").insert({
            "org_id": org_id, "user_id": user_id,
            "mode": "voice",
            "title": f"Call · {datetime.now(timezone.utc).strftime('%H:%M')}",
        }).execute()
        conversation_id = conv.data[0]["id"]
        logger.info("call-media: conversation_id=%s", conversation_id)
    except Exception:
        logger.exception("call-media: failed to create conversation")

    # Same persistent-socket approach as the browser, but mulaw/8000 and
    # framed the way Twilio expects. Previously the whole reply was
    # generated, then synthesised, then sent — so nothing was heard until
    # everything was finished.
    phone_tts: object | None = None

    async def _phone_tts_socket():
        nonlocal phone_tts
        if phone_tts is not None:
            return phone_tts
        phone_tts = await websockets.connect(
            PHONE_TTS_WS_URL,
            additional_headers={"Authorization": f"Token {s.deepgram_api_key}"},
            max_size=None,
        )
        return phone_tts

    async def _drop_phone_tts():
        nonlocal phone_tts
        if phone_tts is not None:
            try:
                await phone_tts.close()
            except Exception:
                pass
            phone_tts = None

    async def stream_reply_to_call(messages, tool_exec) -> str:
        """Stream the model into the call, speaking as it writes."""
        client = get_async_openai()
        model = get_model_id(ModelTier.FAST)
        oai_tools = _convert_tools_for_openai(active_registry.list_definitions())

        oai_msgs: list[dict] = [{"role": "system", "content": system_prompt}]
        for m in messages:
            if isinstance(m.get("content"), str):
                oai_msgs.append({"role": m["role"], "content": m["content"]})

        try:
            sock = await _phone_tts_socket()
        except Exception:
            logger.exception("call-media: TTS socket failed")
            return ""

        async def pump():
            """Deepgram sends arbitrary-sized mulaw; Twilio wants ~20ms frames."""
            carry = b""
            try:
                async for frame in sock:
                    if isinstance(frame, bytes):
                        carry += frame
                        while len(carry) >= TWILIO_FRAME_BYTES and stream_sid:
                            chunk, carry = carry[:TWILIO_FRAME_BYTES], carry[TWILIO_FRAME_BYTES:]
                            await ws.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": base64.b64encode(chunk).decode()},
                            })
                    else:
                        evt = json.loads(frame)
                        if evt.get("type") == "Flushed":
                            if carry and stream_sid:
                                await ws.send_json({
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": base64.b64encode(carry).decode()},
                                })
                            return
                        if evt.get("type") == "Warning":
                            logger.warning("call-media TTS: %s", evt.get("description"))
            except Exception:
                logger.exception("call-media: TTS pump ended")

        pump_task = asyncio.create_task(pump())
        parts: list[str] = []

        try:
            for _turn in range(5):
                stream = await client.chat.completions.create(
                    model=model, messages=oai_msgs,
                    tools=oai_tools, stream=True,
                    **completion_params(model, VOICE_MAX_TOKENS, has_tools=bool(oai_tools)),
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
                        parts.append(d.content)
                        sbuf += d.content
                        if re.search(r"[.!?,;:]\s$|[.!?]$", sbuf) and len(sbuf) >= 12:
                            await sock.send(json.dumps({"type": "Speak", "text": sbuf}))
                            sbuf = ""
                    if d and d.tool_calls:
                        for tcd in d.tool_calls:
                            slot = tc_map.setdefault(tcd.index, {"id": "", "name": "", "args": ""})
                            if tcd.id:
                                slot["id"] = tcd.id
                            if tcd.function:
                                if tcd.function.name:
                                    slot["name"] = tcd.function.name
                                if tcd.function.arguments:
                                    slot["args"] += tcd.function.arguments

                if sbuf.strip():
                    await sock.send(json.dumps({"type": "Speak", "text": sbuf}))

                if finish != "tool_calls" or not tc_map:
                    break

                oai_msgs.append({
                    "role": "assistant", "content": text or None,
                    "tool_calls": [
                        {"id": tc_map[i]["id"], "type": "function",
                         "function": {"name": tc_map[i]["name"], "arguments": tc_map[i]["args"]}}
                        for i in sorted(tc_map)
                    ],
                })
                for i in sorted(tc_map):
                    tc = tc_map[i]
                    try:
                        args = json.loads(tc["args"]) if tc["args"] else {}
                    except json.JSONDecodeError:
                        args = {}
                    try:
                        result = await tool_exec(tc["name"], args)
                        content = result if isinstance(result, str) else json.dumps(result)
                    except Exception as e:
                        content = f"Error: {e}"
                    oai_msgs.append({"role": "tool", "tool_call_id": tc["id"], "content": content})

        except asyncio.CancelledError:
            pump_task.cancel()
            await _drop_phone_tts()
            raise
        except Exception:
            logger.exception("call-media: generation failed")
        finally:
            try:
                await sock.send(json.dumps({"type": "Flush"}))
                await asyncio.wait_for(pump_task, timeout=40)
            except Exception:
                pump_task.cancel()
                await _drop_phone_tts()

        reply = "".join(parts)
        if org_id and reply:
            await track_tts_usage(org_id, len(reply))
        return reply

    async def process_phone_transcript(transcript: str, is_final: bool):
        nonlocal messages_history, current_tts_task, turns

        if not is_final or not transcript.strip():
            return

        if turns >= MAX_PHONE_TURNS:
            if turns == MAX_PHONE_TURNS:
                logger.warning("call-media: hit %d turns — refusing to reply further", MAX_PHONE_TURNS)
                turns += 1
            return
        turns += 1

        logger.info("call-media: transcript #%d: '%s'", turns, transcript)

        # Name the thread after what the call was actually about.
        if turns == 1 and conversation_id:
            try:
                db.table("conversations").update({"title": transcript[:80]}) \
                    .eq("id", conversation_id).execute()
            except Exception:
                pass

        # No self-interruption: the mic hears Kaia's own voice down the line,
        # and cancelling on that made her cut herself off mid-sentence.
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
            result = await active_registry.execute(name, args, org_id=org_id or "", conversation_id=conversation_id)
            logger.info("call-media: tool result: %s", str(result)[:200])
            return result

        async def _run():
            reply = await stream_reply_to_call(messages_history, tool_executor)
            if not reply:
                return
            logger.info("call-media: reply: '%s'", reply[:200])
            messages_history.append({"role": "assistant", "content": reply})
            if conversation_id:
                try:
                    db.table("messages").insert({
                        "conversation_id": conversation_id,
                        "role": "assistant", "content": reply,
                    }).execute()
                except Exception:
                    pass

        current_tts_task = asyncio.create_task(_run())

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
