from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    ROOT / "shared" / "contracts" / "schedule" / "v1" / "schedule-chat-boundary-v1.schema.json"
)
FIXTURES = Path(__file__).resolve().parent / "fixtures"

COMMON = {
    "contract_version": "v1",
    "request_id": "request_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    "intent_ref": "intent_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    "trace_id": "trace_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
}
SELECTOR = {"schedule_id": "schedule_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF"}
MUTATION = {
    "selector": SELECTOR,
    "expected_revision": 7,
    "approval_ref": "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    "idempotency_key": "schedule-chat:01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
}


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def validator() -> Draft202012Validator:
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def valid_document(operation: str) -> dict[str, object]:
    document: dict[str, object] = {**COMMON, "operation": operation}
    if operation == "create":
        document.update(
            approval_ref=MUTATION["approval_ref"],
            idempotency_key=MUTATION["idempotency_key"],
        )
    elif operation == "list":
        document["selector"] = copy.deepcopy(SELECTOR)
    elif operation in {"modify", "cancel", "snooze"}:
        document.update(copy.deepcopy(MUTATION))
        if operation == "snooze":
            document["snooze_for_seconds"] = 900
    elif operation == "status":
        document["selector"] = copy.deepcopy(SELECTOR)
    else:
        raise AssertionError(f"No valid document factory for {operation!r}.")
    return document


def assert_valid(document: dict[str, object]) -> None:
    validator().validate(document)


def assert_invalid(document: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        validator().validate(document)


@pytest.mark.parametrize("operation", ("create", "list", "modify", "cancel", "snooze", "status"))
def test_all_chat_operations_validate_directly(operation: str) -> None:
    assert_valid(valid_document(operation))


def test_valid_fixture_validates_directly() -> None:
    assert_valid(load_json(FIXTURES / "valid" / "schedule_chat_boundary.json"))


def test_list_allows_an_omitted_selector() -> None:
    document = valid_document("list")
    document.pop("selector")
    assert_valid(document)


@pytest.mark.parametrize(
    "selector",
    (
        {"schedule_id": "schedule_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF"},
        {"task_brief_ref": "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF"},
    ),
)
def test_selector_accepts_either_opaque_reference(selector: dict[str, object]) -> None:
    document = valid_document("status")
    document["selector"] = selector
    assert_valid(document)


@pytest.mark.parametrize(
    "fixture_name",
    (
        "schedule_chat_boundary_unknown_operation.json",
        "schedule_chat_boundary_missing_mutation_precondition.json",
    ),
)
def test_named_invalid_fixtures_fail_direct_validation(fixture_name: str) -> None:
    assert_invalid(load_json(FIXTURES / "invalid" / fixture_name))


@pytest.mark.parametrize("operation", ("archive", "run_now", "update", ""))
def test_unknown_operations_are_rejected(operation: str) -> None:
    document = valid_document("status")
    document["operation"] = operation
    assert_invalid(document)


@pytest.mark.parametrize(
    ("operation", "field_name"),
    (
        ("create", "approval_ref"),
        ("create", "idempotency_key"),
        ("modify", "selector"),
        ("modify", "expected_revision"),
        ("modify", "approval_ref"),
        ("modify", "idempotency_key"),
        ("cancel", "selector"),
        ("cancel", "expected_revision"),
        ("cancel", "approval_ref"),
        ("cancel", "idempotency_key"),
        ("snooze", "selector"),
        ("snooze", "expected_revision"),
        ("snooze", "approval_ref"),
        ("snooze", "idempotency_key"),
        ("snooze", "snooze_for_seconds"),
        ("status", "selector"),
    ),
)
def test_each_operation_requires_its_own_fields(operation: str, field_name: str) -> None:
    document = valid_document(operation)
    document.pop(field_name)
    assert_invalid(document)


@pytest.mark.parametrize(
    ("operation", "field_name", "value"),
    (
        ("create", "selector", SELECTOR),
        ("create", "expected_revision", 0),
        ("create", "snooze_for_seconds", 1),
        ("list", "expected_revision", 0),
        ("list", "approval_ref", MUTATION["approval_ref"]),
        ("list", "idempotency_key", MUTATION["idempotency_key"]),
        ("list", "snooze_for_seconds", 1),
        ("modify", "snooze_for_seconds", 1),
        ("cancel", "snooze_for_seconds", 1),
        ("status", "expected_revision", 0),
        ("status", "approval_ref", MUTATION["approval_ref"]),
        ("status", "idempotency_key", MUTATION["idempotency_key"]),
        ("status", "snooze_for_seconds", 1),
    ),
)
def test_each_operation_rejects_its_prohibited_fields(
    operation: str, field_name: str, value: object
) -> None:
    document = valid_document(operation)
    assert_valid(document)
    document[field_name] = copy.deepcopy(value)
    assert_invalid(document)


@pytest.mark.parametrize(
    "selector",
    (
        {},
        {
            "schedule_id": "schedule_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
            "task_brief_ref": "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        },
        {"calendar_id": "calendar_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF"},
    ),
)
def test_selector_is_closed_and_carries_exactly_one_choice(selector: dict[str, object]) -> None:
    document = valid_document("status")
    document["selector"] = selector
    assert_invalid(document)


@pytest.mark.parametrize("seconds", (0, -1, 2_592_001))
def test_snooze_duration_is_positive_and_bounded(seconds: int) -> None:
    document = valid_document("snooze")
    document["snooze_for_seconds"] = seconds
    assert_invalid(document)


@pytest.mark.parametrize("operation", ("create", "list", "modify", "cancel", "status"))
def test_snooze_duration_is_rejected_for_other_operations(operation: str) -> None:
    document = valid_document(operation)
    assert_valid(document)
    document["snooze_for_seconds"] = 60
    assert_invalid(document)


@pytest.mark.parametrize("field_name", ("provider", "runtime", "command", "endpoint", "credential", "database", "openfang"))
def test_free_execution_provider_and_secret_fields_are_rejected(field_name: str) -> None:
    document = valid_document("list")
    assert_valid(document)
    document[field_name] = "forbidden"
    assert_invalid(document)


@pytest.mark.parametrize("revision", (-1, 0, 1_000_000, 1.5))
def test_mutation_revision_is_a_bounded_integer(revision: object) -> None:
    document = valid_document("modify")
    document["expected_revision"] = revision
    assert_invalid(document)


@pytest.mark.parametrize("key", ("", " contains-space", "x" * 201))
def test_mutation_idempotency_key_uses_the_existing_safe_pattern(key: str) -> None:
    document = valid_document("cancel")
    document["idempotency_key"] = key
    assert_invalid(document)
