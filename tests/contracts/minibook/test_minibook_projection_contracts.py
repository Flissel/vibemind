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
        "project_refs": [ref("project")],
        "task_refs": [ref("task", "A"), ref("task", "B")],
        "trace_id": ref("trace"),
        "space_id": "minibook",
        "requested_views": ["projects", "tasks", "evidence"],
        "filters": {"project_refs": [ref("project")], "task_refs": [], "include_incomplete": True},
        "as_of_cursor": 41,
        "as_of_ref": ref("ledger"),
        "read_only": True,
        "bounds": {"max_projects": 1, "max_tasks_per_project": 2, "max_events": 2},
        "request_hash": "sha256:" + "a" * 64,
        "quote_ref": ref("quote"),
        "approval_refs": [ref("approval")],
        "idempotency_key": "minibook-projection-0001",
        "requested_at": "2026-07-31T10:00:00Z",
    }
    snapshot = {
        "contract_version": "v1",
        "projection_id": ref("projection"),
        "projection_version": 1,
        "projection_hash": "sha256:" + "b" * 64,
        "request_id": request["request_id"],
        "trace_id": request["trace_id"],
        "space_id": "minibook",
        "snapshot_cursor": request["as_of_cursor"],
        "source_ledger_refs": [ref("ledger")],
        "generated_at": "2026-07-31T10:01:00Z",
        "project_rows": [
            {
                "project_ref": ref("project"),
                "task_rows": [
                    {
                        "task_ref": ref("task", "A"),
                        "task_order": 1,
                        "parent_task_ref": None,
                        "depends_on_task_refs": [],
                        "brief_refs": [ref("task")],
                        "todo_refs": [ref("todo")],
                        "session_refs": [ref("session")],
                        "lifecycle_status": "succeeded",
                        "authority_ref": ref("authority"),
                        "approval_refs": [ref("approval")],
                        "cost_provenance_refs": [ref("evidence")],
                        "log_refs": [ref("log")],
                        "pr_refs": [ref("pr")],
                        "result_refs": [ref("result")],
                        "handoff_refs": [ref("handoff")],
                        "source_evidence_refs": [ref("evidence")],
                        "created_at": "2026-07-31T09:00:00Z",
                        "updated_at": "2026-07-31T10:00:30Z",
                        "complete": True,
                    },
                    {
                        "task_ref": ref("task", "B"),
                        "task_order": 2,
                        "parent_task_ref": ref("task", "A"),
                        "depends_on_task_refs": [ref("task", "A")],
                        "brief_refs": [ref("task", "A")],
                        "todo_refs": [ref("todo", "A")],
                        "session_refs": [ref("session", "A")],
                        "lifecycle_status": "queued",
                        "authority_ref": ref("authority"),
                        "approval_refs": [],
                        "cost_provenance_refs": [],
                        "log_refs": [],
                        "pr_refs": [],
                        "result_refs": [],
                        "handoff_refs": [],
                        "source_evidence_refs": [],
                        "created_at": "2026-07-31T10:00:31Z",
                        "updated_at": "2026-07-31T10:00:32Z",
                        "complete": False,
                    },
                ],
            }
        ],
        "stale": False,
        "complete": False,
    }
    delta = {
        "contract_version": "v1",
        "delta_id": ref("delta"),
        "projection_id": snapshot["projection_id"],
        "request_id": request["request_id"],
        "trace_id": request["trace_id"],
        "space_id": "minibook",
        "from_cursor": 39,
        "to_cursor": snapshot["snapshot_cursor"],
        "source_ledger_refs": snapshot["source_ledger_refs"],
        "events": [
            {"event_ref": ref("event", "A"), "source_revision": 40, "event_order": 1, "project_ref": ref("project"), "task_ref": ref("task", "A"), "row_hash": "sha256:" + "c" * 64},
            {"event_ref": ref("event", "B"), "source_revision": 41, "event_order": 2, "project_ref": ref("project"), "task_ref": ref("task", "B"), "row_hash": "sha256:" + "d" * 64},
        ],
        "generated_at": snapshot["generated_at"],
    }
    evidence = {
        "contract_version": "v1",
        "evidence_id": ref("evidence", "B"),
        "request_id": request["request_id"],
        "projection_id": snapshot["projection_id"],
        "snapshot_ref": snapshot["projection_id"],
        "delta_ref": delta["delta_id"],
        "snapshot_cursor": snapshot["snapshot_cursor"],
        "delta_to_cursor": delta["to_cursor"],
        "source_evidence_refs": [ref("evidence")],
        "source_log_refs": [ref("log")],
        "row_counts": {"project_count": 1, "task_count": 2, "event_count": 2},
        "cost_provenance_refs": [ref("evidence")],
        "generated_at": snapshot["generated_at"],
        "completed_at": "2026-07-31T10:01:01Z",
        "stale": False,
        "complete": False,
    }
    return {
        "minibook-projection-request": request,
        "minibook-projection-snapshot": snapshot,
        "minibook-projection-delta": delta,
        "minibook-projection-evidence": evidence,
    }


