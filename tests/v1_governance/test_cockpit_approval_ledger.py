from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.v1_governance.cli import main
from tools.v1_governance.errors import GovernanceError
from tools.v1_governance import portfolio


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APPROVAL_LEDGER_PATH = (
    REPOSITORY_ROOT / "docs/governance/cockpit-approval-ledger-v1.json"
)
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/runbooks/v1-session-lifecycle.md"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "authority": {
            "normative_membership": "portfolio",
            "current_lifecycle": "main-orchestrator-external",
        },
        "cockpits": [
            {
                "cockpit_session_id": "cockpit-openfang",
                "historical_observations": [],
            },
            {
                "cockpit_session_id": "cockpit-agentfarm",
                "historical_observations": [],
            },
        ],
    }


def _ledger(approvals: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "membership_source": "docs/governance/session-portfolio-registry-v1.json",
        "approval_policy": "individual-user-approval-required",
        "approvals": approvals,
    }


def _approved_openfang() -> dict[str, object]:
    return {
        "cockpit_session_id": "cockpit-openfang",
        "visible_title": "V1 Cockpit · OpenFang",
        "approval_reference": (
            "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@"
            "2026-08-04T18:53:50+02:00"
        ),
        "created_at": "2026-08-04T18:55:41+02:00",
    }


def _approved_agentfarm() -> dict[str, object]:
    return {
        "cockpit_session_id": "cockpit-agentfarm",
        "visible_title": "V1 Cockpit · AgentFarm / AutoGen",
        "approval_reference": (
            "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@"
            "2026-08-05T01:43:24+02:00"
        ),
        "created_at": "2026-08-05T01:47:12+02:00",
    }


_WAVE_ONE_APPROVAL_REFERENCE = (
    "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T09:58:00Z"
)


def _approved_wave_one(cockpit_session_id: str, visible_title: str) -> dict[str, object]:
    return {
        "cockpit_session_id": cockpit_session_id,
        "visible_title": visible_title,
        "approval_reference": _WAVE_ONE_APPROVAL_REFERENCE,
        "created_at": "2026-08-13T10:00:00Z",
    }


def _approved_git() -> dict[str, object]:
    return _approved_wave_one("cockpit-git", "V1 Cockpit · Git & Repositories")


def _approved_shared() -> dict[str, object]:
    return _approved_wave_one("cockpit-shared", "V1 Cockpit · Shared")


def _approved_brain() -> dict[str, object]:
    return _approved_wave_one("cockpit-brain", "V1 Cockpit · Brain")


def _approved_deployment() -> dict[str, object]:
    return _approved_wave_one("cockpit-deployment", "V1 Cockpit · Deployment")


_MAINTENANCE_DELEGATION_REFERENCE = (
    "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T13:09:00Z"
)

_PORTFOLIO_DELEGATION_TITLES = (
    ("cockpit-integration", "V1 Cockpit · Integration & Golden Paths"),
    ("cockpit-observability", "V1 Cockpit · Observability & Evidence"),
    ("cockpit-channels", "V1 Cockpit · Channels"),
    ("cockpit-ideas", "V1 Cockpit · Ideas"),
    ("cockpit-bubbles", "V1 Cockpit · Bubbles / Shuttles"),
    ("cockpit-minibook", "V1 Cockpit · Minibook intern"),
    ("cockpit-coding", "V1 Cockpit · Coding"),
    ("cockpit-desktop", "V1 Cockpit · Desktop"),
    ("cockpit-research", "V1 Cockpit · Research"),
    ("cockpit-rowboat", "V1 Cockpit · Rowboat"),
    ("cockpit-schedule", "V1 Cockpit · Schedule"),
    ("cockpit-flowzen", "V1 Cockpit · Flowzen"),
    ("cockpit-mirofish", "V1 Cockpit · MiroFish"),
    ("cockpit-marketing", "V1 Cockpit · Marketing"),
    ("cockpit-n8n", "V1 Cockpit · n8n"),
    ("cockpit-video", "V1 Cockpit · Video"),
)


def _approved_portfolio_delegation() -> list[dict[str, object]]:
    return [
        {
            "cockpit_session_id": cockpit_session_id,
            "visible_title": visible_title,
            "approval_reference": _MAINTENANCE_DELEGATION_REFERENCE,
            "created_at": "2026-08-13T13:12:00Z",
        }
        for cockpit_session_id, visible_title in _PORTFOLIO_DELEGATION_TITLES
    ]


def test_committed_approval_ledger_contains_only_the_recorded_pre_creation_approvals() -> None:
    ledger = json.loads(APPROVAL_LEDGER_PATH.read_text(encoding="utf-8"))

    assert set(ledger) == {
        "schema_version",
        "membership_source",
        "approval_policy",
        "approvals",
    }
    assert ledger == _ledger(
        [
            _approved_openfang(),
            _approved_agentfarm(),
            _approved_git(),
            _approved_shared(),
            _approved_brain(),
            _approved_deployment(),
            *_approved_portfolio_delegation(),
        ]
    )


