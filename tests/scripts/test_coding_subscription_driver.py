from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any, cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from coding_subscription_driver import (
    Backend,
    DriverRequest,
    Invocation,
    build_invocation,
)


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_wrapper(filename: str) -> ModuleType:
    wrapper_path = SCRIPTS_DIR / filename
    assert wrapper_path.is_file(), f"missing subscription wrapper: {filename}"
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), wrapper_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCompletedProcess:
    def __init__(self, *, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _resolved_command(command: str, *, path: str | None) -> str:
    return command


def _valid_openfang_driver_argv(tmp_path: Path) -> tuple[str, ...]:
    system_prompt_file = tmp_path / "openfang-system-prompt.txt"
    system_prompt_file.write_text("test system prompt", encoding="utf-8")
    return (
        "-p",
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--system-prompt-file",
        str(system_prompt_file),
        "--dangerously-skip-permissions",
        "--model",
        "sonnet",
    )


def test_opencode_wrapper_requires_explicit_model_for_missing_or_blank_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")

    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: None)
    for model in (None, "", "   "):
        environ: dict[str, str] = {}
        if model is not None:
            environ["VIBEMIND_OPENCODE_MODEL"] = model

        with pytest.raises(ValueError, match="VIBEMIND_OPENCODE_MODEL"):
            wrapper.make_request("Implement the endpoint.", environ=environ)


def test_claude_wrapper_requires_explicit_model_for_missing_or_blank_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_claude_subscription_wrapper.py")

    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: None)
    for model in (None, "", "\t"):
        environ: dict[str, str] = {}
        if model is not None:
            environ["VIBEMIND_CLAUDE_MODEL"] = model

        with pytest.raises(ValueError, match="VIBEMIND_CLAUDE_MODEL"):
            wrapper.make_request("Implement the endpoint.", environ=environ)


def test_opencode_wrapper_builds_dedicated_runtime_request_from_resolved_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    project_dir = tmp_path / "project"
    runtime_dir = tmp_path / "runtime"
    project_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    request = wrapper.make_request(
        "Build the requested feature.",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai/gpt-5",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
            "VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS": "45",
        },
    )

    assert request.backend is Backend.OPENCODE
    assert request.cwd == str(project_dir.resolve())
    assert request.runtime_cwd == str(runtime_dir.resolve())
    assert request.runtime_cwd != request.cwd
    assert request.model == "openai/gpt-5"
    assert request.prompt == "Build the requested feature."
    assert request.timeout_seconds == 45


def test_claude_wrapper_builds_project_request_from_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_claude_subscription_wrapper.py")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    request = wrapper.make_request(
        "Inspect the implementation.",
        environ={
            "VIBEMIND_CLAUDE_MODEL": "claude-sonnet-subscription",
            "VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS": "30",
        },
    )

    assert request.backend is Backend.CLAUDE_CODE
    assert request.cwd == str(project_dir.resolve())
    assert request.runtime_cwd == str(project_dir.resolve())
    assert request.model == "claude-sonnet-subscription"
    assert request.prompt == "Inspect the implementation."
    assert request.timeout_seconds == 30


