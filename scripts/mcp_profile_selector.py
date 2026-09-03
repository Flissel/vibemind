"""Adaptive MCP-profile + skill selector for openclaude-vibemind.

Given a user prompt, decide which MCP profile (`bare`/`code`/`desktop`/`full`)
to start openclaude with, and which skills should be hinted to the model.

Two-layer strategy for robustness:

1. **Heuristic** (always on): keyword/regex match against the prompt to pick
   a baseline profile. Cheap, deterministic, no external deps.
2. **Qdrant boost** (if reachable): query the `vibemind_skills` collection,
   inspect the top-K skills' `app` namespace, refine the profile. The skills
   list also gets injected into openclaude's append-system-prompt as `/skill-name`
   hints so the model knows it can invoke them.

If Qdrant is offline, the heuristic path stays correct — no breakage, just
less precise.

Output: JSON with `{profile, skills, reason}`. The wrapper consumes this.

Usage::

    python scripts/mcp_profile_selector.py "fix the bug in agent_loop.rs"
    # => {"profile": "code", "skills": ["systematic-debugging", "test-fixing"], ...}
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6730")
COLLECTION = os.environ.get("VIBEMIND_SKILLS_COLLECTION", "vibemind_skills")
QDRANT_TIMEOUT_SECS = 2.0  # short — we tolerate Qdrant being down


# ---------------------------------------------------------------------------
# Layer 1 — heuristic keyword router.
# ---------------------------------------------------------------------------

# Order matters: first match wins. Patterns are German + English because the
# user voice-codes in both. Compiled once at module load.
HEURISTIC_RULES: list[tuple[re.Pattern[str], str]] = [
    # Desktop-automation indicators: app names, UI verbs, screen interaction.
    (re.compile(
        r"\b(excel|word|powerpoint|outlook|browser|chrome|firefox|edge|click|"
        r"mouse|maus|tippen|klicken|fenster|screen|screenshot|window|app)\b",
        re.IGNORECASE,
    ), "desktop"),
    # System/security: docker, registry, firewall, network.
    (re.compile(
        r"\b(docker|container|registry|firewall|network|netzwerk|process|"
        r"prozess|driver|treiber|netstat|systemd|service)\b",
        re.IGNORECASE,
    ), "full"),
    # Code-search / refactor / bug fix indicators.
    (re.compile(
        r"\b(code|funktion|function|class|klasse|module|modul|refactor|test|"
        r"bug|fehler|debug|grep|suche|search|fix|implement|implementier|"
        r"\.py|\.rs|\.ts|\.js|\.tsx|\.go|\.java|repo|repository|commit|"
        r"branch|merge|pull request|pr\b)\b",
        re.IGNORECASE,
    ), "code"),
    # Pure file/CLI work — bare is enough.
    (re.compile(
        r"\b(read|lies|write|schreib|create|erstell|delete|l(o|ö)sch|"
        r"file|datei|directory|ordner|hello world|smoke test)\b",
        re.IGNORECASE,
    ), "bare"),
]

# Map skill `app` namespace -> recommended profile.
APP_TO_PROFILE: dict[str, str] = {
    # Productivity apps -> desktop-automation MCP
    "excel": "desktop",
    "word": "desktop",
    "powerpoint": "desktop",
    "outlook": "desktop",
    "chrome": "desktop",
    "browser": "desktop",
    "file-explorer": "desktop",
    "vscode": "desktop",
    "claude-desktop": "desktop",
    # Heavy infrastructure namespaces -> full (all 25 MCPs)
    # Only namespaces that really need docker/n8n/system tools.
    "system-poc": "full",
    "security-poc": "full",
    "docker": "full",
    "n8n": "full",
    # Code-oriented namespaces -> code (fungus-search + skills)
    "dev": "code",
    "devops": "code",   # test-fixing/git-pushing/etc. — pure code work
    "code": "code",
    "git": "code",
    "review": "code",
    "system": "code",   # script-style system stuff, not heavy MCPs
    "security": "code", # security-review is code, not the system MCPs
    "openclaw": "code",
    "tapestry": "code",
    "science": "code",
    # HR/business -> bare (just file tools + skills)
    "hr": "bare",
    "business": "bare",
    "office": "bare",
}

PROFILE_PRIORITY = {"bare": 0, "code": 1, "desktop": 2, "full": 3}


def heuristic_pick(prompt: str) -> str:
    for pattern, profile in HEURISTIC_RULES:
        if pattern.search(prompt):
            return profile
    return "code"  # safe default


# ---------------------------------------------------------------------------
# Layer 2 — Qdrant semantic skill search (optional).
# ---------------------------------------------------------------------------

def qdrant_reachable() -> bool:
    try:
        req = urllib.request.Request(f"{QDRANT_URL}/", method="GET")
        with urllib.request.urlopen(req, timeout=QDRANT_TIMEOUT_SECS) as resp:
            return resp.status == 200
    except Exception:
        return False


def qdrant_search_skills(prompt: str, limit: int = 5) -> list[dict[str, Any]]:
    """Best-effort skill search. Returns [] on any failure."""
    # The indexer reads QDRANT_URL from env at import time; make sure it sees ours.
    os.environ["QDRANT_URL"] = QDRANT_URL
    sys.path.insert(0, str(ROOT / "vibemind-os" / "skills"))
    try:
        from _indexer import _load_dotenv_into_env, search  # type: ignore
    except Exception as e:
        print(f"[selector] could not import _indexer: {e}", file=sys.stderr)
        return []

    _load_dotenv_into_env()
    # search() needs OPENAI_API_KEY for embed; if missing we silently skip.
    if not os.environ.get("OPENAI_API_KEY"):
        return []
    try:
        results = search(prompt, limit=limit)
    except Exception as e:
        print(f"[selector] qdrant search failed: {e}", file=sys.stderr)
        return []
    return results


def refine_profile_from_skills(
    base_profile: str,
    skills: list[dict[str, Any]],
    min_score: float = 0.35,
) -> tuple[str, list[str]]:
    """Look at top skills' apps; upgrade base_profile if a hit needs more MCPs.

    Returns `(profile, skill_names)`. `skill_names` are the slugs we'll hint
    to openclaude.
    """
    relevant: list[tuple[str, str, float]] = []  # (name, app, score)
    for r in skills:
        score = float(r.get("score") or 0)
        if score < min_score:
            continue
        payload = r.get("payload") or {}
        app = (payload.get("app") or "").lower()
        name = payload.get("name") or ""
        if name and app:
            relevant.append((name, app, score))

    if not relevant:
        return base_profile, []

    suggested = base_profile
    base_rank = PROFILE_PRIORITY.get(base_profile, 1)
    for _name, app, _score in relevant:
        candidate = APP_TO_PROFILE.get(app)
        if candidate and PROFILE_PRIORITY.get(candidate, 0) > PROFILE_PRIORITY.get(suggested, base_rank):
            suggested = candidate

    skill_names = [name for name, _app, _score in relevant]
    return suggested, skill_names


# ---------------------------------------------------------------------------
# Top-level entry.
# ---------------------------------------------------------------------------

def select(prompt: str, limit: int = 5) -> dict[str, Any]:
    base = heuristic_pick(prompt)
    reason_parts = [f"heuristic={base}"]

    skills: list[str] = []
    if qdrant_reachable():
        hits = qdrant_search_skills(prompt, limit=limit)
        if hits:
            refined, skills = refine_profile_from_skills(base, hits)
            if refined != base:
                reason_parts.append(f"qdrant_refined={base}->{refined}")
            else:
                reason_parts.append(f"qdrant_agreed={refined}")
            base = refined
        else:
            reason_parts.append("qdrant_no_hits")
    else:
        reason_parts.append("qdrant_offline")

    return {
        "profile": base,
        "skills": skills,
        "reason": " ".join(reason_parts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="prompt text (or read stdin)")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if args.prompt:
        prompt = " ".join(args.prompt)
    else:
        prompt = sys.stdin.read().strip()

    if not prompt:
        print(json.dumps({"error": "empty prompt"}), file=sys.stderr)
        return 2

    result = select(prompt, limit=args.limit)
    if args.pretty:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
