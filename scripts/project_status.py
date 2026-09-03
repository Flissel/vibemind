"""project_status — show a human-readable status of one (or all) coding-projects.

Reads the manifest, optionally re-syncs git state via project_refresh, and prints
a status report. Use `--all` for an overview table.

Output formats:
  - default: pretty markdown (good for piping into a chat reply)
  - --json: machine-readable

Examples::

    python project_status.py --slug openclaude-test-deploy
    python project_status.py --all --refresh             # full sync + report
    python project_status.py --slug foo --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Force UTF-8 on stdout to survive Windows cp1252 defaults — manifests can
# contain any utf-8 chars.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROWBOAT_ROOT = Path("C:/Users/User/.rowboat")
MANIFESTS_DIR = ROWBOAT_ROOT / "knowledge" / "Coding-Projects"

# Reuse project_refresh for live git sync
sys.path.insert(0, str(Path(__file__).parent))
try:
    from project_refresh import refresh_one  # type: ignore
except ImportError:
    refresh_one = None  # graceful fallback


def parse_manifest(slug: str) -> dict[str, Any] | None:
    path = MANIFESTS_DIR / f"{slug}.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    fm: dict[str, Any] = {"_path": str(path).replace("\\", "/")}
    block = text[4:end]
    current_key = None
    current_dict: dict[str, str] | None = None
    for line in block.splitlines():
        # Top-level "key: value" or "key:" (dict-opener)
        m_top = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m_top:
            key, value = m_top.group(1), m_top.group(2).strip()
            if value:
                fm[key] = value
                current_key = None
                current_dict = None
            else:
                current_key = key
                current_dict = {}
                fm[key] = current_dict
            continue
        # Indented "  key: value" inside a current dict
        m_nested = re.match(r"^\s+([a-z_]+):\s*(.*)$", line)
        if m_nested and current_dict is not None:
            current_dict[m_nested.group(1)] = m_nested.group(2).strip()
    return fm


def list_all_slugs() -> list[str]:
    if not MANIFESTS_DIR.is_dir():
        return []
    return sorted(p.stem for p in MANIFESTS_DIR.glob("*.md"))


def format_status_markdown(fm: dict[str, Any]) -> str:
    name = fm.get("name", "?")
    slug = fm.get("slug", "?")
    code_path = fm.get("code_path", "?")
    stack = fm.get("stack") or {}
    git = fm.get("git") or {}
    deploy = fm.get("deployment") or {}
    tags = fm.get("tags", "—")

    lines = [
        f"### {name} (`{slug}`)",
        f"- **Pfad:** `{code_path}`",
    ]
    if isinstance(stack, dict):
        lang = stack.get("language", "—")
        framework = stack.get("framework", "—")
        lines.append(f"- **Stack:** {lang} {framework}")
    if isinstance(git, dict):
        lines.append(f"- **Git:** branch `{git.get('branch', '—')}` · last commit `{git.get('last_commit', '—')}`")
        remote = git.get("remote", "—")
        if remote and remote != "—":
            lines.append(f"- **Remote:** {remote}")
    if isinstance(deploy, dict):
        url = deploy.get("url", "—")
        provider = deploy.get("provider", "—")
        if url and url != "—":
            lines.append(f"- **Deployed:** {provider} -> {url}")
        else:
            lines.append(f"- **Deployed:** (not yet)")
    if tags and tags != "—":
        lines.append(f"- **Tags:** {tags}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="Single project")
    parser.add_argument("--all", action="store_true", help="All projects")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-sync git state from disk before reporting")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("--slug or --all required")

    slugs = list_all_slugs() if args.all else [args.slug]

    reports: list[dict[str, Any]] = []
    for slug in slugs:
        if args.refresh and refresh_one is not None:
            refresh_one(slug)
        fm = parse_manifest(slug)
        if fm is None:
            reports.append({"slug": slug, "error": "manifest not found"})
            continue
        reports.append(fm)

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
        return 0

    # Markdown output
    if args.all:
        print(f"# Coding-Projekte ({len(reports)})\n")
    for fm in reports:
        if "error" in fm:
            print(f"### {fm['slug']} — *error: {fm['error']}*\n")
            continue
        print(format_status_markdown(fm))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
