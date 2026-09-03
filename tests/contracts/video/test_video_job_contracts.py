from __future__ import annotations

from copy import deepcopy

import pytest

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, validate_document


TOKEN = "0" * 26


def ref(kind: str, suffix: str = "") -> str:
    return f"{kind}_v1_{TOKEN[:-len(suffix)] if suffix else TOKEN}{suffix}"


def valid_bundle() -> dict[str, dict[str, object]]:
    limits = {
        "timeout_seconds": 600,
        "max_steps": 8,
        "max_retries": 1,
        "max_concurrency": 2,
        "max_cost_minor": 4000,
        "currency": "EUR",
        "max_artifacts": 4,
        "max_input_bytes": 10_000_000,
        "max_output_bytes": 20_000_000,
        "max_duration_seconds": 120,
    }
    request = {
        "contract_version": "v1",
        "request_id": ref("request"),
        "project_ref": ref("project"),
        "task_ref": ref("task"),
        "trace_id": ref("trace"),
        "space_id": "video",
        "job_kind": "video",
        "requested_artifact_kinds": ["video", "thumbnail"],
        "requested_at": "2026-08-01T10:00:00Z",
        "clarification": {"status": "resolved", "questions": [], "resolved_at": "2026-08-01T10:00:00Z"},
        "hard_limits": limits,
        "quote_ref": ref("quote"),
        "approval_ref": ref("approval"),
        "idempotency_key": "video-contract-0001",
    }
    plan = {
        "contract_version": "v1",
        "plan_id": ref("plan"),
        "plan_version": 1,
        "plan_hash": "sha256:" + "a" * 64,
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "video",
        "job_kind": request["job_kind"],
        "created_at": "2026-08-01T10:01:00Z",
        "steps": [
            {"step_id": "compose", "order": 1, "depends_on": [], "capability": "media_transform", "output_artifact_kinds": ["video"]},
            {"step_id": "preview", "order": 2, "depends_on": ["compose"], "capability": "vision_analyze", "output_artifact_kinds": ["thumbnail"]},
        ],
        "declared_artifact_kinds": request["requested_artifact_kinds"],
        "success_criteria": ["artifacts_declared", "terminal_evidence", "cost_accounted"],
        "limits": deepcopy(limits),
    }
    run_request = {
        "contract_version": "v1",
        "run_id": ref("run"),
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "plan_hash": plan["plan_hash"],
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "video",
        "job_kind": request["job_kind"],
        "mode": "dry_run",
        "input_artifact_refs": [ref("artifact")],
        "approved_limits": deepcopy(limits),
        "quote_ref": request["quote_ref"],
        "approval_ref": request["approval_ref"],
        "idempotency_key": request["idempotency_key"],
    }
    events = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-08-01T10:01:00Z"},
        {"status": "running", "revision": 2, "occurred_at": "2026-08-01T10:02:00Z"},
        {"status": "succeeded", "revision": 3, "occurred_at": "2026-08-01T10:04:00Z"},
    ]
    cost = {"actual_cost_minor": 1000, "currency": "EUR", "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"]}
    state = {
        "contract_version": "v1",
        "run_id": run_request["run_id"],
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "plan_hash": plan["plan_hash"],
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "video",
        "job_kind": request["job_kind"],
        "mode": run_request["mode"],
        "revision": 3,
        "status": "succeeded",
        "event_history": events,
        "counters": {"executed_steps": 2, "retry_count": 0, "active_workers": 0, "artifact_count": 2, "input_bytes": 1000, "output_bytes": 2000, "media_duration_seconds": 30},
        "cost": cost,
    }
    result = {
        "contract_version": "v1",
        "result_id": ref("result"),
        "terminal_result_ref": ref("terminal_result"),
        "run_id": run_request["run_id"],
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "plan_hash": plan["plan_hash"],
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "video",
        "job_kind": request["job_kind"],
        "mode": run_request["mode"],
        "outcome": "succeeded",
        "started_at": "2026-08-01T10:02:00Z",
        "completed_at": "2026-08-01T10:04:00Z",
        "artifacts": [
            {"artifact_ref": ref("artifact", "A"), "kind": "video", "content_hash": "sha256:" + "b" * 64, "size_bytes": 1500},
            {"artifact_ref": ref("artifact", "B"), "kind": "thumbnail", "content_hash": "sha256:" + "c" * 64, "size_bytes": 500},
        ],
        "evidence_refs": [ref("evidence")],
        "log_refs": [ref("log")],
        "counters": deepcopy(state["counters"]),
        "cost": deepcopy(cost),
        "satisfied_criteria": plan["success_criteria"],
    }
    return {
        "video-job-request": request,
        "video-job-plan": plan,
        "video-job-run-request": run_request,
        "video-job-run-state": state,
        "video-job-result": result,
    }


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_video_job_bundle", None)
    assert callable(validator), "VideoJob bundle validation is not registered."
    validator(bundle)


def mutate(document: str, path: tuple[object, ...], value: object) -> dict[str, dict[str, object]]:
    bundle = deepcopy(valid_bundle())
    target: object = bundle[document]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    return bundle


