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
        "contract_version": "v1",
        "request_id": ref("request"),
        "project_ref": ref("project"),
        "task_ref": ref("task"),
        "trace_id": ref("trace"),
        "space_id": "coding",
        "objective": "Apply the approved bounded repository change.",
        "change_kind": "change",
        "repository_ref": ref("repository"),
        "base_ref": ref("base"),
        "requested_outputs": ["change_set", "test_evidence"],
        "requested_at": "2026-07-31T10:00:00Z",
        "clarification": {"status": "resolved", "questions": [], "resolved_at": "2026-07-31T10:00:00Z"},
        "risk_class": "moderate",
        "hard_bounds": {
            "timeout_seconds": 300,
            "max_steps": 10,
            "max_retries": 1,
            "max_concurrency": 2,
            "max_cost_minor": 5000,
            "currency": "EUR",
            "max_changed_files": 3,
            "max_artifacts": 2,
            "max_test_profiles": 2,
        },
        "quote_ref": ref("quote"),
        "approval_ref": ref("approval"),
        "idempotency_key": "coding-contract-0001",
    }
    test_profile_ref = ref("test_profile")
    plan = {
        "contract_version": "v1",
        "plan_id": ref("plan"),
        "plan_version": 1,
        "plan_hash": "sha256:" + "a" * 64,
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "coding",
        "repository_ref": request["repository_ref"],
        "base_ref": request["base_ref"],
        "change_kind": request["change_kind"],
        "requested_outputs": request["requested_outputs"],
        "created_at": "2026-07-31T10:01:00Z",
        "capabilities": ["repository_read", "repository_write", "test_profile_execute"],
        "phases": [
            {
                "phase_id": "prepare",
                "order": 1,
                "depends_on": [],
                "tasks": [{"task_id": "inspect", "order": 1, "depends_on": [], "capabilities": ["repository_read"], "input_artifact_kinds": [], "output_artifact_kinds": ["repository_snapshot"], "test_profile_refs": []}],
            },
            {
                "phase_id": "change",
                "order": 2,
                "depends_on": ["prepare"],
                "tasks": [{"task_id": "edit", "order": 1, "depends_on": ["inspect"], "capabilities": ["repository_write"], "input_artifact_kinds": ["repository_snapshot"], "output_artifact_kinds": ["change_set"], "test_profile_refs": []}],
            },
            {
                "phase_id": "verify",
                "order": 3,
                "depends_on": ["change"],
                "tasks": [{"task_id": "test", "order": 1, "depends_on": ["edit"], "capabilities": ["test_profile_execute"], "input_artifact_kinds": ["change_set"], "output_artifact_kinds": ["test_summary"], "test_profile_refs": [test_profile_ref]}],
            },
        ],
        "required_output_artifact_kinds": ["change_set"],
        "required_test_profile_refs": [test_profile_ref],
        "success_criteria": [
            {"criterion_id": "change-artifact", "kind": "artifact"},
            {"criterion_id": "approved-tests", "kind": "test"},
            {"criterion_id": "evidence-recorded", "kind": "evidence"},
        ],
        "bounds": deepcopy(request["hard_bounds"]),
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
        "space_id": "coding",
        "repository_ref": request["repository_ref"],
        "base_ref": request["base_ref"],
        "mode": "dry_run",
        "input_artifact_refs": [ref("artifact")],
        "approved_limits": deepcopy(request["hard_bounds"]),
        "quote_ref": request["quote_ref"],
        "approval_ref": request["approval_ref"],
        "idempotency_key": request["idempotency_key"],
    }
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
        "space_id": "coding",
        "repository_ref": request["repository_ref"],
        "base_ref": request["base_ref"],
        "mode": run_request["mode"],
        "revision": 4,
        "status": "succeeded",
        "event_history": [
            {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
            {"status": "waiting_for_approval", "revision": 2, "occurred_at": "2026-07-31T10:01:01Z", "checkpoint_ref": None, "cancellation_ref": None},
            {"status": "running", "revision": 3, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
            {"status": "succeeded", "revision": 4, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        ],
        "cancellation_requested": False,
        "resume_from_checkpoint_ref": None,
        "counters": {"executed_steps": 3, "retry_count": 0, "active_workers": 0, "changed_file_count": 2, "artifact_count": 1, "test_count": 1},
        "cost": {"actual_cost_minor": 100, "currency": "EUR", "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"]},
    }
    commit_ref = ref("commit")
    result = {
        "contract_version": "v1",
        "result_id": ref("result"),
        "run_id": run_request["run_id"],
        "plan_id": plan["plan_id"],
        "plan_version": plan["plan_version"],
        "plan_hash": plan["plan_hash"],
        "request_id": request["request_id"],
        "project_ref": request["project_ref"],
        "task_ref": request["task_ref"],
        "trace_id": request["trace_id"],
        "space_id": "coding",
        "repository_ref": request["repository_ref"],
        "base_ref": request["base_ref"],
        "head_ref": ref("head"),
        "head_commit_ref": commit_ref,
        "branch_ref": ref("branch"),
        "commit_ref": commit_ref,
        "pr_ref": ref("pr"),
        "worktree_ref": ref("worktree"),
        "mode": run_request["mode"],
        "outcome": "succeeded",
        "started_at": "2026-07-31T10:02:00Z",
        "completed_at": "2026-07-31T10:04:00Z",
        "artifacts": [{"artifact_ref": ref("artifact", "A"), "kind": "change_set"}],
        "evidence_refs": [ref("evidence")],
        "log_refs": [ref("log")],
        "test_summaries": [{"test_profile_ref": test_profile_ref, "test_summary_ref": ref("test_summary"), "status": "passed"}],
        "counters": deepcopy(state["counters"]),
        "cost": deepcopy(state["cost"]),
        "satisfied_criteria_ids": ["approved-tests", "change-artifact", "evidence-recorded"],
    }
    return {
        "code-job-request": request,
        "code-job-plan": plan,
        "code-job-run-request": run_request,
        "code-job-run-state": state,
        "code-job-result": result,
    }


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
    validator = getattr(contract_validation, "validate_code_job_bundle", None)
    assert callable(validator), "CodeJob bundle validation is not registered."
    validator(bundle)


def test_accepts_complete_bounded_dry_run_code_job_bundle() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize("document_type", tuple(valid_bundle()))
def test_accepts_each_code_job_document(document_type: str) -> None:
    validate_document(document_type, valid_bundle()[document_type])


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("code-job-request", ("space_id",), "codegen"),
        ("code-job-request", ("clarification", "status"), "required"),
        ("code-job-plan", ("phases", 2, "phase_id"), "change"),
        ("code-job-plan", ("phases", 2, "depends_on"), ["unknown"]),
        ("code-job-plan", ("phases", 0, "depends_on"), ["verify"]),
        ("code-job-plan", ("phases", 2, "order"), 2),
        ("code-job-plan", ("phases", 1, "tasks", 0, "capabilities"), ["repository_read"]),
        ("code-job-run-request", ("plan_hash",), "sha256:" + "b" * 64),
        ("code-job-run-request", ("approved_limits", "max_steps"), 11),
        ("code-job-run-state", ("event_history", 0, "status"), "running"),
        ("code-job-run-state", ("event_history", 3, "occurred_at"), "2026-07-31T10:01:30Z"),
        ("code-job-run-state", ("cancellation_requested",), True),
        ("code-job-run-state", ("counters", "changed_file_count"), 4),
        ("code-job-result", ("repository_ref",), ref("repository", "A")),
        ("code-job-result", ("head_commit_ref",), ref("commit", "A")),
        ("code-job-result", ("artifacts",), []),
        ("code-job-result", ("evidence_refs",), []),
        ("code-job-result", ("test_summaries", 0, "status"), "failed"),
        ("code-job-result", ("counters", "artifact_count"), 3),
        ("code-job-result", ("cost", "actual_cost_minor"), 5001),
    ],
)
def test_rejects_code_job_bundle_drift(document: str, path: tuple[object, ...], value: object) -> None:
    with pytest.raises(ContractValidationError):
        validate_bundle(mutate(document, path, value))