def test_opencode_wrapper_forwards_normalized_result_and_child_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    project_dir = tmp_path / "project"
    runtime_dir = tmp_path / "runtime"
    project_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )
    observed: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return _FakeCompletedProcess(
            returncode=0,
            stdout='{"type":"text","part":{"text":"completed"}}',
            stderr="child diagnostic\n",
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = wrapper.main(
        argv=_valid_openfang_driver_argv(tmp_path),
        stdin=io.StringIO("Complete stdin prompt."),
        stdout=stdout,
        stderr=stderr,
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai/gpt-5",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
        },
        runner=runner,
        resolver=_resolved_command,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "completed\n"
    assert stderr.getvalue() == "child diagnostic\n"
    assert observed["args"][0][0] == "opencode.exe"
    assert observed["kwargs"]["cwd"] == runtime_dir.resolve()
    assert observed["kwargs"]["input"] == "Complete stdin prompt."
    assert observed["kwargs"]["timeout"] <= 600
    assert observed["kwargs"]["shell"] is False


def test_opencode_wrapper_normalizes_only_assistant_text_jsonl_events() -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")

    result = wrapper._normalize_result(
        "\n".join(
            [
                '{"type":"step_start","metadata":{"cost":1}}',
                '{"type":"text","part":{"text":"First "}}',
                '{"type":"tool","part":{"text":"must not appear"}}',
                '{"type":"text","part":{"text":"second."}}',
            ]
        )
    )

    assert result == "First second."


@pytest.mark.parametrize(
    "output",
    [
        '{"type":"step_start","metadata":{"cost":1}}',
        '{"type":"text","part":{"not_text":"missing"}}',
        "not-json-protocol",
    ],
)
def test_opencode_wrapper_rejects_malformed_or_unrecognized_success_protocol(output: str) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")

    assert wrapper._normalize_result(output) is None


@pytest.mark.parametrize(
    "output",
    [
        '{"result":"legacy result must not be accepted"}',
        "\n".join(
            [
                '{"type":"text","part":{"text":"partial output"}}',
                '{"type":"error","message":"provider failure"}',
            ]
        ),
        "\n".join(
            [
                '{"type":"error","message":"provider failure"}',
                '{"type":"text","part":{"text":"partial output"}}',
            ]
        ),
        "\n".join(
            [
                '{"type":"text","part":{"text":"partial output"}}',
                '{"error":"provider failure"}',
            ]
        ),
        "\n".join(
            [
                '{"status":500}',
                '{"type":"text","part":{"text":"partial output"}}',
            ]
        ),
    ],
)
def test_opencode_wrapper_fails_closed_on_zero_exit_error_protocol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    project_dir = tmp_path / "project"
    runtime_dir = tmp_path / "runtime"
    project_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        return _FakeCompletedProcess(returncode=0, stdout=output, stderr="")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = wrapper.main(
        argv=_valid_openfang_driver_argv(tmp_path),
        stdin=io.StringIO("Complete stdin prompt."),
        stdout=stdout,
        stderr=stderr,
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai/gpt-5",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
        },
        runner=runner,
        resolver=_resolved_command,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "subscription response invalid\n"


def test_claude_wrapper_forwards_stdin_result_and_timeout_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_claude_subscription_wrapper.py")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )
    observed: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return _FakeCompletedProcess(
            returncode=0,
            stdout='{"result": "review complete"}',
            stderr="",
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = wrapper.main(
        argv=_valid_openfang_driver_argv(tmp_path),
        stdin=io.StringIO("The complete stdin prompt."),
        stdout=stdout,
        stderr=stderr,
        environ={"VIBEMIND_CLAUDE_MODEL": "claude-subscription"},
        runner=runner,
        resolver=_resolved_command,
    )

    assert exit_code == 0
    assert stdout.getvalue() == "review complete\n"
    assert stderr.getvalue() == ""
    assert observed["args"][0][:2] == ("claude.exe", "-p")
    assert observed["kwargs"]["cwd"] == project_dir.resolve()
    assert observed["kwargs"]["input"] == "The complete stdin prompt."
    assert observed["kwargs"]["shell"] is False

    def timeout_runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    timeout_stderr = io.StringIO()
    assert (
        wrapper.main(
            argv=_valid_openfang_driver_argv(tmp_path),
            stdin=io.StringIO("The complete stdin prompt."),
            stdout=io.StringIO(),
            stderr=timeout_stderr,
            environ={"VIBEMIND_CLAUDE_MODEL": "claude-subscription"},
            runner=timeout_runner,
            resolver=_resolved_command,
        )
        == 124
    )
    assert "timed out" in timeout_stderr.getvalue().lower()


@pytest.mark.parametrize(
    ("filename", "model_key", "auth_output"),
    [
        (
            "openfang_opencode_wrapper.py",
            "VIBEMIND_OPENCODE_MODEL",
            {"stderr": "request failed: unauthorized; token=never-echo", "stdout": ""},
        ),
        (
            "openfang_claude_subscription_wrapper.py",
            "VIBEMIND_CLAUDE_MODEL",
            {"stderr": "", "stdout": '{"error":"login required; token=never-echo"}'},
        ),
    ],
)
def test_subscription_wrapper_redacts_child_auth_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
    auth_output: dict[str, str],
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    def auth_runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        return _FakeCompletedProcess(returncode=1, **auth_output)

    stdout = io.StringIO()
    stderr = io.StringIO()
    environ = {model_key: "subscription-model"}
    if filename == "openfang_opencode_wrapper.py":
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)

    assert (
        wrapper.main(
            argv=_valid_openfang_driver_argv(tmp_path),
            stdin=io.StringIO("Use the subscription CLI."),
            stdout=stdout,
            stderr=stderr,
            environ=environ,
            runner=auth_runner,
            resolver=_resolved_command,
        )
        == 2
    )
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "subscription authentication failed\n"
    assert "token" not in stderr.getvalue().lower()


@pytest.mark.parametrize(
    ("diagnostic", "output_stream"),
    [
        ("HTTP 401 Unauthorized", "stderr"),
        ('{"error":"Error: HTTP 403 Forbidden"}', "stdout"),
        ('{"error":"unauthorized"}', "stdout"),
        ("invalid credentials", "stderr"),
    ],
)
@pytest.mark.parametrize(
    ("filename", "model_key"),
    [
        ("openfang_opencode_wrapper.py", "VIBEMIND_OPENCODE_MODEL"),
        ("openfang_claude_subscription_wrapper.py", "VIBEMIND_CLAUDE_MODEL"),
    ],
)
def test_subscription_wrapper_classifies_common_auth_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
    diagnostic: str,
    output_stream: str,
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )
    child_output = {"stdout": "", "stderr": ""}
    child_output[output_stream] = diagnostic

    def auth_runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        return _FakeCompletedProcess(returncode=23, **child_output)

    stdout = io.StringIO()
    stderr = io.StringIO()
    environ = {model_key: "subscription-model"}
    if filename == "openfang_opencode_wrapper.py":
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)

    assert (
        wrapper.main(
            argv=_valid_openfang_driver_argv(tmp_path),
            stdin=io.StringIO("Use the subscription CLI."),
            stdout=stdout,
            stderr=stderr,
            environ=environ,
            runner=auth_runner,
            resolver=_resolved_command,
        )
        == 2
    )
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "subscription authentication failed\n"
    assert diagnostic not in stderr.getvalue()


