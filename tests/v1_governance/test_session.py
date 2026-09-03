from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import subprocess

import pytest

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.models import SessionRequest
from tools.v1_governance.session import create_task_worktree, plan_task_worktree


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def repository(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "tests@example.invalid")
    git(path, "config", "user.name", "Governance Tests")
    (path / "README.md").write_text("baseline\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "test: initialize repository")
    return path


def request() -> SessionRequest:
    return SessionRequest.from_mapping(
        {
            "schema_version": 1,
            "session_id": "task-platform-0002",
            "session_type": "task",
            "space": "platform",
            "objective": "Test worktree gate",
            "repositories": ["vibemind-v1"],
            "allowed_paths": ["tools/v1_governance/**"],
            "writes_allowed": True,
            "approval_status": "approved",
            "approval_reference": "user-message:2026-07-30",
            "base_ref": "main",
            "branch": "codex/platform/task-platform-0002-gate",
            "risk_class": "code",
        }
    )


def governed_request(parent_cockpit: str = "cockpit-coding") -> SessionRequest:
    return SessionRequest.from_mapping(
        {
            "schema_version": 2,
            "session_id": "task-governance-0017",
            "session_type": "task",
            "space": "governance",
            "parent_cockpit": parent_cockpit,
            "request_reference": "task-request:task-governance-0017-v1",
            "objective": "Gate task parent cockpits against the portfolio registry",
            "repositories": ["vibemind-v1"],
            "allowed_paths": ["tools/v1_governance/**"],
            "writes_allowed": True,
            "approval_status": "approved",
            "approval_reference": "standing-autonomy:v1",
            "base_ref": "main",
            "branch": "codex/governance/task-governance-0017-parent-cockpit-gate",
            "risk_class": "code",
            "dependencies": [],
            "merge_position": 1,
        }
    )


def write_registry(root: Path, payload: object) -> None:
    registry = root / "docs" / "governance" / "session-portfolio-registry-v1.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps(payload), encoding="utf-8")
    git(root, "add", str(registry.relative_to(root)))
    git(root, "commit", "-m", "test: add portfolio registry")


def test_pending_request_cannot_create_worktree(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    pending = replace(request(), approval_status="pending")

    with pytest.raises(GovernanceError, match="^session request is not approved$"):
        plan_task_worktree(root, pending, root / ".worktrees")


def test_cockpit_request_cannot_create_writing_worktree(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    cockpit = replace(request(), session_type="space-cockpit")

    with pytest.raises(GovernanceError, match="^only writing task sessions may create worktrees$"):
        plan_task_worktree(root, cockpit, root / ".worktrees")


def test_task_plan_rejects_missing_portfolio_registry(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")

    with pytest.raises(GovernanceError, match="^cockpit registry is unavailable$"):
        plan_task_worktree(root, governed_request(), root / ".worktrees")


def test_task_plan_rejects_malformed_portfolio_registry(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    write_registry(root, {"cockpits": "not-a-list"})

    with pytest.raises(GovernanceError, match="^cockpit registry is malformed$"):
        plan_task_worktree(root, governed_request(), root / ".worktrees")


def test_task_plan_rejects_unregistered_parent_cockpit(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    write_registry(root, {"cockpits": [{"cockpit_session_id": "cockpit-coding"}]})

    with pytest.raises(GovernanceError, match="^parent_cockpit is not registered$"):
        plan_task_worktree(root, governed_request("cockpit-unknown"), root / ".worktrees")


def test_task_plan_accepts_registered_parent_cockpit(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    write_registry(root, {"cockpits": [{"cockpit_session_id": "cockpit-coding"}]})

    plan = plan_task_worktree(root, governed_request(), root / ".worktrees")

    assert plan.branch == "codex/governance/task-governance-0017-parent-cockpit-gate"


def test_dirty_base_checkout_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    (root / "dirty.txt").write_text("private\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="^base checkout is dirty$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_existing_branch_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    git(root, "branch", request().branch)

    with pytest.raises(GovernanceError, match="^planned branch already exists$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_existing_destination_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    destination = root / ".worktrees" / request().session_id
    destination.mkdir(parents=True)

    with pytest.raises(GovernanceError, match="^planned destination already exists$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_dry_run_has_no_git_or_filesystem_side_effect(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    worktrees_root = root / ".worktrees"
    branches_before = git(root, "branch", "--format=%(refname)")
    paths_before = sorted(path.relative_to(root) for path in root.rglob("*") if ".git" not in path.parts)

    plan = plan_task_worktree(root, request(), worktrees_root)

    assert plan.destination == (worktrees_root / request().session_id).resolve()
    assert git(root, "branch", "--format=%(refname)") == branches_before
    assert sorted(path.relative_to(root) for path in root.rglob("*") if ".git" not in path.parts) == paths_before
    assert not worktrees_root.exists()


def test_approved_request_creates_expected_branch_and_worktree(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    expected_head = git(root, "rev-parse", request().base_ref)
    plan = plan_task_worktree(root, request(), root / ".worktrees")

    create_task_worktree(root, plan)

    assert git(plan.destination, "branch", "--show-current") == request().branch
    assert git(plan.destination, "rev-parse", "HEAD") == expected_head
    assert plan.branch == request().branch


def test_remote_branch_conflict_is_rejected(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    root = repository(tmp_path / "repo")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "origin", f"main:refs/heads/{request().branch}")
    git(root, "fetch", "origin")

    with pytest.raises(GovernanceError, match="^planned branch already exists$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_unresolvable_base_ref_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    invalid = replace(request(), base_ref="missing")

    with pytest.raises(GovernanceError, match="^base_ref does not resolve to a commit$"):
        plan_task_worktree(root, invalid, root / ".worktrees")


def test_base_ref_behind_remote_is_rejected(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    root = repository(tmp_path / "repo")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-u", "origin", "main")
    other = tmp_path / "other"
    git(tmp_path, "clone", "-b", "main", str(remote), str(other))
    git(other, "config", "user.email", "tests@example.invalid")
    git(other, "config", "user.name", "Governance Tests")
    (other / "remote.txt").write_text("remote\n", encoding="utf-8")
    git(other, "add", "remote.txt")
    git(other, "commit", "-m", "test: remote commit")
    git(other, "push", "origin", "main")
    git(root, "fetch", "origin")

    with pytest.raises(GovernanceError, match="^base_ref is behind its remote$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_session_id_cannot_escape_worktrees_root(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    escaping = replace(request(), session_id="../escape")

    with pytest.raises(GovernanceError, match="^planned destination escapes worktrees root$"):
        plan_task_worktree(root, escaping, root / ".worktrees")


def test_external_worktrees_root_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    external = tmp_path / "external-worktrees"

    with pytest.raises(GovernanceError, match="^worktrees root must be the canonical repo-local .worktrees$"):
        plan_task_worktree(root, request(), external)


def test_symlinked_worktrees_root_escape_is_rejected(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    external = tmp_path / "external-worktrees"
    external.mkdir()
    try:
        (root / ".worktrees").symlink_to(external, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")

    with pytest.raises(GovernanceError, match="^worktrees root must be the canonical repo-local .worktrees$"):
        plan_task_worktree(root, request(), root / ".worktrees")


def test_execute_rechecks_dirty_base_checkout(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    plan = plan_task_worktree(root, request(), root / ".worktrees")
    (root / "became-dirty.txt").write_text("private\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="^base checkout is dirty$"):
        create_task_worktree(root, plan)

    assert not plan.destination.exists()
    assert not git(root, "branch", "--list", request().branch)
