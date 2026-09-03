from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tools.v1_governance.git_state import audit_repository


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
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


def test_audit_reports_branch_head_and_clean_state(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")

    audit = audit_repository(root)

    assert audit.root == root.resolve()
    assert audit.branch == "main"
    assert audit.head == git(root, "rev-parse", "HEAD")
    assert audit.dirty_paths == ()


def test_audit_lists_dirty_paths_without_file_contents(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    marker = "sensitive-value"
    (root / "private.txt").write_text(marker, encoding="utf-8")

    audit = audit_repository(root)
    serialized = json.dumps(audit.to_mapping())

    assert audit.dirty_paths == ("private.txt",)
    assert marker not in serialized


def test_audit_keeps_the_whole_path_of_an_unstaged_modification(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    (root / "docs").mkdir()
    tracked = root / "docs" / "notes.md"
    tracked.write_text("baseline\n", encoding="utf-8")
    git(root, "add", "docs/notes.md")
    git(root, "commit", "-m", "test: add tracked file")
    tracked.write_text("changed\n", encoding="utf-8")

    audit = audit_repository(root)

    # An unstaged modification is reported by porcelain v1 as " M docs/notes.md",
    # with a leading space. Stripping the output before splitting it eats that
    # space on the first line only, and the fixed offset then eats the "d".
    assert audit.dirty_paths == ("docs/notes.md",)


def test_audit_keeps_every_path_when_a_leading_space_line_comes_first(
    tmp_path: Path,
) -> None:
    root = repository(tmp_path / "repo")
    (root / "docs").mkdir()
    tracked = root / "docs" / "notes.md"
    tracked.write_text("baseline\n", encoding="utf-8")
    git(root, "add", "docs/notes.md")
    git(root, "commit", "-m", "test: add tracked file")
    tracked.write_text("changed\n", encoding="utf-8")
    (root / "zz-untracked.txt").write_text("new\n", encoding="utf-8")

    audit = audit_repository(root)

    assert audit.dirty_paths == ("docs/notes.md", "zz-untracked.txt")


def test_audit_detects_linked_worktree(tmp_path: Path) -> None:
    root = repository(tmp_path / "repo")
    linked = tmp_path / "linked"
    git(root, "worktree", "add", "-b", "feature", str(linked))

    audit = audit_repository(root)

    assert any(
        item.get("branch") == "refs/heads/feature"
        and Path(item["worktree"]).resolve() == linked.resolve()
        for item in audit.worktrees
    )


def test_audit_reports_ahead_behind_against_remote(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    root = repository(tmp_path / "repo")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-u", "origin", "main")
    (root / "local.txt").write_text("local\n", encoding="utf-8")
    git(root, "add", "local.txt")
    git(root, "commit", "-m", "test: local commit")

    audit = audit_repository(root)

    assert audit.upstream == "origin/main"
    assert audit.ahead == 1
    assert audit.behind == 0


def test_audit_reports_recursive_submodule_pins(tmp_path: Path) -> None:
    child = repository(tmp_path / "child")
    nested = repository(tmp_path / "nested")
    git(child, "-c", "protocol.file.allow=always", "submodule", "add", str(nested), "nested")
    git(child, "commit", "-am", "test: add nested submodule")
    root = repository(tmp_path / "repo")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(child), "child")
    git(root, "commit", "-am", "test: add child submodule")
    git(root, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")

    audit = audit_repository(root)

    assert any("child" in item and git(child, "rev-parse", "HEAD") in item for item in audit.submodules)
    assert any("child/nested" in item and git(nested, "rev-parse", "HEAD") in item for item in audit.submodules)
