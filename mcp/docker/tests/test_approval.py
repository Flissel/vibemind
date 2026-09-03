from docker import approval


def test_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    allowed, reason = approval.require_approval("docker stack rm vibemind")
    assert allowed is False
    assert "docker stack rm vibemind" in reason


def test_allow_all_writes_env(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    allowed, _ = approval.require_approval("docker rm abc")
    assert allowed is True


def test_allow_specific_group_verb(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "container:start,container:restart")
    assert approval.require_approval("docker start abc")[0] is True
    assert approval.require_approval("docker rm abc")[0] is False


def test_bare_verb_does_not_match(monkeypatch):
    # Security: a bare 'rm' must NOT grant container rm (and thus never stack rm).
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "rm")
    assert approval.require_approval("docker rm abc")[0] is False


def test_group_verb_does_not_cross_groups(monkeypatch):
    # Allowing container:rm must NOT allow stack rm.
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "container:rm")
    assert approval.require_approval("docker rm abc")[0] is True
    assert approval.require_approval("docker stack rm vibemind")[0] is False


def test_gate_result_denied_shape():
    res = approval.denied_result("docker rm abc", "nope")
    assert res["ok"] is False
    assert res["approval_denied"] is True
    assert res["command"] == "docker rm abc"
    assert res["stderr"] == "nope"
    assert res["stdout"] == ""
    assert res["data"] is None
    assert res["exit_code"] is None
    assert res["daemon_unreachable"] is False


def test_allow_verbs_skips_flags_for_compose(monkeypatch):
    # Regression: -f <file> before the verb must not break group:verb derivation.
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "compose:up")
    allowed, _ = approval.require_approval(
        "docker compose -f dc.yml up -d", args=["compose", "-f", "dc.yml", "up", "-d"]
    )
    assert allowed is True


def test_allow_verbs_stack_deploy_with_flag(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "stack:deploy")
    allowed, _ = approval.require_approval(
        "docker stack deploy -c stack.yml vibemind",
        args=["stack", "deploy", "-c", "stack.yml", "vibemind"],
    )
    assert allowed is True
