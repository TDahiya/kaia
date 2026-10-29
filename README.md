# Kaia — Personal AI Voice Assistant

A personal AI assistant with a Vapi-inspired dashboard, real-time voice, phone integration, and Google workspace tools.

## Quick Start

### 1. Prerequisites

- Python 3.12+, Node.js 20+
- Supabase project (free tier works)
- Anthropic API key

### 2. Setup

```bash
cp .env.example .env
# Fill in your API keys

# Database
# Run migrations/001_initial_schema.sql in Supabase SQL editor

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
cp .env.local.example .env.local
# Fill in Supabase URL and anon key
npm install
npm run dev
```

### 3. Open

Visit `http://localhost:3000`. Sign up, then start chatting.

## Features

- **Text + Voice chat** — unified conversation with mode switching
- **AI brain** — Claude model routing (Haiku routine, Sonnet complex, Opus exceptional)
- **Voice** — Deepgram Nova-3 STT + Aura 2 TTS with barge-in
- **Phone** — Telnyx inbound/outbound (restricted to owner's number only)
- **Google** — Calendar, Gmail, Sheets CRM via OAuth 2.0
- **Memory** — 7-day retention, weekly summarization, manual management
- **Tools** — Weather, calendar, email, CRM, memory, phone
- **Cost tracking** — Per-provider usage with spend limits

## Deployment

```bash
# Set DOMAIN in Caddyfile
docker-compose up -d
```

See [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) for full account setup.
See [ARCHITECTURE.md](ARCHITECTURE.md) for system design.

## Security

- Outbound calls restricted to `OWNER_PHONE_E164` only
- OAuth tokens encrypted at rest (Fernet)
- Row Level Security on all database tables
- No API keys in frontend
