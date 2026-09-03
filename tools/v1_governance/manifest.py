from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Mapping, cast
from urllib.parse import urlsplit

import yaml

from tools.v1_governance.errors import GovernanceError


KNOWN_LEGACY_WARNING_IDENTITIES: tuple[tuple[str, str, str], ...] = (
    ("flowzen-declaration", "vibemind-os", "spaces/flowzen/flowzen"),
    (
        "outer-moire-tracker-declaration",
        "vibemind-os",
        "spaces/desktop/Automation_ui/moire_tracker",
    ),
    ("voice-minibook-declaration", "voice", "external/minibook"),
)


@dataclass(frozen=True)
class ManifestIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


def _is_known_legacy_warning(
    *,
    repository_id: str,
    parent: str,
    relative_path: str,
    required: object,
    migration_state: str,
    initialization_state: str,
    expected_pin: str,
    gitlink_state: str,
    evidence_source: str,
    validation_state: str,
) -> bool:
    return (
        (repository_id, parent, relative_path) in KNOWN_LEGACY_WARNING_IDENTITIES
        and required is False
        and migration_state == "declared-legacy"
        and initialization_state == "absent"
        and expected_pin == "absent"
        and gitlink_state == "declared-without-gitlink"
        and evidence_source == "pinned-remote-tree"
        and validation_state == "pinned-not-live"
    )


def load_manifest(path: Path) -> Mapping[str, object]:
    """Load YAML and raise GovernanceError unless the root is a mapping."""
    try:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GovernanceError(f"cannot load manifest: {exc}") from exc
    if not isinstance(loaded, dict):
        raise GovernanceError("manifest root must be a mapping")
    if any(not isinstance(key, str) for key in loaded):
        raise GovernanceError("manifest keys must be strings")
    return cast(Mapping[str, object], loaded)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise GovernanceError(f"{field} must be a mapping")
    return cast(Mapping[str, object], value)


def _string(data: Mapping[str, object], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GovernanceError(f"{field} must be a non-empty string")
    return value


def _repositories(manifest: Mapping[str, object]) -> list[Mapping[str, object]]:
    value = manifest.get("repositories")
    if not isinstance(value, list):
        raise GovernanceError("repositories must be a list")
    repositories: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        repositories.append(_mapping(item, f"repositories[{index}]"))
    return repositories


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        shell=False,
        text=True,
        capture_output=True,
    )


def _gitmodules(repo_root: Path) -> dict[str, str]:
    path = repo_root / ".gitmodules"
    if not path.is_file():
        return {}
    result = _run_git(
        repo_root,
        "config",
        "-f",
        ".gitmodules",
        "--get-regexp",
        r"^submodule\..*\.path$",
    )
    if result.returncode == 1:
        return {}
    if result.returncode != 0:
        raise GovernanceError(result.stderr.strip() or "invalid .gitmodules")
    modules: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, module_path = line.partition(" ")
        if not separator or not key.endswith(".path"):
            raise GovernanceError("invalid .gitmodules path entry")
        remote_result = _run_git(
            repo_root,
            "config",
            "-f",
            ".gitmodules",
            "--get",
            f"{key[:-5]}.url",
        )
        remote = remote_result.stdout.strip()
        if not module_path or not remote:
            raise GovernanceError("every .gitmodules entry requires path and url")
        modules[module_path.replace("\\", "/")] = remote
    return modules


def _gitlink_paths(repo_root: Path) -> set[str]:
    """Every mode-160000 index entry path.

    Read from the index rather than from `.gitmodules`, because a gitlink can be
    committed with no submodule mapping at all -- in which case the index is the
    only place it appears. Deriving the coverage candidates from `.gitmodules`
    alone is what let finding B2 survive three pin chains.
    """
    result = _run_git(repo_root, "ls-files", "--stage", "-z")
    if result.returncode != 0:
        raise GovernanceError(result.stderr.strip() or "git ls-files failed")
    paths: set[str] = set()
    for record in result.stdout.split("\0"):
        if not record:
            continue
        metadata, separator, relative_path = record.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise GovernanceError("invalid git ls-files output")
        if fields[0] == "160000":
            paths.add(relative_path.replace("\\", "/"))
    return paths


def _git_entry(repo_root: Path, relative_path: str) -> tuple[str, str] | None:
    result = _run_git(repo_root, "ls-files", "--stage", "--", relative_path)
    if result.returncode != 0:
        raise GovernanceError(result.stderr.strip() or "git ls-files failed")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    fields = lines[0].split()
    if len(fields) < 2:
        raise GovernanceError("invalid git ls-files output")
    return fields[0], fields[1]


