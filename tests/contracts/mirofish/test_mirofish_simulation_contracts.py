from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, validate_document


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "valid"
DOCUMENT_TYPES = (
    "mirofish-simulation-request",
    "mirofish-simulation-plan",
    "mirofish-simulation-run-request",
    "mirofish-simulation-run-state",
    "mirofish-simulation-evidence",
    "mirofish-simulation-result",
)


def valid_bundle() -> dict[str, dict[str, object]]:
    value = json.loads((FIXTURES / "simulation_bundle.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return deepcopy(value)


def typed_ref(kind: str) -> str:
    return f"{kind}_v1_00000000000000000000000000"


def typed_refs(kind: str, count: int) -> list[str]:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return [f"{kind}_v1_{'0' * 25}{alphabet[index]}" for index in range(count)]


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_mirofish_simulation_bundle", None)
    assert callable(validator), "MiroFish simulation bundle validation is not registered."
    validator(bundle)


def test_accepts_complete_evidenced_mirofish_simulation_bundle() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize("document_type", DOCUMENT_TYPES)
def test_accepts_each_mirofish_document(document_type: str) -> None:
    validate_document(document_type, valid_bundle()[document_type])


@pytest.mark.parametrize(
    "field",
    ("provider", "credential", "secret", "token", "api_key", "runtime", "url", "endpoint", "webhook", "command", "shell", "model", "mock", "ok", "status_code"),
)
def test_rejects_free_provider_runtime_secret_and_success_shortcuts(field: str) -> None:
    request = valid_bundle()["mirofish-simulation-request"]
    request[field] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("mirofish-simulation-request", request)


@pytest.mark.parametrize(
    ("document", "path", "value"),
    (
        ("mirofish-simulation-request", ("space_id",), "MiroFish"),
        ("mirofish-simulation-plan", ("input_artifact_refs",), ["artifact_v1_0000000000000000000000000B"]),
        ("mirofish-simulation-plan", ("phases", 1, "depends_on"), []),
        ("mirofish-simulation-run-request", ("plan_hash",), "sha256:" + "0" * 64),
        ("mirofish-simulation-run-state", ("event_history", 0, "status"), "running"),
        ("mirofish-simulation-run-state", ("progress", "completed_units"), 2),
        ("mirofish-simulation-evidence", ("graph_artifact", "content_hash"), "sha256:ABC"),
        ("mirofish-simulation-evidence", ("external_receipt_ref",), None),
        ("mirofish-simulation-result", ("evidence_id",), "evidence_v1_0000000000000000000000000B"),
        ("mirofish-simulation-result", ("cost", "actual_cost_minor"), 5001),
    ),
)
def test_rejects_bound_input_lifecycle_evidence_and_cost_drift(
    document: str, path: tuple[object, ...], value: object
) -> None:
    bundle = valid_bundle()
    target: object = bundle[document]
    for key in path[:-1]:
        if isinstance(target, dict):
            target = target[key]
        else:
            assert isinstance(target, list)
            assert isinstance(key, int)
            target = target[key]
    assert isinstance(target, dict)
    target[path[-1]] = value
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_success_after_cancellation_requested() -> None:
    bundle = valid_bundle()
    state = bundle["mirofish-simulation-run-state"]
    history = state["event_history"]
    assert isinstance(history, list)
    history[3] = {
        "status": "cancellation_requested",
        "revision": 4,
        "occurred_at": "2026-07-31T10:04:00Z",
        "checkpoint_ref": None,
        "cancellation_ref": "cancellation_v1_00000000000000000000000000",
    }
    history.append({"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:05:00Z", "checkpoint_ref": None, "cancellation_ref": None})
    state["revision"] = 5
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_resume_without_the_paused_checkpoint() -> None:
    bundle = valid_bundle()
    state = bundle["mirofish-simulation-run-state"]
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "paused", "revision": 3, "occurred_at": "2026-07-31T10:02:30Z", "checkpoint_ref": "checkpoint_v1_00000000000000000000000000", "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    state["revision"] = 5
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("document_type", "path", "wrong_ref"),
    (
        ("mirofish-simulation-request", ("request_id",), typed_ref("artifact")),
        ("mirofish-simulation-request", ("project_ref",), typed_ref("task")),
        ("mirofish-simulation-request", ("task_ref",), typed_ref("project")),
        ("mirofish-simulation-request", ("trace_id",), typed_ref("request")),
        ("mirofish-simulation-plan", ("plan_id",), typed_ref("run")),
        ("mirofish-simulation-run-request", ("run_id",), typed_ref("plan")),
        ("mirofish-simulation-evidence", ("evidence_id",), typed_ref("run")),
        ("mirofish-simulation-request", ("input_artifact_refs", 0), typed_ref("evidence")),
        ("mirofish-simulation-request", ("quote_ref",), typed_ref("approval")),
        ("mirofish-simulation-request", ("approval_ref",), typed_ref("quote")),
        ("mirofish-simulation-evidence", ("external_receipt_ref",), typed_ref("evidence")),
    ),
)
def test_rejects_wrong_canonical_reference_prefix(
    document_type: str, path: tuple[object, ...], wrong_ref: str
) -> None:
    document = valid_bundle()[document_type]
    target: object = document
    for key in path[:-1]:
        if isinstance(target, dict):
            target = target[key]
        else:
            assert isinstance(target, list)
            assert isinstance(key, int)
            target = target[key]
    if isinstance(target, dict):
        target[path[-1]] = wrong_ref
    else:
        assert isinstance(target, list)
        assert isinstance(path[-1], int)
        target[path[-1]] = wrong_ref
    with pytest.raises(ContractValidationError):
        validate_document(document_type, document)


def test_rejects_wrong_checkpoint_and_cancellation_prefixes() -> None:
    state = valid_bundle()["mirofish-simulation-run-state"]
    checkpoint = typed_ref("artifact")
    state["resume_from_checkpoint_ref"] = checkpoint
    history = state["event_history"]
    assert isinstance(history, list)
    assert isinstance(history[2], dict)
    history[2]["checkpoint_ref"] = checkpoint
    with pytest.raises(ContractValidationError):
        validate_document("mirofish-simulation-run-state", state)

    state = valid_bundle()["mirofish-simulation-run-state"]
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "cancellation_requested", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": typed_ref("checkpoint")},
    ]
    state["revision"] = 2
    state["status"] = "cancellation_requested"
    state["cancellation_requested"] = True
    with pytest.raises(ContractValidationError):
        validate_document("mirofish-simulation-run-state", state)