def direct_terminal_bundle(outcome: str) -> dict[str, dict[str, object]]:
    bundle = valid_bundle()
    state = bundle["video-job-run-state"]
    result = bundle["video-job-result"]
    state["revision"] = 2
    state["status"] = outcome
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-08-01T10:01:00Z"},
        {"status": outcome, "revision": 2, "occurred_at": "2026-08-01T10:01:30Z"},
    ]
    counters = state["counters"]
    assert isinstance(counters, dict)
    counters.update({"executed_steps": 0, "active_workers": 0, "artifact_count": 0, "output_bytes": 0, "media_duration_seconds": 0})
    result["outcome"] = outcome
    result["started_at"] = "2026-08-01T10:01:00Z"
    result["completed_at"] = "2026-08-01T10:01:30Z"
    result["artifacts"] = []
    result["evidence_refs"] = []
    result["log_refs"] = []
    result["counters"] = deepcopy(counters)
    result["satisfied_criteria"] = []
    result.pop("terminal_result_ref")
    if outcome in {"failed", "unavailable"}:
        state["error_class"] = "execution_failed" if outcome == "failed" else "resource_unavailable"
        result["error_class"] = state["error_class"]
    return bundle


def test_accepts_complete_offline_video_job_bundle() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize("document_type", tuple(valid_bundle()))
def test_accepts_each_closed_draft_2020_12_document(document_type: str) -> None:
    validate_document(document_type, valid_bundle()[document_type])


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("video-job-request", ("space_id",), "vision"),
        ("video-job-request", ("clarification", "status"), "required"),
        ("video-job-plan", ("request_id",), ref("request", "A")),
        ("video-job-run-request", ("plan_hash",), "sha256:" + "d" * 64),
        ("video-job-run-request", ("approval_ref",), ref("approval", "A")),
        ("video-job-run-state", ("cost", "actual_cost_minor"), 4001),
        ("video-job-run-state", ("counters", "output_bytes"), 20_000_001),
        ("video-job-run-state", ("counters", "active_workers"), 3),
        ("video-job-result", ("artifacts",), []),
        ("video-job-result", ("evidence_refs",), []),
        ("video-job-result", ("log_refs",), []),
        ("video-job-result", ("terminal_result_ref",), None),
        ("video-job-result", ("cost", "quote_ref"), ref("quote", "A")),
    ],
)
def test_rejects_identity_hash_approval_cost_artifact_and_evidence_drift(
    document: str, path: tuple[object, ...], value: object
) -> None:
    with pytest.raises(ContractValidationError):
        validate_bundle(mutate(document, path, value))


def test_rejects_terminal_state_reopening() -> None:
    bundle = valid_bundle()
    history = bundle["video-job-run-state"]["event_history"]
    assert isinstance(history, list)
    history.append({"status": "running", "revision": 4, "occurred_at": "2026-08-01T10:05:00Z"})
    bundle["video-job-run-state"]["revision"] = 4
    bundle["video-job-run-state"]["status"] = "running"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_active_workers_above_concurrency_limit() -> None:
    bundle = valid_bundle()
    bundle["video-job-run-state"]["counters"]["active_workers"] = 3  # type: ignore[index]
    bundle["video-job-result"]["counters"]["active_workers"] = 3  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="active_workers"):
        validate_bundle(bundle)


@pytest.mark.parametrize("outcome", ("cancelled", "failed", "unavailable"))
def test_accepts_direct_terminal_bundle_without_running(outcome: str) -> None:
    validate_bundle(direct_terminal_bundle(outcome))


def test_rejects_terminal_bundle_with_active_workers() -> None:
    bundle = direct_terminal_bundle("cancelled")
    bundle["video-job-run-state"]["counters"]["active_workers"] = 1  # type: ignore[index]
    bundle["video-job-result"]["counters"]["active_workers"] = 1  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="active_workers"):
        validate_bundle(bundle)


def test_rejects_succeeded_bundle_without_all_plan_steps_executed() -> None:
    bundle = valid_bundle()
    bundle["video-job-run-state"]["counters"]["executed_steps"] = 1  # type: ignore[index]
    bundle["video-job-result"]["counters"]["executed_steps"] = 1  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="executed_steps"):
        validate_bundle(bundle)


def test_rejects_clarification_resolved_after_plan_creation() -> None:
    bundle = valid_bundle()
    bundle["video-job-request"]["clarification"]["resolved_at"] = "2026-08-01T10:01:01Z"  # type: ignore[index]
    with pytest.raises(ContractValidationError, match="chronology"):
        validate_bundle(bundle)


@pytest.mark.parametrize("shortcut", ("mock", "queued", "dispatched", "healthcheck", "ok"))
def test_rejects_success_shortcuts_and_runtime_fields(shortcut: str) -> None:
    document = valid_bundle()["video-job-result"]
    document[shortcut] = True
    with pytest.raises(ContractValidationError):
        validate_document("video-job-result", document)


@pytest.mark.parametrize("job_kind", ("audio", "vision"))
def test_accepts_provider_neutral_audio_and_vision_requests(job_kind: str) -> None:
    bundle = valid_bundle()
    for document in bundle.values():
        document["job_kind"] = job_kind
    validate_bundle(bundle)


@pytest.mark.parametrize("outcome", ("failed", "unavailable"))
def test_non_success_requires_closed_redacted_error_class(outcome: str) -> None:
    bundle = valid_bundle()
    state = bundle["video-job-run-state"]
    result = bundle["video-job-result"]
    state["status"] = outcome
    state["event_history"][-1]["status"] = outcome  # type: ignore[index]
    result["outcome"] = outcome
    result["artifacts"] = []
    result["evidence_refs"] = []
    result["log_refs"] = []
    result["satisfied_criteria"] = []
    result.pop("terminal_result_ref")
    with pytest.raises(ContractValidationError, match="error_class"):
        validate_bundle(bundle)