def _branch_exists(repo_root: Path, branch: str) -> bool:
    for reference in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"):
        result = _run_git(repo_root, "show-ref", "--verify", "--quiet", reference)
        if result.returncode == 0:
            return True
        if result.returncode not in (1,):
            raise GovernanceError(result.stderr.strip() or "git show-ref failed")
    return False


def _is_ancestor(repo_root: Path, commit: str) -> bool:
    result = _run_git(repo_root, "merge-base", "--is-ancestor", commit, "HEAD")
    if result.returncode in (0, 1):
        return result.returncode == 0
    return False


def _contains_secret_material(value: object, parent_key: str = "") -> bool:
    sensitive = ("password", "passwd", "token", "secret", "credential", "api_key")
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in sensitive):
                return True
            if _contains_secret_material(child, key_text):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret_material(item, parent_key) for item in value)
    if isinstance(value, str) and "://" in value:
        parsed = urlsplit(value)
        return parsed.username is not None or parsed.password is not None
    return False


def validate_manifest(repo_root: Path, manifest_path: Path) -> list[ManifestIssue]:
    """Return every deterministic manifest issue; return an empty list on success."""
    root = repo_root.resolve()
    manifest = load_manifest(manifest_path)
    issues: list[ManifestIssue] = []

    if manifest.get("schema_version") != 1:
        issues.append(ManifestIssue("schema-version", ".", "schema_version must be 1"))
    if _contains_secret_material(manifest):
        issues.append(ManifestIssue("secret-material", ".", "manifest contains secret material"))

    superproject = _mapping(manifest.get("superproject"), "superproject")
    current_branch = _string(superproject, "current_integration_branch")
    _string(superproject, "target_integration_branch")
    if not _branch_exists(root, current_branch):
        issues.append(
            ManifestIssue(
                "missing-integration-branch",
                ".",
                f"integration branch {current_branch!r} does not exist",
            )
        )

    superproject_id = _string(superproject, "id")
    repositories = _repositories(manifest)
    by_id: dict[str, Mapping[str, object]] = {}
    declared_ids: set[str] = set()
    declared_edges: set[tuple[str, str]] = set()
    for repository in repositories:
        repository_id = _string(repository, "id")
        parent = _string(repository, "parent")
        relative_path = _string(repository, "path").replace("\\", "/")
        if repository_id in declared_ids:
            issues.append(ManifestIssue("duplicate-id", relative_path, repository_id))
        declared_ids.add(repository_id)
        by_id[repository_id] = repository
        edge = (parent, relative_path)
        if edge in declared_edges:
            issues.append(ManifestIssue("duplicate-path", relative_path, f"duplicate edge under {parent}"))
        declared_edges.add(edge)

    local_modules_by_parent: dict[str, dict[str, str]] = {}
    local_paths_by_id: dict[str, Path] = {superproject_id: root}
    hex_pin = re.compile(r"^[0-9a-f]{40}$")
    for repository in repositories:
        repository_id = _string(repository, "id")
        parent = _string(repository, "parent")
        relative_path = _string(repository, "path").replace("\\", "/")
        kind = _string(repository, "kind")
        expected_pin = _string(repository, "expected_gitlink_pin")
        remote = _string(repository, "remote")
        _string(repository, "remote_role")
        migration_state = _string(repository, "migration_state")
        _string(repository, "owner")
        initialization_state = _string(repository, "initialization_state")
        gitlink_state = _string(repository, "gitlink_state")
        evidence = _mapping(repository.get("evidence"), f"evidence for {repository_id}")
        source = _string(evidence, "source")
        parent_pin = _string(evidence, "parent_pin")
        validation_state = _string(evidence, "validation_state")

        if parent != superproject_id and parent not in by_id:
            issues.append(ManifestIssue("missing-parent", relative_path, f"unknown parent {parent}"))
            continue
        if gitlink_state == "declared-without-gitlink":
            if expected_pin != "absent":
                issues.append(ManifestIssue("invalid-absent-pin", relative_path, "absent gitlink needs absent pin"))
        elif not hex_pin.fullmatch(expected_pin):
            issues.append(ManifestIssue("invalid-pin", relative_path, "expected pin must be a full SHA"))

        if source == "pinned-remote-tree":
            if validation_state != "pinned-not-live":
                issues.append(
                    ManifestIssue("invalid-evidence-state", relative_path, "pinned evidence is not live")
                )
            parent_repository = by_id.get(parent)
            if parent_repository is None:
                issues.append(ManifestIssue("missing-parent", relative_path, f"unknown parent {parent}"))
                continue
            expected_parent_pin = _string(parent_repository, "expected_gitlink_pin")
            if parent_pin != expected_parent_pin:
                issues.append(
                    ManifestIssue("parent-pin-mismatch", relative_path, "evidence parent pin differs")
                )
            parent_initialization = _string(parent_repository, "initialization_state")
            if initialization_state not in {"unobserved", "absent"}:
                issues.append(
                    ManifestIssue(
                        "parent-uninitialized",
                        relative_path,
                        f"child cannot be locally observed under {parent_initialization} parent",
                    )
                )
            if gitlink_state == "declared-without-gitlink":
                severity = "warning" if _is_known_legacy_warning(
                    repository_id=repository_id,
                    parent=parent,
                    relative_path=relative_path,
                    required=repository.get("required"),
                    migration_state=migration_state,
                    initialization_state=initialization_state,
                    expected_pin=expected_pin,
                    gitlink_state=gitlink_state,
                    evidence_source=source,
                    validation_state=validation_state,
                ) else "error"
                issues.append(
                    ManifestIssue(
                        "declared-without-gitlink",
                        relative_path,
                        "pinned parent declares path without a gitlink",
                        severity,
                    )
                )
            continue

        if source != "local-git" or validation_state != "local":
            issues.append(ManifestIssue("invalid-evidence-state", relative_path, "unknown evidence state"))
            continue
        if parent not in local_paths_by_id:
            issues.append(
                ManifestIssue("parent-uninitialized", relative_path, "parent is not locally initialized")
            )
            continue
        parent_root = local_paths_by_id[parent]
        if not _is_ancestor(parent_root, parent_pin):
            issues.append(
                ManifestIssue(
                    "parent-pin-mismatch",
                    relative_path,
                    "local evidence parent pin is not in current ancestry",
                )
            )
        resolved_path = (parent_root / relative_path).resolve()
        if not resolved_path.is_relative_to(root):
            issues.append(ManifestIssue("path-outside-root", relative_path, "path escapes repository"))
            continue

        if kind == "submodule":
            modules = local_modules_by_parent.setdefault(parent, _gitmodules(parent_root))
            if relative_path not in modules:
                issues.append(
                    ManifestIssue("missing-gitmodules-entry", relative_path, "submodule is not declared")
                )
                continue
            entry = _git_entry(parent_root, relative_path)
            if entry is None or entry[0] != "160000":
                issues.append(
                    ManifestIssue(
                        "declared-without-gitlink",
                        relative_path,
                        "path is declared in .gitmodules without a gitlink",
                    )
                )
                continue
            if entry[1] != expected_pin:
                issues.append(ManifestIssue("pin-mismatch", relative_path, "gitlink pin differs"))
            if modules[relative_path] != remote:
                issues.append(
                    ManifestIssue("remote-mismatch", relative_path, "declared remote differs from .gitmodules")
                )
            initialized = (resolved_path / ".git").exists()
            if initialization_state == "initialized":
                if not resolved_path.exists():
                    issues.append(ManifestIssue("missing-path", relative_path, "initialized path is missing"))
                elif not initialized:
                    issues.append(
                        ManifestIssue("initialization-state-mismatch", relative_path, "submodule is not initialized")
                    )
                else:
                    local_paths_by_id[repository_id] = resolved_path
            elif initialization_state == "uninitialized":
                if initialized:
                    issues.append(
                        ManifestIssue("initialization-state-mismatch", relative_path, "submodule is initialized")
                    )
            else:
                issues.append(
                    ManifestIssue("invalid-initialization-state", relative_path, initialization_state)
                )
        elif not resolved_path.exists():
            issues.append(ManifestIssue("missing-path", relative_path, "required path does not exist"))

    # Coverage is keyed on every locally available parent, not only on those that
    # already have a declared child: `local_modules_by_parent` is populated as a
    # side effect of iterating declared repositories, so a parent with zero
    # declared children never entered it -- the `coding-engine` case before its
    # children were declared. And the candidate set is the union of both path
    # sources, because a gitlink absent from `.gitmodules` appears only in the
    # index. Either half alone leaves finding B2 undetectable.
    for parent, parent_root in sorted(local_paths_by_id.items()):
        modules = local_modules_by_parent.setdefault(parent, _gitmodules(parent_root))
        observed_paths = set(modules) | _gitlink_paths(parent_root)
        expected_paths = {
            _string(repository, "path").replace("\\", "/")
            for repository in repositories
            if _string(repository, "parent") == parent
        }
        for module_path in sorted(observed_paths - expected_paths):
            issues.append(
                ManifestIssue("undeclared-submodule", module_path, "submodule is absent from manifest")
            )
    return issues
