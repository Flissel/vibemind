from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from coding_subscription_driver import Invocation


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_runtime() -> ModuleType:
    runtime_path = SCRIPTS_DIR / "subscription_wrapper_runtime.py"
    assert runtime_path.is_file(), "missing shared subscription wrapper runtime"
    spec = importlib.util.spec_from_file_location("subscription_wrapper_runtime", runtime_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeCompletedProcess:
    def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _invocation(tmp_path: Path, *, stdin_text: str = "prompt") -> Invocation:
    return Invocation(
        argv=("claude", "-p"),
        env={"PATH": "sanitized-path"},
        cwd=tmp_path,
        stdin_text=stdin_text,
    )


@pytest.mark.parametrize("suffix", [".cmd", ".bat", ".ps1"])
def test_shared_runtime_rejects_windows_batch_shims_without_runner(
    tmp_path: Path,
    suffix: str,
) -> None:
    runtime = _load_runtime()
    observed: dict[str, Any] = {}
    batch_shim = tmp_path / f"claude{suffix}"

    def resolver(command: str, *, path: str | None) -> str:
        observed.setdefault("resolver", []).append((command, path))
        return str(batch_shim)

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        pytest.fail("batch shims must not reach the runner")

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=resolver,
        runner=runner,
    )

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription configuration failed"
    assert observed["resolver"] == [
        ("claude", "sanitized-path"),
        ("claude.exe", "sanitized-path"),
    ]


def test_shared_runtime_accepts_native_windows_executable_without_shell(tmp_path: Path) -> None:
    runtime = _load_runtime()
    observed: dict[str, Any] = {}
    exact_command = tmp_path / "claude.exe"
    metacharacter_prompt = "explain $(not-run) & <never-an-argument>"
    invocation = Invocation(
        argv=("claude", "--model", "model&name", "--dir", "C:/project&name"),
        env={"PATH": "sanitized-path"},
        cwd=tmp_path,
        stdin_text=metacharacter_prompt,
    )

    def resolver(command: str, *, path: str | None) -> str:
        observed["resolver"] = (command, path)
        return str(exact_command)

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        observed["argv"] = args[0]
        observed["kwargs"] = kwargs
        return _FakeCompletedProcess(returncode=17, stdout="sensitive failure", stderr="details")

    outcome = runtime.execute_invocation(
        invocation,
        timeout_seconds=30,
        resolver=resolver,
        runner=runner,
    )

    assert outcome.exit_code == 17
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription command failed"
    assert observed["resolver"] == ("claude", "sanitized-path")
    assert observed["argv"][0] == str(exact_command)
    assert metacharacter_prompt not in observed["argv"]
    assert "model&name" in observed["argv"]
    assert "C:/project&name" in observed["argv"]
    assert observed["kwargs"]["input"] == metacharacter_prompt
    assert observed["kwargs"]["shell"] is False


def test_shared_runtime_returns_generic_configuration_failure_when_missing_executable(
    tmp_path: Path,
) -> None:
    runtime = _load_runtime()

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=lambda command, *, path: None,
        runner=lambda *args, **kwargs: pytest.fail("runner must not be called"),
    )

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription configuration failed"


def test_shared_runtime_maps_timeout_without_child_output(tmp_path: Path) -> None:
    runtime = _load_runtime()

    def timeout_runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=lambda command, *, path: command,
        runner=timeout_runner,
    )

    assert outcome.exit_code == 124
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription command timed out"


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        ("", "invalid API key"),
        ("", "OAuth token revoked; run /login"),
        ("", "session expired; run /login"),
        ("", "sign-in required"),
        ("", "authentication failed"),
        ("", "HTTP 401 Unauthorized"),
        ('{"error":"forbidden"}', ""),
        ('{"type":"error","status":403}', ""),
        (
            '{"type":"result","subtype":"error_during_execution",'
            '"is_error":true,"errors":["Invalid API key"]}',
            "",
        ),
        (
            '{"type":"result","is_error":true,'
            '"errors":["OAuth token revoked; run /login"]}',
            "",
        ),
        (
            '{"type":"result","is_error":true,'
            '"errors":["session expired; run /login"]}',
            "",
        ),
    ],
)
def test_shared_runtime_classifies_bounded_auth_diagnostics(
    tmp_path: Path,
    stdout: str,
    stderr: str,
) -> None:
    runtime = _load_runtime()

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=lambda command, *, path: command,
        runner=lambda *args, **kwargs: _FakeCompletedProcess(
            returncode=9,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    assert outcome.exit_code == 2
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription authentication failed"


def test_shared_runtime_does_not_classify_unstructured_stdout_as_auth(tmp_path: Path) -> None:
    runtime = _load_runtime()

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=lambda command, *, path: command,
        runner=lambda *args, **kwargs: _FakeCompletedProcess(
            returncode=9,
            stdout="The generated code prints HTTP 403 Forbidden for a test.",
            stderr="",
        ),
    )

    assert outcome.exit_code == 9
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription command failed"


@pytest.mark.parametrize(
    "stderr",
    [
        "assert response.status == 401",
        "fixture_403_forbidden_case.py failed",
        "user task text contains forbidden as an ordinary word",
    ],
)
def test_shared_runtime_does_not_classify_weak_stderr_auth_words(
    tmp_path: Path,
    stderr: str,
) -> None:
    runtime = _load_runtime()

    outcome = runtime.execute_invocation(
        _invocation(tmp_path),
        timeout_seconds=30,
        resolver=lambda command, *, path: command,
        runner=lambda *args, **kwargs: _FakeCompletedProcess(
            returncode=9,
            stdout="",
            stderr=stderr,
        ),
    )

    assert outcome.exit_code == 9
    assert outcome.stdout == ""
    assert outcome.diagnostic == "subscription command failed"
