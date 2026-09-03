"""project_resolver — resolve a project alias from a prompt to a code_path.

Scans all `.rowboat/knowledge/Coding-Projects/*.md` manifests, builds an
alias-table, and decides whether a given user prompt references a known project.

Resolution strategy (first hit wins):

  1. **Explicit prefix** — prompt starts with `"<alias>: ..."` or
     `"in <alias>: ..."` (German: "in <alias>:").
  2. **First-30-tokens word match** — a project's slug/alias appears as a
     standalone word in the prompt's opening (so "in foo do bar" matches but
     "discuss foo as a concept" doesn't, because we only scan the start).

If nothing matches, returns `None` and the wrapper falls back to its default
project cwd (Vibemind_V1).

The resolver is intentionally **conservative**: false-positive routing into the
wrong project is worse than no routing. So we only match on opening context.

Usage::

    from project_resolver import resolve
    result = resolve("in test-bootstrap: add a /health endpoint")
    # => {"slug": "test-bootstrap", "code_path": "C:/.../test-bootstrap",
    #     "manifest_path": "...", "match": "explicit-prefix"}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


MANIFESTS_DIR = Path("C:/Users/User/.rowboat/knowledge/Coding-Projects")


def parse_frontmatter(md_path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter from a manifest md file.

    Very lightweight (no yaml dep) — we only need: name, slug, code_path,
    aliases. Falls back to {} if anything looks off.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end_idx = text.find("\n---", 4)
    if end_idx < 0:
        return {}
    fm_block = text[4:end_idx].strip()

    fields: dict[str, Any] = {}
    for line in fm_block.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        # parse JSON-style list (we wrote aliases/tags as json strings)
        if value.startswith("[") and value.endswith("]"):
            try:
                fields[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        fields[key] = value
    return fields


def load_all_projects() -> list[dict[str, Any]]:
    """Discover every coding-project manifest and return their key fields."""
    if not MANIFESTS_DIR.is_dir():
        return []
    projects: list[dict[str, Any]] = []
    for md in sorted(MANIFESTS_DIR.glob("*.md")):
        fm = parse_frontmatter(md)
        if not fm or fm.get("type") != "coding-project":
            continue
        slug = fm.get("slug") or md.stem
        code_path = fm.get("code_path")
        if not code_path:
            continue
        aliases = fm.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        # Ensure slug itself is always a valid alias
        if slug not in aliases:
            aliases.append(slug)
        projects.append({
            "slug": slug,
            "name": fm.get("name", slug),
            "code_path": code_path,
            "manifest_path": str(md).replace("\\", "/"),
            "aliases": aliases,
        })
    return projects


def build_alias_index(projects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Lowercased alias -> project entry. Longer aliases win in tie-breaks."""
    index: dict[str, dict[str, Any]] = {}
    for p in projects:
        for a in p["aliases"]:
            a_lc = a.lower().strip()
            if not a_lc:
                continue
            # Keep the project; if conflict, prefer the one whose alias is longer
            # (more-specific wins).
            existing = index.get(a_lc)
            if existing is None or len(a_lc) > max(len(x.lower()) for x in existing["aliases"] if x):
                index[a_lc] = p
    return index


# Regex for "<alias>: rest" or "in <alias>: rest" / "im <alias>: rest"
# `<alias>` matches non-whitespace tokens that may contain hyphen/dot/underscore.
PREFIX_RE = re.compile(
    r"^\s*(?:in|im)?\s*([a-z0-9][\w\.\- ]{0,60}?)\s*[:\-]\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)


def resolve(prompt: str) -> dict[str, Any] | None:
    """Resolve a project from a prompt. Returns None when no match."""
    projects = load_all_projects()
    if not projects:
        return None
    index = build_alias_index(projects)

    # Strategy 1: explicit "<alias>: rest"
    m = PREFIX_RE.match(prompt)
    if m:
        candidate = m.group(1).strip().lower()
        if candidate in index:
            return {**index[candidate], "match": "explicit-prefix", "stripped_prompt": m.group(2).strip()}
        # Try without trailing/leading spaces compressed
        compressed = re.sub(r"\s+", " ", candidate)
        if compressed in index:
            return {**index[compressed], "match": "explicit-prefix", "stripped_prompt": m.group(2).strip()}

    # Strategy 2: standalone token match in first 30 words
    head = " ".join(prompt.split()[:30]).lower()
    head_tokens = set(re.findall(r"[a-z0-9][\w\-]*", head))
    # Prefer the longest matching alias (most-specific)
    best: tuple[int, dict[str, Any]] | None = None
    for alias_lc, proj in index.items():
        # alias might be multi-word ("test bootstrap"); check whole alias in head
        if " " in alias_lc:
            if alias_lc in head:
                score = len(alias_lc)
                if best is None or score > best[0]:
                    best = (score, proj)
        else:
            if alias_lc in head_tokens:
                score = len(alias_lc)
                if best is None or score > best[0]:
                    best = (score, proj)
    if best is not None:
        return {**best[1], "match": "token-in-head"}

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="prompt text (or read stdin)")
    parser.add_argument("--list", action="store_true", help="list all known projects")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.list:
        projects = load_all_projects()
        for p in projects:
            print(f"  {p['slug']:30s} -> {p['code_path']}")
            print(f"      aliases: {p['aliases']}")
        if not projects:
            print("(no coding-projects found in", MANIFESTS_DIR, ")", file=sys.stderr)
        return 0

    if args.prompt:
        prompt = " ".join(args.prompt)
    else:
        prompt = sys.stdin.read().strip()
    if not prompt:
        print(json.dumps({"error": "empty prompt"}), file=sys.stderr)
        return 2

    result = resolve(prompt)
    out = result if result else {"match": None}
    if args.pretty:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