@pytest.mark.parametrize(
    "field",
    ("provider", "model", "credential", "runtime", "url", "endpoint", "webhook", "command", "shell", "prompt", "code", "patch", "diff", "ok", "mock"),
)
def test_rejects_raw_runtime_execution_and_success_shortcut_fields(field: str) -> None:
    document = valid_bundle()["code-job-request"]
    document[field] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("code-job-request", document)


def test_accepts_offset_equivalent_terminal_timestamp() -> None:
    bundle = mutate("code-job-run-state", ("event_history", 3, "occurred_at"), "2026-07-31T12:04:00+02:00")
    bundle["code-job-result"]["completed_at"] = "2026-07-31T12:04:00+02:00"
    validate_bundle(bundle)


def test_rejects_terminal_state_reopening() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"].append(
        {"status": "running", "revision": 5, "occurred_at": "2026-07-31T10:05:00Z", "checkpoint_ref": None, "cancellation_ref": None}
    )
    bundle["code-job-run-state"]["revision"] = 5
    bundle["code-job-run-state"]["status"] = "running"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_paused_resume_without_matching_checkpoint() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "paused", "revision": 3, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": ref("checkpoint"), "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:01Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    bundle["code-job-run-state"]["revision"] = 5
    bundle["code-job-run-state"]["resume_from_checkpoint_ref"] = None
    bundle["code-job-result"]["completed_at"] = "2026-07-31T10:04:00Z"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def set_bundle_bound(bundle: dict[str, dict[str, object]], name: str, value: int) -> None:
    for document, field in (("code-job-request", "hard_bounds"), ("code-job-plan", "bounds"), ("code-job-run-request", "approved_limits")):
        bounds = bundle[document][field]
        assert isinstance(bounds, dict)
        bounds[name] = value


