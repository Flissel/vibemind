from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from tools.v1_governance import cli
from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.git_state import GitAudit
from tools.v1_governance.handoff import TaskHandoff
from tools.v1_governance.models import SessionRequest
from tools.v1_governance.pr_gate import GateResult, evaluate_pr_readiness


BRANCH = "codex/coding/task-coding-1042-codegen-start"
SHA = "0123456789abcdef0123456789abcdef01234567"


def _request(
    *, risk_class: str = "code", approval_reference: str | None = None
) -> SessionRequest:
    return SessionRequest.from_mapping(
        {
            "schema_version": 2,
            "session_id": "task-coding-1042",
            "session_type": "task",
            "space": "coding",
            "parent_cockpit": "cockpit-coding",
            "request_reference": "task-request:task-coding-1042-v1",
            "objective": "Add the async code-generation start endpoint",
            "repositories": ["vibemind-v1"],
            "allowed_paths": ["tools/v1_governance/**", "tests/v1_governance/**"],
            "writes_allowed": True,
            "approval_status": "approved",
            "approval_reference": approval_reference
            or "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@2026-07-30T12:00:00+02:00",
            "base_ref": "origin/master",
            "branch": BRANCH,
            "risk_class": risk_class,
            "dependencies": ["task-platform-0004"],
            "merge_position": 2,
        }
    )


def _handoff(**changes: object) -> TaskHandoff:
    data: dict[str, object] = {
        "schema_version": 2,
        "session_id": "task-coding-1042",
        "branch": BRANCH,
        "parent_cockpit": "cockpit-coding",
        "request_reference": "task-request:task-coding-1042-v1",
        "approval_reference": "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@2026-07-30T12:00:00+02:00",
        "commits": [{"sha": SHA, "subject": "feat: add async job start"}],
        "tests": [
            {
                "command": "python -m pytest tests/coding -q",
                "status": "passed",
                "summary": "18 passed",
            }
        ],
        "evidence": [{"kind": "test-output", "path": "results/task-coding-1042/pytest.txt"}],
        "dependencies": [{"session_id": "task-platform-0004", "merged": True}],
        "merge_position": 2,
        "deployment_status": "not_required",
        "remaining_blockers": [],
    }
    data.update(changes)
    return TaskHandoff.from_mapping(data)


def _audit(**changes: object) -> GitAudit:
    data: dict[str, object] = {
        "root": Path("."),
        "branch": BRANCH,
        "head": SHA,
        "dirty_paths": (),
        "worktrees": (),
        "upstream": None,
        "ahead": None,
        "behind": None,
        "submodules": (),
    }
    data.update(changes)
    return GitAudit(**data)


def _request_mapping(parent_cockpit: str) -> dict[str, object]:
    return {
        "schema_version": 2,
        "session_id": "task-coding-1042",
        "session_type": "task",
        "space": "coding",
        "parent_cockpit": parent_cockpit,
        "request_reference": "task-request:task-coding-1042-v1",
        "objective": "Add the async code-generation start endpoint",
        "repositories": ["vibemind-v1"],
        "allowed_paths": ["tools/v1_governance/**", "tests/v1_governance/**"],
        "writes_allowed": True,
        "approval_status": "approved",
        "approval_reference": "standing-autonomy:v1",
        "base_ref": "origin/master",
        "branch": BRANCH,
        "risk_class": "code",
        "dependencies": ["task-platform-0004"],
        "merge_position": 2,
    }


