"""Static drift guard for the offline evidence-governance contract."""

from pathlib import Path


CONTRACT = Path("docs/contracts/observability-evidence-governance-v2.md")
SHARED_CORE = Path("docs/contracts/v1-shared-contract-core.md")


def _contract_text() -> str:
    assert CONTRACT.is_file(), "the observability evidence-governance contract is required"
    return CONTRACT.read_text(encoding="utf-8")


def test_evidence_classes_and_verified_live_threshold_are_normative() -> None:
    contract = _contract_text()

    for statement in (
        "`static`",
        "`configured`",
        "`historical`",
        "`reachable`",
        "`verified_live`",
        "fresh, operation-specific, end-to-end evidence",
        "No current system is `verified_live` under this contract.",
    ):
        assert statement in contract


def test_non_terminal_or_non_live_signals_cannot_be_verified_live() -> None:
    contract = _contract_text()

    for statement in (
        "Transport success is not `verified_live`.",
        "Health success is not `verified_live`.",
        "An HTTP 2xx response is not `verified_live`.",
        "Mocks are not `verified_live`.",
        "No-op results are not `verified_live`.",
        "Queued status is not `verified_live`.",
        "Registry matches are not `verified_live`.",
        "Offline-terminal documents are not `verified_live`.",
    ):
        assert statement in contract


def test_evidence_reference_durability_and_acceptance_are_separate() -> None:
    contract = _contract_text()
    shared_core = SHARED_CORE.read_text(encoding="utf-8")

    assert "`EvidenceRefV1` is a durable reference, not acceptance." in contract
    assert "In-memory or event transport is not durable evidence." in contract
    assert "Evidence acceptance remains an explicit owner decision." in contract
    assert "An `EvidenceRefV1` is a durable reference" in shared_core
    assert "not a claim that the evidence has been evaluated or accepted" in shared_core


def test_redaction_retention_and_openfang_runtime_behavior_are_explicitly_out_of_scope() -> None:
    contract = _contract_text()

    for statement in (
        "Redaction is reference-only in this wave.",
        "Retention is explicitly `unassigned` until a separate contract exists.",
        "OpenFang is the MVP execution boundary, but its runtime behavior is outside this evidence-classification contract.",
        "This contract adds no schema, validator, runtime persistence, adapter, database, deployment, live probe, Golden Path, or OpenFang behavior.",
    ):
        assert statement in contract
