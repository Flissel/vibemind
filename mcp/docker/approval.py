"""Approval gate for state-changing Docker tools.

stdio MCP has no interactive prompt channel, so approval is an explicit,
env-controlled opt-in. Default-deny. The denial message always shows the
exact command that would have run.

MCP_DOCKER_ALLOW_VERBS entries are `group:verb` tokens (e.g. container:rm,
stack:rm). A bare verb like `rm` matches NOTHING — this prevents an allow of
container rm from also allowing the far more destructive stack rm / volume rm.
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}

_GROUPS = {"compose", "stack", "service", "system", "image", "network", "volume", "container"}

# Flags that take a value (the following token is the value, not the verb).
_VALUE_FLAGS = {"-f", "--file", "-p", "--project-name", "-c", "--compose-file"}

_TOP_LEVEL_CONTAINER = {"ps", "run", "start", "stop", "restart", "rm", "exec", "logs", "top", "inspect", "stats"}
_TOP_LEVEL_IMAGE = {"images", "pull", "push", "rmi", "build", "history", "tag"}


def _first_non_flag(tokens: list[str]) -> str:
    """Return the first token that is not a flag and not a flag's value."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _VALUE_FLAGS:
            i += 2  # skip the flag AND its value
            continue
        if tok.startswith("-"):
            i += 1  # skip a boolean flag
            continue
        return tok
    return ""


def _group_verb_from_args(args: list[str]) -> str:
    """Derive a 'group:verb' token from a docker ARG LIST (no 'docker' prefix).

    ["compose", "-f", "dc.yml", "up", "-d"] -> "compose:up"
    ["stack", "rm", "vibemind"]             -> "stack:rm"
    ["rm", "-f", "abc"]                     -> "container:rm"
    ["pull", "redis:7"]                     -> "image:pull"
    ["system", "prune", "-f"]               -> "system:prune"
    Unrecognized / malformed -> "" (never matches -> stays denied).
    """
    if not args:
        return ""
    head = args[0]
    if head in _GROUPS:
        verb = _first_non_flag(args[1:])
        return f"{head}:{verb}" if verb else ""
    # No explicit group word: map a top-level verb to its implicit group.
    verb = head
    if verb in _TOP_LEVEL_IMAGE:
        return f"image:{verb}"
    if verb in _TOP_LEVEL_CONTAINER:
        return f"container:{verb}"
    return ""


def require_approval(command: str, args: list[str] | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Default-deny unless an env opt-in matches.

    `command` is the human-readable string (shown in denials). `args` is the
    structured docker arg list used to derive the group:verb token robustly
    (immune to -f/-p/-c flags preceding the verb). If `args` is None, the token
    is derived from `command` by stripping a leading 'docker '.
    """
    if os.environ.get("MCP_DOCKER_ALLOW_WRITES", "").strip().lower() in _TRUE:
        return True, "approved via MCP_DOCKER_ALLOW_WRITES"
    if args is None:
        parts = command.split()
        args = parts[1:] if parts and parts[0] == "docker" else parts
    allow_verbs = os.environ.get("MCP_DOCKER_ALLOW_VERBS", "")
    tokens = {v.strip() for v in allow_verbs.split(",") if v.strip()}
    gv = _group_verb_from_args(args)
    if gv and gv in tokens:
        return True, f"approved via MCP_DOCKER_ALLOW_VERBS ({gv})"
    return (
        False,
        f"approval required for: `{command}`. "
        "Set MCP_DOCKER_ALLOW_WRITES=1 or add the group:verb to MCP_DOCKER_ALLOW_VERBS to allow.",
    )


def denied_result(command: str, reason: str) -> dict:
    # NOTE: `approval_denied` is an opt-in key NOT present in docker_cli.run's
    # result dict (success OR normal failure). Callers must read it with
    # result.get("approval_denied", False), never result["approval_denied"].
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
