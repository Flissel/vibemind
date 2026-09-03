from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
from importlib import resources
import json
from pathlib import Path
import sys
from types import MappingProxyType

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, load_schema, validate_document


FIXTURES = ROOT / "tests" / "contracts"
PACKAGE_SOURCE = ROOT / "vibemind-os" / "shared" / "src"
EXPECTED_SCHEMA_DIGESTS = MappingProxyType(
    {
        "channel-intent-v1.schema.json": "c2e839018f9b5ed98d84088ce49769fc2584ce6354b65945542a55161e006a10",
        "brain-plan-v1.schema.json": "488541303e51935a1b6d38d5fc9c666376bf8a743bd8dc26d046979b3162c632",
        "space-execution-contract-v1.schema.json": "2b0ad853d80840488b83e4f88946531f059f39789e9cc85b4debff7efd526351",
        "brain-plan-lifecycle-v1.schema.json": "efafbaa06b228e07b976d9ff293d244931af4cafdc694026d4c8dcbcdd66f1e3",
        "brain-openfang-handoff-v1.schema.json": "e69afd00058af8f101aa60886f8cd26e9d3bd04979e0f67e0d9ed2968d6d2239",
    }
)


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

    return (
        channel_intent,
        brain_plan,
        contracts,
        fixture("valid", "brain_plan_lifecycle"),
        fixture("valid", "brain_openfang_handoff"),
    )


def validate_bundle(
    channel_intent: dict[str, object],
    brain_plan: dict[str, object],
    contracts: list[dict[str, object]],
    lifecycle: dict[str, object],
    handoff: dict[str, object],
) -> None:
    validator = getattr(contract_validation, "validate_brain_openfang_handoff_bundle", None)
    assert callable(validator), "Brain OpenFang handoff bundle validation is not registered."
    validator(channel_intent, brain_plan, contracts, lifecycle, handoff)


def test_pinned_contract_package_is_imported_only_from_the_nested_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, _, _ = package_contract_api(monkeypatch)
    package_file = Path(str(package.__file__)).resolve()

    assert package_file.is_relative_to(PACKAGE_SOURCE.resolve())


def package_contract_api(monkeypatch: pytest.MonkeyPatch) -> tuple[object, type[ValueError], object]:
    for module_name in tuple(sys.modules):
        if module_name == "vibemind_shared" or module_name.startswith("vibemind_shared."):
            monkeypatch.delitem(sys.modules, module_name)
    monkeypatch.syspath_prepend(str(PACKAGE_SOURCE))

    from vibemind_shared.contracts import (
        ContractValidationError as package_validation_error,
        validate_brain_openfang_handoff_bundle as package_validate_bundle,
    )

    package = importlib.import_module("vibemind_shared.contracts")
    package_file = Path(str(package.__file__)).resolve()
    assert package_file.is_relative_to(PACKAGE_SOURCE.resolve())
    return package, package_validation_error, package_validate_bundle


def test_pinned_package_resources_are_byte_identical_to_the_normative_outer_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, _, _ = package_contract_api(monkeypatch)
    package_resources = resources.files(package)
    manifest = json.loads(
        package_resources.joinpath("schema-manifest-v1.json").read_text(encoding="utf-8")
    )
    assert manifest == {
        "outer_commit": "f0001e40f306745f60818a5bbd3065377dacd443",
        "schemas": dict(EXPECTED_SCHEMA_DIGESTS),
    }
    schema_files = {
        "channel-intent-v1.schema.json": ROOT
        / "shared"
        / "contracts"
        / "schemas"
        / "channel-intent-v1.schema.json",
        "brain-plan-v1.schema.json": ROOT
        / "shared"
        / "contracts"
        / "schemas"
        / "brain-plan-v1.schema.json",
        "space-execution-contract-v1.schema.json": ROOT
        / "shared"
        / "contracts"
        / "schemas"
        / "space-execution-contract-v1.schema.json",
        "brain-plan-lifecycle-v1.schema.json": ROOT
        / "shared"
        / "contracts"
        / "brain"
        / "v1"
        / "brain-plan-lifecycle-v1.schema.json",
        "brain-openfang-handoff-v1.schema.json": ROOT
        / "shared"
        / "contracts"
        / "brain"
        / "v1"
        / "brain-openfang-handoff-v1.schema.json",
    }

    for schema_name, outer_path in schema_files.items():
        outer_bytes = outer_path.read_bytes()
        package_bytes = package_resources.joinpath("schemas", schema_name).read_bytes()
        expected_digest = EXPECTED_SCHEMA_DIGESTS[schema_name]

        assert hashlib.sha256(outer_bytes).hexdigest() == expected_digest
        assert hashlib.sha256(package_bytes).hexdigest() == expected_digest
        assert package_bytes == outer_bytes


