from __future__ import annotations

from copy import deepcopy

import pytest

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, validate_document


TOKEN = "0" * 26


def ref(kind: str, suffix: str = "") -> str:
    return f"{kind}_v1_{TOKEN[:-len(suffix)] if suffix else TOKEN}{suffix}"


def valid_bundle() -> dict[str, dict[str, object]]:
    request = {
        "contract_version": "v1", "request_id": ref("request"), "project_ref": ref("project"),
        "task_ref": ref("task"), "trace_id": ref("trace"), "space_id": "rowboat",
        "ingress_alias": "roarboot", "objective": "Produce a source-grounded knowledge briefing.",
        "query": "Which approved records support the architecture decision?", "requested_output": "briefing",
        "requested_at": "2026-07-31T10:00:00Z",
        "clarification": {"status": "resolved", "questions": [], "resolved_at": "2026-07-31T10:00:00Z"},
        "source_policy": {"allowed_source_kinds": ["workspace", "curated"], "citation_required": True},
        "hard_bounds": {"max_sources": 2, "max_chunks": 4, "timeout_seconds": 300, "max_steps": 4,
                        "max_retries": 1, "max_concurrency": 2, "max_cost_minor": 5000, "currency": "EUR"},
        "quote_ref": ref("quote"), "approval_ref": ref("approval"), "idempotency_key": "rowboat-contract-0001",
    }
    plan = {
        "contract_version": "v1", "plan_id": ref("plan"), "plan_version": 1, "plan_hash": "sha256:" + "a" * 64,
        "request_id": request["request_id"], "project_ref": request["project_ref"], "task_ref": request["task_ref"],
        "trace_id": request["trace_id"], "space_id": "rowboat", "requested_output": request["requested_output"],
        "created_at": "2026-07-31T10:01:00Z", "source_policy": request["source_policy"],
        "sources": [{"source_ref": ref("source"), "source_kind": "workspace"}, {"source_ref": ref("source", "A"), "source_kind": "curated"}],
        "stages": [
            {"stage_id": "retrieve", "order": 1, "kind": "retrieve", "depends_on": [], "source_refs": [ref("source"), ref("source", "A")]},
            {"stage_id": "compose", "order": 2, "kind": "compose", "depends_on": ["retrieve"], "source_refs": []},
        ],
        "required_citation_count": 1, "evidence_required": True, "output_artifact_ref": ref("artifact"),
    }
    run_request = {
        "contract_version": "v1", "run_id": ref("run"), "plan_id": plan["plan_id"], "plan_version": 1,
        "plan_hash": plan["plan_hash"], "request_id": request["request_id"], "project_ref": request["project_ref"],
        "task_ref": request["task_ref"], "trace_id": request["trace_id"], "space_id": "rowboat",
        "requested_output": request["requested_output"], "mode": "offline", "input_artifact_refs": [ref("artifact", "A")],
        "input_evidence_refs": [ref("evidence", "A")],
        "limits": {"max_sources": 2, "max_chunks": 4, "timeout_seconds": 300, "max_steps": 4,
                   "max_retries": 1, "max_concurrency": 2, "max_cost_minor": 5000, "currency": "EUR"},
        "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"], "idempotency_key": request["idempotency_key"],
    }
    state = {
        "contract_version": "v1", "run_id": run_request["run_id"], "plan_id": plan["plan_id"], "plan_version": 1,
        "plan_hash": plan["plan_hash"], "request_id": request["request_id"], "project_ref": request["project_ref"],
        "task_ref": request["task_ref"], "trace_id": request["trace_id"], "space_id": "rowboat",
        "requested_output": request["requested_output"], "mode": "offline", "revision": 3, "status": "succeeded",
        "event_history": [
            {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z"},
            {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z"},
            {"status": "succeeded", "revision": 3, "occurred_at": "2026-07-31T10:04:00Z"},
        ],
        "counters": {"sources_examined": 2, "chunks_examined": 2, "executed_steps": 2, "retry_count": 0,
                     "active_stages": 0, "actual_cost_minor": 1200}, "cancellation_requested": False,
        "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"], "idempotency_key": request["idempotency_key"],
    }
    result = {
        "contract_version": "v1", "result_id": ref("result"), "run_id": run_request["run_id"], "plan_id": plan["plan_id"],
        "plan_version": 1, "plan_hash": plan["plan_hash"], "request_id": request["request_id"],
        "project_ref": request["project_ref"], "task_ref": request["task_ref"], "trace_id": request["trace_id"],
        "space_id": "rowboat", "requested_output": request["requested_output"], "mode": "offline", "outcome": "succeeded",
        "started_at": "2026-07-31T10:02:00Z", "completed_at": "2026-07-31T10:04:00Z",
        "sources": [{"source_ref": ref("source"), "source_kind": "workspace", "evidence_ref": ref("evidence")},
                    {"source_ref": ref("source", "A"), "source_kind": "curated", "evidence_ref": ref("evidence", "B")}],
        "citations": [{"citation_ref": ref("citation"), "claim_id": "architecture-decision", "source_ref": ref("source"),
                       "evidence_ref": ref("evidence"), "locator_ref": "locator_v1_architecture-decision"}],
        "artifact_refs": [plan["output_artifact_ref"]], "evidence_refs": [ref("evidence"), ref("evidence", "B")], "log_refs": [ref("log")],
        "counters": state["counters"], "cost": {"actual_cost_minor": 1200, "currency": "EUR", "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"]},
    }
    return {"knowledge-request": request, "knowledge-plan": plan, "knowledge-run-request": run_request,
            "knowledge-run-state": state, "knowledge-result": result}


def mutate(document: str, path: tuple[object, ...], value: object) -> dict[str, dict[str, object]]:
    bundle = deepcopy(valid_bundle())
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
    return bundle


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_rowboat_bundle", None)
    assert callable(validator), "Rowboat bundle validation is not registered."
    validator(bundle)


