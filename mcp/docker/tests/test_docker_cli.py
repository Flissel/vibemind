import subprocess
from unittest import mock

from docker import docker_cli


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_success_no_parse_returns_stdout():
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stdout="hello\n")):
        result = docker_cli.run(["version"])
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "hello\n"
    assert result["data"] is None
    assert result["command"] == "docker version"


def test_run_parses_ndjson_lines():
    out = '{"ID":"a"}\n{"ID":"b"}\n'
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stdout=out)):
        result = docker_cli.run(["ps"], parse="ndjson")
    assert result["ok"] is True
    assert result["data"] == [{"ID": "a"}, {"ID": "b"}]


def test_run_parses_json_array():
    out = '[{"Id":"x"}]'
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stdout=out)):
        result = docker_cli.run(["inspect", "x"], parse="json")
    assert result["data"] == [{"Id": "x"}]


def test_run_bad_json_keeps_stdout_data_none():
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stdout="not json")):
        result = docker_cli.run(["ps"], parse="ndjson")
    assert result["ok"] is True
    assert result["data"] is None
    assert result["stdout"] == "not json"


def test_run_timeout_returns_ok_false():
    with mock.patch("docker.docker_cli.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=30)):
        result = docker_cli.run(["ps"], timeout=30)
    assert result["ok"] is False
    assert "timed out" in result["stderr"]
    assert result["exit_code"] is None


def test_run_docker_not_found():
    with mock.patch("docker.docker_cli.subprocess.run", side_effect=FileNotFoundError()):
        result = docker_cli.run(["ps"])
    assert result["ok"] is False
    assert "not found" in result["stderr"]


def test_run_nonzero_exit_passes_stderr():
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stderr="No such container: x", returncode=1)):
        result = docker_cli.run(["inspect", "x"])
    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert "No such container" in result["stderr"]


def test_run_daemon_unreachable_hint():
    err = "Cannot connect to the Docker daemon at npipe:////./pipe/docker_engine."
    with mock.patch("docker.docker_cli.subprocess.run", return_value=_completed(stderr=err, returncode=1)):
        result = docker_cli.run(["ps"])
    assert result["ok"] is False
    assert result["daemon_unreachable"] is True


def test_run_permission_error_returns_ok_false():
    with mock.patch("docker.docker_cli.subprocess.run", side_effect=PermissionError("denied")):
        result = docker_cli.run(["ps"])
    assert result["ok"] is False
    assert "failed to run docker" in result["stderr"]
    assert result["exit_code"] is None
    assert result["daemon_unreachable"] is False
