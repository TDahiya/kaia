# Setup Checklist — Kaia Personal AI Assistant

Complete these steps in order. Items marked **(optional)** can be skipped initially.

---

## 1. Supabase Project (FREE tier available)

- [ ] Create account at https://supabase.com
- [ ] Create a new project (any region, "kaia-assistant" or similar)
- [ ] From Project Settings → API:
  - Copy **Project URL** → `SUPABASE_URL`
  - Copy **anon/public key** → `SUPABASE_ANON_KEY`
  - Copy **service_role key** → `SUPABASE_SERVICE_ROLE_KEY`
- [ ] From Project Settings → Authentication:
  - Add your app's domain to "Redirect URLs" (e.g., `https://yourdomain.com/auth/callback`)
  - Enable Email auth provider
- [ ] Run the SQL migrations from `migrations/` in the SQL Editor (in order)

**Cost:** Free tier includes 500MB database, 50K monthly active users, 1GB storage.

---

## 2. Anthropic API Key (USAGE-BASED — primary cost)

- [ ] Create account at https://console.anthropic.com
- [ ] Generate an API key → `ANTHROPIC_API_KEY`
- [ ] Add billing/credits

**Cost estimate (personal use):**
- Haiku 5.5 (most requests): ~$0.10/$0.50 per MTok input/output
- Sonnet 5.5 (complex tasks): ~$2.00/$10.00 per MTok
- Opus 5.5 (rare): ~$4.00/$20.00 per MTok
- Typical personal use: $5–30/month depending on usage

---

## 3. Deepgram API Key (USAGE-BASED)

- [ ] Create account at https://console.deepgram.com
- [ ] Generate an API key → `DEEPGRAM_API_KEY`

**Cost:**
- STT (Nova-3 streaming): $0.0043/min
- TTS (Aura 2): $0.0070/1000 chars
- Free tier: $200 credit on signup
- Typical personal use: $2–10/month

---

## 4. Google OAuth Credentials (FREE)

- [ ] Go to https://console.cloud.google.com
- [ ] Create a project (e.g., "Kaia Assistant")
- [ ] Enable these APIs:
  - Google Calendar API
  - Gmail API
  - Google Sheets API
  - Google Docs API
- [ ] Create OAuth 2.0 credentials:
  - Application type: **Web application**
  - Authorized redirect URI: `https://yourdomain.com/api/auth/google/callback`
  - (For local dev: also add `http://localhost:8000/api/auth/google/callback`)
  - Copy **Client ID** → `GOOGLE_CLIENT_ID`
  - Copy **Client Secret** → `GOOGLE_CLIENT_SECRET`
- [ ] Configure OAuth consent screen:
  - User type: **External** (or Internal if using Google Workspace)
  - Add scopes:
    - `https://www.googleapis.com/auth/calendar`
    - `https://www.googleapis.com/auth/gmail.modify`
    - `https://www.googleapis.com/auth/spreadsheets`
    - `https://www.googleapis.com/auth/documents`
  - Add your email as a test user (required while in "Testing" mode)

**Note:** While in "Testing" mode, only listed test users can authorize. Publishing
requires Google verification (takes days/weeks) but is not needed for personal use.

**Cost:** Free. Google APIs have generous free quotas.

---

## 5. Telnyx Account + Irish Number (USAGE-BASED)

- [ ] Create account at https://portal.telnyx.com
- [ ] Add payment method
- [ ] Generate an API key (v2) → `TELNYX_API_KEY`
- [ ] Create a TeXML Application or Call Control Application:
  - Set webhook URL: `https://yourdomain.com/api/telephony/webhook`
  - Copy the **Connection ID** → `TELNYX_CONNECTION_ID`
- [ ] Search for and purchase an Irish number (+353):
  - Navigate to Numbers → Search & Buy
  - Country: Ireland
  - Copy the purchased number in E.164 format → `TELNYX_PHONE_NUMBER`
  - Assign it to your Call Control Application
- [ ] Note: Irish number availability and address verification requirements
  vary. Telnyx may require an Irish address for regulatory compliance.

