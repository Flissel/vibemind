"""Generate OpenFang's tool [[mcp_servers]] block and Claude's .mcp.json
from servers.json (the single source of truth for generic MCP tools).

servers.json carries TWO invocations per tool: the top-level command/args are
the CONTAINER invocation (coding-engine, Docker/Linux). An optional `host` block
{command,args,env?} is the WINDOWS-HOST invocation. OpenFang + the Claude session
both run on the host, so this generator emits the `host` block — never the
container command/args. A tool reaches the host configs iff it is global-scope
and has a `host` block (host.active != False).

Pure stdlib. Usage:
    python mcp_sync.py --write     # write the generated blocks in place
    python mcp_sync.py --check     # exit 1 if files differ from the generation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOML_BEGIN = "# >>> generated:tools (mcp_sync.py — do not edit by hand)"
TOML_END = "# <<< generated:tools"

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVERS_JSON = REPO_ROOT / "vibemind-os/coding-engine/mcp_plugins/servers/servers.json"
OPENFANG_TOML = REPO_ROOT / "vibemind-os/openfang/openfang.vibemind.toml.template"
MCP_JSON = REPO_ROOT / ".mcp.json"


def selected(registry: dict) -> list[dict]:
    """Servers emitted to the HOST configs (OpenFang TOML + .mcp.json):
    global-scope AND carrying a `host` block (host.active != False)."""
    out = []
    for s in registry.get("servers", []):
        if s.get("scope", "global") != "global":
            continue
        h = s.get("host")
        if not h or h.get("active") is False:
            continue
        out.append(s)
    return out


def _toml_str_list(items: list[str]) -> str:
    return "[" + ", ".join(json.dumps(i) for i in items) + "]"


def _toml_body(registry: dict) -> str:
    """The TOML entries WITHOUT the surrounding markers (host invocations)."""
    lines: list[str] = []
    for s in selected(registry):
        h = s["host"]
        lines.append("[[mcp_servers]]")
        lines.append(f'name = {json.dumps(s["name"])}')
        lines.append(f'timeout_secs = {int(s.get("read_timeout_seconds", 30))}')
        lines.append("[mcp_servers.transport]")
        lines.append('type = "stdio"')
        lines.append(f'command = {json.dumps(h["command"])}')
        lines.append(f'args = {_toml_str_list(h.get("args", []))}')
        env = h.get("env") or {}
        if env:
            pairs = ", ".join(f"{k} = {json.dumps(v)}" for k, v in env.items())
            lines.append(f"env = {{ {pairs} }}")
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def render_toml(registry: dict) -> str:
    """Full block INCLUDING markers (used by tests + for display)."""
    return f"{TOML_BEGIN}\n{_toml_body(registry)}\n{TOML_END}"


def render_mcp_json(registry: dict) -> str:
    servers = {}
    for s in selected(registry):
        h = s["host"]
        entry = {"command": h["command"], "args": h.get("args", [])}
        if h.get("env"):
            entry["env"] = h["env"]
        servers[s["name"]] = entry
    return json.dumps({"mcpServers": servers}, indent=2)


def splice(text: str, begin: str, end: str, payload: str) -> str:
    if begin not in text or end not in text:
        raise ValueError(f"markers {begin!r}/{end!r} not found in target")
    head, _, rest = text.partition(begin)
    _, _, tail = rest.partition(end)
    return f"{head}{begin}\n{payload}\n{end}{tail}"


def _load() -> dict:
    return json.loads(SERVERS_JSON.read_text(encoding="utf-8"))


def write() -> None:
    reg = _load()
    toml = OPENFANG_TOML.read_text(encoding="utf-8")
    OPENFANG_TOML.write_text(
        splice(toml, TOML_BEGIN, TOML_END, _toml_body(reg)), encoding="utf-8")
    MCP_JSON.write_text(render_mcp_json(reg) + "\n", encoding="utf-8")
    print("[mcp_sync] wrote OpenFang TOML block + .mcp.json")


def check() -> int:
    reg = _load()
    ok = True
    toml = OPENFANG_TOML.read_text(encoding="utf-8")
    expected = splice(toml, TOML_BEGIN, TOML_END, _toml_body(reg))
    if toml != expected:
        print("[mcp_sync] DRIFT: openfang TOML out of sync"); ok = False
    if MCP_JSON.exists() and MCP_JSON.read_text(encoding="utf-8") != render_mcp_json(reg) + "\n":
        print("[mcp_sync] DRIFT: .mcp.json out of sync"); ok = False
    if ok:
        print("[mcp_sync] in sync")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.write:
        write(); return 0
    ap.print_help(); return 2


if __name__ == "__main__":
    sys.exit(main())
