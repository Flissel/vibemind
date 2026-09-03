from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, is_canonical_id, validate_document


IDENTIFIER = "01J8Q3Z4R5T6V7W8X9Y0ABCDEF"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"


def valid_bundle() -> dict[str, dict[str, object]]:
    return {
        "flowzen-checkin": {
            "contract_version": "v1",
            "checkin_id": f"checkin_v1_{IDENTIFIER}",
            "subject_ref": f"subject_v1_{IDENTIFIER}",
            "task_brief_ref": f"task_v1_{IDENTIFIER}",
            "intent_ref": f"intent_v1_{IDENTIFIER}",
            "trace_id": f"trace_v1_{IDENTIFIER}",
            "observed_at": "2026-07-31T09:00:00Z",
            "expires_at": "2026-07-31T09:15:00Z",
            "operation_class": "readonly",
            "signal_band": "neutral",
            "idempotency_key": f"checkin:checkin_v1_{IDENTIFIER}",
        },
        "flowzen-recommendation": {
            "contract_version": "v1",
            "recommendation_id": f"recommendation_v1_{IDENTIFIER}",
            "checkin_id": f"checkin_v1_{IDENTIFIER}",
            "subject_ref": f"subject_v1_{IDENTIFIER}",
            "task_brief_ref": f"task_v1_{IDENTIFIER}",
            "intent_ref": f"intent_v1_{IDENTIFIER}",
            "trace_id": f"trace_v1_{IDENTIFIER}",
            "generated_at": "2026-07-31T09:00:01Z",
            "expires_at": "2026-07-31T09:15:00Z",
            "operation_class": "readonly",
            "status": "proposed",
            "recommendation_kind": "focus",
            "title": "Ordne den nächsten Schritt.",
            "summary": "Wähle genau eine klar abgegrenzte Aufgabe für den aktuellen Fokusblock.",
            "evidence_refs": [f"evidence_v1_{IDENTIFIER}"],
            "cost": {
                "actual_cost_minor": 0,
                "currency": "EUR",
                "quote_ref": f"quote_v1_{IDENTIFIER}",
                "evidence_ref": f"evidence_v1_{IDENTIFIER}",
            },
        },
        "flowzen-acceptance": {
            "contract_version": "v1",
            "acceptance_id": f"acceptance_v1_{IDENTIFIER}",
            "recommendation_id": f"recommendation_v1_{IDENTIFIER}",
            "checkin_id": f"checkin_v1_{IDENTIFIER}",
            "subject_ref": f"subject_v1_{IDENTIFIER}",
            "task_brief_ref": f"task_v1_{IDENTIFIER}",
            "intent_ref": f"intent_v1_{IDENTIFIER}",
            "trace_id": f"trace_v1_{IDENTIFIER}",
            "accepted_at": "2026-07-31T09:00:02Z",
            "operation_class": "mutating",
            "expected_recommendation_status": "proposed",
            "approval_ref": f"approval_v1_{IDENTIFIER}",
            "idempotency_key": f"accept:recommendation_v1_{IDENTIFIER}",
            "parameter_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "timeout_seconds": 60,
            "cost_limit": {
                "max_cost_minor": 10,
                "currency": "EUR",
                "quote_ref": f"quote_v1_{IDENTIFIER}",
                "approval_ref": f"approval_v1_{IDENTIFIER}",
            },
        },
        "flowzen-acceptance-evidence": {
            "contract_version": "v1",
            "acceptance_id": f"acceptance_v1_{IDENTIFIER}",
            "recommendation_id": f"recommendation_v1_{IDENTIFIER}",
            "checkin_id": f"checkin_v1_{IDENTIFIER}",
            "subject_ref": f"subject_v1_{IDENTIFIER}",
            "task_brief_ref": f"task_v1_{IDENTIFIER}",
            "intent_ref": f"intent_v1_{IDENTIFIER}",
            "trace_id": f"trace_v1_{IDENTIFIER}",
            "started_at": "2026-07-31T09:00:02Z",
            "completed_at": "2026-07-31T09:00:03Z",
            "outcome": "succeeded",
            "readback": {
                "status": "accepted",
                "observed_at": "2026-07-31T09:00:03Z",
                "evidence_ref": f"evidence_v1_{IDENTIFIER}",
            },
            "cost": {
                "actual_cost_minor": 0,
                "currency": "EUR",
                "quote_ref": f"quote_v1_{IDENTIFIER}",
                "approval_ref": f"approval_v1_{IDENTIFIER}",
                "evidence_ref": f"evidence_v1_{IDENTIFIER}",
            },
        },
    }


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_flowzen_bundle", None)
    assert callable(validator), "Flowzen bundle validation is not registered."
    validator(bundle)


