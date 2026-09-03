from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, validate_document


FIXTURES = ROOT / "tests" / "contracts"
LIFECYCLE_SCHEMA = ROOT / "shared" / "contracts" / "brain" / "v1" / "brain-plan-lifecycle-v1.schema.json"
SPACE_EXECUTION_SCHEMA = ROOT / "shared" / "contracts" / "schemas" / "space-execution-contract-v1.schema.json"
SPACE_IDENTITY_SNAPSHOT = ROOT / "shared" / "contracts" / "snapshots" / "space-identity-snapshot-v1.json"


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def fixture(category: str, name: str) -> dict[str, object]:
    return load_json(FIXTURES / "brain" / "fixtures" / category / f"{name}.json")


def shared_fixture(category: str, name: str) -> dict[str, object]:
    return load_json(FIXTURES / "fixtures" / category / f"{name}.json")


def valid_bundle() -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    channel_intent = shared_fixture("valid", "channel_intent")
    channel_intent["requested_space_id"] = "research"
    brain_plan = shared_fixture("valid", "brain_plan")
    participating_spaces = brain_plan["participating_spaces"]
    tasks = brain_plan["tasks"]
    assert isinstance(participating_spaces, list) and isinstance(tasks, list)
    second_space = participating_spaces[1]
    second_task = tasks[1]
    assert isinstance(second_space, dict) and isinstance(second_task, dict)
    second_space["space_id"] = "coding"
    second_task["space_ids"] = ["coding"]

    contracts: list[dict[str, object]] = []
    for space_id in ("research", "coding"):
        contract = shared_fixture("valid", "space_execution_contract")
        contract["space_id"] = space_id
        contracts.append(contract)

    return channel_intent, brain_plan, contracts, fixture("valid", "brain_plan_lifecycle")


def validate_bundle(
    channel_intent: dict[str, object],
    brain_plan: dict[str, object],
    contracts: list[dict[str, object]],
    lifecycle: dict[str, object],
) -> None:
    validator = getattr(contract_validation, "validate_brain_plan_lifecycle_bundle", None)
    assert callable(validator), "BrainPlanLifecycle bundle validation is not registered."
    validator(channel_intent, brain_plan, contracts, lifecycle)


def test_brain_plan_lifecycle_schema_is_registered_and_valid_fixture_validates() -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")

    validate_document("brain-plan-lifecycle", lifecycle)


def test_lifecycle_canonical_space_enum_matches_shared_identity_contracts() -> None:
    lifecycle_schema = load_json(LIFECYCLE_SCHEMA)
    execution_schema = load_json(SPACE_EXECUTION_SCHEMA)
    identity_snapshot = load_json(SPACE_IDENTITY_SNAPSHOT)

    lifecycle_definitions = lifecycle_schema["$defs"]
    execution_definitions = execution_schema["$defs"]
    assert isinstance(lifecycle_definitions, dict)
    assert isinstance(execution_definitions, dict)
    lifecycle_space_id = lifecycle_definitions["canonicalSpaceId"]
    execution_space_id = execution_definitions["canonicalSpaceId"]
    assert isinstance(lifecycle_space_id, dict)
    assert isinstance(execution_space_id, dict)
    lifecycle_ids = lifecycle_space_id["enum"]
    execution_ids = execution_space_id["enum"]
    snapshot_ids = identity_snapshot["canonical_space_ids"]
    assert isinstance(lifecycle_ids, list)
    assert isinstance(execution_ids, list)
    assert isinstance(snapshot_ids, list)

    assert lifecycle_ids == execution_ids == snapshot_ids


def test_lifecycle_participating_spaces_accepts_rowboat() -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    lifecycle["participating_space_ids"] = ["research", "rowboat"]

    validate_document("brain-plan-lifecycle", lifecycle)


def test_lifecycle_participating_spaces_rejects_roarboot() -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    lifecycle["participating_space_ids"] = ["research", "roarboot"]

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


def test_brain_plan_lifecycle_bundle_accepts_an_admitted_deferred_plan() -> None:
    validate_bundle(*valid_bundle())


@pytest.mark.parametrize(
    ("target", "field_name", "value", "message"),
    (
        ("lifecycle", "correlation_id", "event_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG", "correlation_id"),
        ("lifecycle", "plan_id", "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG", "plan_id"),
        ("lifecycle", "participating_space_ids", ["research", "agentfarm"], "participating_space_ids"),
    ),
)
def test_bundle_rejects_persisted_route_drift(
    target: str, field_name: str, value: object, message: str
) -> None:
    channel_intent, brain_plan, contracts, lifecycle = valid_bundle()
    documents = {"lifecycle": lifecycle}
    documents[target][field_name] = value

    with pytest.raises(ContractValidationError, match=message):
        validate_bundle(channel_intent, brain_plan, contracts, lifecycle)


@pytest.mark.parametrize("status", ("running", "succeeded", "failed", "dispatched", "queued"))
def test_execution_statuses_are_rejected(status: str) -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    lifecycle["status"] = status

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


@pytest.mark.parametrize("status", ("running", "succeeded", "failed", "dispatched", "queued"))
def test_execution_statuses_are_rejected_in_event_history(status: str) -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    event = history[1]
    assert isinstance(event, dict)
    event["status"] = status

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


def make_awaiting_clarification_sequence_valid(
    lifecycle: dict[str, object],
) -> dict[str, object]:
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    awaiting_event = history[1]
    final_event = history[2]
    assert isinstance(awaiting_event, dict) and isinstance(final_event, dict)
    awaiting_event["status"] = "awaiting_clarification"
    awaiting_event["reason_code"] = "clarification-required"
    final_event["status"] = "planned"
    final_event.pop("reason_code", None)
    lifecycle["status"] = "planned"
    lifecycle["updated_at"] = final_event["occurred_at"]
    return awaiting_event


