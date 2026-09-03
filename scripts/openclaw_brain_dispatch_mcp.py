"""
brain-dispatch — stdio MCP server that gives openclaw a single tool to
delegate a task to the VibeMind Brain capability pipeline.

WHY (the "smart dispatcher" design, 2026-06):
    openclaw-main (the WhatsApp/Telegram agent) has only its own browser /
    shell / file tools. With this MCP it gains ONE tool — `brain_dispatch` —
    so its soul can decide: trivial browser work it does itself; everything
    else (desktop automation, coding, knowledge, multi-step) it hands to
    Brain, which loads capabilities.yaml, plans, and routes to the right
    OpenFang specialist (skill-coordinator / openclaude-coder / ...).

    This is the sibling of scripts/openfang_brain_gateway_wrapper.py:
      - gateway wrapper: OpenFang channel -> Brain (deterministic, every msg)
      - this MCP:        openclaw agent  -> Brain (LLM-chosen, on demand)

LOOP NOTE:
    brain_dispatch -> Brain -> may route browser_automation ->
    openfang:openclaw-visible. That is a DIFFERENT openclaw agent (the
    OpenFang-invoked browser tool) than openclaw-main (which dispatches), so
    there is no direct self-loop. We do NOT re-enter brain_dispatch from
    within a dispatched task.

Protocol: minimal MCP over stdio (JSON-RPC 2.0). Implements:
    initialize, tools/list, tools/call, notifications/initialized (no-op).

Register in openclaw:
    openclaw mcp set brain-dispatch '{"command":"python","args":["<abs>/scripts/openclaw_brain_dispatch_mcp.py"]}'

Env:
    BRAIN_MULTIHOP_URL    default http://127.0.0.1:5000/api/multihop/execute
    BRAIN_DISPATCH_TIMEOUT_S  default 290
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MULTIHOP_URL = os.environ.get(
    "BRAIN_MULTIHOP_URL", "http://127.0.0.1:5000/api/multihop/execute"
)
PLAN_URL = os.environ.get(
    "BRAIN_PLAN_URL", "http://127.0.0.1:5000/api/multihop/plan"
)
# Foreground plan-probe must finish well under openclaw's hard ~30s MCP
# tool-call timeout. The long execute runs in the detached worker.
PLAN_TIMEOUT_S = int(os.environ.get("BRAIN_DISPATCH_PLAN_TIMEOUT_S", "25"))

_THIS_DIR = Path(__file__).resolve().parent
NOTIFY_SCRIPT = _THIS_DIR / "notify_telegram.py"

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "brain-dispatch", "version": "0.2.0"}

TOOL_DEF = {
    "name": "brain_dispatch",
    "description": (
        "Delegate a task to the VibeMind Brain capability pipeline. Brain "
        "plans the task and routes it to the right specialist agent: desktop "
        "automation (Excel/Word/PowerPoint/Outlook, HR workflows), code "
        "generation, knowledge/bubble operations, or multi-step jobs. Use "
        "this for anything beyond simple in-browser actions you can do "
        "yourself. ASYNC: this returns immediately ('task started'); the "
        "specialist runs in the background and the RESULT is delivered to "
        "the user via Telegram when done. Tell the user it's running and "
        "they'll get the result on Telegram. Pass the user's request "
        "verbatim as `intent`."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "description": "The task/request to hand to Brain, in natural language.",
            }
        },
        "required": ["intent"],
    },
}


def _extract_final_text(payload: dict) -> str:
    """Brain multihop returns {ok, final_text, executed, ...}. Prefer
    final_text; fall back to the last hop's response, then raw."""
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


def _notify_telegram(text: str) -> None:
    """Push a message to the VibeMind Telegram channel (best-effort)."""
    try:
        if not NOTIFY_SCRIPT.is_file():
            return
        subprocess.run(
            [sys.executable, str(NOTIFY_SCRIPT), text],
            timeout=30, capture_output=True,
        )
    except Exception:
        pass


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


_WORKER = Path(__file__).resolve().parent / "openclaw_brain_dispatch_worker.py"


def _spawn_detached_worker(intent: str) -> bool:
    """Launch the Brain multihop in a FULLY DETACHED process.

    A background thread inside this stdio MCP server dies the moment openclaw
    retires the runtime after the tool call ("one-shot agent entry points
    retire MCP runtimes when reply completes" — openclaw docs). So the long
    Brain+specialist execution must run in a process that OUTLIVES this one.
    The worker calls Brain to completion and Telegram-notifies the result;
    it has its own hard wall-clock self-kill so it can never become a zombie.
    """
    if not _WORKER.is_file():
        return False
    creationflags = 0
    kwargs = {}
    if sys.platform == "win32":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW —
        # the child is decoupled from this process's console + lifecycle.
        creationflags = 0x00000008 | 0x00000200 | 0x08000000
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(
        [sys.executable, str(_WORKER), intent],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        **kwargs,
    )
    return True


def _dispatch(intent: str) -> str:
    """Fast foreground probe + fire-and-forget background execution.

    1. Quick PLAN probe (~1-2s): is this routable? what capability?
    2. If routable -> start background execute (result via Telegram),
       return 'started' immediately.
    3. If not routable (e.g. chitchat with no target) -> tell the agent so
       it can just answer directly instead.
    """
    # 1. Plan probe — fast, tells us the capability + whether it's routable.
    try:
        plan = _post_json(PLAN_URL, {"intent": intent}, PLAN_TIMEOUT_S)
    except Exception as e:
        return (f"Brain plan probe failed ({e}). Konnte die Aufgabe nicht "
                f"einordnen — bitte direkt mit eigenen Tools versuchen.")

    hops = (plan.get("plan") or {}).get("hops") or []
    caps = [h.get("capability") for h in hops]

    # chitchat / no real target -> don't background-execute, let agent answer.
    if not hops or caps == ["chitchat"]:
        return ("Diese Anfrage ist kein Spezial-Task (Brain stuft sie als "
                "Smalltalk/chitchat ein). Beantworte sie selbst direkt — "
                "nicht dispatchen.")

    # 2. Routable -> detached worker (survives MCP teardown), return now.
    spawned = _spawn_detached_worker(intent)
    if not spawned:
        return ("Konnte den Hintergrund-Worker nicht starten "
                "(openclaw_brain_dispatch_worker.py fehlt).")
    return (f"Aufgabe an Brain übergeben (Capability: {', '.join(c for c in caps if c)}). "
            f"Läuft jetzt im Hintergrund beim zuständigen Spezial-Agenten — "
            f"das Ergebnis kommt per Telegram, sobald es fertig ist.")


def _reply(request_id, result=None, error=None) -> None:
    msg = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore malformed lines (no id to reply to)

        method = req.get("method")
        rid = req.get("id")

        if method == "initialize":
            _reply(rid, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        elif method == "notifications/initialized":
            pass  # notification, no response
        elif method == "tools/list":
            _reply(rid, {"tools": [TOOL_DEF]})
        elif method == "tools/call":
            params = req.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if name != "brain_dispatch":
                _reply(rid, error={"code": -32601, "message": f"Unknown tool: {name}"})
                continue
            intent = (args.get("intent") or "").strip()
            if not intent:
                _reply(rid, error={"code": -32602, "message": "intent is required"})
                continue
            text = _dispatch(intent)
            _reply(rid, {"content": [{"type": "text", "text": text}]})
        elif rid is not None:
            _reply(rid, error={"code": -32601, "message": f"Method not found: {method}"})
        # notifications (rid is None) with unknown method: ignore

    return 0


if __name__ == "__main__":
    sys.exit(main())
