"""PostToolUse hook — syntax-verify files openclaude just wrote/edited.

openclaude (Claude-Code fork) calls PostToolUse hooks after Edit/Write/MultiEdit.
The tool input arrives as JSON on stdin:

    {"tool_name": "Edit", "tool_input": {"file_path": "...", ...}, ...}

We pull the touched file path, and if it's a language we can cheaply
syntax-check, we parse it. On a syntax error we exit 2 with the error on
stderr — Claude-Code/openclaude treats hook exit-2 as a BLOCK, feeds stderr
back to the model, and the model gets a chance to fix its own broken edit in
the same turn.

Why this exists: gpt-4o-mini (openclaude-coder's backend) corrupts files on
non-trivial edits — observed inserting a code block ~12x between every line
of an existing file, then *reporting success*. A cheap deterministic syntax
gate catches that class of failure regardless of model strength.

Checkers (extend SYNTAX_CHECKERS as needed):
  .py            → ast.parse (in-process, no subprocess)
  .json          → json.loads
  (others)       → skipped (exit 0 — we only block on what we can verify)

Exit codes:
  0  = ok / not a checkable file / no file in payload (never block on these)
  2  = syntax error → BLOCK, stderr shown to model
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def _check_python(path: Path) -> str | None:
    """Return an error string if the file has a Python syntax error, else None."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"could not read {path}: {e}"
    try:
        ast.parse(src, filename=str(path))
        return None
    except SyntaxError as e:
        return (
            f"SyntaxError in {path.name} at line {e.lineno}: {e.msg}\n"
            f"  >>> {(e.text or '').rstrip()}"
        )


def _check_json(path: Path) -> str | None:
    try:
        json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return None
    except (OSError, json.JSONDecodeError) as e:
        return f"Invalid JSON in {path.name}: {e}"


SYNTAX_CHECKERS = {
    ".py": _check_python,
    ".json": _check_json,
}


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        # Can't parse the hook payload — don't block, just pass.
        return 0

    tool_input = payload.get("tool_input") or {}
    # Edit/Write/MultiEdit all carry file_path; MultiEdit may carry edits[].
    file_path = tool_input.get("file_path") or tool_input.get("path")
    if not file_path:
        return 0

    p = Path(file_path)
    if not p.is_file():
        return 0

    checker = SYNTAX_CHECKERS.get(p.suffix.lower())
    if checker is None:
        return 0  # no cheap checker for this type — don't block

    error = checker(p)
    if error is None:
        return 0

    # Block. stderr is fed back to the model by openclaude/Claude-Code.
    sys.stderr.write(
        f"[verify-edit-hook] Your edit left {p.name} syntactically broken. "
        f"Re-read the file and fix it — do NOT repeat the same edit.\n{error}\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
