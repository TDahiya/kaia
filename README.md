# Kaia

A personal AI assistant that runs on your own server. Text chat, voice in
the browser, real phone calls, calendar and email actions, and spreadsheet
analysis that computes answers instead of guessing at them.

Live: [kaia-ai.duckdns.org](https://kaia-ai.duckdns.org)

---

## Run it locally

You need **four API keys** to get chat working. Everything else is
optional and switches itself off if you leave it blank.

Prerequisites: Python 3.12+, Node 20+, and a free Supabase project.

### 1. Database

Open your Supabase project, go to the **SQL Editor**, and paste the whole
of [`migrations/all.sql`](migrations/all.sql). That is every migration in
order. It is safe to run more than once.

### 2. Backend

```bash
cd backend
python -m venv venv
venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
python ../scripts/new_key.py    # paste the output into TOKEN_ENCRYPTION_KEY
```

Fill in the four required values in `backend/.env`:

| Variable | Where it comes from |
|---|---|
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `OPENAI_API_KEY` | platform.openai.com → API keys |

Then:

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in the Supabase URL and anon key
npm run dev
```

Open <http://localhost:3000>.

### Check your setup

```bash
python scripts/check_env.py
```

It lists exactly what is set, what is missing, and which features are
switched off as a result — rather than letting you find out through a 500.

---

## Optional features

Each one is independent. Leave the keys blank and the feature is simply
absent; nothing else breaks.

| Feature | Needs | Notes |
|---|---|---|
| Voice (browser + phone) | `DEEPGRAM_API_KEY` | Speech in and out |
| Calendar, Gmail, Docs | Google OAuth client | See the note below |
| Phone calls | Twilio account + number | Only ever dials `OWNER_PHONE_E164` |
| Weather and maps | `GOOGLE_MAPS_API_KEY` | |
| Guest portal | `GUEST_RELAY_TO` | Code-gated demo at `/try` |

### Google sign-in, if you want calendar and email

This is the step people get stuck on. In
[Google Cloud Console](https://console.cloud.google.com) → **APIs &
Services** → **Credentials**, create an OAuth client and add this exact
redirect URI:

```
http://localhost:8000/api/auth/google/callback
```

It must match `GOOGLE_REDIRECT_URI` in your `.env` character for
character. If they differ you get sent to a host that isn't listening,
which looks like *"localhost refused to connect"* after you click
Connect.

Also set the app's publishing status to **In production**. Apps left in
*Testing* get refresh tokens that expire after seven days, so the
connection silently dies about a week later.

---

## How it fits together

```
Next.js 16  ──HTTP/SSE──>  FastAPI  ──>  OpenAI        (chat, tools)
(frontend)  ──WebSocket─>  (backend) ──>  Deepgram     (speech both ways)
                                     ──>  Twilio       (phone calls)
                                     ──>  Supabase     (Postgres + auth)
                                     ──>  subprocess   (pandas sandbox)
```

[`ARCHITECTURE.md`](ARCHITECTURE.md) has the detail: request flow, the
tool registry, how the sandbox is isolated, and why spreadsheets don't go
through a vector database.

---

## Layout

```
backend/app/
  routes/      HTTP and WebSocket endpoints, one file per area
  services/    the work: model routing, tools, documents, voice, guest
  services/tools/   one module per tool group, self-registering
frontend/src/
  app/(app)/   the signed-in dashboard
  app/try/     the public code-gated guest portal
  components/  shared UI
migrations/    SQL, numbered; all.sql is all of them combined
scripts/       setup helpers
```

## Tests

Several modules carry a self-check. Run them as modules from `backend/`,
so their imports resolve:

```bash
cd backend
python -m app.services.phone_check     # which numbers may be dialled
python -m app.services.exporters       # docx / pdf / xlsx generation
python -m app.services.app_settings    # E.164 normalisation
python -m app.services.guest_passes    # access-code signing
```

Each prints `ok` or raises. They need no API keys and no database.

## Licence

MIT.