def validate_bundle(documents: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_minibook_projection_bundle", None)
    assert callable(validator), "Minibook projection bundle validation is not registered."
    validator(documents)


def mutate(document: str, path: tuple[object, ...], value: object) -> dict[str, dict[str, object]]:
    documents = deepcopy(valid_bundle())
    target: object = documents[document]
    for key in path[:-1]:
        assert isinstance(target, (dict, list))
        target = target[key]  # type: ignore[index]
    assert isinstance(target, dict)
    target[path[-1]] = value
    return documents


def with_second_project(documents: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    request = documents["minibook-projection-request"]
    snapshot = documents["minibook-projection-snapshot"]
    evidence = documents["minibook-projection-evidence"]
    request["project_refs"].append(ref("project", "A"))
    request["task_refs"].append(ref("task", "C"))
    request["filters"] = {"project_refs": [], "task_refs": [], "include_incomplete": True}
    request["bounds"]["max_projects"] = 2
    second_task = deepcopy(snapshot["project_rows"][0]["task_rows"][0])
    second_task.update({"task_ref": ref("task", "C"), "task_order": 1, "parent_task_ref": None, "depends_on_task_refs": []})
    snapshot["project_rows"].append({"project_ref": ref("project", "A"), "task_rows": [second_task]})
    evidence["row_counts"] = {"project_count": 2, "task_count": 3, "event_count": 2}
    return documents


def test_accepts_deterministic_offline_projection_bundle() -> None:
    validate_bundle(valid_bundle())


@pytest.mark.parametrize("document_type", tuple(valid_bundle()))
def test_accepts_each_minibook_projection_document(document_type: str) -> None:
    validate_document(document_type, valid_bundle()[document_type])


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("minibook-projection-request", ("space_id",), "desktop"),
        ("minibook-projection-request", ("read_only",), False),
        ("minibook-projection-snapshot", ("project_rows", 0, "task_rows", 1, "task_order"), 3),
        ("minibook-projection-snapshot", ("project_rows", 0, "task_rows", 1, "depends_on_task_refs"), [ref("task", "Z")]),
        ("minibook-projection-delta", ("to_cursor",), 39),
        ("minibook-projection-delta", ("events", 1, "source_revision"), 40),
        ("minibook-projection-evidence", ("snapshot_cursor",), 42),
    ],
)
def test_rejects_projection_continuity_and_order_drift(
    document: str, path: tuple[object, ...], value: object
) -> None:
    with pytest.raises(ContractValidationError):
        validate_bundle(mutate(document, path, value))


def test_rejects_cyclic_parent_or_dependency_references() -> None:
    documents = mutate(
        "minibook-projection-snapshot",
        ("project_rows", 0, "task_rows", 0, "depends_on_task_refs"),
        [ref("task", "B")],
    )
    with pytest.raises(ContractValidationError, match="cycle"):
        validate_bundle(documents)


def test_rejects_succeeded_projection_without_source_evidence_and_logs() -> None:
    documents = mutate(
        "minibook-projection-snapshot",
        ("project_rows", 0, "task_rows", 0, "source_evidence_refs"),
        [],
    )
    with pytest.raises(ContractValidationError, match="succeeded"):
        validate_bundle(documents)


def test_rejects_stale_or_incomplete_complete_claims() -> None:
    documents = mutate("minibook-projection-snapshot", ("complete",), True)
    documents["minibook-projection-evidence"]["complete"] = True
    with pytest.raises(ContractValidationError, match="complete"):
        validate_bundle(documents)


def test_rejects_snapshot_project_outside_nonempty_project_filter() -> None:
    documents = with_second_project(valid_bundle())
    documents["minibook-projection-request"]["filters"]["project_refs"] = [ref("project")]
    with pytest.raises(ContractValidationError, match="selected"):
        validate_bundle(documents)


def test_rejects_snapshot_task_outside_nonempty_task_filter() -> None:
    documents = valid_bundle()
    documents["minibook-projection-request"]["filters"]["task_refs"] = [ref("task", "A")]
    with pytest.raises(ContractValidationError, match="selected"):
        validate_bundle(documents)


def test_allows_partial_selected_rows_when_snapshot_is_incomplete() -> None:
    documents = with_second_project(valid_bundle())
    documents["minibook-projection-snapshot"]["project_rows"] = documents["minibook-projection-snapshot"]["project_rows"][:1]
    documents["minibook-projection-evidence"]["row_counts"] = {"project_count": 1, "task_count": 2, "event_count": 2}
    validate_bundle(documents)


