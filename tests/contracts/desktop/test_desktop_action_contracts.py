from __future__ import annotations

from copy import deepcopy

import pytest

from shared.contracts import validate as contracts
from shared.contracts.validate import ContractValidationError


def ref(kind: str, character: str = "0") -> str:
    return f"{kind}_v1_{character * 26}"


def digest(character: str = "a") -> str:
    return f"sha256:{character * 64}"


def target_refs() -> list[dict[str, str]]:
    return [
        {
            "target_ref": ref("target"),
            "application_ref": ref("application"),
            "window_ref": ref("window"),
        }
    ]


def limits() -> dict[str, object]:
    return {
        "timeout_seconds": 300,
        "max_steps": 3,
        "max_retries": 1,
        "max_cost_minor": 250,
        "currency": "EUR",
        "max_screenshots": 3,
        "max_artifacts": 3,
    }


def valid_bundle() -> dict[str, dict[str, object]]:
    targets = target_refs()
    request = {
        "contract_version": "v1", "request_id": ref("request"), "project_ref": ref("project"),
        "task_ref": ref("task"), "trace_id": ref("trace"), "space_id": "desktop",
        "objective": "Apply the already clarified desktop change.", "action_class": "input",
        "mutation_class": "mutating", "risk_class": "high", "target_refs": targets, "requested_at": "2026-07-31T10:00:00Z",
        "clarification": {"status": "resolved", "questions": [], "resolved_at": "2026-07-31T10:01:00Z", "clarification_ref": ref("clarification")},
        "hard_bounds": limits(), "request_hash": digest(), "quote_ref": ref("quote"),
        "approval_ref": ref("approval"), "idempotency_key": "desktop-test-1",
    }
    plan = {
        "contract_version": "v1", "plan_id": ref("plan"), "plan_version": 1, "plan_hash": digest("b"),
        "request_id": ref("request"), "project_ref": ref("project"), "task_ref": ref("task"),
        "trace_id": ref("trace"), "space_id": "desktop", "created_at": "2026-07-31T10:02:00Z",
        "request_hash": digest(), "parameter_digest": digest("c"), "approval_class": "mutating",
        "bounds": limits(), "actions": [{
            "action_id": "apply", "order": 1, "depends_on": [], "action_class": "input",
            "mutation_class": "mutating", "capability_profile_ref": ref("capability"),
            "target_refs": targets, "precondition_refs": [ref("evidence")],
            "postcondition_refs": [ref("evidence", "A")], "evidence_requirements": ["before_visual", "after_visual", "external_verification"],
            "stop_condition_refs": [ref("stop")], "parameter_digest": digest("d"),
        }],
    }
    run_request = {
        "contract_version": "v1", "run_id": ref("run"), "plan_id": ref("plan"), "plan_version": 1,
        "plan_hash": digest("b"), "request_id": ref("request"), "project_ref": ref("project"),
        "task_ref": ref("task"), "trace_id": ref("trace"), "space_id": "desktop", "mode": "manual",
        "mutation_class": "mutating", "request_hash": digest(), "parameter_digest": digest("c"),
        "limits": limits(), "confirmation_ref": ref("confirmation"), "confirmed_parameter_digest": digest("c"),
        "quote_ref": ref("quote"), "approval_ref": ref("approval"), "idempotency_key": "desktop-test-1",
    }
    history = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:03:00Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_confirmation", "revision": 2, "occurred_at": "2026-07-31T10:03:01Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_approval", "revision": 3, "occurred_at": "2026-07-31T10:03:02Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:03Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:03:10Z", "pause_ref": None, "cancellation_ref": None},
    ]
    state = {
        "contract_version": "v1", "run_id": ref("run"), "plan_id": ref("plan"), "plan_version": 1,
        "plan_hash": digest("b"), "request_id": ref("request"), "project_ref": ref("project"),
        "task_ref": ref("task"), "trace_id": ref("trace"), "space_id": "desktop", "mode": "manual",
        "mutation_class": "mutating", "request_hash": digest(), "parameter_digest": digest("c"),
        "confirmation_ref": ref("confirmation"), "confirmed_parameter_digest": digest("c"),
        "quote_ref": ref("quote"), "approval_ref": ref("approval"), "idempotency_key": "desktop-test-1",
        "revision": 5, "status": "succeeded", "event_history": history, "cancellation_requested": False,
        "cancellation_ref": None, "active_actions": 0,
        "counters": {"executed_steps": 1, "retry_count": 0, "screenshot_count": 2, "artifact_count": 1},
        "cost": {"actual_cost_minor": 10, "currency": "EUR", "quote_ref": ref("quote"), "approval_ref": ref("approval")},
    }
    result = {
        "contract_version": "v1", "result_id": ref("result"), "run_id": ref("run"), "plan_id": ref("plan"),
        "plan_version": 1, "plan_hash": digest("b"), "request_id": ref("request"), "project_ref": ref("project"),
        "task_ref": ref("task"), "trace_id": ref("trace"), "space_id": "desktop", "mode": "manual",
        "mutation_class": "mutating", "request_hash": digest(), "parameter_digest": digest("c"),
        "confirmation_ref": ref("confirmation"), "confirmed_parameter_digest": digest("c"),
        "quote_ref": ref("quote"), "approval_ref": ref("approval"), "idempotency_key": "desktop-test-1",
        "outcome": "succeeded", "started_at": "2026-07-31T10:03:03Z", "completed_at": "2026-07-31T10:03:10Z",
        "target_refs": targets, "visual_evidence": {"before_screenshot_ref": ref("screenshot"), "after_screenshot_ref": ref("screenshot", "A"), "current_screenshot_ref": None},
        "artifact_refs": [ref("artifact")], "evidence_refs": [ref("evidence")], "log_refs": [ref("log")],
        "externally_verifiable": True, "verification_ref": ref("verification"),
        "counters": {"executed_steps": 1, "retry_count": 0, "screenshot_count": 2, "artifact_count": 1},
        "cost": {"actual_cost_minor": 10, "currency": "EUR", "quote_ref": ref("quote"), "approval_ref": ref("approval")},
    }
    return {"desktop-action-request": request, "desktop-action-plan": plan, "desktop-action-run-request": run_request, "desktop-action-run-state": state, "desktop-action-result": result}