def test_rejects_plan_with_more_declared_tasks_than_approved_steps() -> None:
    bundle = valid_bundle()
    set_bundle_bound(bundle, "max_steps", 2)
    with pytest.raises(ContractValidationError):
        validate_document("code-job-plan", bundle["code-job-plan"])


def test_rejects_plan_with_more_distinct_test_profiles_than_approved() -> None:
    bundle = valid_bundle()
    test_task = bundle["code-job-plan"]["phases"][1]["tasks"][0]
    test_task["test_profile_refs"] = [ref("test_profile", "A")]
    set_bundle_bound(bundle, "max_test_profiles", 1)
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_plan_with_more_required_artifacts_than_approved() -> None:
    bundle = valid_bundle()
    bundle["code-job-plan"]["required_output_artifact_kinds"] = ["change_set", "review_record"]
    bundle["code-job-plan"]["phases"][1]["tasks"][0]["output_artifact_kinds"] = ["change_set", "review_record"]
    set_bundle_bound(bundle, "max_artifacts", 1)
    with pytest.raises(ContractValidationError):
        validate_document("code-job-plan", bundle["code-job-plan"])


def test_rejects_required_artifact_kind_not_produced_by_plan_task() -> None:
    bundle = valid_bundle()
    bundle["code-job-plan"]["required_output_artifact_kinds"] = ["review_record"]
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("requested_output", "other_kind"),
    [("change_set", "review_record"), ("review_record", "change_set"), ("artifact", "change_set")],
)
def test_rejects_requested_output_without_matching_success_artifact(
    requested_output: str, other_kind: str
) -> None:
    bundle = valid_bundle()
    bundle["code-job-request"]["requested_outputs"] = [requested_output]
    bundle["code-job-plan"]["requested_outputs"] = [requested_output]
    bundle["code-job-plan"]["required_output_artifact_kinds"] = [other_kind]
    bundle["code-job-plan"]["phases"][1]["tasks"][0]["output_artifact_kinds"] = [other_kind]
    bundle["code-job-result"]["artifacts"][0]["kind"] = other_kind
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_test_evidence_requested_without_required_profile_mapping() -> None:
    bundle = valid_bundle()
    bundle["code-job-request"]["requested_outputs"] = ["test_evidence"]
    bundle["code-job-plan"]["requested_outputs"] = ["test_evidence"]
    bundle["code-job-plan"]["required_test_profile_refs"] = []
    bundle["code-job-plan"]["phases"][2]["tasks"][0]["test_profile_refs"] = []
    bundle["code-job-plan"]["capabilities"] = ["repository_read", "repository_write"]
    bundle["code-job-plan"]["phases"][2]["tasks"][0]["capabilities"] = ["repository_write"]
    with pytest.raises(ContractValidationError, match="requested output"):
        validate_bundle(bundle)


