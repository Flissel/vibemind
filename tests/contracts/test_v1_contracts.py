from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.contracts.validate import (
    ContractValidationError,
    is_canonical_id,
    validate_brain_plan_admission_bundle,
    validate_document,
)
from shared.contracts import validate as contract_validation


FIXTURES = ROOT / "tests" / "contracts" / "fixtures"
SPACE_IDENTITY_SNAPSHOT = (
    ROOT / "shared" / "contracts" / "snapshots" / "space-identity-snapshot-v1.json"
)

CONTRACT_FIXTURES = (
    ("task-brief", "task_brief"),
    ("task-event", "task_event"),
    ("evidence-ref", "evidence_ref"),
    ("task-handoff", "task_handoff"),
)


def load_fixture(category: str, name: str) -> dict[str, object]:
    path = FIXTURES / category / f"{name}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


@pytest.mark.parametrize(("document_type", "fixture_name"), CONTRACT_FIXTURES)
def test_valid_v1_contract_fixtures_validate(
    document_type: str, fixture_name: str
) -> None:
    document = load_fixture("valid", fixture_name)

    validate_document(document_type, document)


@pytest.mark.parametrize(("document_type", "fixture_name"), CONTRACT_FIXTURES)
def test_invalid_v1_contract_fixtures_are_rejected(
    document_type: str, fixture_name: str
) -> None:
    document = load_fixture("invalid", fixture_name)

    with pytest.raises(ContractValidationError):
        validate_document(document_type, document)


def test_valid_brain_plan_fixture_validates() -> None:
    document = load_fixture("valid", "brain_plan")

    validate_document("brain-plan", document)


def test_brain_plan_cycle_is_rejected_offline() -> None:
    document = load_fixture("invalid", "brain_plan_cycle")

    with pytest.raises(ContractValidationError, match="cycle"):
        validate_document("brain-plan", document)


def test_brain_plan_direct_application_target_is_rejected_offline() -> None:
    document = load_fixture("invalid", "brain_plan_application_target")

    with pytest.raises(ContractValidationError, match="application targets are forbidden"):
        validate_document("brain-plan", document)


def test_brain_plan_undeclared_space_is_rejected_offline() -> None:
    document = load_fixture("invalid", "brain_plan_undeclared_space")

    with pytest.raises(ContractValidationError, match="undeclared space"):
        validate_document("brain-plan", document)


def test_brain_plan_dangling_dependency_is_rejected_offline() -> None:
    document = load_fixture("valid", "brain_plan")
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    second_task = tasks[1]
    assert isinstance(second_task, dict)
    second_task["depends_on"] = ["missing-task"]

    with pytest.raises(ContractValidationError, match="unknown task node"):
        validate_document("brain-plan", document)


def test_brain_plan_duplicate_node_id_is_rejected_offline() -> None:
    document = load_fixture("valid", "brain_plan")
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    second_task = tasks[1]
    assert isinstance(second_task, dict)
    second_task["node_id"] = "research-sources"

    with pytest.raises(ContractValidationError, match="duplicate task node_id"):
        validate_document("brain-plan", document)


def test_brain_plan_duplicate_order_is_rejected_offline() -> None:
    document = load_fixture("valid", "brain_plan")
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    second_task = tasks[1]
    assert isinstance(second_task, dict)
    second_task["order"] = 1

    with pytest.raises(ContractValidationError, match="duplicate task order"):
        validate_document("brain-plan", document)


def test_brain_plan_dependency_must_precede_its_dependent_task() -> None:
    document = load_fixture("valid", "brain_plan")
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    first_task = tasks[0]
    second_task = tasks[1]
    assert isinstance(first_task, dict)
    assert isinstance(second_task, dict)
    first_task["order"] = 2
    second_task["order"] = 1

    with pytest.raises(ContractValidationError, match="must precede"):
        validate_document("brain-plan", document)


def test_valid_channel_intent_fixture_validates() -> None:
    document = load_fixture("valid", "channel_intent")

    validate_document("channel-intent", document)


