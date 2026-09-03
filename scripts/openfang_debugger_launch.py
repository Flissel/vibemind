"""OpenFang `debugger` agent launcher / liveness sidecar.

Replaces the legacy `electron_debug_agent.py` slot in Vibemind.debug.ps1.
The launcher itself does NOT run debugging logic — it locates the
OpenFang-side `debugger` agent (defined in
vibemind-os/openfang/agents/debugger/agent.toml), caches its UUID for
downstream consumers, and stays alive so the launcher's `Verify =
"process"` dashboard row for the `debug_agent` slot remains green.

Flow at startup:
  1. Wait for GET <OPENFANG_URL>/api/health to return 200 (with retries —
     handles the launch-order race where PHASE 5 starts before OpenFang
     finishes booting in PHASE 4).
  2. GET /api/agents, find the entry whose name == "debugger", capture
     its `id` field.
  3. Write the id to <ROOT>/logs/openfang/debugger_agent.id so the Brain
     capability router / MCP tools / manual curls can read it without
     re-querying the agent list.
  4. Optional warmup ping (set OPENFANG_DEBUGGER_WARMUP=1) — sends a no-op
     message through POST /api/agents/{id}/message to confirm the LLM
     path is wired.
  5. Idle loop on a 30 s tick: re-resolve the id (in case OpenFang
     restarted and minted a new one) and re-check health. Exit non-zero
     if OpenFang stays unreachable for the full miss budget — that lets
     the launcher's crash-detector surface the failure.

Env vars (with defaults that match openfang/CLAUDE.md):
  OPENFANG_URL                http://127.0.0.1:4200
  OPENFANG_AGENT_NAME         debugger
  OPENFANG_DEBUGGER_ID_FILE   <repo>/logs/openfang/debugger_agent.id
  OPENFANG_DEBUGGER_TIMEOUT_S 10           per-request HTTP timeout
  OPENFANG_DEBUGGER_BOOT_S    120          how long we wait for /api/health on startup
  OPENFANG_DEBUGGER_TICK_S    30           idle-loop tick
  OPENFANG_DEBUGGER_MISS_MAX  20           consecutive idle-loop failures before we exit
  OPENFANG_DEBUGGER_WARMUP    0            set to 1 to send a startup ping
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENFANG_URL = os.environ.get("OPENFANG_URL", "http://127.0.0.1:4200").rstrip("/")
AGENT_NAME = os.environ.get("OPENFANG_AGENT_NAME", "debugger")
TIMEOUT_S = int(os.environ.get("OPENFANG_DEBUGGER_TIMEOUT_S", "10"))
BOOT_BUDGET_S = int(os.environ.get("OPENFANG_DEBUGGER_BOOT_S", "120"))
TICK_S = int(os.environ.get("OPENFANG_DEBUGGER_TICK_S", "30"))
MISS_MAX = int(os.environ.get("OPENFANG_DEBUGGER_MISS_MAX", "20"))
WARMUP = os.environ.get("OPENFANG_DEBUGGER_WARMUP", "0") in ("1", "true", "yes")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ID_FILE = _REPO_ROOT / "logs" / "openfang" / "debugger_agent.id"
ID_FILE = Path(os.environ.get("OPENFANG_DEBUGGER_ID_FILE", str(_DEFAULT_ID_FILE)))


def _say(msg: str) -> None:
    print(f"[openfang-debugger] {msg}", flush=True)


def _http_json(method: str, path: str, payload: dict | None = None) -> dict | list | None:
    url = f"{OPENFANG_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        body = resp.read()
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body.decode("utf-8", errors="replace")}


def _health_ok() -> bool:
    try:
        _http_json("GET", "/api/health")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def _wait_for_openfang() -> bool:
    deadline = time.time() + BOOT_BUDGET_S
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        if _health_ok():
            _say(f"OpenFang reachable at {OPENFANG_URL} (attempt {attempt})")
            return True
        time.sleep(2)
    _say(f"OpenFang not reachable within {BOOT_BUDGET_S}s — giving up")
    return False


def _resolve_agent_id() -> str | None:
    try:
        agents = _http_json("GET", "/api/agents")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        _say(f"GET /api/agents failed: {exc}")
        return None
    if not isinstance(agents, list):
        _say(f"unexpected /api/agents payload: {type(agents).__name__}")
        return None
    for entry in agents:
        if isinstance(entry, dict) and entry.get("name") == AGENT_NAME:
            aid = entry.get("id")
            if isinstance(aid, str) and aid:
                return aid
    _say(f"no agent named {AGENT_NAME!r} in /api/agents (found {len(agents)} agents)")
    return None


def _write_id_file(agent_id: str) -> None:
    ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    ID_FILE.write_text(agent_id, encoding="utf-8")
    _say(f"agent id {agent_id} cached at {ID_FILE}")


def _warmup(agent_id: str) -> None:
    msg = "Warmup ping from Vibemind.debug.ps1 launcher. Reply OK."
    try:
        resp = _http_json(
            "POST",
            f"/api/agents/{agent_id}/message",
            {"message": msg},
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        _say(f"warmup failed (non-fatal): {exc}")
        return
    if isinstance(resp, dict):
        snippet = (resp.get("response") or resp.get("message") or "")[:120]
    else:
        snippet = ""
    _say(f"warmup ok ({snippet!r})")


def main() -> int:
    _say(f"starting; OPENFANG_URL={OPENFANG_URL} AGENT_NAME={AGENT_NAME}")

    if not _wait_for_openfang():
        return 2

    agent_id = _resolve_agent_id()
    if not agent_id:
        return 3
    _write_id_file(agent_id)

    if WARMUP:
        _warmup(agent_id)

    _say(f"entering idle loop (tick={TICK_S}s, miss_max={MISS_MAX})")
    misses = 0
    while True:
        time.sleep(TICK_S)
        if not _health_ok():
            misses += 1
            _say(f"health miss ({misses}/{MISS_MAX})")
            if misses >= MISS_MAX:
                _say("miss budget exhausted — exiting non-zero")
                return 4
            continue

        misses = 0
        current = _resolve_agent_id()
        if current and current != agent_id:
            _say(f"agent id changed: {agent_id} -> {current}")
            agent_id = current
            _write_id_file(agent_id)


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        _say("interrupted; exiting clean")
        sys.exit(0)
