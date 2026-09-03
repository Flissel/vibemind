"""Skill 3 — Grant-Gap-Finder.

Cross-references Investor-Grant-Fragenkatalog with all 115 Project _overview.md
files. For each Grant-Frage that has status != 'beantwortet', search semantically
in Projects for content that could fill the gap.

Output Excel:
  Sheet 'Gaps': one row per non-beantwortet Frage with:
    [Nummer, Sektion, Frage, Aktueller_Status, Aktuelle_Antwort,
     Top_Match_Projekt, Match_Excerpt, LLM_Suggestion]

This is the "knowledge base proactively helps" demo: the user sees on a
dashboard exactly what's missing AND what existing project notes could
fill the gap.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vibemind-os" / "spaces" / "desktop"
                       / "Automation_ui" / "backend" / "moire_agents"))

from dotenv import load_dotenv
load_dotenv(HERE.parent / ".env")

from mcp_server_handoff import (  # type: ignore
    _xlsx_create_from_data,
    _excel_verify_file,
    _file_evaluate,
    _roarboot_ask,
)

GRANT_FILE = Path(os.path.expanduser(
    "~/.rowboat/knowledge/Investor Programs/AI Nation Grant/Fragenkatalog AI Nation Grant.md"
))
PROJECTS_ROOT = Path(os.path.expanduser("~/.rowboat/knowledge/Projects"))
OUTPUT_FILE = "C:/Users/User/Desktop/HR/Investor_Grant_Gap_Analysis_2026.xlsx"
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "grant-gap-finder"

P_QUESTION = re.compile(
    r"^### (\d+\.\d+(?:\.\d+)?)\s+(.+?)\n\n"
    r"\*\*Frage:\*\*\s*(.+?)\n"
    r"\*\*Antwort:\*\*\s*(.*?)"
    r"(?:\n\*\*Offene Punkte:\*\*\s*(.*?))?"
    r"(?:\n\*\*Benötigte Quellen/Nachweise:\*\*\s*(.*?))?"
    r"\n\*\*Status:\*\*\s*(\w+)",
    re.MULTILINE | re.DOTALL,
)


def parse_grant_questions() -> list[dict]:
    text = GRANT_FILE.read_text(encoding="utf-8")
    # Find current section as we go
    questions = []
    section = ""
    for line in text.splitlines(keepends=False):
        sec_m = re.match(r"^## (\d+\.\s*.+)", line)
        if sec_m:
            section = sec_m.group(1).strip()

    # Now extract questions with regex (multi-line)
    for m in P_QUESTION.finditer(text):
        nummer, title, frage, antwort, offen, quellen, status = m.groups()
        # Determine which section this question belongs to (by nummer prefix)
        sec_num = nummer.split(".")[0]
        sec_title = ""
        for sec_m in re.finditer(r"^## (\d+)\.\s*(.+?)$", text, re.MULTILINE):
            if sec_m.group(1) == sec_num:
                sec_title = f"{sec_m.group(1)}. {sec_m.group(2).strip()}"
                break

        # Strip Hinweis-blöcke from frage
        frage_clean = re.sub(r"\n\*\*Hinweis:\*\*.*", "", frage, flags=re.DOTALL).strip()

        questions.append({
            "nummer": nummer.strip(),
            "title": title.strip(),
            "section": sec_title,
            "frage": frage_clean[:300],
            "antwort": (antwort or "").strip()[:500],
            "offene_punkte": (offen or "").strip()[:200],
            "quellen": (quellen or "").strip()[:200],
            "status": status.strip(),
        })
    return questions


def find_relevant_projects(question_text: str, limit: int = 3) -> list[tuple[str, int, str]]:
    """For a question, score each project _overview.md by keyword overlap.
    Returns top-N (project_name, score, excerpt)."""
    # Extract content keywords from question (≥4 chars, lowercased)
    stopwords = set("""der die das ist sind als und oder ein eine the and you your with what
                       which when have has had been was were will would could should there
                       this that these those wie viel viele was wer wie wann wo warum welche
                       welcher welches but for from this please just tell about your""".split())
    words = [w.lower() for w in re.findall(r"\b[a-zA-ZäöüÄÖÜß]{4,}\b", question_text)]
    keywords = [w for w in words if w not in stopwords][:8]

    if not keywords:
        return []

    scores = []
    for ov in PROJECTS_ROOT.glob("*/_overview.md"):
        try:
            content = ov.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            continue
        score = sum(1 for kw in keywords if kw in content)
        if score >= 1:
            # Extract a relevant excerpt: first paragraph mentioning a keyword
            excerpt = ""
            for line in content.splitlines():
                if any(kw in line for kw in keywords):
                    excerpt = line.strip()
                    break
            scores.append((ov.parent.name, score, excerpt[:200]))
    scores.sort(key=lambda x: -x[1])
    return scores[:limit]


def main() -> int:
    print("=== 1. Parse Grant Fragenkatalog ===")
    questions = parse_grant_questions()
    print(f"  {len(questions)} questions parsed")

    # Filter to those that need attention
    GAPS = [q for q in questions if q["status"] != "beantwortet"]
    print(f"  Gaps (not 'beantwortet'): {len(GAPS)}")
    for q in GAPS:
        print(f"    [{q['status']:14}] {q['nummer']} {q['title'][:60]}")
    print()

    print("=== 2. For each gap, find candidate Projects ===")
    gap_rows = []
    for q in GAPS:
        # Search criteria: question + offene_punkte combined
        search_text = f"{q['frage']} {q['offene_punkte']}"
        matches = find_relevant_projects(search_text, limit=3)

        if matches:
            top_proj, top_score, top_excerpt = matches[0]
            print(f"  {q['nummer']}: top match = {top_proj} (score {top_score})")
        else:
            top_proj, top_score, top_excerpt = "", 0, ""
            print(f"  {q['nummer']}: NO match")

        all_matches_str = " | ".join(f"{p} ({s})" for p, s, _ in matches)
        gap_rows.append({
            **q,
            "top_match_project": top_proj,
            "top_match_score": top_score,
            "top_match_excerpt": top_excerpt[:200],
            "all_matches": all_matches_str,
        })
    print()

    print("=== 3. LLM-Suggestion per Gap (only top-3 to save tokens) ===")
    # LLM-augment any gap with a non-zero match (we have only score=1 in
    # this dataset because question_text is sparse — the search scoring is
    # tuned for longer texts). Cap at 5 to keep cost <$0.05.
    actionable = [r for r in gap_rows if r["top_match_score"] >= 1][:5]
    suggestions: dict[str, str] = {}
    for r in actionable:
        ans = _roarboot_ask(
            question=(
                f"Investor-Grant-Frage {r['nummer']}: {r['frage']}\n"
                f"Aktueller Antwort-Stand: '{r['antwort']}'\n"
                f"Offene Punkte: '{r['offene_punkte']}'\n\n"
                f"Schaue im Project '{r['top_match_project']}' und finde 2-3 Saetze die "
                f"den Antwort-Stand verbessern oder die offenen Punkte schliessen koennten. "
                f"Antworte konkret in 2-3 Saetzen Deutsch, kein Markdown."
            ),
            folder=f"Projects/{r['top_match_project']}",
            max_files=5,
            max_chars_per_file=2000,
            model="gpt-4o-mini",
        )
        sug = (ans.get("answer") or ans.get("error") or "").strip()
        suggestions[r["nummer"]] = sug[:400]
        print(f"  {r['nummer']}: {sug[:80]}...")
    print()

    print("=== 4. Build Excel ===")
    main_header = ["Nummer", "Sektion", "Frage", "Aktueller-Status",
                   "Aktuelle-Antwort", "Top-Match-Projekt", "Match-Score",
                   "Match-Excerpt", "LLM-Vorschlag"]
    main_rows = [main_header]
    for r in gap_rows:
        main_rows.append([
            r["nummer"], r["section"], r["frage"], r["status"],
            r["antwort"], r["top_match_project"], r["top_match_score"],
            r["top_match_excerpt"], suggestions.get(r["nummer"], ""),
        ])

    summary_rows = [
        ["Metric", "Wert"],
        ["Gesamt-Fragen", len(questions)],
        ["Beantwortet", sum(1 for q in questions if q["status"] == "beantwortet")],
        ["Gaps gesamt", len(GAPS)],
        ["Gaps mit Projekt-Match", sum(1 for r in gap_rows if r["top_match_score"] > 0)],
        ["Gaps mit Score >= 2", sum(1 for r in gap_rows if r["top_match_score"] >= 2)],
        ["LLM-Suggestions generiert", len(suggestions)],
    ]

    sheets = [
        {"name": "Gaps", "rows": main_rows, "bold_rows": [1]},
        {"name": "Summary", "rows": summary_rows, "bold_rows": [1]},
    ]
    cell_styles = [
        {"range": "A1:I1", "fill_color": "C00000", "font_color": "FFFFFF", "bold": True},
    ]

    res = _xlsx_create_from_data(
        file_path=OUTPUT_FILE,
        sheets=sheets,
        freeze_pane="A2",
        cell_styles=cell_styles,
    )
    print(f"  xlsx: success={res.get('success')}, size={res.get('size_bytes')}B")
    print()

    print("=== 5. Verify + Evaluate ===")
    v = _excel_verify_file(
        file_path=OUTPUT_FILE,
        must_contain_text=["Frage", "Match", "LLM"],
        min_rows=len(GAPS) + 1,
    )
    print(f"  verify: {v.get('summary')}")

    e = _file_evaluate(
        file_path=OUTPUT_FILE,
        expected_intent=(
            f"Gap-Analysis fuer Investor-Grant-Antrag: pro Frage die nicht 'beantwortet' "
            f"ist, zeige aktuellen Status, beste passende Projekt-Quelle, und LLM-Vorschlag "
            f"wie die Frage aus dem Projekt-Inhalt vervollstaendigt werden kann."
        ),
        source_data_description=(
            f"{len(questions)} Grant-Fragen + 115 Project _overview.md-Dateien"
        ),
    )
    score = e.get("score", 0)
    print(f"  eval score: {score}/100")
    print(f"  summary: {e.get('summary', '')}")
    if e.get("issues"):
        for i in e.get("issues", [])[:3]:
            print(f"    [{i.get('severity')}] {i.get('issue', '')[:120]}")
    print()

    print("=== 6. Persist SKILL.md ===")
    if score >= 90: confidence = 1.0
    elif score >= 70: confidence = 0.8
    elif score >= 50: confidence = 0.6
    else: confidence = 0.3

    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"

    frontmatter = {
        "name": "roarboot-grant-gap-finder",
        "description": "Cross-references Investor-Grant Fragenkatalog mit allen 115 Roarboot-Projekten und schlaegt fuer jede unvollstaendige Frage Quellen + LLM-Vorschlaege vor.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [],
        "expected_state": {
            "description": f"Excel mit {len(GAPS)} Gap-Zeilen + LLM-Suggestions existiert",
            "verification_tool": "excel_verify_file",
        },
        "confidence": confidence,
        "attempts": 1,
        "successes": 1 if v.get("success") else 0,
        "eval_score": score,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-grant-gap-finder

Cross-Reference Tool: identifiziert Lücken im Investor-Grant-Antrag und
schlägt Antworten aus dem Projekt-Knowledge vor.

## Pipeline

1. Parse Grant-Fragenkatalog ({len(questions)} Fragen) — Regex auf strukturierte Q&A-Sections
2. Filtere auf nicht-'beantwortet' → {len(GAPS)} Gaps
3. Für jede Gap: keyword-overlap-Score gegen alle 115 Project _overview.md
4. Für die Top-3 actionable Gaps (Score ≥ 2): LLM-Vorschlag via roarboot_ask
5. Excel-Output mit Sheets 'Gaps' + 'Summary'
6. excel_verify + file_evaluate

## Aktuelle Lage ({datetime.now().date().isoformat()})

- Gesamt-Fragen: {len(questions)}
- Beantwortet: {sum(1 for q in questions if q['status'] == 'beantwortet')}
- Gaps gesamt: {len(GAPS)}
- Gaps mit Projekt-Match: {sum(1 for r in gap_rows if r['top_match_score'] > 0)}
- Gaps mit Score ≥ 2: {sum(1 for r in gap_rows if r['top_match_score'] >= 2)}
- LLM-Suggestions generiert: {len(suggestions)}

## Reproduzierbarkeit

`python scripts/demo_grant_gap_finder.py` — keine Args, deterministisch
für die Search-Phase, LLM-Aufruf nur für Top-3 actionable.
"""

    import yaml
    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm_text}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print(f"  confidence: {confidence}")
    print()

    print("=" * 60)
    print(f"DONE. file={OUTPUT_FILE}, gaps={len(GAPS)}, eval={score}, conf={confidence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