def valid_channel_result_route_bundle() -> tuple[
    dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]
]:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    channel_result = load_fixture("valid", "channel_result")
    return channel_intent, brain_plan, contracts, channel_result


def test_valid_channel_result_fixture_validates() -> None:
    document = load_fixture("valid", "channel_result")

    validate_document("channel-result", document)


def test_channel_result_route_bundle_preserves_the_admitted_route() -> None:
    channel_intent, brain_plan, contracts, channel_result = valid_channel_result_route_bundle()

    contract_validation.validate_channel_result_route_bundle(
        channel_intent, brain_plan, contracts, channel_result
    )


@pytest.mark.parametrize(
    ("fixture_name", "message"),
    (
        ("channel_result_correlation_mismatch", "correlation_id"),
        ("channel_result_success_without_evidence", "succeeded"),
        ("channel_result_approval_decision", "approval_ref"),
        ("channel_result_runtime_field", "channel-result is invalid"),
    ),
)
def test_channel_result_route_bundle_rejects_invalid_result_fixtures(
    fixture_name: str, message: str
) -> None:
    channel_intent, brain_plan, contracts, _ = valid_channel_result_route_bundle()
    channel_result = load_fixture("invalid", fixture_name)

    with pytest.raises(ContractValidationError, match=message):
        contract_validation.validate_channel_result_route_bundle(
            channel_intent, brain_plan, contracts, channel_result
        )


@pytest.mark.parametrize(
    "field_name",
    (
        "channel_kind",
        "actor_context",
        "session_context",
        "plan_id",
        "participating_space_ids",
    ),
)
def test_channel_result_route_bundle_rejects_each_remaining_route_mutation(
    field_name: str,
) -> None:
    channel_intent, brain_plan, contracts, channel_result = valid_channel_result_route_bundle()

    if field_name == "channel_kind":
        channel_result[field_name] = "voice"
    elif field_name == "actor_context":
        channel_result[field_name] = {"actor_id": "user:another-actor", "locale": "de-DE"}
    elif field_name == "session_context":
        channel_result[field_name] = {
            "session_id": "session-20260731-02",
            "conversation_id": "desktop-chat-42",
        }
    elif field_name == "plan_id":
        channel_result[field_name] = "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"
    else:
        channel_result[field_name] = ["coding", "research"]

    with pytest.raises(ContractValidationError, match=field_name):
        contract_validation.validate_channel_result_route_bundle(
            channel_intent, brain_plan, contracts, channel_result
        )


def valid_brain_plan_admission_bundle() -> tuple[
    dict[str, object], dict[str, object], list[dict[str, object]]
]:
    channel_intent = load_fixture("valid", "channel_intent")
    channel_intent["requested_space_id"] = "research"
    brain_plan = load_fixture("valid", "brain_plan")
    participating_spaces = brain_plan["participating_spaces"]
    tasks = brain_plan["tasks"]
    assert isinstance(participating_spaces, list) and isinstance(tasks, list)
    second_space = participating_spaces[1]
    second_task = tasks[1]
    assert isinstance(second_space, dict) and isinstance(second_task, dict)
    second_space["space_id"] = "coding"
    second_task["space_ids"] = ["coding"]

    contracts = []
    for space_id in ("research", "coding"):
        contract = load_fixture("valid", "space_execution_contract")
        contract["space_id"] = space_id
        contracts.append(contract)
    return channel_intent, brain_plan, contracts


def test_brain_plan_admission_bundle_accepts_a_complete_canonical_bundle() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()

    validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts)


def test_brain_plan_admission_bundle_rejects_missing_requested_space() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    channel_intent["requested_space_id"] = "agentfarm"

    with pytest.raises(ContractValidationError, match="requested_space_id"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts)


def test_brain_plan_admission_bundle_rejects_missing_space_contract() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()

    with pytest.raises(ContractValidationError, match="exactly one"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts[:1])


def test_brain_plan_admission_bundle_rejects_duplicate_space_contract() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()

    with pytest.raises(ContractValidationError, match="exactly one"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, [*contracts, contracts[0]])


