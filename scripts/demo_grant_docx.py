"""Skill A — Grant-Application-DOCX.

Reads the AI Nation Grant Fragenkatalog (53 questions, 8 sections) and
writes an investor-ready Word document. Uses docx_create_from_data with
heading/paragraph blocks — no LLM needed for the data, the markdown is
already structured.

Output: C:/Users/User/Desktop/HR/Investor_Grant_Antrag_2026.docx
        + skill at vibemind-os/skills/roarboot/grant-application-docx/SKILL.md
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
    _docx_create_from_data,
    _docx_verify_file,
    _file_evaluate,
)

GRANT_FILE = Path(os.path.expanduser(
    "~/.rowboat/knowledge/Investor Programs/AI Nation Grant/Fragenkatalog AI Nation Grant.md"
))
OUTPUT_FILE = "C:/Users/User/Desktop/HR/Investor_Grant_Antrag_2026.docx"
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "grant-application-docx"


P_SECTION = re.compile(r"^## (\d+)\.\s+(.+?)$", re.MULTILINE)
P_QUESTION = re.compile(
    r"^### (\d+\.\d+(?:\.\d+)?)\s+(.+?)\n\n"
    r"\*\*Frage:\*\*\s*(.+?)\n"
    r"\*\*Antwort:\*\*\s*(.*?)"
    r"(?:\n\*\*Offene Punkte:\*\*\s*(.*?))?"
    r"(?:\n\*\*Benötigte Quellen/Nachweise:\*\*\s*(.*?))?"
    r"\n\*\*Status:\*\*\s*(\w+)",
    re.MULTILINE | re.DOTALL,
)


def parse_grant() -> dict:
    text = GRANT_FILE.read_text(encoding="utf-8")
    sections: dict[str, dict] = {}
    for m in P_SECTION.finditer(text):
        num = m.group(1)
        title = m.group(2).strip()
        sections[num] = {"num": num, "title": title, "questions": []}

    for m in P_QUESTION.finditer(text):
        num, title, frage, antwort, offen, quellen, status = m.groups()
        # Strip Hinweis-blocks from frage so it's pure question
        frage_clean = re.sub(r"\n\*\*Hinweis:\*\*.*", "", frage, flags=re.DOTALL).strip()
        sec_num = num.split(".")[0]
        if sec_num in sections:
            sections[sec_num]["questions"].append({
                "num": num,
                "title": title.strip(),
                "frage": frage_clean,
                "antwort": (antwort or "").strip(),
                "offen": (offen or "").strip(),
                "quellen": (quellen or "").strip(),
                "status": status.strip(),
            })
    return sections


def main() -> int:
    print("=== 1. Parse Grant ===")
    sections = parse_grant()
    total_q = sum(len(s["questions"]) for s in sections.values())
    print(f"  {len(sections)} sections, {total_q} questions")
    print()

    print("=== 2. Build DOCX blocks ===")
    blocks: list[dict] = []

    # Cover
    blocks.append({"type": "heading", "level": 1, "text": "AI Nation Grant — Application"})
    blocks.append({"type": "paragraph", "text": f"Submitted: {datetime.now().strftime('%B %Y')}"})
    blocks.append({"type": "paragraph", "text": "Company: VibeMind"})
    blocks.append({"type": "page_break"})

    # Table of contents (simple list)
    blocks.append({"type": "heading", "level": 2, "text": "Contents"})
    for sec_num in sorted(sections.keys(), key=int):
        sec = sections[sec_num]
        if not sec["questions"]:
            continue
        blocks.append({"type": "paragraph",
                       "text": f"{sec_num}. {sec['title']} ({len(sec['questions'])} questions)"})
    blocks.append({"type": "page_break"})

    # Sections
    for sec_num in sorted(sections.keys(), key=int):
        sec = sections[sec_num]
        if not sec["questions"]:
            continue
        blocks.append({"type": "heading", "level": 1,
                       "text": f"{sec_num}. {sec['title']}"})
        for q in sec["questions"]:
            blocks.append({"type": "heading", "level": 2,
                           "text": f"{q['num']}  {q['title']}"})
            blocks.append({"type": "paragraph",
                           "text": f"Question: {q['frage']}"})
            answer = q["antwort"] or "[to be completed]"
            blocks.append({"type": "paragraph",
                           "text": f"Answer: {answer}"})
            if q["offen"]:
                blocks.append({"type": "paragraph",
                               "text": f"Open items: {q['offen']}"})
            if q["quellen"]:
                blocks.append({"type": "paragraph",
                               "text": f"Sources: {q['quellen']}"})
            blocks.append({"type": "paragraph",
                           "text": f"Status: {q['status']}"})

    # Status table at end
    blocks.append({"type": "page_break"})
    blocks.append({"type": "heading", "level": 1, "text": "Status Overview"})

    n_total = total_q
    n_beantwortet = sum(
        1 for s in sections.values() for q in s["questions"]
        if q["status"] == "beantwortet"
    )
    n_vorausgef = sum(
        1 for s in sections.values() for q in s["questions"]
        if "vorausgef" in q["status"].lower()
    )
    n_teilweise = sum(
        1 for s in sections.values() for q in s["questions"]
        if q["status"] == "teilweise"
    )

    table_rows = [
        ["Metric", "Value"],
        ["Total questions", str(n_total)],
        ["Answered", str(n_beantwortet)],
        ["Pre-filled", str(n_vorausgef)],
        ["Partially answered", str(n_teilweise)],
        ["Progress", f"{n_beantwortet/n_total*100:.1f}%"],
    ]
    blocks.append({"type": "table", "header_row": True, "rows": table_rows})

    print(f"  {len(blocks)} blocks built")
    print()

    print("=== 3. Write DOCX ===")
    res = _docx_create_from_data(file_path=OUTPUT_FILE, blocks=blocks)
    print(f"  success={res.get('success')}, blocks_written={res.get('blocks_written')}")
    print(f"  counts={res.get('counts')}, size={res.get('size_bytes')}B")
    print()

    print("=== 4. Verify ===")
    v = _docx_verify_file(
        file_path=OUTPUT_FILE,
        expected_substrings=["AI Nation Grant", "VibeMind", "Question", "Answer"],
        min_paragraphs=20,
        min_tables=1,
    )
    print(f"  verify success={v.get('success')}")
    print()

    print("=== 5. Evaluate ===")
    e = _file_evaluate(
        file_path=OUTPUT_FILE,
        expected_intent=(
            f"Investor-ready Word application for AI Nation Grant: "
            f"cover page, table of contents, all {n_total} questions across "
            f"{len([s for s in sections.values() if s['questions']])} sections "
            "with question/answer/status, plus a status overview table at the end."
        ),
        source_data_description=(
            f"Single markdown file with {n_total} structured Q&A entries"
        ),
    )
    score = e.get("score", 0)
    print(f"  score: {score}/100")
    print(f"  {e.get('summary', '')}")
    if e.get("issues"):
        for i in e["issues"][:3]:
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
        "name": "roarboot-grant-application-docx",
        "description": "Generates investor-ready Word DOCX of the AI Nation Grant application from the Roarboot Fragenkatalog markdown. Cover, TOC, sections, Q&A, status table.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [],
        "expected_state": {
            "description": f"DOCX with {n_total} Q&A entries + status table exists",
            "verification_tool": "docx_verify_file",
        },
        "confidence": confidence,
        "attempts": 1,
        "successes": 1 if v.get("success") else 0,
        "eval_score": score,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-grant-application-docx

Generates a Word DOCX submission-ready version of the AI Nation Grant
application directly from the structured Markdown Fragenkatalog.

## Pipeline

1. Parse the Fragenkatalog markdown ({total_q} questions across {len(sections)} sections)
2. Build DOCX blocks: cover page, TOC, per-section headings, per-question heading + Q/A/status
3. Append status overview table at the end
4. `docx_create_from_data` writes the file
5. `docx_verify_file` checks structure
6. `file_evaluate` quality-checks

## Current state ({datetime.now().date().isoformat()})

- Total questions: {n_total}
- Answered: {n_beantwortet}
- Pre-filled: {n_vorausgef}
- Partially: {n_teilweise}
- Progress: {n_beantwortet/n_total*100:.1f}%

## Reproducibility

`python scripts/demo_grant_docx.py` — no args, deterministic, ~5 seconds.
"""

    import yaml
    fm_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm_text}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print()

    print("=" * 60)
    print(f"DONE. file={OUTPUT_FILE}, eval={score}, conf={confidence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
