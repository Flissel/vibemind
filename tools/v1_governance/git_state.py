from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Mapping

from tools.v1_governance.errors import GovernanceError


@dataclass(frozen=True)
class GitAudit:
    root: Path
    branch: str
    head: str
    dirty_paths: tuple[str, ...]
    worktrees: tuple[Mapping[str, str], ...]
    upstream: str | None
    ahead: int | None
    behind: int | None
    submodules: tuple[str, ...]

    def to_mapping(self) -> Mapping[str, object]:
        data = asdict(self)
        data["root"] = str(self.root)
        return data


def run_git(root: Path, *args: str, check: bool = True, strip: bool = True) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if check and completed.returncode != 0:
        raise GovernanceError(
            f"git {' '.join(args)} failed with exit {completed.returncode}"
        )
    if not strip:
        return completed.stdout
    return completed.stdout.strip()


def _dirty_paths(output: str) -> tuple[str, ...]:
    paths: set[str] = set()
    for line in output.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.add(value.strip('"'))
    return tuple(sorted(paths))


def _worktrees(output: str) -> tuple[Mapping[str, str], ...]:
    records: list[Mapping[str, str]] = []
    current: dict[str, str] = {}
    for line in (*output.splitlines(), ""):
        if not line:
            if current:
                records.append(dict(current))
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return tuple(records)


def audit_repository(root: Path) -> GitAudit:
    """Collect repository state without fetching or mutating Git state."""
    repository = Path(run_git(root, "rev-parse", "--show-toplevel")).resolve()
    branch = run_git(repository, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    upstream = run_git(
        repository,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    ) or None
    ahead: int | None = None
    behind: int | None = None
    if upstream is not None:
        counts = run_git(repository, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
        ahead_text, behind_text = counts.split()
        ahead, behind = int(ahead_text), int(behind_text)
    return GitAudit(
        root=repository,
        branch=branch or "HEAD",
        head=run_git(repository, "rev-parse", "HEAD"),
        dirty_paths=_dirty_paths(
            run_git(repository, "status", "--porcelain=v1", strip=False)
        ),
        worktrees=_worktrees(run_git(repository, "worktree", "list", "--porcelain")),
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        submodules=tuple(
            line for line in run_git(repository, "submodule", "status", "--recursive").splitlines()
            if line
        ),
    )
