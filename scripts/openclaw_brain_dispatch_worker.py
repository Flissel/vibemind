"""
brain-dispatch background worker — runs ONE Brain multihop_execute to
completion and Telegram-notifies the result, fully detached from the
openclaw MCP process that spawned it.

WHY a separate detached process (not a thread):
    openclaw retires the stdio MCP runtime as soon as the tool call returns
    ("one-shot agent entry points retire MCP runtimes when reply completes"
    — openclaw docs). A background THREAD inside the MCP server dies with
    that process, so a 30-300s desktop/code task never finished. This worker
    is launched with DETACHED_PROCESS so it outlives the MCP server and
    delivers the result via Telegram whenever Brain is done.

Invoked by openclaw_brain_dispatch_mcp.py via detached Popen:
    python openclaw_brain_dispatch_worker.py "<intent>"

Env:
    BRAIN_MULTIHOP_URL        default http://127.0.0.1:5000/api/multihop/execute
    BRAIN_DISPATCH_TIMEOUT_S  default 600 (worker is detached, can wait long)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

MULTIHOP_URL = os.environ.get(
    "BRAIN_MULTIHOP_URL", "http://127.0.0.1:5000/api/multihop/execute"
)
TIMEOUT_S = int(os.environ.get("BRAIN_DISPATCH_TIMEOUT_S", "600"))
# Hard wall-clock self-kill: a daemon timer that force-exits the process
# even if urllib's per-socket timeout is somehow circumvented (drip-stream,
# stuck read). Guarantees the detached worker NEVER becomes a zombie — it
# lives at most HARD_KILL_S regardless of what Brain's socket does.
HARD_KILL_S = TIMEOUT_S + 30
NOTIFY_SCRIPT = Path(__file__).resolve().parent / "notify_telegram.py"


def _arm_self_kill() -> None:
    """Force-terminate this process after HARD_KILL_S no matter what."""
    def _kill():
        os._exit(124)  # bypasses any hung I/O / atexit; clean OS-level exit
    t = threading.Timer(HARD_KILL_S, _kill)
    t.daemon = True
    t.start()


def _extract_final_text(payload: dict) -> str:
    result = payload.get("result", payload)
    if isinstance(result, dict):
        ft = result.get("final_text")
        if isinstance(ft, str) and ft.strip():
            return ft.strip()
        executed = result.get("executed")
        if isinstance(executed, dict) and executed:
            last = list(executed.values())[-1]
            if isinstance(last, dict):
                r = last.get("result")
                if isinstance(r, dict) and isinstance(r.get("response"), str):
                    if r["response"].strip():
                        return r["response"].strip()
                elif isinstance(r, str) and r.strip():
                    return r.strip()
        for key in ("message", "error", "detail"):
            v = result.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return json.dumps(payload)[:1500]


def _notify(text: str) -> None:
    try:
        if NOTIFY_SCRIPT.is_file():
            subprocess.run(
                [sys.executable, str(NOTIFY_SCRIPT), text],
                timeout=30, capture_output=True,
            )
    except Exception:
        pass


def main() -> int:
    intent = " ".join(sys.argv[1:]).strip()
    if not intent:
        return 2
    _arm_self_kill()  # guaranteed termination ceiling
    try:
        body = json.dumps({"intent": intent}).encode("utf-8")
        req = urllib.request.Request(
            MULTIHOP_URL, data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        result_text = _extract_final_text(payload)
        _notify(f"✅ Aufgabe erledigt:\n{intent}\n\n{result_text}")
        return 0
    except urllib.error.HTTPError as e:
        _notify(f"⚠️ Aufgabe fehlgeschlagen:\n{intent}\n\nBrain HTTP {e.code}")
    except Exception as e:
        _notify(f"⚠️ Aufgabe fehlgeschlagen:\n{intent}\n\n{e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
