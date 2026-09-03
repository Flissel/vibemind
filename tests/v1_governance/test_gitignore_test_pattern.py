"""Canary + regression tests for the .gitignore ``test_*.py`` rule.

This file is itself the canary for task-governance-0032: it matches
``test_*.py`` and must be addable WITHOUT ``git add -f``. The previous
unanchored rule (introduced in 2b5ec80 for root-level session-scratch
scripts) accidentally blocked every new test file in the whole tree;
it is now root-anchored as ``/test_*.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _is_ignored(path: str) -> bool:
    """Return True when git would ignore *path* (path need not exist)."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore failed for {path!r}: {result.stderr.strip()}"
        )
    return result.returncode == 0


def test_root_level_test_scratch_stays_ignored() -> None:
    # Original intent of the rule: throwaway test scripts dropped at the
    # repo root during interactive sessions.
    assert _is_ignored("test_scratch_session_probe.py")


def test_governance_test_files_are_not_ignored() -> None:
    assert not _is_ignored("tests/v1_governance/test_new_governance_canary.py")


def test_nested_test_files_are_not_ignored() -> None:
    for path in (
        "tests/architecture/test_new_architecture_probe.py",
        "tests/contracts/test_new_contract_probe.py",
        "spaces/marketing/tools/tests/test_new_marketing_probe.py",
    ):
        assert not _is_ignored(path), f"{path} must be addable without -f"


def test_this_canary_file_is_tracked_without_force() -> None:
    # The canary itself: once committed, git ls-files must list it. Being
    # listed here proves it entered the index; the add happened without -f
    # (see task-governance-0032 handoff evidence).
    result = subprocess.run(
        ["git", "ls-files", "--", "tests/v1_governance/test_gitignore_test_pattern.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip(), "canary file must be tracked"