@pytest.mark.parametrize(
    ("filename", "model_key"),
    [
        ("openfang_opencode_wrapper.py", "VIBEMIND_OPENCODE_MODEL"),
        ("openfang_claude_subscription_wrapper.py", "VIBEMIND_CLAUDE_MODEL"),
    ],
)
def test_subscription_wrapper_redacts_non_auth_child_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    def failure_runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        return _FakeCompletedProcess(
            returncode=19,
            stdout="implementation failure details",
            stderr="child diagnostic details",
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    environ = {model_key: "subscription-model"}
    if filename == "openfang_opencode_wrapper.py":
        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)

    assert (
        wrapper.main(
            argv=_valid_openfang_driver_argv(tmp_path),
            stdin=io.StringIO("Use the subscription CLI."),
            stdout=stdout,
            stderr=stderr,
            environ=environ,
            runner=failure_runner,
            resolver=_resolved_command,
        )
        == 19
    )
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "subscription command failed\n"


@pytest.mark.parametrize(
    ("project_parts", "runtime_parts"),
    [
        (("project",), ("project",)),
        (("project",), ("project", "runtime")),
        (("runtime", "project"), ("runtime",)),
        (("project",), ("outside-runtime",)),
    ],
)
def test_opencode_runtime_rejects_untrusted_or_overlapping_configurations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_parts: tuple[str, ...],
    runtime_parts: tuple[str, ...],
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setattr(wrapper.Path, "home", classmethod(lambda cls: home_dir))
    project_dir = home_dir.joinpath(*project_parts)
    runtime_dir = (
        tmp_path.joinpath(*runtime_parts)
        if runtime_parts == ("outside-runtime",)
        else home_dir.joinpath(*runtime_parts)
    )
    project_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    with pytest.raises(ValueError, match="current user home|overlap"):
        wrapper.make_request(
            "Run OpenCode.",
            environ={
                "VIBEMIND_OPENCODE_MODEL": "subscription-model",
                "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
            },
        )


