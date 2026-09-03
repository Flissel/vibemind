"""Scope guards for the coding-subscription lanes.

History: this file used to assert that the salvage was OpenCode-only - that
`Backend` had exactly one member, that the preflight reported exactly one lane,
and that no Claude subscription wrapper existed. That was the Codex line's
deliberately narrow salvage boundary.

The 2026-07-14 superproject fork was reconciled on 2026-08-25. The operational
line, where the Claude lane was actually built and is still being worked on,
carries both backends, so the OpenCode-only assertions no longer describe the
repository. They are replaced here by guards on the boundary that still matters:
both lanes are declared, and the Claude lane may never receive a system prompt
through argv.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from coding_subscription_driver import Backend, DriverRequest, build_invocation  # noqa: E402
from coding_subscription_preflight import inspect_environment, run_live_probe  # noqa: E402


def test_subscription_driver_exposes_both_reconciled_backends() -> None:
    assert tuple(Backend) == (Backend.OPENCODE, Backend.CLAUDE_CODE)


def test_static_preflight_reports_both_lanes(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    report = inspect_environment(
        {
            "VIBEMIND_OPENCODE_MODEL": "openai/gpt-5",
            "VIBEMIND_OPENCODE_RUNTIME_CWD": str(runtime),
        },
        resolver=lambda command, path=None: "C:/bin/opencode.exe"
        if command == "opencode"
        else None,
        project_cwd=tmp_path / "project",
        current_user_home=tmp_path,
    )

    assert tuple(report) == ("openai", "anthropic")
    assert report["openai"].ready is True
    # Only the OpenCode binary is resolvable in this fixture, so the Anthropic
    # lane must report not-ready rather than claiming a runnable path.
    assert report["anthropic"].ready is False


def test_unknown_backend_live_probe_fails_before_process_execution(tmp_path: Path) -> None:
    calls = 0

    def runner(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("unsupported backend reached process execution")

    result = run_live_probe(
        "not-a-backend",
        environ={},
        runner=runner,
        project_cwd=tmp_path / "project",
        current_user_home=tmp_path,
    )

    assert result.exit_code == 2
    assert result.status == "failed"
    assert calls == 0


def test_claude_lane_never_puts_a_system_prompt_in_argv(tmp_path: Path) -> None:
    """A prompt in argv is readable from any process listing on the host.

    The driver must take a file path instead, and fail closed when handed a raw
    prompt with no protected file to read it from.
    """
    request = DriverRequest(
        backend=Backend.CLAUDE_CODE,
        prompt="do the thing",
        cwd=str(tmp_path),
        runtime_cwd=str(tmp_path),
        model="sonnet",
        timeout_seconds=60,
        system_prompt="SECRET SYSTEM PROMPT",
    )

    try:
        invocation = build_invocation(request, {})
    except ValueError as exc:
        assert "protected file" in str(exc)
    else:  # pragma: no cover - only reached if the guard regresses
        assert "--system-prompt" not in invocation.argv
        assert "SECRET SYSTEM PROMPT" not in " ".join(invocation.argv)
