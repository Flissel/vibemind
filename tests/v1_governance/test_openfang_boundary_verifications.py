from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.v1_governance import cli
from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.git_state import GitAudit
from tools.v1_governance.handoff import (
    OPENFANG_BOUNDARIES,
    OpenFangBoundaryVerification,
    TaskHandoff,
)
from tools.v1_governance.models import SessionRequest
from tools.v1_governance.pr_gate import evaluate_pr_readiness


BRANCH = "codex/coding/task-coding-1042-codegen-start"
SHA = "0123456789abcdef0123456789abcdef01234567"


def _request(*, risk_class: str = "code") -> SessionRequest:
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
            "approval_reference": "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@2026-07-30T12:00:00+02:00",
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


def _write_registry(root: Path, cockpits: list[str]) -> None:
    registry = root / "docs" / "governance"
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "session-portfolio-registry-v1.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cockpits": [
                    {
                        "cockpit_session_id": cockpit,
                        "space": cockpit.removeprefix("cockpit-"),
                        "visible_title": cockpit,
                        "tasks": ["task-coding-1042"],
                    }
                    for cockpit in cockpits
                ],
            }
        ),
        encoding="utf-8",
    )


# A verification records that a task CHECKED an OpenFang boundary and says what it
# produced while checking it. It is not a claim that the boundary is sound, and it is
# not an approval: the contract's five boundaries are documented to different depths,
# and for some of them the honest evidence is "the contract asserts nothing here that a
# task could check". Recording that is the point - the field makes task-level
# verification RECORDABLE, which is the half of success condition 8 that had no
# mechanism at all before this task.
_EXECUTION = {
    "boundary": "execution",
    "evidence": [
        "Read shared/contracts/openfang-mcp-authority-v1.json at the pinned revision "
        "and confirmed all 41 server entries carry a registration state and sources."
    ],
}
_PROVIDER = {
    "boundary": "provider",
    "evidence": [
        "The contract expresses no provider boundary to check: provider appears only "
        "in role_semantics prose and in gaps as static-provider-pinning."
    ],
}


def test_the_five_openfang_boundaries_are_the_contract_boundaries() -> None:
    assert OPENFANG_BOUNDARIES == frozenset(
        {"execution", "provider", "cost", "approval", "evidence"}
    )


def test_a_boundary_verification_is_a_valid_handoff_field() -> None:
    handoff = _handoff(openfang_boundary_verifications=[_EXECUTION])

    assert handoff.openfang_boundary_verifications == (
        OpenFangBoundaryVerification(
            boundary="execution", evidence=(_EXECUTION["evidence"][0],)
        ),
    )


def test_a_handoff_without_boundary_verifications_carries_none() -> None:
    assert _handoff().openfang_boundary_verifications == ()


def test_several_boundaries_can_be_verified_by_one_task() -> None:
    handoff = _handoff(openfang_boundary_verifications=[_EXECUTION, _PROVIDER])

    assert tuple(
        item.boundary for item in handoff.openfang_boundary_verifications
    ) == ("execution", "provider")


def test_an_unknown_boundary_is_rejected() -> None:
    with pytest.raises(GovernanceError):
        _handoff(
            openfang_boundary_verifications=[
                {"boundary": "telemetry", "evidence": ["measured something"]}
            ]
        )


def test_a_boundary_may_not_be_verified_twice_in_one_handoff() -> None:
    with pytest.raises(GovernanceError):
        _handoff(openfang_boundary_verifications=[_EXECUTION, _EXECUTION])


def test_boundary_evidence_must_be_non_empty_strings() -> None:
    with pytest.raises(GovernanceError):
        _handoff(
            openfang_boundary_verifications=[{"boundary": "cost", "evidence": ["   "]}]
        )


# A boundary named with no evidence behind it is the exact shape this field exists to
# prevent: a task that claims to have verified a boundary without saying what it
# checked. "Nothing to check here" is a legitimate finding, but it has to be WRITTEN,
# not implied by an empty list.
def test_a_boundary_claimed_without_evidence_is_rejected() -> None:
    with pytest.raises(GovernanceError):
        _handoff(openfang_boundary_verifications=[{"boundary": "cost", "evidence": []}])


def test_a_boundary_verification_entry_must_be_a_mapping() -> None:
    with pytest.raises(GovernanceError):
        _handoff(openfang_boundary_verifications=["execution"])


def test_boundary_verifications_must_be_a_list() -> None:
    with pytest.raises(GovernanceError):
        _handoff(openfang_boundary_verifications={"boundary": "execution"})


# Disclosure, never a blocker. The field records what a task checked; a gate that
# blocked on it would turn an honest record into a cost and teach the next session to
# omit it - the same failure mode "not_run" and "failed_at_base" were introduced to
# avoid.
def test_a_boundary_verification_does_not_block_readiness() -> None:
    result = evaluate_pr_readiness(
        _request(), _handoff(openfang_boundary_verifications=[_EXECUTION]), _audit()
    )

    assert result.ready is True
    assert result.reasons == ()


def test_a_boundary_verification_is_named_in_the_gate_result() -> None:
    result = evaluate_pr_readiness(
        _request(), _handoff(openfang_boundary_verifications=[_EXECUTION]), _audit()
    )

    assert result.openfang_boundary_verifications == (
        OpenFangBoundaryVerification(
            boundary="execution", evidence=(_EXECUTION["evidence"][0],)
        ),
    )


def test_a_real_blocker_still_blocks_beside_a_boundary_verification() -> None:
    result = evaluate_pr_readiness(
        _request(),
        _handoff(
            openfang_boundary_verifications=[_EXECUTION],
            remaining_blockers=["the migration was never executed"],
        ),
        _audit(),
    )

    assert result.ready is False
    assert "remaining-blockers" in result.reasons
    assert len(result.openfang_boundary_verifications) == 1


def test_a_gate_result_without_verifications_discloses_nothing() -> None:
    result = evaluate_pr_readiness(_request(), _handoff(), _audit())

    assert result.openfang_boundary_verifications == ()


def test_pr_check_reports_boundary_verifications_alongside_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(
        cli,
        "load_task_handoff",
        lambda _path, _root: _handoff(
            openfang_boundary_verifications=[_EXECUTION, _PROVIDER]
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
        "openfang_boundary_verifications": [
            {"boundary": "execution", "evidence": _EXECUTION["evidence"]},
            {"boundary": "provider", "evidence": _PROVIDER["evidence"]},
        ],
    }


def test_pr_check_omits_boundary_verifications_when_there_are_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_registry(tmp_path, ["cockpit-coding"])
    monkeypatch.setattr(cli, "load_session_request", lambda _path: _request())
    monkeypatch.setattr(cli, "load_task_handoff", lambda _path, _root: _handoff())
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
    assert "openfang_boundary_verifications" not in json.loads(capsys.readouterr().out)