def test_pinned_package_accepts_the_same_complete_valid_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, package_validate_bundle = package_contract_api(monkeypatch)
    bundle = valid_bundle()

    validate_bundle(*bundle)
    package_validate_bundle(*bundle)


def _set_lifecycle_to_admitted(bundle: tuple[object, object, object, object, object]) -> None:
    lifecycle = bundle[3]
    assert isinstance(lifecycle, dict)
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    final_event = history[1]
    assert isinstance(final_event, dict)
    lifecycle.update(
        {
            "revision": 2,
            "status": "admitted",
            "updated_at": final_event["occurred_at"],
            "event_history": history[:2],
        }
    )


@pytest.mark.parametrize(
    ("name", "mutate"),
    (
        ("malformed-date-time", lambda bundle: bundle[0].__setitem__("received_at", "not-a-date")),
        ("noncanonical-space", lambda bundle: bundle[4].__setitem__("space_id", "research-alias")),
        ("lifecycle-not-deferred", _set_lifecycle_to_admitted),
        ("correlation-drift", lambda bundle: bundle[4].__setitem__("correlation_id", "event_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG")),
        ("plan-drift", lambda bundle: bundle[4].__setitem__("plan_id", "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG")),
        ("revision-drift", lambda bundle: bundle[4].__setitem__("lifecycle_revision", 2)),
        ("node-drift", lambda bundle: bundle[4].__setitem__("brain_task_node_id", "unknown-node")),
        ("space-drift", lambda bundle: bundle[4].__setitem__("space_id", "coding")),
        ("role-drift", lambda bundle: bundle[4]["roles"][0].__setitem__("required_agent_count", 2)),
        ("non-cognitive-mode", lambda bundle: bundle[4].__setitem__("execution_mode", "direct")),
        ("non-openfang-boundary", lambda bundle: bundle[4].__setitem__("execution_boundary", "direct")),
        ("unknown-runtime", lambda bundle: bundle[4].__setitem__("runtime", "forbidden")),
        ("unknown-provider", lambda bundle: bundle[4].__setitem__("provider", "forbidden")),
        ("unknown-application", lambda bundle: bundle[4].__setitem__("application", "forbidden")),
        ("unknown-fallback", lambda bundle: bundle[4].__setitem__("fallback", "forbidden")),
        ("unknown-success", lambda bundle: bundle[4].__setitem__("success", "forbidden")),
        ("invalid-retry-bound", lambda bundle: bundle[4]["retry"].update({"classification": "transient", "max_attempts": 4})),
    ),
)
def test_pinned_package_matches_outer_fail_closed_bundle_decisions(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    mutate: object,
) -> None:
    _, package_validation_error, package_validate_bundle = package_contract_api(monkeypatch)
    original_bundle = valid_bundle()
    outer_bundle = deepcopy(original_bundle)
    package_bundle = deepcopy(original_bundle)
    assert callable(mutate)
    mutate(outer_bundle)
    mutate(package_bundle)
    outer_before_validation = deepcopy(outer_bundle)
    package_before_validation = deepcopy(package_bundle)

    with pytest.raises(ContractValidationError) as outer_failure:
        validate_bundle(*outer_bundle)
    with pytest.raises(package_validation_error) as package_failure:
        package_validate_bundle(*package_bundle)

    assert str(outer_failure.value) == str(package_failure.value), name
    assert outer_bundle == outer_before_validation
    assert package_bundle == package_before_validation


def test_pinned_package_does_not_mutate_bundle_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, package_validate_bundle = package_contract_api(monkeypatch)
    bundle = valid_bundle()
    before = deepcopy(bundle)

    package_validate_bundle(*bundle)

    assert bundle == before


def test_handoff_schema_is_registered_and_valid_fixture_validates() -> None:
    handoff = fixture("valid", "brain_openfang_handoff")

    validate_document("brain-openfang-handoff", handoff)
    validate_bundle(*valid_bundle())


def test_handoff_execution_contract_is_explicit_and_closed() -> None:
    schema = load_schema("brain-openfang-handoff")
    required = schema["required"]
    properties = schema["properties"]
    assert isinstance(required, list) and isinstance(properties, dict)

    assert "execution_mode" in required
    assert "execution_boundary" in required
    assert properties["execution_mode"] == {"const": "cognitive"}
    assert properties["execution_boundary"] == {"const": "openfang"}


