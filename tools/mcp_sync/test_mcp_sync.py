import json

import mcp_sync


SAMPLE = {
    "servers": [
        {"name": "docker", "active": True, "scope": "global",
         "command": "python", "args": ["-m", "mcp_server_docker"],
         "read_timeout_seconds": 120, "description": "Docker",
         "host": {"command": "${HOME}/.local/bin/docker-mcp.exe", "args": []}},
        {"name": "qdrant", "active": True, "scope": "global",
         "command": "python", "args": ["mcp_plugins/servers/qdrant/agent.py"],
         "read_timeout_seconds": 15, "description": "Qdrant",
         "host": {"command": "${HOME}/.local/bin/mcp-server-qdrant.exe", "args": [],
                  "env": {"QDRANT_URL": "http://localhost:6340"}}},
        # coding-only -> excluded from host configs even though it has a host block
        {"name": "npm", "active": True, "scope": "coding-only",
         "command": "npx", "args": ["-y", "server-npm"],
         "read_timeout_seconds": 60, "description": "npm",
         "host": {"command": "npx", "args": ["-y", "server-npm"]}},
        # global but no host block (container-only, no host binary) -> excluded
        {"name": "supabase", "active": True, "scope": "global",
         "command": "python", "args": ["-m", "mcp_server_supabase"],
         "read_timeout_seconds": 30, "description": "Supabase container-only"},
    ]
}


def test_selected_is_global_with_host_block():
    names = [s["name"] for s in mcp_sync.selected(SAMPLE)]
    assert names == ["docker", "qdrant"]  # npm=coding-only, supabase=no host block


def test_render_toml_uses_host_invocation_and_inline_env():
    block = mcp_sync.render_toml(SAMPLE)
    assert mcp_sync.TOML_BEGIN in block and mcp_sync.TOML_END in block
    assert '[[mcp_servers]]\nname = "docker"' in block
    assert 'timeout_secs = 120' in block
    # HOST command, never the container "python"
    assert 'command = "${HOME}/.local/bin/docker-mcp.exe"' in block
    assert '"python"' not in block
    # qdrant host env as an inline table (OpenFang's convention)
    assert 'env = { QDRANT_URL = "http://localhost:6340" }' in block
    assert block == mcp_sync.render_toml(SAMPLE)


def test_render_mcp_json_uses_host_invocation():
    obj = json.loads(mcp_sync.render_mcp_json(SAMPLE))
    assert set(obj["mcpServers"].keys()) == {"docker", "qdrant"}
    assert obj["mcpServers"]["docker"]["command"] == "${HOME}/.local/bin/docker-mcp.exe"
    assert obj["mcpServers"]["qdrant"]["env"] == {"QDRANT_URL": "http://localhost:6340"}


def test_splice_replaces_only_between_markers():
    original = f"head\n{mcp_sync.TOML_BEGIN}\nOLD\n{mcp_sync.TOML_END}\ntail\n"
    spliced = mcp_sync.splice(original, mcp_sync.TOML_BEGIN, mcp_sync.TOML_END, "NEW")
    assert spliced == f"head\n{mcp_sync.TOML_BEGIN}\nNEW\n{mcp_sync.TOML_END}\ntail\n"
    assert "head" in spliced and "tail" in spliced and "OLD" not in spliced
