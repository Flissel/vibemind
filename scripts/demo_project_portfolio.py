"""Skill 2 v3 — Pure Python, no coordinator.

The coordinator-loop hung twice on this volume of data. Since the data
is strictly structured (115 _overview.md with identical template), this
becomes pure data-engineering: regex-parse → openpyxl-write → eval →
write SKILL.md. The coordinator adds no value here.

This still uses the project's MCP tools (xlsx_create_from_data,
file_evaluate) but calls them directly as Python functions, bypassing
the MCP-stdio dance.

Output: C:/Users/User/Desktop/HR/Project_Portfolio_2026.xlsx
        + vibemind-os/skills/roarboot/project-portfolio/SKILL.md
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Bring tool functions into scope
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "vibemind-os" / "spaces" / "desktop"
                       / "Automation_ui" / "backend" / "moire_agents"))

from dotenv import load_dotenv
load_dotenv(HERE.parent / ".env")

from mcp_server_handoff import (  # type: ignore
    _xlsx_create_from_data,
    _excel_verify_file,
    _file_evaluate,
)

KNOWLEDGE_ROOT = Path(os.path.expanduser("~/.rowboat/knowledge/Projects"))
OUTPUT_FILE = "C:/Users/User/Desktop/HR/Project_Portfolio_2026.xlsx"
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "project-portfolio"

P_TYPE = re.compile(r"\*\*Type:\*\*\s*(\S+)")
P_STATUS = re.compile(r"\*\*Status:\*\*\s*(\S+)")
P_STARTED = re.compile(r"\*\*Started:\*\*\s*(\S+)")
P_SUMMARY = re.compile(r"## Summary\s*\n(.+?)(?=\n##|\n---|\Z)", re.DOTALL)
P_KEYFACT_IDEAS = re.compile(r"-\s*(\d+)\s+ideas?/notes?", re.IGNORECASE)
P_OPENITEMS = re.compile(r"## Open items\s*\n(.+?)(?=\n##|\n---|\Z)", re.DOTALL)


def parse_overview(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    type_m = P_TYPE.search(text)
    status_m = P_STATUS.search(text)
    started_m = P_STARTED.search(text)
    summary_m = P_SUMMARY.search(text)
    ideas_m = P_KEYFACT_IDEAS.search(text)
    openitems_m = P_OPENITEMS.search(text)

    summary = (summary_m.group(1).strip() if summary_m else "")
    if len(summary) > 200:
        summary = summary[:197] + "..."

    open_items_text = openitems_m.group(1).strip() if openitems_m else ""
    if "(none)" in open_items_text.lower() or not open_items_text.strip():
        open_items_count = 0
    else:
        open_items_count = sum(
            1 for line in open_items_text.splitlines()
            if line.strip().startswith("-")
        )

    subdir_files = len([p for p in path.parent.glob("*.md") if p.name != "_overview.md"])

    return {
        "project_name": path.parent.name,
        "type": type_m.group(1) if type_m else "",
        "status": status_m.group(1) if status_m else "",
        "started": started_m.group(1) if started_m else "",
        "summary": summary,
        "ideas": int(ideas_m.group(1)) if ideas_m else 0,
        "open_items": open_items_count,
        "sub_pages": subdir_files,
        "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def main() -> int:
    overviews = sorted(KNOWLEDGE_ROOT.glob("*/_overview.md"))
    print(f"=== 1. Parse {len(overviews)} _overview.md files ===")
    rows_data = [parse_overview(p) for p in overviews]
    print(f"  parsed {len(rows_data)} projects")

    # Stats
    n = len(rows_data)
    n_active = sum(1 for r in rows_data if r["status"] == "active")
    n_with_ideas = sum(1 for r in rows_data if r["ideas"] > 0)
    n_with_open = sum(1 for r in rows_data if r["open_items"] > 0)
    n_with_subs = sum(1 for r in rows_data if r["sub_pages"] > 0)
    total_ideas = sum(r["ideas"] for r in rows_data)
    avg_ideas = total_ideas / n if n else 0
    print(f"  active={n_active}/{n}, ideas>0={n_with_ideas}, open>0={n_with_open}, sub-pgs>0={n_with_subs}")
    print(f"  total ideas={total_ideas}, avg={avg_ideas:.1f}")
    print()

    print("=== 2. Build Excel ===")
    main_header = ["Projekt", "Typ", "Status", "Gestartet", "Summary",
                   "Ideen", "Offene Items", "Sub-Pages", "Geaendert"]
    main_rows = [main_header]
    for r in rows_data:
        main_rows.append([
            r["project_name"], r["type"], r["status"], r["started"],
            r["summary"], r["ideas"], r["open_items"], r["sub_pages"],
            r["modified"],
        ])

    summary_rows = [
        ["Metric", "Wert"],
        ["Gesamt-Projekte", n],
        ["Active", n_active],
        ["Mit Ideen (>0)", n_with_ideas],
        ["Mit Open-Items (>0)", n_with_open],
        ["Mit Sub-Pages (>0)", n_with_subs],
        ["Total Ideen", total_ideas],
        ["Avg Ideen pro Projekt", round(avg_ideas, 2)],
    ]

    sheets = [
        {"name": "Projekte", "rows": main_rows, "bold_rows": [1]},
        {"name": "Status-Summary", "rows": summary_rows, "bold_rows": [1]},
    ]

    cell_styles = [
        {"range": "A1:I1", "fill_color": "305496", "font_color": "FFFFFF", "bold": True},
    ]

    res = _xlsx_create_from_data(
        file_path=OUTPUT_FILE,
        sheets=sheets,
        freeze_pane="A2",
        cell_styles=cell_styles,
    )
    print(f"  xlsx_create result: success={res.get('success')}, sheets={res.get('sheets')}, size={res.get('size_bytes')}B")
    if not res.get("success"):
        print(f"  ERROR: {res}")
        return 1
    print()

    print("=== 3. Verify ===")
    v = _excel_verify_file(
        file_path=OUTPUT_FILE,
        must_contain_text=["Projekt", "Status", "Active", "Total Ideen"],
        min_rows=10,
    )
    print(f"  verify success={v.get('success')}, summary={v.get('summary')}")
    print()

    print("=== 4. Evaluate ===")
    e = _file_evaluate(
        file_path=OUTPUT_FILE,
        expected_intent=(
            f"Project-Portfolio-Dashboard fuer {n} Roarboot-Projekte: "
            "Sheet Projekte mit pro Zeile name/type/status/started/summary/ideas/open-items/sub-pages, "
            "Sheet Status-Summary mit Aggregaten."
        ),
        source_data_description=(
            f"{n} _overview.md-Dateien aus ~/.rowboat/knowledge/Projects/, "
            "alle Type=idea-bubble Status=active."
        ),
    )
    score = e.get("score", 0)
    print(f"  eval score: {score}/100")
    print(f"  summary: {e.get('summary', '')}")
    if e.get("issues"):
        print(f"  issues:")
        for i in e.get("issues", [])[:5]:
            print(f"    [{i.get('severity')}] {i.get('issue', '')[:120]}")
    print()

    print("=== 5. Persist SKILL.md ===")
    if score >= 90:
        confidence = 1.0
    elif score >= 70:
        confidence = 0.8
    elif score >= 50:
        confidence = 0.6
    else:
        confidence = 0.3

    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"

    frontmatter = {
        "name": "roarboot-project-portfolio",
        "description": "Excel-Portfolio-Dashboard aller Roarboot-Projekte (regex-parsed _overview.md, kein LLM noetig fuer Daten)",
        "app": "roarboot",
        "requires_approval": False,  # pure read-then-write, deterministic
        "agents": ["*"],
        "inputs": [],
        "expected_state": {
            "description": f"Excel mit {n} Projekten existiert",
            "verification_tool": "excel_verify_file",
        },
        "confidence": confidence,
        "attempts": 1,
        "successes": 1 if v.get("success") else 0,
        "eval_score": score,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-project-portfolio

Liest alle `_overview.md`-Dateien unter `~/.rowboat/knowledge/Projects/` und erzeugt
ein Excel-Portfolio-Dashboard. Direkter Python-Pfad — der Coordinator-LLM-Loop
hängt bei {n}+ Files (zu viele tokens), deshalb regex-parsing + openpyxl direkt.

## Schritte

1. Glob `~/.rowboat/knowledge/Projects/*/_overview.md` -> {n} Files
2. Pro File regex-parse: `Type`, `Status`, `Started`, `Summary`, Ideen-Count, Open-Items-Count
3. Sub-Pages-Count = Anzahl `.md` im Folder ausser `_overview.md`
4. Build Excel: Sheet 'Projekte' (eine Zeile pro Projekt) + 'Status-Summary' (Aggregate)
5. excel_verify_file + file_evaluate
6. SKILL.md persistieren

## Aktuelle Datenlage ({datetime.now().date().isoformat()})

- Gesamt: **{n}** Projekte
- Active: **{n_active}**
- Mit Ideen (>0): {n_with_ideas}
- Mit Open-Items (>0): {n_with_open}
- Mit Sub-Pages (>0): {n_with_subs}
- Total Ideen: {total_ideas}
- Avg Ideen pro Projekt: {avg_ideas:.1f}

## Reproduzierbarkeit

`python scripts/demo_project_portfolio.py` — keine Args nötig, kein LLM-Roundtrip,
deterministisch. Tool-Calls intern: `_xlsx_create_from_data`, `_excel_verify_file`,
`_file_evaluate`.
"""

    import yaml
    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm_text}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md written: {skill_md}")
    print(f"  confidence: {confidence}")
    print()

    print("=" * 60)
    print(f"DONE. file={OUTPUT_FILE}, eval={score}, conf={confidence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
