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
    ("schedule-request", "schedule_request"),
    ("schedule-definition", "schedule_definition"),
    ("schedule-change", "schedule_change"),
    ("schedule-state", "schedule_state"),
    ("schedule-run-evidence", "schedule_run_evidence"),
)


def load_fixture(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def valid_bundle() -> dict[str, dict[str, object]]:
    value = load_fixture("schedule_bundle")
    return copy.deepcopy(value)  # type: ignore[return-value]


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_schedule_bundle", None)
    assert callable(validator), "Schedule bundle validation is not registered."
    validator(bundle)


def recurring_success_bundle() -> dict[str, dict[str, object]]:
    bundle = valid_bundle()
    request_limits = bundle["schedule-request"]["limits"]
    definition = bundle["schedule-definition"]
    definition_limits = definition["limits"]
    schedule = definition["schedule"]
    state = bundle["schedule-state"]
    counters = state["counters"]
    history = state["status_history"]
    assert isinstance(request_limits, dict)
    assert isinstance(definition_limits, dict)
    assert isinstance(schedule, dict)
    assert isinstance(counters, dict)
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    request_limits["max_runs"] = 2
    definition_limits["max_runs"] = 2
    schedule.clear()
    schedule.update(
        {"mode": "interval", "starts_at": "2026-08-01T07:00:00Z", "every_seconds": 3600}
    )
    history[-1] = {"status": "scheduled", "occurred_at": "2026-08-01T07:00:01Z", "revision": 5}
    state["status"] = "scheduled"
    state["next_run_at"] = "2026-08-01T08:00:00Z"
    counters["run_count"] = 1
    counters["max_runs"] = 2
    return bundle


@pytest.mark.parametrize(("document_type", "fixture_name"), DOCUMENT_TYPES)
def test_valid_schedule_v1_documents_validate(document_type: str, fixture_name: str) -> None:
    validate_document(document_type, load_fixture(fixture_name))


def test_complete_schedule_bundle_validates_offline() -> None:
    validate_bundle(valid_bundle())


def test_complete_execution_bundle_requires_run_now_change() -> None:
    bundle = valid_bundle()
    bundle["schedule-change"]["action"] = "update"

    with pytest.raises(ContractValidationError, match="run_now"):
        validate_bundle(bundle)


def test_recurring_success_returns_to_scheduled_until_max_runs() -> None:
    validate_bundle(recurring_success_bundle())


@pytest.mark.parametrize(
    ("status", "run_count", "max_runs", "next_run_at"),
    (
        ("succeeded", 1, 2, None),
        ("scheduled", 2, 2, "2026-08-01T08:00:00Z"),
    ),
)
def test_state_enforces_run_count_against_its_lifecycle_status(
    status: str, run_count: int, max_runs: int, next_run_at: object
) -> None:
    document = load_fixture("schedule_state")
    history = document["status_history"]
    counters = document["counters"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    assert isinstance(counters, dict)
    history[-1]["status"] = status
    document["status"] = status
    document["next_run_at"] = next_run_at
    counters["run_count"] = run_count
    counters["max_runs"] = max_runs

    with pytest.raises(ContractValidationError, match="max_runs"):
        validate_document("schedule-state", document)


def test_interval_execution_bundle_rejects_evidence_before_start_anchor() -> None:
    bundle = recurring_success_bundle()
    bundle["schedule-run-evidence"]["scheduled_for"] = "2026-08-01T06:59:00Z"

    with pytest.raises(ContractValidationError, match="starts_at"):
        validate_bundle(bundle)


def test_interval_execution_bundle_rejects_evidence_off_the_deterministic_grid() -> None:
    bundle = recurring_success_bundle()
    evidence = bundle["schedule-run-evidence"]
    state = bundle["schedule-state"]
    assert isinstance(state, dict)
    evidence["scheduled_for"] = "2026-08-01T07:00:30Z"
    evidence["started_at"] = "2026-08-01T07:00:30Z"
    evidence["completed_at"] = "2026-08-01T07:00:31Z"
    state["last_run_at"] = "2026-08-01T07:00:31Z"

    with pytest.raises(ContractValidationError, match="grid"):
        validate_bundle(bundle)


def test_interval_execution_bundle_requires_next_run_after_last_run() -> None:
    bundle = recurring_success_bundle()
    bundle["schedule-state"]["next_run_at"] = "2026-08-01T07:00:01Z"

    with pytest.raises(ContractValidationError, match="next_run_at"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("state_status", "next_run_at"),
    (
        ("scheduled", None),
        ("succeeded", "2026-08-01T08:00:00Z"),
        ("failed", "2026-08-01T08:00:00Z"),
        ("cancelled", "2026-08-01T08:00:00Z"),
        ("unavailable", "2026-08-01T08:00:00Z"),
    ),
)
def test_state_requires_next_run_for_scheduled_and_null_for_terminal_states(
    state_status: str, next_run_at: object
) -> None:
    document = load_fixture("schedule_state")
    history = document["status_history"]
    counters = document["counters"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    assert isinstance(counters, dict)
    history[-1]["status"] = state_status
    document["status"] = state_status
    document["next_run_at"] = next_run_at
    if state_status == "scheduled":
        counters["run_count"] = 0
    with pytest.raises(ContractValidationError, match="next_run_at"):
        validate_document("schedule-state", document)


def test_execution_bundle_requires_last_run_timestamp_to_equal_evidence_completion() -> None:
    bundle = valid_bundle()
    bundle["schedule-state"]["last_run_at"] = "2026-08-01T07:00:02Z"

    with pytest.raises(ContractValidationError, match="last_run_at"):
        validate_bundle(bundle)


def test_one_shot_execution_bundle_requires_scheduled_for_to_match_run_at() -> None:
    bundle = valid_bundle()
    bundle["schedule-run-evidence"]["scheduled_for"] = "2026-08-01T07:01:00Z"

    with pytest.raises(ContractValidationError, match="scheduled_for"):
        validate_bundle(bundle)


def test_execution_bundle_rejects_unresolved_clarification() -> None:
    bundle = valid_bundle()
    clarification = bundle["schedule-request"]["clarification"]
    assert isinstance(clarification, dict)
    clarification["required"] = True
    clarification["questions"] = ["Bitte präzisiere die lokale DST-Zeit."]
    bundle["schedule-definition"]["clarification_required"] = True

    with pytest.raises(ContractValidationError, match="clarification"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("document_type", "fixture_name", "field_name", "value"),
    (
        ("schedule-request", "schedule_request", "requested_at", "2026-07-31T09:00:00"),
        ("schedule-definition", "schedule_definition", "timezone", "Berlin"),
        ("schedule-run-evidence", "schedule_run_evidence", "started_at", "2026-07-31T09:00:00"),
    ),
)
def test_schedule_documents_reject_naive_timestamps_and_non_iana_timezone(
    document_type: str, fixture_name: str, field_name: str, value: str
) -> None:
    document = load_fixture(fixture_name)
    document[field_name] = value
    with pytest.raises(ContractValidationError):
        validate_document(document_type, document)


@pytest.mark.parametrize(
    "mutation",
    (
        {"mode": "one_shot", "run_at": "2026-07-31T09:00:00Z", "every_seconds": 60},
        {"mode": "one_shot"},
        {"mode": "interval", "every_seconds": 60, "run_at": "2026-07-31T09:00:00Z"},
        {"mode": "interval", "every_seconds": 0},
        {"mode": "interval", "every_seconds": 2_592_001},
        {"mode": "cron", "expression": "0 9 * *"},
    ),
)
def test_schedule_definition_rejects_invalid_modes_and_bounds(mutation: dict[str, object]) -> None:
    document = load_fixture("schedule_definition")
    schedule = document["schedule"]
    assert isinstance(schedule, dict)
    schedule.clear()
    schedule.update(mutation)
    with pytest.raises(ContractValidationError):
        validate_document("schedule-definition", document)


@pytest.mark.parametrize(
    "schedule_value",
    (
        {"mode": "interval", "every_seconds": 60},
        {"mode": "interval", "starts_at": "2026-08-01T07:00:00", "every_seconds": 60},
        {
            "mode": "interval",
            "starts_at": "2026-08-01T07:00:00Z",
            "every_seconds": 60,
            "run_at": "2026-08-01T07:00:00Z",
        },
    ),
)
def test_interval_schedule_requires_an_exclusive_aware_start_anchor(
    schedule_value: dict[str, object]
) -> None:
    document = load_fixture("schedule_definition")
    document["schedule"] = schedule_value
    with pytest.raises(ContractValidationError):
        validate_document("schedule-definition", document)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("limits", "max_runs"), 0),
        (("limits", "max_runs"), 1_001),
        (("retry_policy", "max_retries"), 11),
        (("retry_policy", "retry_delay_seconds"), 0),
        (("retry_policy", "retry_delay_seconds"), 86_401),
    ),
)
def test_schedule_definition_rejects_unbounded_or_invalid_run_retry_limits(
    path: tuple[str, str], value: int
) -> None:
    document = load_fixture("schedule_definition")
    nested = document[path[0]]
    assert isinstance(nested, dict)
    nested[path[1]] = value
    with pytest.raises(ContractValidationError):
        validate_document("schedule-definition", document)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("action", "list"), ("approval_ref", ""), ("expected_revision", -1)),
)
def test_schedule_change_is_declarative_and_requires_approval_and_revision(
    field_name: str, value: object
) -> None:
    document = load_fixture("schedule_change")
    document[field_name] = value
    with pytest.raises(ContractValidationError):
        validate_document("schedule-change", document)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("unknown_status", "invalid"),
        ("illegal_transition", "transition"),
        ("reopen_terminal", "transition"),
        ("non_monotonic_time", "monotonic"),
        ("final_status_mismatch", "last"),
    ),
)
def test_schedule_state_fails_closed_for_invalid_lifecycle_history(
    mutation: str, message: str
) -> None:
    document = load_fixture("schedule_state")
    history = document["status_history"]
    assert isinstance(history, list)
    assert all(isinstance(item, dict) for item in history)
    if mutation == "unknown_status":
        history[-1]["status"] = "queued"
    elif mutation == "illegal_transition":
        history[1]["status"] = "succeeded"
    elif mutation == "reopen_terminal":
        history.append({"status": "scheduled", "occurred_at": "2026-07-31T09:00:03Z", "revision": 6})
        document["status"] = "scheduled"
        document["revision"] = 6
    elif mutation == "non_monotonic_time":
        history[2]["occurred_at"] = "2026-07-31T09:00:00Z"
    else:
        document["status"] = "running"
    with pytest.raises(ContractValidationError, match=message):
        validate_document("schedule-state", document)


