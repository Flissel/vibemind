"""Skill D — HTML to PPTX converter.

Takes a scroll-snap HTML pitch deck (like the one Skill B produces),
screenshots each `<section class="slide">` via headless Playwright at
1920x1080, and assembles a PowerPoint deck where each slide is the
screenshot as a full-bleed background.

Use cases:
- "Investor wants the deck as PPTX for upload to their portal"
- "Need to share with someone who can't open HTML"
- "Want to embed in a larger PowerPoint deck"

Usage:
  python scripts/demo_html_to_pptx.py
  python scripts/demo_html_to_pptx.py --html <path>
  python scripts/demo_html_to_pptx.py --html <path> --pptx <out.pptx>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HR_DIR = Path("C:/Users/User/Desktop/HR")
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "html-to-pptx"


def find_latest_pitch_html() -> Path:
    candidates = sorted(HR_DIR.glob("VibeMind_Pitch_*.html"),
                        key=lambda p: -p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(
            "No VibeMind_Pitch_*.html in C:/Users/User/Desktop/HR/. "
            "Run scripts/demo_pitch_html.py first."
        )
    return candidates[0]


def html_to_screenshots(html_path: Path, out_dir: Path,
                       width: int = 1920, height: int = 1080) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    images: list[Path] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.goto(f"file:///{html_path.as_posix()}")
        # Disable scroll-snap so slide-N navigation jumps cleanly
        page.add_style_tag(content="body{scroll-snap-type:none!important;}")
        # Count slides
        slide_count = page.evaluate("document.querySelectorAll('section.slide').length")
        print(f"  found {slide_count} slides")

        for i in range(1, slide_count + 1):
            # Scroll to slide-i
            page.evaluate(f"document.getElementById('slide-{i}').scrollIntoView()")
            page.wait_for_timeout(300)  # let any transitions settle
            png = out_dir / f"slide_{i:02d}.png"
            # Screenshot only the viewport (already at the slide top)
            page.screenshot(path=str(png), full_page=False)
            images.append(png)
            print(f"  slide {i} -> {png.name} ({png.stat().st_size}B)")
        browser.close()
    return images


def screenshots_to_pptx(images: list[Path], pptx_path: Path,
                        title: str = "VibeMind Pitch") -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    # Standard 16:9 dimensions (already default in modern python-pptx)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]  # truly blank layout
    for img in images:
        slide = prs.slides.add_slide(blank_layout)
        # Full-bleed image
        slide.shapes.add_picture(
            str(img), 0, 0,
            width=prs.slide_width, height=prs.slide_height,
        )
    prs.save(str(pptx_path))
    print(f"  pptx saved: {pptx_path} ({pptx_path.stat().st_size}B)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=str, default=None,
                        help="Path to source HTML; default = newest VibeMind_Pitch_*.html in HR/")
    parser.add_argument("--pptx", type=str, default=None,
                        help="Output PPTX path; default = same name with .pptx extension")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    print("=== 1. Locate HTML ===")
    if args.html:
        html_path = Path(args.html)
    else:
        html_path = find_latest_pitch_html()
    if not html_path.is_file():
        print(f"  not found: {html_path}")
        return 2
    print(f"  source: {html_path}")
    print()

    if args.pptx:
        pptx_path = Path(args.pptx)
    else:
        pptx_path = html_path.with_suffix(".pptx")
    print(f"  target: {pptx_path}")
    print()

    print("=== 2. Render slides via Playwright ===")
    screenshots_dir = HR_DIR / "_pptx_screenshots" / html_path.stem
    images = html_to_screenshots(html_path, screenshots_dir,
                                  width=args.width, height=args.height)
    print()

    if not images:
        print("  no images generated — abort")
        return 3

    print("=== 3. Build PPTX ===")
    screenshots_to_pptx(images, pptx_path, title=html_path.stem)
    print()

    print("=== 4. Persist SKILL.md ===")
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"
    frontmatter = {
        "name": "roarboot-html-to-pptx",
        "description": "Converts a scroll-snap HTML pitch deck (Skill B output) to PowerPoint by screenshotting each slide via headless Playwright at 1920x1080 and embedding as full-bleed images.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [{"name": "html", "type": "string"},
                   {"name": "pptx", "type": "string"}],
        "expected_state": {
            "description": "PPTX with one slide per HTML section exists",
            "verification_tool": "none",
        },
        "confidence": 1.0,
        "attempts": 1,
        "successes": 1,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-html-to-pptx

Converts an HTML pitch deck (Skill B output) into a PowerPoint deck where
each slide is a full-bleed screenshot. The HTML stays the source of truth,
PPTX is a derived artifact for tools that need PowerPoint format.

## Pipeline

1. Find newest `VibeMind_Pitch_*.html` in `C:/Users/User/Desktop/HR/`
2. Headless Playwright opens HTML at 1920x1080, disables scroll-snap CSS
3. For each `<section class="slide">`, scroll into view + screenshot
4. python-pptx builds a 16:9 deck with one slide per image

## Last run ({datetime.now().date().isoformat()})

- Source: {html_path.name}
- Target: {pptx_path.name}
- Slides: {len(images)}
- Resolution: {args.width}x{args.height}

## Reproducibility

```
python scripts/demo_html_to_pptx.py
python scripts/demo_html_to_pptx.py --html <path> --pptx <out>
```
"""
    import yaml
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print()

    print("=" * 60)
    print(f"DONE.")
    print(f"  HTML  : {html_path}")
    print(f"  PPTX  : {pptx_path}")
    print(f"  Slides: {len(images)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