def test_rejects_plan_created_before_request() -> None:
    bundle = valid_bundle()
    bundle["code-job-plan"]["created_at"] = "2026-07-31T09:59:59Z"
    with pytest.raises(ContractValidationError, match="request"):
        validate_bundle(bundle)


def test_rejects_queued_event_before_plan_creation() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"][0]["occurred_at"] = "2026-07-31T10:00:30Z"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_running_event_after_result_start() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"][2]["occurred_at"] = "2026-07-31T10:02:01Z"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_rejects_failed_work_without_running_predecessor() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_approval", "revision": 2, "occurred_at": "2026-07-31T10:01:01Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "failed", "revision": 3, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    bundle["code-job-run-state"]["revision"] = 3
    bundle["code-job-run-state"]["status"] = "failed"
    bundle["code-job-run-state"]["error_class"] = "execution_failed"
    bundle["code-job-result"]["outcome"] = "failed"
    bundle["code-job-result"]["completed_at"] = "2026-07-31T10:03:00Z"
    bundle["code-job-result"]["error_class"] = "execution_failed"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_accepts_valid_in_run_pause_resume_checkpoint() -> None:
    bundle = valid_bundle()
    checkpoint = ref("checkpoint")
    bundle["code-job-run-state"]["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "paused", "revision": 3, "occurred_at": "2026-07-31T10:02:30Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    bundle["code-job-run-state"]["revision"] = 5
    validate_bundle(bundle)


def test_rejects_result_start_reset_to_in_run_resume() -> None:
    bundle = valid_bundle()
    checkpoint = ref("checkpoint")
    bundle["code-job-run-state"]["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "paused", "revision": 3, "occurred_at": "2026-07-31T10:02:30Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    bundle["code-job-run-state"]["revision"] = 5
    bundle["code-job-result"]["started_at"] = "2026-07-31T10:03:00Z"
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)


def test_accepts_offset_equivalent_first_running_result_start_after_resume() -> None:
    bundle = valid_bundle()
    checkpoint = ref("checkpoint")
    bundle["code-job-run-state"]["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:01:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:02:00Z", "checkpoint_ref": None, "cancellation_ref": None},
        {"status": "paused", "revision": 3, "occurred_at": "2026-07-31T10:02:30Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:00Z", "checkpoint_ref": checkpoint, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:04:00Z", "checkpoint_ref": None, "cancellation_ref": None},
    ]
    bundle["code-job-run-state"]["revision"] = 5
    bundle["code-job-result"]["started_at"] = "2026-07-31T12:02:00+02:00"
    validate_bundle(bundle)


def test_accepts_valid_initial_resume_checkpoint() -> None:
    bundle = valid_bundle()
    checkpoint = ref("checkpoint")
    bundle["code-job-run-request"]["resume_from_checkpoint_ref"] = checkpoint
    bundle["code-job-run-state"]["resume_from_checkpoint_ref"] = checkpoint
    bundle["code-job-run-state"]["event_history"][2]["checkpoint_ref"] = checkpoint
    validate_bundle(bundle)


def test_rejects_checkpoint_on_queued_lifecycle_event() -> None:
    bundle = valid_bundle()
    bundle["code-job-run-state"]["event_history"][0]["checkpoint_ref"] = ref("checkpoint")
    with pytest.raises(ContractValidationError):
        validate_bundle(bundle)
