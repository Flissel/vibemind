"""
Send a Telegram notification using the existing VibeMind bot.

Reads TELEGRAM_BOT_TOKEN from `.env` at the repo root and posts to
chat_id from $TELEGRAM_CHAT_ID, falling back to the OpenFang
`channels.telegram.allowed_users[0]`; set TELEGRAM_CHAT_ID in .env.

Usage:
    python scripts/notify_telegram.py "Your message here"
    echo "Your message" | python scripts/notify_telegram.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_dotenv(env_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_path.is_file():
        return out
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    env = {**load_dotenv(repo / ".env"), **os.environ}

    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = env.get("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID).strip()

    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        return 1

    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
    else:
        # stdin MUSS als UTF-8 gelesen werden — auf Windows ist der Default
        # cp1252, was UTF-8-Umlaute zu Mojibake macht (AusfÃ¼hrung statt
        # Ausführung). Buffer direkt mit utf-8 dekodieren.
        try:
            raw = sys.stdin.buffer.read()
            message = raw.decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001 — Fallback auf den Default-Reader
            message = sys.stdin.read().strip()

    if not message:
        print("ERROR: empty message", file=sys.stderr)
        return 1

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": message}
    ).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read())
    except Exception as exc:
        print(f"ERROR: telegram api request failed: {exc}", file=sys.stderr)
        return 2

    if not payload.get("ok"):
        print(f"ERROR: telegram api returned: {payload}", file=sys.stderr)
        return 3

    # stdout = message_id der gesendeten Nachricht (für Reply-Korrelation, z.B.
    # SoM message_id->run_id-Mapping). Fallback "ok" falls die API sie mal nicht
    # liefert. Exit 0 bleibt unverändert (abwärtskompatibel).
    message_id = (payload.get("result") or {}).get("message_id")
    print(message_id if message_id is not None else "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
