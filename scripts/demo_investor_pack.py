"""Skill E3 — Investor-Pack ZIP.

Bundles all four investor-facing artifacts into a single deployable ZIP:
  - Investor_Grant_Antrag_2026.docx     (full grant application)
  - VibeMind_Pitch_<theme>_<ts>.html    (interactive deck)
  - VibeMind_Pitch_<theme>_<ts>.pdf     (printable deck)
  - VibeMind_Pitch_<theme>_<ts>.pptx    (PowerPoint deck)
  - README.md                           (manifest with hashes + descriptions)

Pipeline:
  1. (optional) regenerate the four artifacts via existing skills
  2. Compute SHA256 for each
  3. Write README.md manifest
  4. Bundle into VibeMind_Investor_Pack_<ts>.zip

Usage:
  python scripts/demo_investor_pack.py
  python scripts/demo_investor_pack.py --regenerate
  python scripts/demo_investor_pack.py --theme emerald --regenerate
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
HR_DIR = Path("C:/Users/User/Desktop/HR")
SKILL_DIR = HERE.parent / "vibemind-os" / "skills" / "roarboot" / "investor-pack"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def find_latest(pattern: str) -> Path | None:
    cands = sorted(HR_DIR.glob(pattern), key=lambda p: -p.stat().st_mtime)
    return cands[0] if cands else None


def regenerate_artifacts(theme: str, python_exe: str) -> None:
    """Re-run the four upstream skills before bundling."""
    print("=== Regenerating artifacts ===")

    # 1. Grant DOCX
    print("  [1/4] grant DOCX...")
    subprocess.run(
        [python_exe, "-u", str(HERE / "demo_grant_docx.py")],
        cwd=str(HERE.parent), check=False, capture_output=True,
    )

    # 2. Pitch HTML
    print(f"  [2/4] pitch HTML (theme={theme})...")
    subprocess.run(
        [python_exe, "-u", str(HERE / "demo_pitch_html.py"), "--theme", theme],
        cwd=str(HERE.parent), check=False, capture_output=True,
    )

    # 3. Pitch PDF (uses latest HTML)
    print("  [3/4] pitch PDF...")
    subprocess.run(
        [python_exe, "-u", str(HERE / "demo_html_to_pdf.py")],
        cwd=str(HERE.parent), check=False, capture_output=True,
    )

    # 4. Pitch PPTX (uses latest HTML)
    print("  [4/4] pitch PPTX...")
    subprocess.run(
        [python_exe, "-u", str(HERE / "demo_html_to_pptx.py")],
        cwd=str(HERE.parent), check=False, capture_output=True,
    )
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true",
                        help="Re-run all four upstream skills before bundling")
    parser.add_argument("--theme", default="midnight",
                        choices=["midnight", "emerald", "crimson", "arctic",
                                 "obsidian", "sunset"])
    args = parser.parse_args()

    if args.regenerate:
        regenerate_artifacts(args.theme, sys.executable)

    print("=== 1. Locate artifacts ===")
    artifacts = {
        "grant_docx": find_latest("Investor_Grant_Antrag_*.docx"),
        "pitch_html": find_latest("VibeMind_Pitch_*.html"),
        "pitch_pdf": find_latest("VibeMind_Pitch_*.pdf"),
        "pitch_pptx": find_latest("VibeMind_Pitch_*.pptx"),
    }
    for label, p in artifacts.items():
        if p is None:
            print(f"  MISSING: {label}")
            return 2
        print(f"  {label:12} -> {p.name} ({p.stat().st_size:,}B)")
    print()

    print("=== 2. Compute hashes ===")
    hashes = {label: sha256(p) for label, p in artifacts.items()}
    for label, h in hashes.items():
        print(f"  {label:12}: {h[:16]}...")
    print()

    print("=== 3. Write README manifest ===")
    ts = datetime.now()
    pack_name = f"VibeMind_Investor_Pack_{ts.strftime('%Y%m%d_%H%M%S')}"
    pack_dir = HR_DIR / pack_name
    pack_dir.mkdir(parents=True, exist_ok=True)

    # Copy artifacts into pack-staging dir with normalized names
    target_names = {
        "grant_docx": "1_Grant_Application.docx",
        "pitch_html": "2_Pitch_Deck.html",
        "pitch_pdf":  "3_Pitch_Deck.pdf",
        "pitch_pptx": "4_Pitch_Deck.pptx",
    }
    copied = []
    for label, src in artifacts.items():
        dest = pack_dir / target_names[label]
        shutil.copy(src, dest)
        copied.append((label, dest, src.name))

    readme = f"""# VibeMind Investor Pack
