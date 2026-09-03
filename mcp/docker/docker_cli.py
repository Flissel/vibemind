"""Subprocess foundation for the Docker-CLI MCP server.

This is the ONLY module that runs subprocesses. It never uses shell=True;
arguments are passed as an array to avoid command injection.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Optional

DEFAULT_TIMEOUT = 30  # seconds — guards against a hung docker call (WSL mirrored hang)


def _parse(stdout: str, parse: Optional[str]) -> Optional[Any]:
    if not parse or not stdout.strip():
        return None
    try:
        if parse == "json":
            return json.loads(stdout)
        if parse == "ndjson":
            return [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except (json.JSONDecodeError, ValueError):
        return None
    return None


def run(
    args: list[str],
    *,
    base: str = "docker",
    timeout: int = DEFAULT_TIMEOUT,
    parse: Optional[str] = None,
) -> dict:
    """Run a docker CLI command. Returns the uniform result dict.

    parse: None | "json" (single array) | "ndjson" (one object per line).
    base: the docker binary, always "docker". Subcommand groups like
          "compose" / "stack" / "service" are passed as the FIRST element(s)
          of `args`, NEVER as `base` (a multi-word base would fail to exec).
    """
    cmd = [base, *args]
    command_str = " ".join(cmd)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "command": command_str,
            "data": None,
            "stdout": "",
            "stderr": f"command timed out after {timeout}s",
            "exit_code": None,
            "daemon_unreachable": False,
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "command": command_str,
            "data": None,
            "stdout": "",
            "stderr": "docker CLI not found on PATH",
            "exit_code": None,
            "daemon_unreachable": False,
        }
    except OSError as exc:
        return {
            "ok": False,
            "command": command_str,
            "data": None,
            "stdout": "",
            "stderr": f"failed to run docker: {exc}",
            "exit_code": None,
            "daemon_unreachable": False,
        }

    ok = completed.returncode == 0
    stderr = completed.stderr or ""
    daemon_unreachable = "Cannot connect to the Docker daemon" in stderr
    return {
        "ok": ok,
        "command": command_str,
        "data": _parse(completed.stdout, parse) if ok else None,
        "stdout": completed.stdout,
        "stderr": stderr,
        "exit_code": completed.returncode,
        "daemon_unreachable": daemon_unreachable,
    }
