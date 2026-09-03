"""OpenFang -> SoM-Execute bridge wrapper (führt einen ready-Plan aus).

Der Nutzer sagt „führe den Plan aus" / „los, mach das" → Brain (som_execute
capability) → openfang:som-execute → DIESER Wrapper. Nimmt den jüngsten
ready-Plan (oder per 'run_0022:' Präfix einen bestimmten), startet die
Ausführung DETACHED (Schritte dauern Minuten > OpenFang 300s) und antwortet
sofort. Pausiert an Approval-Gates (Telegram-Push via notify), Freigabe kommt
dann über som-resume zurück.

run-id-frei analog som-resume: latest_ready_run() nimmt den jüngsten ready-Plan.
Läuft mit voice/.venv312.
"""

from __future__ import annotations

import importlib.util
import io
import os
import json
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


def _state():
    spec = importlib.util.spec_from_file_location("som_state_exectrig", _PLANNER / "_lib" / "state.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unwrap_envelope(text: str) -> str:
    """Packt ein Brain-Argument-Envelope aus ({"value":...,"_intent":...}) falls
    vorhanden, sonst Text unverändert. Defense-in-depth — siehe
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


def _latest_user_turn(text: str) -> str:
    t = (text or "").strip()
    users = re.findall(r"\[user\]\s*\n?(.*?)(?=\n\s*\[[^\]]+\]|$)", t, flags=re.IGNORECASE | re.DOTALL)
    if users:
        return users[-1].strip()
    return re.sub(r"^(?:\s*\[[^\]]{0,80}\]\s*\n?)+", "", t).strip()


def _explicit_run_id(text: str) -> str | None:
    m = re.search(r"\b(run_\d+)\b", text or "", flags=re.IGNORECASE)
    return m.group(1) if m else None


def _latest_ready_run(st) -> str | None:
    """Jüngster Run mit run_meta.status == ready."""
    cands = []
    for rid in st.list_runs():
        if st.run_meta(rid).get("status") == "ready":
            cands.append((st.run_meta(rid).get("updated_at") or "", rid))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


def _execute_detached(run_id: str) -> None:
    py = str(_VENV_PY) if _VENV_PY.exists() else sys.executable
    cmd = [py, str(_PLANNER / "runner" / "som_execute.py"), "--run-id", run_id]
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags, close_fds=True, env=dict(os.environ),
    )


def main() -> int:
    _force_utf8_stdout()
    try:
        text = sys.stdin.read()
    except Exception:  # noqa: BLE001
        text = ""
    text = _latest_user_turn(_unwrap_envelope(text))

    st = _state()
    run_id = _explicit_run_id(text) or _latest_ready_run(st)
    if not run_id:
        sys.stdout.write("Es gibt gerade keinen fertigen Plan zum Ausführen.\n")
        return 0
    if st.run_meta(run_id).get("status") != "ready":
        sys.stdout.write(f"Plan {run_id} ist nicht im Status 'ready' (kann nicht ausgeführt werden).\n")
        return 0

    _execute_detached(run_id)
    reply = (f"Ich führe den Plan {run_id} jetzt aus. Bei sensiblen Schritten "
             f"(z.B. Speichern) frage ich vorher per Telegram um Freigabe.")
    if not reply.endswith("\n"):
        reply += "\n"
    sys.stdout.write(reply)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
