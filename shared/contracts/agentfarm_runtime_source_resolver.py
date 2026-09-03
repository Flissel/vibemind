"""Fail-closed local resolver for an admitted AgentFarm source record.

This module intentionally verifies only a local Git source snapshot.  It does
not select, build, route, enable, deploy, reach, approve, or execute a runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
from threading import Thread
from typing import Mapping, Sequence

from shared.contracts.validate import (
    ContractValidationError,
    validate_agentfarm_runtime_admission_bundle,
)


_GIT_TIMEOUT_SECONDS = 5
_PROCESS_CLEANUP_SECONDS = 0.05
_MAX_GIT_OUTPUT_BYTES = 1_048_576
_MAX_BLOB_BYTES = 8 * 1_048_576
_MAX_ARCHIVE_BYTES = 64 * 1_048_576
_MAX_ALTERNATES_BYTES = 65_536
_MAX_ALTERNATE_DEPTH = 16
_MAX_ALTERNATE_DIRECTORIES = 64
_REGULAR_BLOB_MODES = {b"100644", b"100755"}
_NONCLAIMS = (
    "runtime_enabled",
    "built",
    "routed",
    "deployed",
    "reachable",
    "approved",
    "executed",
    "identity_ownership",
)

if os.name == "nt":
    _FIXED_GIT_CANDIDATES = (
        Path(r"C:\Program Files\Git\cmd\git.exe"),
        Path(r"C:\Program Files\Git\bin\git.exe"),
    )
else:
    _FIXED_GIT_CANDIDATES = (Path("/usr/bin/git"), Path("/bin/git"))


def _resolve_trusted_git_executable() -> Path | None:
    """Resolve Git once from fixed locations, then the process PATH boundary."""
    discovered = shutil.which("git")
    candidates = (*_FIXED_GIT_CANDIDATES, *((Path(discovered),) if discovered else ()))
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_file() and resolved.is_absolute():
            return resolved
    return None


_GIT_EXECUTABLE = _resolve_trusted_git_executable()


class AgentFarmRuntimeSourceResolutionError(RuntimeError):
    """A stable, redacted reason that a local source snapshot was rejected."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AgentFarmVerifiedLocalSourceReceipt:
    """Immutable receipt for a verified local source snapshot and nothing more."""

    repository_identity: str
    commit_sha: str
    tree_sha: str
    source_tree_digest: str
    entrypoint_path: str
    entrypoint_digest: str
    build_manifest_path: str
    build_manifest_digest: str
    claims: tuple[str, ...] = ("verified_local_source",)
    nonclaims: tuple[str, ...] = _NONCLAIMS


class _LocalGitError(Exception):
    pass


