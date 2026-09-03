from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_FILES: dict[str, str] = {
    "task-brief": "task-brief-v1.schema.json",
    "task-event": "task-event-v1.schema.json",
    "evidence-ref": "evidence-ref-v1.schema.json",
    "task-handoff": "task-handoff-v1.schema.json",
    "brain-plan": "brain-plan-v1.schema.json",
    "brain-plan-lifecycle": "brain-plan-lifecycle-v1.schema.json",
    "brain-openfang-handoff": "brain-openfang-handoff-v1.schema.json",
    "channel-intent": "channel-intent-v1.schema.json",
    "channel-result": "channel-result-v1.schema.json",
    "space-execution-contract": "space-execution-contract-v1.schema.json",
    "research-request": "research-request-v1.schema.json",
    "research-plan": "research-plan-v1.schema.json",
    "research-job": "research-job-v1.schema.json",
    "source-evidence": "source-evidence-v1.schema.json",
    "citation": "citation-v1.schema.json",
    "research-result": "research-result-v1.schema.json",
    "research-idea-handoff": "research-idea-handoff-v1.schema.json",
    "schedule-request": "schedule-request-v1.schema.json",
    "schedule-definition": "schedule-definition-v1.schema.json",
    "schedule-change": "schedule-change-v1.schema.json",
    "schedule-state": "schedule-state-v1.schema.json",
    "schedule-run-evidence": "schedule-run-evidence-v1.schema.json",
    "workflow-request": "workflow-request-v1.schema.json",
    "workflow-definition-ref": "workflow-definition-ref-v1.schema.json",
    "workflow-change": "workflow-change-v1.schema.json",
    "workflow-run-request": "workflow-run-request-v1.schema.json",
    "workflow-run-state": "workflow-run-state-v1.schema.json",
    "workflow-run-evidence": "workflow-run-evidence-v1.schema.json",
    "n8n-operation-authority": "n8n-operation-authority-v1.schema.json",
    "agent-team-request": "agent-team-request-v1.schema.json",
    "agent-team-plan": "agent-team-plan-v1.schema.json",
    "agent-team-run-request": "agent-team-run-request-v1.schema.json",
    "agent-task-event": "agent-task-event-v1.schema.json",
    "agent-team-run-state": "agent-team-run-state-v1.schema.json",
    "agent-team-run-evidence": "agent-team-run-evidence-v1.schema.json",
    "agentfarm-runtime-source-provenance": "agentfarm-runtime-source-provenance-v1.schema.json",
    "agentfarm-openfang-handoff-admission": "agentfarm-openfang-handoff-admission-v1.schema.json",
    "knowledge-request": "knowledge-request-v1.schema.json",
    "knowledge-plan": "knowledge-plan-v1.schema.json",
    "knowledge-run-request": "knowledge-run-request-v1.schema.json",
    "knowledge-run-state": "knowledge-run-state-v1.schema.json",
    "knowledge-result": "knowledge-result-v1.schema.json",
    "code-job-request": "code-job-request-v1.schema.json",
    "code-job-plan": "code-job-plan-v1.schema.json",
    "code-job-run-request": "code-job-run-request-v1.schema.json",
    "code-job-run-state": "code-job-run-state-v1.schema.json",
    "code-job-result": "code-job-result-v1.schema.json",
    "video-job-request": "video-job-request-v1.schema.json",
    "video-job-plan": "video-job-plan-v1.schema.json",
    "video-job-run-request": "video-job-run-request-v1.schema.json",
    "video-job-run-state": "video-job-run-state-v1.schema.json",
    "video-job-result": "video-job-result-v1.schema.json",
    "desktop-action-request": "desktop-action-request-v1.schema.json",
    "desktop-action-plan": "desktop-action-plan-v1.schema.json",
    "desktop-action-run-request": "desktop-action-run-request-v1.schema.json",
    "desktop-action-run-state": "desktop-action-run-state-v1.schema.json",
    "desktop-action-result": "desktop-action-result-v1.schema.json",
    "minibook-projection-request": "minibook-projection-request-v1.schema.json",
    "minibook-projection-snapshot": "minibook-projection-snapshot-v1.schema.json",
    "minibook-projection-delta": "minibook-projection-delta-v1.schema.json",
    "minibook-projection-evidence": "minibook-projection-evidence-v1.schema.json",
    "mirofish-simulation-request": "mirofish-simulation-request-v1.schema.json",
    "mirofish-simulation-plan": "mirofish-simulation-plan-v1.schema.json",
    "mirofish-simulation-run-request": "mirofish-simulation-run-request-v1.schema.json",
    "mirofish-simulation-run-state": "mirofish-simulation-run-state-v1.schema.json",
    "mirofish-simulation-evidence": "mirofish-simulation-evidence-v1.schema.json",
    "mirofish-simulation-result": "mirofish-simulation-result-v1.schema.json",
    "flowzen-checkin": "flowzen-checkin-v1.schema.json",
    "flowzen-recommendation": "flowzen-recommendation-v1.schema.json",
    "flowzen-acceptance": "flowzen-acceptance-v1.schema.json",
    "flowzen-acceptance-evidence": "flowzen-acceptance-evidence-v1.schema.json",
}
ID_PATTERN = re.compile(
    r"^(?:task|event|evidence|handoff|todo|approval|plan|request|job|result|trace|quote|artifact|citation|schedule|change|run|intent|project|workflow|definition|capability|log|source|repository|base|head|branch|commit|pr|worktree|test_profile|test_summary|checkpoint|cancellation|projection|delta|ledger|authority|session|receipt|checkin|recommendation|acceptance|subject)_v1_"
    r"[0-9A-HJKMNPQRSTVWXYZ]{26}$"
)
SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "schemas"
RESEARCH_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "research" / "v1"
SCHEDULE_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "schedule" / "v1"
N8N_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "n8n" / "v1"
AGENTFARM_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "agentfarm" / "v1"
ROWBOAT_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "rowboat" / "v1"
CODING_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "coding" / "v1"
VIDEO_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "video" / "v1"
DESKTOP_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "desktop" / "v1"
MINIBOOK_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "minibook" / "v1"
MIROFISH_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "mirofish" / "v1"
FLOWZEN_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "flowzen" / "v1"
BRAIN_SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "brain" / "v1"
SPACE_IDENTITY_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "snapshots" / "space-identity-snapshot-v1.json"
)


@dataclass(frozen=True)
class SpaceIdentitySnapshotVerification:
    """A read-only comparison of the pinned identity snapshot and a registry file."""

    status: str
    registry_path: Path
    missing_from_registry: tuple[str, ...] = ()
    extra_in_registry: tuple[str, ...] = ()


class ContractValidationError(ValueError):
    """Raised when a document is not valid for a registered shared contract."""


def is_canonical_id(identifier: str) -> bool:
    """Return whether an identifier uses the V1 kind, version, and ULID grammar."""
    return ID_PATTERN.fullmatch(identifier) is not None


