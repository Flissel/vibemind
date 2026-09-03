# Docker-CLI-MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python stdio MCP server in `mcp/docker/` that exposes the Docker CLI as ~40 explicitly-named tools (read-only run free, state-changing tools gated by approval).

**Architecture:** A thin `docker_cli.py` module is the ONLY place subprocesses run — it builds an argument array (never `shell=True`), runs `docker` with a timeout, and returns a uniform result dict (`ok/command/data/stdout/stderr/exit_code`). `server.py` is a thin FastMCP layer: each `@mcp.tool` only maps parameters to an arg list and delegates to `docker_cli.run(...)`. Write tools route through `approval.py` first. CLI-only — no `docker-py` SDK.

**Tech Stack:** Python 3.11, official `mcp` SDK (already installed — `from mcp.server.fastmcp import FastMCP`), `subprocess` (stdlib), pytest 7.4.3. No new pip dependencies.

---

## Environment Notes (verified 2026-06-04)

- `fastmcp` standalone package is **NOT** installed, but the official `mcp` SDK **is**, and ships `mcp.server.fastmcp.FastMCP`. Use that import. No `pip install` needed.
- `docker ps -a --format '{{json .}}'` → one JSON object **per line** (NDJSON). Same for `images`, `network ls`, `volume ls`, `service ls`, `stack ls` (where supported).
- `docker inspect` / `image inspect` / `service inspect` → a single JSON **array** (parse with `json.loads` directly).
- Swarm is active. Live stacks: `vibemind` (21 services), `unity-ai` (5). Smoke tests MUST be read-only.
- Recycle from `vibemind-os/spaces/coding/Coding_engine/mcp_plugins/servers/docker/agent.py`: the `_run_docker_cmd` shape and the UTF-8 console fix. Do **NOT** copy `shell=True` — that file's `" ".join(cmd)` is command-injection-prone.

## File Structure

```
mcp/docker/
├── README.md                  # purpose, tool list, stdio + OpenFang-bridge setup
├── pyproject.toml             # metadata + console entry-point (no runtime deps beyond mcp)
├── docker_cli.py              # run(args, timeout, parse) subprocess foundation + result shape
├── approval.py                # approval gate for write tools
├── server.py                  # FastMCP instance + all ~40 @mcp.tool definitions
└── tests/
    ├── __init__.py
    ├── test_docker_cli.py     # mocks subprocess; result shape + 3 error classes + json parsing
    └── test_approval.py       # approval allow/deny behavior
```

Responsibilities are split so each file holds one concern: subprocess+parsing (`docker_cli.py`), gating (`approval.py`), tool surface (`server.py`). Tests mock `subprocess.run` so no real Docker is needed for unit tests.

---

## Task 1: Package scaffold

**Files:**
- Create: `mcp/docker/pyproject.toml`
- Create: `mcp/docker/tests/__init__.py`
- Create: `mcp/docker/__init__.py`

- [ ] **Step 1: Create the package `__init__.py`**

Create `mcp/docker/__init__.py`:

```python
"""Docker-CLI MCP server: exposes the Docker CLI as explicit MCP tools."""

__version__ = "0.1.0"
```

- [ ] **Step 2: Create the tests package marker**

Create `mcp/docker/tests/__init__.py` (empty file):

```python
```

- [ ] **Step 3: Create `pyproject.toml`**

Create `mcp/docker/pyproject.toml`:

```toml
[project]
name = "vibemind-mcp-docker"
version = "0.1.0"
description = "Docker-CLI MCP server (stdio) — exposes docker as explicit MCP tools"
requires-python = ">=3.11"
dependencies = ["mcp"]

[project.scripts]
vibemind-mcp-docker = "mcp.docker.server:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Verify the package imports**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1" && python -c "import importlib.util, sys; sys.path.insert(0,'mcp'); import docker as d; print(d.__version__)"`

Expected: prints `0.1.0` (note: run from a path where `mcp/docker` resolves; the real entry-point is exercised in Task 6).

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/__init__.py mcp/docker/tests/__init__.py mcp/docker/pyproject.toml
git commit -m "feat(mcp-docker): package scaffold"
```

---

## Task 2: `docker_cli.run` — happy path + JSON parsing

**Files:**
- Create: `mcp/docker/docker_cli.py`
- Test: `mcp/docker/tests/test_docker_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_docker_cli.py`:

```python
import subprocess
from unittest import mock

