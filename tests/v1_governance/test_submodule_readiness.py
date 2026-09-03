from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from tools.v1_governance import cli
from tools.v1_governance.submodule_readiness import assess_submodule_readiness


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def repository(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "tests@example.invalid")
    git(path, "config", "user.name", "V1 Governance Tests")
    (path / "README.md").write_text("baseline\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "test: initialize repository")
    return path


def submodule_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    nested = repository(tmp_path / "nested-source")
    child = repository(tmp_path / "component-source")
    git(child, "-c", "protocol.file.allow=always", "submodule", "add", str(nested), "nested")
    git(child, "commit", "-m", "test: add nested submodule")

    root = repository(tmp_path / "superproject")
    git(root, "-c", "protocol.file.allow=always", "submodule", "add", str(child), "component")
    git(root, "commit", "-m", "test: add component submodule")
    git(root, "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--recursive")
    return root, root / "component", root / "component" / "nested"


def test_assessment_accepts_aligned_clean_recursive_fixture(tmp_path: Path) -> None:
    root, _, _ = submodule_fixture(tmp_path)

    result = assess_submodule_readiness(root)

    assert result.ready is True
    assert result.findings == ()


def test_assessment_rejects_uninitialized_tracked_top_level_submodule(tmp_path: Path) -> None:
    root, component, _ = submodule_fixture(tmp_path)
    shutil.rmtree(component)
    component.mkdir()

    result = assess_submodule_readiness(root)

    assert result.ready is False
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("uninitialized", "component")
    ]


def test_assessment_rejects_checked_out_commit_that_differs_from_gitlink(tmp_path: Path) -> None:
    root, component, _ = submodule_fixture(tmp_path)
    git(component, "config", "user.email", "tests@example.invalid")
    git(component, "config", "user.name", "V1 Governance Tests")
    (component / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    git(component, "add", "advanced.txt")
    git(component, "commit", "-m", "test: advance checkout")

    result = assess_submodule_readiness(root)

    assert result.ready is False
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("pin-mismatch", "component")
    ]


def test_assessment_rejects_dirty_top_level_submodule_without_exposing_contents(tmp_path: Path) -> None:
    root, component, _ = submodule_fixture(tmp_path)
    marker = "do-not-disclose-this-value"
    (component / "private.txt").write_text(marker, encoding="utf-8")

    result = assess_submodule_readiness(root)

    serialized = json.dumps(result.to_mapping())
    assert result.ready is False
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("dirty-submodule", "component")
    ]
    assert marker not in serialized


def test_assessment_rejects_dirty_nested_submodule(tmp_path: Path) -> None:
    root, _, nested = submodule_fixture(tmp_path)
    (nested / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = assess_submodule_readiness(root)

    assert result.ready is False
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("dirty-submodule", "component/nested")
    ]


def test_assessment_fail_closes_when_git_repository_is_unavailable(tmp_path: Path) -> None:
    result = assess_submodule_readiness(tmp_path / "missing-repository")

    assert result.ready is False
    assert [(finding.code, finding.path) for finding in result.findings] == [
        ("repository-unavailable", ".")
    ]


def test_cli_returns_nonzero_gate_result_and_redacts_fixture_remote(tmp_path: Path, capsys) -> None:
    root, component, _ = submodule_fixture(tmp_path)
    shutil.rmtree(component)
    component.mkdir()

    exit_code = cli.main(["submodules", "readiness", "--repo", str(root)])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert json.loads(output) == {
        "findings": [{"code": "uninitialized", "path": "component"}],
        "ready": False,
    }
    assert "file://" not in output


def test_cli_returns_nonzero_for_unavailable_repository(tmp_path: Path, capsys) -> None:
    exit_code = cli.main(["submodules", "readiness", "--repo", str(tmp_path / "missing")])

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == {
        "findings": [{"code": "repository-unavailable", "path": "."}],
        "ready": False,
    }
