from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import subprocess
from typing import Mapping


@dataclass(frozen=True)
class SubmoduleFinding:
    """A redacted, deterministic reason a repository is not session-ready."""

    code: str
    path: str

    def to_mapping(self) -> Mapping[str, str]:
        return {"code": self.code, "path": self.path}


@dataclass(frozen=True)
class SubmoduleReadiness:
    ready: bool
    findings: tuple[SubmoduleFinding, ...]

    def to_mapping(self) -> Mapping[str, object]:
        return {
            "ready": self.ready,
            "findings": [finding.to_mapping() for finding in self.findings],
        }


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except OSError:
        return None


def _tracked_gitlinks(root: Path) -> tuple[tuple[str, str], ...] | None:
    result = _run_git(root, "ls-files", "--stage", "-z")
    if result is None or result.returncode != 0:
        return None
    gitlinks: list[tuple[str, str]] = []
    for record in result.stdout.split("\0"):
        if not record:
            continue
        metadata, separator, relative_path = record.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            return None
        mode, object_id, _stage = fields
        if mode == "160000":
            gitlinks.append((relative_path.replace("\\", "/"), object_id))
    return tuple(gitlinks)


def _safe_child(root: Path, relative_path: str) -> Path | None:
    path = PurePosixPath(relative_path)
    if not relative_path or path.is_absolute() or ".." in path.parts:
        return None
    candidate = (root / Path(*path.parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _is_git_worktree(path: Path) -> bool:
    result = _run_git(path, "rev-parse", "--show-toplevel")
    if result is None or result.returncode != 0:
        return False
    return Path(result.stdout.strip()).resolve() == path.resolve()


def _is_dirty(path: Path) -> bool | None:
    result = _run_git(path, "status", "--porcelain=v1", "-z", "--ignore-submodules=dirty")
    if result is None or result.returncode != 0:
        return None
    return bool(result.stdout)


def _head(path: Path) -> str | None:
    result = _run_git(path, "rev-parse", "HEAD")
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def assess_submodule_readiness(root: Path) -> SubmoduleReadiness:
    """Assess tracked submodule checkout readiness without changing Git state."""
    top_level = _run_git(root, "rev-parse", "--show-toplevel")
    if top_level is None or top_level.returncode != 0:
        return SubmoduleReadiness(False, (SubmoduleFinding("repository-unavailable", "."),))

    repository = Path(top_level.stdout.strip()).resolve()
    gitlinks = _tracked_gitlinks(repository)
    if gitlinks is None:
        return SubmoduleReadiness(False, (SubmoduleFinding("repository-unavailable", "."),))

    findings: list[SubmoduleFinding] = []

    def inspect_nested(module_root: Path, display_path: str) -> None:
        dirty = _is_dirty(module_root)
        if dirty is None:
            findings.append(SubmoduleFinding("submodule-unavailable", display_path))
            return
        if dirty:
            findings.append(SubmoduleFinding("dirty-submodule", display_path))

        nested_gitlinks = _tracked_gitlinks(module_root)
        if nested_gitlinks is None:
            findings.append(SubmoduleFinding("submodule-unavailable", display_path))
            return
        for nested_relative_path, _expected_pin in nested_gitlinks:
            nested_display_path = f"{display_path}/{nested_relative_path}"
            nested_path = _safe_child(module_root, nested_relative_path)
            if nested_path is None:
                findings.append(SubmoduleFinding("invalid-submodule-path", nested_display_path))
            elif not _is_git_worktree(nested_path):
                findings.append(SubmoduleFinding("nested-uninitialized", nested_display_path))
            else:
                inspect_nested(nested_path, nested_display_path)

    for relative_path, expected_pin in gitlinks:
        module_path = _safe_child(repository, relative_path)
        if module_path is None:
            findings.append(SubmoduleFinding("invalid-submodule-path", relative_path))
            continue
        if not _is_git_worktree(module_path):
            findings.append(SubmoduleFinding("uninitialized", relative_path))
            continue
        checked_out_pin = _head(module_path)
        if checked_out_pin is None:
            findings.append(SubmoduleFinding("submodule-unavailable", relative_path))
            continue
        if checked_out_pin != expected_pin:
            findings.append(SubmoduleFinding("pin-mismatch", relative_path))
        inspect_nested(module_path, relative_path)

    ordered = tuple(sorted(set(findings), key=lambda finding: (finding.path, finding.code)))
    return SubmoduleReadiness(not ordered, ordered)