def test_brain_plan_admission_bundle_rejects_additional_space_contract() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    additional_contract = load_fixture("valid", "space_execution_contract")
    additional_contract["space_id"] = "bubbles"

    with pytest.raises(ContractValidationError, match="unparticipating"):
        validate_brain_plan_admission_bundle(
            channel_intent, brain_plan, [*contracts, additional_contract]
        )


def test_brain_plan_admission_bundle_rejects_noncanonical_plan_space() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    participating_spaces = brain_plan["participating_spaces"]
    tasks = brain_plan["tasks"]
    assert isinstance(participating_spaces, list) and isinstance(tasks, list)
    second_space = participating_spaces[1]
    second_task = tasks[1]
    assert isinstance(second_space, dict) and isinstance(second_task, dict)
    second_space["space_id"] = "writing"
    second_task["space_ids"] = ["writing"]

    with pytest.raises(ContractValidationError, match="not canonical"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts[:1])


def test_brain_plan_admission_bundle_rejects_task_space_drift() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    tasks = brain_plan["tasks"]
    assert isinstance(tasks, list)
    second_task = tasks[1]
    assert isinstance(second_task, dict)
    second_task["space_ids"] = ["agentfarm"]

    with pytest.raises(ContractValidationError, match="undeclared space"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts)


def test_brain_plan_admission_bundle_rejects_missing_task_evidence_requirements() -> None:
    channel_intent, brain_plan, contracts = valid_brain_plan_admission_bundle()
    tasks = brain_plan["tasks"]
    assert isinstance(tasks, list)
    first_task = tasks[0]
    assert isinstance(first_task, dict)
    first_task["evidence_requirements"] = []

    with pytest.raises(ContractValidationError, match="evidence_requirements"):
        validate_brain_plan_admission_bundle(channel_intent, brain_plan, contracts)


@pytest.mark.parametrize(
    "space_id",
    (
        "bubbles",
        "ideas",
        "coding",
        "desktop",
        "research",
        "rowboat",
        "minibook",
        "schedule",
        "n8n",
        "agentfarm",
        "video",
        "flowzen",
        "mirofish",
    ),
)
def test_space_execution_contract_accepts_each_canonical_snapshot_space(
    space_id: str,
) -> None:
    document = load_fixture("valid", "space_execution_contract")
    document["space_id"] = space_id

    validate_document("space-execution-contract", document)


@pytest.mark.parametrize(
    "fixture_name",
    (
        "space_execution_contract_alias",
        "space_execution_contract_command",
        "space_execution_contract_url",
        "space_execution_contract_provider",
        "space_execution_contract_credential",
    ),
)
def test_space_execution_contract_rejects_aliases_and_free_runtime_fields(
    fixture_name: str,
) -> None:
    document = load_fixture("invalid", fixture_name)

    with pytest.raises(ContractValidationError, match="space-execution-contract is invalid"):
        validate_document("space-execution-contract", document)


@pytest.mark.parametrize("alias", ("autogen", "roarboot", "shuttles"))
def test_space_execution_contract_rejects_each_ingress_alias(alias: str) -> None:
    document = load_fixture("invalid", "space_execution_contract_alias")
    document["space_id"] = alias

    with pytest.raises(ContractValidationError, match="space-execution-contract is invalid"):
        validate_document("space-execution-contract", document)


def test_space_identity_snapshot_matches_the_execution_contract_schema() -> None:
    assert SPACE_IDENTITY_SNAPSHOT.is_file()
    snapshot = json.loads(SPACE_IDENTITY_SNAPSHOT.read_text(encoding="utf-8"))
    assert isinstance(snapshot, dict)
    canonical_space_ids = snapshot["canonical_space_ids"]
    assert isinstance(canonical_space_ids, list)
    assert snapshot["snapshot_version"] == "v1"
    assert snapshot["source"] == {
        "repository": "vibemind-os",
        "gitlink_commit": "227f7e6edf2ce6cbec9bcdab45498364dbe9cdfd",
        "path": "config/space_agent_registry.yml",
        "captured_on": "2026-08-01",
    }
    schema = contract_validation.load_schema("space-execution-contract")
    definitions = schema["$defs"]
    assert isinstance(definitions, dict)
    canonical_space_id = definitions["canonicalSpaceId"]
    assert isinstance(canonical_space_id, dict)
    assert canonical_space_id["enum"] == canonical_space_ids
    assert set(snapshot["rejected_ingress_aliases"]).isdisjoint(canonical_space_ids)


