"""OpenFang -> Bürgergeld-Pipeline bridge wrapper.

Analog zu openfang_brain_gateway_wrapper.py. OpenFang's claude_code Driver
spawnt dieses Skript (via .cmd Shim) und pipet den Intent via stdin.

Wir routen den Intent an die richtige Pipeline-Funktion in
skills/buergergeld/ und geben eine gesprochene deutsche Antwort auf stdout
(das relayt OpenFang an Brain/Voice zurück).

Routing (Keyword-basiert, deterministisch):
  "vorbereiten|antwort|fertig|nachreichung"  -> komplette Pipeline (bis Gate)
  "status|fehlt|stand|lücke"                 -> nur Status-Abgleich
  "lies|parse|auswerten"                     -> nur parse-eingang
  sonst                                       -> Status-Abgleich (sicherster Default)

Das neueste PDF in eingang/ wird automatisch gewählt wenn keins genannt ist.

WICHTIG: Versendet NICHTS ans Jobcenter. Stoppt am Approval-Gate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# skills/buergergeld/ liegt relativ zu diesem Skript:
#   scripts/openfang_buergergeld_wrapper.py  ->  vibemind-os/skills/buergergeld/
_REPO = Path(__file__).resolve().parents[1]  # Vibemind_V1/
_SKILLS_BG = _REPO / "vibemind-os" / "skills" / "buergergeld"


def _load(module_path: Path, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _timeline():
    return _load(_SKILLS_BG / "_lib" / "timeline_helper.py", "bg_timeline")


def _orchestrate():
    return _load(_SKILLS_BG / "orchestrate.py", "bg_orchestrate")


def _newest_eingang_pdf() -> str | None:
    tl = _timeline()
    eingang = tl.buergergeld_root() / "eingang"
    if not eingang.exists():
        return None
    pdfs = sorted(eingang.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pdfs:
        return None
    # Relativ zur Akte zurückgeben (orchestrate resolved gegen BUERGERGELD_ROOT)
    return f"eingang/{pdfs[0].name}"


def _format_status(summary: dict, gate: dict | None = None) -> str:
    """Baut eine gesprochene deutsche Antwort aus dem Pipeline-Ergebnis."""
    total = summary.get("total", 0)
    erf = summary.get("erfuellt", 0)
    offen = summary.get("offen", 0)
    opt = summary.get("offen_optional", 0)

    lines = [
        f"Ich habe das Schreiben ausgewertet. Das Jobcenter hat {total} Punkte "
        f"gefordert. Davon hast du {erf} bereits eingereicht, {offen} sind noch "
        f"offen" + (f" und {opt} sind optional und für dich nicht zutreffend." if opt else ".")
    ]

    if gate:
        offene = gate.get("offene_positionen", [])
        if offene:
            lines.append("Noch offen: " + ", ".join(offene) + ".")
        pdfs = gate.get("sammel_pdfs", [])
        anschreiben = gate.get("anschreiben", "")
        if anschreiben:
            import os
            lines.append(
                f"Ich habe ein Anschreiben und {len(pdfs)} Sammel-PDF"
                f"{'s' if len(pdfs) != 1 else ''} im Ausgang-Ordner vorbereitet."
            )
        warnungen = gate.get("warnungen", [])
        frist_warn = next((w for w in warnungen if "frist" in w.lower()), None)
        if frist_warn:
            lines.append(
                "Achtung: die Frist ist überschritten — bitte mit Hinweis auf den "
                "laufenden Antrag trotzdem nachreichen."
            )
        lines.append(
            "Bitte prüfen und unterschreiben. Versenden musst du selbst — ich lade "
            "nichts automatisch hoch."
        )
    return " ".join(lines)


def handle(intent: str) -> str:
    intent_lc = intent.lower()
    orch = _orchestrate()
    pdf = _newest_eingang_pdf()

    if pdf is None:
        return ("Ich finde kein Schreiben im Eingang-Ordner "
                "(~/Documents/Buergergeld/eingang/). Bitte lege das Behörden-PDF "
                "dort ab.")

    vorbereiten_kw = ("vorbereit", "antwort", "fertig", "nachreich", "erstell")
    status_kw = ("status", "fehlt", "stand", "lücke", "luecke", "offen")
    parse_kw = ("lies", "parse", "auswert", "auslesen")

    if any(k in intent_lc for k in vorbereiten_kw):
        result = orch.run_pipeline(pdf, status_only=False)
        return _format_status(result.get("summary", {}), result.get("gate"))

    if any(k in intent_lc for k in status_kw) or not any(k in intent_lc for k in parse_kw):
        result = orch.run_pipeline(pdf, status_only=True)
        return _format_status(result.get("summary", {}))

    # parse-only
    parse = _load(_SKILLS_BG / "parse-eingang" / "run.py", "bg_parse")
    p = parse.run(Path(pdf))
    return (f"Ich habe das Schreiben gelesen: {p.get('n_forderungen')} Forderungen "
            f"vom Absender {p.get('absender')}, Frist {p.get('frist')}.")


def main() -> int:
    try:
        prompt = sys.stdin.read()
    except Exception:
        prompt = ""
    prompt = (prompt or "").strip()
    if not prompt:
        sys.stdout.write("Kein Intent empfangen.\n")
        return 2

    try:
        reply = handle(prompt)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc(file=sys.stderr)
        reply = f"Bei der Bürgergeld-Pipeline ist ein Fehler aufgetreten: {e}"

    if not reply.endswith("\n"):
        reply += "\n"
    sys.stdout.write(reply)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
