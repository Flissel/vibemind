"""project_refresh — re-sync a coding-project's manifest with its git state.

Reads the project's manifest at `.rowboat/knowledge/Coding-Projects/<slug>.md`,
queries the local git repo at `code_path` for the latest branch + commit + dirty
flag, and writes those back into the manifest's frontmatter and body.

Idempotent — running twice with no git changes produces no diff in the manifest.

What it updates:
  - frontmatter `git.branch` → current branch name
  - frontmatter `git.last_commit` → short HEAD sha (or "<sha>-dirty" if uncommitted changes)
  - body line `- **Aktueller Branch:** ...`
  - body line `- **Letzter Commit:** ...`

What it does NOT touch: `git.remote` (only `/github-create-repo` writes that),
`deployment.*` (only `/vercel-deploy` writes those), or anything outside the
git-related fields.

Usage::

    python project_refresh.py --slug test-bootstrap          # one project
    python project_refresh.py --all                          # all manifests
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROWBOAT_ROOT = Path("C:/Users/User/.rowboat")
MANIFESTS_DIR = ROWBOAT_ROOT / "knowledge" / "Coding-Projects"


def load_manifest(slug: str) -> tuple[Path, str, dict[str, Any]]:
    path = MANIFESTS_DIR / f"{slug}.md"
    if not path.is_file():
        return path, "", {}
    text = path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    if text.startswith("---"):
        end = text.find("\n---", 4)
        if end >= 0:
            for line in text[4:end].splitlines():
                m = re.match(r"^\s*([\w]+):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip()
    return path, text, fm


def query_git_state(code_path: Path) -> dict[str, Any]:
    """Return {branch, last_commit, dirty} or {error: ...}."""
    if not (code_path / ".git").is_dir():
        return {"error": f"not a git repo: {code_path}"}
    state: dict[str, Any] = {}
    try:
        state["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=code_path, text=True,
        ).strip()
    except subprocess.CalledProcessError as e:
        return {"error": f"git branch query failed: {e}"}
    try:
        state["last_commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=code_path, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        state["last_commit"] = ""
    try:
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=code_path, text=True,
        )
        state["dirty"] = bool(porcelain.strip())
    except subprocess.CalledProcessError:
        state["dirty"] = False
    return state


def update_manifest_git(manifest_path: Path, branch: str, last_commit: str, dirty: bool) -> bool:
    """Update branch + last_commit in both frontmatter and body. Returns True
    when at least one substitution actually changed something."""
    text = manifest_path.read_text(encoding="utf-8")
    commit_label = f"{last_commit}-dirty" if dirty and last_commit else last_commit

    new_text = text
    # Frontmatter: `  branch: X` under git:
    new_text = re.sub(
        r"(git:\s*\n(?:[^\n]*\n){0,5}?\s*branch:)\s*[^\n]*",
        rf"\1 {branch}",
        new_text, count=1,
    )
    new_text = re.sub(
        r"(git:\s*\n(?:[^\n]*\n){0,5}?\s*last_commit:)\s*[^\n]*",
        rf"\1 {commit_label}",
        new_text, count=1,
    )
    # Body
    new_text = re.sub(
        r"-\s*\*\*Aktueller Branch:\*\*\s*[^\n]*",
        f"- **Aktueller Branch:** {branch}",
        new_text, count=1,
    )
    new_text = re.sub(
        r"-\s*\*\*Letzter Commit:\*\*\s*[^\n]*",
        f"- **Letzter Commit:** {commit_label}",
        new_text, count=1,
    )
    if new_text == text:
        return False
    manifest_path.write_text(new_text, encoding="utf-8")
    return True


def refresh_one(slug: str) -> dict[str, Any]:
    path, _text, fm = load_manifest(slug)
    if not path.is_file():
        return {"slug": slug, "status": "error", "error": f"manifest not found: {path}"}
    code_path = Path(fm.get("code_path", ""))
    if not code_path.is_dir():
        return {"slug": slug, "status": "error", "error": f"code_path missing: {code_path}"}
    git_state = query_git_state(code_path)
    if "error" in git_state:
        return {"slug": slug, "status": "error", **git_state}
    changed = update_manifest_git(
        path,
        git_state["branch"],
        git_state["last_commit"],
        git_state["dirty"],
    )
    return {
        "slug": slug,
        "status": "ok",
        "changed": changed,
        "branch": git_state["branch"],
        "last_commit": git_state["last_commit"],
        "dirty": git_state["dirty"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="Single project slug to refresh")
    parser.add_argument("--all", action="store_true", help="Refresh every manifest")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("--slug or --all required")

    if args.all:
        slugs = [p.stem for p in MANIFESTS_DIR.glob("*.md")]
    else:
        slugs = [args.slug]

    results = [refresh_one(s) for s in slugs]
    indent = 2 if args.pretty else None
    print(json.dumps(results, indent=indent, ensure_ascii=False))
    return 0 if all(r.get("status") == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
