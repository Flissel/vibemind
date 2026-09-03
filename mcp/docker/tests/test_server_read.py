from unittest import mock

from docker import server


def test_container_ls_builds_ps_command():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True, "command": "docker ps --format {{json .}}", "data": []}
        server.container_ls(all=False)
    args, kwargs = run.call_args
    assert args[0][0] == "ps"
    assert "-a" not in args[0]
    assert kwargs.get("parse") == "ndjson"


def test_container_ls_all_adds_flag():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_ls(all=True)
    assert "-a" in run.call_args[0][0]


def test_container_inspect_uses_json_parse():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_inspect("abc")
    args, kwargs = run.call_args
    assert args[0] == ["container", "inspect", "abc"]
    assert kwargs.get("parse") == "json"


def test_image_ls_builds_images_command():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.image_ls()
    assert run.call_args[0][0][0] == "images"


def test_container_logs_tail_and_since():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_logs("abc", tail=50, since="10m")
    assert run.call_args[0][0] == ["logs", "--tail", "50", "--since", "10m", "abc"]


def test_container_logs_without_since_omits_flag():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_logs("abc", tail=200)
    args = run.call_args[0][0]
    assert args == ["logs", "--tail", "200", "abc"]
    assert "--since" not in args