def test_opencode_runtime_accepts_dedicated_directory_under_current_user_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    home_dir = tmp_path / "home"
    project_dir = home_dir / "project"
    runtime_dir = home_dir / "subscription-runtime" / "opencode"
    project_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(wrapper.Path, "home", classmethod(lambda cls: home_dir))
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    request = wrapper.make_request(
        "Run OpenCode.",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "subscription-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
        },
    )

    assert request.runtime_cwd == str(runtime_dir.resolve())


def test_opencode_runtime_defaults_to_dedicated_current_user_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    home_dir = tmp_path / "home"
    project_dir = home_dir / "project"
    project_dir.mkdir(parents=True)
    monkeypatch.setattr(wrapper.Path, "home", classmethod(lambda cls: home_dir))
    monkeypatch.setattr(
        wrapper,
        "resolve_project",
        lambda prompt: {"code_path": str(project_dir)},
    )

    request = wrapper.make_request(
        "Run OpenCode.",
        environ={"VIBEMIND_OPENCODE_MODEL": "subscription-model"},
    )

    assert request.runtime_cwd == str(
        (home_dir / ".vibemind" / "subscription-runtime" / "opencode").resolve()
    )


def _request(
    *,
    backend: Backend,
    model: str,
    runtime_dir: Path,
    project_dir: Path,
    prompt: str = "Explain the failing test.",
) -> DriverRequest:
    return DriverRequest(
        backend=backend,
        prompt=prompt,
        cwd=str(project_dir),
        runtime_cwd=str(runtime_dir),
        model=model,
        timeout_seconds=30,
    )


def test_exposes_frozen_subscription_driver_contract_types(tmp_path: Path) -> None:
    request = _request(
        backend=Backend.OPENCODE,
        model="openai/gpt-5",
        runtime_dir=tmp_path,
        project_dir=tmp_path,
    )
    invocation = Invocation(argv=(), env={}, cwd=tmp_path, stdin_text=None)

    assert Backend.OPENCODE.value == "opencode"
    assert Backend.CLAUDE_CODE.value == "claude-code"
    assert [field.name for field in fields(DriverRequest)] == [
        "backend",
        "prompt",
        "cwd",
        "runtime_cwd",
        "model",
        "timeout_seconds",
        "system_prompt_file",
        "system_prompt",
    ]
    assert [field.name for field in fields(Invocation)] == [
        "argv",
        "env",
        "cwd",
        "stdin_text",
    ]
    with pytest.raises(FrozenInstanceError):
        request.model = "another-model"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        invocation.cwd = tmp_path / "other"  # type: ignore[misc]


