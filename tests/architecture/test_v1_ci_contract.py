from pathlib import Path
import subprocess

import pytest

from tools.v1_governance import cli
from tools.v1_governance.models import SessionRequest
from tools.v1_governance.session import WorktreePlan


def _legacy_writing_request() -> SessionRequest:
    return SessionRequest.from_mapping(
        {
            "schema_version": 1,
            "session_id": "task-platform-0006",
            "session_type": "task",
            "space": "platform",
            "objective": "Legacy request fixture",
            "repositories": ["vibemind-v1"],
            "allowed_paths": ["tools/v1_governance/**"],
            "writes_allowed": True,
            "approval_status": "approved",
            "approval_reference": "user-message:2026-07-31",
            "base_ref": "origin/master",
            "branch": "codex/platform/task-platform-0006-legacy",
            "risk_class": "code",
        }
    )


def test_cli_validate_rejects_legacy_writing_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _legacy_writing_request())

    assert cli.main(["session", "validate", "--request", "legacy.yaml"]) == 2


def test_cli_dry_run_start_rejects_legacy_writing_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _legacy_writing_request())
    monkeypatch.setattr(
        cli,
        "plan_task_worktree",
        lambda *_args: WorktreePlan("branch", "base", Path("destination"), ("git",)),
    )

    assert cli.main(["session", "start", "--request", "legacy.yaml", "--dry-run"]) == 2


def test_v2_provenance_contract_is_exposed_to_contributors() -> None:
    request_template = Path(".agents/templates/SESSION_REQUEST.yaml").read_text(encoding="utf-8")
    handoff_template = Path(".agents/templates/TASK_HANDOFF.yaml").read_text(encoding="utf-8")
    pr_template = Path(".github/pull_request_template.md").read_text(encoding="utf-8")

    for field in ("parent_cockpit", "request_reference", "dependencies", "merge_position"):
        assert field in request_template
    for field in ("parent_cockpit", "request_reference", "approval_reference", "dependencies", "merge_position"):
        assert field in handoff_template
    assert "codex-user-message:" in request_template
    assert "codex-user-message:" in handoff_template
    for heading in ("Approval", "Parent cockpit", "Request reference", "Handoff", "Dependencies", "Merge position"):
        assert heading in pr_template


def test_current_mvp_portfolio_requires_openfang_execution() -> None:
    portfolio = Path(
        "docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md"
    ).read_text(encoding="utf-8")

    assert "Brain -> OpenFang -> Space-Agent -> MCP/Service" in portfolio
    assert "OpenFang Execution-/Cost-/Approval-Vertrag" in portfolio
    assert "cockpit-openfang" in portfolio


def test_current_mvp_governance_requires_openfang_execution() -> None:
    historical_design = Path(
        "docs/superpowers/specs/2026-07-30-v1-space-orchestration-design.md"
    ).read_text(encoding="utf-8")
    lifecycle = Path("docs/runbooks/v1-session-lifecycle.md").read_text(encoding="utf-8")

    assert "Normatives MVP-Zieldesign" in historical_design
    assert "OpenFang bleibt die verpflichtende Execution Engine des MVP." in historical_design
    assert "docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md" in historical_design
    assert "docs/runbooks/v1-session-lifecycle.md" in historical_design
    assert "Die aktuelle MVP-Governance hat Vorrang vor historischen Spezifikationen." in lifecycle
    assert "OpenFang execution is part of the current MVP wave." in lifecycle