def test_schedule_bundle_rejects_reference_revision_and_idempotency_drift() -> None:
    bundle = valid_bundle()
    bundle["schedule-definition"]["idempotency_key"] = "different-key"
    with pytest.raises(ContractValidationError, match="idempotency"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["schedule-change"]["expected_revision"] = 3
    with pytest.raises(ContractValidationError, match="expected_revision"):
        validate_bundle(bundle)

    bundle = valid_bundle()
    bundle["schedule-run-evidence"]["trace_id"] = "trace_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    with pytest.raises(ContractValidationError, match="trace_id"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("outcome", "field_name", "value"),
    (
        ("succeeded", "evidence_refs", []),
        ("failed", "error_class", None),
        ("unavailable", "error_class", "raw provider response"),
    ),
)
def test_schedule_run_evidence_requires_outcome_specific_evidence_or_redacted_classification(
    outcome: str, field_name: str, value: object
) -> None:
    document = load_fixture("schedule_run_evidence")
    document["outcome"] = outcome
    document[field_name] = value
    with pytest.raises(ContractValidationError):
        validate_document("schedule-run-evidence", document)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("cost", "actual_cost_minor"), 1.25),
        (("cost", "actual_cost_minor"), 501),
        (("schedule-definition", "budget", "max_cost_minor"), 99),
        (("schedule-definition", "budget", "currency"), "USD"),
    ),
)
def test_schedule_bundle_rejects_float_over_budget_and_cost_reference_drift(
    path: tuple[str, ...], value: object
) -> None:
    bundle = valid_bundle()
    if len(path) == 2:
        nested = bundle["schedule-run-evidence"][path[0]]
        assert isinstance(nested, dict)
        nested[path[1]] = value
    else:
        nested = bundle[path[0]][path[1]]
        assert isinstance(nested, dict)
        nested[path[2]] = value
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize("field_name", ("provider", "credential", "runtime", "command", "db", "endpoint", "action_text"))
def test_schedule_contracts_reject_free_execution_and_secret_bearing_fields(field_name: str) -> None:
    document = load_fixture("schedule_definition")
    document[field_name] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("schedule-definition", document)


@pytest.mark.parametrize(
    "identifier",
    (
        "schedule_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "change_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "run_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "intent_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    ),
)
def test_new_schedule_contract_identifier_kinds_are_canonical(identifier: str) -> None:
    assert is_canonical_id(identifier)
