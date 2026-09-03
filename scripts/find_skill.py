"""Self-service skill finder for Claude Code.

Workflow:
  1. Claude Code (or any agent) calls this with a task description
  2. Qdrant returns top-N relevant skills semantically
  3. Skill bodies are returned as concatenated markdown context

This is the "selbst-staendig" path: no curation, no symlinks, no claude
CLI integration needed. The skill content is just loaded as context.

Usage:
    python scripts/find_skill.py "debug a failing python test"
    python scripts/find_skill.py "refactor a function" --limit 5
    python scripts/find_skill.py "..." --print-body  # include full body, not just frontmatter
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vibemind-os" / "skills"))
from _indexer import _load_dotenv_into_env, search  # type: ignore

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "vibemind-os" / "skills"


def find_skill_path(name: str, app: str) -> Path | None:
    """Resolve a skill name to its SKILL.md path on disk."""
    app_dir = SKILLS_ROOT / app
    if not app_dir.is_dir():
        return None
    # Try exact folder match first (stripping app- prefix)
    short = name
    if short.startswith(f"{app}-"):
        short = short[len(app) + 1:]
    candidate = app_dir / short / "SKILL.md"
    if candidate.is_file():
        return candidate
    # Fall back: search for the name in any SKILL.md frontmatter
    for skill_md in app_dir.rglob("SKILL.md"):
        text = skill_md.read_text(encoding="utf-8", errors="replace")
        if f"name: {name}" in text[:500]:
            return skill_md
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="Natural-language task description")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--print-body", action="store_true",
                        help="Include full skill body, not just frontmatter")
    parser.add_argument("--min-score", type=float, default=0.4)
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of markdown")
    args = parser.parse_args()

    os.environ.setdefault("QDRANT_URL", "http://localhost:6730")
    _load_dotenv_into_env()

    results = search(args.task, limit=args.limit)
    results = [r for r in results if r.get("score", 0) >= args.min_score]

    if not results:
        print(f"# No skills found (min_score={args.min_score})", file=sys.stderr)
        return 1

    if args.json:
        import json
        out = []
        for r in results:
            p = r["payload"]
            path = find_skill_path(p["name"], p["app"])
            entry = {
                "score": r["score"],
                "name": p["name"],
                "app": p["app"],
                "description": p.get("description", ""),
                "path": str(path) if path else None,
            }
            if args.print_body and path:
                entry["body"] = path.read_text(encoding="utf-8")
            out.append(entry)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    # Markdown output — easy to paste into a chat as context
    print(f"# Skills for task: {args.task!r}")
    print()
    print(f"_Search returned {len(results)} skill(s) with score >= {args.min_score}_")
    print()

    for i, r in enumerate(results, 1):
        p = r["payload"]
        path = find_skill_path(p["name"], p["app"])
        print(f"## {i}. `{p['name']}` (score {r['score']:.3f}, app `{p['app']}`)")
        print()
        print(f"**Description:** {p.get('description', '')}")
        print()
        if path:
            print(f"**Path:** `{path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}`")
            print()
            if args.print_body:
                body = path.read_text(encoding="utf-8")
                print("```markdown")
                print(body)
                print("```")
                print()
        print("---")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
