# Kaia — Architecture

## System Overview

```
Browser ──► Next.js (3000) ──► FastAPI (8000) ──► Claude API
                │                    │               │
                │                    ├── Deepgram STT/TTS
                │                    ├── Google APIs
                │                    ├── Telnyx Call Control
                │                    └── OpenWeatherMap
                │                    │
                └── Supabase Auth ◄──┴── Supabase PostgreSQL
```

## Backend (`backend/`)

**FastAPI + Python 3.12**

- `app/main.py` — App entrypoint, lifespan, CORS, router wiring, APScheduler for weekly summarization
- `app/config.py` — Pydantic Settings loaded from `.env`
- `app/auth.py` — Supabase JWT validation middleware
- `app/database.py` — Supabase client (service_role and anon)
- `app/encryption.py` — Fernet encryption for OAuth token storage

### Services

- `services/ai_brain.py` — Model routing (Haiku/Sonnet/Opus), complexity classification, tool loop with loop detection
- `services/tool_registry.py` — Extensible tool registry with categories
- `services/usage_tracker.py` — Per-provider cost tracking (LLM, STT, TTS, telephony)
- `services/google_auth.py` — OAuth 2.0 flow, token encryption/refresh
- `services/memory_summarizer.py` — Weekly conversation digest → durable memories

### Tools (`services/tools/`)

| Tool | Category | Confirmation Required |
|------|----------|----------------------|
| `get_weather` | Weather | No |
| `search_memories` | Memory | No |
| `add_memory` | Memory | No |
| `update_memory` | Memory | No |
| `delete_memory` | Memory | No |
| `list_calendar_events` | Google Calendar | No |
| `check_calendar_availability` | Google Calendar | No |
| `create_calendar_event` | Google Calendar | Yes |
| `cancel_calendar_event` | Google Calendar | Yes |
| `search_emails` | Gmail | No |
| `read_email` | Gmail | No |
| `create_email_draft` | Gmail | No |
| `send_email` | Gmail | Yes |
| `crm_add_or_update_contact` | Sheets CRM | No |
| `crm_search_contacts` | Sheets CRM | No |
| `call_owner` | Phone | Yes |

### Routes

- `/api/chat` — Text chat with tool loop
- `/api/agents` — Agent CRUD + clone
- `/api/memories` — Memory management + manual summarize
- `/api/usage` — Cost tracking + call logs
- `/api/auth/google` — OAuth flow
- `/api/telephony/webhook` — Telnyx webhook handler
- `/api/health`, `/api/system-status`
- `/ws/voice` — Browser voice (Deepgram streaming)
- `/ws/call-media` — Phone voice (Telnyx media → Deepgram)

## Frontend (`frontend/`)

**Next.js 15 + TypeScript + Tailwind CSS v4**

- `lib/supabase.ts` — Browser Supabase client
- `lib/api.ts` — Typed API client with auth token injection
- `lib/auth-context.tsx` — React auth context (user/session/loading)
- `components/sidebar.tsx` — Navigation with 10 routes

### Pages

| Route | Description |
|-------|-------------|
| `/login` | Auth (sign in / sign up) |
| `/dashboard` | Overview cards, status, cost breakdown |
| `/dashboard/chat` | Unified text + voice chat |
| `/dashboard/agents` | Agent list with create/clone/delete |
| `/dashboard/agents/[id]` | Agent editor |
| `/dashboard/memories` | Memory browser + weekly summaries |
| `/dashboard/voice` | Voice info (links to chat) |
| `/dashboard/phone` | Phone config + call history |
| `/dashboard/usage` | Spend tracking + provider breakdown |
| `/dashboard/settings` | Google OAuth + system config |
| `/dashboard/tools` | Tool registry display |
| `/dashboard/knowledge` | Knowledge base info |

## Database (Supabase PostgreSQL)

13 tables with org-scoped RLS. See `migrations/001_initial_schema.sql`.

## Security

- Phone calls restricted to `OWNER_PHONE_E164` only (`call_owner` tool)
- OAuth tokens encrypted with Fernet
- Row Level Security on all tables
- JWT auth on all API routes
- No secrets in frontend bundle

## Deployment

Docker Compose with Caddy reverse proxy. `docker-compose up -d` on Hetzner VPS.
Set `DOMAIN=yourdomain.com` for automatic HTTPS via Caddy.
