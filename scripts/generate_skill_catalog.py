"""Generate INDEX.md catalog for vibemind-os/skills/.

Scans every SKILL.md, groups by app namespace, and writes a markdown
catalog with quick-stats + per-skill descriptions. Used as a discoverability
aid when the library is used as a git submodule by other repos.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "vibemind-os" / "skills"
OUTPUT = ROOT / "INDEX.md"


def parse_frontmatter(p: Path) -> dict:
    text = p.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}


def main() -> int:
    by_app: dict[str, list[dict]] = defaultdict(list)
    total = 0
    parse_errors = 0
    confidences: list[float] = []

    for skill_md in sorted(ROOT.glob("*/*/SKILL.md")):
        if any(part.startswith("_") or part.startswith(".") for part in skill_md.parts):
            continue
        fm = parse_frontmatter(skill_md)
        if not fm:
            parse_errors += 1
            continue
        app = skill_md.parent.parent.name
        name = fm.get("name", skill_md.parent.name)
        desc = (fm.get("description") or "").strip().replace("\n", " ")
        if len(desc) > 200:
            desc = desc[:197] + "..."
        conf = fm.get("confidence")
        if isinstance(conf, (int, float)):
            confidences.append(float(conf))
        # source-pack hint from metadata
        meta = fm.get("metadata") or {}
        source_pack = meta.get("source_pack") if isinstance(meta, dict) else None
        by_app[app].append({
            "name": name,
            "description": desc,
            "confidence": conf,
            "source_pack": source_pack,
            "slug": skill_md.parent.name,
        })
        total += 1

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Write INDEX.md
    lines: list[str] = []
    lines.append("# VibeMind Skill Library Index")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_  ")
    lines.append(f"_Total skills: **{total}** across **{len(by_app)}** app namespaces · avg confidence: **{avg_conf:.2f}**_")
    lines.append("")
    lines.append("This index lists every SKILL.md in `vibemind-os/skills/`. ")
    lines.append("Skills are auto-discoverable via `_loader.py` and semantically searchable via Qdrant (`vibemind_skills` collection).")
    lines.append("")

    # TOC
    lines.append("## Namespaces")
    lines.append("")
    lines.append("| App | Skills | Origin |")
    lines.append("|---|---:|---|")
    for app in sorted(by_app):
        skills = by_app[app]
        # Origin: most common source_pack, or "local"
        packs = [s.get("source_pack") for s in skills if s.get("source_pack")]
        origin = "imported" if packs else "local"
        if packs:
            most_common = max(set(packs), key=packs.count)
            origin = most_common
        anchor = app.lower().replace("-", "-")
        lines.append(f"| [`{app}`](#{anchor}) | {len(skills)} | {origin} |")
    lines.append("")

    # Per-app listing
    for app in sorted(by_app):
        skills = sorted(by_app[app], key=lambda s: s["name"])
        lines.append(f"## {app}")
        lines.append("")
        lines.append(f"_{len(skills)} skills_")
        lines.append("")
        lines.append("| Name | Description |")
        lines.append("|---|---|")
        for s in skills:
            n = s["name"]
            d = s["description"].replace("|", "\\|")
            lines.append(f"| `{n}` | {d} |")
        lines.append("")

    if parse_errors:
        lines.append(f"_⚠ {parse_errors} skill(s) had parse errors and were skipped._")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Regenerate with `python scripts/generate_skill_catalog.py`.")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"  total: {total} skills · {len(by_app)} namespaces · avg conf: {avg_conf:.2f}")
    print(f"  parse errors: {parse_errors}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