def test_accepts_complete_bounded_offline_rowboat_bundle() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize("document_type", tuple(valid_bundle()))
def test_accepts_each_rowboat_document(document_type: str) -> None:
    validate_document(document_type, valid_bundle()[document_type])


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("knowledge-request", ("space_id",), "roarboot"),
        ("knowledge-request", ("ingress_alias",), "rowboat"),
        ("knowledge-request", ("clarification", "status"), "required"),
        ("knowledge-plan", ("sources", 1, "source_ref"), ref("source")),
        ("knowledge-plan", ("stages", 1, "stage_id"), "retrieve"),
        ("knowledge-plan", ("stages", 1, "depends_on"), ["unknown"]),
        ("knowledge-plan", ("stages", 0, "depends_on"), ["compose"]),
        ("knowledge-plan", ("stages", 1, "order"), 1),
        ("knowledge-plan", ("stages", 0, "source_refs"), [ref("source"), ref("source")]),
        ("knowledge-run-request", ("plan_hash",), "sha256:" + "b" * 64),
        ("knowledge-run-request", ("limits", "max_steps"), 5),
        ("knowledge-run-state", ("event_history", 0, "status"), "running"),
        ("knowledge-run-state", ("event_history", 2, "occurred_at"), "2026-07-31T10:01:30Z"),
        ("knowledge-run-state", ("cancellation_requested",), True),
        ("knowledge-run-state", ("counters", "executed_steps"), 5),
        ("knowledge-result", ("outcome",), "failed"),
        ("knowledge-result", ("citations", 0, "source_ref"), ref("source", "A")),
        ("knowledge-result", ("evidence_refs",), [ref("evidence", "B")]),
        ("knowledge-result", ("artifact_refs",), []),
        ("knowledge-result", ("cost", "actual_cost_minor"), 5001),
    ],
)
def test_rejects_rowboat_bundle_drift(document: str, path: tuple[object, ...], value: object) -> None:
    with pytest.raises(ContractValidationError):
        validate_bundle(mutate(document, path, value))


@pytest.mark.parametrize("field", ("provider", "model", "credential", "secret", "token", "api_key", "runtime", "url", "endpoint", "command", "prompt", "code"))
def test_rejects_direct_runtime_and_secret_fields(field: str) -> None:
    document = valid_bundle()["knowledge-request"]
    document[field] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("knowledge-request", document)


def test_accepts_offset_equivalent_terminal_timestamp() -> None:
    bundle = mutate("knowledge-run-state", ("event_history", 2, "occurred_at"), "2026-07-31T12:04:00+02:00")
    validate_bundle(bundle)


def test_rejects_wrong_document_set() -> None:
    bundle = valid_bundle()
    del bundle["knowledge-result"]
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("stage_path", "value"),
    [
        ((0, "source_refs"), []),
        ((0, "source_refs"), [ref("source")]),
        ((1, "depends_on"), []),
    ],
)
def test_rejects_ungrounded_retrieval_or_composition(
    stage_path: tuple[object, ...], value: object
) -> None:
    bundle = valid_bundle()
    stage_index, field_name = stage_path
    assert isinstance(stage_index, int)
    assert isinstance(field_name, str)
    bundle["knowledge-plan"]["stages"][stage_index][field_name] = value
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("knowledge-request", ("clarification", "resolved_at"), "2026-07-31T10:01:01Z"),
        ("knowledge-plan", ("created_at",), "2026-07-31T09:59:59Z"),
        ("knowledge-run-state", ("event_history", 0, "occurred_at"), "2026-07-31T10:00:59Z"),
    ],
)
def test_rejects_clarification_plan_and_queue_chronology_drift(
    document: str, path: tuple[object, ...], value: object
) -> None:
    with pytest.raises(ContractValidationError):
        validate_bundle(mutate(document, path, value))


def test_rejects_result_exceeding_run_timeout() -> None:
    bundle = valid_bundle()
    bundle["knowledge-run-state"]["event_history"][2]["occurred_at"] = "2026-07-31T10:07:01Z"
    bundle["knowledge-result"]["completed_at"] = "2026-07-31T10:07:01Z"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_terminal_active_stages() -> None:
    bundle = valid_bundle()
    bundle["knowledge-run-state"]["counters"]["active_stages"] = 1
    bundle["knowledge-result"]["counters"]["active_stages"] = 1
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_more_result_sources_than_examined() -> None:
    bundle = valid_bundle()
    bundle["knowledge-run-state"]["counters"]["sources_examined"] = 1
    bundle["knowledge-result"]["counters"]["sources_examined"] = 1
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_more_examined_sources_than_immutable_plan() -> None:
    bundle = valid_bundle()
    bundle["knowledge-plan"]["sources"] = [bundle["knowledge-plan"]["sources"][0]]
    bundle["knowledge-plan"]["stages"][0]["source_refs"] = [ref("source")]
    bundle["knowledge-result"]["sources"] = [bundle["knowledge-result"]["sources"][0]]
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_success_result_with_error_class() -> None:
    bundle = valid_bundle()
    bundle["knowledge-result"]["error_class"] = "execution_failed"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    "clarification",
    [
        {"status": "required", "questions": ["Which audience?"], "resolved_at": "2026-07-31T10:00:00Z"},
        {"status": "resolved", "questions": ["Which audience?"], "resolved_at": "2026-07-31T10:00:00Z"},
    ],
)
def test_rejects_inconsistent_clarification_document(clarification: dict[str, object]) -> None:
    document = valid_bundle()["knowledge-request"]
    document["clarification"] = clarification
    with pytest.raises(ContractValidationError):
        validate_document("knowledge-request", document)