def resolve_agentfarm_runtime_source_admission(
    documents: Mapping[str, Mapping[str, object]],
    local_repository: Path,
    allowed_root: Path,
    expected_canonical_repository_identity: str,
) -> AgentFarmVerifiedLocalSourceReceipt:
    """Resolve one exact admission bundle against a contained local repository.

    ``expected_canonical_repository_identity`` is caller-supplied trusted input;
    repository ownership is deliberately outside this resolver's claims.
    """
    try:
        validate_agentfarm_runtime_admission_bundle(documents)
    except (ContractValidationError, KeyError, TypeError, ValueError):
        raise AgentFarmRuntimeSourceResolutionError("invalid_admission_bundle") from None

    provenance = documents["agentfarm-runtime-source-provenance"]
    repository = _mapping(provenance["repository"])
    revision = _mapping(provenance["revision"])
    entrypoint = _mapping(provenance["entrypoint"])
    build_manifest = _mapping(provenance["build_manifest"])
    canonical_identity = _text(repository["canonical_identity"])
    if canonical_identity != expected_canonical_repository_identity:
        raise AgentFarmRuntimeSourceResolutionError("repository_identity_mismatch")

    root = _resolve_path(allowed_root, "allowed_root_unavailable")
    repo = _resolve_path(local_repository, "repository_unavailable")
    _require_contained(repo, root, "repository_outside_allowed_root")

    try:
        if _git_text(repo, ("rev-parse", "--is-inside-work-tree")) != "true":
            raise _LocalGitError
        git_dir = _resolve_path(
            Path(_git_text(repo, ("rev-parse", "--absolute-git-dir"))),
            "git_directory_unavailable",
        )
        _require_contained(git_dir, root, "git_directory_outside_allowed_root")
        common_dir = _resolve_path(
            Path(_git_text(repo, ("rev-parse", "--path-format=absolute", "--git-common-dir"))),
            "git_common_directory_unavailable",
        )
        _require_contained(common_dir, root, "git_common_directory_outside_allowed_root")
        _require_empty_common_attributes(common_dir)
        object_dir = _resolve_path(common_dir / "objects", "object_directory_unavailable")
        _require_contained(object_dir, root, "object_directory_outside_allowed_root")
        _require_contained_alternates(object_dir, root)

        commit_sha = _text(revision["commit_sha"])
        tree_sha = _text(revision["tree_sha"])
        _require_commit(repo, commit_sha)
        if _git_text(repo, ("rev-parse", f"{commit_sha}^{{tree}}")) != tree_sha:
            raise AgentFarmRuntimeSourceResolutionError("tree_mismatch")
        _assert_regular_source_tree(repo, tree_sha)
        _verify_blob(repo, tree_sha, _mapping(entrypoint))
        _verify_blob(repo, tree_sha, _mapping(build_manifest))
        _verify_archive(repo, commit_sha, _text(revision["source_tree_digest"]))
    except AgentFarmRuntimeSourceResolutionError:
        raise
    except _LocalGitError:
        raise AgentFarmRuntimeSourceResolutionError("local_git_unavailable") from None

    return AgentFarmVerifiedLocalSourceReceipt(
        repository_identity=canonical_identity,
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        source_tree_digest=_text(revision["source_tree_digest"]),
        entrypoint_path=_text(entrypoint["path"]),
        entrypoint_digest=_text(entrypoint["digest"]),
        build_manifest_path=_text(build_manifest["path"]),
        build_manifest_digest=_text(build_manifest["digest"]),
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AgentFarmRuntimeSourceResolutionError("invalid_admission_bundle")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise AgentFarmRuntimeSourceResolutionError("invalid_admission_bundle")
    return value


def _resolve_path(path: Path, code: str) -> Path:
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        raise AgentFarmRuntimeSourceResolutionError(code) from None


def _require_contained(path: Path, root: Path, code: str) -> None:
    try:
        path.relative_to(root)
    except ValueError:
        raise AgentFarmRuntimeSourceResolutionError(code) from None


def _require_contained_alternates(object_dir: Path, root: Path) -> None:
    pending = [(object_dir, 0)]
    visited: set[Path] = set()
    while pending:
        current, depth = pending.pop()
        if depth > _MAX_ALTERNATE_DEPTH or len(visited) >= _MAX_ALTERNATE_DIRECTORIES:
            raise AgentFarmRuntimeSourceResolutionError("object_alternate_limit")
        try:
            current = current.resolve(strict=True)
        except (OSError, RuntimeError):
            raise AgentFarmRuntimeSourceResolutionError("object_alternate_unavailable") from None
        _require_contained(current, root, "object_alternate_outside_allowed_root")
        if current in visited:
            continue
        visited.add(current)
        alternates = current / "info" / "alternates"
        if not alternates.exists():
            continue
        try:
            with alternates.open("rb") as handle:
                data = handle.read(_MAX_ALTERNATES_BYTES + 1)
        except OSError:
            raise AgentFarmRuntimeSourceResolutionError("object_alternate_unavailable") from None
        if len(data) > _MAX_ALTERNATES_BYTES:
            raise AgentFarmRuntimeSourceResolutionError("object_alternate_too_large")
        for raw_path in data.splitlines():
            if not raw_path.strip():
                continue
            try:
                decoded = raw_path.decode("utf-8")
            except UnicodeDecodeError:
                raise AgentFarmRuntimeSourceResolutionError("object_alternate_unavailable") from None
            candidate = Path(decoded)
            if not candidate.is_absolute():
                candidate = current / candidate
            try:
                resolved = candidate.resolve(strict=False)
            except (OSError, RuntimeError):
                raise AgentFarmRuntimeSourceResolutionError("object_alternate_unavailable") from None
            _require_contained(resolved, root, "object_alternate_outside_allowed_root")
            pending.append((resolved, depth + 1))


def _require_empty_common_attributes(common_dir: Path) -> None:
    attributes = common_dir / "info" / "attributes"
    if not attributes.exists():
        return
    try:
        with attributes.open("rb") as handle:
            nonempty = bool(handle.read(1))
    except OSError:
        raise AgentFarmRuntimeSourceResolutionError(
            "git_common_attributes_unavailable"
        ) from None
    if nonempty:
        raise AgentFarmRuntimeSourceResolutionError(
            "git_common_attributes_not_empty"
        )


def _sanitized_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_PAGER": "cat",
            "PAGER": "cat",
            "GIT_EDITOR": "true",
            "EDITOR": "true",
            "VISUAL": "true",
            "LC_ALL": "C",
        }
    )
    return environment


def _git_argv(repo: Path, arguments: Sequence[str]) -> list[str]:
    if _GIT_EXECUTABLE is None:
        raise _LocalGitError
    return [
        str(_GIT_EXECUTABLE),
        "--no-replace-objects",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "tar.umask=0002",
        "-C",
        str(repo),
        *arguments,
    ]


