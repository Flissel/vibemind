"""OpenFang CLI wrapper for the OpenCode subscription backend."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence, TextIO

from coding_subscription_driver import Backend, DriverRequest, build_invocation
from project_resolver import resolve as resolve_project
from subscription_wrapper_runtime import ExecutableResolver, ProcessRunner, execute_invocation


DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 600
DEFAULT_PROJECT_CWD = Path(__file__).resolve().parent.parent
_EXPECTED_DRIVER_MODEL = "sonnet"


def make_request(
    prompt: str,
    *,
    system_prompt_file: Path | None = None,
    system_prompt: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> DriverRequest:
    """Build an OpenCode request without selecting a provider or credentials."""
    environment = os.environ if environ is None else environ
    model = environment.get("VIBEMIND_OPENCODE_MODEL", "").strip()
    if not model:
        raise ValueError("VIBEMIND_OPENCODE_MODEL must be set")

    project_cwd = _resolve_project_cwd(prompt, environment)
    runtime_cwd = _runtime_cwd(project_cwd, environment)
    return DriverRequest(
        backend=Backend.OPENCODE,
        prompt=prompt,
        cwd=str(project_cwd),
        runtime_cwd=str(runtime_cwd),
        model=model,
        timeout_seconds=_timeout_seconds(environment),
        system_prompt_file=str(system_prompt_file) if system_prompt_file is not None else None,
        system_prompt=system_prompt,
    )


def main(
    *,
    argv: Sequence[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    environ: Mapping[str, str] | None = None,
    runner: ProcessRunner = subprocess.run,
    resolver: ExecutableResolver = shutil.which,
) -> int:
    """Execute OpenCode with a bounded, shell-free subscription invocation."""
    input_stream = sys.stdin if stdin is None else stdin
    output_stream = sys.stdout if stdout is None else stdout
    error_stream = sys.stderr if stderr is None else stderr
    environment = os.environ if environ is None else environ
    try:
        system_prompt_file, system_prompt = _parse_openfang_driver_argv(argv)
        prompt = input_stream.read()
        request = make_request(
            prompt,
            system_prompt_file=system_prompt_file,
            system_prompt=system_prompt,
            environ=environment,
        )
        invocation = build_invocation(request, environment)
    except ValueError as error:
        print(f"configuration error: {error}", file=error_stream)
        return 2

    outcome = execute_invocation(
        invocation,
        timeout_seconds=request.timeout_seconds,
        resolver=resolver,
        runner=runner,
    )
    if outcome.exit_code:
        print(outcome.diagnostic or "subscription command failed", file=error_stream)
        return outcome.exit_code

    result = _normalize_result(outcome.stdout)
    if result is None or _contains_system_context(result, system_prompt_file, system_prompt):
        print("subscription response invalid", file=error_stream)
        return 2
    if result:
        output_stream.write(result if result.endswith("\n") else f"{result}\n")
    if outcome.diagnostic:
        error_stream.write(_safe_diagnostic(outcome.diagnostic, system_prompt_file, system_prompt))
    return 0


def _parse_openfang_driver_argv(argv: Sequence[str] | None) -> tuple[Path | None, str | None]:
    if argv is None:
        raise ValueError("OpenFang driver arguments are invalid")
    values = list(argv)
    index = 0
    seen: set[str] = set()
    system_prompt_file: Path | None = None
    model: str | None = None
    while index < len(values):
        flag = values[index]
        if flag in {"-p", "--verbose", "--dangerously-skip-permissions"}:
            if flag in seen:
                raise ValueError("OpenFang driver arguments are invalid")
            seen.add(flag)
            index += 1
            continue
        if flag not in {"--input-format", "--output-format", "--system-prompt-file", "--model"}:
            raise ValueError("OpenFang driver arguments are invalid")
        if flag in seen or index + 1 >= len(values):
            raise ValueError("OpenFang driver arguments are invalid")
        value = values[index + 1]
        seen.add(flag)
        if flag == "--input-format" and value != "text":
            raise ValueError("OpenFang driver arguments are invalid")
        if flag == "--output-format" and value != "stream-json":
            raise ValueError("OpenFang driver arguments are invalid")
        if flag == "--system-prompt-file":
            system_prompt_file, system_prompt = _read_system_prompt_file(value)
        if flag == "--model":
            model = value
        index += 2
    if not {"-p", "--input-format", "--output-format", "--verbose", "--system-prompt-file", "--model"}.issubset(seen):
        raise ValueError("OpenFang driver arguments are invalid")
    if model != _EXPECTED_DRIVER_MODEL:
        raise ValueError("OpenFang driver arguments are invalid")
    return system_prompt_file, system_prompt


def _read_system_prompt_file(raw_path: str) -> tuple[Path, str]:
    path = Path(raw_path)
    try:
        if not path.is_absolute() or not path.is_file():
            raise ValueError
        prompt = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("OpenFang system prompt file is invalid") from error
    if not prompt:
        raise ValueError("OpenFang system prompt file is invalid")
    return path.resolve(), prompt


def _safe_diagnostic(diagnostic: str, system_prompt_file: Path | None, system_prompt: str | None) -> str:
    redacted = diagnostic
    if system_prompt:
        redacted = redacted.replace(system_prompt, "[redacted system prompt]")
    if system_prompt_file is not None:
        redacted = redacted.replace(str(system_prompt_file), "[redacted system prompt file]")
    return redacted


def _contains_system_context(text: str, system_prompt_file: Path | None, system_prompt: str | None) -> bool:
    return bool(
        (system_prompt and system_prompt in text)
        or (system_prompt_file is not None and str(system_prompt_file) in text)
    )


def _resolve_project_cwd(prompt: str, environ: Mapping[str, str]) -> Path:
    resolved = resolve_project(prompt)
    if resolved and isinstance(resolved.get("code_path"), str):
        candidate = Path(resolved["code_path"])
        if candidate.is_dir():
            return candidate.resolve()
    configured = environ.get("VIBEMIND_PROJECT_CWD", "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_dir():
            return candidate.resolve()
        raise ValueError("VIBEMIND_PROJECT_CWD must name an existing directory")
    return DEFAULT_PROJECT_CWD.resolve()


def _runtime_cwd(project_cwd: Path, environ: Mapping[str, str]) -> Path:
    current_user_home = Path.home().resolve()
    configured = environ.get("VIBEMIND_OPENCODE_RUNTIME_CWD", "").strip()
    if configured:
        runtime_cwd = Path(configured)
        if not runtime_cwd.is_absolute() or not runtime_cwd.is_dir():
            raise ValueError("VIBEMIND_OPENCODE_RUNTIME_CWD must name an existing absolute directory")
    else:
        runtime_cwd = current_user_home / ".vibemind" / "subscription-runtime" / "opencode"
        runtime_cwd.mkdir(parents=True, exist_ok=True)
    runtime_cwd = runtime_cwd.resolve()
    try:
        runtime_cwd.relative_to(current_user_home)
    except ValueError:
        raise ValueError("OpenCode runtime directory must be under current user home") from None
    if _paths_overlap(runtime_cwd, project_cwd.resolve()):
        raise ValueError("OpenCode runtime directory must not overlap the project directory")
    return runtime_cwd


def _timeout_seconds(environ: Mapping[str, str]) -> int:
    raw_timeout = environ.get("VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        timeout = int(raw_timeout)
    except ValueError as error:
        raise ValueError("VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS must be an integer") from error
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"VIBEMIND_SUBSCRIPTION_TIMEOUT_SECONDS must be 1-{MAX_TIMEOUT_SECONDS}")
    return timeout


def _normalize_result(output: str) -> str | None:
    lines = [line for line in output.splitlines() if line.strip()]
    if not lines:
        return None
    payloads: list[dict[str, object]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        payloads.append(payload)

    text_parts: list[str] = []
    for payload in payloads:
        if _is_error_payload(payload):
            return None
        if payload.get("type") != "text":
            continue
        part = payload.get("part")
        if not isinstance(part, dict) or not isinstance(part.get("text"), str):
            return None
        text_parts.append(part["text"])
    return "".join(text_parts) if text_parts else None


def _is_error_payload(payload: dict[str, object]) -> bool:
    if payload.get("type") == "error" or "error" in payload:
        return True
    return any(_indicates_failure(payload.get(key)) for key in ("code", "status") if key in payload)


def _indicates_failure(value: object) -> bool:
    if isinstance(value, int):
        return value >= 400
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized.isdigit():
            return int(normalized) >= 400
        return any(marker in normalized for marker in ("error", "fail", "unauthorized", "forbidden"))
    return False


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        try:
            second.relative_to(first)
            return True
        except ValueError:
            return False


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv[1:]))
