"""Local settings read from environment variables and an optional `.env` file.

The pseudonym salt is generated once on first use and stored in `.env`
(never committed). Without the same salt, pseudonyms cannot be linked back to
IMO numbers.
"""

from __future__ import annotations

import os
import secrets

from spa.paths import ROOT

ENV_FILE = ROOT / ".env"


def load_env() -> None:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def ensure_salt() -> str:
    load_env()
    salt = os.environ.get("SPA_PSEUDONYM_SALT")
    if not salt:
        salt = secrets.token_hex(16)
        with ENV_FILE.open("a", encoding="utf-8") as f:
            f.write(f"SPA_PSEUDONYM_SALT={salt}\n")
        os.environ["SPA_PSEUDONYM_SALT"] = salt
    return salt