def load_fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_complete_flowzen_v1_bundle_validates_offline() -> None:
    validate_bundle(valid_bundle())


def test_valid_flowzen_bundle_fixture_validates_offline() -> None:
    fixture = load_fixture("flowzen_bundle")
    validate_bundle(fixture)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("document_type", "document_key"),
    (
        ("flowzen-checkin", "flowzen-checkin"),
        ("flowzen-recommendation", "flowzen-recommendation"),
        ("flowzen-acceptance", "flowzen-acceptance"),
        ("flowzen-acceptance-evidence", "flowzen-acceptance-evidence"),
    ),
)
def test_flowzen_v1_documents_are_registered(document_type: str, document_key: str) -> None:
    validate_document(document_type, valid_bundle()[document_key])


def test_acceptance_requires_explicit_approval_and_deterministic_recommendation_key() -> None:
    bundle = valid_bundle()
    del bundle["flowzen-acceptance"]["approval_ref"]
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["flowzen-acceptance"]["idempotency_key"] = "accept:other"
    with pytest.raises(ContractValidationError, match="idempotency"):
        validate_bundle(bundle)


def test_acceptance_cannot_precede_recommendation_generation() -> None:
    bundle = valid_bundle()
    bundle["flowzen-acceptance"]["accepted_at"] = "2026-07-31T09:00:00Z"

    with pytest.raises(ContractValidationError, match="generated_at"):
        validate_bundle(bundle)


def test_checkin_idempotency_key_must_be_deterministic_from_checkin_id() -> None:
    document = copy.deepcopy(valid_bundle()["flowzen-checkin"])
    document["idempotency_key"] = "flowzen.checkin.arbitrary"
    with pytest.raises(ContractValidationError):
        validate_document("flowzen-checkin", document)

    bundle = valid_bundle()
    bundle["flowzen-checkin"]["idempotency_key"] = (
        "checkin:checkin_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    )
    with pytest.raises(ContractValidationError, match="idempotency"):
        validate_bundle(bundle)


def test_success_requires_terminal_accepted_readback_within_timeout() -> None:
    bundle = valid_bundle()
    evidence = bundle["flowzen-acceptance-evidence"]
    evidence["readback"] = None
    with pytest.raises(ContractValidationError, match="readback"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["flowzen-acceptance-evidence"]["completed_at"] = "2026-07-31T09:01:03Z"
    with pytest.raises(ContractValidationError, match="timeout"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    "field_name",
    ("provider", "credential", "secret", "runtime", "endpoint", "http_status", "no_op"),
)
def test_flowzen_contracts_reject_runtime_secret_and_transport_success_fields(field_name: str) -> None:
    document = copy.deepcopy(valid_bundle()["flowzen-recommendation"])
    document[field_name] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("flowzen-recommendation", document)


@pytest.mark.parametrize(
    "identifier",
    (
        f"checkin_v1_{IDENTIFIER}",
        f"recommendation_v1_{IDENTIFIER}",
        f"acceptance_v1_{IDENTIFIER}",
        f"subject_v1_{IDENTIFIER}",
    ),
)
def test_flowzen_identifier_kinds_are_canonical(identifier: str) -> None:
    assert is_canonical_id(identifier)