def test_current_mvp_documents_do_not_defer_openfang() -> None:
    paths = (
        Path("docs/contracts/channel-intent-v1.md"),
        Path("docs/contracts/observability-evidence-governance-v2.md"),
        Path("docs/spaces/agentfarm/update-spec-v2.md"),
        Path("spaces/marketing/docs/COCKPIT_CONTRACT.md"),
        Path("spaces/marketing/README.md"),
        Path("spaces/marketing/STATUS.md"),
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for stale_statement in (
        "outside this MVP implementation",
        "OpenFang is explicitly excluded from this wave.",
        "OpenFang is a deferred, not-implemented future dependency",
        "OpenFang execution is deferred and out of this MVP wave",
        "OpenFang execution is deferred in this MVP wave",
    ):
        assert stale_statement not in combined


def test_openfang_mvp_scope_marks_repository_fork_gate_historical_and_superseded() -> None:
    portfolio = Path(
        "docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md"
    ).read_text(encoding="utf-8")
    lifecycle = Path("docs/runbooks/v1-session-lifecycle.md").read_text(encoding="utf-8")
    lifecycle_normalized = " ".join(lifecycle.split())

    assert "Historischer Repository-Fork-Kontext (superseded)" in portfolio
    assert "kein aktuelles Fork-Gate und keine Live-Aussage" in portfolio
    assert "historical, superseded context" in lifecycle_normalized
    assert "rather than a current repository-state claim" in lifecycle_normalized
    assert (
        "Any new Git task must establish those facts from fresh repository evidence"
        in lifecycle_normalized
    )

    combined = portfolio + lifecycle
    for stale_live_gate_claim in (
        "394104d",
        "630452e",
        "origin/master pinnt",
        "No `vibemind-os` Gitlink may be changed or merged",
        "mandatory integration gate",
    ):
        assert stale_live_gate_claim not in combined


def test_local_governance_wrapper_is_parseable_and_runs_only_local_commands() -> None:
    wrapper = Path("scripts/vibemind-governance.ps1")

    assert wrapper.is_file()
    command = (
        "& { param([string]$TargetPath) $errors = $null; $tokens = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($TargetPath, [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { exit 1 } } '"
        + str(wrapper.resolve())
        + "'"
    )
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            command,
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    content = wrapper.read_text(encoding="utf-8")
    assert "'manifest', 'validate'" in content
    assert "'pytest', 'tests/architecture', 'tests/v1_governance'" in content
    assert "'submodules', 'readiness'" not in content
    assert "fetch" not in content.lower()
    assert "$LASTEXITCODE" in content


def test_governance_workflow_keeps_private_submodules_unchecked_out_and_root_checks_separate() -> None:
    governance_workflow = Path(".github/workflows/v1-governance.yml")
    root_checks = Path(".github/workflows/open-source-checks.yml")

    assert governance_workflow.is_file()
    assert root_checks.is_file()
    content = governance_workflow.read_text(encoding="utf-8")
    assert "submodules: false" in content
    assert "submodules: recursive" not in content
    assert "fetch-depth: 0" in content
    assert "refs/remotes/origin/master" in content
    assert "git show-ref --verify --quiet refs/remotes/origin/master" in content
    assert "git fetch" not in content.lower()
    assert "git branch" not in content.lower()
    assert "tools/v1_governance/requirements.txt" in content
    assert "python -m pytest tests/architecture/test_v1_ci_contract.py tests/v1_governance/test_manifest.py" in content
    assert "./scripts/vibemind-governance.ps1" not in content
    assert "tools/mcp_sync -q" in root_checks.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("exit_codes", "expected_exit"),
    (
        ((0, 0), 0),
        ((0, 2), 2),
        ((2, 3), 1),
    ),
)
def test_local_governance_wrapper_exit_precedence(
    tmp_path: Path, exit_codes: tuple[int, int], expected_exit: int
) -> None:
    counter = tmp_path / "counter.txt"
    counter.write_text("0", encoding="utf-8")
    fake_python = tmp_path / "fake-python.cmd"
    fake_python.write_text(
        "\r\n".join(
            (
                "@echo off",
                f'set /p count=<"{counter}"',
                "set /a next=count+1",
                f'>"{counter}" echo %next%',
                f'if "%count%"=="0" exit /b {exit_codes[0]}',
                f'exit /b {exit_codes[1]}',
            )
        )
        + "\r\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path("scripts/vibemind-governance.ps1").resolve()),
            "-RepositoryRoot",
            str(Path(".").resolve()),
            "-PythonCommand",
            str(fake_python),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == expected_exit
