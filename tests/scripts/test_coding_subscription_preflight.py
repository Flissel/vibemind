from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load_preflight() -> ModuleType:
    module_path = SCRIPTS_DIR / "coding_subscription_preflight.py"
    assert module_path.is_file(), "missing coding subscription preflight"
    spec = importlib.util.spec_from_file_location("coding_subscription_preflight", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _native(command: str, *, path: str | None) -> str:
    return f"C:/tools/{Path(command).stem}.exe"


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    home = tmp_path / "home"
    project = home / "project"
    runtime = home / ".vibemind" / "subscription-runtime" / "opencode"
    project.mkdir(parents=True)
    home.mkdir(exist_ok=True)
    return home, project, runtime


def test_inspection_redacts_values_and_marks_both_backends_ready(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    environment = {
        "VIBEMIND_OPENCODE_MODEL": "model-that-must-not-appear",
        "VIBEMIND_CLAUDE_MODEL": "another-model-that-must-not-appear",
        "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        "UNRELATED_SECRET": "must-not-appear",
    }

    report = preflight.inspect_environment(
        environment,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].ready is True
    assert report["anthropic"].ready is True
    assert report["openai"].auth_status == "unknown"
    assert report["anthropic"].auth_status == "unknown"
    rendered = repr(report)
    for value in environment.values():
        assert value not in rendered


def test_billing_shadow_reasons_are_case_insensitive_and_take_priority(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, _ = _inputs(tmp_path)

    report = preflight.inspect_environment(
        {
            "oPeNaI_aPi_KeY": "never-report-this",
            "aNtHrOpIc_BaSe_Url": "never-report-this-either",
        },
        resolver=lambda command, *, path: None,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].ready is False
    assert report["openai"].reason == "OPENAI_API_KEY shadows subscription auth"
    assert report["anthropic"].ready is False
    assert report["anthropic"].reason == "Anthropic PAYG environment shadows subscription auth"
    assert "VIBEMIND" not in report["openai"].reason
    assert "executable" not in report["anthropic"].reason
    assert "never-report-this" not in repr(report)


def test_inspection_requires_explicit_nonblank_models_without_defaults(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, _ = _inputs(tmp_path)

    report = preflight.inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": " \t",
            "VIBEMIND_CLAUDE_MODEL": "\n",
        },
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].reason == "VIBEMIND_OPENCODE_MODEL must be set"
    assert report["anthropic"].reason == "VIBEMIND_CLAUDE_MODEL must be set"


def test_inspection_uses_native_executable_policy_without_paths(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)

    def resolver(command: str, *, path: str | None) -> str | None:
        if command == "claude":
            return "C:/npm/claude.cmd"
        return None

    report = preflight.inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        resolver=resolver,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].reason == "OpenCode native executable unavailable"
    assert report["anthropic"].reason == "Claude Code native executable unavailable"
    assert "C:/" not in repr(report)


def test_inspection_validates_runtime_without_creating_or_copying_state(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    assert not runtime.exists()

    report = preflight.inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].ready is True
    assert not runtime.exists()


@pytest.mark.parametrize(
    ("runtime_builder", "expected_reason"),
    [
        (lambda project, home: project, "OpenCode runtime directory must not overlap project directory"),
        (lambda project, home: home / "outside", "OpenCode runtime directory must not contain .env"),
    ],
)
def test_inspection_rejects_runtime_overlap_and_dotenv(
    tmp_path: Path,
    runtime_builder: Any,
    expected_reason: str,
) -> None:
    preflight = _load_preflight()
    home, project, _ = _inputs(tmp_path)
    runtime = runtime_builder(project, home)
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime != project:
        (runtime / ".env").write_text("not-a-secret-test-fixture", encoding="utf-8")

    report = preflight.inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].reason == expected_reason


