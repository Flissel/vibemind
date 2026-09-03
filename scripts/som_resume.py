"""SoM-Planner — Resume CLI.

Nimmt einen bei needs_input/awaiting_approval pausierten Run wieder auf, nachdem
die offenen Rückfragen beantwortet wurden. Datei-Pfad (ohne Telegram) — die
Quelle der Wahrheit ist answers_needed.yaml im run-Verzeichnis.

Nutzung:
    # 1) answers_needed.yaml manuell ausfüllen (antwort: "...")  ODER inline:
    python scripts/som_resume.py run_0021 --answer 1="AI-Vollzeit Konzern" --answer 2=ja
    # 2) ohne --answer: nimmt die bereits in answers_needed.yaml eingetragenen Antworten
    python scripts/som_resume.py run_0021
    # Abbrechen:
    python scripts/som_resume.py run_0021 --cancel

Läuft mit voice/.venv312-Python (hat autogen + pydantic, die som_core braucht);
fällt sonst auf das globale Python zurück.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

_REPO = Path(__file__).resolve().parents[1]                       # Vibemind_V1/
_PLANNER = _REPO / "vibemind-os" / "spaces" / "autogen" / "planner"


def _load_som_core():
    spec = importlib.util.spec_from_file_location("som_core_resume", _PLANNER / "runner" / "som_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse_answers(pairs: list[str]) -> dict[str, str]:
    """--answer 1="text"  ->  {"1": "text"}. Key kann Index oder question-id sein."""
    out: dict[str, str] = {}
    for p in pairs or []:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="SoM-Planner Run wieder aufnehmen")
    parser.add_argument("run_id")
    parser.add_argument("--answer", action="append", default=[],
                        help='Antwort als id=text oder index=text (mehrfach)')
    parser.add_argument("--cancel", action="store_true", help="Run abbrechen statt fortsetzen")
    args = parser.parse_args()

    som = _load_som_core()
    answers = _parse_answers(args.answer)
    result = som.resume(args.run_id, answers=answers or None, cancel=args.cancel)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
