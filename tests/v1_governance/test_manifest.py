import json
from pathlib import Path
import subprocess

import pytest
import yaml

from tools.v1_governance import cli
from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.manifest import ManifestIssue, validate_manifest


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        shell=False,
        text=True,
        capture_output=True,
    )


def _arrange_superproject(tmp_path: Path) -> tuple[Path, Path]:
    child = tmp_path / "child-source"
    child.mkdir()
    _git(child, "init")
    _git(child, "config", "user.name", "V1 Tests")
    _git(child, "config", "user.email", "v1-tests@example.invalid")
    (child / "README.md").write_text("child\n", encoding="utf-8")
    _git(child, "add", "README.md")
    _git(child, "commit", "-m", "test: initialize child")

    root = tmp_path / "superproject"
    root.mkdir()
    _git(root, "init", "-b", "master")
    _git(root, "config", "user.name", "V1 Tests")
    _git(root, "config", "user.email", "v1-tests@example.invalid")
    _git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(child),
        "component",
    )
    _git(root, "commit", "-m", "test: add component")

    recorded_remote = _git(
        root,
        "config",
        "-f",
        ".gitmodules",
        "--get",
        "submodule.component.url",
    ).stdout.strip()
    gitlink_pin = _git(root, "rev-parse", "HEAD:component").stdout.strip()
    parent_pin = _git(root, "rev-parse", "HEAD").stdout.strip()
    manifest_path = root / "repo-manifest.yaml"
    _write_manifest(manifest_path, recorded_remote, gitlink_pin, parent_pin)
    return root, manifest_path


def _write_manifest(
    path: Path,
    remote: str,
    gitlink_pin: str,
    parent_pin: str,
    *,
    initialization_state: str = "initialized",
    gitlink_state: str = "present",
) -> None:
    document: dict[str, object] = {
        "schema_version": 1,
        "superproject": {
            "id": "test-superproject",
            "path": ".",
            "current_integration_branch": "master",
            "target_integration_branch": "main",
            "branch_rename_status": "approval-required",
        },
        "repositories": [
            {
                "id": "component",
                "parent": "test-superproject",
                "path": "component",
                "kind": "submodule",
                "expected_gitlink_pin": gitlink_pin,
                "remote": remote,
                "remote_role": "origin",
                "required": True,
                "migration_state": "current",
                "owner": "platform",
                "initialization_state": initialization_state,
                "gitlink_state": gitlink_state,
                "evidence": {
                    "source": "local-git",
                    "parent_pin": parent_pin,
                    "validation_state": "local",
                },
            }
        ],
        "submodule_policy": {
            "recursive_inventory_required": True,
            "pin_change_requires_separate_commit": True,
            "nested_submodules_target_state": "remove-gradually",
        },
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _codes(repo: Path, manifest: Path) -> list[str]:
    return [issue.code for issue in validate_manifest(repo, manifest)]


CURRENT_WARNING_IDENTITIES = {
    ("external/minibook", "declared-without-gitlink"),
    ("spaces/desktop/Automation_ui/moire_tracker", "declared-without-gitlink"),
    ("spaces/flowzen/flowzen", "declared-without-gitlink"),
}


def _has_integration_reference(root: Path) -> bool:
    return any(
        subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", reference],
            cwd=root,
            check=False,
            shell=False,
            text=True,
            capture_output=True,
        ).returncode
        == 0
        for reference in ("refs/heads/master", "refs/remotes/origin/master")
    )


def _assert_current_manifest_findings(root: Path, issues: list[ManifestIssue]) -> None:
    warning_identities = {
        (issue.path, issue.code)
        for issue in issues
        if issue.severity == "warning"
    }
    error_identities = {
        (issue.path, issue.code)
        for issue in issues
        if issue.severity == "error"
    }

    assert warning_identities == CURRENT_WARNING_IDENTITIES
    expected_environment_errors = (
        set() if _has_integration_reference(root) else {(".", "missing-integration-branch")}
    )
    assert error_identities == expected_environment_errors


def test_cli_exposes_manifest_validate_command() -> None:
    assert "manifest" in cli._parser().format_help()


def test_cli_manifest_validate_reports_sorted_findings_and_nonzero_for_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "validate_manifest",
        lambda _repo, _manifest: [
            ManifestIssue("z-code", "z-path", "last"),
            ManifestIssue("a-code", "a-path", "first"),
        ],
    )

    assert cli.main(["manifest", "validate", "--repo", "repo", "--manifest", "manifest.yaml"]) == 2
    assert capsys.readouterr().out == (
        '{"findings": [{"code": "a-code", "message": "first", "path": "a-path", '
        '"severity": "error"}, {"code": "z-code", "message": "last", "path": "z-path", '
        '"severity": "error"}]}\n'
    )