_Generated: {ts.isoformat(timespec='seconds')}_

This pack contains everything an investor or grant reviewer needs to
evaluate VibeMind:

| File | Purpose | Source artifact |
|---|---|---|
| `1_Grant_Application.docx` | Full AI Nation Grant application — 50 questions across 8 sections | `{artifacts['grant_docx'].name}` |
| `2_Pitch_Deck.html` | Interactive 6-slide pitch — open in browser, scroll-snap | `{artifacts['pitch_html'].name}` |
| `3_Pitch_Deck.pdf` | Printable pitch — landscape A4, one page per slide | `{artifacts['pitch_pdf'].name}` |
| `4_Pitch_Deck.pptx` | PowerPoint pitch — for portals that require .pptx upload | `{artifacts['pitch_pptx'].name}` |

## SHA256 hashes

```
{chr(10).join(f"{hashes[k]}  {target_names[k]}" for k in artifacts.keys())}
```

## Source-of-truth

All artifacts derive from the Roarboot knowledge graph at
`~/.rowboat/knowledge/`:

- 115 active project bubbles
- AI Nation Grant Fragenkatalog (50/53 questions answered)
- Bewerbung folder (Felix Baumann CV)

The grant DOCX is built from the structured Markdown via deterministic
regex parsing. The pitch HTML uses the same data plus aggregate stats.
PDF and PPTX are derived from the HTML (Playwright print-to-pdf + Playwright
screenshots → python-pptx).

Theme: **{args.theme}**

## Reproducibility

```
python scripts/demo_investor_pack.py --regenerate --theme {args.theme}
```

This regenerates all four artifacts from current Roarboot state and
re-bundles them into a fresh ZIP. Idempotent — same input = same output
modulo timestamp.

## Contact

VibeMind · contact via GitHub
github.com/Flissel
"""

    readme_path = pack_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    print(f"  README: {readme_path}")
    print()

    print("=== 4. Build ZIP ===")
    zip_path = HR_DIR / f"{pack_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in pack_dir.iterdir():
            if f.is_file():
                zf.write(f, arcname=f"{pack_name}/{f.name}")
    pack_size = zip_path.stat().st_size
    print(f"  zip: {zip_path} ({pack_size:,}B = {pack_size/1024/1024:.1f}MB)")
    print()

    print("=== 5. Persist SKILL.md ===")
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_md = SKILL_DIR / "SKILL.md"
    frontmatter = {
        "name": "roarboot-investor-pack",
        "description": "Bundles Grant DOCX + Pitch HTML/PDF/PPTX into one investor-ready ZIP with SHA256 manifest and reproducibility instructions.",
        "app": "roarboot",
        "requires_approval": False,
        "agents": ["*"],
        "inputs": [
            {"name": "regenerate", "type": "boolean", "description": "Re-run all upstream skills first"},
            {"name": "theme", "type": "string"},
        ],
        "expected_state": {"description": "ZIP file with 4 artifacts + README exists",
                           "verification_tool": "none"},
        "confidence": 1.0,
        "attempts": 1,
        "successes": 1,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    body = f"""# roarboot-investor-pack

One-shot bundler for the four investor-facing artifacts. Combines:
- Grant DOCX (Skill A)
- Pitch HTML (Skill B)
- Pitch PDF (Skill E1)
- Pitch PPTX (Skill D)

## What's inside

```
{pack_name}.zip
├── 1_Grant_Application.docx     ({artifacts['grant_docx'].stat().st_size:,}B)
├── 2_Pitch_Deck.html            ({artifacts['pitch_html'].stat().st_size:,}B)
├── 3_Pitch_Deck.pdf             ({artifacts['pitch_pdf'].stat().st_size:,}B)
├── 4_Pitch_Deck.pptx            ({artifacts['pitch_pptx'].stat().st_size:,}B)
└── README.md                    (with SHA256 manifest)
```

## Usage

```
python scripts/demo_investor_pack.py                          # bundle existing artifacts
python scripts/demo_investor_pack.py --regenerate             # regen all 4 first
python scripts/demo_investor_pack.py --regenerate --theme sunset
```

## Last bundle ({ts.date().isoformat()})

- Theme: {args.theme}
- Total ZIP size: {pack_size/1024/1024:.1f}MB
- Output: `{zip_path}`
"""

    import yaml
    fm = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=True).strip()
    skill_md.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
    print(f"  SKILL.md: {skill_md}")
    print()

    print("=" * 60)
    print(f"DONE.")
    print(f"  Pack folder: {pack_dir}")
    print(f"  Pack ZIP:    {zip_path} ({pack_size/1024/1024:.1f}MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
