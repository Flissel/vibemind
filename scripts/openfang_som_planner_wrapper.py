"""OpenFang -> SoM-Planner bridge wrapper.

Analog zu openfang_buergergeld_wrapper.py. OpenFang's claude_code-Driver spawnt
dieses Skript (via .cmd Shim) und pipet den Intent via stdin. Wir routen den
Intent an som_core.run(intent) — die volle SoM-Pipeline (Planner→Executor→
Validator→Matrix, mit Feedback-Loop) — und geben eine gesprochene deutsche
Zusammenfassung auf stdout zurück (OpenFang relayt an Brain/Telegram/Voice).

Läuft mit voice/.venv312-Python (hat autogen + pydantic, die som_core braucht).

So wird der SoM-Planner per Telegram (brain-gateway → Brain → openfang:som-planner)
UND per Voice (Brain multihop) ansteuerbar. Der ausgehende Telegram-Push passiert
automatisch in som_core.run (notify.py).
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

# UTF-8 stdout (Windows cp1252-Crash bei Umlauten vermeiden)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def _unwrap_envelope(text: str) -> str:
    """Packt das Brain-Argument-Envelope aus, falls vorhanden.

    Brain ruft den SoM-Planner via build_executor(...).call_with_arg(intent,
    extra_params={"_intent": intent}) — OpenFang liefert das dann als JSON-String
    {"value": "<intent>", "_intent": "<intent>"} an stdin. Ohne Auspacken plant
    der Planner gegen den rohen JSON-Text statt gegen den echten Intent (Bug,
    run_0024: intent='{"value": "erstelle...", "_intent": "..."}').

    Reihenfolge: value > _intent > intent > message. Kein JSON → Text unverändert.
    """
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
    """E2E-Trace (2026-06-09): zieht _trace_id aus dem Envelope (Brain gibt es via
    extra_params mit), damit der SoM-Worker seine Stage-Events unter derselben
    trace_id an /api/trace/{id}/stage pushen kann. Leer wenn keins da."""
    t = (text or "").strip()
    if not (t.startswith("{") and t.endswith("}")):
        return ""
    try:
        obj = json.loads(t)
    except (json.JSONDecodeError, ValueError):
        return ""
    return (obj.get("_trace_id") or "").strip() if isinstance(obj, dict) else ""


def _latest_user_turn(text: str) -> str:
    """Extrahiert die LETZTE Nutzer-Eingabe aus dem von OpenFang gelieferten Text.

    OpenFang (module=builtin:chat) fuettert dem Agent den GANZEN Konversations-
    Verlauf mit Rollen-Markern ([User]\\n.. [Assistant]\\n.. [User]\\n..). Beim
    Planen wollen wir NUR den letzten [User]-Intent — sonst plant der Planner den
    ganzen Transcript (verifiziert: run_0022 failed an einem Misch-Intent).
    Fallback: fuehrende [Marker]-Bloecke trimmen (Wrapper-direkt / Voice)."""
    t = (text or "").strip()
    users = re.findall(r"\[user\]\s*\n?(.*?)(?=\n\s*\[[^\]]+\]|$)", t,
                       flags=re.IGNORECASE | re.DOTALL)
    if users:
        return users[-1].strip()
    return re.sub(r"^(?:\s*\[[^\]]{0,80}\]\s*\n?)+", "", t).strip()

_REPO = Path(__file__).resolve().parents[1]                       # Vibemind_V1/
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"


def _load_som_core():
    spec = importlib.util.spec_from_file_location(
        "som_core_wrap", _PLANNER / "runner" / "som_core.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _spoken_summary(result: dict) -> str:
    """Gesprochene deutsche Zusammenfassung des Run-Results (für Telegram/Voice)."""
    status = result.get("status", "?")
    steps = result.get("steps", {})
    pl = steps.get("planner", {})
    val = steps.get("validator", {})
    mx = steps.get("matrix", {})

    parts = []
    n = pl.get("n_steps")
    if n is not None:
        parts.append(f"Ich habe einen Plan mit {n} Schritten erstellt.")
    if val.get("verdict"):
        g = val.get("n_gates", 0)
        parts.append(f"Validierung: {val['verdict']}"
                     + (f", {g} Schritt(e) brauchen deine Freigabe." if g else "."))
    if mx.get("ok"):
        iso = mx.get("isolated") or []
        parts.append(f"Die Ausführungs-Matrix hat {mx.get('n_nodes')} Schritte."
                     + (f" Achtung: verwaiste Schritte: {iso}." if iso else ""))
    fb = [k for k in steps if k.startswith("feedback_")]
    if fb:
        parts.append(f"Es gab {len(fb)} Korrektur-Runde(n).")

    status_text = {
        "ready": "Der Plan ist bereit.",
        "needs_input": "Es fehlen noch Eingabe-Daten — bitte ergänzen.",
        "awaiting_approval": "Der Plan wartet auf deine Freigabe.",
        "needs_human": "Der Plan braucht manuelle Prüfung.",
        "failed": "Die Planung ist fehlgeschlagen.",
    }.get(status, f"Status: {status}.")
    parts.append(status_text)
    return " ".join(parts)


def _run_worker(prompt: str) -> int:
    """Synchroner Worker-Modus: führt die volle Pipeline aus + pusht das Ergebnis
    selbst via Telegram (notify in som_core.run). Läuft detached, kein stdout nötig."""
    try:
        som = _load_som_core()
        som.run(prompt)  # volle Pipeline + automatischer Telegram-Push (notify.py)
    except Exception as e:  # noqa: BLE001
        # Fehler ebenfalls an Telegram melden (best-effort)
        try:
            _PLANNER_LIB = _PLANNER / "_lib"
            spec = importlib.util.spec_from_file_location("som_notify_w", _PLANNER_LIB / "notify.py")
            n = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(n)
            n.send(f"🚧 SoM-Planung fehlgeschlagen: {e}")
        except Exception:  # noqa: BLE001
            pass
        return 1
    return 0


def main() -> int:
    # Worker-Modus: synchroner Lauf (vom async-Trigger detached gestartet)
    if "--worker" in sys.argv:
        prompt = ""
        # Worker bekommt den Intent via env (stdin ist beim detached-Start nicht da)
        prompt = os.environ.get("SOM_WORKER_INTENT", "").strip()
        if not prompt:
            return 2
        return _run_worker(prompt)

    # Trigger-Modus (default, von OpenFang): Intent via stdin, Run DETACHED starten,
    # SOFORT antworten (OpenFang/Telegram-Timeout, 300s, reicht nicht für den
    # vollen Lauf). Das Ergebnis kommt asynchron per Telegram-Push (notify.py).
    try:
        prompt = sys.stdin.read()
    except Exception:  # noqa: BLE001
        prompt = ""
    # 0. E2E-Trace: trace_id VOR dem Unwrap aus dem Envelope ziehen (danach weg).
    _trace_id = _extract_trace_id(prompt)
    # 1. Brain-Argument-Envelope auspacken ({"value":...,"_intent":...})
    prompt = _unwrap_envelope(prompt)
    # 2. Nur die letzte [User]-Eingabe planen (OpenFang liefert den ganzen Verlauf)
    prompt = _latest_user_turn(prompt)
    if not prompt:
        sys.stdout.write("Kein Intent empfangen.\n")
        return 2

    try:
        env = dict(os.environ)
        env["SOM_WORKER_INTENT"] = prompt
        if _trace_id:
            env["SOM_TRACE_ID"] = _trace_id   # Worker pusht Stage-Events darunter
        # Detached: eigene Prozessgruppe, überlebt OpenFang-Driver-Timeout/Teardown
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        reply = ("Ich erstelle den Plan (Planner, Executor, Validator, Matrix). "
                 "Das dauert ein paar Minuten — ich melde mich per Telegram sobald "
                 "er fertig ist.")
    except Exception as e:  # noqa: BLE001
        reply = f"Konnte die Planung nicht starten: {e}"

    if not reply.endswith("\n"):
        reply += "\n"
    sys.stdout.write(reply)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
