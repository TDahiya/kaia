#!/usr/bin/env python3
"""Set a Supabase account's password directly, using the service role key.

    python scripts/set_password.py admin@kaia.local

Needed because admin@kaia.local is not a deliverable address, so the normal
"forgot password" email can never arrive. The password is typed at a hidden
prompt and never appears in a shell history, a log, or on screen.

Run it from the repo root with backend/.env present.
"""

import getpass
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_env(path):
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def api(url, key, path, method="GET", body=None):
    req = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=json.dumps(body).encode() if body else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise SystemExit(f"Supabase said {e.code}: {detail}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    email = sys.argv[1].strip().lower()

    env = read_env(ROOT / "backend" / ".env")
    url = env.get("SUPABASE_URL", "")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise SystemExit("backend/.env needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")

    data = api(url, key, "/auth/v1/admin/users?per_page=200")
    users = data.get("users", data if isinstance(data, list) else [])
    match = next((u for u in users if (u.get("email") or "").lower() == email), None)
    if not match:
        known = ", ".join(sorted((u.get("email") or "?") for u in users))
        raise SystemExit(f"No account for {email}.\nAccounts that exist: {known}")

    print(f"Setting a new password for {email}")
    first = getpass.getpass("New password (hidden): ")
    if len(first) < 8:
        raise SystemExit("Use at least 8 characters.")
    if first != getpass.getpass("Again: "):
        raise SystemExit("They didn't match. Nothing changed.")

    api(url, key, f"/auth/v1/admin/users/{match['id']}", "PUT", {"password": first})
    print(f"\nDone. Sign in at /login as {email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
