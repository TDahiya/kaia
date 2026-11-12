# Guest knowledge base

Everything the guest portal knows. Plain markdown, loaded at request time —
edit and the next answer uses it, no redeploy. Sections marked TODO are for
Tanishq to complete; everything else is accurate as of November 2026.

---

## [about] Who Tanishq is

Tanishq Dahiya. Final-year student at Dublin City University, based in Dublin,
Ireland. Looking for AI / ML engineering roles.

Contact: tanishq.dahiya2@mail.dcu.ie

TODO — add in your own words:
- Degree title and expected graduation
- Any internships or work experience, with dates and what you actually did
- Languages and frameworks you'd claim in an interview, honestly rated
- What you want to work on next, and what you'd rather avoid

## [freetime] Outside work

TODO — a few genuine lines. People ask this and a blank answer is worse than
a plain one. Cars come up in your own conversations; say something real.

---

## [kaia] The project you are talking to

Kaia is a personal AI assistant: text chat, browser voice, real phone calls,
calendar and email actions, and spreadsheet analysis. It runs in production on
a single Hetzner VPS behind nginx, not on a laptop.

**Stack.** FastAPI (Python 3.14) backend, Next.js 16 frontend with Tailwind v4,
Supabase for Postgres and auth, OpenAI for the models, Deepgram for speech in
both directions, Twilio for telephony.

**Model routing.** Requests are classified and sent to a tier — a cheap model
for routine work, a stronger one for harder reasoning. Voice is pinned to the
fast model on purpose: on a call, time-to-first-token is what you hear as lag,
so latency beats raw capability there.

## [documents] Why spreadsheets do not go through RAG

The obvious design is to embed an uploaded spreadsheet and retrieve chunks.
That is wrong, and the reason is worth stating plainly: retrieval returns text
that *looks* like the answer. Ask "total spend over €5,000" and the model gets
a handful of rows and produces a confident, invented number.

So spreadsheets do not go near the vector path. The model inspects the real
schema, writes pandas, and the code runs against the actual file in a
subprocess. The number is computed, not recalled. Prose still uses retrieval,
because prose genuinely does chunk well.

The sandbox runs with `python -I`, a scrubbed environment, an empty working
directory, and rlimits on CPU, address space and file size, with the parent
killing anything that overruns. Verified behaviour: a runaway loop is killed by
the CPU limit, a 4GB allocation dies as MemoryError, and a bad column name
returns a clean error to the model instead of a confident wrong answer.

## [voice] Making the voice sound like a person

The first version called Deepgram's HTTP endpoint once per sentence. Two
problems, neither obvious until you listen: every request paid a fresh TLS
handshake, and every sentence was a separate synthesis with its own intonation
curve. The result sounded like clips stitched together.

It now holds one WebSocket open per session and streams LLM text into it as the
model writes, so one continuous synthesis comes back. Measured on the server:
first audio at 0.20s, consistent across turns on a reused socket.

A detail that mattered more than the architecture: turn-taking originally keyed
off Deepgram's `is_final`, which only means a chunk will not be revised — it
fires mid-sentence. The assistant was answering fragments. Switching to
`speech_final` fixed it.

## [safety] What it refuses to do

Outbound calls can only reach one number, validated as E.164 and enforced in
backend code. No prompt can redirect it, because the model never supplies the
destination.

Phone calls run answering-machine detection. Without it the assistant
cheerfully held a twelve-turn conversation with a voicemail system, answering
each prompt at the cost of a model call and speech synthesis every time. There
is also a hard turn cap per call as a backstop.

This guest portal has its own tool allowlist. It cannot send arbitrary email,
place calls to arbitrary numbers, write to memory, or execute code against
anything but a file the guest uploaded themselves.

## [stack] Notable engineering decisions

- Streaming chat over SSE, so text appears as it is generated rather than
  arriving in one block when the model finishes.
- Google tokens: expiry is recorded at exchange time. Omitting it is a silent
  failure, because google-auth reports `expired=False` when it has no expiry,
  so the refresh token is never used and access dies after an hour.
- Documents are stored on disk with signed download URLs — a link clicked from
  a chat bubble cannot carry an auth header.
- Every limit that matters is enforced in code, never in a prompt.

---

## [hiring] What to take from this

TODO — one short paragraph in your own voice: what you want someone to conclude
about you after using this. Keep it specific and avoid adjectives.
