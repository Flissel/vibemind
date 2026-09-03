# Docker-CLI MCP Server

Stdio MCP server exposing the Docker CLI as ~40 explicitly-named tools.
CLI-only (no docker-py). Read tools run free; write tools are gated by an
env-controlled, default-deny approval allowlist. Verified end-to-end against a
live Docker Engine (swarm stacks present).

## Run

From the `mcp/` directory:

```bash
python -m docker.server
```

(The package dir is `docker`; the installed `mcp` SDK does not conflict.)
A console entry-point `vibemind-mcp-docker` is also defined in `pyproject.toml`.

## Approval (write tools)

State-changing tools (start/stop/rm/exec, pull/rmi/build, compose up/down/build,
stack deploy/rm, service scale/update, system prune) are DENIED BY DEFAULT.
Opt in per session via environment variables:

- `MCP_DOCKER_ALLOW_WRITES=1` — allow ALL write tools (use in fully trusted setups).
  Also accepts `true` / `yes` / `on`.
- `MCP_DOCKER_ALLOW_VERBS=container:rm,container:stop` — allow ONLY the listed
  `group:verb` tokens.

The token format is `group:verb` (e.g. `container:rm`, `stack:deploy`,
`system:prune`), NOT a bare verb. This is deliberate: a bare `rm` matches nothing,
so allowing `container:rm` does NOT also grant the far more destructive
`stack:rm` (tears down a whole swarm stack) or `volume:rm` (data loss).

Denied calls return a result with `approval_denied: true` and the exact command:

```json
{"ok": false, "approval_denied": true, "command": "docker stack rm vibemind", "...": "..."}
```

## Result shape

Every tool returns:

```json
{
  "ok": true,
  "command": "docker ps -a",
  "data": ["...parsed JSON when the command supports --format json, else null..."],
  "stdout": "...",
  "stderr": "",
  "exit_code": 0,
  "daemon_unreachable": false
}
```

`approval_denied: true` is added ONLY on write-denials. Read it defensively with
`result.get("approval_denied", False)`.

## Tools

Read (free): `container_ls`, `container_inspect`, `container_logs`, `container_stats`,
`container_top`, `image_ls`, `image_inspect`, `image_history`, `network_ls`,
`network_inspect`, `volume_ls`, `volume_inspect`, `compose_ps`, `compose_logs`,
`compose_config`, `stack_ls`, `stack_ps`, `stack_services`, `service_ls`, `service_logs`,
`service_inspect`, `system_info`, `system_df`, `version`.

Write (approval): `container_start`, `container_stop`, `container_restart`,
`container_rm`, `container_exec`, `image_pull`, `image_rm`, `image_build`, `compose_up`,
`compose_down`, `compose_restart`, `compose_build`, `stack_deploy`, `stack_rm`,
`service_scale`, `service_update`, `system_prune`.

## Live smoke test (read-only)

From the `mcp/` directory:

```bash
python -m docker.tests.smoke_live
```

Calls 6 read tools against the real engine and prints OK/FAIL per tool.

## Register in Claude Code (stdio)

Add to your MCP config:

```json
{
  "mcpServers": {
    "docker": {
      "command": "python",
      "args": ["-m", "docker.server"],
      "cwd": "c:/Users/User/Desktop/Vibemind_V1/mcp",
      "env": { "MCP_DOCKER_ALLOW_WRITES": "0" }
    }
  }
}
```

## Register on the OpenFang hub

Bridge via `vibemind-os/openfang/scripts/mcp_stdio_bridge.py` (manual step — no
auto-deploy into the swarm).

NOTE: `vibemind-os/ops/mcp/servers.json` currently has a STALE `"docker"` entry
pointing at the non-existent module `mcp_server_docker` (it would fail with
`ModuleNotFoundError`). Update or remove that entry so it points at this server
instead, to avoid a dead registration.

## Errors

- `daemon_unreachable: true` → Docker isn't reachable (daemon down / pipe gone).
  Each call has a 30s timeout so a hung `docker` cannot block the server.
- Non-zero exit → `ok: false` with docker's stderr passed through.
