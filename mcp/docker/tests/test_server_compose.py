from unittest import mock

from docker import server


def test_compose_ps_read(monkeypatch):
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_ps(file="docker-compose.yml")
    assert run.call_args[0][0] == ["compose", "-f", "docker-compose.yml", "ps", "--format", "json"]


def test_compose_up_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.compose_up(file="dc.yml")
    assert res["approval_denied"] is True


def test_compose_up_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_up(file="dc.yml", project="proj")
    assert run.call_args[0][0] == ["compose", "-f", "dc.yml", "-p", "proj", "up", "-d"]


def test_compose_down_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_down(file="dc.yml")
    assert run.call_args[0][0] == ["compose", "-f", "dc.yml", "down"]


def test_compose_up_allowed_via_group_verb(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "compose:up")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        res = server.compose_up(file="dc.yml")
    # It ran (not denied) and built the right command.
    assert "approval_denied" not in res
    assert run.call_args[0][0] == ["compose", "-f", "dc.yml", "up", "-d"]