def test_builds_opencode_subscription_invocation_without_openai_api_key(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "opencode-runtime"
    project_dir = tmp_path / "project"
    runtime_dir.mkdir()
    project_dir.mkdir()
    prompt = "Summarize this repository; $(never-execute) & <metacharacters>."
    model = "openai/gpt-5"

    invocation = build_invocation(
        _request(
            backend=Backend.OPENCODE,
            model=model,
            runtime_dir=runtime_dir,
            project_dir=project_dir,
            prompt=prompt,
        ),
        inherited_env={
            "OPENAI_API_KEY": "must-be-removed",
            "openai_api_key": "must-also-be-removed",
            "OPENCODE_CONFIG_CONTENT": "must-not-be-inherited",
            "PATH": "test-path",
        },
    )

    assert invocation.argv[:5] == (
        "opencode",
        "--pure",
        "run",
        "--format",
        "json",
    )
    assert invocation.argv[5:7] == ("--model", model)
    dir_index = invocation.argv.index("--dir")
    assert invocation.argv[dir_index + 1] == str(project_dir.resolve())
    assert prompt not in invocation.argv
    assert invocation.cwd == runtime_dir.resolve()
    assert invocation.stdin_text == prompt
    assert "OPENAI_API_KEY" not in invocation.env
    assert "openai_api_key" not in invocation.env
    assert "OPENCODE_CONFIG_CONTENT" not in invocation.env
    assert invocation.env["PATH"] == "test-path"


def test_builds_claude_subscription_invocation_without_anthropic_auth_env(
    tmp_path: Path,
) -> None:
    runtime_dir = tmp_path / "claude-runtime"
    project_dir = tmp_path / "project"
    runtime_dir.mkdir()
    project_dir.mkdir()
    prompt = "Review the current diff."
    model = "claude-sonnet-4-5"

    invocation = build_invocation(
        _request(
            backend=Backend.CLAUDE_CODE,
            model=model,
            runtime_dir=runtime_dir,
            project_dir=project_dir,
            prompt=prompt,
        ),
        inherited_env={
            "Anthropic_Api_Key": "must-be-removed",
            "anthropic_auth_token": "must-be-removed",
            "anthropic_base_url": "must-be-removed",
            "UNRELATED_SETTING": "preserved",
        },
    )

    assert invocation.argv[:6] == (
        "claude",
        "-p",
        "--output-format",
        "json",
        "--model",
        model,
    )
    assert invocation.cwd == project_dir.resolve()
    assert invocation.stdin_text == prompt
    assert "Anthropic_Api_Key" not in invocation.env
    assert "anthropic_auth_token" not in invocation.env
    assert "anthropic_base_url" not in invocation.env
    assert invocation.env["UNRELATED_SETTING"] == "preserved"


def test_builds_claude_system_prompt_file_invocation_without_prompt_contents_in_argv(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    system_file = tmp_path / "protected system prompt.txt"
    sentinel = "{{MEMORY}} protected system sentinel"
    system_file.write_text(sentinel, encoding="utf-8")
    request = DriverRequest(
        backend=Backend.CLAUDE_CODE,
        prompt="Review src/main.py.",
        cwd=str(project_dir),
        runtime_cwd=str(project_dir),
        model="claude-sonnet-4-5",
        timeout_seconds=30,
        system_prompt_file=str(system_file),
        system_prompt=sentinel,
    )

    invocation = build_invocation(request, inherited_env={"PATH": "test-path"})

    assert invocation.argv[invocation.argv.index("--system-prompt-file") + 1] == str(
        system_file.resolve()
    )
    assert "--system-prompt" not in invocation.argv
    assert sentinel not in invocation.argv


def test_rejects_claude_system_prompt_contents_without_protected_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="^Claude system prompt requires a protected file$",
    ):
        build_invocation(
            DriverRequest(
                backend=Backend.CLAUDE_CODE,
                prompt="Review src/main.py.",
                cwd=str(tmp_path),
                runtime_cwd=str(tmp_path),
                model="claude-sonnet-4-5",
                timeout_seconds=30,
                system_prompt="must never enter argv",
            ),
            inherited_env={"PATH": "test-path"},
        )


@pytest.mark.parametrize("backend", [Backend.OPENCODE, Backend.CLAUDE_CODE])
@pytest.mark.parametrize("model", ["", "   ", "\t\r\n"])
def test_rejects_blank_subscription_model(
    tmp_path: Path,
    backend: Backend,
    model: str,
) -> None:
    runtime_dir = tmp_path / "runtime"
    project_dir = tmp_path / "project"
    runtime_dir.mkdir()
    project_dir.mkdir()

    with pytest.raises(ValueError, match="^subscription model is required$"):
        build_invocation(
            _request(
                backend=backend,
                model=model,
                runtime_dir=runtime_dir,
                project_dir=project_dir,
            ),
            inherited_env={"PATH": "test-path"},
        )


def test_rejects_opencode_runtime_directory_containing_dotenv(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "opencode-runtime"
    project_dir = tmp_path / "project"
    runtime_dir.mkdir()
    project_dir.mkdir()
    (runtime_dir / ".env").touch()

    with pytest.raises(
        ValueError,
        match=r"^OpenCode runtime directory must not contain \.env$",
    ):
        build_invocation(
            _request(
                backend=Backend.OPENCODE,
                model="openai/gpt-5",
                runtime_dir=runtime_dir,
                project_dir=project_dir,
            ),
            inherited_env={"PATH": "test-path"},
        )


def test_rejects_unsupported_subscription_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="^unsupported subscription backend$"):
        build_invocation(
            _request(
                backend=cast(Backend, "unsupported"),
                model="subscription-model",
                runtime_dir=tmp_path,
                project_dir=tmp_path,
            ),
            inherited_env={"PATH": "test-path"},
        )


def _openfang_driver_argv(system_prompt_file: Path, *, model: str = "sonnet") -> tuple[str, ...]:
    return (
        "-p",
        "--input-format",
        "text",
        "--output-format",
        "stream-json",
        "--verbose",
        "--system-prompt-file",
        str(system_prompt_file),
        "--dangerously-skip-permissions",
        "--model",
        model,
    )


@pytest.mark.parametrize(
    ("filename", "model_key", "child_stdout"),
    [
        (
            "openfang_opencode_wrapper.py",
            "VIBEMIND_OPENCODE_MODEL",
            '{"type":"text","part":{"text":"OpenCode response"}}',
        ),
        (
            "openfang_claude_subscription_wrapper.py",
            "VIBEMIND_CLAUDE_MODEL",
            '{"result":"Claude response"}',
        ),
    ],
)
def test_wrappers_fail_closed_for_missing_or_unknown_openfang_driver_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
    child_stdout: str,
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: {"code_path": str(project_dir)})
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        nonlocal calls
        calls += 1
        return _FakeCompletedProcess(returncode=0, stdout=child_stdout, stderr="")

    environ = {model_key: "subscription-selected-model"}
    if filename == "openfang_opencode_wrapper.py":
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)

    for argv in [
        (),
        ("-p", "--system-prompt-file", str(tmp_path / "missing.txt")),
        ("-p", "--input-format", "text", "--output-format", "stream-json", "--verbose", "--model", "sonnet"),
        (*_openfang_driver_argv(tmp_path / "missing.txt"), "--not-an-openfang-flag"),
        _openfang_driver_argv(tmp_path / "missing.txt", model="openai/gpt-5"),
    ]:
        stderr = io.StringIO()
        assert (
            wrapper.main(
                argv=argv,
                stdin=io.StringIO("user mutation request"),
                stdout=io.StringIO(),
                stderr=stderr,
                environ=environ,
                runner=runner,
                resolver=_resolved_command,
            )
            == 2
        )
        assert "missing.txt" not in stderr.getvalue()
    assert calls == 0


