"""OpenFang -> SoM-Resume bridge wrapper (Telegram-Antwort nimmt Run wieder auf).

Der Nutzer beantwortet am Handy eine SoM-Rückfrage (z.B. "AI-Vollzeit, Startup"
oder "x" zum Abbrechen). Diese Nachricht läuft den normalen Weg: Telegram ->
brain-gateway -> Brain CapabilityRouter -> matcht 'som_resume' -> openfang:
som-resume -> DIESER Wrapper.

run-id-frei (User-Entscheidung "wenn die Nachricht an Telegram geht"): der
ausgehende Frage-Push hat den Run als awaiting_answers markiert; wir nehmen den
JÜNGSTEN wartenden Run (state.latest_awaiting_run) und tragen die Antwort dort
ein. Meist wartet nur ein Run — kein ID-Tippen nötig.

ASYNC: ein Resume = voller Re-Plan (3 Agents, Minuten) > OpenFang 300s-Timeout.
Wir starten som_resume.py DETACHED (Pattern wie openfang_som_planner_wrapper) und
antworten SOFORT. Das Ergebnis kommt per Telegram-Push (notify in som_core.resume).

Läuft mit voice/.venv312-Python (für den detached Resume; der Trigger selbst
braucht nur state.py + stdlib).
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


def _force_utf8_stdout() -> None:
    """UTF-8 stdout (Windows cp1252-Crash bei Umlauten). NUR im __main__-Lauf —
    beim Import (z.B. aus Tests) darf das stdout des Aufrufers nicht angefasst
    werden, sonst bricht dessen eigener Wrapper."""
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

_REPO = Path(__file__).resolve().parents[1]                       # Vibemind_V1/
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"
_VENV_PY = _REPO / "vibemind-os" / "voice" / ".venv312" / "Scripts" / "python.exe"


def _state():
    spec = importlib.util.spec_from_file_location("som_state_resume", _PLANNER / "_lib" / "state.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_answers(text: str) -> dict[str, str] | None:
    """Parst die Antwort.  None = Abbruch (x).  Sonst {index/id: text}.

    '1: AI-Vollzeit  2: ja' -> {'1':'AI-Vollzeit','2':'ja'}
    'x' / 'abbrechen'       -> None
    Freitext ohne Nummern   -> {'1': '<freitext>'}
    Optionales 'run_0021:' Präfix wird entfernt (gezielter Run, s.u.).
    """
    t = _strip_channel_prefix(text)
    if t.lower() in ("x", "abbrechen", "cancel", "abbruch"):
        return None
    t = re.sub(r"^\s*run_\d+\s*:?\s*", "", t, flags=re.IGNORECASE)   # optionales run-Präfix weg
    t = re.sub(r"^\s*antwort(?:en)?\s*[:=]\s*", "", t, flags=re.IGNORECASE)  # 'antwort:'-Trigger weg
    t = t.strip()
    if t.lower() in ("x", "abbrechen", "cancel", "abbruch"):         # 'antwort: x' = Abbruch
        return None
    matches = list(re.finditer(r"(\d+)\s*[:.)]\s*(.*?)(?=\s+\d+\s*[:.)]|$)", t, re.DOTALL))
    if matches:
        return {m.group(1): m.group(2).strip() for m in matches if m.group(2).strip()}
    return {"1": t} if t else {}


def _strip_channel_prefix(text: str) -> str:
    """Extrahiert die LETZTE Nutzer-Eingabe aus dem von OpenFang gelieferten Text.

    OpenFang (module=builtin:chat) fuettert dem Agent den GANZEN Konversations-
    Verlauf mit Rollen-Markern, z.B.:
        [User]\\nantwort: A\\n\\n[Assistant]\\nDanke…\\n\\n[User]\\nantwort: B
    Verifiziert 2026-06-02. Wir wollen NUR die letzte [User]-Eingabe (hier 'B'),
    nicht den ganzen Transcript. Faellt auf reines Prefix-Trimmen zurueck wenn
    keine Marker da sind (z.B. Wrapper-direkt oder Poller-Reply)."""
    t = (text or "").strip()
    # letztes [User]-Segment bis zum naechsten [Marker] oder Ende
    users = re.findall(r"\[user\]\s*\n?(.*?)(?=\n\s*\[[^\]]+\]|$)", t,
                       flags=re.IGNORECASE | re.DOTALL)
    if users:
        return users[-1].strip()
    # kein [User]-Marker → nur fuehrende [Marker]-Bloecke abschneiden
    return re.sub(r"^(?:\s*\[[^\]]{0,80}\]\s*\n?)+", "", t).strip()


def _explicit_run_id(text: str) -> str | None:
    """Erlaubt optional 'run_0019: ...' um einen bestimmten (nicht den jüngsten)
    Run zu meinen. Channel-Präfix ('[User]\\n') wird vorher entfernt."""
    m = re.match(r"\s*(run_\d+)\s*:?", _strip_channel_prefix(text), flags=re.IGNORECASE)
    return m.group(1) if m else None


def _resume_detached(run_id: str, answers: dict[str, str] | None, cancel: bool) -> None:
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


def main() -> int:
    _force_utf8_stdout()
    try:
        text = sys.stdin.read()
    except Exception:  # noqa: BLE001
        text = ""
    text = _unwrap_envelope(text)
    text = (text or "").strip()
    if not text:
        sys.stdout.write("Keine Antwort empfangen.\n")
        return 2

    st = _state()
    # gezielter Run via Präfix, sonst der jüngste wartende
    run_id = _explicit_run_id(text) or st.latest_awaiting_run()
    if not run_id:
        sys.stdout.write("Gerade wartet kein Plan auf eine Antwort.\n")
        return 0

    answers = parse_answers(text)
    if answers is None:
        _resume_detached(run_id, None, cancel=True)
        reply = f"Okay, ich breche {run_id} ab."
    else:
        _resume_detached(run_id, answers, cancel=False)
        reply = (f"Danke — ich nehme deine Antwort für {run_id} auf und plane neu. "
                 f"Ich melde mich per Telegram wenn er fertig ist.")

    if not reply.endswith("\n"):
        reply += "\n"
    sys.stdout.write(reply)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
