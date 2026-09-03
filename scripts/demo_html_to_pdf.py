"""Skill E1 — HTML to PDF.

Takes a scroll-snap HTML pitch deck and renders each slide as one
landscape PDF page via Playwright's print-to-pdf with page breaks
between slides.

Use cases:
- "Investor wants the deck for archive / email / printout"
- "Need a single immutable file to attach to grant submission"

Usage:
  python scripts/demo_html_to_pdf.py
  python scripts/demo_html_to_pdf.py --html <path>
  python scripts/demo_html_to_pdf.py --html <path> --pdf <out.pdf>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HR_DIR = Path("C:/Users/User/Desktop/HR")
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "html-to-pdf"


def find_latest_pitch_html() -> Path:
    candidates = sorted(HR_DIR.glob("VibeMind_Pitch_*.html"),
                        key=lambda p: -p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(
            "No VibeMind_Pitch_*.html in HR/. Run demo_pitch_html.py first."
        )
    return candidates[0]


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    """Render the HTML to PDF using Playwright. Inject CSS that turns
    each scroll-snap section into a print page so PDF gets one page per slide."""
    from playwright.sync_api import sync_playwright

    # Print CSS: scroll-snap doesn't survive print, so we override:
    # each .slide gets page-break-after: always and is sized exactly to one A4-landscape page.
    print_css = """
    @media print {
      @page { size: 297mm 167mm; margin: 0; }
      html, body { background: var(--bg) !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; scroll-snap-type: none !important; height: auto !important; overflow: visible !important; }
      nav.dots { display: none !important; }
      .slide {
        height: 167mm !important;
        width: 297mm !important;
        page-break-after: always;
        page-break-inside: avoid;
        scroll-snap-align: none !important;
        padding: 30mm 35mm !important;
      }
      .slide:last-child { page-break-after: auto; }
      h1 { font-size: 48pt !important; }
      h1.huge { font-size: 72pt !important; }
      h2 { font-size: 28pt !important; }
      .tagline { font-size: 18pt !important; }
      .stat .num { font-size: 36pt !important; }
    }
    """

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"file:///{html_path.as_posix()}")
        page.add_style_tag(content=print_css)
        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            landscape=True,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=str, default=None)
    parser.add_argument("--pdf", type=str, default=None)
    args = parser.parse_args()

    print("=== 1. Locate HTML ===")
    html_path = Path(args.html) if args.html else find_latest_pitch_html()
    if not html_path.is_file():
        print(f"  not found: {html_path}")
        return 2
    print(f"  source: {html_path}")
    print()

    pdf_path = Path(args.pdf) if args.pdf else html_path.with_suffix(".pdf")
    print(f"  target: {pdf_path}")
    print()

    print("=== 2. Render PDF via Playwright ===")
    html_to_pdf(html_path, pdf_path)
    print(f"  pdf saved: {pdf_path} ({pdf_path.stat().st_size}B)")
    print()

    print("=== 3. Persist SKILL.md ===")
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"
    frontmatter = {
        "name": "roarboot-html-to-pdf",
        "description": "Renders an HTML pitch deck as a landscape A4 PDF via Playwright print-to-pdf, one page per slide.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [{"name": "html", "type": "string"},
                   {"name": "pdf", "type": "string"}],
        "expected_state": {"description": "PDF with one page per HTML slide exists",
                           "verification_tool": "none"},
        "confidence": 1.0,
        "attempts": 1,
        "successes": 1,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    body = f"""# roarboot-html-to-pdf

Renders the same HTML deck as a PDF for archival/email/print. Uses
Playwright's native print-to-pdf with custom @page CSS so each `.slide`
becomes exactly one landscape page.

## Pipeline

1. Find newest `VibeMind_Pitch_*.html` in HR/
2. Inject print CSS: `@page` 297mm x 167mm landscape, `.slide` -> page-break-after
3. Playwright `page.pdf()` -> PDF

## Last run ({datetime.now().date().isoformat()})

- Source: {html_path.name}
- Target: {pdf_path.name}
- Size: {pdf_path.stat().st_size}B

## Usage

```
python scripts/demo_html_to_pdf.py
python scripts/demo_html_to_pdf.py --html <path> --pdf <out>
```
"""
    import yaml
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print()

    print("=" * 60)
    print(f"DONE. PDF: {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