def test_cli_manifest_validate_returns_zero_for_warnings_only(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "validate_manifest",
        lambda _repo, _manifest: [
            ManifestIssue("declared-without-gitlink", "legacy", "legacy", severity="warning")
        ],
    )

    assert cli.main(["manifest", "validate", "--repo", "repo"]) == 0
    assert capsys.readouterr().out == (
        '{"findings": [{"code": "declared-without-gitlink", "message": "legacy", '
        '"path": "legacy", "severity": "warning"}]}\n'
    )


def test_cli_manifest_validate_returns_technical_error_for_unavailable_manifest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raise_load_error(_repo: Path, _manifest: Path) -> list[ManifestIssue]:
        raise GovernanceError("cannot load manifest: unavailable")

    monkeypatch.setattr(cli, "validate_manifest", raise_load_error)

    assert cli.main(["manifest", "validate", "--repo", "repo"]) == 1
    assert capsys.readouterr().out == '{"error": "cannot load manifest: unavailable"}\n'


def test_vibemind_os_current_gitlink_chain_is_consistent() -> None:
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "repo-manifest.yaml").read_text(encoding="utf-8"))
    repositories = {repository["id"]: repository for repository in document["repositories"]}
    # The 760da81..82127e4 interval contains 30 commits. Its mode-filtered
    # gitlink diff changes OpenFang and Voice and adds spaces/video/laura; the
    # remaining twelve previously declared child gitlinks stay unchanged.
    vibemind_os_pin = "82127e44944495e5cb47d22e597cee9c51bbee83"
    openfang_pin = "8a4904b3ff622d7ffda1e8cb01a509d2db430904"
    voice_pin = "a8c8d9f172a768850ad4cf999c6ebbb68bc6f015"
    laura_pin = "909a43d499ffe00f4fd3d779127da45debf64f0c"

    assert repositories["vibemind-os"]["expected_gitlink_pin"] == vibemind_os_pin
    assert repositories["openfang"]["expected_gitlink_pin"] == openfang_pin
    assert repositories["voice"]["expected_gitlink_pin"] == voice_pin
    assert repositories["laura"]["expected_gitlink_pin"] == laura_pin
    assert repositories["la-fungus-search"]["expected_gitlink_pin"] == (
        "22011ea9c437c13f771337516c7f432ceb8be236"
    )
    assert repositories["shared"]["expected_gitlink_pin"] == (
        "fe9c31d257c551568794c44098bf75e92f327e7f"
    )
    vibemind_os_children = [
        repository
        for repository in repositories.values()
        if repository["parent"] == "vibemind-os"
    ]
    voice_children = [
        repository
        for repository in repositories.values()
        if repository["parent"] == "voice"
    ]

    assert vibemind_os_children
    assert all(
        repository["evidence"]["parent_pin"] == vibemind_os_pin
        for repository in vibemind_os_children
    )
    assert voice_children
    assert all(
        repository["evidence"]["parent_pin"] == voice_pin
        for repository in voice_children
    )


def test_outer_gitlink_pins_the_merged_authority_chain_commit() -> None:
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "repo-manifest.yaml").read_text(encoding="utf-8"))
    manifest_pin = next(
        repository["expected_gitlink_pin"]
        for repository in document["repositories"]
        if repository["id"] == "vibemind-os"
    )
    gitlink = _git(root, "ls-files", "--stage", "vibemind-os").stdout.split()[1]

    assert gitlink == manifest_pin


