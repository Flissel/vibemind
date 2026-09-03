"""Docker-CLI MCP server (stdio). Each tool maps params to a docker arg list.

Read tools run free. Write tools route through approval.require_approval first.
"""

from __future__ import annotations

import shlex
from typing import Optional

from mcp.server.fastmcp import FastMCP

from docker import approval, docker_cli

mcp = FastMCP("docker")

JSON_LINE = ["--format", "{{json .}}"]


def _exec(args: list[str], *, parse: Optional[str] = None) -> dict:
    return docker_cli.run(args, parse=parse)


def _exec_write(args: list[str]) -> dict:
    command = "docker " + " ".join(args)
    allowed, reason = approval.require_approval(command, args=args)
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
    return _exec(["container", "inspect", container], parse="json")


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

    `command` is POSIX-split with shlex into argv (quotes/escapes honoured,
    no shell is invoked)."""
    return _exec_write(["exec", container, *shlex.split(command)])


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
    """Update a service (docker service update <svc>). WRITE — needs approval.

    image: new image ref. With no options, docker performs a force-style
    re-evaluation (no-op if nothing changed)."""
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