@pytest.mark.parametrize(
    ("filename", "model_key", "child_stdout"),
    [
        (
            "openfang_opencode_wrapper.py",
            "VIBEMIND_OPENCODE_MODEL",
            '{"type":"text","part":{"text":"must not run"}}',
        ),
        (
            "openfang_claude_subscription_wrapper.py",
            "VIBEMIND_CLAUDE_MODEL",
            '{"result":"must not run"}',
        ),
    ],
)
def test_public_wrapper_main_rejects_omitted_context_abi_before_running_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
    child_stdout: str,
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    runtime_dir = tmp_path / "runtime"
    project_dir.mkdir()
    runtime_dir.mkdir()
    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: {"code_path": str(project_dir)})
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        nonlocal calls
        calls += 1
        return _FakeCompletedProcess(returncode=0, stdout=child_stdout, stderr="")

    environ = {model_key: "subscription-selected-model"}
    if filename == "openfang_opencode_wrapper.py":
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)
    stderr = io.StringIO()
    assert (
        wrapper.main(
            stdin=io.StringIO("fix src/main.py"),
            stdout=io.StringIO(),
            stderr=stderr,
            environ=environ,
            runner=runner,
            resolver=_resolved_command,
        )
        == 2
    )
    assert calls == 0
    assert "configuration error" in stderr.getvalue()