from docker import docker_cli


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_success_no_parse_returns_stdout():
    with mock.patch("subprocess.run", return_value=_completed(stdout="hello\n")):
        result = docker_cli.run(["version"])
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "hello\n"
    assert result["data"] is None
    assert result["command"] == "docker version"


def test_run_parses_ndjson_lines():
    out = '{"ID":"a"}\n{"ID":"b"}\n'
    with mock.patch("subprocess.run", return_value=_completed(stdout=out)):
        result = docker_cli.run(["ps"], parse="ndjson")
    assert result["ok"] is True
    assert result["data"] == [{"ID": "a"}, {"ID": "b"}]


def test_run_parses_json_array():
    out = '[{"Id":"x"}]'
    with mock.patch("subprocess.run", return_value=_completed(stdout=out)):
        result = docker_cli.run(["inspect", "x"], parse="json")
    assert result["data"] == [{"Id": "x"}]


def test_run_bad_json_keeps_stdout_data_none():
    with mock.patch("subprocess.run", return_value=_completed(stdout="not json")):
        result = docker_cli.run(["ps"], parse="ndjson")
    assert result["ok"] is True
    assert result["data"] is None
    assert result["stdout"] == "not json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_docker_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docker.docker_cli'`

- [ ] **Step 3: Write minimal implementation**

Create `mcp/docker/docker_cli.py`:

```python
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
    base: "docker" or "docker compose" / "docker stack" prefixes are passed as
          the first element(s) of args by callers; `base` stays "docker".
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
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "command": command_str,
            "data": None,
            "stdout": "",
            "stderr": "docker CLI not found on PATH",
            "exit_code": None,
        }

    ok = completed.returncode == 0
    return {
        "ok": ok,
        "command": command_str,
        "data": _parse(completed.stdout, parse) if ok else None,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_docker_cli.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/docker_cli.py mcp/docker/tests/test_docker_cli.py
git commit -m "feat(mcp-docker): docker_cli.run with json/ndjson parsing"
```

---

## Task 3: `docker_cli.run` — error classes (timeout, not-found, non-zero, daemon)

**Files:**
- Modify: `mcp/docker/docker_cli.py` (add a daemon-unreachable hint)
- Test: `mcp/docker/tests/test_docker_cli.py` (append)

- [ ] **Step 1: Write the failing tests (append to the test file)**

Append to `mcp/docker/tests/test_docker_cli.py`:

```python
def test_run_timeout_returns_ok_false():
    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=30)):
        result = docker_cli.run(["ps"], timeout=30)
    assert result["ok"] is False
    assert "timed out" in result["stderr"]
    assert result["exit_code"] is None


def test_run_docker_not_found():
    with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
        result = docker_cli.run(["ps"])
    assert result["ok"] is False
    assert "not found" in result["stderr"]


def test_run_nonzero_exit_passes_stderr():
    with mock.patch("subprocess.run", return_value=_completed(stderr="No such container: x", returncode=1)):
        result = docker_cli.run(["inspect", "x"])
    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert "No such container" in result["stderr"]


def test_run_daemon_unreachable_hint():
    err = "Cannot connect to the Docker daemon at npipe:////./pipe/docker_engine."
    with mock.patch("subprocess.run", return_value=_completed(stderr=err, returncode=1)):
        result = docker_cli.run(["ps"])
    assert result["ok"] is False
    assert result["daemon_unreachable"] is True
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_docker_cli.py -v`
Expected: `test_run_daemon_unreachable_hint` FAILS with `KeyError: 'daemon_unreachable'` (the other three already pass from Task 2).

- [ ] **Step 3: Add the daemon-unreachable flag**

In `mcp/docker/docker_cli.py`, replace the final `return {...}` block of `run()` with:

```python
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
```

