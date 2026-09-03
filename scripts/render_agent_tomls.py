"""
Render OpenFang agent.toml files from .tmpl templates + shared memory.

For each `<dir>/agent.toml.tmpl` found, look up `memory_profile` (key in TOML),
load that profile via vibemind_shared.load_memory(), substitute {{MEMORY}}
in the template, and write to `<dir>/agent.toml`.

Run this:
  - Once after editing a template
  - From OpenFang's pre-start hook (if you wire it in)
  - From `/memory-review` accept (so OpenFang agents pick up new memory)

Hard-fails if a template references a profile that load_memory can't supply.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

VIBEMIND_ROOT = Path(__file__).resolve().parent.parent
SHARED_SRC = VIBEMIND_ROOT / "vibemind-os" / "shared" / "src"
AGENTS_DIR = VIBEMIND_ROOT / "vibemind-os" / "openfang" / "agents"
TOKEN = "{{MEMORY}}"

if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from vibemind_shared import load_memory, MemoryLoadError  # noqa: E402


_PROFILE_RE = re.compile(r'^memory_profile\s*=\s*"([^"]+)"', re.MULTILINE)


def _extract_profile(template: str) -> str:
    m = _PROFILE_RE.search(template)
    return m.group(1) if m else "coding"


def _safe_for_literal_triple_quote(text: str) -> str:
    # Templates use TOML literal multi-line strings ('''...''') which interpret
    # nothing — no backslash escapes, no unicode. The only restriction is the
    # content cannot contain ''' itself. If it does, replace one quote with the
    # unicode prime symbol to break the sequence without changing meaning.
    return text.replace("'''", "''′")


def render_one(tmpl_path: Path) -> tuple[Path, str]:
    target = tmpl_path.with_suffix("")  # strips final .tmpl, leaving .toml
    template = tmpl_path.read_text(encoding="utf-8")
    profile = _extract_profile(template)
    try:
        memory = load_memory(profile)
    except MemoryLoadError as e:
        raise RuntimeError(f"{tmpl_path}: memory profile {profile!r} failed: {e}") from e
    rendered = template.replace(TOKEN, _safe_for_literal_triple_quote(memory))
    target.write_text(rendered, encoding="utf-8")
    return target, profile


def main() -> int:
    templates = list(AGENTS_DIR.glob("*/agent.toml.tmpl"))
    if not templates:
        print(f"no templates found under {AGENTS_DIR}", file=sys.stderr)
        return 1
    for t in templates:
        try:
            target, profile = render_one(t)
            print(f"rendered {target} (profile={profile}, {target.stat().st_size} bytes)")
        except Exception as e:
            print(f"FAIL {t}: {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