@pytest.mark.parametrize(
    ("filename", "model_key", "leaked_output"),
    [
        (
            "openfang_opencode_wrapper.py",
            "VIBEMIND_OPENCODE_MODEL",
            lambda sentinel, path: json.dumps(
                {"type": "text", "part": {"text": f"{sentinel} {path}"}}
            ),
        ),
        (
            "openfang_claude_subscription_wrapper.py",
            "VIBEMIND_CLAUDE_MODEL",
            lambda sentinel, path: json.dumps({"result": f"{sentinel} {path}"}),
        ),
    ],
)
def test_wrappers_fail_closed_when_success_output_echoes_system_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    model_key: str,
    leaked_output: Any,
) -> None:
    wrapper = _load_wrapper(filename)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    system_file = tmp_path / "system prompt.txt"
    sentinel = "{{MEMORY}} secret system sentinel"
    system_file.write_text(sentinel, encoding="utf-8")
    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: {"code_path": str(project_dir)})

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        return _FakeCompletedProcess(
            returncode=0,
            stdout=leaked_output(sentinel, system_file.resolve()),
            stderr=f"diagnostic {sentinel} {system_file.resolve()}",
        )

    environ = {model_key: "subscription-selected-model"}
    if filename == "openfang_opencode_wrapper.py":
        environ["VIBEMIND_OPENCODE_RUNTIME_CWD"] = str(runtime_dir)
    stdout = io.StringIO()
    stderr = io.StringIO()
    assert (
        wrapper.main(
            argv=_openfang_driver_argv(system_file),
            stdin=io.StringIO("fix src/main.py"),
            stdout=stdout,
            stderr=stderr,
            environ=environ,
            runner=runner,
            resolver=_resolved_command,
        )
        == 2
    )
    assert sentinel not in stdout.getvalue()
    assert sentinel not in stderr.getvalue()
    assert str(system_file.resolve()) not in stdout.getvalue()
    assert str(system_file.resolve()) not in stderr.getvalue()