def test_rejects_complete_snapshot_missing_selected_project() -> None:
    documents = with_second_project(valid_bundle())
    snapshot = documents["minibook-projection-snapshot"]
    snapshot["project_rows"] = snapshot["project_rows"][:1]
    snapshot["project_rows"][0]["task_rows"][1]["complete"] = True
    snapshot["complete"] = True
    documents["minibook-projection-evidence"]["row_counts"] = {"project_count": 1, "task_count": 2, "event_count": 2}
    documents["minibook-projection-evidence"]["complete"] = True
    with pytest.raises(ContractValidationError, match="complete"):
        validate_bundle(documents)


def test_rejects_complete_snapshot_missing_selected_task() -> None:
    documents = valid_bundle()
    request = documents["minibook-projection-request"]
    snapshot = documents["minibook-projection-snapshot"]
    delta = documents["minibook-projection-delta"]
    evidence = documents["minibook-projection-evidence"]
    request["as_of_cursor"] = 40
    snapshot["snapshot_cursor"] = 40
    snapshot["project_rows"][0]["task_rows"] = snapshot["project_rows"][0]["task_rows"][:1]
    snapshot["complete"] = True
    delta["to_cursor"] = 40
    delta["events"] = delta["events"][:1]
    evidence.update({"snapshot_cursor": 40, "delta_to_cursor": 40, "row_counts": {"project_count": 1, "task_count": 1, "event_count": 1}, "complete": True})
    with pytest.raises(ContractValidationError, match="complete"):
        validate_bundle(documents)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("events", 0, "source_revision"), 39),
        (("events", 1, "source_revision"), 42),
    ],
)
def test_rejects_delta_event_revision_outside_cursor_interval(path: tuple[object, ...], value: int) -> None:
    with pytest.raises(ContractValidationError, match="cursor"):
        validate_bundle(mutate("minibook-projection-delta", path, value))


def test_rejects_delta_when_final_revision_does_not_reach_target_cursor() -> None:
    documents = valid_bundle()
    delta = documents["minibook-projection-delta"]
    delta["from_cursor"] = 38
    delta["events"][0]["source_revision"] = 39
    delta["events"][1]["source_revision"] = 40
    with pytest.raises(ContractValidationError, match="final"):
        validate_bundle(documents)


def test_rejects_delta_event_with_task_from_another_project() -> None:
    documents = with_second_project(valid_bundle())
    documents["minibook-projection-delta"]["events"][0]["project_ref"] = ref("project", "A")
    with pytest.raises(ContractValidationError, match="pair"):
        validate_bundle(documents)


@pytest.mark.parametrize(
    ("row_field", "evidence_field", "kind"),
    [
        ("source_evidence_refs", "source_evidence_refs", "evidence"),
        ("log_refs", "source_log_refs", "log"),
        ("cost_provenance_refs", "cost_provenance_refs", "evidence"),
    ],
)
def test_rejects_missing_task_row_provenance_in_evidence(
    row_field: str, evidence_field: str, kind: str
) -> None:
    documents = valid_bundle()
    documents["minibook-projection-snapshot"]["project_rows"][0]["task_rows"][0][row_field] = [ref(kind, "A")]
    with pytest.raises(ContractValidationError, match="provenance"):
        validate_bundle(documents)


@pytest.mark.parametrize(
    ("evidence_field", "kind"),
    [
        ("source_evidence_refs", "evidence"),
        ("source_log_refs", "log"),
        ("cost_provenance_refs", "evidence"),
    ],
)
def test_rejects_foreign_evidence_provenance(evidence_field: str, kind: str) -> None:
    documents = valid_bundle()
    evidence = documents["minibook-projection-evidence"]
    evidence[evidence_field].append(ref(kind, "A"))
    if evidence_field == "cost_provenance_refs":
        evidence["source_evidence_refs"].append(ref(kind, "A"))
    with pytest.raises(ContractValidationError, match="provenance"):
        validate_bundle(documents)


@pytest.mark.parametrize(
    "field",
    (
        "command", "execute", "approve", "reject", "retry", "cancel", "status_update",
        "db", "sql", "provider", "model", "credential", "runtime", "url", "prompt", "code",
        "approval_decision", "lifecycle_authority",
    ),
)
def test_rejects_runtime_mutation_and_authority_fields(field: str) -> None:
    document = valid_bundle()["minibook-projection-request"]
    document[field] = "forbidden"
    with pytest.raises(ContractValidationError):
        validate_document("minibook-projection-request", document)
