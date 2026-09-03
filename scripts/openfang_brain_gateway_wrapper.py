"""OpenFang -> Brain capability-pipeline bridge wrapper.

Makes the Telegram bot (and any OpenFang channel routed to the
`brain-gateway` agent) flow through Brain's full capability pipeline
instead of answering directly.

OpenFang's `claude_code` driver spawns this script (via the `.cmd` shim)
as if it were a Claude-Code CLI. We translate that into a single Brain
multihop call:

    POST http://127.0.0.1:5000/api/multihop/execute
      {"intent": "<prompt from stdin>"}
    -> {"result": {"ok": ..., "final_text": "...", ...}}

We write only `result.final_text` to stdout (that's what OpenFang's
claude_code driver relays back to the channel — i.e. to Telegram).

Why this shape (decided 2026-05-19, "kann der bot mit brain routing
interagieren?"):
  - OpenFang's telegram routing is HARDCODED to one `default_agent`
    (resolved once at startup, no middleware — verified in
    crates/openfang-channels/src/bridge.rs). The clean insertion point
    is a dedicated thin agent whose base_url is THIS wrapper.
  - This is a DETERMINISTIC bridge: no intermediate LLM "deciding"
    whether to call Brain. The channel message goes verbatim as the
    `intent` to multihop_execute, which runs CapabilityRouter ->
    shortcut -> openfang:openclaw-visible / openclaude-coder /
    skill-coordinator etc. (the [[brain-routing-multihop-execute]]
    pipeline). One round-trip, no extra model cost at the gateway.
  - Prompt arrives via stdin (OpenFang claude_code driver was patched
    for stdin — see [[openclaude-coder OpenFang agent]]). We ignore the
    driver's argv flags (-p / --system-prompt-file / --model / ...).
  - multihop for a real capability (browser/code/desktop) can take
    30-300s. We give a generous client timeout; the .mcp.json brain
    timeout is already 600s.

Config via env (with sane defaults):
  BRAIN_MULTIHOP_URL   default "http://127.0.0.1:5000/api/multihop/execute"
  BRAIN_GATEWAY_TIMEOUT_S  default 290  (room under OpenFang's ceiling)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MULTIHOP_URL = os.environ.get(
    "BRAIN_MULTIHOP_URL", "http://127.0.0.1:5000/api/multihop/execute"
)
TIMEOUT_S = int(os.environ.get("BRAIN_GATEWAY_TIMEOUT_S", "290"))


def _extract_final_text(payload: dict) -> str:
    """Brain multihop returns {"result": {ok, final_text, executed, ...}}.
    Prefer result.final_text; fall back to a per-hop response, then raw."""
    result = payload.get("result", payload)
    if isinstance(result, dict):
        ft = result.get("final_text")
        if isinstance(ft, str) and ft.strip():
            return ft.strip()
        # Fall back to the last executed hop's response text.
        executed = result.get("executed")
        if isinstance(executed, dict) and executed:
            last = list(executed.values())[-1]
            if isinstance(last, dict):
                res = last.get("result")
                if isinstance(res, dict):
                    resp = res.get("response")
                    if isinstance(resp, str) and resp.strip():
                        return resp.strip()
        # Some error shapes put a message at the top.
        for key in ("message", "error", "detail"):
            v = result.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return json.dumps(payload)[:1500]


def main() -> int:
    # OpenFang's patched claude_code driver pipes the user message via stdin.
    try:
        prompt = sys.stdin.read()
    except Exception:
        prompt = ""
    prompt = (prompt or "").strip()
    if not prompt:
        print("[brain-gateway-wrapper] empty prompt on stdin", file=sys.stderr)
        return 2

    body = json.dumps({"intent": prompt}).encode("utf-8")
    req = urllib.request.Request(
        MULTIHOP_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    debug = os.environ.get("OPENFANG_BRAIN_GATEWAY_DEBUG")
    if debug:
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_brain_gateway.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"--- pid={os.getpid()} url={MULTIHOP_URL} "
                    f"intent_len={len(prompt)}\n"
                )
                fh.write(f"intent_head={prompt[:200]!r}\n")
        except Exception:
            pass

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")[:500]
        print(
            f"[brain-gateway-wrapper] Brain HTTP {e.code}: {msg}",
            file=sys.stderr,
        )
        # Still surface a user-facing line so Telegram isn't silent.
        sys.stdout.write(
            f"Brain konnte die Anfrage nicht verarbeiten (HTTP {e.code})."
        )
        return 1
    except urllib.error.URLError as e:
        print(
            f"[brain-gateway-wrapper] Brain unreachable at {MULTIHOP_URL}: "
            f"{e.reason}",
            file=sys.stderr,
        )
        sys.stdout.write(
            "Brain ist gerade nicht erreichbar. Bitte später erneut versuchen."
        )
        return 1
    except TimeoutError:
        print(
            f"[brain-gateway-wrapper] Brain timed out after {TIMEOUT_S}s",
            file=sys.stderr,
        )
        sys.stdout.write(
            "Die Anfrage hat zu lange gedauert (Timeout). "
            "Bei Browser-/Code-Aufgaben kann das vorkommen — bitte erneut "
            "versuchen oder die Aufgabe kleiner fassen."
        )
        return 1

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print(
            "[brain-gateway-wrapper] non-JSON response from Brain",
            file=sys.stderr,
        )
        sys.stdout.write(raw.strip()[:1500] or "Keine Antwort von Brain.")
        return 1

    text = _extract_final_text(payload)

    if debug:
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_brain_gateway.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(f"reply_len={len(text)} head={text[:200]!r}\n")
        except Exception:
            pass

    # Trailing newline is REQUIRED: OpenFang's claude_code streaming driver
    # reads stdout line-by-line; without `\n` the final chunk doesn't surface
    # as a stream event in time → Brain sees response: "". Fix 2026-05-29.
    if not text.endswith("\n"):
        text = text + "\n"
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
