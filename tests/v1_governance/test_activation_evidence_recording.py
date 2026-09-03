from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tools.v1_governance import portfolio
from tools.v1_governance.errors import GovernanceError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DIRECTORY = REPOSITORY_ROOT / "docs/governance"

CREATION_REFERENCE = "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21Z"


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


def _set_current_evidence(
    target_root: Path,
    cockpit_id: str,
    *,
    activation: str,
    interactivity: str,
    approval: str,
    durable_evidence_reference: str | None,
) -> None:
    path = target_root / "docs/governance/cockpit-activation-evidence-v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record in payload["cockpits"]:
        if record["cockpit_session_id"] == cockpit_id:
            record["current_evidence"] = {
                "activation": activation,
                "interactivity": interactivity,
                "approval": approval,
                "durable_evidence_reference": durable_evidence_reference,
            }
            break
    else:  # pragma: no cover - guard against typos in test data
        raise AssertionError(f"unknown cockpit id {cockpit_id}")
    path.write_text(json.dumps(payload), encoding="utf-8")


def _row(rows: tuple[portfolio.CockpitPortfolioStatus, ...], cockpit_id: str) -> dict[str, object]:
    return next(
        row.to_mapping() for row in rows if row.cockpit_session_id == cockpit_id
    )


def test_accepts_git_evidenced_creation_with_durable_ccr_session_reference(
    tmp_path: Path,
) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    row = _row(portfolio.cockpit_portfolio_status(tmp_path), "cockpit-brain")

    assert row["current_activation_evidence"] == "git-evidenced-creation"
    assert row["current_interactivity_evidence"] == "not-git-evidenced"
    assert row["current_approval_evidence"] == "not-git-evidenced"
    assert row["durable_evidence_reference"] == CREATION_REFERENCE


def test_accepts_approval_ledger_class_alongside_creation_class(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval="git-evidenced-approval-ledger",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    row = _row(portfolio.cockpit_portfolio_status(tmp_path), "cockpit-brain")

    assert row["current_activation_evidence"] == "git-evidenced-creation"
    assert row["current_approval_evidence"] == "git-evidenced-approval-ledger"


def test_keeps_fully_not_git_evidenced_entry_valid(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="not-git-evidenced",
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=None,
    )

    row = _row(portfolio.cockpit_portfolio_status(tmp_path), "cockpit-brain")

    assert row["current_activation_evidence"] == "not-git-evidenced"
    assert row["current_interactivity_evidence"] == "not-git-evidenced"
    assert row["current_approval_evidence"] == "not-git-evidenced"
    assert row["durable_evidence_reference"] is None


def test_rejects_creation_class_without_reference(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=None,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


@pytest.mark.parametrize(
    "reference",
    [
        "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT",
        "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21",
        "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13",
        "ccr-session:sess_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21Z",
        "ccr-session:session_short@2026-08-13T10:08:21Z",
        "claude-user-message:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21Z",
        "standing-autonomy:v1",
        "",
    ],
)
def test_rejects_malformed_durable_reference_shapes(
    tmp_path: Path, reference: str
) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=reference,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_rejects_reference_without_creation_class(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="not-git-evidenced",
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


@pytest.mark.parametrize(
    "interactivity",
    ["git-evidenced-creation", "interactive", "git-evidenced-interactivity"],
)
def test_rejects_interactivity_claims_even_with_reference(
    tmp_path: Path, interactivity: str
) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity=interactivity,
        approval="not-git-evidenced",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


@pytest.mark.parametrize(
    "activation",
    ["active", "git-evidenced-runtime", "git-evidenced-activation", "verified-live"],
)
def test_rejects_unknown_activation_vocabulary(tmp_path: Path, activation: str) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation=activation,
        interactivity="not-git-evidenced",
        approval="not-git-evidenced",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


@pytest.mark.parametrize(
    "approval",
    ["approved", "git-evidenced-approval", "approval-ledger"],
)
def test_rejects_unknown_approval_vocabulary(tmp_path: Path, approval: str) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval=approval,
        durable_evidence_reference=CREATION_REFERENCE,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_rejects_approval_class_without_creation_class(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="not-git-evidenced",
        interactivity="not-git-evidenced",
        approval="git-evidenced-approval-ledger",
        durable_evidence_reference=None,
    )

    with pytest.raises(GovernanceError, match="cockpit activation evidence is malformed"):
        portfolio.cockpit_portfolio_status(tmp_path)


def test_rejects_approval_class_when_ledger_entry_is_missing(tmp_path: Path) -> None:
    _copy_governance_inputs(tmp_path)
    ledger_path = tmp_path / "docs/governance/cockpit-approval-ledger-v1.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["approvals"] = [
        record
        for record in ledger["approvals"]
        if record["cockpit_session_id"] != "cockpit-brain"
    ]
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    _set_current_evidence(
        tmp_path,
        "cockpit-brain",
        activation="git-evidenced-creation",
        interactivity="not-git-evidenced",
        approval="git-evidenced-approval-ledger",
        durable_evidence_reference=CREATION_REFERENCE,
    )

    with pytest.raises(
        GovernanceError,
        match="cockpit activation evidence approval claim lacks a ledger approval",
    ):
        portfolio.cockpit_portfolio_status(tmp_path)