def test_static_inspection_never_calls_a_process_runner(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal calls
        calls += 1
        raise AssertionError("static inspection must not execute a subscription command")

    report = preflight.inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        resolver=_native,
        runner=runner,
        project_cwd=project,
        current_user_home=home,
    )

    assert report["openai"].ready is True
    assert calls == 0


def test_opaque_auth_check_uses_injected_bounded_status_command_and_never_returns_output() -> None:
    preflight = _load_preflight()
    observed: dict[str, Any] = {}

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return _Completed(0, stdout="account@example.test token=never-report", stderr="")

    status = preflight.inspect_cli_auth_status(
        "opencode",
        runner=runner,
        resolver=_native,
        timeout_seconds=7,
    )

    assert status == "authenticated"
    assert observed["args"][0] == ("C:/tools/opencode.exe", "auth", "list")
    assert observed["kwargs"]["timeout"] == 7
    assert observed["kwargs"]["shell"] is False
    assert "account@example.test" not in status


@pytest.mark.parametrize(
    ("backend", "command", "arguments"),
    [
        ("opencode", "opencode", ("auth", "list")),
        ("claude-code", "claude", ("auth", "status")),
    ],
)
def test_opaque_auth_check_resolves_a_native_executable_before_running(
    backend: str,
    command: str,
    arguments: tuple[str, ...],
) -> None:
    preflight = _load_preflight()
    resolved = f"C:/native/{command}.exe"
    resolver_calls: list[tuple[str, str | None]] = []
    runner_calls = 0

    def resolver(candidate: str, *, path: str | None) -> str | None:
        resolver_calls.append((candidate, path))
        if candidate == f"{command}.exe":
            return resolved
        return f"C:/npm/{candidate}.cmd"

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal runner_calls
        runner_calls += 1
        assert args[0] == (resolved, *arguments)
        return _Completed(1, stdout="raw account output", stderr="raw error output")

    status = preflight.inspect_cli_auth_status(
        backend,
        runner=runner,
        resolver=resolver,
        timeout_seconds=9,
    )

    assert status == "not-authenticated"
    assert runner_calls == 1
    assert resolver_calls == [(command, None), (f"{command}.exe", None)]


@pytest.mark.parametrize("candidate", [None, "C:/npm/claude.cmd"])
def test_opaque_auth_check_does_not_run_missing_or_non_native_executables(candidate: str | None) -> None:
    preflight = _load_preflight()
    runner_calls = 0

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal runner_calls
        runner_calls += 1
        raise AssertionError("a bare or batch auth command must never run")

    status = preflight.inspect_cli_auth_status(
        "claude-code",
        runner=runner,
        resolver=lambda command, *, path: candidate,
    )

    assert status == "unknown"
    assert runner_calls == 0


def test_opaque_auth_check_reduces_nonzero_and_timeout_to_statuses() -> None:
    preflight = _load_preflight()

    assert (
        preflight.inspect_cli_auth_status(
            "claude-code",
            runner=lambda *args, **kwargs: _Completed(1, stdout="secret"),
            resolver=_native,
        )
        == "not-authenticated"
    )

    def timeout(*args: Any, **kwargs: Any) -> _Completed:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="secret")

    assert (
        preflight.inspect_cli_auth_status(
            "claude-code",
            runner=timeout,
            resolver=_native,
        )
        == "unknown"
    )


