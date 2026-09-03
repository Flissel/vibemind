"""Hermetic tests for worktree-local fungus post-commit resolution."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SOURCE = REPO_ROOT / ".githooks" / "post-commit"


def _find_sh() -> str | None:
    if shell := shutil.which("sh"):
        return shell

    for variable in ("ProgramW6432", "ProgramFiles"):
        if root := os.environ.get(variable):
            candidate = Path(root) / "Git" / "bin" / "sh.exe"
            if candidate.is_file():
                return str(candidate)
    return None


SH = _find_sh()


def _install_hook(tmp_path: Path) -> Path:
    hook = tmp_path / "central" / ".githooks" / "post-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOK_SOURCE, hook)
    return hook


def _install_fake_python(tmp_path: Path) -> Path:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    python = fake_bin / ("python.exe" if os.name == "nt" else "python")
    python.write_text(
        "#!/bin/sh\n"
        "printf 'call\\n' >> \"$FAKE_PYTHON_COUNT\"\n"
        ": > \"$FAKE_PYTHON_CAPTURE\"\n"
        "for arg in \"$@\"; do printf '%s\\n' \"$arg\" >> \"$FAKE_PYTHON_CAPTURE\"; done\n"
        "exit \"${FAKE_PYTHON_STATUS:-0}\"\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    return fake_bin


def _posix_dir(path: Path) -> str:
    assert SH is not None
    completed = subprocess.run(
        [SH, "-c", 'cd "$1" && pwd', "sh", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit_repository(path: Path) -> None:
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "hook-test@example.invalid")
    _git(path, "config", "user.name", "Hook Test")
    _git(path, "add", ".")
    _git(path, "commit", "-qm", "initial fixture")


def _local_git_layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    outer = tmp_path / "layout with spaces" / "outer"
    vibemind_os = outer / "vibemind-os"
    fungus = vibemind_os / "la-fungus-search"

    _updater(fungus / "incremental_updater.py")
    (fungus / "mcp_server.py").write_text("# sentinel marker\n", encoding="utf-8")
    _commit_repository(fungus)
    _git(fungus, "remote", "add", "origin", "https://github.com/Flissel/la_fungus_search.git")
    _commit_repository(vibemind_os)
    _commit_repository(outer)
    return outer, vibemind_os, fungus


def _run_hook(
    tmp_path: Path, repo: Path, *, include_python: bool = True, python_status: int = 0,
) -> list[str] | None:
    if SH is None:
        pytest.skip("POSIX sh is required for the central hook")
    hook = _install_hook(tmp_path)
    fake_bin = _install_fake_python(tmp_path)
    repo.mkdir(parents=True, exist_ok=True)
    hook_arg = Path(os.path.relpath(hook, repo)).as_posix()
    environment = os.environ.copy()
    path_parts = [_posix_dir(fake_bin), "/usr/bin", "/bin"]
    if include_python:
        path_parts.insert(1, _posix_dir(Path(sys.executable).parent))
    environment["PATH"] = ":".join(path_parts)
    capture = tmp_path / ".fungus-hook-spawn"
    environment["FAKE_PYTHON_CAPTURE"] = _posix_dir(capture.parent) + "/.fungus-hook-spawn"
    count = tmp_path / ".fungus-hook-count"
    environment["FAKE_PYTHON_COUNT"] = _posix_dir(count.parent) + "/.fungus-hook-count"
    environment["FAKE_PYTHON_STATUS"] = str(python_status)

    command = '. "$1"'
    arguments = [SH, hook_arg]
    if os.name == "nt" or not include_python:
        python_function = (
            'python() { printf "call\\n" >> "$FAKE_PYTHON_COUNT"; : > "$FAKE_PYTHON_CAPTURE"; '
            'for arg in "$@"; do printf "%s\\n" "$arg" >> "$FAKE_PYTHON_CAPTURE"; done; '
            'return "${FAKE_PYTHON_STATUS:-0}"; }; '
        )
        if not include_python:
            python_function = 'command() { return 1; }; '
        command = python_function + '. "$1"'
        arguments = [SH, "-c", command, hook_arg, hook_arg]

    completed = subprocess.run(
        arguments,
        cwd=repo,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )

    deadline = time.monotonic() + 2
    while not capture.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not capture.exists():
        assert "[fungus-inc] reindex triggered" not in completed.stdout
        return None
    assert count.read_text(encoding="utf-8").splitlines() == ["call"]
    if python_status != 0:
        assert "[fungus-inc] reindex triggered" not in completed.stdout
    return capture.read_text(encoding="utf-8").splitlines()


def _updater(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# sentinel only; never executed\n", encoding="utf-8")
    return path


def test_hook_contains_no_user_specific_or_primary_checkout_fallback() -> None:
    source = HOOK_SOURCE.read_text(encoding="utf-8")

    assert "C:/Users/User" not in source
    assert "C:\\Users\\User" not in source
    assert "Desktop/Vibemind_V1" not in source
    assert 'HOOK_ROOT="$(canonical_dir "$HOOK_DIR/..")"' in source
    assert 'LOG_DIR="${HOOK_ROOT}/backups"' in source
    assert "command -v nohup" not in source
    assert "umask 077" in source


def test_extensionless_hook_is_forced_to_lf() -> None:
    attributes = subprocess.run(
        ["git", "check-attr", "eol", "--", ".githooks/post-commit"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert attributes.stdout.strip() == ".githooks/post-commit: eol: lf"
    assert b"\r\n" not in HOOK_SOURCE.read_bytes()

    mode = subprocess.run(
        ["git", "ls-files", "--stage", "--", ".githooks/post-commit"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert mode.stdout.split(maxsplit=1)[0] == "100755"


@pytest.mark.parametrize("route", ("fungus", "vibemind-os", "outer", "nested"))
def test_hook_resolves_the_first_worktree_local_updater(
    tmp_path: Path, route: str,
) -> None:
    outer, vibemind_os, updater_root = _local_git_layout(tmp_path)
    repos = {
        "fungus": updater_root,
        "vibemind-os": vibemind_os,
        "outer": outer,
        "nested": vibemind_os / "services" / "nested",
    }
    repo = repos[route]
    repo.mkdir(parents=True, exist_ok=True)
    updater = updater_root / "incremental_updater.py"

    argv = _run_hook(tmp_path, repo)

    assert argv == [
        _posix_dir(updater_root) + "/incremental_updater.py",
        "--background",
        "--repo-cwd",
        _posix_dir(Path(_git(repo, "rev-parse", "--show-toplevel"))),
    ]


def test_dirty_or_pin_mismatched_worktree_local_updater_does_not_spawn(tmp_path: Path) -> None:
    outer, vibemind_os, fungus = _local_git_layout(tmp_path)
    (fungus / "incremental_updater.py").write_text("# dirty\n", encoding="utf-8")

    assert _run_hook(tmp_path, outer) is None

    _git(fungus, "add", "incremental_updater.py")
    _git(fungus, "commit", "-qm", "new updater head")

    assert _run_hook(tmp_path, vibemind_os) is None


def test_outer_child_gitlink_drift_does_not_spawn(tmp_path: Path) -> None:
    outer, vibemind_os, _ = _local_git_layout(tmp_path)
    (vibemind_os / "local-marker.txt").write_text("new child head\n", encoding="utf-8")
    _git(vibemind_os, "add", "local-marker.txt")
    _git(vibemind_os, "commit", "-qm", "new vibemind-os head")

    assert _run_hook(tmp_path, outer) is None


def test_no_git_or_missing_interpreter_exits_without_spawn(tmp_path: Path) -> None:
    no_git_repo = tmp_path / "not-a-repository"
    _updater(no_git_repo / "incremental_updater.py")

    assert _run_hook(tmp_path, no_git_repo) is None

    _, _, fungus = _local_git_layout(tmp_path / "with-git")
    assert _run_hook(tmp_path / "with-git", fungus, include_python=False) is None


def test_unrelated_direct_repo_with_tracked_updater_does_not_spawn(tmp_path: Path) -> None:
    unrelated = tmp_path / "unrelated"
    _updater(unrelated / "incremental_updater.py")
    _commit_repository(unrelated)

    assert _run_hook(tmp_path, unrelated) is None


def test_nonzero_background_wrapper_does_not_print_success(tmp_path: Path) -> None:
    _, _, fungus = _local_git_layout(tmp_path)

    assert _run_hook(tmp_path, fungus, python_status=23) is not None


def test_symlinked_updater_exits_without_spawn(tmp_path: Path) -> None:
    outer, _, fungus = _local_git_layout(tmp_path)
    updater = fungus / "incremental_updater.py"
    updater.unlink()
    target = tmp_path / "outside-updater.py"
    target.write_text("# sentinel only\n", encoding="utf-8")
    try:
        updater.symlink_to(target)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    assert _run_hook(tmp_path, outer) is None


def test_nearer_local_candidate_precedes_any_higher_level_candidate(tmp_path: Path) -> None:
    outer, _, fungus = _local_git_layout(tmp_path / "near")
    higher = tmp_path / "la-fungus-search"
    _updater(higher / "incremental_updater.py")

    argv = _run_hook(tmp_path / "near", outer)

    assert argv is not None
    assert argv[0] == _posix_dir(fungus) + "/incremental_updater.py"


def test_missing_worktree_local_updater_exits_without_spawn(tmp_path: Path) -> None:
    repo = tmp_path / "layout" / "outer" / "service"

    argv = _run_hook(tmp_path, repo)

    assert argv is None
