from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from shared.contracts.validate import (
    ContractValidationError,
    validate_agentfarm_bundle,
    validate_agentfarm_openfang_handoff_bundle,
    validate_agentfarm_runtime_admission_bundle,
    validate_document,
)


TOKEN = "0" * 26


def ref(kind: str, suffix: str = "") -> str:
    return f"{kind}_v1_{TOKEN[:-len(suffix)] if suffix else TOKEN}{suffix}"


def valid_bundle() -> dict[str, dict[str, object]]:
    request = {
        "contract_version": "v1", "request_id": ref("request"), "brain_plan_ref": ref("plan"),
        "task_ref": ref("task"), "project_ref": ref("project"), "trace_id": ref("trace"),
        "space_id": "agentfarm", "objective": "Create a bounded offline team plan.",
        "requested_at": "2026-07-31T10:00:00Z",
        "clarification": {"status": "resolved", "questions": [], "resolved_at": "2026-07-31T10:00:00Z"},
        "risk_class": "medium",
        "hard_bounds": {"timeout_seconds": 600, "max_steps": 12, "max_retries": 2, "max_cost_minor": 5000, "currency": "EUR", "max_concurrency": 2, "max_team_members": 2},
        "quote_ref": ref("quote"), "approval_ref": ref("approval"), "idempotency_key": "agentfarm-contract-0001",
    }
    plan = {
        "contract_version": "v1", "plan_id": ref("plan"), "plan_version": 1,
        "plan_hash": "sha256:" + "a" * 64, "request_id": request["request_id"],
        "brain_plan_ref": request["brain_plan_ref"], "task_ref": request["task_ref"],
        "project_ref": request["project_ref"], "trace_id": request["trace_id"], "space_id": "agentfarm",
        "created_at": "2026-07-31T10:01:00Z", "plan_artifact_ref": ref("artifact"),
        "plan_evidence_refs": [ref("evidence")], "max_concurrency": 2,
        "members": [
            {"member_id": "planner", "role": "planner", "capability_refs": [ref("capability")], "max_concurrency": 1},
            {"member_id": "reviewer", "role": "reviewer", "capability_refs": [ref("capability", "A")], "max_concurrency": 1},
        ],
        "tasks": [
            {"task_id": "draft", "member_id": "planner", "capability_ref": ref("capability"), "depends_on": [], "order": 1, "required": True},
            {"task_id": "review", "member_id": "reviewer", "capability_ref": ref("capability", "A"), "depends_on": ["draft"], "order": 2, "required": True},
        ],
    }
    run_request = {
        "contract_version": "v1", "run_id": ref("run"), "plan_id": plan["plan_id"], "plan_version": 1,
        "plan_hash": plan["plan_hash"], "request_id": request["request_id"], "task_ref": request["task_ref"],
        "project_ref": request["project_ref"], "trace_id": request["trace_id"], "space_id": "agentfarm",
        "mode": "dry_run", "input_artifact_refs": [ref("artifact", "A")], "input_evidence_refs": [ref("evidence", "A")],
        "timeout_seconds": 300, "max_steps": 8, "max_retries": 1, "max_concurrency": 2,
        "max_cost_minor": 2500, "currency": "EUR", "quote_ref": request["quote_ref"],
        "approval_ref": request["approval_ref"], "idempotency_key": request["idempotency_key"],
    }
    event = {
        "contract_version": "v1", "event_id": ref("event"), "run_id": run_request["run_id"], "plan_id": plan["plan_id"],
        "plan_version": 1, "plan_hash": plan["plan_hash"], "member_id": "reviewer", "task_id": "review",
        "revision": 3, "occurred_at": "2026-07-31T10:04:00Z", "status": "succeeded", "dependency_refs": ["draft"],
        "executed_steps": 4, "retry_count": 0, "actual_cost_minor": 1500,
        "evidence_refs": [ref("evidence", "B")], "artifact_refs": [ref("artifact", "B")], "log_refs": [ref("log")],
    }
    state = {
        "contract_version": "v1", "run_id": run_request["run_id"], "plan_id": plan["plan_id"], "plan_version": 1,
        "plan_hash": plan["plan_hash"], "request_id": request["request_id"], "task_ref": request["task_ref"],
        "project_ref": request["project_ref"], "trace_id": request["trace_id"], "space_id": "agentfarm", "mode": "dry_run",
        "revision": 3, "status": "succeeded", "event_history": [
            {"status": "queued", "occurred_at": "2026-07-31T10:01:00Z", "revision": 1},
            {"status": "running", "occurred_at": "2026-07-31T10:02:00Z", "revision": 2},
            {"status": "succeeded", "occurred_at": "2026-07-31T10:04:00Z", "revision": 3},
        ],
        "task_states": [{"task_id": "draft", "status": "succeeded"}, {"task_id": "review", "status": "succeeded"}],
        "counters": {"executed_steps": 8, "max_steps": 8, "retry_count": 0, "max_retries": 1, "active_members": 0, "max_concurrency": 2, "completed_tasks": 2, "total_tasks": 2},
        "cancellation_requested": False, "actual_cost_minor": 2500, "max_cost_minor": 2500, "currency": "EUR",
        "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"],
        "evidence_refs": [ref("evidence", "B")], "artifact_refs": [ref("artifact", "B")], "log_refs": [ref("log")],
    }
    evidence = {
        "contract_version": "v1", "run_id": run_request["run_id"], "plan_id": plan["plan_id"], "plan_version": 1,
        "plan_hash": plan["plan_hash"], "request_id": request["request_id"], "task_ref": request["task_ref"],
        "project_ref": request["project_ref"], "trace_id": request["trace_id"], "space_id": "agentfarm", "mode": "dry_run",
        "outcome": "succeeded", "started_at": "2026-07-31T10:02:00Z", "completed_at": "2026-07-31T10:04:00Z",
        "member_summaries": [{"member_id": "planner", "status": "succeeded"}, {"member_id": "reviewer", "status": "succeeded"}],
        "task_summaries": [{"task_id": "draft", "status": "succeeded"}, {"task_id": "review", "status": "succeeded"}],
        "executed_steps": 8, "evidence_refs": state["evidence_refs"], "artifact_refs": state["artifact_refs"], "log_refs": state["log_refs"],
        "actual_cost_minor": 2500, "currency": "EUR", "quote_ref": request["quote_ref"], "approval_ref": request["approval_ref"],
    }
    return {"agent-team-request": request, "agent-team-plan": plan, "agent-team-run-request": run_request, "agent-task-event": event, "agent-team-run-state": state, "agent-team-run-evidence": evidence}