def _write_registry(root: Path, cockpit_ids: list[str]) -> None:
    registry = root / "docs" / "governance" / "session-portfolio-registry-v1.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps({"cockpits": [{"cockpit_session_id": cockpit_id} for cockpit_id in cockpit_ids]}),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("handoff_changes", "expected_reason"),
    [({"tests": []}, "missing-test-evidence")],
)
def test_missing_test_evidence_blocks_pr(
    handoff_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(**handoff_changes), _audit())

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("handoff_changes", "expected_reason"),
    [
        (
            {
                "tests": [
                    {
                        "command": "python -m pytest tests/coding -q",
                        "status": "failed",
                        "summary": "1 failed",
                    }
                ]
            },
            "failed-test-evidence",
        )
    ],
)
def test_failed_test_blocks_pr(
    handoff_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(**handoff_changes), _audit())

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("audit_changes", "expected_reason"),
    [({"dirty_paths": ("tools/v1_governance/pr_gate.py",)}, "dirty-worktree")],
)
def test_dirty_worktree_blocks_pr(
    audit_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(), _audit(**audit_changes))

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("handoff_changes", "audit_changes", "expected_reason"),
    [
        (
            {"branch": "codex/coding/task-coding-1042-other"},
            {},
            "branch-mismatch",
        )
    ],
)
def test_branch_mismatch_blocks_pr(
    handoff_changes: dict[str, object],
    audit_changes: dict[str, object],
    expected_reason: str,
) -> None:
    result = evaluate_pr_readiness(
        _request(), _handoff(**handoff_changes), _audit(**audit_changes)
    )

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("handoff_changes", "expected_reason"),
    [
        (
            {"dependencies": [{"session_id": "task-platform-0004", "merged": False}]},
            "unmerged-dependency",
        )
    ],
)
def test_unmerged_dependency_blocks_pr(
    handoff_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(**handoff_changes), _audit())

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("risk_class", "handoff_changes", "expected_reason"),
    [("deployment", {}, "missing-risk-approval")],
)
def test_high_risk_change_requires_fresh_user_gate(
    risk_class: str, handoff_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(
        _request(risk_class=risk_class), _handoff(**handoff_changes), _audit()
    )

    assert result.ready is False
    assert result.reasons == (expected_reason,)


@pytest.mark.parametrize("handoff_changes", [{}])
def test_green_code_handoff_is_ready(handoff_changes: dict[str, object]) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(**handoff_changes), _audit())

    assert result == GateResult(ready=True, reasons=())


def test_standing_autonomy_handoff_is_ready_without_request_specific_user_gate() -> None:
    authority = "standing-autonomy:v1"

    result = evaluate_pr_readiness(
        _request(approval_reference=authority),
        _handoff(approval_reference=authority),
        _audit(),
    )

    assert result == GateResult(ready=True, reasons=())


@pytest.mark.parametrize(
    ("handoff_changes", "expected_reason"),
    [
        ({"parent_cockpit": "cockpit-shared"}, "parent-cockpit-mismatch"),
        ({"request_reference": "task-request:other-v1"}, "request-reference-mismatch"),
        (
            {
                "approval_reference": "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@2026-07-30T12:01:00+02:00"
            },
            "approval-reference-mismatch",
        ),
        ({"merge_position": 3}, "merge-position-mismatch"),
        ({"dependencies": []}, "dependency-mismatch"),
    ],
)
def test_provenance_mismatch_blocks_pr(
    handoff_changes: dict[str, object], expected_reason: str
) -> None:
    result = evaluate_pr_readiness(_request(), _handoff(**handoff_changes), _audit())

    assert result.ready is False
    assert result.reasons == (expected_reason,)


def test_handoff_rejects_an_unverifiable_approval_reference() -> None:
    with pytest.raises(GovernanceError, match="approval_reference"):
        _handoff(approval_reference="user-message:2026-07-30")


