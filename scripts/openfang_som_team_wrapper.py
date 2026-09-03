"""OpenFang → SoM-Team bridge (Phase B — das 'insane'-Geschütz).

Brain delegiert difficulty=insane an diesen Wrapper (Capability 'openfang:som-team').
Wie openfang_som_planner_wrapper: Intent via stdin, Run DETACHED starten, SOFORT
antworten (OpenFang/Telegram-Timeout), Ergebnis async per Telegram. Der Worker
ruft som_team_runner.run(intent) — baut dynamisch ein SelectorGroupChat aus den
intent-relevantesten Capabilities und führt es aus.

Aktiv nur über diesen Agent (Brain ruft ihn nur bei INSANE_AUTOGEN=1). Läuft mit
voice/.venv312 (hat autogen + die SoM-Libs).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"
_VENV_PY = _REPO / "vibemind-os" / "voice" / ".venv312" / "Scripts" / "python.exe"


def _force_utf8_stdout() -> None:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _unwrap_envelope(text: str) -> str:
    """Packt das Brain-Argument-Envelope aus ({"value":...,"_intent":...}). Siehe
    openfang_som_planner_wrapper._unwrap_envelope (gleicher Bug-Pfad)."""
    t = (text or "").strip()
    if not (t.startswith("{") and t.endswith("}")):
        return t
    try:
        obj = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return t
    if not isinstance(obj, dict):
        return t
    for key in ("value", "_intent", "intent", "message"):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return t


def _extract_trace_id(text: str) -> str:
    """E2E-Trace (Phase 2b): _trace_id aus dem Envelope ziehen, damit der som-team-
    Worker Stage-Events unter derselben trace_id pushen kann."""
    t = (text or "").strip()
    if not (t.startswith("{") and t.endswith("}")):
        return ""
    try:
        obj = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return ""
    return (obj.get("_trace_id") or "").strip() if isinstance(obj, dict) else ""


def _latest_user_turn(text: str) -> str:
    t = (text or "").strip()
    users = re.findall(r"\[user\]\s*\n?(.*?)(?=\n\s*\[[^\]]+\]|$)", t, flags=re.IGNORECASE | re.DOTALL)
    if users:
        return users[-1].strip()
    return re.sub(r"^(?:\s*\[[^\]]{0,80}\]\s*\n?)+", "", t).strip()


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "som_team_runner_w", _PLANNER / "runner" / "som_team_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _notify(msg: str) -> None:
    try:
        spec = importlib.util.spec_from_file_location("som_notify_t", _PLANNER / "_lib" / "notify.py")
        n = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(n)
        n.send(msg)
    except Exception:  # noqa: BLE001
        pass


def _run_worker(intent: str) -> int:
    try:
        runner = _load_runner()
        res = runner.run(intent)
        final = ""
        if isinstance(res, dict):
            final = res.get("final_text") or ("✅ Team-Lauf fertig." if res.get("ok") else
                                              f"🚧 Team-Lauf fehlgeschlagen: {res.get('error','?')}")
        _notify(f"🧠 SoM-Team (insane) — {final or 'fertig'}")
    except Exception as e:  # noqa: BLE001
        _notify(f"🚧 SoM-Team fehlgeschlagen: {e}")
        return 1
    return 0


def main() -> int:
    _force_utf8_stdout()
    if "--worker" in sys.argv:
        intent = os.environ.get("SOM_TEAM_INTENT", "").strip()
        if not intent:
            return 2
        return _run_worker(intent)

    try:
        prompt = sys.stdin.read()
    except Exception:  # noqa: BLE001
        prompt = ""
    _trace_id = _extract_trace_id(prompt)   # E2E-Trace: vor dem Unwrap
    prompt = _latest_user_turn(_unwrap_envelope(prompt))
    if not prompt:
        sys.stdout.write("Kein Intent empfangen.\n")
        return 2

    try:
        env = dict(os.environ)
        if _trace_id:
            env["SOM_TRACE_ID"] = _trace_id
        env["SOM_TEAM_INTENT"] = prompt
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        py = str(_VENV_PY) if _VENV_PY.exists() else sys.executable
        subprocess.Popen(
            [py, str(Path(__file__).resolve()), "--worker"],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=creationflags, close_fds=True,
        )
        reply = ("Ich setze ein Multi-Agent-Team auf die Aufgabe an (dynamische "
                 "Capability-Agenten). Das dauert ein paar Minuten — ich melde mich "
                 "per Telegram mit dem Ergebnis.")
    except Exception as e:  # noqa: BLE001
        reply = f"Konnte das Team nicht starten: {e}"
    sys.stdout.write(reply + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