def test_space_identity_snapshot_verifier_reports_unavailable_and_drift(
    tmp_path: Path,
) -> None:
    verifier = getattr(contract_validation, "verify_space_identity_snapshot", None)
    assert callable(verifier)

    unavailable = verifier(tmp_path / "missing-space_agent_registry.yml")
    assert unavailable.status == "registry-unavailable"

    registry_path = tmp_path / "space_agent_registry.yml"
    registry_path.write_text(
        "spaces:\n  bubbles: {}\n  ideas: {}\n",
        encoding="utf-8",
    )
    drift = verifier(registry_path)
    assert drift.status == "drift"
    assert drift.missing_from_registry == (
        "agentfarm",
        "coding",
        "desktop",
        "flowzen",
        "minibook",
        "mirofish",
        "n8n",
        "research",
        "rowboat",
        "schedule",
        "video",
    )


def test_space_identity_snapshot_verifier_accepts_matching_initialized_registry(
    tmp_path: Path,
) -> None:
    verifier = getattr(contract_validation, "verify_space_identity_snapshot", None)
    assert callable(verifier)
    snapshot = json.loads(SPACE_IDENTITY_SNAPSHOT.read_text(encoding="utf-8"))
    assert isinstance(snapshot, dict)
    canonical_space_ids = snapshot["canonical_space_ids"]
    assert isinstance(canonical_space_ids, list)
    registry_path = tmp_path / "space_agent_registry.yml"
    registry_path.write_text(
        "spaces:\n" + "".join(f"  {space_id}: {{}}\n" for space_id in canonical_space_ids),
        encoding="utf-8",
    )

    verified = verifier(registry_path)

    assert verified.status == "verified"
    assert verified.missing_from_registry == ()
    assert verified.extra_in_registry == ()


def test_channel_intent_unknown_channel_is_rejected_offline() -> None:
    document = load_fixture("invalid", "channel_intent_unknown_channel")

    with pytest.raises(ContractValidationError):
        validate_document("channel-intent", document)


def test_channel_intent_credential_like_field_is_rejected_offline() -> None:
    document = load_fixture("invalid", "channel_intent_credential_field")

    with pytest.raises(ContractValidationError):
        validate_document("channel-intent", document)


@pytest.mark.parametrize(
    "fixture_name",
    ("channel_intent_invalid_space", "channel_intent_space_alias"),
)
def test_channel_intent_invalid_or_noncanonical_requested_space_is_rejected_offline(
    fixture_name: str,
) -> None:
    document = load_fixture("invalid", fixture_name)

    with pytest.raises(ContractValidationError):
        validate_document("channel-intent", document)


@pytest.mark.parametrize(
    "fixture_name",
    ("channel_intent_application_target", "channel_intent_execution_target"),
)
def test_channel_intent_direct_application_or_execution_target_is_rejected_offline(
    fixture_name: str,
) -> None:
    document = load_fixture("invalid", fixture_name)

    with pytest.raises(ContractValidationError):
        validate_document("channel-intent", document)


@pytest.mark.parametrize(
    "identifier",
    (
        "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "event_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "evidence_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "handoff_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "todo_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    ),
)
def test_canonical_v1_identifiers_are_accepted(identifier: str) -> None:
    assert is_canonical_id(identifier)


@pytest.mark.parametrize(
    "identifier",
    (
        "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEI",
        "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEFG",
        "task_v2_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
        "task_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF-",
        "unknown_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEF",
    ),
)
def test_noncanonical_identifiers_are_rejected(identifier: str) -> None:
    assert not is_canonical_id(identifier)
