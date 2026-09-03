from unittest import mock

from docker import server


def test_stack_ls_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_ls()
    assert run.call_args[0][0] == ["stack", "ls", "--format", "{{json .}}"]


def test_stack_ps_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_ps("vibemind")
    assert run.call_args[0][0] == ["stack", "ps", "vibemind", "--format", "{{json .}}"]


def test_service_inspect_json():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.service_inspect("vibemind_brain-core")
    args, kwargs = run.call_args
    assert args[0] == ["service", "inspect", "vibemind_brain-core"]
    assert kwargs.get("parse") == "json"


def test_stack_deploy_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.stack_deploy("vibemind", "stack.yml")
    assert res["approval_denied"] is True


def test_stack_rm_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_rm("vibemind")
    assert run.call_args[0][0] == ["stack", "rm", "vibemind"]


def test_service_scale_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.service_scale("vibemind_brain-core", 3)
    assert run.call_args[0][0] == ["service", "scale", "vibemind_brain-core=3"]


def test_system_df_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.system_df()
    assert run.call_args[0][0] == ["system", "df"]


def test_system_prune_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.system_prune()
    assert res["approval_denied"] is True
    assert "--volumes" not in res["command"]