@pytest.mark.parametrize("field_name", ("execution_mode", "execution_boundary"))
def test_handoff_requires_explicit_execution_contract(field_name: str) -> None:
    handoff = fixture("valid", "brain_openfang_handoff")
    handoff.pop(field_name)

    with pytest.raises(ContractValidationError):
        validate_document("brain-openfang-handoff", handoff)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("execution_mode", "deterministic"),
        ("execution_mode", "direct"),
        ("execution_mode", "provider"),
        ("execution_boundary", "deterministic"),
        ("execution_boundary", "direct"),
        ("execution_boundary", "provider"),
    ),
)
def test_handoff_rejects_non_cognitive_or_non_openfang_execution_values(
    field_name: str, value: str
) -> None:
    handoff = fixture("valid", "brain_openfang_handoff")
    handoff[field_name] = value

    with pytest.raises(ContractValidationError):
        validate_document("brain-openfang-handoff", handoff)


def test_bundle_delegates_to_lifecycle_validation_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = valid_bundle()
    calls: list[str] = []

    def reject_lifecycle(*_args: object) -> None:
        calls.append("lifecycle")
        raise ContractValidationError("sentinel lifecycle rejection")

    monkeypatch.setattr(
        contract_validation, "validate_brain_plan_lifecycle_bundle", reject_lifecycle
    )

    with pytest.raises(ContractValidationError, match="sentinel lifecycle rejection"):
        validate_bundle(*bundle)
    assert calls == ["lifecycle"]


def test_bundle_requires_execution_deferred_lifecycle() -> None:
    channel_intent, brain_plan, contracts, lifecycle, handoff = valid_bundle()
    history = lifecycle["event_history"]
    assert isinstance(history, list)
    lifecycle["event_history"] = history[:2]
    final_event = history[1]
    assert isinstance(final_event, dict)
    lifecycle.update(
        {
            "revision": 2,
            "status": "admitted",
            "updated_at": final_event["occurred_at"],
        }
    )

    with pytest.raises(ContractValidationError, match="execution_deferred"):
        validate_bundle(channel_intent, brain_plan, contracts, lifecycle, handoff)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("correlation_id", "correlation_id"),
        ("plan_id", "plan_id"),
        ("lifecycle_revision", "revision"),
        ("brain_task_node_id", "brain_task_node_id"),
        ("space_id", "space_id"),
        ("roles", "roles"),
    ),
)
def test_bundle_rejects_handoff_continuity_drift(mutation: str, message: str) -> None:
    channel_intent, brain_plan, contracts, lifecycle, handoff = valid_bundle()
    if mutation == "correlation_id":
        handoff[mutation] = "event_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    elif mutation == "plan_id":
        handoff[mutation] = "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    elif mutation == "lifecycle_revision":
        handoff[mutation] = 2
    elif mutation == "brain_task_node_id":
        handoff[mutation] = "unknown-node"
    elif mutation == "space_id":
        handoff[mutation] = "coding"
    else:
        roles = handoff["roles"]
        assert isinstance(roles, list)
        role = roles[0]
        assert isinstance(role, dict)
        role["required_agent_count"] = 2

    with pytest.raises(ContractValidationError, match=message):
        validate_bundle(channel_intent, brain_plan, contracts, lifecycle, handoff)


@pytest.mark.parametrize(
    "field_name",
    (
        "runtime",
        "provider",
        "executor",
        "agent_id",
        "tool",
        "mcp",
        "application",
        "database",
        "approval_status",
        "cost_amount",
        "success",
    ),
)
def test_handoff_rejects_unknown_runtime_and_outcome_fields(field_name: str) -> None:
    handoff = fixture("valid", "brain_openfang_handoff")
    handoff[field_name] = "forbidden"

    with pytest.raises(ContractValidationError):
        validate_document("brain-openfang-handoff", handoff)


@pytest.mark.parametrize("field_name", ("fallback", "fallback_space_id", "direct_route"))
def test_handoff_rejects_fallback_fields(field_name: str) -> None:
    handoff = fixture("valid", "brain_openfang_handoff")
    handoff[field_name] = "forbidden"

    with pytest.raises(ContractValidationError):
        validate_document("brain-openfang-handoff", handoff)


@pytest.mark.parametrize(
    ("classification", "max_attempts"),
    (
        ("unbounded", 3),
        ("transient", 4),
        ("none", 2),
    ),
)
def test_handoff_rejects_invalid_retry_classifications_and_bounds(
    classification: str, max_attempts: int
) -> None:
    handoff = fixture("valid", "brain_openfang_handoff")
    retry = handoff["retry"]
    assert isinstance(retry, dict)
    retry.update({"classification": classification, "max_attempts": max_attempts})

    with pytest.raises(ContractValidationError):
        validate_document("brain-openfang-handoff", handoff)


def test_handoff_does_not_mutate_the_lifecycle_bundle() -> None:
    bundle = valid_bundle()
    lifecycle_before = deepcopy(bundle[3])

    validate_bundle(*bundle)

    assert bundle[3] == lifecycle_before