def test_live_opencode_probe_uses_one_invalid_key_fixture_and_cleans_it(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    runtime.mkdir(parents=True)
    observed: dict[str, Any] = {"calls": 0}

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        observed["calls"] += 1
        observed["argv"] = args[0]
        observed["kwargs"] = kwargs
        fixture = Path(args[0][args[0].index("--dir") + 1])
        observed["fixture"] = fixture
        assert [path.name for path in fixture.iterdir()] == [".env"]
        assert (fixture / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=invalid-do-not-bill\n"
        return _Completed(0, stdout='{"type":"text","part":{"text":"SUBSCRIPTION_OK"}}')

    result = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert observed["calls"] == 1
    assert observed["argv"][0].endswith("opencode.exe")
    assert Path(observed["kwargs"]["cwd"]).parent == runtime.resolve()
    assert Path(observed["kwargs"]["cwd"]) != runtime.resolve()
    assert observed["kwargs"]["input"] == "Reply exactly SUBSCRIPTION_OK"
    assert not observed["fixture"].exists()
    assert result.backend == "opencode"
    assert result.exit_code == 0
    assert result.status == "success"
    assert "openai-model" not in repr(result)


def test_live_claude_probe_removes_billing_environment_without_fallback(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, _ = _inputs(tmp_path)
    observed: dict[str, Any] = {"calls": 0}

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        observed["calls"] += 1
        observed["argv"] = args[0]
        observed["env"] = kwargs["env"]
        return _Completed(0, stdout='{"result":"SUBSCRIPTION_OK"}')

    result = preflight.run_live_probe(
        "claude-code",
        environ={
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "ANTHROPIC_API_KEY": "never-report",
            "anthropic_auth_token": "also-never-report",
            "Anthropic_Base_Url": "never-report-either",
        },
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert observed["calls"] == 1
    assert observed["argv"][0].endswith("claude.exe")
    assert all(key.casefold() not in {"anthropic_api_key", "anthropic_auth_token", "anthropic_base_url"} for key in observed["env"])
    assert result.status == "success"


def test_live_probe_timeout_and_unexpected_output_are_redacted(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    runtime.mkdir(parents=True)

    def timeout(*args: Any, **kwargs: Any) -> _Completed:
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="sensitive output")

    timed_out = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        runner=timeout,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )
    assert timed_out.exit_code == 124
    assert timed_out.status == "failed"
    assert "sensitive output" not in repr(timed_out)

    unexpected = preflight.run_live_probe(
        "claude-code",
        environ={"VIBEMIND_CLAUDE_MODEL": "claude-model"},
        runner=lambda *args, **kwargs: _Completed(0, stdout='{"result":"SUBSCRIPTION_OK extra"}'),
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )
    assert unexpected.exit_code == 2
    assert unexpected.status == "failed"


@pytest.mark.parametrize(
    "failure_event",
    [
        {"type": "error", "detail": "raw type error"},
        {"error": "raw error field"},
        {"code": 500, "detail": "raw code error"},
        {"status": "failed", "detail": "raw status error"},
    ],
)
@pytest.mark.parametrize("failure_first", [True, False])
def test_live_opencode_probe_rejects_protocol_errors_in_any_jsonl_order(
    tmp_path: Path,
    failure_event: dict[str, object],
    failure_first: bool,
) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    runtime.mkdir(parents=True)
    success_event = {"type": "text", "part": {"text": "SUBSCRIPTION_OK"}}
    events = [failure_event, success_event] if failure_first else [success_event, failure_event]
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal calls
        calls += 1
        return _Completed(0, stdout="\n".join(json.dumps(event) for event in events))

    result = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert calls == 1
    assert result.exit_code == 2
    assert result.status == "failed"
    assert "raw" not in repr(result)


def test_live_opencode_probe_accepts_success_with_ordinary_control_and_tool_events(
    tmp_path: Path,
) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    runtime.mkdir(parents=True)
    events = [
        {"type": "step", "status": "started"},
        {"type": "tool", "status": "completed"},
        {"type": "text", "part": {"text": "SUBSCRIPTION_OK"}},
    ]

    result = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        runner=lambda *args, **kwargs: _Completed(
            0,
            stdout="\n".join(json.dumps(event) for event in events),
        ),
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert result.exit_code == 0
    assert result.status == "success"


@pytest.mark.parametrize(
    "failure_fields",
    [
        {"is_error": True, "detail": "raw is-error"},
        {"error": "raw error field"},
        {"code": 500, "detail": "raw code error"},
        {"status": "failed", "detail": "raw status error"},
    ],
)
def test_live_claude_probe_rejects_zero_exit_protocol_errors(
    tmp_path: Path,
    failure_fields: dict[str, object],
) -> None:
    preflight = _load_preflight()
    home, project, _ = _inputs(tmp_path)
    payload = {"result": "SUBSCRIPTION_OK", **failure_fields}

    result = preflight.run_live_probe(
        "claude-code",
        environ={"VIBEMIND_CLAUDE_MODEL": "claude-model"},
        runner=lambda *args, **kwargs: _Completed(0, stdout=json.dumps(payload)),
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert result.exit_code == 2
    assert result.status == "failed"
    assert "raw" not in repr(result)


@pytest.mark.parametrize("payload", ["[]", "null", '"text"', "42"])
def test_live_opencode_probe_rejects_non_object_json_without_raw_output(
    tmp_path: Path,
    payload: str,
) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    runtime.mkdir(parents=True)
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal calls
        calls += 1
        return _Completed(0, stdout=payload)

    result = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert calls == 1
    assert result.exit_code == 2
    assert result.status == "failed"
    assert payload not in repr(result)


@pytest.mark.parametrize(
    ("scenario", "expected_exit", "expected_status"),
    [
        ("success", 0, "success"),
        ("failure", 13, "failed"),
        ("timeout", 124, "failed"),
        ("exception", 2, "failed"),
    ],
)
def test_live_opencode_probe_uses_clean_child_runtime_and_cleans_all_temp_state(
    tmp_path: Path,
    scenario: str,
    expected_exit: int,
    expected_status: str,
) -> None:
    preflight = _load_preflight()
    home, project, runtime_parent = _inputs(tmp_path)
    runtime_parent.mkdir(parents=True)
    (runtime_parent / "instructions.txt").write_text("unrelated", encoding="utf-8")
    (runtime_parent / "config.json").write_text("unrelated", encoding="utf-8")
    observed: dict[str, Path] = {}

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        runtime_child = Path(kwargs["cwd"])
        fixture = Path(args[0][args[0].index("--dir") + 1])
        observed["runtime_child"] = runtime_child
        observed["fixture"] = fixture
        assert runtime_child.parent == runtime_parent.resolve()
        assert runtime_child != project.resolve()
        assert list(runtime_child.iterdir()) == []
        assert not (runtime_child / ".env").exists()
        assert [path.name for path in fixture.iterdir()] == [".env"]
        if scenario == "success":
            return _Completed(0, stdout='{"type":"text","part":{"text":"SUBSCRIPTION_OK"}}')
        if scenario == "failure":
            return _Completed(13, stdout="raw child failure", stderr="raw child error")
        if scenario == "timeout":
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="raw timeout")
        raise RuntimeError("raw runner exception")

    result = preflight.run_live_probe(
        "opencode",
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime_parent),
        },
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert result.exit_code == expected_exit
    assert result.status == expected_status
    assert not observed["runtime_child"].exists()
    assert not observed["fixture"].exists()
    assert "raw" not in repr(result)


def test_cli_requires_live_flag_before_it_can_execute_a_probe(tmp_path: Path) -> None:
    preflight = _load_preflight()
    home, project, runtime = _inputs(tmp_path)
    calls = 0

    def runner(*args: Any, **kwargs: Any) -> _Completed:
        nonlocal calls
        calls += 1
        return _Completed(0, stdout='{"type":"text","part":{"text":"SUBSCRIPTION_OK"}}')

    output = io.StringIO()
    exit_code = preflight.main(
        ["--backend", "opencode"],
        environ={
            "VIBEMIND_OPENCODE_MODEL": "openai-model",
            "VIBEMIND_CLAUDE_MODEL": "claude-model",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        stdout=output,
        runner=runner,
        resolver=_native,
        project_cwd=project,
        current_user_home=home,
    )

    assert exit_code == 0
    assert calls == 0
    assert "openai-model" not in output.getvalue()
