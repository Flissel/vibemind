from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


TOKEN = "0" * 26
IDENTITY = "github.com/Flissel/Autogen_AgentFarm"


def ref(kind: str) -> str:
    return f"{kind}_v1_{TOKEN}"


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return completed.stdout


def init_repo(tmp_path: Path) -> tuple[Path, Path]:
    allowed_root = tmp_path / "allowed"
    repo = allowed_root / "agentfarm"
    repo.mkdir(parents=True)
    git(repo, "init")
    git(repo, "config", "user.email", "tests@example.invalid")
    git(repo, "config", "user.name", "Contract Tests")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "src" / "agentfarm").mkdir(parents=True)
    (repo / "src" / "agentfarm" / "main.py").write_bytes(b'print("hello")\n')
    (repo / "pyproject.toml").write_bytes(b"[build-system]\nrequires = []\n")
    git(repo, "add", "src/agentfarm/main.py", "pyproject.toml")
    commit_env = {
        "GIT_AUTHOR_DATE": "2026-08-04T10:00:00Z",
        "GIT_COMMITTER_DATE": "2026-08-04T10:00:00Z",
    }
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        env={**os.environ, **commit_env},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return repo, allowed_root


def admission_bundle(repo: Path) -> dict[str, dict[str, object]]:
    commit_sha = git(repo, "rev-parse", "HEAD").decode().strip()
    tree_sha = git(repo, "rev-parse", "HEAD^{tree}").decode().strip()
    archive = git(repo, "archive", "--format=tar", commit_sha)
    request = {
        "contract_version": "v1",
        "request_id": ref("request"),
        "brain_plan_ref": ref("plan"),
        "task_ref": ref("task"),
        "project_ref": ref("project"),
        "trace_id": ref("trace"),
        "space_id": "agentfarm",
        "objective": "Verify local source only.",
        "requested_at": "2026-08-04T10:00:00Z",
        "clarification": {
            "status": "resolved",
            "questions": [],
            "resolved_at": "2026-08-04T10:00:00Z",
        },
        "risk_class": "medium",
        "hard_bounds": {
            "timeout_seconds": 600,
            "max_steps": 12,
            "max_retries": 2,
            "max_cost_minor": 5000,
            "currency": "EUR",
            "max_concurrency": 2,
            "max_team_members": 2,
        },
        "quote_ref": ref("quote"),
        "approval_ref": ref("approval"),
        "idempotency_key": "agentfarm-resolver-0004",
    }
    provenance = {
        "contract_version": "v1",
        "provenance_id": ref("source"),
        "request_id": request["request_id"],
        "space_id": "agentfarm",
        "repository": {
            "repository_id": ref("repository"),
            "canonical_identity": IDENTITY,
            "identity_digest": sha256(IDENTITY.encode()),
        },
        "revision": {
            "kind": "commit",
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "source_tree_digest": sha256(archive),
        },
        "entrypoint": {
            "path": "src/agentfarm/main.py",
            "digest": sha256((repo / "src" / "agentfarm" / "main.py").read_bytes()),
        },
        "build_manifest": {
            "path": "pyproject.toml",
            "digest": sha256((repo / "pyproject.toml").read_bytes()),
        },
        "record_digest": "",
        "captured_at": "2026-08-04T10:00:00Z",
    }
    bundle = {
        "agent-team-request": request,
        "agentfarm-runtime-source-provenance": provenance,
    }
    refresh_record_digest(bundle)
    return bundle


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def refresh_record_digest(bundle: dict[str, dict[str, object]]) -> None:
    provenance = bundle["agentfarm-runtime-source-provenance"]
    digest_input = deepcopy(provenance)
    del digest_input["record_digest"]
    provenance["record_digest"] = sha256(
        json.dumps(
            digest_input,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def resolve(bundle: dict[str, dict[str, object]], repo: Path, allowed_root: Path):
    try:
        resolver = importlib.import_module(
            "shared.contracts.agentfarm_runtime_source_resolver"
        )
    except ModuleNotFoundError:
        pytest.fail("runtime source resolver module is missing")
    return resolver.resolve_agentfarm_runtime_source_admission(
        bundle,
        repo,
        allowed_root,
        IDENTITY,
    )


def assert_failure(
    expected_code: str,
    bundle: dict[str, dict[str, object]],
    repo: Path,
    allowed_root: Path,
) -> None:
    try:
        resolver = importlib.import_module(
            "shared.contracts.agentfarm_runtime_source_resolver"
        )
    except ModuleNotFoundError:
        pytest.fail("runtime source resolver module is missing")
    with pytest.raises(resolver.AgentFarmRuntimeSourceResolutionError) as raised:
        resolve(bundle, repo, allowed_root)
    assert raised.value.code == expected_code
    assert str(raised.value) == expected_code


def test_resolves_pinned_clean_local_source_with_deterministic_nonclaims(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]
    assert receipt.claims == ("verified_local_source",)
    assert receipt.nonclaims == (
        "runtime_enabled",
        "built",
        "routed",
        "deployed",
        "reachable",
        "approved",
        "executed",
        "identity_ownership",
    )
    with pytest.raises((AttributeError, TypeError)):
        receipt.commit_sha = "different"  # type: ignore[misc]


def test_rejects_invalid_bundle_before_touching_local_repository(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    del bundle["agentfarm-runtime-source-provenance"]

    assert_failure("invalid_admission_bundle", bundle, tmp_path / "missing", allowed_root)


@pytest.mark.parametrize("mutation", ["staged", "unstaged", "untracked"])
def test_resolves_pinned_commit_despite_dirty_or_untracked_repository(
    mutation: str, tmp_path: Path
) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    if mutation == "staged":
        (repo / "pyproject.toml").write_bytes(b"changed\n")
        git(repo, "add", "pyproject.toml")
    elif mutation == "unstaged":
        (repo / "pyproject.toml").write_bytes(b"changed\n")
    else:
        (repo / "untracked.txt").write_bytes(b"untracked\n")

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]


def test_resolves_pinned_commit_despite_head_divergence(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    (repo / "later.txt").write_bytes(b"later\n")
    git(repo, "add", "later.txt")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "later"],
        env={**os.environ, "GIT_AUTHOR_DATE": "2026-08-04T10:01:00Z", "GIT_COMMITTER_DATE": "2026-08-04T10:01:00Z"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]


def test_resolves_pinned_commit_from_detached_worktree(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    detached_worktree = allowed_root / "detached-worktree"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(detached_worktree), "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    receipt = resolve(bundle, detached_worktree, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]


@pytest.mark.parametrize(
    ("path", "value", "expected_code"),
    [
        (("repository", "canonical_identity"), "github.com/Flissel/Other", "repository_identity_mismatch"),
        (("revision", "commit_sha"), "a" * 40, "commit_unavailable"),
        (("revision", "tree_sha"), "b" * 40, "tree_mismatch"),
        (("entrypoint", "digest"), "sha256:" + "a" * 64, "blob_digest_mismatch"),
        (("build_manifest", "digest"), "sha256:" + "b" * 64, "blob_digest_mismatch"),
        (("revision", "source_tree_digest"), "sha256:" + "c" * 64, "archive_digest_mismatch"),
        (("entrypoint", "path"), "src/agentfarm/missing.py", "path_missing"),
    ],
)
def test_rejects_declared_source_mismatches(
    path: tuple[str, str], value: str, expected_code: str, tmp_path: Path
) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    target = bundle["agentfarm-runtime-source-provenance"]
    target[path[0]][path[1]] = value
    if path == ("repository", "canonical_identity"):
        target["repository"]["identity_digest"] = sha256(value.encode())
    refresh_record_digest(bundle)

    assert_failure(expected_code, bundle, repo, allowed_root)


def test_rejects_repository_outside_allowed_root(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    outside_root = tmp_path / "other-root"
    outside_root.mkdir()

    assert_failure("repository_outside_allowed_root", bundle, repo, outside_root)


def test_rejects_git_directory_outside_allowed_root(tmp_path: Path) -> None:
    allowed_root = tmp_path / "allowed"
    repo = allowed_root / "agentfarm"
    external_git_dir = tmp_path / "external-git-dir"
    repo.mkdir(parents=True)
    subprocess.run(
        ["git", "init", f"--separate-git-dir={external_git_dir}", str(repo)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    git(repo, "config", "user.email", "tests@example.invalid")
    git(repo, "config", "user.name", "Contract Tests")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "src" / "agentfarm").mkdir(parents=True)
    (repo / "src" / "agentfarm" / "main.py").write_bytes(b"main\n")
    (repo / "pyproject.toml").write_bytes(b"manifest\n")
    git(repo, "add", ".")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        env={**os.environ, "GIT_AUTHOR_DATE": "2026-08-04T10:00:00Z", "GIT_COMMITTER_DATE": "2026-08-04T10:00:00Z"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    bundle = admission_bundle(repo)

    assert_failure("git_directory_outside_allowed_root", bundle, repo, allowed_root)


def test_rejects_object_alternate_outside_allowed_root(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    alternate = tmp_path / "alternate-objects"
    alternate.mkdir()
    alternates_file = repo / ".git" / "objects" / "info" / "alternates"
    alternates_file.parent.mkdir(exist_ok=True)
    alternates_file.write_text(str(alternate.resolve()) + "\n", encoding="utf-8")

    assert_failure("object_alternate_outside_allowed_root", bundle, repo, allowed_root)


def test_rejects_nested_object_alternate_outside_allowed_root(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    nested_object_dir = repo / ".git" / "nested-objects"
    nested_object_dir.mkdir()
    (nested_object_dir / "info").mkdir()
    (repo / ".git" / "objects" / "info" / "alternates").write_text(
        "../nested-objects\n", encoding="utf-8"
    )
    (nested_object_dir / "info" / "alternates").write_text(
        str((tmp_path / "outside-objects").resolve()) + "\n", encoding="utf-8"
    )

    assert_failure("object_alternate_outside_allowed_root", bundle, repo, allowed_root)


def test_sanitized_git_environment_ignores_inherited_git_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")
    monkeypatch.setenv("GIT_DIR", "caller-controlled")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "caller-controlled")

    environment = resolver._sanitized_environment()

    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_ATTR_NOSYSTEM"] == "1"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert environment["GIT_NO_LAZY_FETCH"] == "1"
    assert environment["LC_ALL"] == "C"
    assert "GIT_DIR" not in environment


def test_git_argv_disables_replace_objects_and_external_attributes(tmp_path: Path) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")
    repo = tmp_path.resolve()

    arguments = resolver._git_argv(repo, ("cat-file", "-t", "a" * 40))

    assert Path(arguments[0]).is_absolute()
    assert arguments[1:6] == [
        "--no-replace-objects",
        "-c",
        f"core.attributesFile={os.devnull}",
        "-c",
        "tar.umask=0002",
    ]
    assert arguments[6:8] == ["-C", str(repo)]


def test_rejects_replaced_commit_instead_of_verifying_replacement(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    pinned_commit = git(repo, "rev-parse", "HEAD").decode().strip()
    (repo / "src" / "agentfarm" / "main.py").write_bytes(b'print("replacement")\n')
    git(repo, "add", "src/agentfarm/main.py")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "replacement"],
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-08-04T10:01:00Z",
            "GIT_COMMITTER_DATE": "2026-08-04T10:01:00Z",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    replacement_commit = git(repo, "rev-parse", "HEAD").decode().strip()
    bundle = admission_bundle(repo)
    bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"] = pinned_commit
    refresh_record_digest(bundle)
    git(repo, "replace", pinned_commit, replacement_commit)

    assert_failure("tree_mismatch", bundle, repo, allowed_root)


def test_repository_external_attributes_cannot_change_archive(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    external_attributes = tmp_path / "external.attributes"
    external_attributes.write_text("* export-ignore\n", encoding="utf-8")
    git(repo, "config", "core.attributesFile", str(external_attributes.resolve()))

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]


def test_rejects_nonempty_common_git_attributes(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    attributes = repo / ".git" / "info" / "attributes"
    attributes.write_text("* export-ignore\n", encoding="utf-8")

    assert_failure("git_common_attributes_not_empty", bundle, repo, allowed_root)


def test_accepts_empty_common_git_attributes(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    attributes = repo / ".git" / "info" / "attributes"
    attributes.write_bytes(b"")

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.commit_sha == bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"]


def test_repository_tar_umask_cannot_change_canonical_archive(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    bundle = admission_bundle(repo)
    git(repo, "config", "tar.umask", "0077")

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.source_tree_digest == bundle["agentfarm-runtime-source-provenance"]["revision"]["source_tree_digest"]


def test_committed_gitattributes_still_controls_canonical_archive(tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    (repo / ".gitattributes").write_text("excluded.txt export-ignore\n", encoding="utf-8")
    (repo / "excluded.txt").write_text("excluded from archive\n", encoding="utf-8")
    git(repo, "add", ".gitattributes", "excluded.txt")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "archive attributes"],
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2026-08-04T10:02:00Z",
            "GIT_COMMITTER_DATE": "2026-08-04T10:02:00Z",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    bundle = admission_bundle(repo)

    receipt = resolve(bundle, repo, allowed_root)

    assert receipt.source_tree_digest == bundle["agentfarm-runtime-source-provenance"]["revision"]["source_tree_digest"]


def test_git_executable_fallback_resolves_process_path_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")
    executable = Path(sys.executable).resolve()
    monkeypatch.setattr(resolver, "_FIXED_GIT_CANDIDATES", ())
    monkeypatch.setattr(resolver.shutil, "which", lambda command: str(executable))

    assert resolver._resolve_trusted_git_executable() == executable


def test_git_output_reader_error_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")

    class BrokenPipe:
        def read(self, maximum: int) -> bytes:
            raise OSError("redacted reader failure")

        def close(self) -> None:
            return None

    class BrokenProcess:
        args = ["git"]
        stdout = BrokenPipe()

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 1

    monkeypatch.setattr(resolver.subprocess, "Popen", lambda *args, **kwargs: BrokenProcess())

    with pytest.raises(resolver._LocalGitError):
        resolver._git_output(tmp_path, ("rev-parse", "HEAD"))


def test_git_output_timeout_cleanup_is_bounded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")

    class HoldingPipe:
        def __init__(self) -> None:
            from threading import Event

            self.closed = Event()

        def read(self, maximum: int) -> bytes:
            self.closed.wait(0.25)
            return b""

        def close(self) -> None:
            self.closed.set()

    class HoldingProcess:
        args = ["git"]

        def __init__(self) -> None:
            self.stdout = HoldingPipe()

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            if timeout is None:
                time.sleep(0.25)
                return 1
            raise subprocess.TimeoutExpired(self.args, timeout)

    monkeypatch.setattr(resolver, "_GIT_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(resolver.subprocess, "Popen", lambda *args, **kwargs: HoldingProcess())
    started = time.monotonic()

    with pytest.raises(resolver._LocalGitError):
        resolver._git_output(tmp_path, ("rev-parse", "HEAD"))

    assert time.monotonic() - started < 0.15


def test_real_buffered_pipe_cleanup_returns_before_inherited_writer_exits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")
    real_popen = subprocess.Popen
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    writer_holder = real_popen(
        [sys.executable, "-c", "import time;time.sleep(0.6)"],
        close_fds=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)

    class PipeProcess:
        args = ["git"]

        def __init__(self) -> None:
            self.stdout = os.fdopen(read_fd, "rb")

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 1

    pipe_process = PipeProcess()

    monkeypatch.setattr(resolver, "_GIT_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(resolver.subprocess, "Popen", lambda *args, **kwargs: pipe_process)
    started = time.monotonic()

    with pytest.raises(resolver._LocalGitError):
        resolver._git_output(tmp_path, ("rev-parse", "HEAD"))

    elapsed = time.monotonic() - started
    writer_holder.wait(timeout=1)
    pipe_process.stdout.close()
    assert elapsed < 0.3


def test_git_output_rejects_oversized_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resolver = importlib.import_module("shared.contracts.agentfarm_runtime_source_resolver")

    class OversizedProcess:
        args = ["git"]
        stdout = io.BytesIO(b"12345")

        def kill(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    monkeypatch.setattr(resolver.subprocess, "Popen", lambda *args, **kwargs: OversizedProcess())

    with pytest.raises(resolver.AgentFarmRuntimeSourceResolutionError) as raised:
        resolver._git_output(tmp_path, ("rev-parse", "HEAD"), maximum_bytes=4)

    assert raised.value.code == "git_output_too_large"


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_rejects_symlink_or_gitlink_anywhere_in_committed_tree(mode: str, tmp_path: Path) -> None:
    repo, allowed_root = init_repo(tmp_path)
    object_sha = (
        git(repo, "rev-parse", "HEAD").decode().strip()
        if mode == "160000"
        else git(repo, "hash-object", "-w", "--stdin", input_bytes=b"target\n").decode().strip()
    )
    git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{object_sha},unsafe-entry")
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "unsafe entry"],
        env={**os.environ, "GIT_AUTHOR_DATE": "2026-08-04T10:01:00Z", "GIT_COMMITTER_DATE": "2026-08-04T10:01:00Z"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    bundle = admission_bundle(repo)

    assert_failure("source_tree_unsafe", bundle, repo, allowed_root)