def test_session_validation_rejects_unregistered_parent_cockpit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(_request_mapping("cockpit-unknown")), encoding="utf-8")

    result = cli.main(
        ["session", "validate", "--repo", str(tmp_path), "--request", str(request_path)]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {
        "error": "parent_cockpit is not registered"
    }


def test_pr_check_rejects_unregistered_parent_cockpit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(
        cli, "load_session_request", lambda _path: replace(_request(), parent_cockpit="cockpit-unknown")
    )
    monkeypatch.setattr(cli, "load_task_handoff", lambda _path, _root: _handoff())
    monkeypatch.setattr(cli, "audit_repository", lambda _root: _audit())

    result = cli.main(
        ["pr", "check", "--repo", str(tmp_path), "--request", "request.yaml", "--handoff", "handoff.yaml"]
    )

    assert result == 1
    assert json.loads(capsys.readouterr().out) == {
        "error": "parent_cockpit is not registered"
    }


def test_pr_check_preserves_registered_parent_cockpit_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding", "cockpit-shared"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(
        cli, "load_task_handoff", lambda _path, _root: _handoff(parent_cockpit="cockpit-shared")
    )
    monkeypatch.setattr(cli, "audit_repository", lambda _root: _audit())

    result = cli.main(
        ["pr", "check", "--repo", str(tmp_path), "--request", "request.yaml", "--handoff", "handoff.yaml"]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {
        "ready": False,
        "reasons": ["parent-cockpit-mismatch"],
    }


@pytest.mark.parametrize(
    "arguments",
    [
        ["audit", "--repo", "."],
        ["session", "validate", "--request", "request.yaml"],
    ],
)
def test_existing_governance_commands_keep_contract_errors_as_gate_failures(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    def raise_governance_error(*_args: object, **_kwargs: object) -> None:
        raise GovernanceError("invalid contract")

    monkeypatch.setattr(cli, "audit_repository", raise_governance_error)
    monkeypatch.setattr(cli, "load_session_request", raise_governance_error)

    assert cli.main(arguments) == 2


_UNEXECUTED = {
    "command": "pester tests/deployment/deployment-readiness.Tests.ps1",
    "status": "not_run",
    "summary": "pwsh is absent from the image and not installable from the configured apt sources",
}


def test_a_test_declared_not_run_is_a_valid_status() -> None:
    handoff = _handoff(tests=[_UNEXECUTED])

    assert tuple(test.status for test in handoff.tests) == ("not_run",)


def test_an_unexecuted_test_does_not_block_when_another_test_passed() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _UNEXECUTED,
            ]
        ),
        _audit(),
    )

    assert result.ready is True
    assert result.reasons == ()


def test_an_unexecuted_test_is_named_in_the_gate_result() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _UNEXECUTED,
            ]
        ),
        _audit(),
    )

    assert result.unexecuted_tests == (
        "pester tests/deployment/deployment-readiness.Tests.ps1",
    )


def test_a_handoff_whose_every_test_is_unexecuted_still_blocks() -> None:
    result = evaluate_pr_readiness(_request(), _handoff(tests=[_UNEXECUTED]), _audit())

    assert result.ready is False
    assert result.reasons == ("missing-passed-test-evidence",)


def test_pr_check_reports_unexecuted_tests_alongside_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(
        cli,
        "load_task_handoff",
        lambda _path, _root: _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _UNEXECUTED,
            ]
        ),
    )
    monkeypatch.setattr(cli, "audit_repository", lambda _root: _audit())

    result = cli.main(
        [
            "pr",
            "check",
            "--repo",
            str(tmp_path),
            "--request",
            "request.yaml",
            "--handoff",
            "handoff.yaml",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "ready": True,
        "reasons": [],
        "unexecuted_tests": ["pester tests/deployment/deployment-readiness.Tests.ps1"],
    }


_FAILED_AT_BASE = {
    "command": "python -m pytest tests/integration/test_openfang_mcp_authority_contract_v1.py -q",
    "status": "failed_at_base",
    "summary": "15 passed / 3 failed; all three are red at the unmodified base commit and none is in scope",
}


def test_a_failure_that_predates_the_change_is_a_valid_status() -> None:
    handoff = _handoff(tests=[_FAILED_AT_BASE])

    assert tuple(test.status for test in handoff.tests) == ("failed_at_base",)


def test_a_pre_existing_failure_does_not_block_when_another_test_passed() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _FAILED_AT_BASE,
            ]
        ),
        _audit(),
    )

    assert result.ready is True
    assert result.reasons == ()


def test_a_pre_existing_failure_is_named_in_the_gate_result() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _FAILED_AT_BASE,
            ]
        ),
        _audit(),
    )

    assert result.pre_existing_failures == (
        "python -m pytest tests/integration/test_openfang_mcp_authority_contract_v1.py -q",
    )