def bundle() -> dict[str, dict[str, object]]:
    return deepcopy(valid_bundle())


def test_accepts_complete_confirmed_mutating_desktop_bundle() -> None:
    contracts.validate_desktop_bundle(bundle())


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("desktop-action-request", ("space_id",), "openclaw"),
        ("desktop-action-plan", ("actions", 0, "action_class"), "observe"),
        ("desktop-action-plan", ("actions", 0, "depends_on"), ["missing"]),
        ("desktop-action-plan", ("actions", 0, "order"), 2),
        ("desktop-action-run-request", ("plan_hash",), digest("e")),
        ("desktop-action-run-request", ("confirmed_parameter_digest",), digest("e")),
        ("desktop-action-run-state", ("event_history", 0, "status"), "running"),
        ("desktop-action-run-state", ("counters", "executed_steps"), 4),
        ("desktop-action-result", ("externally_verifiable",), False),
        ("desktop-action-result", ("visual_evidence", "before_screenshot_ref"), None),
    ],
)
def test_rejects_desktop_contract_semantic_drift(document: str, path: tuple[object, ...], value: object) -> None:
    documents = bundle()
    target: object = documents[document]
    for part in path[:-1]:
        target = target[part]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    with pytest.raises(ContractValidationError):
        contracts.validate_desktop_bundle(documents)


def test_rejects_plan_before_resolved_clarification() -> None:
    documents = bundle()
    documents["desktop-action-plan"]["created_at"] = "2026-07-31T10:00:30Z"
    with pytest.raises(ContractValidationError):
        contracts.validate_desktop_bundle(documents)


