#!/usr/bin/env python3
"""Tell you exactly what is and isn't configured, before you hit a 500.

    python scripts/check_env.py

Reads backend/.env and frontend/.env.local directly, so it works before
any dependencies are installed. Deliberately plain ASCII with no colour:
a default Windows console is cp1252 and crashes on box-drawing glyphs.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK, BAD, WARN, SKIP = "[ok]", "[--]", "[!!]", "[  ]"
RULE = "-" * 58

REQUIRED = {
    "SUPABASE_URL": "Supabase > Project Settings > API",
    "SUPABASE_ANON_KEY": "Supabase > Project Settings > API",
    "SUPABASE_SERVICE_ROLE_KEY": "Supabase > Project Settings > API (secret)",
    "OPENAI_API_KEY": "platform.openai.com > API keys",
    "TOKEN_ENCRYPTION_KEY": "run: python scripts/new_key.py",
}

# All-or-nothing groups: half a group is a feature that fails strangely.
FEATURES = {
    "Voice (browser + phone)": ["DEEPGRAM_API_KEY"],
    "Calendar / Gmail / Docs": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
    "Phone calls": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                    "TWILIO_PHONE_NUMBER", "OWNER_PHONE_E164"],
    "Weather and maps": ["GOOGLE_MAPS_API_KEY"],
    "Guest portal relay": ["GUEST_RELAY_TO"],
}

FRONTEND = ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
            "NEXT_PUBLIC_BACKEND_URL"]

PLACEHOLDERS = ("your-", "https://your-project.supabase.co", "sk-proj-xxx")


def read_env(path):
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def is_set(value):
    return bool(value) and not value.startswith(PLACEHOLDERS)


def main():
    backend_env = ROOT / "backend" / ".env"
    frontend_env = ROOT / "frontend" / ".env.local"
    problems = []

    print()
    print("  Kaia configuration check")
    print("  " + RULE)

    if not backend_env.is_file():
        print(f"  {BAD} backend/.env is missing")
        print("       copy .env.example to backend/.env and fill it in")
        problems.append("backend/.env")
    env = read_env(backend_env)

    print()
    print("  Required")
    for key, hint in REQUIRED.items():
        if is_set(env.get(key, "")):
            print(f"    {OK} {key:<27} set")
        else:
            print(f"    {BAD} {key:<27} {hint}")
            problems.append(key)

    print()
    print("  Optional features")
    for label, keys in FEATURES.items():
        have = [k for k in keys if is_set(env.get(k, ""))]
        if not have:
            print(f"    {SKIP} {label:<27} off - not configured")
        elif len(have) == len(keys):
            print(f"    {OK} {label:<27} on")
        else:
            missing = ", ".join(k for k in keys if k not in have)
            print(f"    {WARN} {label:<27} partly set - missing {missing}")
            problems.append(label)

    print()
    print("  Frontend")
    if not frontend_env.is_file():
        print(f"    {BAD} frontend/.env.local is missing")
        print("         copy frontend/.env.local.example to frontend/.env.local")
        problems.append("frontend/.env.local")
    else:
        fe = read_env(frontend_env)
        for key in FRONTEND:
            if is_set(fe.get(key, "")):
                print(f"    {OK} {key}")
            else:
                print(f"    {BAD} {key}")
                problems.append(key)

    # The classic "it keeps redirecting to localhost" bug.
    redirect = env.get("GOOGLE_REDIRECT_URI", "")
    base = env.get("APP_BASE_URL", "")
    if redirect and base and not redirect.startswith(base):
        print()
        print(f"  {WARN} GOOGLE_REDIRECT_URI does not match APP_BASE_URL")
        print(f"       redirect: {redirect}")
        print(f"       base:     {base}")
        print("       Google sends users to the host in the redirect URI, and")
        print("       that exact URI must also be registered in Google Cloud Console.")
        problems.append("GOOGLE_REDIRECT_URI")

    print()
    print("  " + RULE)
    if problems:
        print(f"  {len(problems)} item(s) need attention.")
        print("  Required items block startup. Optional ones only turn a feature off.")
        print()
        return 1
    print("  All good. Start the backend, then the frontend.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
