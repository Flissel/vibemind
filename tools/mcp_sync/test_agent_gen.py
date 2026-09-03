import tomllib

import agent_gen


REG = {
    "servers": [
        {"name": "docker", "scope": "global", "host": {"command": "x", "args": []}},
        {"name": "qdrant", "scope": "global", "host": {"command": "y", "args": []}},
        {"name": "npm", "scope": "coding-only", "host": {"command": "z", "args": []}},
        {"name": "supabase", "scope": "global"},  # no host block
    ]
}


def test_host_tools_global_with_host_block():
    assert agent_gen.host_tools(REG) == ["docker", "qdrant"]


def test_manifest_is_valid_toml_with_top_level_allowlist():
    m = tomllib.loads(agent_gen.build_manifest("docker", "do docker things"))
    assert m["name"] == "tool-docker"
    # mcp_servers must be TOP-LEVEL (the per-agent allowlist), not nested in [model]
    assert m["mcp_servers"] == ["docker"]
    assert "mcp_servers" not in m["model"]
    assert m["model"]["system_prompt"] == "do docker things"


def test_manifest_preserves_multiline_and_quotes_in_prompt():
    prompt = 'line1\nline2 with "quotes" and a \\ backslash'
    m = tomllib.loads(agent_gen.build_manifest("git", prompt))
    assert m["model"]["system_prompt"] == prompt


def test_default_prompt_pins_the_single_tool():
    p = agent_gen.default_prompt("redis")
    assert "`redis`" in p and "ONE MCP" in p


def test_manifests_one_per_host_tool(monkeypatch):
    monkeypatch.setattr(agent_gen, "_load", lambda: REG)
    out = agent_gen.manifests()
    tools = [t for t, _ in out]
    assert tools == ["docker", "qdrant"]
    # each manifest is valid + allowlisted to its own tool
    for tool, manifest in out:
        m = tomllib.loads(manifest)
        assert m["mcp_servers"] == [tool]