def test_claude_wrapper_forwards_system_file_to_native_system_channel_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_claude_subscription_wrapper.py")
    project_dir = tmp_path / "checkout with spaces & chars"
    project_dir.mkdir()
    system_file = tmp_path / "system prompt & chars.txt"
    sentinel = "{{MEMORY}} system sentinel: never expose"
    system_file.write_text(sentinel, encoding="utf-8")
    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: {"code_path": str(project_dir)})
    observed: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        observed["argv"] = args[0]
        observed["kwargs"] = kwargs
        return _FakeCompletedProcess(
            returncode=0,
            stdout='{"result":"done"}',
            stderr=f"diagnostic {sentinel} {system_file}",
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    assert (
        wrapper.main(
            argv=_openfang_driver_argv(system_file),
            stdin=io.StringIO("fix src/main.py"),
            stdout=stdout,
            stderr=stderr,
            environ={"VIBEMIND_CLAUDE_MODEL": "subscription-claude"},
            runner=runner,
            resolver=_resolved_command,
        )
        == 0
    )
    argv = observed["argv"]
    assert argv[argv.index("--system-prompt-file") + 1] == str(system_file.resolve())
    assert "--system-prompt" not in argv
    assert sentinel not in argv
    assert observed["kwargs"]["input"] == "fix src/main.py"
    assert "claude-code/sonnet" not in argv
    assert "subscription-claude" in argv
    assert sentinel not in stdout.getvalue()
    assert sentinel not in stderr.getvalue()
    assert str(system_file) not in stdout.getvalue()
    assert str(system_file) not in stderr.getvalue()


def test_opencode_wrapper_references_system_file_from_primary_agent_config_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrapper = _load_wrapper("openfang_opencode_wrapper.py")
    project_dir = tmp_path / "checkout with spaces & chars"
    runtime_dir = tmp_path / "runtime"
    project_dir.mkdir()
    runtime_dir.mkdir()
    system_file = tmp_path / "system prompt & chars.txt"
    sentinel = "{{MEMORY}} system sentinel: never expose"
    system_file.write_text(sentinel, encoding="utf-8")
    monkeypatch.setattr(wrapper, "resolve_project", lambda prompt: {"code_path": str(project_dir)})
    observed: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> _FakeCompletedProcess:
        observed["argv"] = args[0]
        observed["kwargs"] = kwargs
        return _FakeCompletedProcess(
            returncode=0,
            stdout='{"type":"text","part":{"text":"done"}}',
            stderr=f"diagnostic {sentinel} {system_file}",
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    assert (
        wrapper.main(
            argv=_openfang_driver_argv(system_file),
            stdin=io.StringIO("fix src/main.py"),
            stdout=stdout,
            stderr=stderr,
            environ={
                "VIBEMIND_OPENCODE_MODEL": "subscription-opencode",
                "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_dir),
            },
            runner=runner,
            resolver=_resolved_command,
        )
        == 0
    )
    argv = observed["argv"]
    assert ("--agent", "vibemind-openfang") == (
        argv[argv.index("--agent")],
        argv[argv.index("--agent") + 1],
    )
    assert "subscription-opencode" in argv
    assert "claude-code/sonnet" not in argv
    config = json.loads(observed["kwargs"]["env"]["OPENCODE_CONFIG_CONTENT"])
    agent = config["agent"]["vibemind-openfang"]
    assert agent["mode"] == "primary"
    assert str(system_file.resolve()) in agent["prompt"]
    assert sentinel not in observed["kwargs"]["env"]["OPENCODE_CONFIG_CONTENT"]
    assert observed["kwargs"]["input"] == "fix src/main.py"
    assert sentinel not in stdout.getvalue()
    assert sentinel not in stderr.getvalue()


def test_openfang_launchers_prepend_trusted_outer_scripts_directory_to_path() -> None:
    start_script = (SCRIPTS_DIR / "vibemind-start.ps1").read_text(encoding="utf-8")
    restart_script = (SCRIPTS_DIR / "_restart_and_test_gateway.ps1").read_text(encoding="utf-8")
    watchdog = (SCRIPTS_DIR / "openfang_watchdog.py").read_text(encoding="utf-8")
    debug_launcher = (SCRIPTS_DIR.parent / "Vibemind.debug.ps1").read_text(encoding="utf-8")

    assert '$ofScripts = Join-Path $script:ROOT "scripts"' in start_script
    assert '$env:PATH = "$ofScripts;$ofOriginalPath"' in start_script
    assert '$env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofScripts' in start_script
    assert '$Root = Split-Path -Parent $PSScriptRoot' in restart_script
    assert '$OfScripts = Join-Path $Root "scripts"' in restart_script
    assert '$env:PATH = "$OfScripts;$NpmDir;$origPath"' in restart_script
    assert '$env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $OfScripts' in restart_script
    assert 'PROJECT_ROOT = Path(__file__).resolve().parent.parent' in watchdog
    assert 'outer_scripts = PROJECT_ROOT / "scripts"' in watchdog
    assert 'env["PATH"] = os.pathsep.join((str(outer_scripts), env.get("PATH", "")))' in watchdog
    assert 'env["VIBEMIND_SUBSCRIPTION_WRAPPER_DIR"] = str(outer_scripts.resolve())' in watchdog
    assert '$ofScripts = Join-Path $ROOT "scripts"' in debug_launcher
    assert '$env:PATH = "$ofScripts;$ofOriginalPath"' in debug_launcher
    assert '$env:VIBEMIND_SUBSCRIPTION_WRAPPER_DIR = $ofScripts' in debug_launcher
    assert 'C:\\Users\\User\\Desktop\\Vibemind_V1' not in restart_script
    assert 'C:\\Users\\User\\Desktop\\Vibemind_V1' not in watchdog


def test_wrapper_abi_fixture_matches_claude_driver_model_stripping_contract() -> None:
    driver_source = (
        SCRIPTS_DIR.parent
        / "vibemind-os"
        / "openfang"
        / "crates"
        / "openfang-runtime"
        / "src"
        / "drivers"
        / "claude_code.rs"
    ).read_text(encoding="utf-8")

    assert 'ClaudeCodeDriver::model_flag("claude-code/sonnet")' in driver_source
    assert '"sonnet",' in driver_source
