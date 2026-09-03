"""Redacted static readiness and opt-in probes for subscription CLIs."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import TextIO

from coding_subscription_driver import Backend, DriverRequest, build_invocation
from subscription_wrapper_runtime import (
    ExecutableResolver,
    ProcessRunner,
    _resolve_executable,
    execute_invocation,
)


DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120
PROBE_PROMPT = "Reply exactly SUBSCRIPTION_OK"


@dataclass(frozen=True)
class BackendReadiness:
    """Safe summary that deliberately excludes environment values and paths."""

    ready: bool
    reason: str | None
    auth_status: str


@dataclass(frozen=True)
class LiveProbeResult:
    """Redacted terminal result for one explicitly selected backend."""

    backend: str
    exit_code: int
    status: str
    duration_seconds: float


def inspect_environment(
    env: Mapping[str, str],
    *,
    resolver: ExecutableResolver = shutil.which,
    runner: ProcessRunner | None = None,
    project_cwd: Path | None = None,
    current_user_home: Path | None = None,
) -> dict[str, BackendReadiness]:
    """Inspect configuration only; this never invokes a CLI or reads auth state."""
    del runner
    project = (project_cwd or Path.cwd()).resolve()
    home = (current_user_home or Path.home()).resolve()
    return {
        "openai": _readiness_for_opencode(env, resolver, project, home),
        "anthropic": _readiness_for_claude(env, resolver),
    }


def inspect_cli_auth_status(
    backend: str,
    *,
    runner: ProcessRunner = subprocess.run,
    resolver: ExecutableResolver = shutil.which,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    """Return only an opaque local auth state, without exposing process output."""
    command = _auth_status_command(backend)
    if command is None or not _valid_timeout(timeout_seconds):
        return "unknown"
    executable = _resolve_executable(command[0], path=None, resolver=resolver)
    if executable is None:
        return "unknown"
    try:
        completed = runner(
            (str(executable), *command[1:]),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode == 0:
        return "authenticated"
    if completed.returncode == 1:
        return "not-authenticated"
    return "unknown"


def run_live_probe(
    backend: str,
    *,
    environ: Mapping[str, str],
    runner: ProcessRunner = subprocess.run,
    resolver: ExecutableResolver = shutil.which,
    project_cwd: Path | None = None,
    current_user_home: Path | None = None,
) -> LiveProbeResult:
    """Run one bounded, explicit probe. Callers must opt in through ``--live``."""
    started = time.monotonic()
    selected = _parse_backend(backend)
    if selected is None:
        return _failed(str(backend), 2, started)

    project = (project_cwd or Path.cwd()).resolve()
    home = (current_user_home or Path.home()).resolve()
    timeout = _timeout_seconds(environ)
    if timeout is None:
        return _failed(selected.value, 2, started)

    try:
        if selected is Backend.OPENCODE:
            runtime = _runtime_directory(environ, project, home)
            if isinstance(runtime, str):
                return _failed(selected.value, 2, started)
            runtime.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="vibemind-opencode-probe-") as fixture:
                fixture_path = Path(fixture)
                (fixture_path / ".env").write_text(
                    "OPENAI_API_KEY=invalid-do-not-bill\n", encoding="utf-8"
                )
                with tempfile.TemporaryDirectory(
                    dir=runtime,
                    prefix="vibemind-opencode-runtime-",
                ) as clean_runtime:
                    request = DriverRequest(
                        backend=selected,
                        prompt=PROBE_PROMPT,
                        cwd=str(fixture_path),
                        runtime_cwd=clean_runtime,
                        model=_required_model(environ, "VIBEMIND_OPENCODE_MODEL"),
                        timeout_seconds=timeout,
                    )
                    outcome = execute_invocation(
                        build_invocation(request, environ),
                        timeout_seconds=timeout,
                        resolver=resolver,
                        runner=runner,
                    )
        else:
            request = DriverRequest(
                backend=selected,
                prompt=PROBE_PROMPT,
                cwd=str(project),
                runtime_cwd=str(project),
                model=_required_model(environ, "VIBEMIND_CLAUDE_MODEL"),
                timeout_seconds=timeout,
            )
            outcome = execute_invocation(
                build_invocation(request, environ),
                timeout_seconds=timeout,
                resolver=resolver,
                runner=runner,
            )
    except Exception:
        return _failed(selected.value, 2, started)

    if outcome.exit_code:
        return _failed(selected.value, outcome.exit_code, started)
    if _normalized_probe_output(selected, outcome.stdout) != "SUBSCRIPTION_OK":
        return _failed(selected.value, 2, started)
    return LiveProbeResult(
        backend=selected.value,
        exit_code=0,
        status="success",
        duration_seconds=_duration(started),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    runner: ProcessRunner = subprocess.run,
    resolver: ExecutableResolver = shutil.which,
    project_cwd: Path | None = None,
    current_user_home: Path | None = None,
) -> int:
    """Print redacted static readiness unless ``--live`` is explicitly selected."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--backend", choices=(Backend.OPENCODE.value, Backend.CLAUDE_CODE.value))
    args = parser.parse_args(argv)
    environment = os.environ if environ is None else environ
    output = sys.stdout if stdout is None else stdout
    error = sys.stderr if stderr is None else stderr

    if not args.live:
        report = inspect_environment(
            environment,
            resolver=resolver,
            runner=runner,
            project_cwd=project_cwd,
            current_user_home=current_user_home,
        )
        output.write(json.dumps({name: asdict(item) for name, item in report.items()}) + "\n")
        return 0
    if args.backend is None:
        error.write("--backend is required with --live\n")
        return 2

    result = run_live_probe(
        args.backend,
        environ=environment,
        runner=runner,
        resolver=resolver,
        project_cwd=project_cwd,
        current_user_home=current_user_home,
    )
    output.write(json.dumps(asdict(result)) + "\n")
    return result.exit_code