Also add `"daemon_unreachable": False,` to the TimeoutExpired and FileNotFoundError return dicts.

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_docker_cli.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/docker_cli.py mcp/docker/tests/test_docker_cli.py
git commit -m "feat(mcp-docker): error classes + daemon-unreachable hint"
```

---

## Task 4: `approval.py` — write-tool gate

**Files:**
- Create: `mcp/docker/approval.py`
- Test: `mcp/docker/tests/test_approval.py`

**Design:** A stdio MCP has no interactive UI prompt channel. The gate is therefore an **explicit, environment-controlled allowlist** plus a default-deny: a write tool only runs if approval is granted. `require_approval(command)` returns an `(allowed, reason)` tuple. Approval is granted when the env var `MCP_DOCKER_ALLOW_WRITES` is set to `1`/`true` (operator opts in for the session), OR the specific command's first verb is in `MCP_DOCKER_ALLOW_VERBS` (comma-separated). Otherwise denied with a message that shows the exact command. This keeps the safety contract ("write needs approval, the exact command is visible") without depending on an interactive channel; a richer elicitation flow can replace this later without changing tool code.

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_approval.py`:

```python
from docker import approval


def test_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    allowed, reason = approval.require_approval("docker stack rm vibemind")
    assert allowed is False
    assert "docker stack rm vibemind" in reason


def test_allow_all_writes_env(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    allowed, _ = approval.require_approval("docker rm abc")
    assert allowed is True


def test_allow_specific_verb(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.setenv("MCP_DOCKER_ALLOW_VERBS", "start,restart")
    assert approval.require_approval("docker start abc")[0] is True
    assert approval.require_approval("docker rm abc")[0] is False


def test_gate_result_denied_shape():
    res = approval.denied_result("docker rm abc", "nope")
    assert res["ok"] is False
    assert res["approval_denied"] is True
    assert res["command"] == "docker rm abc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_approval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docker.approval'`

- [ ] **Step 3: Write minimal implementation**

Create `mcp/docker/approval.py`:

```python
"""Approval gate for state-changing Docker tools.

stdio MCP has no interactive prompt channel, so approval is an explicit,
env-controlled opt-in. Default-deny. The denial message always shows the
exact command that would have run.
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def _verb(command: str) -> str:
    # command like "docker rm abc" or "docker stack rm x" -> the action verb.
    parts = command.split()
    # skip "docker" and optional subcommand group (compose/stack/service/system/image/network/volume)
    groups = {"compose", "stack", "service", "system", "image", "network", "volume", "container"}
    idx = 1
    if len(parts) > idx and parts[idx] in groups:
        idx += 1
    return parts[idx] if len(parts) > idx else ""


def require_approval(command: str) -> tuple[bool, str]:
    """Return (allowed, reason). Default-deny unless an env opt-in matches."""
    if os.environ.get("MCP_DOCKER_ALLOW_WRITES", "").strip().lower() in _TRUE:
        return True, "approved via MCP_DOCKER_ALLOW_WRITES"
    allow_verbs = os.environ.get("MCP_DOCKER_ALLOW_VERBS", "")
    verbs = {v.strip() for v in allow_verbs.split(",") if v.strip()}
    if _verb(command) in verbs:
        return True, f"approved via MCP_DOCKER_ALLOW_VERBS ({_verb(command)})"
    return (
        False,
        f"approval required for: `{command}`. "
        "Set MCP_DOCKER_ALLOW_WRITES=1 or add the verb to MCP_DOCKER_ALLOW_VERBS to allow.",
    )


def denied_result(command: str, reason: str) -> dict:
    return {
        "ok": False,
        "command": command,
        "data": None,
        "stdout": "",
        "stderr": reason,
        "exit_code": None,
        "daemon_unreachable": False,
        "approval_denied": True,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_approval.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/approval.py mcp/docker/tests/test_approval.py
git commit -m "feat(mcp-docker): env-controlled approval gate for write tools"
```

---

## Task 5: `server.py` — FastMCP instance + read tools (container/image/network/volume)

**Files:**
- Create: `mcp/docker/server.py`
- Test: `mcp/docker/tests/test_server_read.py`

**Pattern for every tool:** build an arg list, call `docker_cli.run(...)`, return the dict. A small `_exec(args, parse=...)` and `_exec_write(args)` helper keep tools to one line each.

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_server_read.py`:

```python
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
    assert args[0] == ["inspect", "abc"]
    assert kwargs.get("parse") == "json"


