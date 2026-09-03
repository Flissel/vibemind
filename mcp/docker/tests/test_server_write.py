from unittest import mock

from docker import server


def test_container_rm_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.container_rm("abc")
    assert res["approval_denied"] is True
    assert "docker rm abc" in res["command"]


def test_container_rm_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_rm("abc", force=True)
    assert run.call_args[0][0] == ["rm", "-f", "abc"]


def test_container_stop_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_stop("abc")
    assert run.call_args[0][0] == ["stop", "abc"]


def test_image_pull_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.image_pull("redis:7")
    assert run.call_args[0][0] == ["pull", "redis:7"]


def test_container_exec_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_exec("abc", "ls -la")
    assert run.call_args[0][0] == ["exec", "abc", "ls", "-la"]


def test_container_exec_shlex_split(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_exec("abc", 'sh -c "echo hello world"')
    assert run.call_args[0][0] == ["exec", "abc", "sh", "-c", "echo hello world"]