def load_schema(document_type: str) -> dict[str, object]:
    """Load one versioned schema by its stable document-type key."""
    try:
        filename = SCHEMA_FILES[document_type]
    except KeyError as error:
        known_types = ", ".join(sorted(SCHEMA_FILES))
        raise ContractValidationError(
            f"Unknown document type {document_type!r}; expected one of: {known_types}."
        ) from error

    if document_type in {"brain-plan-lifecycle", "brain-openfang-handoff"}:
        schema_directory = BRAIN_SCHEMA_DIRECTORY
    elif document_type.startswith("research-") or document_type in {"source-evidence", "citation"}:
        schema_directory = RESEARCH_SCHEMA_DIRECTORY
    elif document_type.startswith("schedule-"):
        schema_directory = SCHEDULE_SCHEMA_DIRECTORY
    elif document_type.startswith("workflow-") or document_type == "n8n-operation-authority":
        schema_directory = N8N_SCHEMA_DIRECTORY
    elif document_type.startswith("agent-") or document_type.startswith("agentfarm-"):
        schema_directory = AGENTFARM_SCHEMA_DIRECTORY
    elif document_type.startswith("knowledge-"):
        schema_directory = ROWBOAT_SCHEMA_DIRECTORY
    elif document_type.startswith("code-job-"):
        schema_directory = CODING_SCHEMA_DIRECTORY
    elif document_type.startswith("video-job-"):
        schema_directory = VIDEO_SCHEMA_DIRECTORY
    elif document_type.startswith("desktop-action-"):
        schema_directory = DESKTOP_SCHEMA_DIRECTORY
    elif document_type.startswith("minibook-projection-"):
        schema_directory = MINIBOOK_SCHEMA_DIRECTORY
    elif document_type.startswith("mirofish-simulation-"):
        schema_directory = MIROFISH_SCHEMA_DIRECTORY
    elif document_type.startswith("flowzen-"):
        schema_directory = FLOWZEN_SCHEMA_DIRECTORY
    else:
        schema_directory = SCHEMA_DIRECTORY
    value = json.loads((schema_directory / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractValidationError(f"Schema for {document_type!r} is not an object.")
    return value


def validate_document(document_type: str, document: Mapping[str, object]) -> None:
    """Validate a parsed JSON object offline against one V1 shared contract."""
    if document_type == "brain-plan":
        _reject_brain_plan_application_targets(document)

    schema = load_schema(document_type)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        first_error = errors[0]
        location = ".".join(str(part) for part in first_error.path) or "<root>"
        raise ContractValidationError(
            f"{document_type} is invalid at {location}: {first_error.message}"
        )

    if document_type == "brain-plan":
        _validate_brain_plan_graph(document)
    elif document_type == "brain-plan-lifecycle":
        _validate_brain_plan_lifecycle(document)
    elif document_type == "channel-result":
        _validate_channel_result(document)
    elif document_type == "research-request":
        _validate_research_request(document)
    elif document_type == "research-job":
        _validate_research_job_state_machine(document)
    elif document_type == "source-evidence":
        _validate_source_evidence(document)
    elif document_type == "research-result":
        _validate_research_result(document)
    elif document_type == "schedule-request":
        _validate_schedule_request(document)
    elif document_type == "schedule-state":
        _validate_schedule_state(document)
    elif document_type == "schedule-run-evidence":
        _validate_schedule_run_evidence(document)
    elif document_type == "workflow-request":
        _validate_workflow_request(document)
    elif document_type == "workflow-run-state":
        _validate_workflow_run_state(document)
    elif document_type == "workflow-run-evidence":
        _validate_workflow_run_evidence(document)
    elif document_type == "agent-team-request":
        _validate_agent_team_request(document)
    elif document_type == "agent-team-plan":
        _validate_agent_team_plan(document)
    elif document_type == "agent-team-run-state":
        _validate_agent_team_run_state(document)
    elif document_type in {"agent-task-event", "agent-team-run-evidence", "agent-team-run-request"}:
        _reject_forbidden_agentfarm_fields(document)
    elif document_type == "agentfarm-runtime-source-provenance":
        _reject_forbidden_agentfarm_fields(document)
    elif document_type == "agentfarm-openfang-handoff-admission":
        _reject_forbidden_agentfarm_fields(document)
    elif document_type == "knowledge-request":
        _validate_rowboat_request(document)
    elif document_type == "knowledge-plan":
        _validate_rowboat_plan(document)
    elif document_type == "knowledge-run-state":
        _validate_rowboat_run_state(document)
    elif document_type == "knowledge-result":
        _validate_rowboat_result(document)
    elif document_type == "code-job-plan":
        _validate_code_job_plan(document)
    elif document_type == "code-job-run-state":
        _validate_code_job_run_state(document)
    elif document_type == "code-job-result":
        _validate_code_job_result(document)
    elif document_type == "desktop-action-plan":
        _validate_desktop_action_plan(document)
    elif document_type == "desktop-action-request":
        _validate_desktop_action_request(document)
    elif document_type == "desktop-action-run-state":
        _validate_desktop_action_run_state(document)
    elif document_type == "desktop-action-result":
        _validate_desktop_action_result(document)
    elif document_type == "minibook-projection-request":
        _validate_minibook_projection_request(document)
    elif document_type == "minibook-projection-snapshot":
        _validate_minibook_projection_snapshot(document)
    elif document_type == "minibook-projection-delta":
        _validate_minibook_projection_delta(document)
    elif document_type == "minibook-projection-evidence":
        _validate_minibook_projection_evidence(document)
    elif document_type == "mirofish-simulation-plan":
        _validate_mirofish_simulation_plan(document)
    elif document_type == "mirofish-simulation-run-state":
        _validate_mirofish_simulation_run_state(document)
    elif document_type in {"mirofish-simulation-evidence", "mirofish-simulation-result"}:
        _validate_mirofish_terminal_document(document)

    if document_type.startswith("mirofish-simulation-"):
        _validate_mirofish_typed_references(document_type, document)
        if document_type == "mirofish-simulation-request":
            _validate_mirofish_simulation_request(document)
    elif document_type == "flowzen-checkin":
        _validate_flowzen_checkin(document)
    elif document_type == "flowzen-recommendation":
        _validate_flowzen_recommendation(document)
    elif document_type == "flowzen-acceptance-evidence":
        _validate_flowzen_acceptance_evidence(document)


def validate_minibook_projection_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact four-document Minibook V1 projection chain offline."""
    expected_types = {
        "minibook-projection-request",
        "minibook-projection-snapshot",
        "minibook-projection-delta",
        "minibook-projection-evidence",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "Minibook projection bundle must contain exactly four V1 documents."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["minibook-projection-request"]
    snapshot = documents["minibook-projection-snapshot"]
    delta = documents["minibook-projection-delta"]
    evidence = documents["minibook-projection-evidence"]
    _require_matching_minibook_fields(snapshot, request, ("request_id", "trace_id", "space_id"), "snapshot")
    _require_matching_minibook_fields(delta, snapshot, ("projection_id", "request_id", "trace_id", "space_id"), "delta")
    _require_matching_minibook_fields(evidence, snapshot, ("request_id", "projection_id"), "evidence")
    if evidence["snapshot_ref"] != snapshot["projection_id"]:
        raise ContractValidationError("Minibook evidence snapshot_ref must equal the snapshot projection_id.")
    if evidence["delta_ref"] != delta["delta_id"]:
        raise ContractValidationError("Minibook evidence delta_ref must equal the delta_id.")
    if snapshot["snapshot_cursor"] != request["as_of_cursor"]:
        raise ContractValidationError("Minibook snapshot cursor must equal the request as_of_cursor.")
    if delta["to_cursor"] != snapshot["snapshot_cursor"]:
        raise ContractValidationError("Minibook delta to_cursor must equal the snapshot cursor.")
    if evidence["snapshot_cursor"] != snapshot["snapshot_cursor"] or evidence["delta_to_cursor"] != delta["to_cursor"]:
        raise ContractValidationError("Minibook evidence cursors must equal the snapshot and delta target cursors.")
    ledger_refs = snapshot["source_ledger_refs"]
    assert isinstance(ledger_refs, list)
    if request["as_of_ref"] not in ledger_refs or delta["source_ledger_refs"] != ledger_refs:
        raise ContractValidationError("Minibook source-ledger continuity is incomplete.")

    requested_at, generated_at, delta_generated_at, evidence_generated_at = (
        request["requested_at"], snapshot["generated_at"], delta["generated_at"], evidence["generated_at"]
    )
    assert all(isinstance(value, str) for value in (requested_at, generated_at, delta_generated_at, evidence_generated_at))
    request_time = _parse_aware_timestamp(requested_at, "Minibook request requested_at")
    snapshot_time = _parse_aware_timestamp(generated_at, "Minibook snapshot generated_at")
    if snapshot_time < request_time:
        raise ContractValidationError("Minibook request must precede its snapshot.")
    if _parse_aware_timestamp(delta_generated_at, "Minibook delta generated_at") != snapshot_time:
        raise ContractValidationError("Minibook delta generated_at must equal snapshot generated_at.")
    if _parse_aware_timestamp(evidence_generated_at, "Minibook evidence generated_at") != snapshot_time:
        raise ContractValidationError("Minibook evidence generated_at must equal snapshot generated_at.")

    project_rows = snapshot["project_rows"]
    requested_projects = request["project_refs"]
    requested_tasks = request["task_refs"]
    filters = request["filters"]
    assert isinstance(project_rows, list) and isinstance(requested_projects, list) and isinstance(requested_tasks, list) and isinstance(filters, Mapping)
    filtered_projects = filters["project_refs"]
    filtered_tasks = filters["task_refs"]
    assert isinstance(filtered_projects, list) and isinstance(filtered_tasks, list)
    selected_projects = set(filtered_projects) if filtered_projects else set(requested_projects)
    selected_tasks = set(filtered_tasks) if filtered_tasks else set(requested_tasks)
    project_refs = {row["project_ref"] for row in project_rows if isinstance(row, Mapping)}
    if not project_refs.issubset(selected_projects):
        raise ContractValidationError("Minibook snapshot project rows must be selected projects.")
    task_refs = {
        task_row["task_ref"]
        for project_row in project_rows if isinstance(project_row, Mapping)
        for task_row in project_row["task_rows"] if isinstance(project_row["task_rows"], list) and isinstance(task_row, Mapping)
    }
    if not task_refs.issubset(selected_tasks):
        raise ContractValidationError("Minibook snapshot task rows must be selected tasks.")
    if snapshot["complete"] and (project_refs != selected_projects or task_refs != selected_tasks):
        raise ContractValidationError("complete Minibook snapshots must exactly cover selected projects and tasks.")
    bounds = request["bounds"]
    assert isinstance(bounds, Mapping)
    if len(project_rows) > bounds["max_projects"]:
        raise ContractValidationError("Minibook snapshot project count exceeds request bounds.")
    for project_row in project_rows:
        assert isinstance(project_row, Mapping)
        task_rows = project_row["task_rows"]
        assert isinstance(task_rows, list)
        if len(task_rows) > bounds["max_tasks_per_project"]:
            raise ContractValidationError("Minibook snapshot task count exceeds request bounds.")
    events = delta["events"]
    assert isinstance(events, list)
    if len(events) > bounds["max_events"]:
        raise ContractValidationError("Minibook delta event count exceeds request bounds.")
    project_task_refs: dict[object, set[object]] = {}
    for project_row in project_rows:
        assert isinstance(project_row, Mapping)
        task_rows = project_row["task_rows"]
        assert isinstance(task_rows, list)
        project_task_refs[project_row["project_ref"]] = {
            task_row["task_ref"] for task_row in task_rows if isinstance(task_row, Mapping)
        }
    for event in events:
        assert isinstance(event, Mapping)
        event_project, event_task = event["project_ref"], event["task_ref"]
        if event_project not in project_task_refs or event_task not in project_task_refs[event_project]:
            raise ContractValidationError("Minibook delta event project/task pair must reference one snapshot row.")

    allowed_approvals = request["approval_refs"]
    assert isinstance(allowed_approvals, list)
    for project_row in project_rows:
        assert isinstance(project_row, Mapping)
        task_rows = project_row["task_rows"]
        assert isinstance(task_rows, list)
        for task_row in task_rows:
            assert isinstance(task_row, Mapping)
            approvals = task_row["approval_refs"]
            assert isinstance(approvals, list)
            if not set(approvals).issubset(set(allowed_approvals)):
                raise ContractValidationError("Minibook approval references must remain request provenance only.")
    row_evidence_refs = {
        reference
        for project_row in project_rows if isinstance(project_row, Mapping)
        for task_row in project_row["task_rows"] if isinstance(project_row["task_rows"], list) and isinstance(task_row, Mapping)
        for reference in task_row["source_evidence_refs"] if isinstance(task_row["source_evidence_refs"], list)
    }
    row_log_refs = {
        reference
        for project_row in project_rows if isinstance(project_row, Mapping)
        for task_row in project_row["task_rows"] if isinstance(project_row["task_rows"], list) and isinstance(task_row, Mapping)
        for reference in task_row["log_refs"] if isinstance(task_row["log_refs"], list)
    }
    row_cost_refs = {
        reference
        for project_row in project_rows if isinstance(project_row, Mapping)
        for task_row in project_row["task_rows"] if isinstance(project_row["task_rows"], list) and isinstance(task_row, Mapping)
        for reference in task_row["cost_provenance_refs"] if isinstance(task_row["cost_provenance_refs"], list)
    }
    source_evidence_refs = evidence["source_evidence_refs"]
    source_log_refs = evidence["source_log_refs"]
    cost_provenance_refs = evidence["cost_provenance_refs"]
    assert isinstance(source_evidence_refs, list) and isinstance(source_log_refs, list) and isinstance(cost_provenance_refs, list)
    if row_evidence_refs != set(source_evidence_refs):
        raise ContractValidationError("Minibook evidence provenance must exactly equal task-row source evidence refs.")
    if row_log_refs != set(source_log_refs):
        raise ContractValidationError("Minibook evidence provenance must exactly equal task-row log refs.")
    if row_cost_refs != set(cost_provenance_refs):
        raise ContractValidationError("Minibook cost provenance must exactly equal task-row cost provenance refs.")
    if not set(cost_provenance_refs).issubset(set(source_evidence_refs)):
        raise ContractValidationError("Minibook cost provenance must be backed by source evidence provenance.")
    counts = evidence["row_counts"]
    assert isinstance(counts, Mapping)
    if counts["project_count"] != len(project_rows) or counts["task_count"] != len(task_refs) or counts["event_count"] != len(events):
        raise ContractValidationError("Minibook evidence row counts must equal the snapshot and delta.")
    if evidence["stale"] != snapshot["stale"] or evidence["complete"] != snapshot["complete"]:
        raise ContractValidationError("Minibook evidence stale and complete markers must equal the snapshot.")


def _require_matching_minibook_fields(
    document: Mapping[str, object], expected: Mapping[str, object], field_names: tuple[str, ...], label: str
) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(f"Minibook {label} {field_name} does not match its reference chain.")


def _validate_minibook_projection_request(document: Mapping[str, object]) -> None:
    filters = document["filters"]
    project_refs = document["project_refs"]
    task_refs = document["task_refs"]
    assert isinstance(filters, Mapping) and isinstance(project_refs, list) and isinstance(task_refs, list)
    filtered_projects = filters["project_refs"]
    filtered_tasks = filters["task_refs"]
    assert isinstance(filtered_projects, list) and isinstance(filtered_tasks, list)
    if not set(filtered_projects).issubset(set(project_refs)) or not set(filtered_tasks).issubset(set(task_refs)):
        raise ContractValidationError("Minibook projection filters must remain within the requested project and task refs.")


def _validate_minibook_projection_snapshot(document: Mapping[str, object]) -> None:
    project_rows = document["project_rows"]
    assert isinstance(project_rows, list)
    seen_projects: set[object] = set()
    task_rows_by_ref: dict[object, Mapping[str, object]] = {}
    dependency_graph: dict[object, set[object]] = {}
    all_rows_complete = True
    for project_row in project_rows:
        assert isinstance(project_row, Mapping)
        project_ref = project_row["project_ref"]
        if project_ref in seen_projects:
            raise ContractValidationError("Minibook snapshot has duplicate project rows.")
        seen_projects.add(project_ref)
        task_rows = project_row["task_rows"]
        assert isinstance(task_rows, list)
        orders: list[int] = []
        for task_row in task_rows:
            assert isinstance(task_row, Mapping)
            task_ref = task_row["task_ref"]
            if task_ref in task_rows_by_ref:
                raise ContractValidationError("Minibook snapshot has duplicate task rows.")
            task_rows_by_ref[task_ref] = task_row
            dependency_graph[task_ref] = set()
            order = task_row["task_order"]
            assert isinstance(order, int)
            orders.append(order)
            created_at, updated_at = task_row["created_at"], task_row["updated_at"]
            assert isinstance(created_at, str) and isinstance(updated_at, str)
            if _parse_aware_timestamp(updated_at, "Minibook task row updated_at") < _parse_aware_timestamp(created_at, "Minibook task row created_at"):
                raise ContractValidationError("Minibook task row updated_at cannot precede created_at.")
            source_evidence_refs, log_refs = task_row["source_evidence_refs"], task_row["log_refs"]
            assert isinstance(source_evidence_refs, list) and isinstance(log_refs, list)
            if task_row["lifecycle_status"] == "succeeded" and (not source_evidence_refs or not log_refs):
                raise ContractValidationError("succeeded Minibook projection rows require source evidence and logs.")
            if not task_row["complete"]:
                all_rows_complete = False
        if sorted(orders) != list(range(1, len(task_rows) + 1)):
            raise ContractValidationError("Minibook task order must be deterministic and contiguous per project.")
    for task_ref, task_row in task_rows_by_ref.items():
        parent = task_row["parent_task_ref"]
        dependencies = task_row["depends_on_task_refs"]
        if parent is not None and parent not in task_rows_by_ref:
            raise ContractValidationError("Minibook parent and dependency refs must be declared task rows.")
        assert isinstance(dependencies, list)
        if parent is not None:
            dependency_graph[task_ref].add(parent)
        for dependency in dependencies:
            if dependency not in task_rows_by_ref:
                raise ContractValidationError("Minibook parent and dependency refs must be declared task rows.")
            dependency_graph[task_ref].add(dependency)
    _reject_minibook_task_cycle(dependency_graph)
    if document["stale"] and document["complete"]:
        raise ContractValidationError("Stale Minibook snapshots cannot claim complete.")
    if document["complete"] and not all_rows_complete:
        raise ContractValidationError("Complete Minibook snapshots require every row to be complete.")


def _reject_minibook_task_cycle(graph: Mapping[object, set[object]]) -> None:
    visiting: set[object] = set()
    visited: set[object] = set()

    def visit(node: object) -> None:
        if node in visiting:
            raise ContractValidationError("Minibook parent and dependency graph contains a cycle.")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_minibook_projection_delta(document: Mapping[str, object]) -> None:
    from_cursor, to_cursor = document["from_cursor"], document["to_cursor"]
    assert isinstance(from_cursor, int) and isinstance(to_cursor, int)
    if to_cursor <= from_cursor:
        raise ContractValidationError("Minibook delta cursors must strictly advance.")
    events = document["events"]
    assert isinstance(events, list)
    seen_events: set[object] = set()
    previous_revision = 0
    orders: list[int] = []
    for event in events:
        assert isinstance(event, Mapping)
        event_ref, revision, order = event["event_ref"], event["source_revision"], event["event_order"]
        assert isinstance(revision, int) and isinstance(order, int)
        if event_ref in seen_events:
            raise ContractValidationError("Minibook delta source event refs must not repeat.")
        if revision <= from_cursor or revision > to_cursor:
            raise ContractValidationError("Minibook delta source event revisions must lie within the cursor interval.")
        if revision <= previous_revision:
            raise ContractValidationError("Minibook delta source event revisions must strictly increase.")
        seen_events.add(event_ref)
        previous_revision = revision
        orders.append(order)
    if sorted(orders) != list(range(1, len(events) + 1)):
        raise ContractValidationError("Minibook delta event order must be deterministic and contiguous.")
    if previous_revision != to_cursor:
        raise ContractValidationError("Minibook delta final source revision must equal the target cursor.")


def _validate_minibook_projection_evidence(document: Mapping[str, object]) -> None:
    generated_at, completed_at = document["generated_at"], document["completed_at"]
    assert isinstance(generated_at, str) and isinstance(completed_at, str)
    if _parse_aware_timestamp(completed_at, "Minibook evidence completed_at") < _parse_aware_timestamp(generated_at, "Minibook evidence generated_at"):
        raise ContractValidationError("Minibook evidence completed_at cannot precede generated_at.")
    if document["stale"] and document["complete"]:
        raise ContractValidationError("Stale Minibook evidence cannot claim complete.")


def validate_n8n_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact six-document n8n V1 chain offline and fail closed."""
    expected_types = {
        "workflow-request",
        "workflow-definition-ref",
        "workflow-change",
        "workflow-run-request",
        "workflow-run-state",
        "workflow-run-evidence",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "n8n bundle must contain exactly the six n8n V1 document types."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["workflow-request"]
    definition = documents["workflow-definition-ref"]
    change = documents["workflow-change"]
    run_request = documents["workflow-run-request"]
    state = documents["workflow-run-state"]
    evidence = documents["workflow-run-evidence"]

    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["required"]:
        raise ContractValidationError(
            "n8n execution bundle cannot run while clarification is required."
        )
    _require_matching_workflow_refs(
        definition,
        request,
        ("request_id", "task_ref", "project_ref", "trace_id"),
        "definition",
    )
    if definition["lifecycle"] != "active":
        raise ContractValidationError("n8n execution bundle requires an active definition.")
    if change["action"] != "activate":
        raise ContractValidationError("n8n execution bundle requires an activate change.")
    if change["expected_lifecycle"] not in {"draft", "inactive"}:
        raise ContractValidationError(
            "n8n execution bundle activation must expect a draft or inactive lifecycle."
        )
    _require_matching_workflow_refs(
        change, definition, ("definition_id", "workflow_id", "request_id", "trace_id"), "change"
    )
    if change["idempotency_key"] != request["idempotency_key"]:
        raise ContractValidationError("n8n change idempotency_key must match the workflow request.")
    definition_revision = definition["revision"]
    expected_revision = change["expected_revision"]
    assert isinstance(definition_revision, int)
    assert isinstance(expected_revision, int)
    if definition_revision != expected_revision + 1:
        raise ContractValidationError(
            "n8n change expected_revision must create the resulting definition revision exactly +1."
        )
    if change["approval_ref"] != definition["approval_ref"]:
        raise ContractValidationError("n8n change approval_ref must match the active definition.")

    _require_matching_workflow_refs(
        run_request,
        definition,
        ("definition_id", "workflow_id", "workflow_version", "request_id", "task_ref", "project_ref", "trace_id"),
        "run request",
    )
    if run_request["definition_revision"] != definition_revision:
        raise ContractValidationError("n8n run request definition_revision must match the definition.")
    if run_request["definition_hash"] != definition["definition_hash"]:
        raise ContractValidationError("n8n run request definition_hash must match the definition.")
    if run_request["idempotency_key"] != request["idempotency_key"]:
        raise ContractValidationError("n8n run request idempotency_key must match the workflow request.")
    run_budget = run_request["budget"]
    request_bounds = request["hard_bounds"]
    assert isinstance(run_budget, Mapping)
    assert isinstance(request_bounds, Mapping)
    for field_name in ("timeout_seconds", "max_steps", "max_retries"):
        if run_request[field_name] > request_bounds[field_name]:
            raise ContractValidationError(
                f"n8n run request {field_name} exceeds the workflow request hard bound."
            )
    if run_budget["max_cost_minor"] > request_bounds["max_cost_minor"]:
        raise ContractValidationError("n8n run request max_cost_minor exceeds the request hard bound.")
    if run_budget["currency"] != request_bounds["currency"]:
        raise ContractValidationError("n8n run request currency must match the request hard bound.")
    if run_budget["approval_ref"] != definition["approval_ref"]:
        raise ContractValidationError("n8n run request approval_ref must match the active definition.")

    run_fields = (
        "run_id", "definition_id", "workflow_id", "workflow_version", "definition_revision",
        "definition_hash", "request_id", "task_ref", "project_ref", "trace_id", "mode",
    )
    _require_matching_workflow_refs(state, run_request, run_fields, "run state")
    _require_matching_workflow_refs(evidence, run_request, run_fields, "run evidence")
    state_counters = state["counters"]
    state_budget = state["budget"]
    assert isinstance(state_counters, Mapping)
    assert isinstance(state_budget, Mapping)
    if state_counters["max_steps"] != run_request["max_steps"]:
        raise ContractValidationError("n8n run state max_steps must match the run request.")
    if state_counters["max_retries"] != run_request["max_retries"]:
        raise ContractValidationError("n8n run state max_retries must match the run request.")
    for field_name in ("max_cost_minor", "currency", "quote_ref", "approval_ref"):
        if state_budget[field_name] != run_budget[field_name]:
            raise ContractValidationError(
                f"n8n run state budget {field_name} must match the run request."
            )

    outcome = evidence["outcome"]
    if state["status"] != outcome:
        raise ContractValidationError("n8n run state status must match the terminal evidence outcome.")
    history = state["event_history"]
    assert isinstance(history, list)
    first_event = history[0]
    final_event = history[-1]
    assert isinstance(first_event, Mapping)
    assert isinstance(final_event, Mapping)
    if first_event["status"] != "queued":
        raise ContractValidationError(
            "n8n execution bundle with resolved clarification must begin queued."
        )
    first_occurred_at = first_event["occurred_at"]
    started_at = evidence["started_at"]
    assert isinstance(first_occurred_at, str)
    assert isinstance(started_at, str)
    if _parse_aware_timestamp(started_at, "Workflow run evidence started_at") < _parse_aware_timestamp(
        first_occurred_at, "Workflow run state first event"
    ):
        raise ContractValidationError(
            "n8n run evidence started_at must not precede the first state event."
        )
    final_occurred_at = final_event["occurred_at"]
    completed_at = evidence["completed_at"]
    assert isinstance(final_occurred_at, str)
    assert isinstance(completed_at, str)
    if _parse_aware_timestamp(final_occurred_at, "Workflow run state final event") != _parse_aware_timestamp(
        completed_at, "Workflow run evidence completed_at"
    ):
        raise ContractValidationError(
            "n8n run state final event must equal workflow run evidence completed_at."
        )
    state_counters = state["counters"]
    assert isinstance(state_counters, Mapping)
    executed_steps = state_counters["executed_steps"]
    assert isinstance(executed_steps, int)
    requires_running = outcome in {"succeeded", "failed", "unavailable"} or (
        outcome == "cancelled" and executed_steps > 0
    )
    if requires_running:
        if len(history) < 2:
            raise ContractValidationError("n8n terminal run evidence requires a prior running event.")
        prior_event = history[-2]
        assert isinstance(prior_event, Mapping)
        if prior_event["status"] != "running":
            raise ContractValidationError("n8n terminal run evidence requires a prior running event.")
        running_occurred_at = prior_event["occurred_at"]
        assert isinstance(running_occurred_at, str)
        if _parse_aware_timestamp(running_occurred_at, "Workflow run state running event") > _parse_aware_timestamp(
            started_at, "Workflow run evidence started_at"
        ):
            raise ContractValidationError(
                "n8n running event must not occur after workflow run evidence started_at."
            )
    for field_name in ("evidence_refs", "artifact_refs", "log_refs"):
        if state[field_name] != evidence[field_name]:
            raise ContractValidationError(
                f"n8n run state {field_name} must match terminal run evidence."
            )
    if state_counters["executed_steps"] != evidence["executed_steps"]:
        raise ContractValidationError(
            "n8n run state executed_steps must match terminal run evidence."
        )
    evidence_cost = evidence["cost"]
    assert isinstance(evidence_cost, Mapping)
    if evidence_cost["actual_cost_minor"] > run_budget["max_cost_minor"]:
        raise ContractValidationError("n8n run evidence actual cost exceeds the approved max.")
    for field_name in ("currency", "quote_ref", "approval_ref"):
        if evidence_cost[field_name] != run_budget[field_name]:
            raise ContractValidationError(
                f"n8n run evidence cost {field_name} must match the run request."
            )


def validate_n8n_operation_authority(
    authority: Mapping[str, object], workflow_run_request: Mapping[str, object]
) -> None:
    """Validate one offline authority record against its immutable run-request identity."""
    validate_document("n8n-operation-authority", authority)
    validate_document("workflow-run-request", workflow_run_request)

    identity_fields = (
        "run_id",
        "definition_id",
        "workflow_id",
        "workflow_version",
        "definition_revision",
        "definition_hash",
        "request_id",
        "task_ref",
        "project_ref",
        "trace_id",
        "mode",
        "idempotency_key",
    )
    for field_name in identity_fields:
        if authority[field_name] != workflow_run_request[field_name]:
            raise ContractValidationError(
                f"n8n operation authority {field_name} reference drift from workflow run request."
            )

    budget = workflow_run_request["budget"]
    assert isinstance(budget, Mapping)
    if authority["approval_ref"] != budget["approval_ref"]:
        raise ContractValidationError(
            "n8n operation authority approval_ref reference drift from workflow run request."
        )

    issued_at = authority["issued_at"]
    expires_at = authority["expires_at"]
    assert isinstance(issued_at, str)
    assert isinstance(expires_at, str)
    if _parse_aware_timestamp(expires_at, "n8n operation authority") <= _parse_aware_timestamp(
        issued_at, "n8n operation authority"
    ):
        raise ContractValidationError(
            "n8n operation authority expires_at must be after issued_at."
        )


def validate_agentfarm_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact six-document AgentFarm V1 contract bundle offline."""
    expected_types = {
        "agent-team-request",
        "agent-team-plan",
        "agent-team-run-request",
        "agent-task-event",
        "agent-team-run-state",
        "agent-team-run-evidence",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "AgentFarm bundle must contain exactly the six AgentFarm V1 document types."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["agent-team-request"]
    plan = documents["agent-team-plan"]
    run_request = documents["agent-team-run-request"]
    task_event = documents["agent-task-event"]
    state = documents["agent-team-run-state"]
    evidence = documents["agent-team-run-evidence"]

    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError("AgentFarm execution bundle requires resolved clarification.")
    _require_matching_agentfarm_refs(
        plan, request, ("request_id", "brain_plan_ref", "task_ref", "project_ref", "trace_id"), "plan"
    )
    _require_matching_agentfarm_refs(
        run_request, plan, ("plan_id", "plan_version", "plan_hash", "request_id", "task_ref", "project_ref", "trace_id"), "run request"
    )
    _require_matching_agentfarm_refs(
        state, run_request, ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "task_ref", "project_ref", "trace_id", "mode"), "run state"
    )
    _require_matching_agentfarm_refs(
        evidence, run_request, ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "task_ref", "project_ref", "trace_id", "mode"), "run evidence"
    )
    _require_matching_agentfarm_refs(
        task_event, run_request, ("run_id", "plan_id", "plan_version", "plan_hash"), "task event"
    )
    for field_name in ("space_id",):
        if plan[field_name] != request[field_name] or run_request[field_name] != request[field_name]:
            raise ContractValidationError(f"AgentFarm {field_name} must remain canonical across the bundle.")

    request_bounds = request["hard_bounds"]
    assert isinstance(request_bounds, Mapping)
    plan_members = plan["members"]
    plan_tasks = plan["tasks"]
    assert isinstance(plan_members, list)
    assert isinstance(plan_tasks, list)
    if len(plan_members) > request_bounds["max_team_members"]:
        raise ContractValidationError("AgentFarm plan team size exceeds request hard bound.")
    if len(plan_tasks) > request_bounds["max_steps"]:
        raise ContractValidationError("AgentFarm plan task count exceeds request hard bound.")
    if plan["max_concurrency"] > request_bounds["max_concurrency"]:
        raise ContractValidationError("AgentFarm plan concurrency exceeds request hard bound.")
    for field_name in ("timeout_seconds", "max_steps", "max_retries", "max_concurrency", "max_cost_minor"):
        if run_request[field_name] > request_bounds[field_name]:
            raise ContractValidationError(f"AgentFarm run request {field_name} exceeds request hard bound.")
    if run_request["currency"] != request_bounds["currency"]:
        raise ContractValidationError("AgentFarm run request currency must match request hard bound.")
    if run_request["max_concurrency"] > plan["max_concurrency"]:
        raise ContractValidationError("AgentFarm run request concurrency exceeds the immutable plan.")
    for field_name in ("quote_ref", "approval_ref", "idempotency_key"):
        if run_request[field_name] != request[field_name]:
            raise ContractValidationError(f"AgentFarm run request {field_name} must match the request.")

    counters = state["counters"]
    assert isinstance(counters, Mapping)
    for field_name in ("max_steps", "max_retries", "max_concurrency"):
        if counters[field_name] != run_request[field_name]:
            raise ContractValidationError(f"AgentFarm state {field_name} must match the run request.")
    for field_name in ("max_cost_minor", "currency", "quote_ref", "approval_ref"):
        if state[field_name] != run_request[field_name]:
            raise ContractValidationError(f"AgentFarm state {field_name} must match the run request.")
    if state["actual_cost_minor"] > run_request["max_cost_minor"]:
        raise ContractValidationError("AgentFarm state actual cost exceeds the approved maximum.")
    _validate_agentfarm_terminal_consistency(plan, run_request, task_event, state, evidence)


def validate_agentfarm_runtime_admission_bundle(
    documents: Mapping[str, Mapping[str, object]],
) -> None:
    """Validate one request-bound AgentFarm runtime source admission offline."""
    expected_types = {
        "agent-team-request",
        "agentfarm-runtime-source-provenance",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "AgentFarm runtime admission bundle must contain exactly the request and source provenance documents."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["agent-team-request"]
    provenance = documents["agentfarm-runtime-source-provenance"]
    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError(
            "AgentFarm runtime source admission requires resolved clarification."
        )
    for field_name in ("request_id", "space_id"):
        if provenance[field_name] != request[field_name]:
            raise ContractValidationError(
                f"AgentFarm runtime source provenance {field_name} must match the request."
            )

    repository = provenance["repository"]
    assert isinstance(repository, Mapping)
    canonical_identity = repository["canonical_identity"]
    identity_digest = repository["identity_digest"]
    assert isinstance(canonical_identity, str)
    assert isinstance(identity_digest, str)
    expected_identity_digest = (
        "sha256:"
        + hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
    )
    if identity_digest != expected_identity_digest:
        raise ContractValidationError(
            "AgentFarm repository identity_digest must bind canonical_identity."
        )

    record_digest = provenance["record_digest"]
    assert isinstance(record_digest, str)
    digest_input = dict(provenance)
    del digest_input["record_digest"]
    canonical_record = json.dumps(
        digest_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected_record_digest = (
        "sha256:" + hashlib.sha256(canonical_record).hexdigest()
    )
    if record_digest != expected_record_digest:
        raise ContractValidationError(
            "AgentFarm provenance record_digest must bind the canonical record."
        )

    captured_at = provenance["captured_at"]
    requested_at = request["requested_at"]
    resolved_at = clarification["resolved_at"]
    assert isinstance(captured_at, str)
    assert isinstance(requested_at, str)
    assert isinstance(resolved_at, str)
    requested_instant = _parse_aware_timestamp(
        requested_at, "AgentFarm request requested_at"
    )
    resolved_instant = _parse_aware_timestamp(
        resolved_at, "AgentFarm clarification resolved_at"
    )
    if resolved_instant < requested_instant:
        raise ContractValidationError(
            "AgentFarm clarification resolution cannot predate its request."
        )
    captured_instant = _parse_aware_timestamp(
        captured_at, "AgentFarm runtime source provenance captured_at"
    )
    if captured_instant < requested_instant:
        raise ContractValidationError(
            "AgentFarm runtime source provenance cannot predate its request."
        )
    if captured_instant < resolved_instant:
        raise ContractValidationError(
            "AgentFarm runtime source provenance cannot predate clarification resolution."
        )


def validate_agentfarm_openfang_handoff_bundle(
    documents: Mapping[str, object],
) -> None:
    """Validate one exact Brain-admitted AgentFarm-to-OpenFang handoff offline."""
    expected_types = {
        "agent-team-request",
        "agentfarm-runtime-source-provenance",
        "agentfarm-openfang-handoff-admission",
        "channel-intent",
        "brain-plan",
        "space-execution-contracts",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "AgentFarm OpenFang handoff bundle must contain exactly the Channel intent, Brain plan, Space execution contracts, AgentFarm request, source provenance, and handoff admission entries."
        )

    mapping_types = (
        "agent-team-request",
        "agentfarm-runtime-source-provenance",
        "agentfarm-openfang-handoff-admission",
        "channel-intent",
        "brain-plan",
    )
    if any(not isinstance(documents[name], Mapping) for name in mapping_types):
        raise ContractValidationError(
            "AgentFarm OpenFang handoff document entries must be objects."
        )
    contracts_value = documents["space-execution-contracts"]
    if not isinstance(contracts_value, list) or any(
        not isinstance(contract, Mapping) for contract in contracts_value
    ):
        raise ContractValidationError(
            "AgentFarm OpenFang handoff space-execution-contracts must be a list of objects."
        )

    request = documents["agent-team-request"]
    provenance = documents["agentfarm-runtime-source-provenance"]
    handoff = documents["agentfarm-openfang-handoff-admission"]
    channel_intent = documents["channel-intent"]
    brain_plan = documents["brain-plan"]
    assert isinstance(request, Mapping)
    assert isinstance(provenance, Mapping)
    assert isinstance(handoff, Mapping)
    assert isinstance(channel_intent, Mapping)
    assert isinstance(brain_plan, Mapping)
    space_execution_contracts = contracts_value

    validate_agentfarm_runtime_admission_bundle(
        {
            "agent-team-request": request,
            "agentfarm-runtime-source-provenance": provenance,
        }
    )
    validate_brain_plan_admission_bundle(
        channel_intent, brain_plan, space_execution_contracts
    )
    validate_document("agentfarm-openfang-handoff-admission", handoff)

    if request["brain_plan_ref"] != brain_plan["plan_id"]:
        raise ContractValidationError(
            "AgentFarm request brain_plan_ref must match the admitted Brain plan."
        )
    channel_received_at = channel_intent["received_at"]
    request_requested_at = request["requested_at"]
    assert isinstance(channel_received_at, str)
    assert isinstance(request_requested_at, str)
    if _parse_aware_timestamp(
        channel_received_at, "AgentFarm Channel intent received_at"
    ) > _parse_aware_timestamp(
        request_requested_at, "AgentFarm request requested_at"
    ):
        raise ContractValidationError(
            "AgentFarm Channel intent must precede or coincide with its request."
        )
    if channel_intent.get("requested_space_id") != "agentfarm":
        raise ContractValidationError(
            "AgentFarm OpenFang handoff requires AgentFarm as the requested Brain route."
        )
    tasks = brain_plan["tasks"]
    assert isinstance(tasks, list)
    selected_tasks = [
        task
        for task in tasks
        if isinstance(task, Mapping)
        and task["node_id"] == handoff["brain_task_node_id"]
    ]
    if len(selected_tasks) != 1:
        raise ContractValidationError(
            "AgentFarm handoff brain_task_node_id must select exactly one admitted Brain task."
        )
    selected_space_ids = selected_tasks[0]["space_ids"]
    assert isinstance(selected_space_ids, list)
    if "agentfarm" not in selected_space_ids:
        raise ContractValidationError(
            "The selected admitted Brain task must route to AgentFarm."
        )
    agentfarm_contracts = [
        contract
        for contract in space_execution_contracts
        if contract["space_id"] == "agentfarm"
    ]
    if len(agentfarm_contracts) != 1 or agentfarm_contracts[0]["executor_id"] != "executor:openfang":
        raise ContractValidationError(
            "The admitted AgentFarm Space execution contract must name OpenFang as executor."
        )
    agentfarm_contract = agentfarm_contracts[0]
    if (
        agentfarm_contract["approval_policy_ref"] != "approval-policy:openfang"
        or agentfarm_contract["cost_policy_ref"] != "cost-policy:openfang"
    ):
        raise ContractValidationError(
            "The admitted AgentFarm Space execution contract must name the OpenFang policy references."
        )

    for field_name in (
        "request_id",
        "task_ref",
        "trace_id",
        "space_id",
        "approval_ref",
        "quote_ref",
        "idempotency_key",
    ):
        if handoff[field_name] != request[field_name]:
            raise ContractValidationError(
                f"AgentFarm OpenFang handoff {field_name} must match the request."
            )
    if handoff["correlation_id"] != channel_intent["correlation_id"]:
        raise ContractValidationError(
            "AgentFarm OpenFang handoff correlation_id must match the admitted Channel intent."
        )
    if handoff["source_provenance_id"] != provenance["provenance_id"]:
        raise ContractValidationError(
            "AgentFarm OpenFang handoff source_provenance_id must match the source provenance."
        )

    issued_at = handoff["issued_at"]
    captured_at = provenance["captured_at"]
    assert isinstance(issued_at, str)
    assert isinstance(captured_at, str)
    if _parse_aware_timestamp(issued_at, "AgentFarm OpenFang handoff issued_at") < _parse_aware_timestamp(
        captured_at, "AgentFarm runtime source provenance captured_at"
    ):
        raise ContractValidationError(
            "AgentFarm OpenFang handoff cannot predate source provenance capture."
        )


def _validate_agent_team_request(document: Mapping[str, object]) -> None:
    _reject_forbidden_agentfarm_fields(document)
    clarification = document["clarification"]
    assert isinstance(clarification, Mapping)
    questions = clarification["questions"]
    assert isinstance(questions, list)
    if clarification["status"] == "required" and not questions:
        raise ContractValidationError("AgentFarm required clarification must include questions.")
    if clarification["status"] == "required" and clarification.get("resolved_at") is not None:
        raise ContractValidationError("AgentFarm required clarification cannot have resolved_at.")
    if clarification["status"] == "resolved" and questions:
        raise ContractValidationError("AgentFarm resolved clarification must not retain questions.")
    if clarification["status"] == "resolved":
        resolved_at = clarification.get("resolved_at")
        if not isinstance(resolved_at, str):
            raise ContractValidationError("AgentFarm resolved clarification requires an aware resolved_at.")
        _parse_aware_timestamp(resolved_at, "AgentFarm clarification resolved_at")


def _validate_agent_team_plan(document: Mapping[str, object]) -> None:
    _reject_forbidden_agentfarm_fields(document)
    members = document["members"]
    tasks = document["tasks"]
    assert isinstance(members, list)
    assert isinstance(tasks, list)
    member_ids: set[str] = set()
    capability_by_member: dict[str, set[str]] = {}
    total_member_concurrency = 0
    for member in members:
        assert isinstance(member, Mapping)
        member_id = member["member_id"]
        assert isinstance(member_id, str)
        if member_id in member_ids:
            raise ContractValidationError("AgentFarm plan member_id values must be unique.")
        member_ids.add(member_id)
        capabilities = member["capability_refs"]
        assert isinstance(capabilities, list)
        capability_by_member[member_id] = set(capabilities)
        member_concurrency = member["max_concurrency"]
        assert isinstance(member_concurrency, int)
        total_member_concurrency += member_concurrency
    plan_concurrency = document["max_concurrency"]
    assert isinstance(plan_concurrency, int)
    if plan_concurrency > len(members) or plan_concurrency > total_member_concurrency:
        raise ContractValidationError("AgentFarm plan concurrency must fit declared team capacity.")
    if any(member["max_concurrency"] > plan_concurrency for member in members if isinstance(member, Mapping)):
        raise ContractValidationError("AgentFarm member concurrency cannot exceed plan concurrency.")

    task_ids: set[str] = set()
    tasks_by_id: dict[str, Mapping[str, object]] = {}
    for task in tasks:
        assert isinstance(task, Mapping)
        task_id = task["task_id"]
        member_id = task["member_id"]
        capability_ref = task["capability_ref"]
        assert isinstance(task_id, str)
        assert isinstance(member_id, str)
        assert isinstance(capability_ref, str)
        if task_id in task_ids:
            raise ContractValidationError("AgentFarm plan task_id values must be unique.")
        if member_id not in member_ids:
            raise ContractValidationError("AgentFarm plan task member_id must be declared.")
        if capability_ref not in capability_by_member[member_id]:
            raise ContractValidationError("AgentFarm plan task capability_ref must belong to its member.")
        task_ids.add(task_id)
        tasks_by_id[task_id] = task
    orders: set[int] = set()
    for task_id, task in tasks_by_id.items():
        order = task["order"]
        dependencies = task["depends_on"]
        assert isinstance(order, int)
        assert isinstance(dependencies, list)
        if order in orders:
            raise ContractValidationError("AgentFarm plan task order values must be unique.")
        orders.add(order)
        for dependency in dependencies:
            if dependency not in task_ids:
                raise ContractValidationError("AgentFarm plan dependency must reference a declared task.")
            if dependency == task_id:
                raise ContractValidationError("AgentFarm plan task cannot depend on itself.")
            dependency_order = tasks_by_id[dependency]["order"]
            assert isinstance(dependency_order, int)
            if dependency_order >= order:
                raise ContractValidationError("AgentFarm plan dependencies must precede task order.")
    _assert_agentfarm_acyclic(tasks_by_id)


def _validate_agent_team_run_state(document: Mapping[str, object]) -> None:
    _reject_forbidden_agentfarm_fields(document)
    transitions = {
        "clarification_required": {"queued", "cancelled", "unavailable"},
        "queued": {"waiting_for_approval", "running", "cancelled", "unavailable"},
        "waiting_for_approval": {"queued", "running", "cancelled", "unavailable"},
        "running": {"succeeded", "failed", "cancelled", "unavailable"},
        "succeeded": set(), "failed": set(), "cancelled": set(), "unavailable": set(),
    }
    history = document["event_history"]
    counters = document["counters"]
    task_states = document["task_states"]
    assert isinstance(history, list)
    assert isinstance(counters, Mapping)
    assert isinstance(task_states, list)
    previous_status: str | None = None
    previous_revision = 0
    previous_time: datetime | None = None
    for event in history:
        assert isinstance(event, Mapping)
        status = event["status"]
        revision = event["revision"]
        occurred_at = event["occurred_at"]
        assert isinstance(status, str)
        assert isinstance(revision, int)
        assert isinstance(occurred_at, str)
        if revision != previous_revision + 1:
            raise ContractValidationError("AgentFarm state history revisions must be consecutive.")
        parsed_time = _parse_aware_timestamp(occurred_at, "AgentFarm state history")
        if previous_time is not None and parsed_time < previous_time:
            raise ContractValidationError("AgentFarm state history times must be monotonic.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("AgentFarm state lifecycle transition is illegal or reopens terminal state.")
        previous_status, previous_revision, previous_time = status, revision, parsed_time
    if document["status"] != previous_status or document["revision"] != previous_revision:
        raise ContractValidationError("AgentFarm state must match its latest lifecycle event.")
    if history[0]["status"] != "queued":
        raise ContractValidationError("AgentFarm execution state must start queued after clarification resolves.")
    cancellation_requested = document["cancellation_requested"]
    assert isinstance(cancellation_requested, bool)
    if (document["status"] == "cancelled") != cancellation_requested:
        raise ContractValidationError("AgentFarm cancellation request and cancelled lifecycle must be symmetric.")
    for name in ("executed_steps", "retry_count", "active_members", "completed_tasks"):
        maximum = {"executed_steps": "max_steps", "retry_count": "max_retries", "active_members": "max_concurrency", "completed_tasks": "total_tasks"}[name]
        if counters[name] > counters[maximum]:
            raise ContractValidationError(f"AgentFarm state {name} exceeds {maximum}.")
    task_ids: set[str] = set()
    for task_state in task_states:
        assert isinstance(task_state, Mapping)
        task_id = task_state["task_id"]
        assert isinstance(task_id, str)
        if task_id in task_ids:
            raise ContractValidationError("AgentFarm state task_states must be unique.")
        task_ids.add(task_id)
    if len(task_states) != counters["total_tasks"]:
        raise ContractValidationError("AgentFarm state total_tasks must match task_states.")
    terminal_task_statuses = {"succeeded", "failed", "cancelled", "unavailable"}
    completed_tasks = sum(
        1
        for task_state in task_states
        if isinstance(task_state, Mapping) and task_state["status"] in terminal_task_statuses
    )
    if counters["completed_tasks"] != completed_tasks:
        raise ContractValidationError("AgentFarm completed_tasks must equal terminal task states.")
    if document["status"] in terminal_task_statuses and counters["active_members"] != 0:
        raise ContractValidationError("AgentFarm terminal team state cannot retain active members.")


def _validate_agentfarm_terminal_consistency(
    plan: Mapping[str, object], run_request: Mapping[str, object], task_event: Mapping[str, object], state: Mapping[str, object], evidence: Mapping[str, object]
) -> None:
    state_history = state["event_history"]
    state_tasks = state["task_states"]
    plan_tasks = plan["tasks"]
    assert isinstance(state_history, list)
    assert isinstance(state_tasks, list)
    assert isinstance(plan_tasks, list)
    first_event = state_history[0]
    final_event = state_history[-1]
    penultimate_event = state_history[-2] if len(state_history) > 1 else None
    assert isinstance(first_event, Mapping)
    assert isinstance(final_event, Mapping)
    if evidence["outcome"] != state["status"]:
        raise ContractValidationError("AgentFarm evidence outcome must match terminal run state.")
    final_occurred_at = final_event["occurred_at"]
    started_at = evidence["started_at"]
    completed_at = evidence["completed_at"]
    first_occurred_at = first_event["occurred_at"]
    assert isinstance(final_occurred_at, str)
    assert isinstance(first_occurred_at, str)
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    terminal_at = _parse_aware_timestamp(final_occurred_at, "AgentFarm terminal state")
    lifecycle_start = _parse_aware_timestamp(first_occurred_at, "AgentFarm lifecycle start")
    evidence_start = _parse_aware_timestamp(started_at, "AgentFarm evidence start")
    evidence_completion = _parse_aware_timestamp(completed_at, "AgentFarm evidence completion")
    if terminal_at != evidence_completion:
        raise ContractValidationError("AgentFarm evidence completion must equal terminal state time.")
    if not lifecycle_start <= evidence_start <= terminal_at:
        raise ContractValidationError("AgentFarm evidence must remain inside the terminal lifecycle window.")
    if not isinstance(penultimate_event, Mapping) or penultimate_event["status"] != "running":
        raise ContractValidationError("AgentFarm terminal evidence requires a penultimate running lifecycle event.")
    running_occurred_at = penultimate_event["occurred_at"]
    assert isinstance(running_occurred_at, str)
    running_at = _parse_aware_timestamp(running_occurred_at, "AgentFarm running lifecycle event")
    if running_at > evidence_start:
        raise ContractValidationError(
            "AgentFarm running lifecycle event must not occur after evidence start."
        )
    for field_name in ("evidence_refs", "artifact_refs", "log_refs", "actual_cost_minor", "currency", "quote_ref", "approval_ref"):
        if evidence[field_name] != state[field_name]:
            raise ContractValidationError(f"AgentFarm evidence {field_name} must match terminal state.")
    if evidence["executed_steps"] != state["counters"]["executed_steps"]:
        raise ContractValidationError("AgentFarm evidence executed_steps must match terminal state.")
    if evidence["actual_cost_minor"] > run_request["max_cost_minor"]:
        raise ContractValidationError("AgentFarm evidence actual cost exceeds approved maximum.")

    declared_tasks = {task["task_id"]: task for task in plan_tasks if isinstance(task, Mapping)}
    declared_members = {member["member_id"] for member in plan["members"] if isinstance(member, Mapping)}
    state_by_task = {task["task_id"]: task["status"] for task in state_tasks if isinstance(task, Mapping)}
    if set(state_by_task) != set(declared_tasks):
        raise ContractValidationError("AgentFarm state must account for every declared task exactly once.")
    event_task_id = task_event["task_id"]
    event_member_id = task_event["member_id"]
    assert isinstance(event_task_id, str)
    assert isinstance(event_member_id, str)
    if event_task_id not in declared_tasks or event_member_id not in declared_members:
        raise ContractValidationError("AgentFarm task event must reference declared task and member.")
    if declared_tasks[event_task_id]["member_id"] != event_member_id:
        raise ContractValidationError("AgentFarm task event member must own its declared task.")
    if task_event["dependency_refs"] != declared_tasks[event_task_id]["depends_on"]:
        raise ContractValidationError("AgentFarm task event dependencies must match the immutable plan.")
    if task_event["status"] != state_by_task[event_task_id]:
        raise ContractValidationError("AgentFarm task event status must match terminal task state.")
    if task_event["revision"] > state["revision"]:
        raise ContractValidationError("AgentFarm task event revision cannot exceed run state revision.")
    event_status = task_event["status"]
    if event_status in {"running", "succeeded"}:
        dependencies = task_event["dependency_refs"]
        assert isinstance(dependencies, list)
        if any(state_by_task[dependency] != "succeeded" for dependency in dependencies):
            raise ContractValidationError("AgentFarm running or succeeded task event requires succeeded dependencies.")
    event_occurred_at = task_event["occurred_at"]
    assert isinstance(event_occurred_at, str)
    if event_status != "queued":
        event_time = _parse_aware_timestamp(event_occurred_at, "AgentFarm task event")
        if not evidence_start <= event_time <= evidence_completion:
            raise ContractValidationError("AgentFarm non-queued task event must stay inside the execution window.")
    state_counters = state["counters"]
    assert isinstance(state_counters, Mapping)
    for field_name, request_limit, state_limit in (
        ("executed_steps", "max_steps", state_counters["executed_steps"]),
        ("retry_count", "max_retries", state_counters["retry_count"]),
        ("actual_cost_minor", "max_cost_minor", state["actual_cost_minor"]),
    ):
        if task_event[field_name] > run_request[request_limit] or task_event[field_name] > state_limit:
            raise ContractValidationError(f"AgentFarm task event {field_name} exceeds run or state bounds.")
    for field_name in ("evidence_refs", "artifact_refs", "log_refs"):
        event_refs = task_event[field_name]
        state_refs = state[field_name]
        evidence_refs = evidence[field_name]
        assert isinstance(event_refs, list)
        assert isinstance(state_refs, list)
        assert isinstance(evidence_refs, list)
        if not set(event_refs).issubset(state_refs) or not set(event_refs).issubset(evidence_refs):
            raise ContractValidationError(f"AgentFarm task event {field_name} must be terminal evidence subsets.")

    task_summaries = evidence["task_summaries"]
    member_summaries = evidence["member_summaries"]
    assert isinstance(task_summaries, list)
    assert isinstance(member_summaries, list)
    evidence_task_states = {summary["task_id"]: summary["status"] for summary in task_summaries if isinstance(summary, Mapping)}
    evidence_member_states = {summary["member_id"]: summary["status"] for summary in member_summaries if isinstance(summary, Mapping)}
    if len(evidence_task_states) != len(task_summaries) or len(evidence_member_states) != len(member_summaries):
        raise ContractValidationError("AgentFarm terminal evidence summaries must not duplicate identities.")
    if evidence_task_states != state_by_task or set(evidence_member_states) != declared_members:
        raise ContractValidationError("AgentFarm terminal evidence summaries must exactly match declared state.")
    expected_member_states = _derive_agentfarm_member_states(plan, state_by_task)
    if evidence_member_states != expected_member_states:
        raise ContractValidationError("AgentFarm member summaries must match owned task-state outcomes.")
    if evidence["outcome"] == "succeeded":
        required_tasks = {task_id for task_id, task in declared_tasks.items() if task["required"]}
        if any(state_by_task[task_id] != "succeeded" for task_id in required_tasks):
            raise ContractValidationError("AgentFarm success requires every required task to succeed.")
        if not all(evidence[field_name] for field_name in ("evidence_refs", "artifact_refs", "log_refs")):
            raise ContractValidationError("AgentFarm success requires evidence, artifacts, and logs.")


def _require_matching_agentfarm_refs(
    candidate: Mapping[str, object], source: Mapping[str, object], fields: tuple[str, ...], label: str
) -> None:
    for field_name in fields:
        if candidate[field_name] != source[field_name]:
            raise ContractValidationError(f"AgentFarm {label} {field_name} must match its source contract.")


def _derive_agentfarm_member_states(
    plan: Mapping[str, object], state_by_task: Mapping[object, object]
) -> dict[object, str]:
    precedence = {"succeeded": 0, "cancelled": 1, "unavailable": 2, "failed": 3}
    members = plan["members"]
    tasks = plan["tasks"]
    assert isinstance(members, list)
    assert isinstance(tasks, list)
    result: dict[object, str] = {}
    for member in members:
        assert isinstance(member, Mapping)
        member_id = member["member_id"]
        owned_states = [
            state_by_task[task["task_id"]]
            for task in tasks
            if isinstance(task, Mapping) and task["member_id"] == member_id
        ]
        if not owned_states:
            result[member_id] = "succeeded"
            continue
        if any(not isinstance(status, str) or status not in precedence for status in owned_states):
            raise ContractValidationError("AgentFarm terminal evidence requires terminal task states.")
        result[member_id] = max(owned_states, key=lambda status: precedence[status])
    return result


def _assert_agentfarm_acyclic(tasks_by_id: Mapping[str, Mapping[str, object]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            raise ContractValidationError("AgentFarm plan task graph must be acyclic.")
        visiting.add(task_id)
        dependencies = tasks_by_id[task_id]["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            assert isinstance(dependency, str)
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks_by_id:
        visit(task_id)


def _reject_forbidden_agentfarm_fields(value: object) -> None:
    forbidden = {
        "provider", "model", "credential", "secret", "token", "api_key", "runtime", "url", "webhook", "endpoint", "command", "shell", "db", "connection", "prompt", "code", "inline_agent",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str) and key.lower() in forbidden:
                raise ContractValidationError(f"AgentFarm contract forbids runtime or secret field {key!r}.")
            _reject_forbidden_agentfarm_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_agentfarm_fields(child)


def validate_rowboat_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact five-document Rowboat knowledge contract bundle offline."""
    expected_types = {
        "knowledge-request", "knowledge-plan", "knowledge-run-request", "knowledge-run-state", "knowledge-result",
    }
    if set(documents) != expected_types:
        raise ContractValidationError("Rowboat bundle must contain exactly the five Rowboat V1 document types.")
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["knowledge-request"]
    plan = documents["knowledge-plan"]
    run_request = documents["knowledge-run-request"]
    state = documents["knowledge-run-state"]
    result = documents["knowledge-result"]
    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError("Rowboat execution bundle requires resolved clarification.")
    resolved_at = clarification["resolved_at"]
    assert isinstance(resolved_at, str)
    _require_matching_rowboat_refs(plan, request, ("request_id", "project_ref", "task_ref", "trace_id", "space_id", "requested_output"), "plan")
    if plan["source_policy"] != request["source_policy"]:
        raise ContractValidationError("Rowboat plan source_policy must exactly match the request.")
    plan_created_at = plan["created_at"]
    requested_at = request["requested_at"]
    assert isinstance(plan_created_at, str)
    assert isinstance(requested_at, str)
    if _parse_aware_timestamp(plan_created_at, "Rowboat plan created_at") < _parse_aware_timestamp(requested_at, "Rowboat request requested_at"):
        raise ContractValidationError("Rowboat plan cannot predate its request.")
    if _parse_aware_timestamp(resolved_at, "Rowboat clarification resolved_at") > _parse_aware_timestamp(plan_created_at, "Rowboat plan created_at"):
        raise ContractValidationError("Rowboat plan cannot predate clarification resolution.")

    request_bounds = request["hard_bounds"]
    plan_sources = plan["sources"]
    plan_stages = plan["stages"]
    assert isinstance(request_bounds, Mapping)
    assert isinstance(plan_sources, list)
    assert isinstance(plan_stages, list)
    if len(plan_sources) > request_bounds["max_sources"]:
        raise ContractValidationError("Rowboat plan source count exceeds request hard bound.")
    if len(plan_stages) > request_bounds["max_steps"]:
        raise ContractValidationError("Rowboat plan stage count exceeds request hard bound.")
    if plan["required_citation_count"] > request_bounds["max_sources"]:
        raise ContractValidationError("Rowboat plan required citations exceed request source bound.")

    _require_matching_rowboat_refs(run_request, plan, ("plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "requested_output"), "run request")
    for field_name in ("quote_ref", "approval_ref", "idempotency_key"):
        if run_request[field_name] != request[field_name]:
            raise ContractValidationError(f"Rowboat run request {field_name} must match request continuity.")
    run_limits = run_request["limits"]
    assert isinstance(run_limits, Mapping)
    for field_name in ("max_sources", "max_chunks", "timeout_seconds", "max_steps", "max_retries", "max_concurrency", "max_cost_minor"):
        if run_limits[field_name] > request_bounds[field_name]:
            raise ContractValidationError(f"Rowboat run request {field_name} exceeds request hard bound.")
    if run_limits["currency"] != request_bounds["currency"]:
        raise ContractValidationError("Rowboat run request currency must match request hard bound.")

    run_fields = ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "requested_output", "mode", "quote_ref", "approval_ref", "idempotency_key")
    _require_matching_rowboat_refs(state, run_request, run_fields, "run state")
    _require_matching_rowboat_refs(result, run_request, run_fields[:11], "result")
    history = state["event_history"]
    assert isinstance(history, list)
    queued_event = history[0]
    assert isinstance(queued_event, Mapping)
    queued_at = queued_event["occurred_at"]
    assert isinstance(queued_at, str)
    if _parse_aware_timestamp(plan_created_at, "Rowboat plan created_at") > _parse_aware_timestamp(queued_at, "Rowboat queued event"):
        raise ContractValidationError("Rowboat queued lifecycle cannot predate immutable plan creation.")
    counters = state["counters"]
    assert isinstance(counters, Mapping)
    for counter_name, limit_name in (("sources_examined", "max_sources"), ("chunks_examined", "max_chunks"), ("executed_steps", "max_steps"), ("retry_count", "max_retries"), ("active_stages", "max_concurrency"), ("actual_cost_minor", "max_cost_minor")):
        if counters[counter_name] > run_limits[limit_name]:
            raise ContractValidationError(f"Rowboat state {counter_name} exceeds approved run limit.")
    if state["status"] != result["outcome"]:
        raise ContractValidationError("Rowboat terminal result outcome must match run state status.")
    result_counters = result["counters"]
    result_cost = result["cost"]
    assert isinstance(result_counters, Mapping)
    assert isinstance(result_cost, Mapping)
    if result_counters != counters:
        raise ContractValidationError("Rowboat result counters must match terminal run state.")
    if result_cost["actual_cost_minor"] != counters["actual_cost_minor"] or result_cost["actual_cost_minor"] > run_limits["max_cost_minor"]:
        raise ContractValidationError("Rowboat result cost must match state and stay within the approved maximum.")
    for field_name in ("currency", "quote_ref", "approval_ref"):
        expected = run_limits["currency"] if field_name == "currency" else run_request[field_name]
        if result_cost[field_name] != expected:
            raise ContractValidationError(f"Rowboat result cost {field_name} must match the run request.")
    _validate_rowboat_terminal_evidence(plan, run_request, state, result)


def _require_matching_rowboat_refs(candidate: Mapping[str, object], source: Mapping[str, object], fields: tuple[str, ...], label: str) -> None:
    for field_name in fields:
        if candidate[field_name] != source[field_name]:
            raise ContractValidationError(f"Rowboat {label} {field_name} must match the referenced contract.")


def _validate_rowboat_request(document: Mapping[str, object]) -> None:
    clarification = document["clarification"]
    assert isinstance(clarification, Mapping)
    questions = clarification["questions"]
    assert isinstance(questions, list)
    if clarification["status"] == "required" and not questions:
        raise ContractValidationError("Rowboat required clarification must include questions.")
    if clarification["status"] == "resolved":
        resolved_at = clarification.get("resolved_at")
        if not isinstance(resolved_at, str):
            raise ContractValidationError("Rowboat resolved clarification requires an aware resolution timestamp.")
        _parse_aware_timestamp(resolved_at, "Rowboat clarification resolved_at")


def _validate_rowboat_plan(document: Mapping[str, object]) -> None:
    sources = document["sources"]
    stages = document["stages"]
    source_policy = document["source_policy"]
    assert isinstance(sources, list)
    assert isinstance(stages, list)
    assert isinstance(source_policy, Mapping)
    allowed_kinds = source_policy["allowed_source_kinds"]
    assert isinstance(allowed_kinds, list)
    source_refs: set[str] = set()
    for source in sources:
        assert isinstance(source, Mapping)
        source_ref = source["source_ref"]
        source_kind = source["source_kind"]
        assert isinstance(source_ref, str)
        assert isinstance(source_kind, str)
        if source_ref in source_refs:
            raise ContractValidationError("Rowboat plan source_ref values must be unique.")
        if source_kind not in allowed_kinds:
            raise ContractValidationError("Rowboat plan source kind must be allowed by its source policy.")
        source_refs.add(source_ref)
    stage_by_id: dict[str, Mapping[str, object]] = {}
    stage_orders: set[int] = set()
    for stage in stages:
        assert isinstance(stage, Mapping)
        stage_id = stage["stage_id"]
        order = stage["order"]
        declared_sources = stage["source_refs"]
        assert isinstance(stage_id, str)
        assert isinstance(order, int)
        assert isinstance(declared_sources, list)
        if stage_id in stage_by_id:
            raise ContractValidationError("Rowboat plan stage_id values must be unique.")
        if order in stage_orders:
            raise ContractValidationError("Rowboat plan stage order values must be unique.")
        if any(source_ref not in source_refs for source_ref in declared_sources):
            raise ContractValidationError("Rowboat plan stage references an unknown source.")
        stage_by_id[stage_id] = stage
        stage_orders.add(order)
    if not any(stage["kind"] == "retrieve" for stage in stage_by_id.values()):
        raise ContractValidationError("Rowboat plan requires a retrieval stage.")
    if not any(stage["kind"] == "compose" for stage in stage_by_id.values()):
        raise ContractValidationError("Rowboat plan requires a composition stage.")
    for stage_id, stage in stage_by_id.items():
        dependencies = stage["depends_on"]
        order = stage["order"]
        assert isinstance(dependencies, list)
        assert isinstance(order, int)
        for dependency in dependencies:
            if dependency not in stage_by_id:
                raise ContractValidationError("Rowboat plan dependency must reference a declared stage.")
            if dependency == stage_id:
                raise ContractValidationError("Rowboat plan stage cannot depend on itself.")
            dependency_order = stage_by_id[dependency]["order"]
            assert isinstance(dependency_order, int)
            if dependency_order >= order:
                raise ContractValidationError("Rowboat plan dependencies must precede stage order.")
    _assert_rowboat_acyclic(stage_by_id)
    retrieved_source_refs: set[str] = set()
    for stage in stage_by_id.values():
        if stage["kind"] == "retrieve":
            stage_sources = stage["source_refs"]
            assert isinstance(stage_sources, list)
            if not stage_sources:
                raise ContractValidationError("Rowboat retrieval stages require at least one source reference.")
            retrieved_source_refs.update(stage_sources)
    if retrieved_source_refs != source_refs:
        raise ContractValidationError("Rowboat plan sources must each be covered by a retrieval stage.")
    for stage_id, stage in stage_by_id.items():
        if stage["kind"] == "compose" and not _rowboat_stage_reaches_retrieval(stage_id, stage_by_id):
            raise ContractValidationError("Rowboat composition stages require a transitive retrieval dependency.")


def _assert_rowboat_acyclic(stages: Mapping[str, Mapping[str, object]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visiting:
            raise ContractValidationError("Rowboat plan stage dependencies must be acyclic.")
        if stage_id in visited:
            return
        visiting.add(stage_id)
        dependencies = stages[stage_id]["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            assert isinstance(dependency, str)
            visit(dependency)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in stages:
        visit(stage_id)


def _rowboat_stage_reaches_retrieval(
    stage_id: str, stages: Mapping[str, Mapping[str, object]]
) -> bool:
    visited: set[str] = set()

    def visit(candidate_id: str) -> bool:
        if candidate_id in visited:
            return False
        visited.add(candidate_id)
        candidate = stages[candidate_id]
        if candidate["kind"] == "retrieve":
            return True
        dependencies = candidate["depends_on"]
        assert isinstance(dependencies, list)
        return any(visit(dependency) for dependency in dependencies)

    return visit(stage_id)


def _validate_rowboat_run_state(document: Mapping[str, object]) -> None:
    transitions = {
        "queued": {"waiting_for_approval", "running", "cancelled", "unavailable"},
        "waiting_for_approval": {"queued", "running", "cancelled", "unavailable"},
        "running": {"succeeded", "failed", "cancelled", "unavailable"},
        "succeeded": set(), "failed": set(), "cancelled": set(), "unavailable": set(),
    }
    history = document["event_history"]
    assert isinstance(history, list)
    previous_status: str | None = None
    previous_revision = 0
    previous_time: datetime | None = None
    for event in history:
        assert isinstance(event, Mapping)
        status = event["status"]
        revision = event["revision"]
        occurred_at = event["occurred_at"]
        assert isinstance(status, str)
        assert isinstance(revision, int)
        assert isinstance(occurred_at, str)
        if revision != previous_revision + 1:
            raise ContractValidationError("Rowboat state history revisions must be consecutive.")
        parsed_time = _parse_aware_timestamp(occurred_at, "Rowboat state history")
        if previous_time is not None and parsed_time < previous_time:
            raise ContractValidationError("Rowboat state history timestamps must be monotonic.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("Rowboat state lifecycle transition is illegal or reopens a terminal state.")
        previous_status, previous_revision, previous_time = status, revision, parsed_time
    if history[0]["status"] != "queued":
        raise ContractValidationError("Rowboat executable state must start queued.")
    if document["status"] != previous_status or document["revision"] != previous_revision:
        raise ContractValidationError("Rowboat state must match its latest lifecycle event.")
    cancellation_requested = document["cancellation_requested"]
    assert isinstance(cancellation_requested, bool)
    if (document["status"] == "cancelled") != cancellation_requested:
        raise ContractValidationError("Rowboat cancellation request and cancelled lifecycle must be symmetric.")
    if document["status"] in {"succeeded", "failed", "cancelled", "unavailable"}:
        counters = document["counters"]
        assert isinstance(counters, Mapping)
        if counters["active_stages"] != 0:
            raise ContractValidationError("Rowboat terminal state cannot retain active stages.")


def _validate_rowboat_result(document: Mapping[str, object]) -> None:
    started_at = document["started_at"]
    completed_at = document["completed_at"]
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    if _parse_aware_timestamp(completed_at, "Rowboat result completed_at") < _parse_aware_timestamp(started_at, "Rowboat result started_at"):
        raise ContractValidationError("Rowboat result cannot complete before it starts.")
    counters = document["counters"]
    assert isinstance(counters, Mapping)
    if counters["active_stages"] != 0:
        raise ContractValidationError("Rowboat terminal result cannot retain active stages.")
    sources = document["sources"]
    citations = document["citations"]
    evidence_refs = document["evidence_refs"]
    assert isinstance(sources, list)
    assert isinstance(citations, list)
    assert isinstance(evidence_refs, list)
    sources_by_ref: dict[str, Mapping[str, object]] = {}
    for source in sources:
        assert isinstance(source, Mapping)
        source_ref = source["source_ref"]
        evidence_ref = source["evidence_ref"]
        assert isinstance(source_ref, str)
        assert isinstance(evidence_ref, str)
        if source_ref in sources_by_ref:
            raise ContractValidationError("Rowboat result source identities must be unique.")
        if evidence_ref not in evidence_refs:
            raise ContractValidationError("Rowboat result source evidence must be declared in evidence_refs.")
        sources_by_ref[source_ref] = source
    citation_refs: set[str] = set()
    for citation in citations:
        assert isinstance(citation, Mapping)
        citation_ref = citation["citation_ref"]
        source_ref = citation["source_ref"]
        evidence_ref = citation["evidence_ref"]
        assert isinstance(citation_ref, str)
        assert isinstance(source_ref, str)
        assert isinstance(evidence_ref, str)
        if citation_ref in citation_refs:
            raise ContractValidationError("Rowboat result citation identities must be unique.")
        if source_ref not in sources_by_ref:
            raise ContractValidationError("Rowboat citation references an unknown result source.")
        if evidence_ref != sources_by_ref[source_ref]["evidence_ref"]:
            raise ContractValidationError("Rowboat citation evidence must match its cited source.")
        citation_refs.add(citation_ref)


def _validate_rowboat_terminal_evidence(
    plan: Mapping[str, object], run_request: Mapping[str, object], state: Mapping[str, object], result: Mapping[str, object]
) -> None:
    history = state["event_history"]
    sources = result["sources"]
    citations = result["citations"]
    artifacts = result["artifact_refs"]
    evidence_refs = result["evidence_refs"]
    log_refs = result["log_refs"]
    assert isinstance(history, list)
    assert isinstance(sources, list)
    assert isinstance(citations, list)
    assert isinstance(artifacts, list)
    assert isinstance(evidence_refs, list)
    assert isinstance(log_refs, list)
    first_event = history[0]
    final_event = history[-1]
    assert isinstance(first_event, Mapping)
    assert isinstance(final_event, Mapping)
    first_at = first_event["occurred_at"]
    final_at = final_event["occurred_at"]
    started_at = result["started_at"]
    completed_at = result["completed_at"]
    assert isinstance(first_at, str)
    assert isinstance(final_at, str)
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    lifecycle_start = _parse_aware_timestamp(first_at, "Rowboat lifecycle start")
    lifecycle_end = _parse_aware_timestamp(final_at, "Rowboat lifecycle end")
    evidence_start = _parse_aware_timestamp(started_at, "Rowboat result start")
    evidence_end = _parse_aware_timestamp(completed_at, "Rowboat result completion")
    if lifecycle_end != evidence_end:
        raise ContractValidationError("Rowboat result completion must equal terminal state timestamp.")
    if not lifecycle_start <= evidence_start <= lifecycle_end:
        raise ContractValidationError("Rowboat result must stay inside its lifecycle window.")
    run_limits = run_request["limits"]
    assert isinstance(run_limits, Mapping)
    if evidence_end - evidence_start > timedelta(seconds=run_limits["timeout_seconds"]):
        raise ContractValidationError("Rowboat result duration exceeds the approved run timeout.")
    outcome = result["outcome"]
    counters = state["counters"]
    assert isinstance(outcome, str)
    assert isinstance(counters, Mapping)
    requires_running = outcome in {"succeeded", "failed", "unavailable"} or (outcome == "cancelled" and counters["executed_steps"] > 0)
    if requires_running:
        if len(history) < 2 or history[-2]["status"] != "running":
            raise ContractValidationError("Rowboat terminal result requires a preceding running event.")
        running_at = history[-2]["occurred_at"]
        assert isinstance(running_at, str)
        if _parse_aware_timestamp(running_at, "Rowboat running event") > evidence_start:
            raise ContractValidationError("Rowboat running event cannot follow result start.")
    plan_sources = plan["sources"]
    assert isinstance(plan_sources, list)
    planned_sources = {source["source_ref"]: source["source_kind"] for source in plan_sources if isinstance(source, Mapping)}
    for source in sources:
        assert isinstance(source, Mapping)
        if source["source_ref"] not in planned_sources:
            raise ContractValidationError("Rowboat result source must be declared by the immutable plan.")
        if source["source_kind"] != planned_sources[source["source_ref"]]:
            raise ContractValidationError("Rowboat result source kind must match the immutable plan.")
    examined_sources = counters["sources_examined"]
    assert isinstance(examined_sources, int)
    if not len(sources) <= examined_sources <= len(plan_sources):
        raise ContractValidationError("Rowboat terminal sources must not exceed examined or planned sources.")
    if outcome == "succeeded":
        if not sources or not citations or not artifacts or not evidence_refs or not log_refs:
            raise ContractValidationError("Rowboat success requires sources, citations, artifacts, evidence, and logs.")
        if len(citations) < plan["required_citation_count"]:
            raise ContractValidationError("Rowboat success does not meet the plan citation requirement.")
        if plan["output_artifact_ref"] not in artifacts:
            raise ContractValidationError("Rowboat success must include the declared output artifact.")


def _validate_workflow_request(document: Mapping[str, object]) -> None:
    clarification = document["clarification"]
    assert isinstance(clarification, Mapping)
    required = clarification["required"]
    questions = clarification["questions"]
    assert isinstance(required, bool)
    assert isinstance(questions, list)
    if required != bool(questions):
        raise ContractValidationError(
            "Workflow request clarification questions must be present exactly when clarification is required."
        )


def _validate_workflow_run_state(document: Mapping[str, object]) -> None:
    transitions = {
        "clarification_required": {"queued", "cancelled", "unavailable"},
        "queued": {"waiting_for_approval", "running", "cancelled", "unavailable"},
        "waiting_for_approval": {"running", "cancelled", "unavailable"},
        "running": {"succeeded", "failed", "cancelled", "unavailable"},
        "succeeded": set(), "failed": set(), "cancelled": set(), "unavailable": set(),
    }
    history = document["event_history"]
    assert isinstance(history, list)
    first_event = history[0]
    assert isinstance(first_event, Mapping)
    first_status = first_event["status"]
    assert isinstance(first_status, str)
    if first_status not in {"queued", "clarification_required"}:
        raise ContractValidationError(
            "Workflow run state history must begin with queued or clarification_required."
        )
    previous_time: datetime | None = None
    previous_revision = 0
    previous_status: str | None = None
    for event in history:
        assert isinstance(event, Mapping)
        status = event["status"]
        occurred_at = event["occurred_at"]
        revision = event["revision"]
        assert isinstance(status, str)
        assert isinstance(occurred_at, str)
        assert isinstance(revision, int)
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError(
                f"Workflow run lifecycle transition {previous_status!r} -> {status!r} is not allowed."
            )
        if revision != previous_revision + 1:
            raise ContractValidationError("Workflow run history revisions must be consecutive.")
        occurred = _parse_aware_timestamp(occurred_at, "Workflow run state history")
        if previous_time is not None and occurred < previous_time:
            raise ContractValidationError("Workflow run history timestamps must be monotonic.")
        previous_status = status
        previous_revision = revision
        previous_time = occurred
    if document["status"] != previous_status:
        raise ContractValidationError("Workflow run state status must equal the last history event.")
    if document["revision"] != previous_revision:
        raise ContractValidationError("Workflow run state revision must equal the last history revision.")
    counters = document["counters"]
    assert isinstance(counters, Mapping)
    if counters["executed_steps"] > counters["max_steps"]:
        raise ContractValidationError("Workflow run executed_steps exceeds max_steps.")
    if counters["retry_count"] > counters["max_retries"]:
        raise ContractValidationError("Workflow run retry_count exceeds max_retries.")
    if document["status"] == "succeeded":
        if counters["executed_steps"] < 1:
            raise ContractValidationError("A succeeded workflow run requires executed_steps > 0.")
        for field_name in ("evidence_refs", "artifact_refs", "log_refs"):
            values = document[field_name]
            assert isinstance(values, list)
            if not values:
                raise ContractValidationError(
                    f"A succeeded workflow run requires {field_name}."
                )
    cancellation_requested = document["cancellation_requested"]
    assert isinstance(cancellation_requested, bool)
    if cancellation_requested != (document["status"] == "cancelled"):
        raise ContractValidationError(
            "Workflow run cancellation_requested must be true exactly for a cancelled state."
        )


def _validate_workflow_run_evidence(document: Mapping[str, object]) -> None:
    started_at = document["started_at"]
    completed_at = document["completed_at"]
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    if _parse_aware_timestamp(started_at, "Workflow run evidence") > _parse_aware_timestamp(
        completed_at, "Workflow run evidence"
    ):
        raise ContractValidationError(
            "Workflow run evidence started_at must not be after completed_at."
        )


def _require_matching_workflow_refs(
    document: Mapping[str, object],
    expected: Mapping[str, object],
    field_names: tuple[str, ...],
    document_label: str,
) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(
                f"n8n {document_label} {field_name} does not match the referenced document."
            )


def validate_schedule_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the complete Schedule V1 reference chain offline and fail closed."""
    expected_types = {
        "schedule-request",
        "schedule-definition",
        "schedule-change",
        "schedule-state",
        "schedule-run-evidence",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "Schedule bundle must contain exactly the five Schedule V1 document types."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["schedule-request"]
    definition = documents["schedule-definition"]
    change = documents["schedule-change"]
    state = documents["schedule-state"]
    run_evidence = documents["schedule-run-evidence"]

    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["required"] or definition["clarification_required"]:
        raise ContractValidationError(
            "Schedule execution bundle cannot run while clarification is required."
        )

    _require_matching_schedule_refs(
        definition,
        request,
        ("request_id", "task_brief_ref", "intent_ref", "trace_id", "timezone", "idempotency_key"),
        "definition",
    )
    if definition["clarification_required"] != clarification["required"]:
        raise ContractValidationError(
            "Schedule definition clarification_required must match the request clarification state."
        )
    request_limits = request["limits"]
    definition_limits = definition["limits"]
    retry_policy = definition["retry_policy"]
    definition_budget = definition["budget"]
    assert isinstance(request_limits, Mapping)
    assert isinstance(definition_limits, Mapping)
    assert isinstance(retry_policy, Mapping)
    assert isinstance(definition_budget, Mapping)
    if definition_limits["max_runs"] != request_limits["max_runs"]:
        raise ContractValidationError("Schedule definition max_runs must match the request hard bound.")
    if retry_policy["max_retries"] != request_limits["max_retries"]:
        raise ContractValidationError("Schedule definition max_retries must match the request hard bound.")
    for field_name in ("max_cost_minor", "currency", "quote_ref", "approval_ref"):
        if definition_budget[field_name] != request_limits[field_name]:
            raise ContractValidationError(
                f"Schedule definition budget {field_name} must match the request hard bound."
            )

    _require_matching_schedule_refs(
        change, definition, ("schedule_id", "request_id", "trace_id", "idempotency_key"), "change"
    )
    if change["action"] != "run_now":
        raise ContractValidationError(
            "Schedule execution bundle requires a declarative run_now change."
        )
    if change["approval_ref"] != definition_budget["approval_ref"]:
        raise ContractValidationError("Schedule change approval_ref must match the definition budget.")
    _require_matching_schedule_refs(
        state,
        definition,
        ("schedule_id", "request_id", "task_brief_ref", "trace_id", "revision", "idempotency_key"),
        "state",
    )
    counters = state["counters"]
    assert isinstance(counters, Mapping)
    if counters["max_runs"] != definition_limits["max_runs"]:
        raise ContractValidationError("Schedule state max_runs must match the definition.")
    if counters["max_retries"] != retry_policy["max_retries"]:
        raise ContractValidationError("Schedule state max_retries must match the definition.")
    state_revision = state["revision"]
    assert isinstance(state_revision, int)
    expected_revision = change["expected_revision"]
    assert isinstance(expected_revision, int)
    if expected_revision != state_revision - 1:
        raise ContractValidationError("Schedule change expected_revision is stale for the resulting state.")

    _require_matching_schedule_refs(
        run_evidence,
        definition,
        ("schedule_id", "request_id", "trace_id", "revision"),
        "run evidence",
    )
    attempt = run_evidence["attempt"]
    max_retries = retry_policy["max_retries"]
    run_count = counters["run_count"]
    max_runs = counters["max_runs"]
    assert isinstance(attempt, int)
    assert isinstance(max_retries, int)
    assert isinstance(run_count, int)
    assert isinstance(max_runs, int)
    if attempt > max_retries + 1:
        raise ContractValidationError("Schedule run evidence attempt exceeds the retry policy.")
    if run_count < 1 or run_count > max_runs:
        raise ContractValidationError("Schedule state counters do not include the evidenced run.")
    cost = run_evidence["cost"]
    assert isinstance(cost, Mapping)
    for field_name in ("currency", "quote_ref", "approval_ref"):
        if cost[field_name] != definition_budget[field_name]:
            raise ContractValidationError(
                f"Schedule run evidence cost {field_name} does not match the definition budget."
            )
    actual_cost = cost["actual_cost_minor"]
    max_cost = definition_budget["max_cost_minor"]
    assert isinstance(actual_cost, int)
    assert isinstance(max_cost, int)
    if actual_cost > max_cost:
        raise ContractValidationError("Schedule run evidence cost exceeds the approved definition budget.")
    outcome = run_evidence["outcome"]
    assert isinstance(outcome, str)
    history = state["status_history"]
    assert isinstance(history, list)
    if len(history) < 2:
        raise ContractValidationError(
            "Schedule execution bundle requires a running event before the outcome projection."
        )
    penultimate_event = history[-2]
    assert isinstance(penultimate_event, Mapping)
    if penultimate_event["status"] != "running":
        raise ContractValidationError(
            "Schedule execution bundle requires the penultimate state event to be running."
        )
    if outcome == "succeeded":
        expected_status = "scheduled" if run_count < max_runs else "succeeded"
    else:
        expected_status = outcome
    if state["status"] != expected_status:
        raise ContractValidationError(
            "Schedule state status does not correctly project the evidenced run outcome."
        )
    last_run_at = state["last_run_at"]
    completed_at = run_evidence["completed_at"]
    if last_run_at != completed_at:
        raise ContractValidationError(
            "Schedule state last_run_at must exactly match Schedule run evidence completed_at."
        )
    schedule = definition["schedule"]
    assert isinstance(schedule, Mapping)
    if schedule["mode"] == "one_shot":
        run_at = schedule["run_at"]
        scheduled_for = run_evidence["scheduled_for"]
        assert isinstance(run_at, str)
        assert isinstance(scheduled_for, str)
        if _parse_aware_timestamp(run_at, "Schedule definition run_at") != _parse_aware_timestamp(
            scheduled_for, "Schedule run evidence scheduled_for"
        ):
            raise ContractValidationError(
                "Schedule run evidence scheduled_for must match one_shot run_at."
            )
    elif schedule["mode"] == "interval":
        starts_at = schedule["starts_at"]
        every_seconds = schedule["every_seconds"]
        scheduled_for = run_evidence["scheduled_for"]
        assert isinstance(starts_at, str)
        assert isinstance(every_seconds, int)
        assert isinstance(scheduled_for, str)
        anchor = _parse_aware_timestamp(starts_at, "Schedule interval starts_at")
        scheduled = _parse_aware_timestamp(scheduled_for, "Schedule run evidence scheduled_for")
        offset = scheduled - anchor
        if offset < timedelta(0):
            raise ContractValidationError(
                "Schedule run evidence scheduled_for must not precede interval starts_at."
            )
        if offset % timedelta(seconds=every_seconds) != timedelta(0):
            raise ContractValidationError(
                "Schedule run evidence scheduled_for must lie on the interval grid."
            )
    if state["status"] == "scheduled":
        next_run_at = state["next_run_at"]
        assert isinstance(next_run_at, str)
        assert isinstance(last_run_at, str)
        if _parse_aware_timestamp(next_run_at, "Schedule state next_run_at") <= _parse_aware_timestamp(
            last_run_at, "Schedule state last_run_at"
        ):
            raise ContractValidationError(
                "A scheduled Schedule execution bundle requires next_run_at after last_run_at."
            )


def _validate_schedule_request(document: Mapping[str, object]) -> None:
    clarification = document["clarification"]
    assert isinstance(clarification, Mapping)
    required = clarification["required"]
    questions = clarification["questions"]
    assert isinstance(required, bool)
    assert isinstance(questions, list)
    if required != bool(questions):
        raise ContractValidationError(
            "Schedule request clarification questions must be present exactly when clarification is required."
        )


def _validate_schedule_state(document: Mapping[str, object]) -> None:
    transitions = {
        "draft": {"clarification_required", "awaiting_approval", "scheduled", "cancelled", "unavailable"},
        "clarification_required": {"awaiting_approval", "scheduled", "cancelled", "unavailable"},
        "awaiting_approval": {"scheduled", "paused", "cancelled", "unavailable"},
        "scheduled": {"paused", "running", "cancelled", "unavailable"},
        "paused": {"scheduled", "cancelled", "unavailable"},
        "running": {"scheduled", "succeeded", "failed", "cancelled", "unavailable"},
        "succeeded": set(),
        "failed": set(),
        "cancelled": set(),
        "unavailable": set(),
    }
    history = document["status_history"]
    assert isinstance(history, list)
    statuses: list[str] = []
    previous_time: datetime | None = None
    previous_revision = 0
    for record in history:
        assert isinstance(record, Mapping)
        status = record["status"]
        occurred_at = record["occurred_at"]
        revision = record["revision"]
        assert isinstance(status, str)
        assert isinstance(occurred_at, str)
        assert isinstance(revision, int)
        if statuses and status not in transitions[statuses[-1]]:
            raise ContractValidationError(
                f"Schedule state lifecycle transition {statuses[-1]!r} -> {status!r} is not allowed."
            )
        statuses.append(status)
        if revision != previous_revision + 1:
            raise ContractValidationError("Schedule state history revisions must be consecutive.")
        current_time = _parse_aware_timestamp(occurred_at, "Schedule state history")
        if previous_time is not None and current_time < previous_time:
            raise ContractValidationError("Schedule state history timestamps must be monotonic.")
        previous_time = current_time
        previous_revision = revision
    if statuses[0] != "draft":
        raise ContractValidationError("Schedule state history must begin with draft.")
    if statuses[-1] != document["status"]:
        raise ContractValidationError("Schedule state status must equal the last history event.")
    if document["revision"] != previous_revision:
        raise ContractValidationError("Schedule state revision must equal the last history revision.")
    counters = document["counters"]
    assert isinstance(counters, Mapping)
    run_count = counters["run_count"]
    max_runs = counters["max_runs"]
    retry_count = counters["retry_count"]
    max_retries = counters["max_retries"]
    assert isinstance(run_count, int)
    assert isinstance(max_runs, int)
    assert isinstance(retry_count, int)
    assert isinstance(max_retries, int)
    if run_count > max_runs:
        raise ContractValidationError("Schedule state run_count exceeds max_runs.")
    if retry_count > max_retries:
        raise ContractValidationError("Schedule state retry_count exceeds max_retries.")
    if document["status"] in {"succeeded", "failed", "unavailable"} and run_count < 1:
        raise ContractValidationError("A completed Schedule state requires at least one run.")
    if document["status"] == "succeeded" and run_count != max_runs:
        raise ContractValidationError("A succeeded Schedule state requires run_count to equal max_runs.")
    if document["status"] == "scheduled" and run_count >= max_runs:
        raise ContractValidationError("A scheduled Schedule state requires run_count below max_runs.")
    next_run_at = document["next_run_at"]
    if document["status"] == "scheduled" and next_run_at is None:
        raise ContractValidationError("A scheduled Schedule state requires a timezone-aware next_run_at.")
    if document["status"] in {"succeeded", "failed", "cancelled", "unavailable"} and next_run_at is not None:
        raise ContractValidationError("A terminal Schedule state requires next_run_at to be null.")


def _validate_schedule_run_evidence(document: Mapping[str, object]) -> None:
    scheduled_for = document["scheduled_for"]
    started_at = document["started_at"]
    completed_at = document["completed_at"]
    assert isinstance(scheduled_for, str)
    assert isinstance(started_at, str)
    assert isinstance(completed_at, str)
    scheduled = _parse_aware_timestamp(scheduled_for, "Schedule run evidence")
    started = _parse_aware_timestamp(started_at, "Schedule run evidence")
    completed = _parse_aware_timestamp(completed_at, "Schedule run evidence")
    if not scheduled <= started <= completed:
        raise ContractValidationError(
            "Schedule run evidence scheduled_for, started_at, and completed_at must be monotonic."
        )


def _parse_aware_timestamp(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractValidationError(f"{label} timestamp is not RFC3339.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractValidationError(f"{label} timestamp must be timezone-aware.")
    return parsed


def _require_matching_schedule_refs(
    document: Mapping[str, object],
    expected: Mapping[str, object],
    field_names: tuple[str, ...],
    document_label: str,
) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(
                f"Schedule {document_label} {field_name} does not match the referenced document."
            )


def validate_flowzen_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the complete Flowzen V1 read-only-to-acceptance chain offline."""
    expected_types = {
        "flowzen-checkin",
        "flowzen-recommendation",
        "flowzen-acceptance",
        "flowzen-acceptance-evidence",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "Flowzen bundle must contain exactly the four Flowzen V1 document types."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    checkin = documents["flowzen-checkin"]
    recommendation = documents["flowzen-recommendation"]
    acceptance = documents["flowzen-acceptance"]
    evidence = documents["flowzen-acceptance-evidence"]
    checkin_id = checkin["checkin_id"]
    checkin_key = checkin["idempotency_key"]
    assert isinstance(checkin_id, str) and isinstance(checkin_key, str)
    if checkin_key != f"checkin:{checkin_id}":
        raise ContractValidationError(
            "Flowzen checkin idempotency_key must be deterministic from checkin_id."
        )
    _require_matching_flowzen_refs(
        recommendation,
        checkin,
        ("checkin_id", "subject_ref", "task_brief_ref", "intent_ref", "trace_id", "expires_at"),
        "recommendation",
    )
    observed_at = checkin["observed_at"]
    generated_at = recommendation["generated_at"]
    assert isinstance(observed_at, str) and isinstance(generated_at, str)
    generated = _parse_aware_timestamp(generated_at, "Flowzen recommendation")
    if generated < _parse_aware_timestamp(observed_at, "Flowzen checkin"):
        raise ContractValidationError("Flowzen recommendation cannot precede its checkin.")
    recommendation_evidence = recommendation["evidence_refs"]
    recommendation_cost = recommendation["cost"]
    assert isinstance(recommendation_evidence, list) and isinstance(recommendation_cost, Mapping)
    if recommendation_cost["evidence_ref"] not in recommendation_evidence:
        raise ContractValidationError(
            "Flowzen recommendation cost evidence_ref must be one of its evidence_refs."
        )

    _require_matching_flowzen_refs(
        acceptance,
        recommendation,
        ("recommendation_id", "checkin_id", "subject_ref", "task_brief_ref", "intent_ref", "trace_id"),
        "acceptance",
    )
    if acceptance["expected_recommendation_status"] != recommendation["status"]:
        raise ContractValidationError(
            "Flowzen acceptance expected_recommendation_status must match the recommendation."
        )
    recommendation_id = recommendation["recommendation_id"]
    acceptance_key = acceptance["idempotency_key"]
    assert isinstance(recommendation_id, str) and isinstance(acceptance_key, str)
    if acceptance_key != f"accept:{recommendation_id}":
        raise ContractValidationError(
            "Flowzen acceptance idempotency_key must be deterministic from recommendation_id."
        )
    accepted_at = acceptance["accepted_at"]
    expires_at = recommendation["expires_at"]
    assert isinstance(accepted_at, str) and isinstance(expires_at, str)
    accepted_timestamp = _parse_aware_timestamp(accepted_at, "Flowzen acceptance")
    if accepted_timestamp < generated:
        raise ContractValidationError(
            "Flowzen acceptance accepted_at cannot precede recommendation generated_at."
        )
    if accepted_timestamp > _parse_aware_timestamp(expires_at, "Flowzen recommendation"):
        raise ContractValidationError("Flowzen acceptance cannot target an expired recommendation.")
    cost_limit = acceptance["cost_limit"]
    assert isinstance(cost_limit, Mapping)
    if cost_limit["approval_ref"] != acceptance["approval_ref"]:
        raise ContractValidationError(
            "Flowzen acceptance cost_limit approval_ref must match the explicit acceptance approval."
        )
    if cost_limit["quote_ref"] != recommendation_cost["quote_ref"]:
        raise ContractValidationError(
            "Flowzen acceptance cost_limit quote_ref must match the recommendation cost quote_ref."
        )

    _require_matching_flowzen_refs(
        evidence,
        acceptance,
        ("acceptance_id", "recommendation_id", "checkin_id", "subject_ref", "task_brief_ref", "intent_ref", "trace_id"),
        "acceptance evidence",
    )
    started_at = evidence["started_at"]
    completed_at = evidence["completed_at"]
    timeout_seconds = acceptance["timeout_seconds"]
    assert isinstance(accepted_at, str) and isinstance(started_at, str) and isinstance(completed_at, str)
    assert isinstance(timeout_seconds, int)
    accepted = accepted_timestamp
    started = _parse_aware_timestamp(started_at, "Flowzen acceptance evidence")
    completed = _parse_aware_timestamp(completed_at, "Flowzen acceptance evidence")
    if not accepted <= started <= completed:
        raise ContractValidationError(
            "Flowzen acceptance evidence timestamps must begin after acceptance and remain monotonic."
        )
    if completed - accepted > timedelta(seconds=timeout_seconds):
        raise ContractValidationError("Flowzen acceptance evidence exceeds the configured timeout.")
    evidence_cost = evidence["cost"]
    assert isinstance(evidence_cost, Mapping)
    for field_name in ("currency", "quote_ref", "approval_ref"):
        if evidence_cost[field_name] != cost_limit[field_name]:
            raise ContractValidationError(
                f"Flowzen acceptance evidence cost {field_name} does not match the acceptance cost limit."
            )
    actual_cost = evidence_cost["actual_cost_minor"]
    maximum_cost = cost_limit["max_cost_minor"]
    assert isinstance(actual_cost, int) and isinstance(maximum_cost, int)
    if actual_cost > maximum_cost:
        raise ContractValidationError("Flowzen acceptance evidence cost exceeds the approved cost limit.")
    if evidence["outcome"] == "succeeded":
        readback = evidence["readback"]
        assert isinstance(readback, Mapping)
        if readback["status"] != "accepted":
            raise ContractValidationError("Flowzen acceptance success requires accepted readback status.")
        readback_observed_at = readback["observed_at"]
        assert isinstance(readback_observed_at, str)
        if _parse_aware_timestamp(
            readback_observed_at, "Flowzen acceptance readback"
        ) != completed:
            raise ContractValidationError(
                "Flowzen acceptance success readback must be observed at completion."
            )
        if readback["evidence_ref"] != evidence_cost["evidence_ref"]:
            raise ContractValidationError(
                "Flowzen acceptance readback evidence_ref must match the acceptance evidence cost provenance."
            )


def _validate_flowzen_checkin(document: Mapping[str, object]) -> None:
    observed_at = document["observed_at"]
    expires_at = document["expires_at"]
    assert isinstance(observed_at, str) and isinstance(expires_at, str)
    if _parse_aware_timestamp(expires_at, "Flowzen checkin") <= _parse_aware_timestamp(
        observed_at, "Flowzen checkin"
    ):
        raise ContractValidationError("Flowzen checkin expires_at must be after observed_at.")


def _validate_flowzen_recommendation(document: Mapping[str, object]) -> None:
    generated_at = document["generated_at"]
    expires_at = document["expires_at"]
    assert isinstance(generated_at, str) and isinstance(expires_at, str)
    if _parse_aware_timestamp(expires_at, "Flowzen recommendation") <= _parse_aware_timestamp(
        generated_at, "Flowzen recommendation"
    ):
        raise ContractValidationError("Flowzen recommendation expires_at must be after generated_at.")


def _validate_flowzen_acceptance_evidence(document: Mapping[str, object]) -> None:
    started_at = document["started_at"]
    completed_at = document["completed_at"]
    assert isinstance(started_at, str) and isinstance(completed_at, str)
    if _parse_aware_timestamp(completed_at, "Flowzen acceptance evidence") < _parse_aware_timestamp(
        started_at, "Flowzen acceptance evidence"
    ):
        raise ContractValidationError(
            "Flowzen acceptance evidence completed_at must not precede started_at."
        )


def _require_matching_flowzen_refs(
    document: Mapping[str, object],
    expected: Mapping[str, object],
    field_names: tuple[str, ...],
    document_label: str,
) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(
                f"Flowzen {document_label} {field_name} does not match the referenced document."
            )


def validate_code_job_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact five-document Coding V1 chain offline and fail closed."""
    expected_types = {
        "code-job-request",
        "code-job-plan",
        "code-job-run-request",
        "code-job-run-state",
        "code-job-result",
    }
    if set(documents) != expected_types:
        raise ContractValidationError("Coding bundle must contain exactly five CodeJob V1 documents.")
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["code-job-request"]
    plan = documents["code-job-plan"]
    run_request = documents["code-job-run-request"]
    state = documents["code-job-run-state"]
    result = documents["code-job-result"]
    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError("CodeJob plan cannot exist before clarification resolves.")
    resolved_at = clarification["resolved_at"]
    created_at = plan["created_at"]
    requested_at = request["requested_at"]
    assert isinstance(requested_at, str) and isinstance(resolved_at, str) and isinstance(created_at, str)
    requested_instant = _parse_aware_timestamp(requested_at, "CodeJob request requested_at")
    resolved_instant = _parse_aware_timestamp(resolved_at, "CodeJob clarification resolved_at")
    created_instant = _parse_aware_timestamp(created_at, "CodeJob plan created_at")
    if resolved_instant < requested_instant or created_instant < resolved_instant:
        raise ContractValidationError("CodeJob request must precede clarification and immutable plan creation.")

    _require_matching_code_job_fields(
        plan, request,
        ("request_id", "project_ref", "task_ref", "trace_id", "space_id", "repository_ref", "base_ref", "change_kind", "requested_outputs"),
        "plan",
    )
    if plan["bounds"] != request["hard_bounds"]:
        raise ContractValidationError("CodeJob plan bounds must exactly match request hard_bounds.")
    _validate_code_job_requested_output_plan(plan)

    _require_matching_code_job_fields(
        run_request, plan,
        ("plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "repository_ref", "base_ref"),
        "run request",
    )
    _require_matching_code_job_fields(
        run_request, request, ("quote_ref", "approval_ref", "idempotency_key"), "run request"
    )
    _validate_code_job_limits(run_request["approved_limits"], request["hard_bounds"], "run request")

    _require_matching_code_job_fields(
        state, run_request,
        ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "repository_ref", "base_ref", "mode"),
        "run state",
    )
    if state["resume_from_checkpoint_ref"] != run_request.get("resume_from_checkpoint_ref"):
        raise ContractValidationError("CodeJob state resume checkpoint must match the run request.")
    _validate_code_job_counters(state["counters"], state["cost"], run_request["approved_limits"], "run state")
    _require_matching_code_job_fields(state["cost"], {"quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"]}, ("quote_ref", "approval_ref"), "run state cost")

    _require_matching_code_job_fields(
        result, state,
        ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "repository_ref", "base_ref", "mode"),
        "result",
    )
    if result["outcome"] != state["status"]:
        raise ContractValidationError("CodeJob result outcome must equal the terminal run state.")
    if state["status"] not in {"succeeded", "failed", "cancelled", "unavailable"}:
        raise ContractValidationError("CodeJob result requires a terminal run state.")
    if result["counters"] != state["counters"] or result["cost"] != state["cost"]:
        raise ContractValidationError("CodeJob result counters and cost must match the run state.")
    _validate_code_job_counters(result["counters"], result["cost"], run_request["approved_limits"], "result")
    history = state["event_history"]
    assert isinstance(history, list)
    first_event = history[0]
    assert isinstance(first_event, Mapping)
    queued_at = first_event["occurred_at"]
    assert isinstance(queued_at, str)
    if _parse_aware_timestamp(queued_at, "CodeJob queued lifecycle event") < _parse_aware_timestamp(
        created_at, "CodeJob plan created_at"
    ):
        raise ContractValidationError("CodeJob queued lifecycle event cannot precede immutable plan creation.")
    _validate_code_job_requested_output_result(plan, result)
    _validate_code_job_terminal_evidence(plan, run_request, state, result)


def _validate_code_job_plan(document: Mapping[str, object]) -> None:
    phases = document["phases"]
    capabilities = document["capabilities"]
    assert isinstance(phases, list) and isinstance(capabilities, list)
    phase_by_id: dict[str, Mapping[str, object]] = {}
    phase_order: dict[str, int] = {}
    task_by_id: dict[str, tuple[Mapping[str, object], int]] = {}
    declared_task_capabilities: set[str] = set()
    declared_test_profiles: set[str] = set()
    produced_artifact_kinds: set[str] = set()
    for phase in phases:
        assert isinstance(phase, Mapping)
        phase_id, order = phase["phase_id"], phase["order"]
        assert isinstance(phase_id, str) and isinstance(order, int)
        if phase_id in phase_by_id or order in phase_order.values():
            raise ContractValidationError("CodeJob plan phase IDs and orders must be unique.")
        phase_by_id[phase_id] = phase
        phase_order[phase_id] = order
        tasks = phase["tasks"]
        assert isinstance(tasks, list)
        seen_task_orders: set[int] = set()
        for task in tasks:
            assert isinstance(task, Mapping)
            task_id, task_order = task["task_id"], task["order"]
            assert isinstance(task_id, str) and isinstance(task_order, int)
            if task_id in task_by_id or task_order in seen_task_orders:
                raise ContractValidationError("CodeJob plan task IDs and per-phase orders must be unique.")
            seen_task_orders.add(task_order)
            task_by_id[task_id] = (task, order * 1001 + task_order)
            task_capabilities = task["capabilities"]
            test_profiles = task["test_profile_refs"]
            assert isinstance(task_capabilities, list) and isinstance(test_profiles, list)
            declared_task_capabilities.update(task_capabilities)
            declared_test_profiles.update(test_profiles)
            output_kinds = task["output_artifact_kinds"]
            assert isinstance(output_kinds, list)
            produced_artifact_kinds.update(output_kinds)
    if set(capabilities) != declared_task_capabilities:
        raise ContractValidationError("CodeJob plan capabilities must exactly equal declared task capabilities.")
    for phase_id, phase in phase_by_id.items():
        dependencies = phase["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            if dependency not in phase_by_id or phase_order[dependency] >= phase_order[phase_id]:
                raise ContractValidationError("CodeJob phase dependencies must exist and precede their phase.")
    _assert_code_job_acyclic({key: value["depends_on"] for key, value in phase_by_id.items()}, "phase")
    for task_id, (task, position) in task_by_id.items():
        dependencies = task["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            if dependency not in task_by_id or task_by_id[dependency][1] >= position:
                raise ContractValidationError("CodeJob task dependencies must exist and precede their task.")
    _assert_code_job_acyclic({key: value[0]["depends_on"] for key, value in task_by_id.items()}, "task")
    required_profiles = document["required_test_profile_refs"]
    assert isinstance(required_profiles, list)
    if not set(required_profiles).issubset(declared_test_profiles):
        raise ContractValidationError("CodeJob required test profiles must be declared by an immutable task.")
    bounds = document["bounds"]
    required_artifacts = document["required_output_artifact_kinds"]
    assert isinstance(bounds, Mapping) and isinstance(required_artifacts, list)
    if len(task_by_id) > bounds["max_steps"]:
        raise ContractValidationError("CodeJob plan declared tasks exceed its immutable max_steps bound.")
    if len(declared_test_profiles) > bounds["max_test_profiles"] or len(required_profiles) > bounds["max_test_profiles"]:
        raise ContractValidationError("CodeJob plan test profiles exceed its immutable max_test_profiles bound.")
    if len(required_artifacts) > bounds["max_artifacts"]:
        raise ContractValidationError("CodeJob plan required artifacts exceed its immutable max_artifacts bound.")
    if not set(required_artifacts).issubset(produced_artifact_kinds):
        raise ContractValidationError("CodeJob required output artifact kinds must be produced by an immutable task.")
    criteria = document["success_criteria"]
    assert isinstance(criteria, list)
    criterion_ids = [criterion["criterion_id"] for criterion in criteria if isinstance(criterion, Mapping)]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise ContractValidationError("CodeJob success criterion IDs must be unique.")


def _assert_code_job_acyclic(graph: Mapping[str, object], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ContractValidationError(f"CodeJob {label} dependencies must be acyclic.")
        if node in visited:
            return
        visiting.add(node)
        dependencies = graph[node]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            assert isinstance(dependency, str)
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_code_job_run_state(document: Mapping[str, object]) -> None:
    transitions = {
        "queued": {"waiting_for_approval", "running", "cancelled", "unavailable"},
        "waiting_for_approval": {"queued", "running", "cancelled", "unavailable"},
        "running": {"paused", "cancelled", "failed", "unavailable", "succeeded"},
        "paused": {"running", "cancelled", "unavailable"},
        "cancelled": set(), "failed": set(), "unavailable": set(), "succeeded": set(),
    }
    history = document["event_history"]
    assert isinstance(history, list)
    previous_status: str | None = None
    previous_revision = 0
    previous_time: datetime | None = None
    previous_checkpoint: object = None
    first_running_seen = False
    initial_resume_checkpoint = document["resume_from_checkpoint_ref"]
    for event in history:
        assert isinstance(event, Mapping)
        status, revision, occurred_at = event["status"], event["revision"], event["occurred_at"]
        assert isinstance(status, str) and isinstance(revision, int) and isinstance(occurred_at, str)
        timestamp = _parse_aware_timestamp(occurred_at, "CodeJob lifecycle event")
        if revision != previous_revision + 1 or (previous_time is not None and timestamp < previous_time):
            raise ContractValidationError("CodeJob lifecycle revisions and timestamps must be monotonic.")
        if previous_status is None and status != "queued":
            raise ContractValidationError("CodeJob lifecycle must start queued.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("CodeJob lifecycle transition is illegal or reopens a terminal state.")
        checkpoint = event["checkpoint_ref"]
        cancellation = event["cancellation_ref"]
        if status == "paused" and checkpoint is None:
            raise ContractValidationError("CodeJob paused lifecycle events require a checkpoint reference.")
        if status == "running":
            if not first_running_seen and initial_resume_checkpoint is not None:
                if checkpoint != initial_resume_checkpoint:
                    raise ContractValidationError("CodeJob initial resume must carry its immutable checkpoint on the first running event.")
            elif previous_status == "paused":
                if checkpoint != previous_checkpoint:
                    raise ContractValidationError("CodeJob in-run resume must carry the immediately preceding paused checkpoint.")
            elif checkpoint is not None:
                raise ContractValidationError("CodeJob checkpoints are only allowed on meaningful resume events.")
            first_running_seen = True
        elif checkpoint is not None and status != "paused":
            raise ContractValidationError("CodeJob checkpoints are only allowed on paused or resume running events.")
        if status == "cancelled" and cancellation is None:
            raise ContractValidationError("CodeJob cancellation requires a cancellation reference.")
        if status != "cancelled" and cancellation is not None:
            raise ContractValidationError("CodeJob cancellation references are only allowed on cancelled events.")
        previous_status, previous_revision, previous_time, previous_checkpoint = status, revision, timestamp, checkpoint
    if document["status"] != previous_status or document["revision"] != previous_revision:
        raise ContractValidationError("CodeJob state must equal its latest lifecycle event.")
    if (document["status"] == "cancelled") != document["cancellation_requested"]:
        raise ContractValidationError("CodeJob cancellation request and cancelled state must be symmetric.")
    counters = document["counters"]
    assert isinstance(counters, Mapping)
    if document["status"] in {"succeeded", "failed", "cancelled", "unavailable"} and counters["active_workers"] != 0:
        raise ContractValidationError("Terminal CodeJob state cannot retain active workers.")
    if document["status"] in {"failed", "unavailable"} and "error_class" not in document:
        raise ContractValidationError("Failed or unavailable CodeJob state requires a redacted error class.")
    if document["status"] == "succeeded" and "error_class" in document:
        raise ContractValidationError("Succeeded CodeJob state cannot carry an error class.")


def _validate_code_job_result(document: Mapping[str, object]) -> None:
    started_at, completed_at = document["started_at"], document["completed_at"]
    assert isinstance(started_at, str) and isinstance(completed_at, str)
    if _parse_aware_timestamp(completed_at, "CodeJob result completion") < _parse_aware_timestamp(started_at, "CodeJob result start"):
        raise ContractValidationError("CodeJob result completion cannot precede start.")
    if document["head_commit_ref"] != document["commit_ref"]:
        raise ContractValidationError("CodeJob result head must resolve to the declared commit reference.")
    if document["outcome"] in {"failed", "unavailable"} and "error_class" not in document:
        raise ContractValidationError("Failed or unavailable CodeJob result requires a redacted error class.")
    if document["outcome"] == "succeeded" and "error_class" in document:
        raise ContractValidationError("Succeeded CodeJob result cannot carry an error class.")


def _validate_code_job_limits(limits: object, bounds: object, label: str) -> None:
    assert isinstance(limits, Mapping) and isinstance(bounds, Mapping)
    for field_name in ("timeout_seconds", "max_steps", "max_retries", "max_concurrency", "max_cost_minor", "max_changed_files", "max_artifacts", "max_test_profiles"):
        if limits[field_name] > bounds[field_name]:
            raise ContractValidationError(f"CodeJob {label} {field_name} exceeds the request bound.")
    if limits["currency"] != bounds["currency"]:
        raise ContractValidationError(f"CodeJob {label} currency must match the request bound.")


def _validate_code_job_counters(counters: object, cost: object, limits: object, label: str) -> None:
    assert isinstance(counters, Mapping) and isinstance(cost, Mapping) and isinstance(limits, Mapping)
    checked = {"executed_steps": "max_steps", "retry_count": "max_retries", "active_workers": "max_concurrency", "changed_file_count": "max_changed_files", "artifact_count": "max_artifacts", "test_count": "max_test_profiles"}
    for counter, bound in checked.items():
        if counters[counter] > limits[bound]:
            raise ContractValidationError(f"CodeJob {label} {counter} exceeds its approved limit.")
    if cost["actual_cost_minor"] > limits["max_cost_minor"] or cost["currency"] != limits["currency"]:
        raise ContractValidationError(f"CodeJob {label} cost exceeds or drifts from approved limits.")


def _validate_code_job_terminal_evidence(plan: Mapping[str, object], run_request: Mapping[str, object], state: Mapping[str, object], result: Mapping[str, object]) -> None:
    history = state["event_history"]
    assert isinstance(history, list)
    first_event, final_event = history[0], history[-1]
    assert isinstance(first_event, Mapping) and isinstance(final_event, Mapping)
    started_at, completed_at = result["started_at"], result["completed_at"]
    assert isinstance(started_at, str) and isinstance(completed_at, str)
    lifecycle_start = _parse_aware_timestamp(first_event["occurred_at"], "CodeJob lifecycle start")
    lifecycle_end = _parse_aware_timestamp(final_event["occurred_at"], "CodeJob lifecycle end")
    result_start = _parse_aware_timestamp(started_at, "CodeJob result start")
    result_end = _parse_aware_timestamp(completed_at, "CodeJob result completion")
    if lifecycle_end != result_end or not lifecycle_start <= result_start <= lifecycle_end:
        raise ContractValidationError("CodeJob result timestamps must remain inside and end at the terminal lifecycle instant.")
    limits = run_request["approved_limits"]
    assert isinstance(limits, Mapping)
    if result_end - result_start > timedelta(seconds=limits["timeout_seconds"]):
        raise ContractValidationError("CodeJob result exceeds its approved timeout.")
    counters = result["counters"]
    assert isinstance(counters, Mapping)
    if counters["artifact_count"] != len(result["artifacts"]) or counters["test_count"] != len(result["test_summaries"]):
        raise ContractValidationError("CodeJob result counters must match artifacts and test summaries.")
    if counters["executed_steps"] > 0:
        if len(history) < 2 or history[-2]["status"] != "running":
            raise ContractValidationError("Worked CodeJob result requires a preceding running lifecycle event.")
        first_running = next(
            (event for event in history if isinstance(event, Mapping) and event["status"] == "running"),
            None,
        )
        assert isinstance(first_running, Mapping)
        first_running_at = first_running["occurred_at"]
        assert isinstance(first_running_at, str)
        if _parse_aware_timestamp(first_running_at, "CodeJob first running lifecycle event") != result_start:
            raise ContractValidationError("Worked CodeJob result start must equal its first running lifecycle event.")
    if result["outcome"] != "succeeded":
        return
    artifacts, evidence_refs, log_refs, tests = result["artifacts"], result["evidence_refs"], result["log_refs"], result["test_summaries"]
    assert isinstance(artifacts, list) and isinstance(evidence_refs, list) and isinstance(log_refs, list) and isinstance(tests, list)
    if not artifacts or not evidence_refs or not log_refs or not tests:
        raise ContractValidationError("Succeeded CodeJob result requires artifacts, evidence, logs, and test summaries.")
    artifact_refs = [artifact["artifact_ref"] for artifact in artifacts if isinstance(artifact, Mapping)]
    if len(artifact_refs) != len(set(artifact_refs)):
        raise ContractValidationError("CodeJob result artifact references must be unique.")
    artifact_kinds = {artifact["kind"] for artifact in artifacts if isinstance(artifact, Mapping)}
    required_artifacts = plan["required_output_artifact_kinds"]
    assert isinstance(required_artifacts, list)
    if not set(required_artifacts).issubset(artifact_kinds):
        raise ContractValidationError("Succeeded CodeJob result is missing a required immutable artifact kind.")
    profiles: set[str] = set()
    for summary in tests:
        assert isinstance(summary, Mapping)
        profile, status = summary["test_profile_ref"], summary["status"]
        assert isinstance(profile, str) and isinstance(status, str)
        if profile in profiles or status != "passed":
            raise ContractValidationError("Succeeded CodeJob required test summaries must be unique and passed.")
        profiles.add(profile)
    required_profiles = plan["required_test_profile_refs"]
    assert isinstance(required_profiles, list)
    if set(required_profiles) != profiles:
        raise ContractValidationError("Succeeded CodeJob result must pass every and only required test profile.")
    criteria = plan["success_criteria"]
    assert isinstance(criteria, list)
    expected_criteria = {criterion["criterion_id"] for criterion in criteria if isinstance(criterion, Mapping)}
    satisfied = result["satisfied_criteria_ids"]
    assert isinstance(satisfied, list)
    if set(satisfied) != expected_criteria:
        raise ContractValidationError("Succeeded CodeJob result must satisfy the immutable plan criteria exactly.")


def _validate_code_job_requested_output_plan(plan: Mapping[str, object]) -> None:
    requested_outputs = plan["requested_outputs"]
    required_artifacts = plan["required_output_artifact_kinds"]
    required_profiles = plan["required_test_profile_refs"]
    assert isinstance(requested_outputs, list)
    assert isinstance(required_artifacts, list)
    assert isinstance(required_profiles, list)
    output_artifacts = {"change_set": "change_set", "review_record": "review_record", "artifact": "artifact"}
    for requested_output, artifact_kind in output_artifacts.items():
        if requested_output in requested_outputs and artifact_kind not in required_artifacts:
            raise ContractValidationError(f"CodeJob requested output {requested_output} requires immutable artifact kind {artifact_kind}.")
    if "test_evidence" in requested_outputs and not required_profiles:
        raise ContractValidationError("CodeJob requested output test_evidence requires an immutable test profile.")


def _validate_code_job_requested_output_result(plan: Mapping[str, object], result: Mapping[str, object]) -> None:
    if result["outcome"] != "succeeded":
        return
    requested_outputs = plan["requested_outputs"]
    artifacts = result["artifacts"]
    evidence_refs = result["evidence_refs"]
    test_summaries = result["test_summaries"]
    assert isinstance(requested_outputs, list)
    assert isinstance(artifacts, list) and isinstance(evidence_refs, list) and isinstance(test_summaries, list)
    artifact_kinds = {artifact["kind"] for artifact in artifacts if isinstance(artifact, Mapping)}
    output_artifacts = {"change_set": "change_set", "review_record": "review_record", "artifact": "artifact"}
    for requested_output, artifact_kind in output_artifacts.items():
        if requested_output in requested_outputs and artifact_kind not in artifact_kinds:
            raise ContractValidationError(f"Succeeded CodeJob requested output {requested_output} is missing its artifact.")
    if "test_evidence" in requested_outputs:
        if not evidence_refs or not test_summaries:
            raise ContractValidationError("Succeeded CodeJob requested output test_evidence is missing evidence or test summaries.")
        if any(summary["status"] != "passed" for summary in test_summaries if isinstance(summary, Mapping)):
            raise ContractValidationError("Succeeded CodeJob requested output test_evidence requires passed test summaries.")


def _require_matching_code_job_fields(document: Mapping[str, object], expected: Mapping[str, object], field_names: tuple[str, ...], label: str) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(f"CodeJob {label} {field_name} does not match the referenced document.")


def _validate_mirofish_simulation_request(document: Mapping[str, object]) -> None:
    expected_key = f"mirofish:{document['request_id']}"
    if document["idempotency_key"] != expected_key:
        raise ContractValidationError("MiroFish request idempotency_key must equal mirofish:<request_id>.")


def _require_mirofish_typed_reference(value: object, kind: str, label: str) -> None:
    if not isinstance(value, str) or not is_canonical_id(value) or not value.startswith(f"{kind}_v1_"):
        raise ContractValidationError(f"MiroFish {label} must be a canonical {kind}_v1 reference.")


def _require_mirofish_typed_reference_list(value: object, kind: str, label: str) -> None:
    assert isinstance(value, list)
    for index, reference in enumerate(value):
        _require_mirofish_typed_reference(reference, kind, f"{label}[{index}]")


def _validate_mirofish_typed_references(document_type: str, document: Mapping[str, object]) -> None:
    common_references = {
        "request_id": "request",
        "project_ref": "project",
        "task_ref": "task",
        "trace_id": "trace",
    }
    for field_name, kind in common_references.items():
        _require_mirofish_typed_reference(document[field_name], kind, field_name)

    if document_type == "mirofish-simulation-request":
        _require_mirofish_typed_reference_list(document["input_artifact_refs"], "artifact", "input_artifact_refs")
        _require_mirofish_typed_reference_list(document["input_evidence_refs"], "evidence", "input_evidence_refs")
        _require_mirofish_typed_reference(document["quote_ref"], "quote", "quote_ref")
        _require_mirofish_typed_reference(document["approval_ref"], "approval", "approval_ref")
        return

    if document_type == "mirofish-simulation-plan":
        _require_mirofish_typed_reference(document["plan_id"], "plan", "plan_id")
        _require_mirofish_typed_reference_list(document["input_artifact_refs"], "artifact", "input_artifact_refs")
        _require_mirofish_typed_reference_list(document["input_evidence_refs"], "evidence", "input_evidence_refs")
        return

    _require_mirofish_typed_reference(document["run_id"], "run", "run_id")
    _require_mirofish_typed_reference(document["external_run_ref"], "session", "external_run_ref")
    _require_mirofish_typed_reference(document["plan_id"], "plan", "plan_id")

    if document_type == "mirofish-simulation-run-request":
        _require_mirofish_typed_reference_list(document["input_artifact_refs"], "artifact", "input_artifact_refs")
        _require_mirofish_typed_reference_list(document["input_evidence_refs"], "evidence", "input_evidence_refs")
        _require_mirofish_typed_reference(document["quote_ref"], "quote", "quote_ref")
        _require_mirofish_typed_reference(document["approval_ref"], "approval", "approval_ref")
        return

    if document_type == "mirofish-simulation-run-state":
        checkpoint = document["resume_from_checkpoint_ref"]
        if checkpoint is not None:
            _require_mirofish_typed_reference(checkpoint, "checkpoint", "resume_from_checkpoint_ref")
        progress = document["progress"]
        assert isinstance(progress, Mapping)
        _require_mirofish_typed_reference(progress["readback_ref"], "artifact", "progress.readback_ref")
        history = document["event_history"]
        assert isinstance(history, list)
        for index, event in enumerate(history):
            assert isinstance(event, Mapping)
            checkpoint = event["checkpoint_ref"]
            cancellation = event["cancellation_ref"]
            if checkpoint is not None:
                _require_mirofish_typed_reference(checkpoint, "checkpoint", f"event_history[{index}].checkpoint_ref")
            if cancellation is not None:
                _require_mirofish_typed_reference(cancellation, "cancellation", f"event_history[{index}].cancellation_ref")
        cost = document["cost"]
        assert isinstance(cost, Mapping)
        _require_mirofish_typed_reference(cost["quote_ref"], "quote", "cost.quote_ref")
        _require_mirofish_typed_reference(cost["approval_ref"], "approval", "cost.approval_ref")
        return

    if document_type == "mirofish-simulation-evidence":
        _require_mirofish_typed_reference(document["evidence_id"], "evidence", "evidence_id")
        receipt = document.get("external_receipt_ref")
        if receipt is not None:
            _require_mirofish_typed_reference(receipt, "receipt", "external_receipt_ref")
        for artifact_name in ("graph_artifact", "simulation_artifact", "forecast_artifact"):
            artifact = document.get(artifact_name)
            if artifact is None:
                continue
            assert isinstance(artifact, Mapping)
            _require_mirofish_typed_reference(artifact["artifact_ref"], "artifact", f"{artifact_name}.artifact_ref")
            _require_mirofish_typed_reference(artifact["provenance_ref"], "evidence", f"{artifact_name}.provenance_ref")
            _require_mirofish_typed_reference(artifact["readback_ref"], "artifact", f"{artifact_name}.readback_ref")
            _require_mirofish_typed_reference(artifact["verification_ref"], "evidence", f"{artifact_name}.verification_ref")
    elif document_type == "mirofish-simulation-result":
        _require_mirofish_typed_reference(document["result_id"], "result", "result_id")
        _require_mirofish_typed_reference(document["evidence_id"], "evidence", "evidence_id")
        receipt = document.get("external_receipt_ref")
        if receipt is not None:
            _require_mirofish_typed_reference(receipt, "receipt", "external_receipt_ref")
        for field_name in ("graph_artifact_ref", "simulation_artifact_ref", "forecast_artifact_ref"):
            value = document.get(field_name)
            if value is not None:
                _require_mirofish_typed_reference(value, "artifact", field_name)
        for field_name, kind in (("readback_refs", "artifact"), ("verification_refs", "evidence")):
            value = document.get(field_name)
            if value is not None:
                _require_mirofish_typed_reference_list(value, kind, field_name)
        cost = document["cost"]
        assert isinstance(cost, Mapping)
        _require_mirofish_typed_reference(cost["quote_ref"], "quote", "cost.quote_ref")
        _require_mirofish_typed_reference(cost["approval_ref"], "approval", "cost.approval_ref")


def validate_mirofish_simulation_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact MiroFish V1 evidence chain offline and fail closed."""
    expected_types = {
        "mirofish-simulation-request",
        "mirofish-simulation-plan",
        "mirofish-simulation-run-request",
        "mirofish-simulation-run-state",
        "mirofish-simulation-evidence",
        "mirofish-simulation-result",
    }
    if set(documents) != expected_types:
        raise ContractValidationError("MiroFish bundle must contain exactly six V1 documents.")
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["mirofish-simulation-request"]
    plan = documents["mirofish-simulation-plan"]
    run_request = documents["mirofish-simulation-run-request"]
    state = documents["mirofish-simulation-run-state"]
    evidence = documents["mirofish-simulation-evidence"]
    result = documents["mirofish-simulation-result"]

    expected_idempotency_key = f"mirofish:{request['request_id']}"
    if request["idempotency_key"] != expected_idempotency_key or run_request["idempotency_key"] != expected_idempotency_key:
        raise ContractValidationError("MiroFish request and run request must share idempotency_key mirofish:<request_id>.")

    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError("MiroFish plan cannot exist before clarification resolves.")
    requested_at = _parse_aware_timestamp(request["requested_at"], "MiroFish request requested_at")
    resolved_at = _parse_aware_timestamp(clarification["resolved_at"], "MiroFish clarification resolved_at")
    created_at = _parse_aware_timestamp(plan["created_at"], "MiroFish plan created_at")
    if resolved_at < requested_at or created_at < resolved_at:
        raise ContractValidationError("MiroFish request must precede clarification and immutable plan creation.")

    _require_matching_mirofish_fields(
        plan, request,
        ("request_id", "project_ref", "task_ref", "trace_id", "space_id", "request_hash", "requested_outputs", "input_artifact_refs", "input_evidence_refs"),
        "plan",
    )
    if plan["bounds"] != request["hard_bounds"]:
        raise ContractValidationError("MiroFish plan bounds must exactly match request hard_bounds.")
    _require_matching_mirofish_fields(
        run_request, plan,
        ("plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "request_hash", "input_artifact_refs", "input_evidence_refs"),
        "run request",
    )
    _require_matching_mirofish_fields(run_request, request, ("quote_ref", "approval_ref", "idempotency_key"), "run request")
    if run_request["approved_limits"] != request["hard_bounds"]:
        raise ContractValidationError("MiroFish run limits must exactly match immutable request bounds.")

    run_fields = (
        "run_id", "external_run_ref", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "request_hash"
    )
    _require_matching_mirofish_fields(state, run_request, run_fields, "run state")
    _require_matching_mirofish_fields(evidence, state, run_fields, "evidence")
    _require_matching_mirofish_fields(result, state, run_fields, "result")
    if result["evidence_id"] != evidence["evidence_id"]:
        raise ContractValidationError("MiroFish result evidence_id must identify the supplied evidence document.")
    if evidence["outcome"] != state["status"] or result["outcome"] != state["status"]:
        raise ContractValidationError("MiroFish evidence and result outcomes must equal the terminal run state.")
    if state["status"] not in {"succeeded", "failed", "cancelled", "timed_out", "unavailable"}:
        raise ContractValidationError("MiroFish result requires a terminal run state.")

    state_cost = state["cost"]
    evidence_cost = evidence["cost"]
    result_cost = result["cost"]
    assert isinstance(state_cost, Mapping) and isinstance(evidence_cost, Mapping) and isinstance(result_cost, Mapping)
    if state_cost != evidence_cost or state_cost != result_cost:
        raise ContractValidationError("MiroFish state, evidence, and result costs must be exact matches.")
    if state_cost["quote_ref"] != request["quote_ref"] or state_cost["approval_ref"] != request["approval_ref"]:
        raise ContractValidationError("MiroFish cost references must remain bound to the request.")
    _validate_mirofish_counters_and_cost(state["counters"], state_cost, run_request["approved_limits"], "run state")
    if result["counters"] != state["counters"]:
        raise ContractValidationError("MiroFish result counters must exactly match the queryable run state.")
    _validate_mirofish_counters_and_cost(result["counters"], result_cost, run_request["approved_limits"], "result")

    history = state["event_history"]
    assert isinstance(history, list)
    first_event, final_event = history[0], history[-1]
    assert isinstance(first_event, Mapping) and isinstance(final_event, Mapping)
    queued_at = _parse_aware_timestamp(first_event["occurred_at"], "MiroFish queued event")
    started_at = _parse_aware_timestamp(result["started_at"], "MiroFish result started_at")
    completed_at = _parse_aware_timestamp(result["completed_at"], "MiroFish result completed_at")
    evidence_started_at = _parse_aware_timestamp(evidence["started_at"], "MiroFish evidence started_at")
    evidence_completed_at = _parse_aware_timestamp(evidence["completed_at"], "MiroFish evidence completed_at")
    if queued_at < created_at or evidence_started_at != started_at or evidence_completed_at != completed_at:
        raise ContractValidationError("MiroFish temporal evidence must remain bound to immutable plan and result timestamps.")
    if _parse_aware_timestamp(final_event["occurred_at"], "MiroFish terminal event") != completed_at:
        raise ContractValidationError("MiroFish terminal state and result completion must be the same instant.")
    if completed_at - started_at > timedelta(seconds=run_request["approved_limits"]["timeout_seconds"]):
        raise ContractValidationError("MiroFish result exceeds its approved timeout.")
    running_events = [event for event in history if isinstance(event, Mapping) and event["status"] == "running"]
    if state["status"] in {"succeeded", "failed", "timed_out", "unavailable"}:
        if not running_events or _parse_aware_timestamp(running_events[0]["occurred_at"], "MiroFish running event") != started_at:
            raise ContractValidationError("Worked MiroFish terminal result requires a matching running event.")

    if result["outcome"] == "succeeded":
        _validate_mirofish_succeeded_evidence(plan, state, evidence, result)


def _validate_mirofish_simulation_plan(document: Mapping[str, object]) -> None:
    phases = document["phases"]
    bounds = document["bounds"]
    assert isinstance(phases, list) and isinstance(bounds, Mapping)
    expected = (
        ("graph_build", 1, [], "graph_artifact"),
        ("simulation", 2, ["graph_build"], "simulation_artifact"),
        ("forecast", 3, ["simulation"], "forecast_artifact"),
    )
    actual = [(phase["phase_id"], phase["order"], phase["depends_on"], phase["produced_artifact_kind"]) for phase in phases if isinstance(phase, Mapping)]
    if actual != list(expected):
        raise ContractValidationError("MiroFish plan must bind graph_build, simulation, and forecast in order.")
    if len(phases) > bounds["max_steps"]:
        raise ContractValidationError("MiroFish plan phases exceed immutable max_steps.")
    if set(document["success_criteria"]) != {"graph-artifact", "simulation-artifact", "forecast-artifact", "readback-verified", "external-receipt"}:
        raise ContractValidationError("MiroFish plan must require every external-artifact verification criterion.")


def _validate_mirofish_simulation_run_state(document: Mapping[str, object]) -> None:
    transitions = {
        "queued": {"waiting_for_approval", "running", "cancellation_requested", "cancelled", "unavailable"},
        "waiting_for_approval": {"running", "cancellation_requested", "cancelled", "unavailable"},
        "running": {"paused", "cancellation_requested", "succeeded", "failed", "timed_out", "unavailable"},
        "paused": {"running", "cancellation_requested", "cancelled", "unavailable"},
        "cancellation_requested": {"cancelled", "unavailable"},
        "cancelled": set(), "failed": set(), "timed_out": set(), "unavailable": set(), "succeeded": set(),
    }
    history = document["event_history"]
    assert isinstance(history, list)
    previous_status: str | None = None
    previous_revision = 0
    previous_time: datetime | None = None
    previous_checkpoint: object = None
    first_running_seen = False
    initial_checkpoint = document["resume_from_checkpoint_ref"]
    for event in history:
        assert isinstance(event, Mapping)
        status, revision, occurred_at = event["status"], event["revision"], event["occurred_at"]
        assert isinstance(status, str) and isinstance(revision, int) and isinstance(occurred_at, str)
        timestamp = _parse_aware_timestamp(occurred_at, "MiroFish lifecycle event")
        if revision != previous_revision + 1 or (previous_time is not None and timestamp < previous_time):
            raise ContractValidationError("MiroFish lifecycle revisions and timestamps must be monotonic.")
        if previous_status is None and status != "queued":
            raise ContractValidationError("MiroFish lifecycle must start queued.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("MiroFish lifecycle transition is illegal or reopens a terminal state.")
        checkpoint, cancellation = event["checkpoint_ref"], event["cancellation_ref"]
        if status == "paused" and checkpoint is None:
            raise ContractValidationError("MiroFish paused lifecycle events require a checkpoint reference.")
        if status == "running":
            if not first_running_seen and initial_checkpoint is not None and checkpoint != initial_checkpoint:
                raise ContractValidationError("MiroFish initial resume must carry its immutable checkpoint.")
            if previous_status == "paused" and checkpoint != previous_checkpoint:
                raise ContractValidationError("MiroFish resume must carry the preceding paused checkpoint.")
            if previous_status not in {"paused", None} and not (not first_running_seen and initial_checkpoint is not None) and checkpoint is not None:
                raise ContractValidationError("MiroFish checkpoints are only allowed for a meaningful resume.")
            first_running_seen = True
        elif checkpoint is not None and status != "paused":
            raise ContractValidationError("MiroFish checkpoints are only allowed on paused or resumed running events.")
        if status == "cancellation_requested" and cancellation is None:
            raise ContractValidationError("MiroFish cancellation requests require an opaque cancellation reference.")
        if status != "cancellation_requested" and cancellation is not None:
            raise ContractValidationError("MiroFish cancellation references are only allowed on cancellation requests.")
        previous_status, previous_revision, previous_time, previous_checkpoint = status, revision, timestamp, checkpoint
    if document["status"] != previous_status or document["revision"] != previous_revision:
        raise ContractValidationError("MiroFish state must equal its latest lifecycle event.")
    if document["cancellation_requested"] != (document["status"] in {"cancellation_requested", "cancelled"}):
        raise ContractValidationError("MiroFish cancellation_requested must reflect the current cancellation lifecycle.")
    counters = document["counters"]
    progress = document["progress"]
    assert isinstance(counters, Mapping) and isinstance(progress, Mapping)
    if progress["completed_units"] > progress["total_units"]:
        raise ContractValidationError("MiroFish progress cannot exceed its declared total.")
    if document["status"] == "succeeded" and (progress["phase"] != "completed" or progress["completed_units"] != progress["total_units"]):
        raise ContractValidationError("Succeeded MiroFish state requires completed readback-backed progress.")
    if document["status"] in {"succeeded", "failed", "cancelled", "timed_out", "unavailable"} and counters["active_workers"] != 0:
        raise ContractValidationError("Terminal MiroFish state cannot retain active workers.")
    if document["status"] in {"failed", "timed_out", "unavailable"} and "error_class" not in document:
        raise ContractValidationError("Failed, timed-out, or unavailable MiroFish state requires a redacted error class.")
    if document["status"] == "succeeded" and "error_class" in document:
        raise ContractValidationError("Succeeded MiroFish state cannot carry an error class.")


def _validate_mirofish_terminal_document(document: Mapping[str, object]) -> None:
    started_at = _parse_aware_timestamp(document["started_at"], "MiroFish terminal document start")
    completed_at = _parse_aware_timestamp(document["completed_at"], "MiroFish terminal document completion")
    if completed_at < started_at:
        raise ContractValidationError("MiroFish terminal document completion cannot precede start.")
    if document["outcome"] in {"failed", "timed_out", "unavailable"} and "error_class" not in document:
        raise ContractValidationError("Failed, timed-out, or unavailable MiroFish terminal documents require a redacted error class.")
    if document["outcome"] == "succeeded" and "error_class" in document:
        raise ContractValidationError("Succeeded MiroFish terminal documents cannot carry an error class.")


def _validate_mirofish_counters_and_cost(counters: object, cost: object, limits: object, label: str) -> None:
    assert isinstance(counters, Mapping) and isinstance(cost, Mapping) and isinstance(limits, Mapping)
    for counter, limit in (("executed_steps", "max_steps"), ("retry_count", "max_retries"), ("active_workers", "max_agents"), ("agent_count", "max_agents"), ("rounds_completed", "max_rounds"), ("artifact_count", "max_artifacts")):
        if counters[counter] > limits[limit]:
            raise ContractValidationError(f"MiroFish {label} {counter} exceeds its approved limit.")
    if counters["verification_count"] > counters["artifact_count"] or cost["actual_cost_minor"] > limits["max_cost_minor"] or cost["currency"] != limits["currency"]:
        raise ContractValidationError(f"MiroFish {label} verification or cost exceeds approved limits.")


def _validate_mirofish_succeeded_evidence(plan: Mapping[str, object], state: Mapping[str, object], evidence: Mapping[str, object], result: Mapping[str, object]) -> None:
    counters = state["counters"]
    assert isinstance(counters, Mapping)
    if counters["executed_steps"] < 3 or counters["agent_count"] < 1 or counters["rounds_completed"] < 1 or counters["artifact_count"] != 3 or counters["verification_count"] != 3:
        raise ContractValidationError("Succeeded MiroFish result cannot be a no-op and requires complete bounded work.")
    required_evidence_fields = ("external_receipt_ref", "graph_artifact", "simulation_artifact", "forecast_artifact")
    if any(field not in evidence for field in required_evidence_fields) or "external_receipt_ref" not in result:
        raise ContractValidationError("Succeeded MiroFish result requires external receipt and all three artifact evidence records.")
    if evidence["external_receipt_ref"] != result["external_receipt_ref"]:
        raise ContractValidationError("Succeeded MiroFish result receipt must match the supplied evidence.")
    artifacts = ("graph_artifact", "simulation_artifact", "forecast_artifact")
    artifact_refs: list[object] = []
    readback_refs: list[object] = []
    verification_refs: list[object] = []
    for artifact_name in artifacts:
        artifact = evidence[artifact_name]
        assert isinstance(artifact, Mapping)
        artifact_ref, readback_ref, verification_ref = artifact["artifact_ref"], artifact["readback_ref"], artifact["verification_ref"]
        artifact_refs.append(artifact_ref)
        readback_refs.append(readback_ref)
        verification_refs.append(verification_ref)
        if not artifact["content_hash"] or not artifact["provenance_ref"]:
            raise ContractValidationError("Succeeded MiroFish artifacts require content hashes and provenance references.")
    if len(set(artifact_refs)) != 3 or len(set(readback_refs)) != 3 or len(set(verification_refs)) != 3:
        raise ContractValidationError("Succeeded MiroFish artifact, readback, and verification references must be distinct.")
    if (result["graph_artifact_ref"], result["simulation_artifact_ref"], result["forecast_artifact_ref"]) != tuple(artifact_refs):
        raise ContractValidationError("Succeeded MiroFish result artifact references must exactly match evidence.")
    if result["readback_refs"] != readback_refs or result["verification_refs"] != verification_refs:
        raise ContractValidationError("Succeeded MiroFish result readback and verification references must exactly match evidence.")
    if set(result["satisfied_criteria_ids"]) != set(plan["success_criteria"]):
        raise ContractValidationError("Succeeded MiroFish result must satisfy every immutable external-evidence criterion.")


def _require_matching_mirofish_fields(document: Mapping[str, object], expected: Mapping[str, object], field_names: tuple[str, ...], label: str) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(f"MiroFish {label} {field_name} does not match its immutable reference.")


def validate_research_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate a complete Research V1 chain offline and fail closed on broken refs."""
    expected_types = {
        "research-request",
        "research-plan",
        "research-job",
        "source-evidence",
        "citation",
        "research-result",
        "research-idea-handoff",
    }
    if set(documents) != expected_types:
        raise ContractValidationError(
            "Research bundle must contain exactly the seven Research V1 document types."
        )
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["research-request"]
    plan = documents["research-plan"]
    job = documents["research-job"]
    source_evidence = documents["source-evidence"]
    citation = documents["citation"]
    result = documents["research-result"]
    handoff = documents["research-idea-handoff"]

    _require_matching_refs(plan, request, ("request_id", "task_id", "trace_id"), "plan")
    _require_matching_refs(job, plan, ("request_id", "plan_id", "task_id", "trace_id"), "job")
    _require_matching_refs(
        source_evidence, job, ("request_id", "plan_id", "job_id"), "source evidence"
    )
    _require_matching_refs(
        result, job, ("request_id", "plan_id", "job_id", "task_id", "trace_id"), "result"
    )

    request_limits = request["collection_limits"]
    plan_limits = plan["collection_limits"]
    assert isinstance(request_limits, Mapping)
    assert isinstance(plan_limits, Mapping)
    for limit_name in ("max_sources", "max_depth", "max_duration_seconds"):
        assert isinstance(request_limits[limit_name], int)
        assert isinstance(plan_limits[limit_name], int)
        if plan_limits[limit_name] > request_limits[limit_name]:
            raise ContractValidationError(
                f"Research plan {limit_name} exceeds the request hard bound."
            )

    _validate_research_budget_chain(request, plan, result)
    _validate_bundle_evidence_and_citation(source_evidence, citation, result)
    if result["status"] != job["status"]:
        raise ContractValidationError("Research result status must match the referenced job status.")
    if handoff["result_id"] != result["result_id"]:
        raise ContractValidationError("Research idea handoff result_id does not match the result.")
    if result["status"] != "succeeded":
        raise ContractValidationError("Research idea handoff requires a succeeded result.")
    result_evidence_refs = result["evidence_refs"]
    handoff_evidence_refs = handoff["evidence_refs"]
    assert isinstance(result_evidence_refs, list)
    assert isinstance(handoff_evidence_refs, list)
    if not set(handoff_evidence_refs).issubset(result_evidence_refs):
        raise ContractValidationError(
            "Research idea handoff evidence references must be present on the result."
        )
    result_cost = result["cost"]
    assert isinstance(result_cost, Mapping)
    if handoff["approval_ref"] != result_cost["approval_ref"]:
        raise ContractValidationError(
            "Research idea handoff approval_ref must match the result approval reference."
        )


def _validate_research_request(document: Mapping[str, object]) -> None:
    clarification = document["clarification"]
    assert isinstance(clarification, Mapping)
    required = clarification["required"]
    questions = clarification["questions"]
    assert isinstance(required, bool)
    assert isinstance(questions, list)
    if required and not questions:
        raise ContractValidationError(
            "Research request requires at least one clarification question when clarification is required."
        )


def _validate_research_job_state_machine(document: Mapping[str, object]) -> None:
    transitions = {
        "clarification_required": {"queued", "cancelled", "unavailable"},
        "queued": {"running", "waiting_for_approval", "paused", "cancelled", "unavailable"},
        "running": {"waiting_for_approval", "paused", "succeeded", "failed", "cancelled", "unavailable"},
        "waiting_for_approval": {"queued", "paused", "cancelled", "unavailable"},
        "paused": {"queued", "cancelled", "unavailable"},
        "succeeded": set(),
        "failed": set(),
        "cancelled": set(),
        "unavailable": set(),
    }
    history = document["status_history"]
    assert isinstance(history, list)
    statuses: list[str] = []
    for record in history:
        assert isinstance(record, Mapping)
        status = record["status"]
        assert isinstance(status, str)
        statuses.append(status)
    if statuses[-1] != document["status"]:
        raise ContractValidationError("Research job status must equal the last status_history entry.")
    for previous, current in zip(statuses, statuses[1:]):
        if current not in transitions[previous]:
            raise ContractValidationError(
                f"Research job lifecycle transition {previous!r} -> {current!r} is not allowed."
            )


def _validate_source_evidence(document: Mapping[str, object]) -> None:
    source_url = document["source_url"]
    assert isinstance(source_url, str)
    _validate_source_url(source_url)


def _validate_source_url(source_url: str) -> None:
    parsed = urlsplit(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ContractValidationError("Research source_url must use http or https with a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ContractValidationError("Research source_url must not contain userinfo.")


def _validate_research_result(document: Mapping[str, object]) -> None:
    source_evidence = document["source_evidence"]
    citations = document["citations"]
    claims = document["claims"]
    artifact_refs = document["artifact_refs"]
    evidence_refs = document["evidence_refs"]
    assert isinstance(source_evidence, list)
    assert isinstance(citations, list)
    assert isinstance(claims, list)
    assert isinstance(artifact_refs, list)
    assert isinstance(evidence_refs, list)
    if document["status"] == "succeeded" and (
        not source_evidence or not citations or not artifact_refs or not evidence_refs
    ):
        raise ContractValidationError(
            "A succeeded research result requires source evidence, citations, artifact references, and evidence references."
        )
    source_by_id: dict[str, Mapping[str, object]] = {}
    for source in source_evidence:
        assert isinstance(source, Mapping)
        _validate_embedded_source_evidence(source, document)
        evidence_id = source["evidence_id"]
        assert isinstance(evidence_id, str)
        if evidence_id in source_by_id:
            raise ContractValidationError(f"Research result has duplicate source evidence {evidence_id!r}.")
        source_by_id[evidence_id] = source
    claim_by_id: dict[str, Mapping[str, object]] = {}
    for claim in claims:
        assert isinstance(claim, Mapping)
        claim_id = claim["claim_id"]
        assert isinstance(claim_id, str)
        if claim_id in claim_by_id:
            raise ContractValidationError(f"Research result has duplicate claim {claim_id!r}.")
        claim_by_id[claim_id] = claim
    citations_by_claim: dict[str, list[Mapping[str, object]]] = {}
    citation_ids: set[str] = set()
    for citation in citations:
        assert isinstance(citation, Mapping)
        citation_id = citation["citation_id"]
        claim_id = citation["claim_id"]
        evidence_id = citation["source_evidence_id"]
        assert isinstance(citation_id, str)
        assert isinstance(claim_id, str)
        assert isinstance(evidence_id, str)
        if citation_id in citation_ids:
            raise ContractValidationError(f"Research result has duplicate citation {citation_id!r}.")
        if claim_id not in claim_by_id:
            raise ContractValidationError(f"Citation {citation_id!r} references an unknown claim.")
        if evidence_id not in source_by_id:
            raise ContractValidationError(
                f"Citation {citation_id!r} references missing source evidence {evidence_id!r}."
            )
        source = source_by_id[evidence_id]
        if citation["locator"] != source["locator"]:
            raise ContractValidationError(
                f"Citation {citation_id!r} locator does not match its source evidence."
            )
        if citation["passage"] != source["passage"]:
            raise ContractValidationError(
                f"Citation {citation_id!r} passage does not match its source evidence."
            )
        citation_ids.add(citation_id)
        citations_by_claim.setdefault(claim_id, []).append(citation)
    for claim_id, claim in claim_by_id.items():
        if claim["verification_status"] == "verified":
            cited_sources = citations_by_claim.get(claim_id, [])
            if not cited_sources or not any(
                source_by_id[citation["source_evidence_id"]]["verification_status"] == "verified"
                for citation in cited_sources
            ):
                raise ContractValidationError(
                    f"Verified claim {claim_id!r} lacks verified source evidence."
                )


def _validate_embedded_source_evidence(
    source_evidence: Mapping[str, object], result: Mapping[str, object]
) -> None:
    _require_matching_refs(
        source_evidence, result, ("request_id", "plan_id", "job_id"), "result source evidence"
    )
    source_url = source_evidence["source_url"]
    assert isinstance(source_url, str)
    _validate_source_url(source_url)


def _validate_research_budget_chain(
    request: Mapping[str, object], plan: Mapping[str, object], result: Mapping[str, object]
) -> None:
    request_budget = request["budget"]
    plan_budget = plan["budget"]
    result_cost = result["cost"]
    assert isinstance(request_budget, Mapping)
    assert isinstance(plan_budget, Mapping)
    assert isinstance(result_cost, Mapping)
    for field_name in ("currency", "quote_ref", "approval_ref"):
        if plan_budget[field_name] != request_budget[field_name]:
            raise ContractValidationError(
                f"Research plan budget {field_name} does not match the request budget."
            )
    request_max_cost = request_budget["max_cost_minor"]
    plan_max_cost = plan_budget["max_cost_minor"]
    assert isinstance(request_max_cost, int)
    assert isinstance(plan_max_cost, int)
    if plan_max_cost > request_max_cost:
        raise ContractValidationError(
            "Research plan budget max_cost_minor exceeds the request budget."
        )
    for field_name in ("currency", "quote_ref", "approval_ref"):
        if result_cost[field_name] != plan_budget[field_name]:
            raise ContractValidationError(
                f"Research result cost {field_name} does not match the plan budget."
            )
    for field_name in ("estimated_cost_minor", "actual_cost_minor"):
        cost = result_cost[field_name]
        assert isinstance(cost, int)
        if cost > plan_max_cost:
            raise ContractValidationError(
                f"Research result cost {field_name} exceeds the approved plan budget."
            )


def _require_matching_refs(
    document: Mapping[str, object],
    expected: Mapping[str, object],
    field_names: tuple[str, ...],
    document_label: str,
) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(
                f"Research {document_label} {field_name} does not match the referenced document."
            )


def _validate_bundle_evidence_and_citation(
    source_evidence: Mapping[str, object], citation: Mapping[str, object], result: Mapping[str, object]
) -> None:
    if citation["source_evidence_id"] != source_evidence["evidence_id"]:
        raise ContractValidationError("Citation source evidence reference does not match the bundle source evidence.")
    result_sources = result["source_evidence"]
    result_citations = result["citations"]
    result_evidence_refs = result["evidence_refs"]
    assert isinstance(result_sources, list)
    assert isinstance(result_citations, list)
    assert isinstance(result_evidence_refs, list)
    if not any(source == source_evidence for source in result_sources):
        raise ContractValidationError("Research result must include the referenced source evidence.")
    if not any(item == citation for item in result_citations):
        raise ContractValidationError("Research result must include the referenced citation.")
    source_refs = source_evidence["evidence_refs"]
    assert isinstance(source_refs, list)
    if not set(source_refs).issubset(result_evidence_refs):
        raise ContractValidationError(
            "Research result evidence references must include source evidence references."
        )


def verify_space_identity_snapshot(
    registry_path: Path,
) -> SpaceIdentitySnapshotVerification:
    """Compare the outer canonical-space snapshot with an initialized registry.

    This helper is read-only. A missing registry is reported explicitly rather
    than treated as a successful comparison.
    """
    if not registry_path.is_file():
        return SpaceIdentitySnapshotVerification(
            status="registry-unavailable",
            registry_path=registry_path,
        )

    snapshot = _load_space_identity_snapshot()
    expected_space_ids = _snapshot_string_list(snapshot, "canonical_space_ids")
    try:
        registry_value = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ContractValidationError(
            f"Space registry {registry_path} is not valid YAML."
        ) from error

    actual_space_ids = _registry_space_ids(registry_value, registry_path)
    missing_from_registry = tuple(sorted(set(expected_space_ids) - set(actual_space_ids)))
    extra_in_registry = tuple(sorted(set(actual_space_ids) - set(expected_space_ids)))
    return SpaceIdentitySnapshotVerification(
        status=("verified" if not missing_from_registry and not extra_in_registry else "drift"),
        registry_path=registry_path,
        missing_from_registry=missing_from_registry,
        extra_in_registry=extra_in_registry,
    )


def validate_brain_plan_admission_bundle(
    channel_intent: Mapping[str, object],
    brain_plan: Mapping[str, object],
    space_execution_contracts: list[Mapping[str, object]],
) -> None:
    """Validate that an offline Brain plan bundle is admissible, never executed."""
    validate_document("channel-intent", channel_intent)
    validate_document("brain-plan", brain_plan)
    for contract in space_execution_contracts:
        validate_document("space-execution-contract", contract)

    participating_spaces = brain_plan["participating_spaces"]
    tasks = brain_plan["tasks"]
    assert isinstance(participating_spaces, list) and isinstance(tasks, list)
    participating_space_ids = {
        space["space_id"]
        for space in participating_spaces
        if isinstance(space, Mapping) and isinstance(space["space_id"], str)
    }
    canonical_space_ids = set(
        _snapshot_string_list(_load_space_identity_snapshot(), "canonical_space_ids")
    )
    noncanonical_space_ids = participating_space_ids - canonical_space_ids
    if noncanonical_space_ids:
        raise ContractValidationError(
            "Brain plan participating spaces must be canonical; "
            f"not canonical: {sorted(noncanonical_space_ids)!r}."
        )

    requested_space_id = channel_intent.get("requested_space_id")
    if requested_space_id is not None and requested_space_id not in participating_space_ids:
        raise ContractValidationError(
            "channel-intent requested_space_id must be a Brain plan participating space."
        )

    contract_space_ids = [contract["space_id"] for contract in space_execution_contracts]
    assert all(isinstance(space_id, str) for space_id in contract_space_ids)
    unparticipating_contract_space_ids = set(contract_space_ids) - participating_space_ids
    if unparticipating_contract_space_ids:
        raise ContractValidationError(
            "Brain plan admission bundle contains unparticipating SpaceExecutionContracts: "
            f"{sorted(unparticipating_contract_space_ids)!r}."
        )
    for space_id in participating_space_ids:
        if contract_space_ids.count(space_id) != 1:
            raise ContractValidationError(
                "Brain plan admission bundle requires exactly one "
                f"SpaceExecutionContract for participating space {space_id!r}."
            )

    covered_space_ids = set(contract_space_ids)
    for task in tasks:
        assert isinstance(task, Mapping)
        task_space_ids = task["space_ids"]
        evidence_requirements = task["evidence_requirements"]
        assert isinstance(task_space_ids, list) and isinstance(evidence_requirements, list)
        if not set(task_space_ids).issubset(participating_space_ids):
            raise ContractValidationError(
                "Brain plan task spaces must be participating spaces."
            )
        if not set(task_space_ids).issubset(covered_space_ids):
            raise ContractValidationError(
                "Brain plan task spaces must be covered by SpaceExecutionContracts."
            )
        if not evidence_requirements:
            raise ContractValidationError(
                "Brain plan tasks must retain at least one evidence requirement."
            )


def validate_brain_plan_lifecycle_bundle(
    channel_intent: Mapping[str, object],
    brain_plan: Mapping[str, object],
    space_execution_contracts: list[Mapping[str, object]],
    lifecycle: Mapping[str, object],
) -> None:
    """Validate a persisted planning lifecycle after offline admission checks."""
    validate_brain_plan_admission_bundle(
        channel_intent, brain_plan, space_execution_contracts
    )
    validate_document("brain-plan-lifecycle", lifecycle)

    if lifecycle["correlation_id"] != channel_intent["correlation_id"]:
        raise ContractValidationError(
            "Brain plan lifecycle correlation_id must exactly match the admitted channel intent."
        )
    if lifecycle["plan_id"] != brain_plan["plan_id"]:
        raise ContractValidationError(
            "Brain plan lifecycle plan_id must exactly match the admitted Brain plan."
        )

    participating_spaces = brain_plan["participating_spaces"]
    lifecycle_space_ids = lifecycle["participating_space_ids"]
    assert isinstance(participating_spaces, list) and isinstance(lifecycle_space_ids, list)
    plan_space_ids = [space["space_id"] for space in participating_spaces]
    if lifecycle_space_ids != plan_space_ids:
        raise ContractValidationError(
            "Brain plan lifecycle participating_space_ids must exactly match the admitted Brain plan."
        )


def validate_brain_openfang_handoff_bundle(
    channel_intent: Mapping[str, object],
    brain_plan: Mapping[str, object],
    space_execution_contracts: list[Mapping[str, object]],
    lifecycle: Mapping[str, object],
    handoff: Mapping[str, object],
) -> None:
    """Validate a deferred Brain plan node handoff without execution authority."""
    validate_brain_plan_lifecycle_bundle(
        channel_intent, brain_plan, space_execution_contracts, lifecycle
    )
    validate_document("brain-openfang-handoff", handoff)

    if lifecycle["status"] != "execution_deferred":
        raise ContractValidationError(
            "Brain OpenFang handoff requires an execution_deferred Brain plan lifecycle."
        )
    for field_name in ("correlation_id", "plan_id"):
        if handoff[field_name] != lifecycle[field_name]:
            raise ContractValidationError(
                f"Brain OpenFang handoff {field_name} must match the deferred lifecycle."
            )
    if handoff["lifecycle_revision"] != lifecycle["revision"]:
        raise ContractValidationError(
            "Brain OpenFang handoff lifecycle_revision must match the deferred lifecycle revision."
        )

    tasks = brain_plan["tasks"]
    assert isinstance(tasks, list)
    selected_tasks = [
        task
        for task in tasks
        if isinstance(task, Mapping) and task["node_id"] == handoff["brain_task_node_id"]
    ]
    if len(selected_tasks) != 1:
        raise ContractValidationError(
            "Brain OpenFang handoff brain_task_node_id must select exactly one admitted Brain task."
        )
    selected_task_space_ids = selected_tasks[0]["space_ids"]
    assert isinstance(selected_task_space_ids, list)
    if handoff["space_id"] not in selected_task_space_ids:
        raise ContractValidationError(
            "Brain OpenFang handoff space_id must be declared by the selected Brain task."
        )

    participating_spaces = brain_plan["participating_spaces"]
    assert isinstance(participating_spaces, list)
    selected_spaces = [
        space
        for space in participating_spaces
        if isinstance(space, Mapping) and space["space_id"] == handoff["space_id"]
    ]
    if len(selected_spaces) != 1:
        raise ContractValidationError(
            "Brain OpenFang handoff space_id must select exactly one admitted canonical Space."
        )
    if handoff["roles"] != selected_spaces[0]["roles"]:
        raise ContractValidationError(
            "Brain OpenFang handoff roles must exactly match the admitted Space roles."
        )


def validate_channel_result_route_bundle(
    channel_intent: Mapping[str, object],
    brain_plan: Mapping[str, object],
    space_execution_contracts: list[Mapping[str, object]],
    channel_result: Mapping[str, object],
) -> None:
    """Validate an offline ChannelResultV1 projection of one admitted Brain route."""
    validate_brain_plan_admission_bundle(
        channel_intent, brain_plan, space_execution_contracts
    )
    validate_document("channel-result", channel_result)

    for field_name in (
        "correlation_id",
        "channel_kind",
        "actor_context",
        "session_context",
    ):
        if channel_result[field_name] != channel_intent[field_name]:
            raise ContractValidationError(
                f"Channel result {field_name} must exactly match the admitted channel intent."
            )

    if channel_result["plan_id"] != brain_plan["plan_id"]:
        raise ContractValidationError(
            "Channel result plan_id must exactly match the admitted Brain plan."
        )

    participating_spaces = brain_plan["participating_spaces"]
    result_space_ids = channel_result["participating_space_ids"]
    assert isinstance(participating_spaces, list) and isinstance(result_space_ids, list)
    plan_space_ids = [space["space_id"] for space in participating_spaces]
    if result_space_ids != plan_space_ids:
        raise ContractValidationError(
            "Channel result participating_space_ids must exactly match the admitted Brain plan."
        )


def _validate_channel_result(document: Mapping[str, object]) -> None:
    """Keep a ChannelResultV1 a user projection without approval authority."""
    status = document["status"]
    evidence_refs = document.get("evidence_refs", [])
    assert isinstance(status, str) and isinstance(evidence_refs, list)

    if status == "succeeded" and not evidence_refs:
        raise ContractValidationError(
            "A succeeded channel result requires at least one evidence reference."
        )

    approval_ref = document.get("approval_ref")
    if status == "waiting_for_approval":
        if not isinstance(approval_ref, str) or not approval_ref:
            raise ContractValidationError(
                "A waiting_for_approval channel result requires an opaque approval_ref."
            )
    elif approval_ref is not None:
        raise ContractValidationError(
            "Only waiting_for_approval channel results may carry an approval_ref."
        )


def _load_space_identity_snapshot() -> Mapping[str, object]:
    try:
        value = json.loads(SPACE_IDENTITY_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except OSError as error:
        raise ContractValidationError("The Space identity snapshot is unavailable.") from error
    except json.JSONDecodeError as error:
        raise ContractValidationError("The Space identity snapshot is not valid JSON.") from error
    if not isinstance(value, Mapping):
        raise ContractValidationError("The Space identity snapshot must be an object.")
    return value


def _snapshot_string_list(snapshot: Mapping[str, object], field_name: str) -> tuple[str, ...]:
    value = snapshot.get(field_name)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise ContractValidationError(
            f"The Space identity snapshot field {field_name!r} must be a non-empty string list."
        )
    return tuple(value)


def _registry_space_ids(registry_value: object, registry_path: Path) -> tuple[str, ...]:
    if not isinstance(registry_value, Mapping):
        raise ContractValidationError(f"Space registry {registry_path} must be an object.")
    spaces = registry_value.get("spaces")
    if isinstance(spaces, Mapping):
        if not spaces or not all(isinstance(space_id, str) for space_id in spaces):
            raise ContractValidationError(
                f"Space registry {registry_path} must contain named Space entries."
            )
        return tuple(spaces)
    if isinstance(spaces, list):
        space_ids: list[str] = []
        for entry in spaces:
            if not isinstance(entry, Mapping):
                raise ContractValidationError(
                    f"Space registry {registry_path} has a non-object Space entry."
                )
            space_id = entry.get("space_id", entry.get("id"))
            if not isinstance(space_id, str):
                raise ContractValidationError(
                    f"Space registry {registry_path} has a Space entry without an ID."
                )
            space_ids.append(space_id)
        if not space_ids:
            raise ContractValidationError(f"Space registry {registry_path} has no Space entries.")
        return tuple(space_ids)
    raise ContractValidationError(
        f"Space registry {registry_path} must contain a 'spaces' mapping or list."
    )


def _reject_brain_plan_application_targets(document: Mapping[str, object]) -> None:
    """Keep Brain plans declarative and independent of application calls."""
    tasks = document.get("tasks")
    if not isinstance(tasks, list):
        return

    for index, task in enumerate(tasks):
        if isinstance(task, Mapping) and "application_target" in task:
            raise ContractValidationError(
                "brain-plan application targets are forbidden; "
                f"found one at tasks.{index}."
            )


def _validate_brain_plan_graph(document: Mapping[str, object]) -> None:
    """Validate references, order, and acyclicity in a BrainPlanV1 task graph."""
    tasks = document["tasks"]
    participating_spaces = document["participating_spaces"]
    assert isinstance(tasks, list)
    assert isinstance(participating_spaces, list)

    declared_space_ids: set[str] = set()
    for space in participating_spaces:
        assert isinstance(space, Mapping)
        space_id = space["space_id"]
        assert isinstance(space_id, str)
        if space_id in declared_space_ids:
            raise ContractValidationError(
                f"brain-plan contains duplicate participating space_id {space_id!r}."
            )
        declared_space_ids.add(space_id)

    dependencies: dict[str, list[str]] = {}
    node_orders: dict[str, int] = {}
    used_orders: set[int] = set()
    for task in tasks:
        assert isinstance(task, Mapping)
        node_id = task["node_id"]
        order = task["order"]
        space_ids = task["space_ids"]
        depends_on = task["depends_on"]
        assert isinstance(node_id, str)
        assert isinstance(order, int)
        assert isinstance(space_ids, list)
        assert isinstance(depends_on, list)

        if node_id in dependencies:
            raise ContractValidationError(
                f"brain-plan contains duplicate task node_id {node_id!r}."
            )
        if order in used_orders:
            raise ContractValidationError(
                f"brain-plan contains duplicate task order {order}."
            )

        for space_id in space_ids:
            assert isinstance(space_id, str)
            if space_id not in declared_space_ids:
                raise ContractValidationError(
                    f"brain-plan task {node_id!r} references undeclared space {space_id!r}."
                )

        dependencies[node_id] = [dependency for dependency in depends_on if isinstance(dependency, str)]
        node_orders[node_id] = order
        used_orders.add(order)

    for node_id, dependency_ids in dependencies.items():
        for dependency_id in dependency_ids:
            if dependency_id not in dependencies:
                raise ContractValidationError(
                    f"brain-plan task {node_id!r} depends on unknown task node {dependency_id!r}."
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            raise ContractValidationError(
                f"brain-plan task graph contains a cycle at {node_id!r}."
            )
        if node_id in visited:
            return

        visiting.add(node_id)
        for dependency in dependencies[node_id]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in dependencies:
        visit(node_id)

    for node_id, dependency_ids in dependencies.items():
        for dependency_id in dependency_ids:
            if node_orders[dependency_id] >= node_orders[node_id]:
                raise ContractValidationError(
                    f"brain-plan dependency {dependency_id!r} must precede task {node_id!r}."
                )


def _validate_brain_plan_lifecycle(document: Mapping[str, object]) -> None:
    """Validate the closed Brain planning state machine and its persisted history."""
    event_history = document["event_history"]
    assert isinstance(event_history, list)
    events = [event for event in event_history if isinstance(event, Mapping)]
    if len(events) != len(event_history):
        raise ContractValidationError("Brain plan lifecycle event history must contain objects.")
    if events[0]["status"] != "planned":
        raise ContractValidationError("Brain plan lifecycle must start in planned status.")

    allowed_transitions = {
        "planned": {"awaiting_clarification", "admitted", "cancelled"},
        "awaiting_clarification": {"planned", "cancelled"},
        "admitted": {"execution_deferred", "cancelled"},
        "execution_deferred": set(),
        "cancelled": set(),
    }
    terminal_statuses = {"execution_deferred", "cancelled"}
    previous_status: str | None = None
    previous_timestamp: datetime | None = None

    for expected_revision, event in enumerate(events, start=1):
        revision = event["revision"]
        status = event["status"]
        occurred_at = event["occurred_at"]
        assert isinstance(revision, int) and isinstance(status, str) and isinstance(occurred_at, str)
        if revision != expected_revision:
            raise ContractValidationError(
                "Brain plan lifecycle event revisions must be contiguous from revision 1."
            )

        timestamp = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ContractValidationError(
                "Brain plan lifecycle timestamps must be timezone-aware."
            )
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise ContractValidationError(
                "Brain plan lifecycle timestamps must be monotonically non-decreasing."
            )
        if previous_status is not None:
            if previous_status in terminal_statuses:
                raise ContractValidationError(
                    "Brain plan lifecycle terminal status cannot be reopened."
                )
            if status not in allowed_transitions[previous_status]:
                raise ContractValidationError(
                    f"Brain plan lifecycle transition {previous_status!r} -> {status!r} is forbidden."
                )
        previous_status = status
        previous_timestamp = timestamp

    final_event = events[-1]
    if document["revision"] != final_event["revision"]:
        raise ContractValidationError(
            "Brain plan lifecycle revision must match the final event revision."
        )
    if document["status"] != final_event["status"]:
        raise ContractValidationError(
            "Brain plan lifecycle final status must match the final event status."
        )
    if document["updated_at"] != final_event["occurred_at"]:
        raise ContractValidationError(
            "Brain plan lifecycle updated_at must match the final event occurred_at."
        )


def validate_desktop_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate the exact five-document Desktop V1 chain offline and fail closed."""
    expected_types = {
        "desktop-action-request",
        "desktop-action-plan",
        "desktop-action-run-request",
        "desktop-action-run-state",
        "desktop-action-result",
    }
    if set(documents) != expected_types:
        raise ContractValidationError("Desktop bundle must contain exactly five DesktopAction V1 documents.")
    for document_type in sorted(expected_types):
        validate_document(document_type, documents[document_type])

    request = documents["desktop-action-request"]
    plan = documents["desktop-action-plan"]
    run_request = documents["desktop-action-run-request"]
    state = documents["desktop-action-run-state"]
    result = documents["desktop-action-result"]

    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved":
        raise ContractValidationError("Desktop plan cannot exist before clarification resolves.")
    requested_at = request["requested_at"]
    resolved_at = clarification["resolved_at"]
    created_at = plan["created_at"]
    assert isinstance(requested_at, str) and isinstance(resolved_at, str) and isinstance(created_at, str)
    if _parse_aware_timestamp(resolved_at, "Desktop clarification resolved_at") < _parse_aware_timestamp(requested_at, "Desktop request requested_at") or _parse_aware_timestamp(created_at, "Desktop plan created_at") < _parse_aware_timestamp(resolved_at, "Desktop clarification resolved_at"):
        raise ContractValidationError("Desktop request must precede clarification and immutable plan creation.")

    _require_matching_desktop_fields(plan, request, ("request_id", "project_ref", "task_ref", "trace_id", "space_id", "request_hash"), "plan")
    if plan["bounds"] != request["hard_bounds"]:
        raise ContractValidationError("Desktop plan bounds must exactly match request hard_bounds.")
    if plan["approval_class"] != request["mutation_class"]:
        raise ContractValidationError("Desktop plan approval_class must match the request mutation_class.")
    _validate_desktop_plan_targets(plan, request)
    actions = plan["actions"]
    assert isinstance(actions, list)
    if not any(isinstance(action, Mapping) and action["action_class"] == request["action_class"] for action in actions):
        raise ContractValidationError("Desktop plan must include the requested action_class.")

    _require_matching_desktop_fields(run_request, plan, ("plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "request_hash", "parameter_digest"), "run request")
    _require_matching_desktop_fields(run_request, request, ("quote_ref", "approval_ref", "idempotency_key", "mutation_class"), "run request")
    _validate_desktop_limits(run_request["limits"], request["hard_bounds"], "run request")
    _validate_desktop_confirmation(run_request, "run request")

    _require_matching_desktop_fields(state, run_request, ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "mode", "mutation_class", "request_hash", "parameter_digest", "confirmation_ref", "confirmed_parameter_digest", "quote_ref", "approval_ref", "idempotency_key"), "run state")
    _validate_desktop_counters_and_cost(state["counters"], state["cost"], run_request["limits"], "run state")

    _require_matching_desktop_fields(result, state, ("run_id", "plan_id", "plan_version", "plan_hash", "request_id", "project_ref", "task_ref", "trace_id", "space_id", "mode", "mutation_class", "request_hash", "parameter_digest", "confirmation_ref", "confirmed_parameter_digest", "quote_ref", "approval_ref", "idempotency_key"), "result")
    if result["outcome"] != state["status"] or state["status"] not in {"succeeded", "failed", "cancelled", "unavailable"}:
        raise ContractValidationError("Desktop result requires the matching terminal run state.")
    if result["counters"] != state["counters"] or result["cost"] != state["cost"]:
        raise ContractValidationError("Desktop result counters and cost must match the run state.")
    _validate_desktop_counters_and_cost(result["counters"], result["cost"], run_request["limits"], "result")
    if result["target_refs"] != request["target_refs"]:
        raise ContractValidationError("Desktop result target/application/window refs must match the request.")
    _validate_desktop_result_evidence(result, run_request)

    history = state["event_history"]
    assert isinstance(history, list)
    first_event = history[0]
    final_event = history[-1]
    assert isinstance(first_event, Mapping) and isinstance(final_event, Mapping)
    queued_at = first_event["occurred_at"]
    completed_at = result["completed_at"]
    assert isinstance(queued_at, str) and isinstance(completed_at, str)
    if _parse_aware_timestamp(queued_at, "Desktop queued event") < _parse_aware_timestamp(created_at, "Desktop plan created_at"):
        raise ContractValidationError("Desktop queued lifecycle event cannot precede immutable plan creation.")
    if _parse_aware_timestamp(final_event["occurred_at"], "Desktop terminal event") != _parse_aware_timestamp(completed_at, "Desktop result completed_at"):
        raise ContractValidationError("Desktop terminal event must equal result completed_at.")
    running_events = [event for event in history if isinstance(event, Mapping) and event["status"] == "running"]
    if result["outcome"] in {"succeeded", "failed", "unavailable"} and not running_events:
        raise ContractValidationError("Desktop worked terminal result requires a running lifecycle event.")
    if running_events:
        started_at = result["started_at"]
        first_running = running_events[0]["occurred_at"]
        assert isinstance(started_at, str) and isinstance(first_running, str)
        if _parse_aware_timestamp(started_at, "Desktop result started_at") != _parse_aware_timestamp(first_running, "Desktop first running event"):
            raise ContractValidationError("Desktop result started_at must equal the first running lifecycle event.")
        elapsed = _parse_aware_timestamp(completed_at, "Desktop result completed_at") - _parse_aware_timestamp(started_at, "Desktop result started_at")
        limits = run_request["limits"]
        assert isinstance(limits, Mapping)
        if elapsed > timedelta(seconds=limits["timeout_seconds"]):
            raise ContractValidationError("Desktop worked result exceeds the approved timeout.")


def _require_matching_desktop_fields(document: Mapping[str, object], expected: Mapping[str, object], field_names: tuple[str, ...], label: str) -> None:
    for field_name in field_names:
        if document[field_name] != expected[field_name]:
            raise ContractValidationError(f"Desktop {label} {field_name} does not match its immutable reference.")


def _validate_desktop_action_plan(document: Mapping[str, object]) -> None:
    actions = document["actions"]
    bounds = document["bounds"]
    assert isinstance(actions, list) and isinstance(bounds, Mapping)
    if len(actions) > bounds["max_steps"]:
        raise ContractValidationError("Desktop plan actions exceed immutable max_steps.")
    actions_by_id: dict[str, Mapping[str, object]] = {}
    orders: set[int] = set()
    has_mutation = False
    for action in actions:
        assert isinstance(action, Mapping)
        action_id = action["action_id"]
        order = action["order"]
        action_class = action["action_class"]
        mutation_class = action["mutation_class"]
        assert isinstance(action_id, str) and isinstance(order, int)
        assert isinstance(action_class, str) and isinstance(mutation_class, str)
        if action_id in actions_by_id or order in orders:
            raise ContractValidationError("Desktop action IDs and orders must be unique.")
        if action_class == "observe" and mutation_class != "readonly":
            raise ContractValidationError("Desktop observe actions cannot hide mutation.")
        if action_class in {"input", "application_control"} and mutation_class != "mutating":
            raise ContractValidationError("Desktop input and application_control actions must be explicit mutations.")
        _validate_desktop_target_refs(action["target_refs"], "action target refs")
        actions_by_id[action_id] = action
        orders.add(order)
        has_mutation = has_mutation or mutation_class == "mutating"
    if orders != set(range(1, len(actions) + 1)):
        raise ContractValidationError("Desktop action orders must be contiguous from one.")
    if (document["approval_class"] == "mutating") != has_mutation:
        raise ContractValidationError("Desktop approval_class must exactly describe declared action mutation.")
    for action_id, action in actions_by_id.items():
        dependencies = action["depends_on"]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            assert isinstance(dependency, str)
            if dependency not in actions_by_id or actions_by_id[dependency]["order"] >= action["order"]:
                raise ContractValidationError(f"Desktop action {action_id!r} has an unknown or unordered dependency.")
    _assert_desktop_acyclic({action_id: action["depends_on"] for action_id, action in actions_by_id.items()})


def _validate_desktop_action_request(document: Mapping[str, object]) -> None:
    action_class = document["action_class"]
    mutation_class = document["mutation_class"]
    if action_class == "observe" and mutation_class != "readonly":
        raise ContractValidationError("Desktop request observe action_class must be readonly.")
    if action_class in {"input", "application_control"} and mutation_class != "mutating":
        raise ContractValidationError("Desktop request input and application_control action_class must be mutating.")


def _validate_desktop_plan_targets(plan: Mapping[str, object], request: Mapping[str, object]) -> None:
    request_targets = request["target_refs"]
    actions = plan["actions"]
    assert isinstance(request_targets, list) and isinstance(actions, list)
    _validate_desktop_target_refs(request_targets, "request target refs")
    for action in actions:
        assert isinstance(action, Mapping)
        if action["target_refs"] != request_targets:
            raise ContractValidationError("Desktop immutable action targets must match the request target refs.")


def _assert_desktop_acyclic(graph: Mapping[str, object]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ContractValidationError("Desktop action dependencies must be acyclic.")
        if node in visited:
            return
        visiting.add(node)
        dependencies = graph[node]
        assert isinstance(dependencies, list)
        for dependency in dependencies:
            assert isinstance(dependency, str)
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_desktop_target_refs(value: object, label: str) -> None:
    assert isinstance(value, list)
    identities: set[tuple[object, object, object]] = set()
    for target in value:
        assert isinstance(target, Mapping)
        identity = (target["target_ref"], target["application_ref"], target["window_ref"])
        if identity in identities:
            raise ContractValidationError(f"Desktop {label} cannot contain duplicate opaque refs.")
        identities.add(identity)


def _validate_desktop_limits(limits: object, hard_bounds: object, label: str) -> None:
    assert isinstance(limits, Mapping) and isinstance(hard_bounds, Mapping)
    for field_name in ("timeout_seconds", "max_steps", "max_retries", "max_cost_minor", "max_screenshots", "max_artifacts"):
        if limits[field_name] > hard_bounds[field_name]:
            raise ContractValidationError(f"Desktop {label} {field_name} exceeds the request hard bound.")
    if limits["currency"] != hard_bounds["currency"]:
        raise ContractValidationError(f"Desktop {label} currency must match the request hard bound.")


def _validate_desktop_confirmation(document: Mapping[str, object], label: str) -> None:
    mutation_class = document["mutation_class"]
    confirmation_ref = document.get("confirmation_ref")
    confirmed_digest = document.get("confirmed_parameter_digest")
    if mutation_class == "mutating":
        if confirmation_ref is None or confirmed_digest != document["parameter_digest"]:
            raise ContractValidationError(f"Desktop mutating {label} requires the exact confirmation digest.")
    elif confirmation_ref is not None or confirmed_digest is not None:
        raise ContractValidationError(f"Desktop read-only {label} cannot carry mutation confirmation.")


def _validate_desktop_action_run_state(document: Mapping[str, object]) -> None:
    transitions = {
        "queued": {"waiting_for_confirmation", "waiting_for_approval", "running", "cancelled", "unavailable"},
        "waiting_for_confirmation": {"waiting_for_approval", "cancelled", "unavailable"},
        "waiting_for_approval": {"running", "cancelled", "unavailable"},
        "running": {"paused", "succeeded", "failed", "cancelled", "unavailable"},
        "paused": {"running", "cancelled", "unavailable"},
        "succeeded": set(), "failed": set(), "cancelled": set(), "unavailable": set(),
    }
    history = document["event_history"]
    assert isinstance(history, list)
    previous_status: str | None = None
    previous_time: datetime | None = None
    previous_revision = 0
    paused_ref: object = None
    for event in history:
        assert isinstance(event, Mapping)
        status = event["status"]
        revision = event["revision"]
        occurred_at = event["occurred_at"]
        assert isinstance(status, str) and isinstance(revision, int) and isinstance(occurred_at, str)
        timestamp = _parse_aware_timestamp(occurred_at, "Desktop lifecycle event")
        if revision != previous_revision + 1 or (previous_time is not None and timestamp < previous_time):
            raise ContractValidationError("Desktop lifecycle revisions and timestamps must be monotonic.")
        if previous_status is None and status != "queued":
            raise ContractValidationError("Desktop lifecycle must start queued.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("Desktop lifecycle transition is illegal or reopens terminal state.")
        pause_ref = event["pause_ref"]
        cancellation_ref = event["cancellation_ref"]
        if status == "paused":
            if pause_ref is None:
                raise ContractValidationError("Desktop paused lifecycle events require a pause reference.")
            paused_ref = pause_ref
        elif status == "running" and previous_status == "paused":
            if pause_ref != paused_ref:
                raise ContractValidationError("Desktop resumed lifecycle events must carry the preceding pause reference.")
            paused_ref = None
        elif pause_ref is not None:
            raise ContractValidationError("Desktop pause references are only allowed for pause and matching resume events.")
        if status == "cancelled" and cancellation_ref is None:
            raise ContractValidationError("Desktop cancelled lifecycle events require a cancellation reference.")
        if status != "cancelled" and cancellation_ref is not None:
            raise ContractValidationError("Desktop cancellation references are only allowed on cancelled lifecycle events.")
        previous_status, previous_time, previous_revision = status, timestamp, revision
    if document["status"] != previous_status or document["revision"] != previous_revision:
        raise ContractValidationError("Desktop run state must equal its final lifecycle event.")
    terminal = document["status"] in {"succeeded", "failed", "cancelled", "unavailable"}
    if terminal and document["active_actions"] != 0:
        raise ContractValidationError("Desktop terminal states require active_actions=0.")
    if document["status"] in {"failed", "unavailable"} and document.get("error_class") is None:
        raise ContractValidationError("Desktop failed and unavailable states require a redacted error class.")
    if document["status"] == "succeeded" and document.get("error_class") is not None:
        raise ContractValidationError("Desktop succeeded states cannot carry an error_class.")
    if document["status"] == "cancelled":
        if not document["cancellation_requested"] or document["cancellation_ref"] != history[-1]["cancellation_ref"]:
            raise ContractValidationError("Desktop cancellation state must continue the terminal cancellation reference.")
    elif document["cancellation_requested"] or document["cancellation_ref"] is not None:
        raise ContractValidationError("Desktop non-cancelled states cannot carry cancellation state.")
    _validate_desktop_confirmation(document, "run state")
    statuses = [event["status"] for event in history if isinstance(event, Mapping)]
    first_running_index = next((index for index, status in enumerate(statuses) if status == "running"), None)
    if document["mutation_class"] == "mutating" and first_running_index is not None:
        prior_statuses = statuses[:first_running_index]
        try:
            confirmation_index = prior_statuses.index("waiting_for_confirmation")
            approval_index = prior_statuses.index("waiting_for_approval", confirmation_index + 1)
        except ValueError as error:
            raise ContractValidationError("Desktop mutating runs require confirmation then approval before running.") from error
        if confirmation_index == 0 or approval_index <= confirmation_index:
            raise ContractValidationError("Desktop mutating runs require confirmation then approval before running.")
    if document["mutation_class"] == "readonly" and "waiting_for_confirmation" in statuses:
        raise ContractValidationError("Desktop read-only runs cannot wait for confirmation.")


def _validate_desktop_action_result(document: Mapping[str, object]) -> None:
    outcome = document["outcome"]
    if outcome in {"failed", "unavailable"} and document.get("error_class") is None:
        raise ContractValidationError("Desktop failed and unavailable results require a redacted error class.")
    if outcome == "succeeded" and document.get("error_class") is not None:
        raise ContractValidationError("Desktop succeeded results cannot carry an error_class.")
    _validate_desktop_target_refs(document["target_refs"], "result target refs")


def _validate_desktop_counters_and_cost(counters: object, cost: object, limits: object, label: str) -> None:
    assert isinstance(counters, Mapping) and isinstance(cost, Mapping) and isinstance(limits, Mapping)
    for field_name, limit_name in (("executed_steps", "max_steps"), ("retry_count", "max_retries"), ("screenshot_count", "max_screenshots"), ("artifact_count", "max_artifacts")):
        if counters[field_name] > limits[limit_name]:
            raise ContractValidationError(f"Desktop {label} {field_name} exceeds the approved limit.")
    if cost["actual_cost_minor"] > limits["max_cost_minor"] or cost["currency"] != limits["currency"]:
        raise ContractValidationError(f"Desktop {label} cost exceeds or drifts from the approved limit.")


def _validate_desktop_result_evidence(result: Mapping[str, object], run_request: Mapping[str, object]) -> None:
    counters = result["counters"]
    visual = result["visual_evidence"]
    artifact_refs = result["artifact_refs"]
    assert isinstance(counters, Mapping) and isinstance(visual, Mapping) and isinstance(artifact_refs, list)
    if counters["artifact_count"] != len(artifact_refs):
        raise ContractValidationError("Desktop result artifact counter must equal artifact refs.")
    screenshot_refs = [reference for reference in visual.values() if reference is not None]
    if len(screenshot_refs) != len(set(screenshot_refs)):
        raise ContractValidationError("Desktop result visual evidence refs must be distinct.")
    if counters["screenshot_count"] != len(screenshot_refs):
        raise ContractValidationError("Desktop result screenshot counter must equal visual evidence refs.")
    if result["outcome"] != "succeeded":
        return
    evidence_refs = result["evidence_refs"]
    log_refs = result["log_refs"]
    assert isinstance(evidence_refs, list) and isinstance(log_refs, list)
    if result["mutation_class"] == "mutating":
        if result["confirmation_ref"] is None or result["confirmed_parameter_digest"] != result["parameter_digest"]:
            raise ContractValidationError("Desktop mutating success requires the matching confirmation digest.")
        if visual["before_screenshot_ref"] is None or visual["after_screenshot_ref"] is None:
            raise ContractValidationError("Desktop mutating success requires before and after visual evidence.")
        if visual["before_screenshot_ref"] == visual["after_screenshot_ref"]:
            raise ContractValidationError("Desktop mutating success requires distinct before and after visual evidence.")
        if not result["externally_verifiable"] or result["verification_ref"] is None:
            raise ContractValidationError("Desktop mutating success requires external verification evidence.")
        if not artifact_refs or not evidence_refs or not log_refs:
            raise ContractValidationError("Desktop mutating success requires artifact, evidence, and log references.")
    else:
        if not evidence_refs or (visual["before_screenshot_ref"] is None and visual["current_screenshot_ref"] is None):
            raise ContractValidationError("Desktop observe success requires truth evidence and before/current visual evidence.")
    _validate_desktop_confirmation(run_request, "run request")


def validate_video_job_bundle(documents: Mapping[str, Mapping[str, object]]) -> None:
    """Validate one exact, provider-neutral VideoJobV1 chain offline."""
    expected = {
        "video-job-request",
        "video-job-plan",
        "video-job-run-request",
        "video-job-run-state",
        "video-job-result",
    }
    if set(documents) != expected:
        raise ContractValidationError("VideoJob bundle must contain exactly the five V1 documents.")
    for document_type in sorted(expected):
        validate_document(document_type, documents[document_type])

    request = documents["video-job-request"]
    plan = documents["video-job-plan"]
    run_request = documents["video-job-run-request"]
    state = documents["video-job-run-state"]
    result = documents["video-job-result"]
    clarification = request["clarification"]
    assert isinstance(clarification, Mapping)
    if clarification["status"] != "resolved" or clarification["questions"] or clarification["resolved_at"] is None:
        raise ContractValidationError("VideoJob clarification must be resolved before planning or execution.")

    continuity = ("request_id", "project_ref", "task_ref", "trace_id", "space_id", "job_kind")
    for document in (plan, run_request, state, result):
        for field_name in continuity:
            if document[field_name] != request[field_name]:
                raise ContractValidationError(f"VideoJob {field_name} reference drift.")
    plan_fields = ("plan_id", "plan_version", "plan_hash")
    for document in (run_request, state, result):
        for field_name in plan_fields:
            if document[field_name] != plan[field_name]:
                raise ContractValidationError(f"VideoJob {field_name} reference drift.")
    for document in (state, result):
        for field_name in ("run_id", "mode"):
            if document[field_name] != run_request[field_name]:
                raise ContractValidationError(f"VideoJob {field_name} reference drift.")
    for field_name in ("quote_ref", "approval_ref", "idempotency_key"):
        if run_request[field_name] != request[field_name]:
            raise ContractValidationError(f"VideoJob {field_name} continuity drift.")
    if plan["limits"] != request["hard_limits"] or run_request["approved_limits"] != request["hard_limits"]:
        raise ContractValidationError("VideoJob plan and run limits must equal the request hard limits.")
    if plan["declared_artifact_kinds"] != request["requested_artifact_kinds"]:
        raise ContractValidationError("VideoJob declared artifact kinds must match the request.")

    steps = plan["steps"]
    assert isinstance(steps, list)
    limits = request["hard_limits"]
    assert isinstance(limits, Mapping)
    if len(steps) > limits["max_steps"]:
        raise ContractValidationError("VideoJob plan steps exceed the approved limit.")
    step_ids = [step["step_id"] for step in steps if isinstance(step, Mapping)]
    if len(step_ids) != len(set(step_ids)):
        raise ContractValidationError("VideoJob plan step identities must be unique.")
    seen: set[object] = set()
    emitted: set[object] = set()
    for expected_order, step in enumerate(steps, start=1):
        assert isinstance(step, Mapping)
        if step["order"] != expected_order or any(dependency not in seen for dependency in step["depends_on"]):
            raise ContractValidationError("VideoJob plan steps must be ordered and acyclic.")
        seen.add(step["step_id"])
        emitted.update(step["output_artifact_kinds"])
    if not set(plan["declared_artifact_kinds"]).issubset(emitted):
        raise ContractValidationError("VideoJob plan must emit every declared artifact kind.")

    history = state["event_history"]
    assert isinstance(history, list)
    transitions = {
        "queued": {"waiting_for_approval", "running", "cancelled", "failed", "unavailable"},
        "waiting_for_approval": {"running", "cancelled", "failed", "unavailable"},
        "running": {"succeeded", "failed", "cancelled", "unavailable"},
        "succeeded": set(), "failed": set(), "cancelled": set(), "unavailable": set(),
    }
    previous_status: str | None = None
    previous_time: datetime | None = None
    first_event_at: datetime | None = None
    running_at: datetime | None = None
    for expected_revision, event in enumerate(history, start=1):
        assert isinstance(event, Mapping)
        status = event["status"]
        occurred_at = event["occurred_at"]
        assert isinstance(status, str) and isinstance(occurred_at, str)
        event_time = _parse_aware_timestamp(occurred_at, "VideoJob lifecycle event")
        if first_event_at is None:
            first_event_at = event_time
        if event["revision"] != expected_revision or (previous_time is not None and event_time < previous_time):
            raise ContractValidationError("VideoJob lifecycle revisions and timestamps must be monotonic.")
        if previous_status is None and status != "queued":
            raise ContractValidationError("VideoJob lifecycle must start queued.")
        if previous_status is not None and status not in transitions[previous_status]:
            raise ContractValidationError("VideoJob lifecycle transition is illegal or reopens terminal state.")
        if status == "running" and running_at is None:
            running_at = event_time
        previous_status, previous_time = status, event_time
    if state["revision"] != len(history) or state["status"] != previous_status:
        raise ContractValidationError("VideoJob state must equal its final lifecycle event.")
    if state["status"] != result["outcome"]:
        raise ContractValidationError("VideoJob terminal result outcome must match run state.")

    state_counters = state["counters"]
    state_cost = state["cost"]
    assert isinstance(state_counters, Mapping) and isinstance(state_cost, Mapping)
    for counter, bound in (("executed_steps", "max_steps"), ("retry_count", "max_retries"), ("active_workers", "max_concurrency"), ("artifact_count", "max_artifacts"), ("input_bytes", "max_input_bytes"), ("output_bytes", "max_output_bytes"), ("media_duration_seconds", "max_duration_seconds")):
        if state_counters[counter] > limits[bound]:
            raise ContractValidationError(f"VideoJob {counter} exceeds its approved limit.")
    if state_counters["active_workers"] != 0:
        raise ContractValidationError("VideoJob terminal active_workers must be 0.")
    if state_cost["actual_cost_minor"] > limits["max_cost_minor"] or state_cost["currency"] != limits["currency"]:
        raise ContractValidationError("VideoJob cost exceeds or drifts from the approved limit.")
    for field_name in ("quote_ref", "approval_ref"):
        if state_cost[field_name] != request[field_name]:
            raise ContractValidationError(f"VideoJob cost {field_name} drift.")
    if result["counters"] != state_counters or result["cost"] != state_cost:
        raise ContractValidationError("VideoJob result counters and cost must match terminal state.")

    started_at = result["started_at"]
    completed_at = result["completed_at"]
    assert isinstance(started_at, str) and isinstance(completed_at, str)
    start = _parse_aware_timestamp(started_at, "VideoJob result start")
    completion = _parse_aware_timestamp(completed_at, "VideoJob result completion")
    requested_at = request["requested_at"]
    resolved_at = clarification["resolved_at"]
    created_at = plan["created_at"]
    assert isinstance(requested_at, str) and isinstance(resolved_at, str) and isinstance(created_at, str)
    request_time = _parse_aware_timestamp(requested_at, "VideoJob request")
    clarification_time = _parse_aware_timestamp(resolved_at, "VideoJob clarification")
    plan_time = _parse_aware_timestamp(created_at, "VideoJob plan")
    assert first_event_at is not None
    if not request_time <= clarification_time <= plan_time <= first_event_at:
        raise ContractValidationError("VideoJob request, clarification, plan, and lifecycle chronology is invalid.")
    expected_start = running_at if running_at is not None else first_event_at
    if start != expected_start or completion != previous_time or completion < start:
        raise ContractValidationError("VideoJob result timing must match running and terminal lifecycle evidence.")
    if completion - start > timedelta(seconds=limits["timeout_seconds"]):
        raise ContractValidationError("VideoJob result exceeds the approved timeout.")

    outcome = result["outcome"]
    if outcome == "succeeded" and running_at is None:
        raise ContractValidationError("VideoJob succeeded requires a running lifecycle event.")
    if outcome == "succeeded" and state_counters["executed_steps"] != len(steps):
        raise ContractValidationError("VideoJob succeeded executed_steps must equal all plan steps.")
    if outcome in {"failed", "unavailable"}:
        if state.get("error_class") is None or result.get("error_class") is None:
            raise ContractValidationError("VideoJob failed and unavailable outcomes require error_class.")
        if state["error_class"] != result["error_class"]:
            raise ContractValidationError("VideoJob error_class must match terminal state.")
    elif state.get("error_class") is not None or result.get("error_class") is not None:
        raise ContractValidationError("VideoJob non-error outcomes cannot carry error_class.")
    if outcome != "succeeded":
        return
    artifacts = result["artifacts"]
    assert isinstance(artifacts, list)
    artifact_kinds = {artifact["kind"] for artifact in artifacts if isinstance(artifact, Mapping)}
    artifact_refs = [artifact["artifact_ref"] for artifact in artifacts if isinstance(artifact, Mapping)]
    if not set(plan["declared_artifact_kinds"]).issubset(artifact_kinds):
        raise ContractValidationError("VideoJob success requires every declared media artifact.")
    if len(artifact_refs) != len(set(artifact_refs)) or len(artifacts) != state_counters["artifact_count"]:
        raise ContractValidationError("VideoJob success artifact identities and counter must be exact.")
    if sum(artifact["size_bytes"] for artifact in artifacts if isinstance(artifact, Mapping)) != state_counters["output_bytes"]:
        raise ContractValidationError("VideoJob success artifact sizes must equal output bytes.")
    if not result["evidence_refs"] or not result["log_refs"] or result.get("terminal_result_ref") is None:
        raise ContractValidationError("VideoJob success requires terminal result, evidence, and log references.")
    if set(result["satisfied_criteria"]) != set(plan["success_criteria"]):
        raise ContractValidationError("VideoJob success criteria must be satisfied exactly.")
