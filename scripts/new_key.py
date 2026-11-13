#!/usr/bin/env python3
"""Print a TOKEN_ENCRYPTION_KEY.

    python scripts/new_key.py

This key encrypts stored Google OAuth tokens. Generate it once and keep
it: change it later and every saved token becomes undecryptable, so the
Google connection has to be redone.
"""

import sys

try:
    from cryptography.fernet import Fernet
except ImportError:
    print("cryptography isn't installed yet. From the repo root:")
    print("    pip install -r backend/requirements.txt")
    print("or just:")
    print("    pip install cryptography")
    sys.exit(1)

print(Fernet.generate_key().decode())
