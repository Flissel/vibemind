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


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
DOCUMENT_TYPES = (
    ("workflow-request", "workflow_request"),
    ("workflow-definition-ref", "workflow_definition_ref"),
    ("workflow-change", "workflow_change"),
    ("workflow-run-request", "workflow_run_request"),
    ("workflow-run-state", "workflow_run_state"),
    ("workflow-run-evidence", "workflow_run_evidence"),
)


def n8n_operation_authority_validator() -> object:
    return getattr(contract_validation, "validate_n8n_operation_authority", None)


AUTHORITY_DRIFT_VALUES: dict[str, object] = {
    "run_id": "run_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "definition_id": "definition_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "workflow_id": "workflow_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "workflow_version": 4,
    "definition_revision": 6,
    "definition_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "request_id": "request_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "task_ref": "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "project_ref": "project_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "trace_id": "trace_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "mode": "test",
    "idempotency_key": "n8n-request-01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
    "approval_ref": "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG",
}

def load_fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def valid_bundle() -> dict[str, dict[str, object]]:
    value = load_fixture("workflow_bundle")
    return copy.deepcopy(value)  # type: ignore[return-value]


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_n8n_bundle", None)
    assert callable(validator), "n8n bundle validation is not registered."
    validator(bundle)


@pytest.mark.parametrize(("document_type", "fixture_name"), DOCUMENT_TYPES)
def test_valid_n8n_v1_documents_validate(document_type: str, fixture_name: str) -> None:
    validate_document(document_type, load_fixture(fixture_name))


def test_valid_n8n_operation_authority_validates_offline() -> None:
    validate_document("n8n-operation-authority", load_fixture("n8n_operation_authority"))


def test_n8n_operation_authority_accepts_non_mutating_read_status() -> None:
    document = load_fixture("n8n_operation_authority")
    document["operation"] = "read-status"

    validate_document("n8n-operation-authority", document)


def test_n8n_operation_authority_rejects_unknown_operations() -> None:
    document = load_fixture("n8n_operation_authority")
    document["operation"] = "delete"

    with pytest.raises(ContractValidationError, match="not one of"):
        validate_document("n8n-operation-authority", document)


@pytest.mark.parametrize("field_name", tuple(AUTHORITY_DRIFT_VALUES))
def test_n8n_operation_authority_rejects_reference_drift(field_name: str) -> None:
    validator = n8n_operation_authority_validator()
    assert callable(validator), "n8n operation-authority validation is not registered."
    authority = load_fixture("n8n_operation_authority")
    run_request = load_fixture("workflow_run_request")
    authority[field_name] = AUTHORITY_DRIFT_VALUES[field_name]

    with pytest.raises(ContractValidationError, match="drift"):
        validator(authority, run_request)


@pytest.mark.parametrize("operation", ("trigger", "cancel"))
@pytest.mark.parametrize("field_name", ("authority_ref", "approval_ref", "expires_at", "idempotency_key"))
def test_mutating_n8n_operations_require_authority_approval_expiry_and_idempotency(
    operation: str, field_name: str
) -> None:
    document = load_fixture("n8n_operation_authority")
    document["operation"] = operation
    del document[field_name]

    with pytest.raises(ContractValidationError, match="required property"):
        validate_document("n8n-operation-authority", document)


@pytest.mark.parametrize(
    "field_name",
    (
        "provider",
        "credential",
        "url",
        "endpoint",
        "command",
        "raw_workflow_content",
        "execution_target",
    ),
)
def test_n8n_operation_authority_is_closed_to_runtime_fields(field_name: str) -> None:
    document = load_fixture("n8n_operation_authority")
    document[field_name] = "forbidden"

    with pytest.raises(ContractValidationError, match="Additional properties"):
        validate_document("n8n-operation-authority", document)


def test_n8n_operation_authority_requires_expiry_after_issued_at() -> None:
    validator = n8n_operation_authority_validator()
    assert callable(validator), "n8n operation-authority validation is not registered."
    authority = load_fixture("n8n_operation_authority")
    authority["expires_at"] = "2026-07-31T09:00:00Z"

    with pytest.raises(ContractValidationError, match="expires_at"):
        validator(authority, load_fixture("workflow_run_request"))


def test_complete_n8n_bundle_validates_offline() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize(
    "field_name",
    (
        "provider",
        "credential",
        "secret",
        "token",
        "api_key",
        "runtime",
        "url",
        "webhook",
        "endpoint",
        "command",
        "shell",
        "db",
        "connection",
        "inline_workflow",
        "code",
    ),
)
def test_contracts_reject_provider_and_inline_runtime_fields(field_name: str) -> None:
    document = load_fixture("workflow_definition_ref")
    document[field_name] = "forbidden"

    with pytest.raises(ContractValidationError):
        validate_document("workflow-definition-ref", document)