def test_rejects_duplicate_or_cyclic_desktop_actions() -> None:
    documents = bundle()
    action = deepcopy(documents["desktop-action-plan"]["actions"][0])
    action["action_id"] = "verify"
    action["order"] = 2
    action["depends_on"] = ["apply"]
    documents["desktop-action-plan"]["actions"].append(action)
    documents["desktop-action-plan"]["actions"][0]["depends_on"] = ["verify"]
    with pytest.raises(ContractValidationError):
        contracts.validate_desktop_bundle(documents)


def test_rejects_missing_mutation_confirmation_and_readonly_confirmation() -> None:
    mutating = bundle()
    del mutating["desktop-action-run-request"]["confirmation_ref"]
    with pytest.raises(ContractValidationError):
        contracts.validate_document("desktop-action-run-request", mutating["desktop-action-run-request"])
    readonly = bundle()["desktop-action-run-request"]
    readonly["mutation_class"] = "readonly"
    with pytest.raises(ContractValidationError):
        contracts.validate_document("desktop-action-run-request", readonly)


@pytest.mark.parametrize("field", ("url", "selector", "text_to_type", "command", "prompt", "code", "coordinates", "keystrokes", "payload", "credential", "secret", "ok", "mock", "status_code"))
def test_rejects_raw_desktop_execution_or_success_shortcuts(field: str) -> None:
    document = bundle()["desktop-action-request"]
    document[field] = "forbidden"
    with pytest.raises(ContractValidationError):
        contracts.validate_document("desktop-action-request", document)


def test_rejects_terminal_reopening_pause_without_ref_and_cancellation_without_ref() -> None:
    documents = bundle()
    state = documents["desktop-action-run-state"]
    state["event_history"].append({"status": "running", "revision": 6, "occurred_at": "2026-07-31T10:03:11Z", "pause_ref": None, "cancellation_ref": None})
    state["revision"] = 6
    state["status"] = "running"
    with pytest.raises(ContractValidationError):
        contracts.validate_desktop_bundle(documents)
    state = bundle()["desktop-action-run-state"]
    state["event_history"][3] = {"status": "paused", "revision": 4, "occurred_at": "2026-07-31T10:03:03Z", "pause_ref": None, "cancellation_ref": None}
    with pytest.raises(ContractValidationError):
        contracts.validate_document("desktop-action-run-state", state)


def test_accepts_offset_equivalent_terminal_timestamp() -> None:
    documents = bundle()
    documents["desktop-action-run-state"]["event_history"][-1]["occurred_at"] = "2026-07-31T12:03:10+02:00"
    documents["desktop-action-result"]["completed_at"] = "2026-07-31T12:03:10+02:00"
    contracts.validate_desktop_bundle(documents)


def test_rejects_mutating_run_that_skips_confirmation_and_approval() -> None:
    documents = bundle()
    state = documents["desktop-action-run-state"]
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:03:00Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 2, "occurred_at": "2026-07-31T10:03:03Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "succeeded", "revision": 3, "occurred_at": "2026-07-31T10:03:10Z", "pause_ref": None, "cancellation_ref": None},
    ]
    state["revision"] = 3
    with pytest.raises(ContractValidationError, match="confirmation"):
        contracts.validate_desktop_bundle(documents)


def test_rejects_mutating_run_with_approval_before_confirmation() -> None:
    documents = bundle()
    state = documents["desktop-action-run-state"]
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:03:00Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_approval", "revision": 2, "occurred_at": "2026-07-31T10:03:01Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_confirmation", "revision": 3, "occurred_at": "2026-07-31T10:03:02Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:03Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "succeeded", "revision": 5, "occurred_at": "2026-07-31T10:03:10Z", "pause_ref": None, "cancellation_ref": None},
    ]
    with pytest.raises(ContractValidationError):
        contracts.validate_desktop_bundle(documents)


