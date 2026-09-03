from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, cast

import yaml

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.git_state import run_git
from tools.v1_governance.models import BRANCH_PATTERN, SessionRequest
from tools.v1_governance.portfolio import require_registered_parent_cockpit


@dataclass(frozen=True)
class WorktreePlan:
    branch: str
    base_ref: str
    destination: Path
    command: tuple[str, ...]

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "base_ref": self.base_ref,
            "branch": self.branch,
            "command": self.command,
            "destination": str(self.destination),
        }


def load_session_request(path: Path) -> SessionRequest:
    """Load and validate one versioned session request."""
    try:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GovernanceError(f"cannot load session request: {type(exc).__name__}") from exc
    if not isinstance(loaded, dict) or any(not isinstance(key, str) for key in loaded):
        raise GovernanceError("session request root must be a mapping")
    return SessionRequest.from_mapping(cast(Mapping[str, object], loaded))


def _resolved_commit(repo_root: Path, ref: str) -> str:
    commit = run_git(repo_root, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if not commit:
        raise GovernanceError("base_ref does not resolve to a commit")
    return commit


def _matching_remote(repo_root: Path, base_ref: str) -> str | None:
    if base_ref.startswith("refs/remotes/") or "/" in base_ref:
        return None
    candidate = f"refs/remotes/origin/{base_ref}"
    return candidate if run_git(repo_root, "rev-parse", "--verify", candidate, check=False) else None


def _canonical_worktrees_root(repo_root: Path, worktrees_root: Path) -> Path:
    canonical = repo_root / ".worktrees"
    supplied = worktrees_root.absolute()
    resolved = worktrees_root.resolve()
    if supplied != canonical or resolved != canonical or not resolved.is_relative_to(repo_root):
        raise GovernanceError("worktrees root must be the canonical repo-local .worktrees")
    return resolved


def _branch_exists(repo_root: Path, branch: str) -> bool:
    references = (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
    return any(run_git(repo_root, "rev-parse", "--verify", ref, check=False) for ref in references)


def plan_task_worktree(
    repo_root: Path,
    request: SessionRequest,
    worktrees_root: Path,
) -> WorktreePlan:
    """Validate every gate and return the only permitted git worktree command."""
    root = Path(run_git(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if not request.is_approved:
        raise GovernanceError("session request is not approved")
    if request.session_type != "task" or not request.writes_allowed:
        raise GovernanceError("only writing task sessions may create worktrees")
    if not request.approval_reference.strip():
        raise GovernanceError("approved session requires an approval reference")
    if not BRANCH_PATTERN.fullmatch(request.branch):
        raise GovernanceError("planned branch violates policy")
    if request.schema_version == 2:
        require_registered_parent_cockpit(root, request.parent_cockpit)
    resolved_worktrees_root = _canonical_worktrees_root(root, worktrees_root)
    if run_git(root, "status", "--porcelain=v1"):
        raise GovernanceError("base checkout is dirty")
    if _branch_exists(root, request.branch):
        raise GovernanceError("planned branch already exists")

    destination = (resolved_worktrees_root / request.session_id).resolve()
    if destination.parent != resolved_worktrees_root:
        raise GovernanceError("planned destination escapes worktrees root")
    if destination.exists():
        raise GovernanceError("planned destination already exists")

    _resolved_commit(root, request.base_ref)
    remote = _matching_remote(root, request.base_ref)
    if remote is not None:
        counts = run_git(root, "rev-list", "--left-right", "--count", f"{request.base_ref}...{remote}")
        _, behind_text = counts.split()
        if int(behind_text) > 0:
            raise GovernanceError("base_ref is behind its remote")

    command = (
        "git",
        "worktree",
        "add",
        "-b",
        request.branch,
        str(destination),
        request.base_ref,
    )
    return WorktreePlan(request.branch, request.base_ref, destination, command)


def create_task_worktree(repo_root: Path, plan: WorktreePlan) -> None:
    root = Path(run_git(repo_root, "rev-parse", "--show-toplevel")).resolve()
    canonical_root = _canonical_worktrees_root(root, plan.destination.parent)
    expected_destination = (canonical_root / plan.destination.name).resolve()
    expected_command = (
        "git",
        "worktree",
        "add",
        "-b",
        plan.branch,
        str(expected_destination),
        plan.base_ref,
    )
    if plan.destination.resolve() != expected_destination or plan.command != expected_command:
        raise GovernanceError("stored worktree command does not match plan fields")
    if run_git(root, "status", "--porcelain=v1"):
        raise GovernanceError("base checkout is dirty")
    if _branch_exists(root, plan.branch):
        raise GovernanceError("planned branch already exists")
    if plan.destination.exists():
        raise GovernanceError("planned destination already exists")
    _resolved_commit(root, plan.base_ref)
    run_git(
        root,
        "worktree",
        "add",
        "-b",
        plan.branch,
        str(plan.destination),
        plan.base_ref,
    )