def test_a_handoff_whose_every_test_predates_the_change_still_blocks() -> None:
    result = evaluate_pr_readiness(_request(), _handoff(tests=[_FAILED_AT_BASE]), _audit())

    assert result.ready is False
    assert result.reasons == ("missing-passed-test-evidence",)


def test_a_genuine_failure_still_blocks_even_beside_a_pre_existing_one() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _FAILED_AT_BASE,
                {
                    "command": "python -m pytest tests/coding/test_new.py -q",
                    "status": "failed",
                    "summary": "1 failed, caused by this change",
                },
            ]
        ),
        _audit(),
    )

    assert result.ready is False
    assert result.reasons == ("failed-test-evidence",)


def test_pr_check_reports_pre_existing_failures_alongside_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(
        cli,
        "load_task_handoff",
        lambda _path, _root: _handoff(
            tests=[
                {
                    "command": "python -m pytest tests/coding -q",
                    "status": "passed",
                    "summary": "18 passed",
                },
                _FAILED_AT_BASE,
            ]
        ),
    )
    monkeypatch.setattr(cli, "audit_repository", lambda _root: _audit())

    result = cli.main(
        [
            "pr",
            "check",
            "--repo",
            str(tmp_path),
            "--request",
            "request.yaml",
            "--handoff",
            "handoff.yaml",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "ready": True,
        "reasons": [],
        "pre_existing_failures": [
            "python -m pytest tests/integration/test_openfang_mcp_authority_contract_v1.py -q"
        ],
    }


# A deferred decision is not a blocker. "remaining_blockers" means the work in this
# task is unfinished; "deferred_decisions" means the task finished by WRITING DOWN a
# decision it was told not to make. Two sessions in one maintenance round filed the
# same shape under opposite fields because the schema had only the first, and the gate
# then read a completed fail-closed deliverable as an incomplete one.
_DEFERRED = (
    "vibemind_shared availability is an open program decision, deliberately left open "
    "per the request: six routes are enumerated and priced, every one breaks a declared "
    "invariant, and this session does not choose."
)


def test_a_deferred_decision_is_a_valid_handoff_field() -> None:
    handoff = _handoff(deferred_decisions=[_DEFERRED])

    assert handoff.deferred_decisions == (_DEFERRED,)


def test_a_handoff_without_deferred_decisions_carries_none() -> None:
    assert _handoff().deferred_decisions == ()


def test_a_deferred_decision_does_not_block_readiness() -> None:
    result = evaluate_pr_readiness(
        _request(), _handoff(deferred_decisions=[_DEFERRED]), _audit()
    )

    assert result.ready is True
    assert result.reasons == ()


def test_a_deferred_decision_is_named_in_the_gate_result() -> None:
    result = evaluate_pr_readiness(
        _request(), _handoff(deferred_decisions=[_DEFERRED]), _audit()
    )

    assert result.deferred_decisions == (_DEFERRED,)


def test_a_real_blocker_still_blocks_beside_a_deferred_decision() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            deferred_decisions=[_DEFERRED],
            remaining_blockers=["the migration was never executed"],
        ),
        _audit(),
    )

    assert result.ready is False
    assert "remaining-blockers" in result.reasons
    assert result.deferred_decisions == (_DEFERRED,)


def test_deferred_decisions_must_be_non_empty_strings() -> None:
    with pytest.raises(GovernanceError):
        _handoff(deferred_decisions=["   "])


def test_pr_check_reports_deferred_decisions_alongside_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(
        cli,
        "load_task_handoff",
        lambda _path, _root: _handoff(deferred_decisions=[_DEFERRED]),
    )
    monkeypatch.setattr(cli, "audit_repository", lambda _root: _audit())

    result = cli.main(
        [
            "pr",
            "check",
            "--repo",
            str(tmp_path),
            "--request",
            "request.yaml",
            "--handoff",
            "handoff.yaml",
        ]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == {
        "ready": True,
        "reasons": [],
        "deferred_decisions": [_DEFERRED],
    }
