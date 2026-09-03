"""Phase 3 — generate + register one focused OpenFang agent per host tool.

Each `tool-<name>` agent is a single-tool worker: its manifest pins the MCP
allowlist to exactly that one server (`mcp_servers = ["<name>"]`, so OpenFang
exposes only that server's tools to it), and its system prompt is the tool's
prompt template (from Supabase `agent_prompts`, falling back to a generic one).

Registration is via POST /api/agents with a `manifest_toml`. AgentManifest is
`#[serde(default)]` — only name/description/mcp_servers/[model].system_prompt
need to be set; everything else defaults.

Pure stdlib. The manifest builder is pure + unit-tested; `register()` /
`--apply` hit the live daemon and are intentionally separate.

Usage:
    python agent_gen.py --print            # print manifests, no network
    python agent_gen.py --apply            # POST each manifest to OpenFang (LIVE)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

OPENFANG_URL = os.environ.get("OPENFANG_URL", "http://127.0.0.1:4200")
REPO_ROOT = Path(__file__).resolve().parents[2]
SERVERS_JSON = REPO_ROOT / "vibemind-os/coding-engine/mcp_plugins/servers/servers.json"
DEFAULT_PROVIDER = os.environ.get("OPENFANG_AGENT_PROVIDER", "openai")
DEFAULT_MODEL = os.environ.get("OPENFANG_AGENT_MODEL", "gpt-4o-mini")


def host_tools(registry: dict) -> list[str]:
    """Tool names that run on the host (global scope + a host block) — the same
    set the OpenFang hub exposes, so one agent per host tool."""
    return [
        s["name"] for s in registry.get("servers", [])
        if s.get("scope", "global") == "global" and s.get("host")
    ]


def default_prompt(tool: str) -> str:
    """Generic system prompt used until a tool's agent_prompts row exists."""
    return (
        f"You are the `{tool}` tool agent. You have access to exactly ONE MCP "
        f"server: `{tool}`. Use only its tools to fulfil the task. Resolve the "
        f"task's structured values, call the tool, and return the result as "
        f"JSON. Never invent data; if a required value is missing, say so."
    )


def _toml_ml_string(value: str) -> str:
    """A TOML multi-line basic string literal for `value`."""
    body = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""{body}"""'


def build_manifest(tool: str, system_prompt: str,
                   provider: str = DEFAULT_PROVIDER, model: str = DEFAULT_MODEL) -> str:
    """Build the agent.toml manifest for a single-tool agent.

    Top-level keys (name/description/mcp_servers) come BEFORE the [model] table
    so they parse as top-level, not nested under [model]."""
    return (
        f'name = "tool-{tool}"\n'
        f'description = "Single-tool agent scoped to the {tool} MCP server"\n'
        f'mcp_servers = ["{tool}"]\n'
        f"\n"
        f"[model]\n"
        f'provider = {json.dumps(provider)}\n'
        f'model = {json.dumps(model)}\n'
        f"system_prompt = {_toml_ml_string(system_prompt)}\n"
    )


def register(manifest_toml: str) -> dict:
    """POST a manifest to the live OpenFang daemon. Hits the network."""
    body = json.dumps({"manifest_toml": manifest_toml}).encode()
    req = urllib.request.Request(
        f"{OPENFANG_URL}/api/agents", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.loads(r.read() or b"{}")


def _load() -> dict:
    return json.loads(SERVERS_JSON.read_text(encoding="utf-8"))


def manifests() -> list[tuple[str, str]]:
    """(tool, manifest_toml) for every host tool, using default prompts."""
    return [(t, build_manifest(t, default_prompt(t))) for t in host_tools(_load())]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print manifests (no network)")
    ap.add_argument("--apply", action="store_true", help="POST manifests to OpenFang (LIVE)")
    args = ap.parse_args()
    ms = manifests()
    if args.apply:
        for tool, manifest in ms:
            res = register(manifest)
            print(f"[agent_gen] registered tool-{tool}: {res.get('id', res)}")
        return 0
    # default: print
    for tool, manifest in ms:
        print(f"# ===== tool-{tool} =====\n{manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
