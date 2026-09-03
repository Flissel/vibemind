"""Approval Callback Poller — Telegram inline-button approvals without inbound HTTP.

Closes the desktop-approval loop the secure, reachable-from-anywhere way:
handoff_approval_request (in document-mcp) sends an "Approval-Anfrage" with two
INLINE BUTTONS carrying callback_data 'approve:<clarify_id>' / 'decline:<clarify_id>'.
This poller long-polls getUpdates for callback_query, writes the decision into
clarify.db (status='answered', answer={'_choice': 'Approve'|'Decline'}), and
answers the callback to clear the phone's button spinner. The blocking poll
inside handoff_approval_request then unblocks on the next DB read — no inbound
HTTP, no firewall hole, no tunnel; works on mobile data.

WHY A DEDICATED BOT — Bot-token exclusivity: Telegram getUpdates is EXCLUSIVE
per bot token. OpenFang already polls @VibeMind_agent_bot (TELEGRAM_BOT_TOKEN).
This poller MUST use its OWN bot → env APPROVAL_TELEGRAM_BOT_TOKEN. If unset it
aborts with a clear message (instead of stealing OpenFang's updates). The
approval message (clarify_notify._telegram_notify) is sent via that SAME token
so the callbacks come back here. Mirrors scripts/som_telegram_poll.py.

Setup (once):
  1. @BotFather → new bot → token.
  2. .env:  APPROVAL_TELEGRAM_BOT_TOKEN=...   (chat_id from TELEGRAM_CHAT_ID)
  3. Run this poller as a background process (Scheduled Task / vibemind-start).
  4. Restart OpenFang so document-mcp sees APPROVAL_TELEGRAM_BOT_TOKEN and
     switches to callback_data buttons + fail-safe default.

Test mode: APPROVAL_POLL_ONCE=1 → one getUpdates, then exit.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

_REPO = Path(__file__).resolve().parents[1]  # Vibemind_V1/
_CLARIFY_NOTIFY = (
    _REPO / "vibemind-os" / "spaces" / "desktop" / "Automation_ui"
    / "backend" / "moire_agents" / "agents" / "handoff" / "clarify_notify.py"
)
_OFFSET_FILE = _REPO / "scripts" / "_state" / "approval_telegram_offset.json"

POLL_TIMEOUT = 25  # long-poll seconds
ALLOWED_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _token() -> str:
    env = {**_load_dotenv(_REPO / ".env"), **os.environ}
    # ONLY the dedicated approval bot — never the OpenFang bot (avoid update theft).
    return env.get("APPROVAL_TELEGRAM_BOT_TOKEN", "").strip()


def _load_clarify_notify():
    """Import the SAME clarify_notify module document-mcp uses, so we write to
    the exact clarify.db the blocking poll reads (record_clarify_answer)."""
    spec = importlib.util.spec_from_file_location("clarify_notify_poll", _CLARIFY_NOTIFY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_offset() -> int:
    try:
        return int(json.loads(_OFFSET_FILE.read_text(encoding="utf-8")).get("offset", 0))
    except Exception:  # noqa: BLE001
        return 0


def _write_offset(offset: int) -> None:
    _OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _OFFSET_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"offset": offset}), encoding="utf-8")
    tmp.replace(_OFFSET_FILE)


def _get_updates(token: str, offset: int) -> list[dict]:
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {
        "offset": offset,
        "timeout": POLL_TIMEOUT,
        "allowed_updates": json.dumps(["callback_query"]),
    }
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
        payload = json.loads(resp.read())
    return payload.get("result", []) if payload.get("ok") else []


def _answer_callback(token: str, callback_query_id: str, text: str) -> None:
    """Clear the phone's button spinner with a short toast."""
    try:
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        data = urllib.parse.urlencode(
            {"callback_query_id": callback_query_id, "text": text}
        ).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception as e:  # noqa: BLE001
        print(f"[approval-poll] answerCallbackQuery failed: {e}", file=sys.stderr)


def _handle_callback(cq: dict, token: str, cn) -> None:
    chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
    if ALLOWED_CHAT and chat_id and chat_id != str(ALLOWED_CHAT):
        return  # only the allowed user may approve
    data = (cq.get("data") or "").strip()
    if ":" not in data:
        return
    action, _, clarify_id = data.partition(":")
    action = action.lower()
    clarify_id = clarify_id.strip()
    if action not in ("approve", "decline") or not clarify_id:
        return
    choice = "Approve" if action == "approve" else "Decline"
    try:
        cn.record_clarify_answer(clarify_id, {"_choice": choice})
        print(f"[approval-poll] {clarify_id}: {choice} → clarify.db")
    except Exception as e:  # noqa: BLE001
        print(f"[approval-poll] record_clarify_answer failed for {clarify_id}: {e}", file=sys.stderr)
    _answer_callback(token, cq.get("id", ""),
                     "✅ Freigegeben" if choice == "Approve" else "❌ Abgelehnt")


def main() -> int:
    token = _token()
    if not token:
        print("ERROR: APPROVAL_TELEGRAM_BOT_TOKEN nicht gesetzt.\n"
              "Der Approval-Callback-Poller braucht einen EIGENEN Bot (getUpdates ist\n"
              "exklusiv pro Token — der OpenFang-Bot TELEGRAM_BOT_TOKEN darf nicht doppelt\n"
              "gepollt werden).\n"
              "Setup: @BotFather → neuer Bot → APPROVAL_TELEGRAM_BOT_TOKEN=... in .env.",
              file=sys.stderr)
        return 2

    cn = _load_clarify_notify()
    offset = _read_offset()
    print(f"[approval-poll] gestartet (offset={offset}, chat={ALLOWED_CHAT}). "
          f"Lausche auf Approve/Decline-Callbacks…")
    once = os.environ.get("APPROVAL_POLL_ONCE") in ("1", "true", "True")
    while True:
        try:
            updates = _get_updates(token, offset)
            for upd in updates:
                offset = max(offset, upd.get("update_id", 0) + 1)
                cq = upd.get("callback_query")
                if not cq:
                    continue
                try:
                    _handle_callback(cq, token, cn)
                except Exception as e:  # noqa: BLE001 — one bad update must not kill the poller
                    print(f"[approval-poll] update-Fehler: {e}", file=sys.stderr)
            if updates:
                _write_offset(offset)
        except Exception as e:  # noqa: BLE001 — net error → short wait, continue
            print(f"[approval-poll] poll-Fehler: {e}", file=sys.stderr)
            time.sleep(5)
        if once:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