def _readiness_for_opencode(
    env: Mapping[str, str],
    resolver: ExecutableResolver,
    project: Path,
    home: Path,
) -> BackendReadiness:
    if _has_key(env, "OPENAI_API_KEY"):
        return _blocked("OPENAI_API_KEY shadows subscription auth")
    if not _has_nonblank_value(env, "VIBEMIND_OPENCODE_MODEL"):
        return _blocked("VIBEMIND_OPENCODE_MODEL must be set")
    if not _has_native_executable("opencode", env, resolver):
        return _blocked("OpenCode native executable unavailable")
    runtime = _runtime_directory(env, project, home)
    if isinstance(runtime, str):
        return _blocked(runtime)
    return BackendReadiness(True, None, "unknown")


def _readiness_for_claude(
    env: Mapping[str, str], resolver: ExecutableResolver
) -> BackendReadiness:
    if any(
        _has_key(env, key)
        for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    ):
        return _blocked("Anthropic PAYG environment shadows subscription auth")
    if not _has_nonblank_value(env, "VIBEMIND_CLAUDE_MODEL"):
        return _blocked("VIBEMIND_CLAUDE_MODEL must be set")
    if not _has_native_executable("claude", env, resolver):
        return _blocked("Claude Code native executable unavailable")
    return BackendReadiness(True, None, "unknown")


def _runtime_directory(env: Mapping[str, str], project: Path, home: Path) -> Path | str:
    configured = env.get("VIBEMIND_OPENCODE_RUNTIME_CWD", "").strip()
    candidate = Path(configured) if configured else home / ".vibemind" / "subscription-runtime" / "opencode"
    if configured and not candidate.is_absolute():
        return "OpenCode runtime directory must be absolute"
    try:
        runtime = candidate.resolve()
    except OSError:
        return "OpenCode runtime directory unavailable"
    if not _is_under(runtime, home):
        return "OpenCode runtime directory must be under current user home"
    if _paths_overlap(runtime, project):
        return "OpenCode runtime directory must not overlap project directory"
    if (runtime / ".env").exists():
        return "OpenCode runtime directory must not contain .env"
    return runtime


def _has_native_executable(
    command: str, env: Mapping[str, str], resolver: ExecutableResolver
) -> bool:
    return bool(_resolve_executable(command, path=env.get("PATH"), resolver=resolver))


def _auth_status_command(backend: str) -> tuple[str, ...] | None:
    selected = _parse_backend(backend)
    if selected is Backend.OPENCODE:
        return ("opencode", "auth", "list")
    if selected is Backend.CLAUDE_CODE:
        return ("claude", "auth", "status")
    return None


def _normalized_probe_output(backend: Backend, output: str) -> str | None:
    if backend is Backend.CLAUDE_CODE:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict) or _is_protocol_error(payload):
            return None
        result = payload.get("result")
        return result.strip() if isinstance(result, str) else None

    text: list[str] = []
    for line in output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        if _is_protocol_error(payload):
            return None
        part = payload.get("part")
        if payload.get("type") == "text" and isinstance(part, dict):
            value = part.get("text")
            if isinstance(value, str):
                text.append(value)
    return "".join(text).strip() if text else None


def _is_protocol_error(payload: dict[str, object]) -> bool:
    if payload.get("is_error") is True or payload.get("type") == "error" or "error" in payload:
        return True
    return any(_is_failing_indicator(payload.get(key)) for key in ("code", "status"))


def _is_failing_indicator(value: object) -> bool:
    if isinstance(value, int) and not isinstance(value, bool):
        return value >= 400
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized.isdigit():
            return int(normalized) >= 400
        return any(marker in normalized for marker in ("error", "fail", "unauthorized", "forbidden"))
    return False


def _required_model(env: Mapping[str, str], key: str) -> str:
    model = env.get(key, "").strip()
    if not model:
        raise ValueError("subscription model is required")
    return model


def _timeout_seconds(env: Mapping[str, str]) -> int | None:
    raw = env.get("VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        timeout = int(raw)
    except ValueError:
        return None
    return timeout if _valid_timeout(timeout) else None


def _valid_timeout(timeout_seconds: int) -> bool:
    return 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS


def _parse_backend(backend: str) -> Backend | None:
    try:
        return Backend(backend)
    except ValueError:
        return None


def _has_key(env: Mapping[str, str], key: str) -> bool:
    target = key.casefold()
    return any(candidate.casefold() == target for candidate in env)


def _has_nonblank_value(env: Mapping[str, str], key: str) -> bool:
    value = next((value for candidate, value in env.items() if candidate == key), "")
    return bool(value.strip())


def _blocked(reason: str) -> BackendReadiness:
    return BackendReadiness(False, reason, "unknown")


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_under(first, second) or _is_under(second, first)


def _failed(backend: str, exit_code: int, started: float) -> LiveProbeResult:
    return LiveProbeResult(backend, exit_code, "failed", _duration(started))


def _duration(started: float) -> float:
    return round(max(0.0, time.monotonic() - started), 6)


if __name__ == "__main__":
    raise SystemExit(main())