def test_image_ls_builds_images_command():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.image_ls()
    assert run.call_args[0][0][0] == "images"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_read.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'docker.server'`

- [ ] **Step 3: Write the server with read tools**

Create `mcp/docker/server.py`:

```python
"""Docker-CLI MCP server (stdio). Each tool maps params to a docker arg list.

Read tools run free. Write tools route through approval.require_approval first.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from docker import approval, docker_cli

mcp = FastMCP("docker")

JSON_LINE = ["--format", "{{json .}}"]


def _exec(args: list[str], *, parse: Optional[str] = None) -> dict:
    return docker_cli.run(args, parse=parse)


def _exec_write(args: list[str]) -> dict:
    command = "docker " + " ".join(args)
    allowed, reason = approval.require_approval(command)
    if not allowed:
        return approval.denied_result(command, reason)
    return docker_cli.run(args)


# ---------- Container (read) ----------

@mcp.tool()
def container_ls(all: bool = False) -> dict:
    """List containers (docker ps). all=True includes stopped ones."""
    args = ["ps", *JSON_LINE]
    if all:
        args.insert(1, "-a")
    return _exec(args, parse="ndjson")


@mcp.tool()
def container_inspect(container: str) -> dict:
    """Inspect a container (docker inspect <id>)."""
    return _exec(["inspect", container], parse="json")


@mcp.tool()
def container_logs(container: str, tail: int = 200, since: str = "") -> dict:
    """Container logs (docker logs). tail=lines, since=e.g. '10m'."""
    args = ["logs", "--tail", str(tail)]
    if since:
        args += ["--since", since]
    args.append(container)
    return _exec(args)


@mcp.tool()
def container_stats() -> dict:
    """One-shot resource stats for all containers (docker stats --no-stream)."""
    return _exec(["stats", "--no-stream", *JSON_LINE], parse="ndjson")


@mcp.tool()
def container_top(container: str) -> dict:
    """Running processes in a container (docker top <id>)."""
    return _exec(["top", container])


# ---------- Image (read) ----------

@mcp.tool()
def image_ls() -> dict:
    """List images (docker images)."""
    return _exec(["images", *JSON_LINE], parse="ndjson")


@mcp.tool()
def image_inspect(ref: str) -> dict:
    """Inspect an image (docker image inspect <ref>)."""
    return _exec(["image", "inspect", ref], parse="json")


@mcp.tool()
def image_history(ref: str) -> dict:
    """Image layer history (docker history <ref>)."""
    return _exec(["history", *JSON_LINE, ref], parse="ndjson")


# ---------- Network / Volume (read) ----------

@mcp.tool()
def network_ls() -> dict:
    """List networks (docker network ls)."""
    return _exec(["network", "ls", *JSON_LINE], parse="ndjson")


@mcp.tool()
def network_inspect(name: str) -> dict:
    """Inspect a network (docker network inspect <name>)."""
    return _exec(["network", "inspect", name], parse="json")


@mcp.tool()
def volume_ls() -> dict:
    """List volumes (docker volume ls)."""
    return _exec(["volume", "ls", *JSON_LINE], parse="ndjson")


@mcp.tool()
def volume_inspect(name: str) -> dict:
    """Inspect a volume (docker volume inspect <name>)."""
    return _exec(["volume", "inspect", name], parse="json")


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_read.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/server.py mcp/docker/tests/test_server_read.py
git commit -m "feat(mcp-docker): server + read tools (container/image/network/volume)"
```

---

## Task 6: Write tools (container/image lifecycle) + approval routing

**Files:**
- Modify: `mcp/docker/server.py` (append tools before `def main`)
- Test: `mcp/docker/tests/test_server_write.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_server_write.py`:

```python
from unittest import mock

from docker import server


def test_container_rm_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.container_rm("abc")
    assert res["approval_denied"] is True
    assert "docker rm abc" in res["command"]


def test_container_rm_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_rm("abc", force=True)
    assert run.call_args[0][0] == ["rm", "-f", "abc"]


def test_container_stop_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_stop("abc")
    assert run.call_args[0][0] == ["stop", "abc"]


def test_image_pull_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.image_pull("redis:7")
    assert run.call_args[0][0] == ["pull", "redis:7"]


def test_container_exec_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.container_exec("abc", "ls -la")
    assert run.call_args[0][0] == ["exec", "abc", "ls", "-la"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_write.py -v`
Expected: FAIL — `AttributeError: module 'docker.server' has no attribute 'container_rm'`

- [ ] **Step 3: Add write tools (insert into `server.py` immediately before `def main`)**

```python
# ---------- Container (write) ----------

@mcp.tool()
def container_start(container: str) -> dict:
    """Start a container (docker start <id>). WRITE — needs approval."""
    return _exec_write(["start", container])


@mcp.tool()
def container_stop(container: str) -> dict:
    """Stop a container (docker stop <id>). WRITE — needs approval."""
    return _exec_write(["stop", container])


@mcp.tool()
def container_restart(container: str) -> dict:
    """Restart a container (docker restart <id>). WRITE — needs approval."""
    return _exec_write(["restart", container])


@mcp.tool()
def container_rm(container: str, force: bool = False) -> dict:
    """Remove a container (docker rm). WRITE — needs approval."""
    args = ["rm"]
    if force:
        args.append("-f")
    args.append(container)
    return _exec_write(args)


@mcp.tool()
def container_exec(container: str, command: str) -> dict:
    """Run a command in a container (docker exec). WRITE — needs approval.

    `command` is split on whitespace into argv (no shell)."""
    return _exec_write(["exec", container, *command.split()])


# ---------- Image (write) ----------

@mcp.tool()
def image_pull(ref: str) -> dict:
    """Pull an image (docker pull <ref>). WRITE — needs approval."""
    return _exec_write(["pull", ref])


@mcp.tool()
def image_rm(ref: str, force: bool = False) -> dict:
    """Remove an image (docker rmi). WRITE — needs approval."""
    args = ["rmi"]
    if force:
        args.append("-f")
    args.append(ref)
    return _exec_write(args)


@mcp.tool()
def image_build(tag: str, context: str = ".", dockerfile: str = "") -> dict:
    """Build an image (docker build -t <tag> <context>). WRITE — needs approval."""
    args = ["build", "-t", tag]
    if dockerfile:
        args += ["-f", dockerfile]
    args.append(context)
    return _exec_write(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_write.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/server.py mcp/docker/tests/test_server_write.py
git commit -m "feat(mcp-docker): container/image write tools via approval gate"
```

---

## Task 7: Compose tools

**Files:**
- Modify: `mcp/docker/server.py` (append before `def main`)
- Test: `mcp/docker/tests/test_server_compose.py`

**Note:** compose args are prefixed with `compose`. A `-f <file>` and `-p <project>` may precede the verb. Read tools (`ps/logs/config`) run free; `up/down/restart/build` are writes.

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_server_compose.py`:

```python
from unittest import mock

from docker import server


def test_compose_ps_read(monkeypatch):
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_ps(file="docker-compose.yml")
    assert run.call_args[0][0] == ["compose", "-f", "docker-compose.yml", "ps", "--format", "json"]


def test_compose_up_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.compose_up(file="dc.yml")
    assert res["approval_denied"] is True


def test_compose_up_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_up(file="dc.yml", project="proj")
    assert run.call_args[0][0] == ["compose", "-f", "dc.yml", "-p", "proj", "up", "-d"]


def test_compose_down_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.compose_down(file="dc.yml")
    assert run.call_args[0][0] == ["compose", "-f", "dc.yml", "down"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_compose.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'compose_ps'`

- [ ] **Step 3: Add compose tools + a `_compose_prefix` helper (insert before `def main`)**

```python
# ---------- Compose ----------

def _compose_prefix(file: str, project: str) -> list[str]:
    args = ["compose"]
    if file:
        args += ["-f", file]
    if project:
        args += ["-p", project]
    return args


@mcp.tool()
def compose_ps(file: str = "", project: str = "") -> dict:
    """List compose services (docker compose ps)."""
    return _exec([*_compose_prefix(file, project), "ps", "--format", "json"], parse="json")


@mcp.tool()
def compose_logs(file: str = "", project: str = "", tail: int = 200) -> dict:
    """Compose service logs (docker compose logs --tail N)."""
    return _exec([*_compose_prefix(file, project), "logs", "--tail", str(tail)])


@mcp.tool()
def compose_config(file: str = "", project: str = "") -> dict:
    """Render the resolved compose config (docker compose config)."""
    return _exec([*_compose_prefix(file, project), "config"])


@mcp.tool()
def compose_up(file: str = "", project: str = "") -> dict:
    """Start compose services detached (docker compose up -d). WRITE — needs approval."""
    return _exec_write([*_compose_prefix(file, project), "up", "-d"])


@mcp.tool()
def compose_down(file: str = "", project: str = "") -> dict:
    """Stop compose services (docker compose down). WRITE — needs approval."""
    return _exec_write([*_compose_prefix(file, project), "down"])


@mcp.tool()
def compose_restart(file: str = "", project: str = "", service: str = "") -> dict:
    """Restart compose services (docker compose restart [svc]). WRITE — needs approval."""
    args = [*_compose_prefix(file, project), "restart"]
    if service:
        args.append(service)
    return _exec_write(args)


@mcp.tool()
def compose_build(file: str = "", project: str = "") -> dict:
    """Build compose images (docker compose build). WRITE — needs approval."""
    return _exec_write([*_compose_prefix(file, project), "build"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_compose.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add mcp/docker/server.py mcp/docker/tests/test_server_compose.py
git commit -m "feat(mcp-docker): compose tools (ps/logs/config/up/down/restart/build)"
```

---

## Task 8: Swarm / Stack / Service + System tools

**Files:**
- Modify: `mcp/docker/server.py` (append before `def main`)
- Test: `mcp/docker/tests/test_server_swarm.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp/docker/tests/test_server_swarm.py`:

```python
from unittest import mock

from docker import server


def test_stack_ls_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_ls()
    assert run.call_args[0][0] == ["stack", "ls", "--format", "{{json .}}"]


def test_stack_ps_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_ps("vibemind")
    assert run.call_args[0][0] == ["stack", "ps", "vibemind", "--format", "{{json .}}"]


def test_service_inspect_json():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.service_inspect("vibemind_brain-core")
    args, kwargs = run.call_args
    assert args[0] == ["service", "inspect", "vibemind_brain-core"]
    assert kwargs.get("parse") == "json"


def test_stack_deploy_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.stack_deploy("vibemind", "stack.yml")
    assert res["approval_denied"] is True


def test_stack_rm_runs_when_allowed(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.stack_rm("vibemind")
    assert run.call_args[0][0] == ["stack", "rm", "vibemind"]


def test_service_scale_command(monkeypatch):
    monkeypatch.setenv("MCP_DOCKER_ALLOW_WRITES", "1")
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.service_scale("vibemind_brain-core", 3)
    assert run.call_args[0][0] == ["service", "scale", "vibemind_brain-core=3"]


def test_system_df_read():
    with mock.patch("docker.docker_cli.run") as run:
        run.return_value = {"ok": True}
        server.system_df()
    assert run.call_args[0][0] == ["system", "df"]


def test_system_prune_denied_by_default(monkeypatch):
    monkeypatch.delenv("MCP_DOCKER_ALLOW_WRITES", raising=False)
    monkeypatch.delenv("MCP_DOCKER_ALLOW_VERBS", raising=False)
    res = server.system_prune()
    assert res["approval_denied"] is True
    assert "--volumes" not in res["command"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_swarm.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'stack_ls'`

- [ ] **Step 3: Add swarm/stack/service/system tools (insert before `def main`)**

```python
# ---------- Swarm / Stack / Service ----------

@mcp.tool()
def stack_ls() -> dict:
    """List swarm stacks (docker stack ls)."""
    return _exec(["stack", "ls", *JSON_LINE], parse="ndjson")


@mcp.tool()
def stack_ps(stack: str) -> dict:
    """Tasks of a stack (docker stack ps <stack>)."""
    return _exec(["stack", "ps", stack, *JSON_LINE], parse="ndjson")


@mcp.tool()
def stack_services(stack: str) -> dict:
    """Services of a stack (docker stack services <stack>)."""
    return _exec(["stack", "services", stack, *JSON_LINE], parse="ndjson")


@mcp.tool()
def service_ls() -> dict:
    """List swarm services (docker service ls)."""
    return _exec(["service", "ls", *JSON_LINE], parse="ndjson")


@mcp.tool()
def service_logs(service: str, tail: int = 200) -> dict:
    """Service logs (docker service logs --tail N <svc>)."""
    return _exec(["service", "logs", "--tail", str(tail), service])


@mcp.tool()
def service_inspect(service: str) -> dict:
    """Inspect a service (docker service inspect <svc>)."""
    return _exec(["service", "inspect", service], parse="json")


@mcp.tool()
def stack_deploy(stack: str, compose_file: str) -> dict:
    """Deploy/update a stack (docker stack deploy -c <file> <stack>). WRITE — needs approval."""
    return _exec_write(["stack", "deploy", "-c", compose_file, stack])


@mcp.tool()
def stack_rm(stack: str) -> dict:
    """Remove a stack (docker stack rm <stack>). WRITE — needs approval."""
    return _exec_write(["stack", "rm", stack])


@mcp.tool()
def service_scale(service: str, replicas: int) -> dict:
    """Scale a service (docker service scale <svc>=<n>). WRITE — needs approval."""
    return _exec_write(["service", "scale", f"{service}={replicas}"])


@mcp.tool()
def service_update(service: str, image: str = "") -> dict:
    """Update a service (docker service update <svc>). WRITE — needs approval."""
    args = ["service", "update"]
    if image:
        args += ["--image", image]
    args.append(service)
    return _exec_write(args)


# ---------- System ----------

@mcp.tool()
def system_info() -> dict:
    """Docker system info (docker info)."""
    return _exec(["info", "--format", "{{json .}}"], parse="json")


@mcp.tool()
def system_df() -> dict:
    """Disk usage (docker system df)."""
    return _exec(["system", "df"])


@mcp.tool()
def version() -> dict:
    """Docker version (docker version)."""
    return _exec(["version", "--format", "{{json .}}"], parse="json")


@mcp.tool()
def system_prune() -> dict:
    """Prune unused data WITHOUT volumes (docker system prune -f). WRITE — needs approval."""
    return _exec_write(["system", "prune", "-f"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/test_server_swarm.py -v`
Expected: 8 passed

- [ ] **Step 5: Run the FULL unit suite**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python -m pytest docker/tests/ -v`
Expected: all tests pass (≈33)

- [ ] **Step 6: Commit**

```bash
git add mcp/docker/server.py mcp/docker/tests/test_server_swarm.py
git commit -m "feat(mcp-docker): swarm/stack/service/system tools + full suite green"
```

---

## Task 9: Live smoke test (read-only, real engine)

**Files:**
- Create: `mcp/docker/tests/smoke_live.py` (a script, NOT collected by pytest — named `smoke_*` so testpaths default skips it)

**Note:** This hits the REAL Docker engine (`vibemind`/`unity-ai` stacks live). Read-only tools only.

- [ ] **Step 1: Write the smoke script**

Create `mcp/docker/tests/smoke_live.py`:

```python
"""Manual live smoke test against the real Docker engine. Read-only.