def test_definition_requires_exact_hash_and_positive_immutable_version() -> None:
    document = load_fixture("workflow_definition_ref")
    document["definition_hash"] = "sha256:ABC"
    with pytest.raises(ContractValidationError):
        validate_document("workflow-definition-ref", document)

    document = load_fixture("workflow_definition_ref")
    document["workflow_version"] = 0
    with pytest.raises(ContractValidationError):
        validate_document("workflow-definition-ref", document)


def test_change_rejects_delete_action() -> None:
    document = load_fixture("workflow_change")
    document["action"] = "delete"
    with pytest.raises(ContractValidationError):
        validate_document("workflow-change", document)


def test_change_rejects_missing_approval() -> None:
    document = load_fixture("workflow_change")
    del document["approval_ref"]

    with pytest.raises(ContractValidationError):
        validate_document("workflow-change", document)


@pytest.mark.parametrize(
    ("action", "expected_lifecycle", "expected_revision"),
    (
        ("create", "draft", 0),
        ("create", "absent", 1),
        ("activate", "active", 4),
        ("deactivate", "inactive", 4),
        ("archive", "archived", 4),
        ("update", "archived", 4),
    ),
)
def test_change_requires_action_specific_non_archived_expected_lifecycle(
    action: str, expected_lifecycle: str, expected_revision: int
) -> None:
    document = load_fixture("workflow_change")
    document["action"] = action
    document["expected_lifecycle"] = expected_lifecycle
    document["expected_revision"] = expected_revision

    with pytest.raises(ContractValidationError):
        validate_document("workflow-change", document)


def test_create_change_requires_absent_lifecycle_and_zero_revision() -> None:
    document = load_fixture("workflow_change")
    document.update({"action": "create", "expected_lifecycle": "absent", "expected_revision": 0})

    validate_document("workflow-change", document)


@pytest.mark.parametrize(
    ("action", "expected_lifecycle"),
    (
        ("update", "active"),
        ("activate", "inactive"),
        ("deactivate", "active"),
        ("archive", "draft"),
    ),
)
def test_non_create_change_requires_positive_expected_revision(
    action: str, expected_lifecycle: str
) -> None:
    document = load_fixture("workflow_change")
    document.update(
        {"action": action, "expected_lifecycle": expected_lifecycle, "expected_revision": 0}
    )

    with pytest.raises(ContractValidationError):
        validate_document("workflow-change", document)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("timeout_seconds", 0),
        ("timeout_seconds", 3_601),
        ("max_steps", 0),
        ("max_steps", 501),
        ("max_retries", 11),
        ("max_cost_minor", 1.5),
    ),
)
def test_run_request_requires_finite_integer_caps(field_name: str, value: object) -> None:
    document = load_fixture("workflow_run_request")
    if field_name == "max_cost_minor":
        budget = document["budget"]
        assert isinstance(budget, dict)
        budget[field_name] = value
    else:
        document[field_name] = value
    with pytest.raises(ContractValidationError):
        validate_document("workflow-run-request", document)


@pytest.mark.parametrize(
    "mutation",
    (
        "unknown_status",
        "illegal_transition",
        "reopen_terminal",
        "nonmonotonic_time",
        "final_status_mismatch",
    ),
)
def test_run_state_rejects_invalid_or_reopened_lifecycle(mutation: str) -> None:
    document = load_fixture("workflow_run_state")
    history = document["event_history"]
    assert isinstance(history, list)
    assert all(isinstance(item, dict) for item in history)
    if mutation == "unknown_status":
        history[-1]["status"] = "unknown"
    elif mutation == "illegal_transition":
        history[1]["status"] = "succeeded"
    elif mutation == "reopen_terminal":
        history.append({"status": "queued", "occurred_at": "2026-07-31T09:00:04Z", "revision": 5})
        document["revision"] = 5
        document["status"] = "queued"
    elif mutation == "nonmonotonic_time":
        history[2]["occurred_at"] = "2026-07-31T08:59:59Z"
    else:
        document["status"] = "running"
    with pytest.raises(ContractValidationError):
        validate_document("workflow-run-state", document)


