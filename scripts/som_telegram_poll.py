"""SoM-Planner — Telegram Reply-Poller (Inbound-Bridge, Phase 5 Schritt 4).

Schließt den Telegram-Loop EINGEHEND: lauscht via Telegram getUpdates auf
Antworten (Replies) zu SoM-Frage-Nachrichten und nimmt den zugehörigen Run
automatisch wieder auf.

Korrelation: Beim ausgehenden Frage-Push (notify.py) wird die message_id der
Frage-Nachricht in state/answers_map.json als message_id->run_id gemerkt. Eine
Reply trägt reply_to_message_id → wir schlagen den Run nach → resume.

WICHTIG — Bot-Token-Exklusivität: Telegram getUpdates ist EXKLUSIV pro Bot-Token.
OpenFang pollt bereits @VibeMind_agent_bot (TELEGRAM_BOT_TOKEN). Dieser Poller
MUSS daher einen EIGENEN Bot benutzen → env SOM_TELEGRAM_BOT_TOKEN. Ist der nicht
gesetzt, bricht der Poller mit klarer Meldung ab (statt OpenFang die Updates
wegzuschnappen). Der Frage-Push (notify.py) nutzt denselben SOM-Bot, damit
Replies hier ankommen.

Setup (einmalig):
  1. Bei @BotFather einen zweiten Bot anlegen → Token.
  2. In .env:  SOM_TELEGRAM_BOT_TOKEN=...   (chat_id aus SOM_TELEGRAM_CHAT_ID)
  3. Diesen Poller als Hintergrund-Prozess starten (Scheduled Task / vibemind-start).

Antwort-Format vom Handy (Reply auf die Frage-Nachricht):
    1: AI-Vollzeit Konzern   2: ja        → answers {"1": "...", "2": "ja"}
    x                                     → Run abbrechen
    (Freitext ohne Nummern)               → als Antwort auf Frage 1
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

_REPO = Path(__file__).resolve().parents[1]                       # Vibemind_V1/
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"
_VENV_PY = _REPO / "vibemind-os" / "voice" / ".venv312" / "Scripts" / "python.exe"
_OFFSET_FILE = _PLANNER / "state" / "telegram_offset.json"

POLL_TIMEOUT = 25          # long-poll seconds
ALLOWED_CHAT = os.environ.get("SOM_TELEGRAM_CHAT_ID", "")


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


def _state():
    spec = importlib.util.spec_from_file_location("som_state_poll", _PLANNER / "_lib" / "state.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _token() -> str:
    env = {**_load_dotenv(_REPO / ".env"), **os.environ}
    # NUR der eigene SoM-Bot — niemals der OpenFang-Bot (Update-Klau vermeiden).
    return env.get("SOM_TELEGRAM_BOT_TOKEN", "").strip()


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
    data = urllib.parse.urlencode({"offset": offset, "timeout": POLL_TIMEOUT}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
        payload = json.loads(resp.read())
    return payload.get("result", []) if payload.get("ok") else []


def parse_answers(text: str) -> dict[str, str] | None:
    """Parst die Reply.  Rückgabe None = Abbruch (x).  Sonst {index/id: text}.

    '1: AI-Vollzeit  2: ja'  → {'1': 'AI-Vollzeit', '2': 'ja'}
    'x' / 'X' / 'abbrechen'  → None (cancel)
    Freitext ohne Nummern    → {'1': '<freitext>'}
    """
    # letzte [User]-Eingabe aus evtl. Konversations-Verlauf extrahieren
    raw = (text or "").strip()
    _users = re.findall(r"\[user\]\s*\n?(.*?)(?=\n\s*\[[^\]]+\]|$)", raw, flags=re.IGNORECASE | re.DOTALL)
    t = (_users[-1].strip() if _users
         else re.sub(r"^(?:\s*\[[^\]]{0,80}\]\s*\n?)+", "", raw).strip())
    if t.lower() in ("x", "abbrechen", "cancel", "abbruch"):
        return None
    t = re.sub(r"^\s*antwort(?:en)?\s*[:=]\s*", "", t, flags=re.IGNORECASE).strip()  # 'antwort:'-Trigger weg
    if t.lower() in ("x", "abbrechen", "cancel", "abbruch"):
        return None
    # Muster  <ziffer>: <wert>   (Wert bis zum nächsten "<ziffer>:" oder Ende)
    matches = list(re.finditer(r"(\d+)\s*[:.)]\s*(.*?)(?=\s+\d+\s*[:.)]|$)", t, re.DOTALL))
    if matches:
        return {m.group(1): m.group(2).strip() for m in matches if m.group(2).strip()}
    # kein nummeriertes Muster → ganze Nachricht ist Antwort auf Frage 1
    return {"1": t} if t else {}


def _resume_detached(run_id: str, answers: dict[str, str] | None, cancel: bool) -> None:
    """Startet som_resume.py detached (resume kann Minuten dauern, darf den
    Poll-Loop nicht blockieren). Pattern wie der async SoM-Worker."""
    py = str(_VENV_PY) if _VENV_PY.exists() else sys.executable
    cmd = [py, str(_REPO / "scripts" / "som_resume.py"), run_id]
    if cancel:
        cmd.append("--cancel")
    else:
        for k, v in (answers or {}).items():
            cmd += ["--answer", f"{k}={v}"]
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags, close_fds=True, env=dict(os.environ),
    )


def _handle_update(upd: dict, st) -> None:
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    if ALLOWED_CHAT and chat_id and chat_id != str(ALLOWED_CHAT):
        return  # nur der erlaubte Nutzer
    reply_to = (msg.get("reply_to_message") or {}).get("message_id")
    if not reply_to:
        return  # keine Reply → uns egal (SoM reagiert nur auf Antworten zu Fragen)
    run_id = st.answers_map_get(int(reply_to))
    if not run_id:
        return  # Reply auf eine andere Nachricht (nicht eine SoM-Frage)
    text = msg.get("text") or msg.get("caption") or ""
    answers = parse_answers(text)
    if answers is None:
        print(f"[som-poll] {run_id}: Abbruch (x)")
        _resume_detached(run_id, None, cancel=True)
    else:
        print(f"[som-poll] {run_id}: Antworten {answers} → resume")
        _resume_detached(run_id, answers, cancel=False)


def main() -> int:
    token = _token()
    if not token:
        print("ERROR: SOM_TELEGRAM_BOT_TOKEN nicht gesetzt.\n"
              "Der SoM-Reply-Poller braucht einen EIGENEN Bot (getUpdates ist exklusiv pro\n"
              "Token — der OpenFang-Bot TELEGRAM_BOT_TOKEN darf nicht doppelt gepollt werden).\n"
              "Setup: @BotFather → neuer Bot → SOM_TELEGRAM_BOT_TOKEN=... in .env.", file=sys.stderr)
        return 2

    st = _state()
    offset = _read_offset()
    print(f"[som-poll] gestartet (offset={offset}, chat={ALLOWED_CHAT}). Lausche auf Antworten…")
    # Einmal-Modus für Tests/Cron: SOM_POLL_ONCE=1 → ein getUpdates, dann raus.
    once = os.environ.get("SOM_POLL_ONCE") in ("1", "true", "True")
    while True:
        try:
            updates = _get_updates(token, offset)
            for upd in updates:
                offset = max(offset, upd.get("update_id", 0) + 1)
                try:
                    _handle_update(upd, st)
                except Exception as e:  # noqa: BLE001 — eine kaputte Nachricht killt den Poller nicht
                    print(f"[som-poll] update-Fehler: {e}", file=sys.stderr)
            if updates:
                _write_offset(offset)
        except Exception as e:  # noqa: BLE001 — Netzfehler → kurz warten, weiter
            print(f"[som-poll] poll-Fehler: {e}", file=sys.stderr)
            time.sleep(5)
        if once:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
