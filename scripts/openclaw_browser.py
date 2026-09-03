"""openclaw_browser — thin wrapper around the openclaw container's browser CLI.

Runs `docker exec vibemind-openclaw openclaw browser <subcommand> [args...]`,
proxies the output back. Lets agents control a headless Chromium inside the
openclaw container without managing the container themselves.

What openclaw browser can do:
  navigate <url>          — open a page
  screenshot [--full-page]— PNG of current viewport
  snapshot [--format aria]— ARIA tree of the page (great for LLM consumption)
  click <ref> [--double]  — click element by ref-id from snapshot
  type <ref> "text" [--submit]
  press Enter
  fill --fields '[{"ref":"1","value":"Ada"}]'
  wait --text "Done"
  evaluate --fn '(el) => el.textContent' --ref 7
  console --level error
  pdf

  See `docker exec vibemind-openclaw openclaw browser --help` for all.

Usage::

    python openclaw_browser.py navigate https://example.com
    python openclaw_browser.py snapshot --format aria
    python openclaw_browser.py screenshot --full-page > /tmp/page.png
    python openclaw_browser.py click 12

The wrapper is intentionally a pass-through — we don't translate or wrap the
output. The agent reads the raw openclaw response, which is already
LLM-friendly (markdown/JSON depending on subcommand).
"""

from __future__ import annotations

import subprocess
import sys


CONTAINER_NAME = "vibemind-openclaw"


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: openclaw_browser.py <subcommand> [args...]\n"
            "       openclaw_browser.py --help    (forwards to openclaw browser --help)",
            file=sys.stderr,
        )
        return 2

    # If `--help` and nothing else: pass through directly to get container help.
    args = sys.argv[1:]
    if args == ["--help"] or args == ["-h"]:
        args = ["--help"]

    cmd = ["docker", "exec", CONTAINER_NAME, "node", "openclaw.mjs", "browser", *args]

    try:
        # Use `run` (not `Popen`) so output streams cleanly; check=False so we
        # can surface non-zero exits without raising.
        result = subprocess.run(cmd, capture_output=True, text=False)
    except FileNotFoundError:
        print("openclaw_browser: 'docker' CLI not found on PATH", file=sys.stderr)
        return 127

    # Write bytes through so binary outputs (screenshot PNG, PDF) survive.
    if result.stdout:
        sys.stdout.buffer.write(result.stdout)
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