Run: python docker/tests/smoke_live.py   (from the mcp/ directory)
"""

from docker import server


def main() -> None:
    checks = [
        ("version", lambda: server.version()),
        ("container_ls", lambda: server.container_ls(all=True)),
        ("image_ls", lambda: server.image_ls()),
        ("stack_ls", lambda: server.stack_ls()),
        ("service_ls", lambda: server.service_ls()),
        ("system_df", lambda: server.system_df()),
    ]
    failed = 0
    for name, fn in checks:
        res = fn()
        ok = res.get("ok")
        n = len(res["data"]) if isinstance(res.get("data"), list) else "-"
        print(f"[{'OK ' if ok else 'FAIL'}] {name:16} ok={ok} data_items={n}")
        if not ok:
            failed += 1
            print("        stderr:", res.get("stderr", "")[:200])
    print(f"\n{len(checks) - failed}/{len(checks)} read tools OK")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the smoke test against the live engine**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1\mcp" && python docker/tests/smoke_live.py`
Expected: All 6 read tools print `OK`; `stack_ls` shows `data_items>=2` (vibemind, unity-ai); `version` ok=True. Exit 0.

If `daemon_unreachable` appears, Docker isn't reachable — see the WSL-mirrored-hang note (Windows restart, not `.wslconfig`).

- [ ] **Step 3: Commit**

```bash
git add mcp/docker/tests/smoke_live.py
git commit -m "test(mcp-docker): live read-only smoke script"
```

---

## Task 10: README + MCP registration docs

**Files:**
- Create: `mcp/docker/README.md`

- [ ] **Step 1: Write the README**

Create `mcp/docker/README.md`:

````markdown
# Docker-CLI MCP Server

Stdio MCP server exposing the Docker CLI as ~40 explicitly-named tools.
CLI-only (no docker-py). Read tools run free; write tools are gated by an
env-controlled approval allowlist.

## Run

```bash
# from the repo root
python -m mcp.docker.server        # if mcp/ is on PYTHONPATH
# or from mcp/
python -c "from docker.server import main; main()"
```

## Approval (write tools)

State-changing tools (start/stop/rm/exec, pull/rmi/build, compose up/down/build,
stack deploy/rm, service scale/update, system prune) are **denied by default**.
Opt in per session:

- `MCP_DOCKER_ALLOW_WRITES=1` — allow all write tools, or
- `MCP_DOCKER_ALLOW_VERBS=start,restart,stop` — allow only listed verbs.

Denied calls return `{"ok": false, "approval_denied": true, ...}` with the exact
command in `command`.

## Tools

Read (free): container_ls, container_inspect, container_logs, container_stats,
container_top, image_ls, image_inspect, image_history, network_ls,
network_inspect, volume_ls, volume_inspect, compose_ps, compose_logs,
compose_config, stack_ls, stack_ps, stack_services, service_ls, service_logs,
service_inspect, system_info, system_df, version.

Write (approval): container_start, container_stop, container_restart,
container_rm, container_exec, image_pull, image_rm, image_build, compose_up,
compose_down, compose_restart, compose_build, stack_deploy, stack_rm,
service_scale, service_update, system_prune.

## Register in Claude Code (stdio)

Add to your MCP config:

```json
{
  "mcpServers": {
    "docker": {
      "command": "python",
      "args": ["-m", "mcp.docker.server"],
      "cwd": "c:/Users/User/Desktop/Vibemind_V1"
    }
  }
}
```

## Register on the OpenFang hub

Bridge via `vibemind-os/openfang/scripts/mcp_stdio_bridge.py` (manual step — no
auto-deploy into the swarm). Note: `vibemind-os/ops/mcp/servers.json` has a stale
`"docker"` entry pointing at the non-existent `mcp_server_docker` module; update or
remove it to avoid a dead registration.

## Result shape

```json
{ "ok": true, "command": "docker ps -a", "data": [...], "stdout": "...",
  "stderr": "", "exit_code": 0, "daemon_unreachable": false }
```
````

- [ ] **Step 2: Verify the README renders (quick sanity check)**

Run: `cd "c:\Users\User\Desktop\Vibemind_V1" && python -c "print(open('mcp/docker/README.md', encoding='utf-8').read()[:200])"`
Expected: prints the README header.

- [ ] **Step 3: Commit**

```bash
git add mcp/docker/README.md
git commit -m "docs(mcp-docker): README with tool list, approval, registration"
```

---

## Self-Review Notes

- **Spec coverage:** All ~40 tools from the spec table map to tasks 5–8. Result shape (Task 2/3), error classes incl. daemon-unreachable + 30s timeout (Task 3), approval gate showing exact command (Task 4), no `shell=True` hardening (Task 2), README + OpenFang/servers.json note (Task 10), live read-only smoke (Task 9). ✅
- **Deviation from spec, intentional & verified:** spec said "FastMCP dependency"; the installed reality is the official `mcp` SDK with `mcp.server.fastmcp.FastMCP` — no new dependency. Reflected in Tech Stack + pyproject.
- **Approval mechanism:** spec left the stdio-approval mechanism open for this plan. Resolved as an env-controlled default-deny allowlist (`MCP_DOCKER_ALLOW_WRITES` / `MCP_DOCKER_ALLOW_VERBS`), with denial messages showing the exact command. A richer elicitation flow can replace `approval.py` later without touching tool code.
- **Type consistency:** every tool returns the same dict shape from `docker_cli.run`/`approval.denied_result`; `_exec`/`_exec_write` names are used consistently; `parse` values are only `None|"json"|"ndjson"`.
- **Import note:** tests import `from docker import ...` where `docker` is the local package `mcp/docker/` — tests are run from the `mcp/` directory so the local package shadows nothing (there is no `docker` pip package installed). This is why every test command `cd`s into `mcp/`.
```