def _bounded_process_cleanup(process: subprocess.Popen[bytes], reader: Thread) -> None:
    try:
        process.kill()
    except OSError:
        pass
    reader.join(_PROCESS_CLEANUP_SECONDS)
    if not reader.is_alive() and process.stdout is not None:
        try:
            process.stdout.close()
        except OSError:
            pass
    try:
        process.wait(timeout=_PROCESS_CLEANUP_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _git_output(
    repo: Path,
    arguments: Sequence[str],
    maximum_bytes: int = _MAX_GIT_OUTPUT_BYTES,
    too_large_code: str = "git_output_too_large",
) -> bytes:
    try:
        process = subprocess.Popen(
            _git_argv(repo, arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            env=_sanitized_environment(),
        )
    except OSError:
        raise _LocalGitError from None
    assert process.stdout is not None
    captured: list[bytes] = []
    reader_failed: list[bool] = []

    def read_stdout() -> None:
        try:
            captured.append(process.stdout.read(maximum_bytes + 1))
        except OSError:
            reader_failed.append(True)

    reader = Thread(target=read_stdout, daemon=True)
    reader.start()
    reader.join(_GIT_TIMEOUT_SECONDS)
    if reader.is_alive():
        _bounded_process_cleanup(process, reader)
        raise _LocalGitError
    if reader_failed or len(captured) != 1:
        _bounded_process_cleanup(process, reader)
        raise _LocalGitError
    output = captured[0]
    try:
        if len(output) > maximum_bytes:
            raise AgentFarmRuntimeSourceResolutionError(too_large_code)
        if process.wait(timeout=_PROCESS_CLEANUP_SECONDS) != 0:
            raise _LocalGitError
        process.stdout.close()
        return output
    except AgentFarmRuntimeSourceResolutionError:
        _bounded_process_cleanup(process, reader)
        raise
    except _LocalGitError:
        _bounded_process_cleanup(process, reader)
        raise
    except (OSError, subprocess.TimeoutExpired):
        _bounded_process_cleanup(process, reader)
        raise _LocalGitError from None


def _git_text(repo: Path, arguments: Sequence[str]) -> str:
    try:
        return _git_output(repo, arguments).decode("ascii").strip()
    except UnicodeDecodeError:
        raise _LocalGitError from None


def _require_commit(repo: Path, commit_sha: str) -> None:
    try:
        object_type = _git_text(repo, ("cat-file", "-t", commit_sha))
    except _LocalGitError:
        raise AgentFarmRuntimeSourceResolutionError("commit_unavailable") from None
    if object_type != "commit":
        raise AgentFarmRuntimeSourceResolutionError("commit_unavailable")


def _assert_regular_source_tree(repo: Path, tree_sha: str) -> None:
    entries = _git_output(repo, ("ls-tree", "-r", "-z", "--full-tree", tree_sha))
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, _path = entry.split(b"\t", 1)
            mode, object_type, _object_sha = metadata.split(b" ", 2)
        except ValueError:
            raise AgentFarmRuntimeSourceResolutionError("source_tree_unsafe") from None
        if mode not in _REGULAR_BLOB_MODES or object_type != b"blob":
            raise AgentFarmRuntimeSourceResolutionError("source_tree_unsafe")


def _verify_blob(repo: Path, tree_sha: str, declaration: Mapping[str, object]) -> None:
    path = _text(declaration["path"])
    expected_digest = _text(declaration["digest"])
    raw_entry = _git_output(repo, ("ls-tree", "-z", "--full-tree", tree_sha, "--", path))
    entries = [entry for entry in raw_entry.split(b"\0") if entry]
    if len(entries) != 1:
        raise AgentFarmRuntimeSourceResolutionError("path_missing")
    try:
        metadata, entry_path = entries[0].split(b"\t", 1)
        mode, object_type, object_sha = metadata.split(b" ", 2)
    except ValueError:
        raise AgentFarmRuntimeSourceResolutionError("path_not_regular_blob") from None
    if entry_path != path.encode("utf-8"):
        raise AgentFarmRuntimeSourceResolutionError("path_missing")
    if mode not in _REGULAR_BLOB_MODES or object_type != b"blob":
        raise AgentFarmRuntimeSourceResolutionError("path_not_regular_blob")
    try:
        blob_oid = object_sha.decode("ascii")
    except UnicodeDecodeError:
        raise AgentFarmRuntimeSourceResolutionError("path_not_regular_blob") from None
    blob = _git_output(repo, ("cat-file", "blob", blob_oid), _MAX_BLOB_BYTES)
    if _sha256(blob) != expected_digest:
        raise AgentFarmRuntimeSourceResolutionError("blob_digest_mismatch")


def _verify_archive(repo: Path, commit_sha: str, expected_digest: str) -> None:
    archive = _git_output(
        repo,
        ("archive", "--format=tar", commit_sha),
        _MAX_ARCHIVE_BYTES,
        "archive_too_large",
    )
    if _sha256(archive) != expected_digest:
        raise AgentFarmRuntimeSourceResolutionError("archive_digest_mismatch")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