def valid_runtime_admission_bundle() -> dict[str, dict[str, object]]:
    request = valid_bundle()["agent-team-request"]
    provenance = {
        "contract_version": "v1",
        "provenance_id": ref("source"),
        "request_id": request["request_id"],
        "space_id": "agentfarm",
        "repository": {
            "repository_id": ref("repository"),
            "canonical_identity": "github.com/Flissel/Autogen_AgentFarm",
            "identity_digest": "",
        },
        "revision": {
            "kind": "commit",
            "commit_sha": "2" * 40,
            "tree_sha": "3" * 40,
            "source_tree_digest": "sha256:" + "4" * 64,
        },
        "entrypoint": {
            "path": "src/agentfarm/main.py",
            "digest": "sha256:" + "5" * 64,
        },
        "build_manifest": {
            "path": "pyproject.toml",
            "digest": "sha256:" + "6" * 64,
        },
        "record_digest": "",
        "captured_at": "2026-08-04T10:00:00Z",
    }
    canonical_identity = provenance["repository"]["canonical_identity"]
    provenance["repository"]["identity_digest"] = (
        "sha256:" + hashlib.sha256(canonical_identity.encode("utf-8")).hexdigest()
    )
    digest_input = deepcopy(provenance)
    del digest_input["record_digest"]
    canonical_record = json.dumps(
        digest_input,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    provenance["record_digest"] = "sha256:" + hashlib.sha256(canonical_record).hexdigest()
    return {
        "agent-team-request": request,
        "agentfarm-runtime-source-provenance": provenance,
    }


def valid_openfang_handoff_bundle() -> dict[str, object]:
    bundle = valid_runtime_admission_bundle()
    request = bundle["agent-team-request"]
    provenance = bundle["agentfarm-runtime-source-provenance"]
    channel_intent = {
        "contract_version": "v1",
        "correlation_id": ref("event"),
        "channel_kind": "desktop-chat",
        "actor_context": {"actor_id": "user:local-42", "locale": "de-DE"},
        "session_context": {
            "session_id": "session-agentfarm-0006",
            "conversation_id": "agentfarm-openfang-handoff",
        },
        "message": "Run the admitted AgentFarm task.",
        "received_at": "2026-07-31T09:59:00Z",
        "requested_space_id": "agentfarm",
        "user_facing_expectations": {"reply": "required", "evidence": "references"},
    }
    brain_plan = {
        "contract_version": "v1",
        "plan_id": request["brain_plan_ref"],
        "intent": {
            "summary": "Route one admitted AgentFarm task.",
            "context": ["The AgentFarm source has separate offline provenance."],
            "requested_by": "product-owner",
        },
        "participating_spaces": [
            {
                "space_id": "agentfarm",
                "roles": [{"role": "agent-team", "required_agent_count": 1}],
            }
        ],
        "tasks": [
            {
                "node_id": "route-agentfarm",
                "order": 1,
                "summary": "Route the task to AgentFarm through OpenFang.",
                "space_ids": ["agentfarm"],
                "depends_on": [],
                "success_criteria": ["The handoff remains pending OpenFang admission."],
                "evidence_requirements": [
                    {
                        "evidence_type": "external-record",
                        "description": "A separately authorized OpenFang receipt is required.",
                    }
                ],
            }
        ],
    }
    space_execution_contract = {
        "contract_version": "v1",
        "contract_id": f"space_execution_contract_v1_{TOKEN}",
        "space_id": "agentfarm",
        "executor_id": "executor:openfang",
        "approval_policy_ref": "approval-policy:openfang",
        "cost_policy_ref": "cost-policy:openfang",
        "healthcheck_ref": "healthcheck:agentfarm-structural",
        "golden_path_ref": "golden-path:agentfarm-handoff",
    }
    bundle["agentfarm-openfang-handoff-admission"] = {
        "contract_version": "v1",
        "handoff_id": ref("handoff"),
        "request_id": request["request_id"],
        "task_ref": request["task_ref"],
        "brain_task_node_id": "route-agentfarm",
        "source_provenance_id": provenance["provenance_id"],
        "trace_id": request["trace_id"],
        "correlation_id": channel_intent["correlation_id"],
        "space_id": "agentfarm",
        "executor": "openfang",
        "handoff_status": "pending_openfang_admission",
        "approval_ref": request["approval_ref"],
        "quote_ref": request["quote_ref"],
        "idempotency_key": request["idempotency_key"],
        "issued_at": "2026-08-04T10:01:00Z",
        "execution_boundary": {
            "direct_provider_access": False,
            "direct_application_access": False,
            "fallback_allowed": False,
        },
    }
    bundle["channel-intent"] = channel_intent
    bundle["brain-plan"] = brain_plan
    bundle["space-execution-contracts"] = [space_execution_contract]
    return bundle


def test_accepts_exact_agentfarm_openfang_handoff_admission_bundle() -> None:
    bundle = valid_openfang_handoff_bundle()

    validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_openfang_handoff_without_admitted_brain_plan() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agent-team-request"]["brain_plan_ref"] = ref("plan", "A")

    with pytest.raises(ContractValidationError, match="Brain"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_unmapped_agentfarm_request_task_ref() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agent-team-request"]["task_ref"] = ref("task", "A")

    with pytest.raises(ContractValidationError, match="task_ref"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_openfang_handoff_correlation_drift() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"]["correlation_id"] = ref(
        "event", "A"
    )

    with pytest.raises(ContractValidationError, match="correlation_id"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_non_agentfarm_channel_route() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["channel-intent"]["requested_space_id"] = "research"
    bundle["brain-plan"]["participating_spaces"].append(
        {
            "space_id": "research",
            "roles": [{"role": "researcher", "required_agent_count": 1}],
        }
    )
    bundle["brain-plan"]["tasks"].append(
        {
            "node_id": "research-context",
            "order": 2,
            "summary": "Research additional context.",
            "space_ids": ["research"],
            "depends_on": ["route-agentfarm"],
            "success_criteria": ["Research context is separately evidenced."],
            "evidence_requirements": [
                {
                    "evidence_type": "artifact",
                    "description": "A research artifact is required.",
                }
            ],
        }
    )
    bundle["space-execution-contracts"].append(
        {
            "contract_version": "v1",
            "contract_id": f"space_execution_contract_v1_{'A' + TOKEN[1:]}",
            "space_id": "research",
            "executor_id": "executor:openfang",
            "approval_policy_ref": "approval-policy:openfang",
            "cost_policy_ref": "cost-policy:openfang",
            "healthcheck_ref": "healthcheck:research-structural",
            "golden_path_ref": "golden-path:research-query",
        }
    )

    with pytest.raises(ContractValidationError, match="requested Brain route"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_selected_brain_task_without_agentfarm_route() -> None:
    bundle = valid_openfang_handoff_bundle()
    brain_plan = bundle["brain-plan"]
    brain_plan["participating_spaces"].append(
        {
            "space_id": "research",
            "roles": [{"role": "researcher", "required_agent_count": 1}],
        }
    )
    brain_plan["tasks"][0]["space_ids"] = ["research"]
    brain_plan["tasks"].append(
        {
            "node_id": "other-agentfarm-task",
            "order": 2,
            "summary": "Retain an unrelated AgentFarm task.",
            "space_ids": ["agentfarm"],
            "depends_on": ["route-agentfarm"],
            "success_criteria": ["The unrelated task remains separately admitted."],
            "evidence_requirements": [
                {
                    "evidence_type": "external-record",
                    "description": "Separate evidence is required.",
                }
            ],
        }
    )
    bundle["space-execution-contracts"].append(
        {
            "contract_version": "v1",
            "contract_id": f"space_execution_contract_v1_{'A' + TOKEN[1:]}",
            "space_id": "research",
            "executor_id": "executor:openfang",
            "approval_policy_ref": "approval-policy:openfang",
            "cost_policy_ref": "cost-policy:openfang",
            "healthcheck_ref": "healthcheck:research-structural",
            "golden_path_ref": "golden-path:research-query",
        }
    )

    with pytest.raises(ContractValidationError, match="selected admitted Brain task"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_missing_brain_task_node_selection() -> None:
    bundle = valid_openfang_handoff_bundle()
    del bundle["agentfarm-openfang-handoff-admission"]["brain_task_node_id"]

    with pytest.raises(ContractValidationError, match="brain_task_node_id"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_unknown_brain_task_node_selection() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"]["brain_task_node_id"] = (
        "missing-agentfarm-task"
    )

    with pytest.raises(ContractValidationError, match="exactly one"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_duplicate_selected_brain_task_node() -> None:
    bundle = valid_openfang_handoff_bundle()
    duplicate_task = deepcopy(bundle["brain-plan"]["tasks"][0])
    duplicate_task["order"] = 2
    bundle["brain-plan"]["tasks"].append(duplicate_task)

    with pytest.raises(ContractValidationError, match="duplicate task node_id"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_non_openfang_agentfarm_execution_contract() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["space-execution-contracts"][0]["executor_id"] = (
        "executor:brain-orchestrator"
    )

    with pytest.raises(ContractValidationError, match="OpenFang"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


@pytest.mark.parametrize(
    ("field_name", "different_value"),
    (
        ("approval_policy_ref", "approval-policy:standard"),
        ("cost_policy_ref", "cost-policy:bounded"),
    ),
)
def test_rejects_non_openfang_agentfarm_policy_contract(
    field_name: str, different_value: str,
) -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["space-execution-contracts"][0][field_name] = different_value

    with pytest.raises(ContractValidationError, match="OpenFang policy"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_request_before_channel_intent() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["channel-intent"]["received_at"] = "2026-07-31T10:00:01Z"

    with pytest.raises(ContractValidationError, match="precede"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


@pytest.mark.parametrize(
    ("field_name", "different_value"),
    (
        ("request_id", ref("request", "A")),
        ("task_ref", ref("task", "A")),
        ("trace_id", ref("trace", "A")),
        ("approval_ref", ref("approval", "A")),
        ("quote_ref", ref("quote", "A")),
        ("idempotency_key", "agentfarm-contract-0002"),
    ),
)
def test_rejects_agentfarm_openfang_handoff_request_continuity_drift(
    field_name: str, different_value: str,
) -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"][field_name] = different_value

    with pytest.raises(ContractValidationError, match=field_name):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_noncanonical_agentfarm_openfang_handoff_space() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"]["space_id"] = "autogen"

    with pytest.raises(ContractValidationError, match="space_id"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_openfang_handoff_source_provenance_drift() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"]["source_provenance_id"] = ref(
        "source", "A"
    )

    with pytest.raises(ContractValidationError, match="source_provenance_id"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("executor", "application"),
        ("handoff_status", "dispatched"),
        ("execution_boundary.direct_provider_access", True),
        ("execution_boundary.direct_application_access", True),
        ("execution_boundary.fallback_allowed", True),
    ),
)
def test_rejects_agentfarm_openfang_handoff_execution_boundary_drift(
    field_name: str, value: object
) -> None:
    bundle = valid_openfang_handoff_bundle()
    handoff = bundle["agentfarm-openfang-handoff-admission"]
    if "." in field_name:
        section, nested_field = field_name.split(".")
        handoff[section][nested_field] = value
    else:
        handoff[field_name] = value

    with pytest.raises(ContractValidationError):
        validate_agentfarm_openfang_handoff_bundle(bundle)


@pytest.mark.parametrize("forbidden_field", ("provider", "application", "endpoint"))
def test_rejects_agentfarm_openfang_handoff_direct_execution_fields(
    forbidden_field: str,
) -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"][forbidden_field] = "not allowed"

    with pytest.raises(ContractValidationError):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_openfang_handoff_before_source_capture() -> None:
    bundle = valid_openfang_handoff_bundle()
    bundle["agentfarm-openfang-handoff-admission"]["issued_at"] = "2026-08-04T09:59:59Z"

    with pytest.raises(ContractValidationError, match="cannot predate"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_agentfarm_openfang_handoff_with_wrong_document_set() -> None:
    bundle = valid_openfang_handoff_bundle()
    del bundle["agentfarm-runtime-source-provenance"]

    with pytest.raises(ContractValidationError, match="exactly"):
        validate_agentfarm_openfang_handoff_bundle(bundle)


def test_rejects_legacy_three_document_openfang_handoff_bundle() -> None:
    bundle = valid_openfang_handoff_bundle()
    legacy_bundle = {
        document_type: bundle[document_type]
        for document_type in (
            "agent-team-request",
            "agentfarm-runtime-source-provenance",
            "agentfarm-openfang-handoff-admission",
        )
    }

    with pytest.raises(ContractValidationError, match="exactly"):
        validate_agentfarm_openfang_handoff_bundle(legacy_bundle)


def test_accepts_agentfarm_runtime_source_provenance_admission_bundle() -> None:
    bundle = valid_runtime_admission_bundle()
    validate_document(
        "agentfarm-runtime-source-provenance",
        bundle["agentfarm-runtime-source-provenance"],
    )
    validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize("revision_kind", ["branch", "tag"])
def test_rejects_mutable_agentfarm_runtime_source_revision(revision_kind: str) -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["revision"]["kind"] = revision_kind

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_agentfarm_runtime_source_without_full_commit_sha() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["revision"]["commit_sha"] = "2" * 7

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize(
    "entrypoint_path",
    ["../main.py", "src/../main.py", "/src/main.py", "src\\main.py"],
)
def test_rejects_unsafe_agentfarm_runtime_entrypoint(entrypoint_path: str) -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["entrypoint"]["path"] = entrypoint_path

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize(
    ("section", "digest_field"),
    [
        ("repository", "identity_digest"),
        ("revision", "tree_sha"),
        ("revision", "source_tree_digest"),
        ("entrypoint", "digest"),
        ("build_manifest", "digest"),
        (None, "record_digest"),
    ],
)
def test_rejects_agentfarm_runtime_source_with_missing_digest(
    section: str | None, digest_field: str
) -> None:
    bundle = valid_runtime_admission_bundle()
    provenance = bundle["agentfarm-runtime-source-provenance"]
    target = provenance if section is None else provenance[section]
    del target[digest_field]

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize(
    ("document_type", "field", "value"),
    [
        ("agentfarm-runtime-source-provenance", "space_id", "autogen"),
        ("agentfarm-runtime-source-provenance", "request_id", ref("request", "A")),
        ("agent-team-request", "request_id", ref("request", "A")),
    ],
)
def test_rejects_agentfarm_runtime_admission_identity_drift(
    document_type: str, field: str, value: str
) -> None:
    bundle = valid_runtime_admission_bundle()
    bundle[document_type][field] = value

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_agentfarm_runtime_admission_with_wrong_document_set() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agent-team-plan"] = valid_bundle()["agent-team-plan"]

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_agentfarm_runtime_source_captured_before_request() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["captured_at"] = "2026-07-31T09:59:59Z"

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_agentfarm_repository_identity_digest_drift() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["repository"][
        "canonical_identity"
    ] = "github.com/Flissel/Different_AgentFarm"

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("revision", "commit_sha", "8" * 40),
        ("revision", "tree_sha", "9" * 40),
        ("entrypoint", "path", "src/agentfarm/worker.py"),
        ("build_manifest", "path", "requirements.lock"),
    ],
)
def test_rejects_agentfarm_provenance_content_drift_without_new_record_digest(
    section: str, field: str, value: str
) -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"][section][field] = value

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_agentfarm_clarification_resolved_before_request() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agent-team-request"]["clarification"]["resolved_at"] = (
        "2026-07-31T09:59:59Z"
    )

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_unresolved_agentfarm_runtime_admission() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agent-team-request"]["clarification"] = {
        "status": "required",
        "questions": ["Which bounded source should be admitted?"],
        "resolved_at": None,
    }

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def test_runtime_provenance_does_not_extend_legacy_agentfarm_bundle() -> None:
    execution_bundle = valid_bundle()
    execution_bundle["agentfarm-runtime-source-provenance"] = (
        valid_runtime_admission_bundle()["agentfarm-runtime-source-provenance"]
    )

    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(execution_bundle)


def test_runtime_source_git_objects_are_not_live_verified_by_offline_contract() -> None:
    bundle = valid_runtime_admission_bundle()
    provenance = bundle["agentfarm-runtime-source-provenance"]
    provenance["revision"]["commit_sha"] = "a" * 40
    provenance["revision"]["tree_sha"] = "b" * 40
    digest_input = deepcopy(provenance)
    del digest_input["record_digest"]
    provenance["record_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            digest_input,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    validate_agentfarm_runtime_admission_bundle(bundle)


def test_rejects_unsafe_agentfarm_build_manifest_path() -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"]["build_manifest"]["path"] = (
        "../pyproject.toml"
    )

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


@pytest.mark.parametrize("field", ["url", "command", "credential", "token"])
def test_rejects_agentfarm_runtime_source_authority_fields(field: str) -> None:
    bundle = valid_runtime_admission_bundle()
    bundle["agentfarm-runtime-source-provenance"][field] = "not allowed"

    with pytest.raises(ContractValidationError):
        validate_agentfarm_runtime_admission_bundle(bundle)


def mutate(document: str, path: tuple[object, ...], value: object) -> dict[str, dict[str, object]]:
    bundle = deepcopy(valid_bundle())
    target: object = bundle[document]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]
    return bundle


def test_accepts_the_exact_offline_six_document_bundle() -> None:
    validate_agentfarm_bundle(valid_bundle())


def test_accepts_each_valid_document() -> None:
    for document_type, document in valid_bundle().items():
        validate_document(document_type, document)


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("agent-team-request", ("space_id",), "autogen"),
        ("agent-team-plan", ("members",), [valid_bundle()["agent-team-plan"]["members"][0]] * 2),
        ("agent-team-plan", ("tasks", 1, "member_id"), "unknown"),
        ("agent-team-plan", ("tasks", 1, "depends_on"), ["unknown"]),
        ("agent-team-run-state", ("task_states", 1, "task_id"), "unknown"),
        ("agent-team-plan", ("tasks", 0, "depends_on"), ["review"]),
        ("agent-team-plan", ("tasks", 1, "order"), 1),
        ("agent-team-plan", ("max_concurrency",), 3),
        ("agent-team-plan", ("plan_hash",), "sha256:" + "b" * 64),
        ("agent-team-request", ("clarification", "status"), "required"),
        ("agent-team-run-state", ("event_history", 2, "status"), "running"),
        ("agent-team-run-state", ("event_history", 2, "occurred_at"), "2026-07-31T10:01:30Z"),
        ("agent-team-run-state", ("revision",), 4),
        ("agent-team-run-state", ("cancellation_requested",), True),
        ("agent-team-run-state", ("task_states", 1, "status"), "failed"),
        ("agent-team-run-evidence", ("evidence_refs",), []),
        ("agent-team-run-evidence", ("approval_ref",), ref("approval", "A")),
        ("agent-team-run-evidence", ("actual_cost_minor",), 2500.5),
        ("agent-team-run-request", ("max_steps",), 13),
    ],
)
def test_rejects_invalid_bundle_drift(document: str, path: tuple[object, ...], value: object) -> None:
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(mutate(document, path, value))


@pytest.mark.parametrize("field", ["provider", "model", "credential", "secret", "token", "api_key", "runtime", "url", "webhook", "endpoint", "command", "shell", "db", "connection", "prompt", "code", "inline_agent"])
def test_rejects_forbidden_runtime_and_secret_fields(field: str) -> None:
    bundle = valid_bundle()
    bundle["agent-team-plan"][field] = "not allowed"
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(bundle)


def test_rejects_failed_event_without_redacted_error_class() -> None:
    bundle = valid_bundle()
    bundle["agent-task-event"]["status"] = "failed"
    with pytest.raises(ContractValidationError):
        validate_document("agent-task-event", bundle["agent-task-event"])


def test_rejects_bundle_with_wrong_document_set() -> None:
    bundle = valid_bundle()
    del bundle["agent-task-event"]
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(bundle)


@pytest.mark.parametrize(
    ("document", "path", "value"),
    [
        ("agent-team-request", ("hard_bounds", "max_team_members"), 1),
        ("agent-team-request", ("hard_bounds", "max_steps"), 1),
        ("agent-team-request", ("hard_bounds", "max_concurrency"), 1),
        ("agent-team-plan", ("members", 0, "max_concurrency"), 3),
        ("agent-team-run-state", ("event_history", 0, "status"), "running"),
        ("agent-team-run-state", ("counters", "completed_tasks"), 1),
        ("agent-team-run-state", ("counters", "active_members"), 1),
        ("agent-team-run-evidence", ("started_at",), "2026-07-31T10:00:59Z"),
        ("agent-task-event", ("occurred_at",), "2026-07-31T10:01:59Z"),
        ("agent-task-event", ("executed_steps",), 9),
        ("agent-task-event", ("retry_count",), 2),
        ("agent-task-event", ("actual_cost_minor",), 2501),
        ("agent-task-event", ("evidence_refs",), [ref("evidence", "A")]),
        ("agent-team-run-evidence", ("member_summaries", 0, "status"), "failed"),
    ],
)
def test_rejects_reviewed_bound_and_terminal_invariants(
    document: str, path: tuple[object, ...], value: object
) -> None:
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(mutate(document, path, value))


def test_accepts_offset_equivalent_terminal_timestamp() -> None:
    bundle = mutate(
        "agent-team-run-state", ("event_history", 2, "occurred_at"), "2026-07-31T12:04:00+02:00"
    )
    validate_agentfarm_bundle(bundle)


def test_accepts_offset_equivalent_running_timestamp_at_execution_start() -> None:
    bundle = mutate(
        "agent-team-run-state", ("event_history", 1, "occurred_at"), "2026-07-31T12:02:00+02:00"
    )
    validate_agentfarm_bundle(bundle)


def test_rejects_running_lifecycle_event_after_evidence_start() -> None:
    bundle = mutate(
        "agent-team-run-state", ("event_history", 1, "occurred_at"), "2026-07-31T10:03:00Z"
    )
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(bundle)


def test_accepts_unresolved_request_clarification_before_execution() -> None:
    request = valid_bundle()["agent-team-request"]
    request["clarification"] = {"status": "required", "questions": ["Which audience?"], "resolved_at": None}
    validate_document("agent-team-request", request)


def test_rejects_resolved_request_without_aware_resolution_time() -> None:
    request = valid_bundle()["agent-team-request"]
    request["clarification"] = {"status": "resolved", "questions": [], "resolved_at": None}
    with pytest.raises(ContractValidationError):
        validate_document("agent-team-request", request)


def test_rejects_succeeded_task_event_when_dependency_is_not_succeeded() -> None:
    bundle = valid_bundle()
    bundle["agent-team-run-state"]["status"] = "failed"
    bundle["agent-team-run-state"]["event_history"][2]["status"] = "failed"
    bundle["agent-team-run-state"]["task_states"] = [
        {"task_id": "draft", "status": "failed"}, {"task_id": "review", "status": "succeeded"}
    ]
    bundle["agent-team-run-evidence"]["outcome"] = "failed"
    bundle["agent-team-run-evidence"]["error_class"] = "execution_failed"
    bundle["agent-team-run-evidence"]["task_summaries"] = [
        {"task_id": "draft", "status": "failed"}, {"task_id": "review", "status": "succeeded"}
    ]
    bundle["agent-team-run-evidence"]["member_summaries"] = [
        {"member_id": "planner", "status": "failed"}, {"member_id": "reviewer", "status": "unavailable"}
    ]
    bundle["agent-task-event"]["status"] = "succeeded"
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(bundle)


def test_rejects_member_summary_that_conflicts_with_owned_task_states() -> None:
    bundle = valid_bundle()
    bundle["agent-team-run-state"]["status"] = "failed"
    bundle["agent-team-run-state"]["event_history"][2]["status"] = "failed"
    bundle["agent-team-run-state"]["task_states"] = [
        {"task_id": "draft", "status": "failed"}, {"task_id": "review", "status": "failed"}
    ]
    bundle["agent-team-run-evidence"]["outcome"] = "failed"
    bundle["agent-team-run-evidence"]["error_class"] = "execution_failed"
    bundle["agent-team-run-evidence"]["task_summaries"] = [
        {"task_id": "draft", "status": "failed"}, {"task_id": "review", "status": "failed"}
    ]
    bundle["agent-team-run-evidence"]["member_summaries"] = [
        {"member_id": "planner", "status": "failed"}, {"member_id": "reviewer", "status": "succeeded"}
    ]
    bundle["agent-task-event"]["status"] = "failed"
    bundle["agent-task-event"]["error_class"] = "execution_failed"
    with pytest.raises(ContractValidationError):
        validate_agentfarm_bundle(bundle)


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_rejects_terminal_evidence_without_redacted_error_class(status: str) -> None:
    evidence = valid_bundle()["agent-team-run-evidence"]
    evidence["outcome"] = status
    with pytest.raises(ContractValidationError):
        validate_document("agent-team-run-evidence", evidence)