def test_rejects_readonly_waiting_for_confirmation() -> None:
    state = bundle()["desktop-action-run-state"]
    state["mutation_class"] = "readonly"
    state["confirmation_ref"] = None
    state["confirmed_parameter_digest"] = None
    state["event_history"] = [
        {"status": "queued", "revision": 1, "occurred_at": "2026-07-31T10:03:00Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_confirmation", "revision": 2, "occurred_at": "2026-07-31T10:03:01Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "waiting_for_approval", "revision": 3, "occurred_at": "2026-07-31T10:03:02Z", "pause_ref": None, "cancellation_ref": None},
        {"status": "running", "revision": 4, "occurred_at": "2026-07-31T10:03:03Z", "pause_ref": None, "cancellation_ref": None},
    ]
    state["revision"] = 4
    state["status"] = "running"
    with pytest.raises(ContractValidationError, match="read-only"):
        contracts.validate_document("desktop-action-run-state", state)


def test_rejects_worked_result_over_its_full_timeout_including_pauses() -> None:
    documents = bundle()
    documents["desktop-action-run-state"]["event_history"][-1]["occurred_at"] = "2026-07-31T10:08:04Z"
    documents["desktop-action-result"]["completed_at"] = "2026-07-31T10:08:04Z"
    with pytest.raises(ContractValidationError, match="timeout"):
        contracts.validate_desktop_bundle(documents)


def test_accepts_offset_equivalent_result_interval_within_timeout() -> None:
    documents = bundle()
    documents["desktop-action-run-state"]["event_history"][-1]["occurred_at"] = "2026-07-31T12:08:03+02:00"
    documents["desktop-action-result"]["started_at"] = "2026-07-31T12:03:03+02:00"
    documents["desktop-action-result"]["completed_at"] = "2026-07-31T12:08:03+02:00"
    contracts.validate_desktop_bundle(documents)


@pytest.mark.parametrize(
    ("counter", "value"),
    [("artifact_count", 2), ("screenshot_count", 3)],
)
def test_rejects_result_counter_not_equal_to_its_evidence(counter: str, value: int) -> None:
    documents = bundle()
    documents["desktop-action-run-state"]["counters"][counter] = value
    documents["desktop-action-result"]["counters"][counter] = value
    with pytest.raises(ContractValidationError, match="counter"):
        contracts.validate_desktop_bundle(documents)


def test_rejects_identical_mutating_before_and_after_screenshots() -> None:
    documents = bundle()
    visual = documents["desktop-action-result"]["visual_evidence"]
    visual["after_screenshot_ref"] = visual["before_screenshot_ref"]
    with pytest.raises(ContractValidationError, match="distinct"):
        contracts.validate_desktop_bundle(documents)


@pytest.mark.parametrize(
    ("action_class", "mutation_class"),
    [("observe", "mutating"), ("input", "readonly"), ("application_control", "readonly")],
)
def test_rejects_request_action_mutation_mismatch(action_class: str, mutation_class: str) -> None:
    request = bundle()["desktop-action-request"]
    request["action_class"] = action_class
    request["mutation_class"] = mutation_class
    with pytest.raises(ContractValidationError, match="request"):
        contracts.validate_document("desktop-action-request", request)


def test_rejects_plan_that_omits_the_requested_action_class() -> None:
    documents = bundle()
    documents["desktop-action-plan"]["actions"][0]["action_class"] = "navigate"
    with pytest.raises(ContractValidationError, match="requested action_class"):
        contracts.validate_desktop_bundle(documents)


def test_rejects_succeeded_state_or_result_with_error_class() -> None:
    documents = bundle()
    documents["desktop-action-run-state"]["error_class"] = "execution_failed"
    documents["desktop-action-result"]["error_class"] = "execution_failed"
    with pytest.raises(ContractValidationError, match="succeeded"):
        contracts.validate_desktop_bundle(documents)