@pytest.mark.parametrize(
    ("event_index", "status", "wrong_reason_code"),
    (
        (1, "awaiting_clarification", "admission-validated"),
        (1, "admitted", "clarification-required"),
        (2, "execution_deferred", "admission-validated"),
        (2, "cancelled", "execution-engine-deferred"),
    ),
)
def test_event_status_rejects_a_mismatched_reason_code(
    event_index: int, status: str, wrong_reason_code: str
) -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    event = (
        make_awaiting_clarification_sequence_valid(lifecycle)
        if status == "awaiting_clarification"
        else history[event_index]
    )
    if status == "awaiting_clarification":
        validate_document("brain-plan-lifecycle", lifecycle)
    assert isinstance(event, dict)
    event["status"] = status
    event["reason_code"] = wrong_reason_code

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


def test_planned_event_rejects_a_reason_code() -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    event = history[0]
    assert isinstance(event, dict)
    event["reason_code"] = "clarification-required"

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


@pytest.mark.parametrize(
    ("event_index", "status"),
    (
        (1, "awaiting_clarification"),
        (1, "admitted"),
        (2, "execution_deferred"),
        (2, "cancelled"),
    ),
)
def test_event_status_rejects_a_missing_required_reason_code(
    event_index: int, status: str
) -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    event = (
        make_awaiting_clarification_sequence_valid(lifecycle)
        if status == "awaiting_clarification"
        else history[event_index]
    )
    if status == "awaiting_clarification":
        validate_document("brain-plan-lifecycle", lifecycle)
    assert isinstance(event, dict)
    event["status"] = status
    event.pop("reason_code", None)

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


@pytest.mark.parametrize(
    "field_name",
    (
        "provider",
        "runtime",
        "application",
        "agent",
        "tool",
        "command",
        "url",
        "credential",
        "approval",
        "evidence_success",
    ),
)
def test_authority_and_execution_fields_are_rejected(field_name: str) -> None:
    lifecycle = fixture("valid", "brain_plan_lifecycle")
    lifecycle[field_name] = "forbidden"

    with pytest.raises(ContractValidationError):
        validate_document("brain-plan-lifecycle", lifecycle)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("start", "start"),
        ("revision-gap", "revision"),
        ("revision-summary", "revision"),
        ("timestamp-order", "timestamp"),
        ("updated-at", "updated_at"),
        ("final-state", "final"),
        ("invalid-transition", "transition"),
        ("terminal-reopening", "terminal"),
    ),
)
def test_lifecycle_history_invariants_fail_closed(mutation: str, message: str) -> None:
    channel_intent, brain_plan, contracts, lifecycle = valid_bundle()
    history = lifecycle["event_history"]
    assert isinstance(history, list)

    if mutation == "start":
        history[0]["status"] = "admitted"
        history[0]["reason_code"] = "admission-validated"
    elif mutation == "revision-gap":
        history[1]["revision"] = 3
    elif mutation == "revision-summary":
        lifecycle["revision"] = 2
    elif mutation == "timestamp-order":
        history[1]["occurred_at"] = "2026-08-01T09:59:00Z"
    elif mutation == "updated-at":
        lifecycle["updated_at"] = "2026-08-01T10:03:00Z"
    elif mutation == "final-state":
        lifecycle["status"] = "admitted"
    elif mutation == "invalid-transition":
        history[1]["status"] = "awaiting_clarification"
        history[1]["reason_code"] = "clarification-required"
    else:
        reopened = deepcopy(history[1])
        reopened["revision"] = 4
        reopened["occurred_at"] = "2026-08-01T10:03:00Z"
        history.append(reopened)
        lifecycle.update({"revision": 4, "status": "admitted", "updated_at": reopened["occurred_at"]})

    with pytest.raises(ContractValidationError, match=message):
        validate_bundle(channel_intent, brain_plan, contracts, lifecycle)


def test_awaiting_clarification_can_return_to_planned_then_cancel() -> None:
    channel_intent, brain_plan, contracts, lifecycle = valid_bundle()
    lifecycle.update(
        {
            "revision": 4,
            "status": "cancelled",
            "updated_at": "2026-08-01T10:03:00Z",
            "event_history": [
                {"revision": 1, "status": "planned", "occurred_at": "2026-08-01T10:00:00Z"},
                {
                    "revision": 2,
                    "status": "awaiting_clarification",
                    "reason_code": "clarification-required",
                    "occurred_at": "2026-08-01T10:01:00Z",
                },
                {"revision": 3, "status": "planned", "occurred_at": "2026-08-01T10:02:00Z"},
                {
                    "revision": 4,
                    "status": "cancelled",
                    "reason_code": "user-cancelled",
                    "occurred_at": "2026-08-01T10:03:00Z",
                },
            ],
        }
    )

    validate_bundle(channel_intent, brain_plan, contracts, lifecycle)


def test_bundle_delegates_to_existing_admission_validation_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel_intent, brain_plan, contracts, lifecycle = valid_bundle()
    calls: list[str] = []

    def reject_admission(*_args: object) -> None:
        calls.append("admission")
        raise ContractValidationError("sentinel admission rejection")

    monkeypatch.setattr(contract_validation, "validate_brain_plan_admission_bundle", reject_admission)

    with pytest.raises(ContractValidationError, match="sentinel admission rejection"):
        validate_bundle(channel_intent, brain_plan, contracts, lifecycle)
    assert calls == ["admission"]