**Cost:**
- Irish number: ~$1–3/month
- Inbound calls: ~$0.005–0.02/min
- Outbound calls (to Irish mobile): ~$0.02–0.10/min
- Typical personal use: $3–10/month

---

## 6. Hetzner VPS (MONTHLY — required for deployment)

- [ ] Create account at https://console.hetzner.cloud
- [ ] Create a cloud server:
  - Recommended: **CX22** (2 vCPU, 4GB RAM, 40GB SSD) — ~€4.35/month
  - OS: Ubuntu 24.04
  - Location: Falkenstein or Helsinki (close to EU for Irish number)
- [ ] Point your domain's A record to the server's IP
- [ ] SSH in and install Docker + Docker Compose

**Cost:** €4.35–8.50/month depending on tier chosen.

---

## 7. Domain + DNS (REQUIRED for HTTPS/webhooks)

- [ ] Register a domain or use an existing one
- [ ] Create an A record pointing to your Hetzner VPS IP
- [ ] Set `APP_BASE_URL` to `https://yourdomain.com`
- [ ] Set `GOOGLE_REDIRECT_URI` to `https://yourdomain.com/api/auth/google/callback`

**Cost:** ~$10–15/year for a domain, or free if you already have one.

---

## 8. Weather API (FREE)

- [ ] Create account at https://openweathermap.org
- [ ] Generate an API key → `OPENWEATHER_API_KEY`

**Cost:** Free tier: 1000 calls/day (more than enough).

---

## 9. Generate Encryption Key (FREE — do this locally)

Run this command to generate a Fernet encryption key for OAuth token storage:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output → `TOKEN_ENCRYPTION_KEY`

---

## 10. Set Your Owner Phone Number

- [ ] Set `OWNER_PHONE_E164` to your personal phone number in E.164 format
  - Example: `+353851234567` (Irish mobile)
  - This is the ONLY number the assistant can call outbound

---

## Environment Variables Summary

Create `.env` from `.env.example` and fill in:

| Variable | Source | Required |
|---|---|---|
| `SUPABASE_URL` | Supabase dashboard | Yes |
| `SUPABASE_ANON_KEY` | Supabase dashboard | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard | Yes |
| `ANTHROPIC_API_KEY` | Anthropic console | Yes |
| `DEEPGRAM_API_KEY` | Deepgram console | Yes |
| `GOOGLE_CLIENT_ID` | Google Cloud Console | Yes |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console | Yes |
| `GOOGLE_REDIRECT_URI` | Your domain + path | Yes |
| `TELNYX_API_KEY` | Telnyx portal | For phone |
| `TELNYX_PHONE_NUMBER` | Telnyx portal | For phone |
| `TELNYX_CONNECTION_ID` | Telnyx portal | For phone |
| `OWNER_PHONE_E164` | Your phone number | For phone |
| `APP_BASE_URL` | Your domain | Yes |
| `TOKEN_ENCRYPTION_KEY` | Generated locally | Yes |
| `OPENWEATHER_API_KEY` | OpenWeatherMap | Optional |
| `CLAUDE_MODEL_FAST` | Default: `claude-haiku-5-5` | No |
| `CLAUDE_MODEL_STANDARD` | Default: `claude-sonnet-5-5` | No |
| `CLAUDE_MODEL_PREMIUM` | Default: `claude-opus-5-5` | No |

---

## Monthly Cost Estimate (Personal Use)

| Service | Estimated Cost |
|---|---|
| Anthropic API | $5–30 |
| Deepgram | $2–10 |
| Telnyx | $3–10 |
| Hetzner VPS | €4.35–8.50 |
| Supabase | Free |
| Google APIs | Free |
| Weather API | Free |
| Domain | ~$1/month amortized |
| **Total** | **~$15–60/month** |

---

## Recommended Setup Order

1. Supabase (needed for development immediately)
2. Anthropic API key (core functionality)
3. Deepgram API key (voice features)
4. Google OAuth (integrations)
5. Generate encryption key
6. Weather API key
7. Telnyx (can be last — phone features work independently)
8. Domain + Hetzner VPS (deployment)
