from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tools.v1_governance import portfolio
from tools.v1_governance.cli import main
from tools.v1_governance.errors import GovernanceError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DIRECTORY = REPOSITORY_ROOT / "docs/governance"
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/runbooks/v1-session-lifecycle.md"


def _copy_governance_inputs(target_root: Path) -> None:
    target = target_root / "docs/governance"
    target.mkdir(parents=True)
    for filename in (
        "session-portfolio-registry-v1.json",
        "cockpit-approval-ledger-v1.json",
        "cockpit-activation-evidence-v1.json",
        "cockpit-external-observations-v1.json",
    ):
        shutil.copyfile(GOVERNANCE_DIRECTORY / filename, target / filename)


def test_cli_emits_one_deterministic_status_row_per_normative_cockpit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["cockpit", "portfolio-check", "--repo", str(REPOSITORY_ROOT)])

    assert exit_code == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(rows) == 22
    assert [row["cockpit_session_id"] for row in rows] == sorted(
        row["cockpit_session_id"] for row in rows
    )
    # Deliberately lifted by task-governance-0031 (wave 1..3) and
    # task-governance-0033 (wave 4..6): all 22 cockpits carry a recorded
    # git-evidenced-creation entry; interactivity stays fail-closed everywhere.
    assert rows[0] == {
        "cockpit_session_id": "cockpit-agentfarm",
        "current_activation_evidence": "git-evidenced-creation",
        "current_approval_evidence": "git-evidenced-approval-ledger",
        "current_interactivity_evidence": "not-git-evidenced",
        "durable_evidence_reference": (
            "ccr-session:session_01MVDw1byxFgk7L6rY7C1EL2@2026-08-14T13:54:06Z"
        ),
        "historical_observation_present": True,
        "membership": "normative",
        "pre_creation_approval_available": True,
    }
    assert next(row for row in rows if row["cockpit_session_id"] == "cockpit-brain") == {
        "cockpit_session_id": "cockpit-brain",
        "current_activation_evidence": "git-evidenced-creation",
        "current_approval_evidence": "git-evidenced-approval-ledger",
        "current_interactivity_evidence": "not-git-evidenced",
        "durable_evidence_reference": (
            "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21Z"
        ),
        "historical_observation_present": True,
        "membership": "normative",
        "pre_creation_approval_available": True,
    }
    assert next(
        row for row in rows if row["cockpit_session_id"] == "cockpit-integration"
    ) == {
        "cockpit_session_id": "cockpit-integration",
        "current_activation_evidence": "git-evidenced-creation",
        "current_approval_evidence": "git-evidenced-approval-ledger",
        "current_interactivity_evidence": "not-git-evidenced",
        "durable_evidence_reference": (
            "ccr-session:session_01RcmRkiDCyKN5tAdw5TLWCH@2026-08-13T15:24:30Z"
        ),
        "historical_observation_present": True,
        "membership": "normative",
        "pre_creation_approval_available": True,
    }
    assert all(row["current_interactivity_evidence"] == "not-git-evidenced" for row in rows)
    assert (
        sum(row["current_activation_evidence"] == "git-evidenced-creation" for row in rows)
        == 22
    )
    assert all(row["pre_creation_approval_available"] for row in rows)


def test_portfolio_check_rejects_synchronized_shrink_below_canonical_22(
    tmp_path: Path,
) -> None:
    _copy_governance_inputs(tmp_path)
    removed_cockpit = "cockpit-brain"
    for filename, collection in (
        ("session-portfolio-registry-v1.json", "cockpits"),
        ("cockpit-activation-evidence-v1.json", "cockpits"),
        ("cockpit-external-observations-v1.json", "observations"),
    ):
        path = tmp_path / "docs/governance" / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[collection] = [
            record
            for record in payload[collection]
            if record["cockpit_session_id"] != removed_cockpit
        ]
        path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        GovernanceError, match="cockpit registry does not match canonical portfolio membership"
    ):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_portfolio_check_rejects_external_observation_sidecar_membership_drift(
    tmp_path: Path,
) -> None:
    _copy_governance_inputs(tmp_path)
    sidecar_path = tmp_path / "docs/governance/cockpit-external-observations-v1.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["observations"][0]["cockpit_session_id"] = "cockpit-unregistered"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    with pytest.raises(GovernanceError, match="cockpit external observations sidecar is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_portfolio_check_rejects_open_current_evidence_fields(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    activation_path = tmp_path / "docs/governance/cockpit-activation-evidence-v1.json"
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    activation["cockpits"][0]["current_evidence"]["runtime_status"] = "active"
    activation_path.write_text(json.dumps(activation), encoding="utf-8")

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_runbook_documents_the_read_only_portfolio_status_check() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")

    assert "cockpit portfolio-check --repo ." in runbook
    assert "one JSON row per normative cockpit" in runbook
    assert "does not infer current activation or interactivity" in runbook
