# Architecture

How Kaia is put together, and why the awkward parts are the way they are.

---

## The shape of it

```
                    ┌───────────────────────────────┐
                    │  Next.js 16  (frontend)       │
                    │                               │
                    │  /overview /chat /agents ...  │  signed-in dashboard
                    │  /try                         │  code-gated guest portal
                    │  /login                       │
                    └───────┬───────────────┬───────┘
                            │ HTTP + SSE    │ WebSocket
                            v               v
                    ┌───────────────────────────────┐
                    │  FastAPI  (backend)           │
                    │                               │
   routes/          │  chat   voice   guest         │
                    │  documents  telephony  agents │
                    ├───────────────────────────────┤
   services/        │  ai_brain      tool_registry  │
                    │  documents     guest_passes   │
                    │  google_auth   exporters      │
                    └───┬────┬────┬────┬────┬───────┘
                        │    │    │    │    │
             OpenAI ◄───┘    │    │    │    └──► subprocess
           Deepgram ◄────────┘    │    │         (pandas sandbox,
             Twilio ◄─────────────┘    │          unprivileged user)
           Supabase ◄──────────────────┘
          (Postgres + auth + RLS)
```

Two separate surfaces share one backend:

- **The dashboard** is the owner's. Full tool registry, full history.
- **The guest portal** is for people given an access code. Separate
  registry, separate prompt, metered quota. It cannot reach the owner's
  tools, memories, documents or calendar.

---

## A request, end to end

Text chat, `POST /api/chat/stream`:

1. `_prepare_turn` resolves the conversation, adopts any attachments,
   stores the user message, and assembles the prompt from the agent's
   instructions, stored memories, and a list of attached files.
2. `classify_complexity` picks a model tier from the message.
3. The handler streams from OpenAI. Text deltas go straight out as SSE,
   so the UI renders as the model writes.
4. If the model calls a tool, the registry executes it, the result is
   appended, and the loop runs again — up to six times.
5. The finished reply is stored and a `done` event carries the model,
   token counts and which tools ran.

Voice follows the same shape with speech on both ends. The notable
difference is that text deltas are also pushed into a **live TTS socket**
as they arrive, so speech starts before the model has finished writing.

---

## Decisions worth explaining

### Spreadsheets do not go through a vector database

The obvious design is to embed an uploaded spreadsheet and retrieve
chunks. It is wrong, and the failure is quiet: retrieval returns text
that *looks* like an answer. Ask for "total spend over 5,000" and the
model receives a handful of rows and produces a confident, invented
number.

So tabular files skip retrieval entirely. The model inspects the real
schema, writes pandas, and the code runs against the actual file in a
subprocess. The figure is computed, not recalled. Prose still uses
retrieval, because prose genuinely does chunk well.

### The sandbox, and what it is actually for

`services/sandbox_runner.py` is executed as a subprocess, never
imported. It runs with `python -I` (no env, no cwd on the import path),
an empty working directory, and rlimits on CPU, address space, file size
and process count.

For guest-supplied files it additionally drops to an unprivileged user,
because the API process runs as root and otherwise model-written code
could read `backend/.env`. Verified behaviour: a runaway loop is killed
by the CPU limit, a 4GB allocation raises `MemoryError`, a fork bomb hits
`BlockingIOError`, and reading `.env` raises `PermissionError`.

One sharp edge worth knowing: `RLIMIT_NPROC` must not be zero. Root
ignores it, so the owner path works, but an unprivileged child cannot
start OpenBLAS threads and `import pandas` dies before any user code
runs.

### One persistent TTS socket, not one request per sentence

The first version called the speech API once per sentence. Every call
paid a fresh TLS handshake, and every sentence was synthesised
separately with its own intonation curve, so the result sounded like
clips stitched together.

Now a single WebSocket stays open and LLM text is streamed into it.
Measured on the server: first audio at 0.20s, consistent across turns on
a reused socket.

Turn-taking keys off Deepgram's `speech_final`, not `is_final`.
`is_final` only means a chunk will not be revised — it fires mid-sentence,
and the assistant ends up answering fragments.

### Model differences live in one function

`ai_brain.completion_params()` is the only place that knows how model
families differ. The gpt-6 family renamed `max_tokens` to
`max_completion_tokens` and refuses function tools on
`/v1/chat/completions` unless reasoning is switched off. Scattering that
across the five call sites would mean a new family breaks the app in five
places.

### Limits are enforced in code, never in a prompt

A prompt is the first thing a visitor attacks. So:

- Outbound calls can only reach `OWNER_PHONE_E164`, validated as E.164 in
  backend code. The model never supplies the destination.
- Guest passes carry message and call quotas checked server-side, plus a
  global daily ceiling.
- The guest registry is a separate object. There is no path from a guest
  request to the owner's tools.
- Guest email is two fixed templates. The model can choose the recipient
  (their own address) or the body (a message to the owner), never both —
  which is what would make it a spam relay.

---

## Where the seams are

Honest notes for anyone reading the code:

- **`routes/voice.py` is the biggest file** and holds two handlers: the
  browser socket and the Twilio media socket. They share a shape but not
  code, because the encodings differ (PCM at 24kHz versus mulaw at 8kHz
  in 20ms frames). Merging them would help; it has not been done.
- **Tool modules self-register on import.** `main.py` imports them for
  the side effect. Convenient, but it means import order matters.
- **Documents are stored on local disk**, not object storage. Fine for a
  single VPS; it would need changing to run more than one instance.
- **The deploy is file copy over SSH**, not CI. `deploy/` holds the
  systemd units and nginx config for reference.

---

## Database

Postgres via Supabase, row-level security on. The backend uses the
service role and does its own authorisation.

| Table | Holds |
|---|---|
| `organizations`, `users` | tenancy and identity |
| `agents` | per-agent prompt, models, voice |
| `conversations`, `messages` | chat and call transcripts |
| `memories`, `weekly_summaries` | long-term recall |
| `documents` | uploaded and generated files |
| `integrations` | encrypted OAuth tokens |
| `phone_numbers`, `call_logs` | telephony |
| `guest_passes`, `guest_events` | access codes and their usage |
| `usage_events`, `tool_executions` | cost and audit |
| `app_settings` | runtime config that overrides env |

Schema lives in `migrations/`, numbered. `all.sql` is every migration
combined and is safe to re-run.
