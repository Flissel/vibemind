"""
Smoke-test every MCP tool aggregated by OpenFang.

Strategy
--------
For each connected MCP server we ask /api/mcp/servers for its tools and their
inputSchema. Then per tool:

  1. If the tool is in DANGEROUS_PATTERNS we never run it for real. We send
     `{"__smoketest__": true}` with a short timeout and record:
       - tool_error (validation error)  → ok_validated  (connection lives)
       - ok                              → ok_validated  (tool tolerated junk)
       - transport_error                 → DEAD
  2. Else if the tool has no required args (or all required args have a
     known safe override) we invoke it for real with a longer timeout and
     keep the response summary.
  3. Else (required args we don't know) we skip with reason `needs_args`,
     so we don't time-out trying to guess.

Output
------
  results/mcp_smoke.json   per-tool result
  stdout                   live progress + final counters

Usage
-----
  python -u scripts/test_all_mcps.py
  python -u scripts/test_all_mcps.py --only-server desktop-automation
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENFANG_MCP = "http://127.0.0.1:4200/mcp"
LIST_URL = "http://127.0.0.1:4200/api/mcp/servers"
TIMEOUT_DANGEROUS = 5
TIMEOUT_READ = 25
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

DANGEROUS_PATTERNS = [
    # writes & mutations
    r"_(write|create|update|delete|edit|set|store|put|patch|add|remove|insert|move|rename|append|label|unlabel|reject|approve|trigger|notify)(_|$)",
    # process / system control
    r"_(kill|terminate|stop|restart|reboot|shutdown|deploy|run|exec|execute|spawn|click|type|press|scroll|drag|drop|recreate|recover|self_repair)(_|$)",
    # external i/o & generation (rate-limit / cost / network)
    r"_(search|crawl|extract|fetch|browse|navigate|generate|push|pull|commit|branch|checkout|merge|reset|complete_authentication|deploy_to)(_|$)",
    # active/destructive scans
    r"_(deep_scan|full_scan|train|learn|backup|restore|sync|scan_all|scan_space|scan_security|scan_system_health|zombie_scan|vpn_audit|vpn_botnet_probe|secret_scan|password_audit|os_audit|firewall_audit|tls_check|cve_check|exposed_services|wifi_scan|arp_monitor|port_monitor|connection_monitor|process_monitor|dns_monitor|bandwidth|threat|botnet|fingerprint|headers|robots|sitemap|technology|content_check|reputation|ssl_audit|dependency_check|driver_conflicts|battery_report|monitor_(start|stop)|watcher)(_|$)",
    # blocking / state
    r"_(unblock|block|disable|enable|clear|close|open)(_|$)",
]

ARG_OVERRIDES: dict[str, dict] = {
    "mcp_time_get_current_time": {"timezone": "UTC"},
    "mcp_time_convert_time": {
        "source_timezone": "UTC",
        "time": "12:00",
        "target_timezone": "Europe/Berlin",
    },
    "mcp_filesystem_read_file": {
        "path": "C:/Users/User/Desktop/Vibemind_V1/README.md"
    },
    "mcp_filesystem_list_directory": {"path": "C:/Users/User/Desktop/Vibemind_V1"},
    "mcp_filesystem_directory_tree": {"path": "C:/Users/User/Desktop/Vibemind_V1"},
    "mcp_filesystem_get_file_info": {
        "path": "C:/Users/User/Desktop/Vibemind_V1/README.md"
    },
    "mcp_git_git_status": {"repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os"},
    "mcp_git_git_diff_unstaged": {
        "repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os"
    },
    "mcp_git_git_diff_staged": {
        "repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os"
    },
    "mcp_git_git_log": {
        "repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os",
        "max_count": 3,
    },
    "mcp_git_git_show": {
        "repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os",
        "revision": "HEAD",
    },
    "mcp_git_git_diff": {
        "repo_path": "C:/Users/User/Desktop/Vibemind_V1/vibemind-os",
        "target": "HEAD",
    },
    "mcp_redis_get": {"key": "__nonexistent_smoketest_key__"},
    "mcp_redis_list": {},
    "mcp_qdrant_qdrant_find": {"query": "smoketest", "collection_name": "smoketest"},
    "mcp_context7_resolve_library_id": {"libraryName": "react"},
}


def post(payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENFANG_MCP,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return {"_transport_error": True, "_msg": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {
            "_transport_error": True,
            "_msg": f"{type(e).__name__}: {str(e)[:160]}",
        }


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def is_dangerous(name: str) -> bool:
    return any(re.search(pat, name) for pat in DANGEROUS_PATTERNS)


def classify(resp: dict) -> tuple[str, str]:
    if resp.get("_transport_error"):
        return "transport_error", resp.get("_msg", "")
    if "error" in resp:
        msg = (resp["error"].get("message") or "")[:200]
        return "tool_error", msg
    result = resp.get("result", {})
    if isinstance(result, dict):
        if result.get("isError"):
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""
            return "tool_error", text[:200]
        content = result.get("content", [])
        if content:
            first = content[0]
            text = first.get("text", "") if isinstance(first, dict) else str(first)
            return "ok", text[:200]
        return "ok", json.dumps(result)[:200]
    return "ok", str(result)[:200]


def required_args(tool: dict) -> list[str]:
    schema = tool.get("input_schema") or tool.get("inputSchema") or {}
    if not isinstance(schema, dict):
        return []
    req = schema.get("required") or []
    if isinstance(req, list):
        return req
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-server")
    parser.add_argument("--limit-per-server", type=int, default=0)
    args = parser.parse_args()

    listing = get(LIST_URL)
    connected = listing.get("connected", [])
    total_tools = sum(len(s.get("tools", [])) for s in connected)
    print(f"Servers connected: {len(connected)}, total tools: {total_tools}", flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    results: list[dict] = []
    counters = {
        "ok_real": 0,
        "ok_validated": 0,
        "tool_error": 0,
        "transport_error": 0,
        "skipped_needs_args": 0,
    }

    for server in connected:
        sname = server.get("name", "?")
        if args.only_server and sname != args.only_server:
            continue
        tools = server.get("tools", [])
        if args.limit_per_server > 0:
            tools = tools[: args.limit_per_server]

        print(f"\n=== {sname} ({len(tools)} tools) ===", flush=True)
        for tool in tools:
            tname = tool.get("name", "")
            if not tname:
                continue

            override = ARG_OVERRIDES.get(tname)
            req = required_args(tool)
            dangerous = is_dangerous(tname)

            if dangerous:
                # Probe with junk; tool-side rejection proves connectivity.
                arguments = {"__smoketest__": True}
                timeout = TIMEOUT_DANGEROUS
                mode = "probe"
            elif override is not None:
                arguments = override
                timeout = TIMEOUT_READ
                mode = "real"
            elif not req:
                arguments = {}
                timeout = TIMEOUT_READ
                mode = "real"
            else:
                # Required args we don't have a safe value for.
                results.append({
                    "server": sname,
                    "tool": tname,
                    "dangerous": dangerous,
                    "required": req,
                    "effective": "skipped_needs_args",
                    "elapsed_s": 0.0,
                    "summary": f"required={req}",
                })
                counters["skipped_needs_args"] += 1
                print(f"  [SKIP]  0.00s  {tname:60s} required={req}", flush=True)
                continue

            t0 = time.time()
            payload = {
                "jsonrpc": "2.0",
                "id": tname,
                "method": "tools/call",
                "params": {"name": tname, "arguments": arguments},
            }
            resp = post(payload, timeout=timeout)
            elapsed = round(time.time() - t0, 2)

            status, summary = classify(resp)

            if mode == "probe":
                if status in ("tool_error", "ok"):
                    effective = "ok_validated"
                    counters["ok_validated"] += 1
                    marker = "OKv"
                else:
                    effective = "transport_error"
                    counters["transport_error"] += 1
                    marker = "DEAD"
            else:  # real
                if status == "ok":
                    effective = "ok_real"
                    counters["ok_real"] += 1
                    marker = "OK"
                elif status == "tool_error":
                    effective = "tool_error"
                    counters["tool_error"] += 1
                    marker = "ERR"
                else:
                    effective = "transport_error"
                    counters["transport_error"] += 1
                    marker = "DEAD"

            results.append({
                "server": sname,
                "tool": tname,
                "dangerous": dangerous,
                "mode": mode,
                "effective": effective,
                "elapsed_s": elapsed,
                "summary": summary,
            })

            print(f"  [{marker:4s}] {elapsed:5.2f}s  {tname:60s} {summary[:60]}", flush=True)

    out_path = RESULTS_DIR / "mcp_smoke.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Summary ===", flush=True)
    print(f"  ok_real (read tool, real response):         {counters['ok_real']}", flush=True)
    print(f"  ok_validated (dangerous tool, conn proven): {counters['ok_validated']}", flush=True)
    print(f"  tool_error (real read failed):              {counters['tool_error']}", flush=True)
    print(f"  transport_error (DEAD):                     {counters['transport_error']}", flush=True)
    print(f"  skipped (needs required args):              {counters['skipped_needs_args']}", flush=True)
    print(f"  total tools:                                {sum(counters.values())}", flush=True)
    print(f"  full results:                               {out_path}", flush=True)

    return 0 if counters["transport_error"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