def test_missing_individual_approval_fails_closed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([]),
    )

    with pytest.raises(GovernanceError, match="individual cockpit approval is unavailable"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_unavailable_approval_ledger_fails_closed(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )

    with pytest.raises(GovernanceError, match="cockpit approval ledger is unavailable"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_exact_individual_approval_record_is_accepted(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([_approved_openfang()]),
    )

    approval = portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")

    assert approval.cockpit_session_id == "cockpit-openfang"
    assert approval.visible_title == "V1 Cockpit · OpenFang"
    assert approval.created_at == "2026-08-04T18:55:41+02:00"


def _approved_openfang_claude() -> dict[str, object]:
    return {
        "cockpit_session_id": "cockpit-openfang",
        "visible_title": "V1 Cockpit · OpenFang",
        "approval_reference": (
            "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@"
            "2026-08-13T10:00:00+02:00"
        ),
        "created_at": "2026-08-13T10:05:00+02:00",
    }


def test_claude_user_message_approval_record_is_accepted(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([_approved_openfang_claude()]),
    )

    approval = portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")

    assert approval.cockpit_session_id == "cockpit-openfang"
    assert approval.approval_reference == (
        "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@"
        "2026-08-13T10:00:00+02:00"
    )
    assert approval.created_at == "2026-08-13T10:05:00+02:00"


@pytest.mark.parametrize(
    "reference",
    (
        "claude-user-message:01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_abc123@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_01SdA3ftgP3wciDbcF!Kw4uk@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk",
        "claude-user-message: session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T10:00:00+02:00",
    ),
)
def test_malformed_claude_user_message_approval_fails_closed(
    tmp_path: Path, reference: str
) -> None:
    approval = _approved_openfang_claude()
    approval["approval_reference"] = reference
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([approval]),
    )

    with pytest.raises(GovernanceError, match="individual user message"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_standing_autonomy_cannot_approve_user_owned_cockpit(tmp_path: Path) -> None:
    approval = _approved_openfang()
    approval["approval_reference"] = "standing-autonomy:v1"
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([approval]),
    )

    with pytest.raises(GovernanceError, match="individual user message"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_impossible_approval_reference_timestamp_fails_closed(tmp_path: Path) -> None:
    approval = _approved_openfang()
    approval["approval_reference"] = (
        "codex-user-message:019fb3e4-0b82-7ef1-b722-883d480d2fea@"
        "2026-02-30T25:61:61Z"
    )
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([approval]),
    )

    with pytest.raises(GovernanceError, match="individual user message"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_cockpit_creation_cannot_precede_individual_approval(tmp_path: Path) -> None:
    approval = _approved_openfang()
    approval["created_at"] = "2026-08-03T15:59:59+02:00"
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([approval]),
    )

    with pytest.raises(GovernanceError, match="approval must not follow creation"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


@pytest.mark.parametrize("mutation", ("duplicate", "extra-key"))
def test_duplicate_or_open_approval_records_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    approval = _approved_openfang()
    approvals = [approval]
    if mutation == "duplicate":
        approvals.append(dict(approval))
    else:
        approval["status"] = "approved"
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger(approvals),
    )

    with pytest.raises(GovernanceError, match="cockpit approval ledger is malformed"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("visible_title", ""),
        ("created_at", "not-a-timestamp"),
        ("cockpit_session_id", "cockpit-not-registered"),
    ),
)
def test_malformed_or_nonmember_approval_fails_closed(
    tmp_path: Path, field: str, value: str
) -> None:
    approval = _approved_openfang()
    approval[field] = value
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([approval]),
    )

    with pytest.raises(GovernanceError, match="cockpit approval ledger is malformed"):
        portfolio.require_individual_cockpit_approval(tmp_path, "cockpit-openfang")


def test_cli_approval_check_rejects_remaining_unapproved_cockpit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_json(
        tmp_path / "docs/governance/session-portfolio-registry-v1.json",
        _registry(),
    )
    _write_json(
        tmp_path / "docs/governance/cockpit-approval-ledger-v1.json",
        _ledger([_approved_openfang()]),
    )

    exit_code = main(
        [
            "cockpit",
            "approval-check",
            "--repo",
            str(tmp_path),
            "--cockpit",
            "cockpit-agentfarm",
        ]
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out) == {
        "approved": False,
        "cockpit_session_id": "cockpit-agentfarm",
        "error": "individual cockpit approval is unavailable",
    }


@pytest.mark.parametrize(
    ("cockpit_session_id", "expected"),
    (
        ("cockpit-openfang", _approved_openfang()),
        ("cockpit-agentfarm", _approved_agentfarm()),
        ("cockpit-git", _approved_git()),
        ("cockpit-shared", _approved_shared()),
        ("cockpit-brain", _approved_brain()),
        ("cockpit-deployment", _approved_deployment()),
    ),
)
def test_cli_approval_check_accepts_committed_pre_creation_records(
    cockpit_session_id: str,
    expected: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "cockpit",
            "approval-check",
            "--repo",
            str(REPOSITORY_ROOT),
            "--cockpit",
            cockpit_session_id,
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        **expected,
        "approved": True,
    }


def test_runbook_requires_approval_record_before_user_owned_creation() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    normalized_runbook = " ".join(runbook.split())

    assert "cockpit-approval-ledger-v1.json" in runbook
    assert "before a User-Owned Codex thread is created" in normalized_runbook
    assert "does not backfill unverified approvals" in runbook
    assert "display metadata, not proof" in runbook
    assert "does not intercept the external Codex App API" in normalized_runbook
    assert "reference-only pointer" in runbook
    assert "maintenance delegation of 2026-08-13" in runbook
