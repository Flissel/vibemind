"""Shared, shell-free runtime for subscription CLI wrappers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from coding_subscription_driver import Invocation


STRONG_AUTH_DIAGNOSTIC = re.compile(
    r"\bHTTP\s+401\s+Unauthorized\b|\bHTTP\s+403\s+Forbidden\b|"
    r"\b(?:error|request failed)\s*[:\-]?\s*(?:unauthori[sz]ed|forbidden)\b|"
    r"\binvalid\s+(?:api\s+key|credentials)\b|"
    r"\b(?:login|sign[ -]?in)\s+required\b|"
    r"\bauthentication\s+(?:failed|required)\b|\bnot\s+logged\s+in\b|"
    r"\boauth\s+token\s+revoked\b(?=[\s\S]*/login\b)|"
    r"\bsession\s+expired\b(?=[\s\S]*/login\b)",
    re.IGNORECASE,
)
STRUCTURED_AUTH_DIAGNOSTIC = re.compile(
    STRONG_AUTH_DIAGNOSTIC.pattern + r"|\b(?:401|403)\b|\bunauthori[sz]ed\b|\bforbidden\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeOutcome:
    """Redacted result of launching a subscription CLI."""

    exit_code: int
    stdout: str
    diagnostic: str | None


ExecutableResolver = Callable[..., str | None]
ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def execute_invocation(
    invocation: Invocation,
    *,
    timeout_seconds: int,
    resolver: ExecutableResolver = shutil.which,
    runner: ProcessRunner = subprocess.run,
) -> RuntimeOutcome:
    """Resolve and execute an invocation without forwarding failed child output."""
    executable = _resolve_executable(
        invocation.argv[0],
        path=invocation.env.get("PATH"),
        resolver=resolver,
    )
    if not executable:
        return RuntimeOutcome(2, "", "subscription configuration failed")

    argv = (str(executable), *invocation.argv[1:])
    try:
        completed = runner(
            argv,
            cwd=invocation.cwd,
            env=invocation.env,
            input=invocation.stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return RuntimeOutcome(124, "", "subscription command timed out")
    except OSError:
        return RuntimeOutcome(2, "", "subscription configuration failed")

    if completed.returncode:
        if _is_auth_failure(completed.stdout, completed.stderr):
            return RuntimeOutcome(2, "", "subscription authentication failed")
        return RuntimeOutcome(completed.returncode, "", "subscription command failed")
    return RuntimeOutcome(0, completed.stdout, completed.stderr or None)


def _is_auth_failure(stdout: str, stderr: str) -> bool:
    if STRONG_AUTH_DIAGNOSTIC.search(stderr):
        return True
    return bool(STRUCTURED_AUTH_DIAGNOSTIC.search(_structured_error_details(stdout)))


def _resolve_executable(
    command: str,
    *,
    path: str | None,
    resolver: ExecutableResolver,
) -> str | None:
    candidate = resolver(command, path=path)
    if os.name != "nt":
        return candidate
    if _is_native_windows_executable(candidate):
        return candidate
    native_command = f"{Path(command).stem}.exe"
    native_candidate = resolver(native_command, path=path)
    return native_candidate if _is_native_windows_executable(native_candidate) else None


def _is_native_windows_executable(candidate: str | None) -> bool:
    return bool(candidate and Path(candidate).suffix.casefold() in {".exe", ".com"})


def _structured_error_details(stdout: str) -> str:
    details: list[str] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if not _has_structured_failure_marker(payload):
            continue
        if "error" in payload:
            details.append(_json_text(payload["error"]))
        if payload.get("type") == "error":
            details.append(json.dumps(payload, ensure_ascii=False))
        for key in ("code", "status", "errors"):
            if key in payload:
                details.append(_json_text(payload[key]))
    return "\n".join(details)


def _json_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _has_structured_failure_marker(payload: dict[str, object]) -> bool:
    if payload.get("is_error") is True or payload.get("type") == "error" or "error" in payload:
        return True
    return any(_is_failing_code_or_status(payload.get(key)) for key in ("code", "status"))


def _is_failing_code_or_status(value: object) -> bool:
    if isinstance(value, int):
        return value >= 400
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized.isdigit():
            return int(normalized) >= 400
        return "error" in normalized or "fail" in normalized
    return False