def test_requires_deterministic_request_idempotency_key() -> None:
    request = valid_bundle()["mirofish-simulation-request"]
    request["idempotency_key"] = "mirofish:request_v1_0000000000000000000000000A"
    with pytest.raises(ContractValidationError):
        validate_document("mirofish-simulation-request", request)


def test_rejects_run_idempotency_drift_from_request() -> None:
    bundle = valid_bundle()
    bundle["mirofish-simulation-run-request"]["idempotency_key"] = (
        "mirofish:request_v1_0000000000000000000000000A"
    )
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("document_type", "path", "value"),
    (
        ("mirofish-simulation-request", ("input_artifact_refs",), typed_refs("artifact", 21)),
        ("mirofish-simulation-request", ("input_evidence_refs",), typed_refs("evidence", 21)),
        ("mirofish-simulation-request", ("clarification", "questions"), ["question"] * 21),
        ("mirofish-simulation-request", ("clarification", "questions"), ["q" * 2001]),
        ("mirofish-simulation-plan", ("input_artifact_refs",), typed_refs("artifact", 21)),
        ("mirofish-simulation-plan", ("input_evidence_refs",), typed_refs("evidence", 21)),
        ("mirofish-simulation-plan", ("phases", 2, "depends_on"), ["graph_build", "simulation", "forecast"]),
        ("mirofish-simulation-run-request", ("input_artifact_refs",), typed_refs("artifact", 21)),
        ("mirofish-simulation-run-request", ("input_evidence_refs",), typed_refs("evidence", 21)),
        ("mirofish-simulation-run-state", ("event_history",), [valid_bundle()["mirofish-simulation-run-state"]["event_history"][0]] * 129),
        ("mirofish-simulation-result", ("readback_refs",), [typed_ref("artifact")] * 4),
        ("mirofish-simulation-result", ("verification_refs",), [typed_ref("evidence")] * 4),
        ("mirofish-simulation-result", ("satisfied_criteria_ids",), ["graph-artifact"] * 6),
    ),
)
def test_rejects_collection_limits_before_execution(
    document_type: str, path: tuple[object, ...], value: object
) -> None:
    document = valid_bundle()[document_type]
    target: object = document
    for key in path[:-1]:
        if isinstance(target, dict):
            target = target[key]
        else:
            assert isinstance(target, list)
            assert isinstance(key, int)
            target = target[key]
    assert isinstance(target, dict)
    target[path[-1]] = value
    with pytest.raises(ContractValidationError):
        validate_document(document_type, document)