def test_manifest_accepts_matching_submodule(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    assert _codes(repo, manifest) == []


def test_manifest_rejects_missing_path(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    document["repositories"][0]["kind"] = "repository"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    _git(repo, "rm", "--cached", "-f", "component", ".gitmodules")
    (repo / "component").rename(repo / "component-away")
    assert _codes(repo, manifest) == ["missing-path"]


def test_manifest_rejects_submodule_without_gitlink(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    _git(repo, "rm", "--cached", "-f", "component")
    assert _codes(repo, manifest) == ["declared-without-gitlink"]


def test_manifest_rejects_unexpected_remote(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    document["repositories"][0]["remote"] = "https://example.invalid/unexpected.git"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert _codes(repo, manifest) == ["remote-mismatch"]


def test_current_default_can_differ_from_approved_target(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    assert _codes(repo, manifest) == []


def test_uninitialized_gitlink_is_not_a_missing_path(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    document["repositories"][0]["initialization_state"] = "uninitialized"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (repo / "component").rename(repo / "component-away")
    assert _codes(repo, manifest) == []


def test_manifest_rejects_unexpected_gitlink_pin(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    document["repositories"][0]["expected_gitlink_pin"] = "0" * 40
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert _codes(repo, manifest) == ["pin-mismatch"]


def test_local_evidence_rejects_parent_pin_mismatch(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    document["repositories"][0]["evidence"]["parent_pin"] = "0" * 40
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    assert _codes(repo, manifest) == ["parent-pin-mismatch"]


def test_pinned_child_under_uninitialized_parent_is_not_live_checked(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    parent = document["repositories"][0]
    parent["initialization_state"] = "uninitialized"
    document["repositories"].append(
        {
            "id": "nested-component",
            "parent": "component",
            "path": "nested",
            "kind": "submodule",
            "expected_gitlink_pin": "1" * 40,
            "remote": "https://example.invalid/nested.git",
            "remote_role": "origin",
            "required": True,
            "migration_state": "current",
            "owner": "platform",
            "initialization_state": "unobserved",
            "gitlink_state": "present",
            "evidence": {
                "source": "pinned-remote-tree",
                "parent_pin": parent["expected_gitlink_pin"],
                "validation_state": "pinned-not-live",
            },
        }
    )
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (repo / "component").rename(repo / "component-away")
    assert _codes(repo, manifest) == []


def test_pinned_declared_entry_without_gitlink_is_reported(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    parent = document["repositories"][0]
    parent["initialization_state"] = "uninitialized"
    document["repositories"].append(
        {
            "id": "legacy-declaration",
            "parent": "component",
            "path": "legacy",
            "kind": "submodule",
            "expected_gitlink_pin": "absent",
            "remote": "https://example.invalid/legacy.git",
            "remote_role": "origin",
            "required": False,
            "migration_state": "declared-legacy",
            "owner": "platform",
            "initialization_state": "absent",
            "gitlink_state": "declared-without-gitlink",
            "evidence": {
                "source": "pinned-remote-tree",
                "parent_pin": parent["expected_gitlink_pin"],
                "validation_state": "pinned-not-live",
            },
        }
    )
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (repo / "component").rename(repo / "component-away")
    assert _codes(repo, manifest) == ["declared-without-gitlink"]


def test_current_manifest_warns_only_for_the_three_known_legacy_declarations() -> None:
    root = Path(__file__).resolve().parents[2]
    issues = validate_manifest(root, root / "repo-manifest.yaml")

    _assert_current_manifest_findings(root, issues)


def test_current_manifest_rejects_an_unexpected_error() -> None:
    root = Path(__file__).resolve().parents[2]
    issues = validate_manifest(root, root / "repo-manifest.yaml")

    with pytest.raises(AssertionError):
        _assert_current_manifest_findings(
            root,
            [
                *issues,
                ManifestIssue("unexpected", "vibemind-os", "injected current-state error"),
            ],
        )


@pytest.mark.parametrize("checkout_state", ("detached", "master"))
def test_remote_master_reference_suffices_without_changing_checkout_state(
    tmp_path: Path, checkout_state: str
) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "update-ref", "refs/remotes/origin/master", head)
    if checkout_state == "detached":
        _git(repo, "checkout", "--detach")
        _git(repo, "branch", "-D", "master")
    else:
        _git(repo, "checkout", "master")
    before = _git(repo, "branch", "--show-current").stdout.strip()

    remote_ref = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/master"],
        cwd=repo,
        check=False,
        shell=False,
        text=True,
        capture_output=True,
    )

    assert remote_ref.returncode == 0
    if checkout_state == "detached":
        local_master_ref = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/master"],
            cwd=repo,
            check=False,
            shell=False,
            text=True,
            capture_output=True,
        )
        assert local_master_ref.returncode == 1
    assert _codes(repo, manifest) == []
    assert _git(repo, "branch", "--show-current").stdout.strip() == before


def test_unknown_fully_qualifying_legacy_declaration_remains_an_error(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "repo-manifest.yaml").read_text(encoding="utf-8"))
    vibemind_os = next(
        repository
        for repository in document["repositories"]
        if repository["id"] == "vibemind-os"
    )
    document["repositories"].append(
        {
            "id": "unknown-legacy-declaration",
            "parent": "vibemind-os",
            "path": "spaces/unknown/legacy",
            "kind": "submodule",
            "expected_gitlink_pin": "absent",
            "remote": "https://example.invalid/unknown-legacy.git",
            "remote_role": "canonical-origin",
            "owner": "platform",
            "required": False,
            "migration_state": "declared-legacy",
            "initialization_state": "absent",
            "gitlink_state": "declared-without-gitlink",
            "evidence": {
                "source": "pinned-remote-tree",
                "parent_pin": vibemind_os["expected_gitlink_pin"],
                "validation_state": "pinned-not-live",
            },
        }
    )
    manifest = tmp_path / "repo-manifest.yaml"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    assert [
        issue
        for issue in validate_manifest(root, manifest)
        if issue.path == "spaces/unknown/legacy"
    ] == [
        ManifestIssue(
            "declared-without-gitlink",
            "spaces/unknown/legacy",
            "pinned parent declares path without a gitlink",
            severity="error",
        )
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("required", True),
        ("migration_state", "current"),
        ("initialization_state", "unobserved"),
        ("expected_gitlink_pin", "0" * 40),
        ("gitlink_state", "present"),
        ("evidence.validation_state", "local"),
    ),
)
def test_known_legacy_warning_becomes_an_error_when_any_qualifier_changes(
    tmp_path: Path, field: str, value: object
) -> None:
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "repo-manifest.yaml").read_text(encoding="utf-8"))
    target = next(
        repository
        for repository in document["repositories"]
        if repository["id"] == "flowzen-declaration"
    )
    if field.startswith("evidence."):
        target["evidence"][field.removeprefix("evidence.")] = value
    else:
        target[field] = value
    manifest = tmp_path / "repo-manifest.yaml"
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    target_issues = [
        issue
        for issue in validate_manifest(root, manifest)
        if issue.path == "spaces/flowzen/flowzen"
    ]
    assert target_issues
    assert all(issue.severity == "error" for issue in target_issues)


def test_child_cannot_claim_local_validation_under_uninitialized_parent(tmp_path: Path) -> None:
    repo, manifest = _arrange_superproject(tmp_path)
    document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    parent = document["repositories"][0]
    parent["initialization_state"] = "uninitialized"
    document["repositories"].append(
        {
            **parent,
            "id": "nested-component",
            "parent": "component",
            "path": "nested",
            "initialization_state": "initialized",
            "evidence": {
                "source": "local-git",
                "parent_pin": parent["expected_gitlink_pin"],
                "validation_state": "local",
            },
        }
    )
    manifest.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (repo / "component").rename(repo / "component-away")
    assert _codes(repo, manifest) == ["parent-uninitialized"]


def _manifest_gitlink_pin(document: dict, repository_id: str) -> str:
    entries = [
        entry
        for entry in document["repositories"]
        if entry["id"] == repository_id
    ]
    assert len(entries) == 1, f"expected exactly one '{repository_id}' manifest entry"
    return entries[0]["expected_gitlink_pin"]


def test_authority_contract_source_pins_match_the_manifest_gitlinks() -> None:
    """The OpenFang authority contract must describe the checkout the manifest pins.

    The contract's ``sources`` are file:line references into ``vibemind-os`` and its
    nested ``openfang``. Those coordinates are only meaningful at the commits the
    contract declares in ``source_pins``, so a superproject pin lift silently
    invalidates every one of them unless the contract is re-pinned in the same
    change. This test makes that silence impossible: it will go red on the pin lift
    and stay red until the contract and its line references are advanced together.
    That reddening is the intended behaviour, not a defect.
    """
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "repo-manifest.yaml").read_text(encoding="utf-8"))
    contract = json.loads(
        (root / "shared" / "contracts" / "openfang-mcp-authority-v1.json").read_text(
            encoding="utf-8"
        )
    )
    source_pins = contract["source_pins"]

    assert source_pins["vibemind-os"] == _manifest_gitlink_pin(document, "vibemind-os"), (
        "contract source_pins['vibemind-os'] is stale against repo-manifest.yaml "
        "expected_gitlink_pin; re-pin the contract and advance its sources line "
        "references in the same commit"
    )
    assert source_pins["vibemind-os/openfang"] == _manifest_gitlink_pin(
        document, "openfang"
    ), (
        "contract source_pins['vibemind-os/openfang'] is stale against "
        "repo-manifest.yaml expected_gitlink_pin for 'openfang'; re-pin the contract "
        "and advance its sources line references in the same commit"
    )