def test_cancelled_state_requires_cancellation_semantics() -> None:
    document = load_fixture("workflow_run_state")
    history = document["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    history[-1]["status"] = "cancelled"
    document["status"] = "cancelled"
    document["cancellation_requested"] = False
    with pytest.raises(ContractValidationError, match="cancellation"):
        validate_document("workflow-run-state", document)


@pytest.mark.parametrize("status", ("succeeded", "failed", "unavailable"))
def test_requested_cancellation_rejects_non_cancelled_terminal_state(status: str) -> None:
    document = load_fixture("workflow_run_state")
    history = document["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    history[-1]["status"] = status
    document["status"] = status
    document["cancellation_requested"] = True

    with pytest.raises(ContractValidationError, match="cancellation"):
        validate_document("workflow-run-state", document)


@pytest.mark.parametrize("first_status", ("succeeded", "waiting_for_approval", "running"))
def test_run_state_rejects_non_initial_lifecycle_start(first_status: str) -> None:
    document = load_fixture("workflow_run_state")
    history = document["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[0], dict)
    history[0]["status"] = first_status

    with pytest.raises(ContractValidationError, match="begin"):
        validate_document("workflow-run-state", document)


def test_run_state_accepts_a_clarification_required_start() -> None:
    document = load_fixture("workflow_run_state")
    document["status"] = "clarification_required"
    document["revision"] = 1
    document["event_history"] = [
        {"status": "clarification_required", "occurred_at": "2026-07-31T09:00:00Z", "revision": 1}
    ]
    counters = document["counters"]
    assert isinstance(counters, dict)
    counters["executed_steps"] = 0
    document["evidence_refs"] = []
    document["artifact_refs"] = []
    document["log_refs"] = []

    validate_document("workflow-run-state", document)


def test_complete_bundle_requires_resolved_clarification_matching_approval_and_fresh_revision() -> None:
    bundle = valid_bundle()
    request = bundle["workflow-request"]
    clarification = request["clarification"]
    assert isinstance(clarification, dict)
    clarification.update({"required": True, "questions": ["Bitte präzisiere das Ziel."]})
    with pytest.raises(ContractValidationError, match="clarification"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["workflow-run-request"]["approval_ref"] = "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    with pytest.raises(ContractValidationError, match="approval_ref"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["workflow-change"]["expected_revision"] = 3
    with pytest.raises(ContractValidationError, match="expected_revision"):
        validate_bundle(bundle)


def test_complete_bundle_requires_active_definition_and_declared_caps() -> None:
    bundle = valid_bundle()
    bundle["workflow-definition-ref"]["lifecycle"] = "archived"
    with pytest.raises(ContractValidationError, match="active"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["workflow-run-request"]["max_steps"] = 51
    with pytest.raises(ContractValidationError, match="max_steps"):
        validate_bundle(bundle)


def test_execution_bundle_requires_activate_from_draft_or_inactive_lifecycle() -> None:
    bundle = valid_bundle()
    bundle["workflow-change"]["expected_lifecycle"] = "active"

    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    "mutation",
    ("success_without_refs", "failed_without_redacted_class", "float_cost", "over_budget"),
)
def test_evidence_requires_terminal_outcome_refs_redaction_and_integer_budget(mutation: str) -> None:
    document = load_fixture("workflow_run_evidence")
    if mutation == "success_without_refs":
        document["log_refs"] = []
    elif mutation == "failed_without_redacted_class":
        document["outcome"] = "failed"
    elif mutation == "float_cost":
        cost = document["cost"]
        assert isinstance(cost, dict)
        cost["actual_cost_minor"] = 1.5
    else:
        cost = document["cost"]
        assert isinstance(cost, dict)
        cost["actual_cost_minor"] = 10_000_001
    with pytest.raises(ContractValidationError):
        validate_document("workflow-run-evidence", document)


@pytest.mark.parametrize("mutation", ("outcome", "refs", "count", "cost"))
def test_bundle_rejects_state_evidence_outcome_reference_counter_and_cost_drift(mutation: str) -> None:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    evidence = bundle["workflow-run-evidence"]
    if mutation == "outcome":
        evidence["outcome"] = "failed"
        evidence["error_class"] = "execution_failed"
    elif mutation == "refs":
        evidence["log_refs"] = ["log_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"]
    elif mutation == "count":
        evidence["executed_steps"] = 8
    else:
        cost = evidence["cost"]
        assert isinstance(cost, dict)
        cost["actual_cost_minor"] = 751
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_bundle_rejects_requested_cancellation_with_success_evidence() -> None:
    bundle = valid_bundle()
    bundle["workflow-run-state"]["cancellation_requested"] = True

    with pytest.raises(ContractValidationError, match="cancellation"):
        validate_bundle(bundle)


def cancelled_bundle_without_running_steps() -> dict[str, dict[str, object]]:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    evidence = bundle["workflow-run-evidence"]
    state.update(
        {
            "status": "cancelled",
            "revision": 3,
            "event_history": [
                {"status": "queued", "occurred_at": "2026-07-31T09:00:00Z", "revision": 1},
                {"status": "waiting_for_approval", "occurred_at": "2026-07-31T09:00:01Z", "revision": 2},
                {"status": "cancelled", "occurred_at": "2026-07-31T09:00:02Z", "revision": 3},
            ],
            "cancellation_requested": True,
            "evidence_refs": [],
            "artifact_refs": [],
            "log_refs": [],
        }
    )
    counters = state["counters"]
    assert isinstance(counters, dict)
    counters["executed_steps"] = 0
    evidence.update(
        {
            "outcome": "cancelled",
            "started_at": "2026-07-31T09:00:00Z",
            "completed_at": "2026-07-31T09:00:02Z",
            "executed_steps": 0,
            "evidence_refs": [],
            "artifact_refs": [],
            "log_refs": [],
        }
    )
    return bundle


def test_bundle_accepts_cancelled_while_waiting_with_zero_steps() -> None:
    validate_bundle(cancelled_bundle_without_running_steps())


def test_bundle_rejects_evidence_start_before_first_state_event() -> None:
    bundle = cancelled_bundle_without_running_steps()
    bundle["workflow-run-evidence"]["started_at"] = "2026-07-31T08:59:59Z"

    with pytest.raises(ContractValidationError, match="first state event"):
        validate_bundle(bundle)


def test_bundle_normalizes_offset_equivalent_evidence_start_and_first_state_event() -> None:
    bundle = cancelled_bundle_without_running_steps()
    evidence = bundle["workflow-run-evidence"]
    evidence["started_at"] = "2026-07-31T11:00:00+02:00"
    evidence["completed_at"] = "2026-07-31T11:00:02+02:00"

    validate_bundle(bundle)


def test_bundle_requires_running_for_cancelled_evidence_with_executed_steps() -> None:
    bundle = cancelled_bundle_without_running_steps()
    state = bundle["workflow-run-state"]
    evidence = bundle["workflow-run-evidence"]
    counters = state["counters"]
    assert isinstance(counters, dict)
    counters["executed_steps"] = 1
    evidence["executed_steps"] = 1

    with pytest.raises(ContractValidationError, match="running"):
        validate_bundle(bundle)


def test_bundle_requires_final_state_timestamp_to_match_evidence_completion() -> None:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    history = state["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    history[-1]["occurred_at"] = "2026-07-31T09:00:04Z"

    with pytest.raises(ContractValidationError, match="completed_at"):
        validate_bundle(bundle)


def test_bundle_requires_running_before_non_cancelled_terminal_outcome() -> None:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    evidence = bundle["workflow-run-evidence"]
    state.update(
        {
            "status": "unavailable",
            "revision": 2,
            "event_history": [
                {"status": "queued", "occurred_at": "2026-07-31T09:00:00Z", "revision": 1},
                {"status": "unavailable", "occurred_at": "2026-07-31T09:00:01Z", "revision": 2},
            ],
            "evidence_refs": [],
            "artifact_refs": [],
            "log_refs": [],
        }
    )
    counters = state["counters"]
    assert isinstance(counters, dict)
    counters["executed_steps"] = 0
    evidence.update(
        {
            "outcome": "unavailable",
            "started_at": "2026-07-31T09:00:00Z",
            "completed_at": "2026-07-31T09:00:01Z",
            "executed_steps": 0,
            "evidence_refs": [],
            "artifact_refs": [],
            "log_refs": [],
            "error_class": "unavailable",
        }
    )

    with pytest.raises(ContractValidationError, match="running"):
        validate_bundle(bundle)


def test_bundle_rejects_running_event_after_evidence_start() -> None:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    history = state["event_history"]
    evidence = bundle["workflow-run-evidence"]
    assert isinstance(history, list)
    assert isinstance(history[-2], dict)
    assert isinstance(history[-1], dict)
    history[-2]["occurred_at"] = "2026-07-31T09:00:04Z"
    history[-1]["occurred_at"] = "2026-07-31T09:00:05Z"
    evidence["completed_at"] = "2026-07-31T09:00:05Z"

    with pytest.raises(ContractValidationError, match="started_at"):
        validate_bundle(bundle)


def test_bundle_normalizes_offset_equivalent_final_timestamp() -> None:
    bundle = valid_bundle()
    state = bundle["workflow-run-state"]
    history = state["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[-2], dict)
    assert isinstance(history[-1], dict)
    history[-2]["occurred_at"] = "2026-07-31T11:00:02+02:00"
    history[-1]["occurred_at"] = "2026-07-31T11:00:03+02:00"

    validate_bundle(bundle)


@pytest.mark.parametrize(
    "identifier",
    (
        "project_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "workflow_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "definition_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "capability_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "log_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    ),
)
def test_n8n_contract_identifier_kinds_are_canonical(identifier: str) -> None:
    assert is_canonical_id(identifier)
