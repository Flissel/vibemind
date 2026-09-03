from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from shared.contracts import validate as contract_validation
from shared.contracts.validate import ContractValidationError, validate_document


FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_TYPES = (
    ("research-request", "research_request"),
    ("research-plan", "research_plan"),
    ("research-job", "research_job"),
    ("source-evidence", "source_evidence"),
    ("citation", "citation"),
    ("research-result", "research_result"),
    ("research-idea-handoff", "research_idea_handoff"),
)

STATUS_PROVENANCE_CASES = (
    ("pause", "paused", "chat"),
    ("resume", "queued", "brain"),
    ("cancel", "cancelled", "research_space"),
    ("complete", "succeeded", "chat"),
    ("fail", "failed", "brain"),
    ("mark_unavailable", "unavailable", "research_space"),
)
STATUS_PROVENANCE_TARGETS = {
    action: status for action, status, _actor in STATUS_PROVENANCE_CASES
}
RESEARCH_JOB_STATUSES = (
    "clarification_required",
    "queued",
    "running",
    "waiting_for_approval",
    "paused",
    "succeeded",
    "failed",
    "cancelled",
    "unavailable",
)


def load_fixture(category: str, name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / category / f"{name}.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def validate_bundle(bundle: dict[str, dict[str, object]]) -> None:
    validator = getattr(contract_validation, "validate_research_bundle", None)
    assert callable(validator), "Research bundle validation is not registered."
    validator(bundle)


def valid_bundle() -> dict[str, dict[str, object]]:
    return {
        document_type: load_fixture("valid", fixture_name)
        for document_type, fixture_name in VALID_TYPES
    }


def research_job_with_transition_context(
    *, status: str, actor: str, action: str
) -> dict[str, object]:
    job = load_fixture("valid", "research_job")
    job["status"] = status
    job["status_history"] = [
        {
            "status": status,
            "occurred_at": "2026-07-31T09:10:10Z",
            "transition_context": {"actor": actor, "action": action},
        }
    ]
    return job


@pytest.mark.parametrize(
    ("action", "status", "actor"), STATUS_PROVENANCE_CASES
)
def test_research_job_accepts_closed_chat_status_provenance(
    action: str, status: str, actor: str
) -> None:
    validate_document(
        "research-job",
        research_job_with_transition_context(
            status=status, actor=actor, action=action
        ),
    )


def test_research_job_without_transition_context_remains_valid() -> None:
    validate_document("research-job", load_fixture("valid", "research_job"))


@pytest.mark.parametrize("actor", ("unknown", "provider", "runtime"))
def test_research_job_rejects_unknown_transition_actor(actor: str) -> None:
    job = research_job_with_transition_context(
        status="paused", actor=actor, action="pause"
    )

    with pytest.raises(ContractValidationError, match="actor"):
        validate_document("research-job", job)


def test_research_job_rejects_unknown_transition_action() -> None:
    job = research_job_with_transition_context(
        status="paused", actor="chat", action="retry"
    )

    with pytest.raises(ContractValidationError, match="action"):
        validate_document("research-job", job)


@pytest.mark.parametrize("missing_field", ("actor", "action"))
def test_research_job_rejects_missing_transition_context_field(
    missing_field: str,
) -> None:
    job = research_job_with_transition_context(
        status="paused", actor="chat", action="pause"
    )
    history = job["status_history"]
    assert isinstance(history, list)
    record = history[0]
    assert isinstance(record, dict)
    context = record["transition_context"]
    assert isinstance(context, dict)
    del context[missing_field]

    with pytest.raises(ContractValidationError, match=missing_field):
        validate_document("research-job", job)


def test_research_job_rejects_foreign_transition_context_field() -> None:
    job = research_job_with_transition_context(
        status="paused", actor="chat", action="pause"
    )
    history = job["status_history"]
    assert isinstance(history, list)
    record = history[0]
    assert isinstance(record, dict)
    context = record["transition_context"]
    assert isinstance(context, dict)
    context["reason"] = "inferred by a consumer"

    with pytest.raises(ContractValidationError, match="reason"):
        validate_document("research-job", job)


@pytest.mark.parametrize(
    ("action", "status"),
    tuple(
        (action, status)
        for action, expected_status in STATUS_PROVENANCE_TARGETS.items()
        for status in RESEARCH_JOB_STATUSES
        if status != expected_status
    ),
)
def test_research_job_rejects_every_action_status_mismatch(
    action: str, status: str
) -> None:
    job = research_job_with_transition_context(
        status=status, actor="chat", action=action
    )

    with pytest.raises(ContractValidationError, match="status"):
        validate_document("research-job", job)


@pytest.mark.parametrize(("document_type", "fixture_name"), VALID_TYPES)
def test_valid_research_v1_contract_fixtures_validate(
    document_type: str, fixture_name: str
) -> None:
    validate_document(document_type, load_fixture("valid", fixture_name))


def test_valid_research_result_and_idea_handoff_chain_validates_offline() -> None:
    bundle = {
        document_type: load_fixture("valid", fixture_name)
        for document_type, fixture_name in VALID_TYPES
    }

    validate_bundle(bundle)


@pytest.mark.parametrize(
    ("document_type", "fixture_name"),
    (
        ("research-result", "succeeded_without_evidence"),
        ("research-plan", "unbounded_collection"),
        ("research-request", "excessive_collection"),
        ("research-job", "unknown_lifecycle"),
        ("source-evidence", "invalid_source_url"),
        ("source-evidence", "invalid_content_hash"),
        ("source-evidence", "invalid_retrieved_at"),
        ("research-request", "float_cost"),
        ("research-idea-handoff", "unapproved_idea_handoff"),
        ("research-request", "free_provider_field"),
        ("research-request", "free_credential_field"),
        ("research-job", "free_runtime_field"),
    ),
)
def test_invalid_research_v1_documents_are_rejected(
    document_type: str, fixture_name: str
) -> None:
    with pytest.raises(ContractValidationError):
        validate_document(document_type, load_fixture("invalid", fixture_name))


def test_orphaned_citation_is_rejected_by_the_offline_bundle_validator() -> None:
    bundle = {
        document_type: load_fixture("valid", fixture_name)
        for document_type, fixture_name in VALID_TYPES
    }
    bundle["citation"] = load_fixture("invalid", "orphaned_citation")

    with pytest.raises(ContractValidationError, match="source evidence"):
        validate_bundle(bundle)


def test_result_must_reference_the_same_request_plan_and_job_as_the_bundle() -> None:
    bundle = {
        document_type: load_fixture("valid", fixture_name)
        for document_type, fixture_name in VALID_TYPES
    }
    result = bundle["research-result"]
    assert isinstance(result, dict)
    result["plan_id"] = "plan_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"

    with pytest.raises(ContractValidationError, match="plan_id"):
        validate_bundle(bundle)


def test_handoff_requires_a_succeeded_result_and_matching_evidence_reference() -> None:
    bundle = valid_bundle()
    result = bundle["research-result"]
    assert isinstance(result, dict)
    result["status"] = "failed"
    job = bundle["research-job"]
    assert isinstance(job, dict)
    job["status"] = "failed"
    history = job["status_history"]
    assert isinstance(history, list)
    final_record = history[-1]
    assert isinstance(final_record, dict)
    final_record["status"] = "failed"

    with pytest.raises(ContractValidationError, match="succeeded"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("currency", "USD"), ("quote_ref", "quote_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"), ("approval_ref", "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG")),
)
def test_plan_budget_must_match_the_request_budget_references(
    field_name: str, value: str
) -> None:
    bundle = valid_bundle()
    plan = bundle["research-plan"]
    assert isinstance(plan["budget"], dict)
    plan["budget"][field_name] = value

    with pytest.raises(ContractValidationError, match=field_name):
        validate_bundle(bundle)


def test_plan_budget_must_not_exceed_the_request_budget() -> None:
    bundle = valid_bundle()
    plan = bundle["research-plan"]
    assert isinstance(plan["budget"], dict)
    plan["budget"]["max_cost_minor"] = 501

    with pytest.raises(ContractValidationError, match="max_cost_minor"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("currency", "USD"), ("quote_ref", "quote_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG"), ("approval_ref", "approval_v1_01J8Q3Z4R5T6V7W8X9Y0ABCDEG")),
)
def test_result_cost_must_match_the_plan_budget_references(
    field_name: str, value: str
) -> None:
    bundle = valid_bundle()
    result = bundle["research-result"]
    assert isinstance(result["cost"], dict)
    result["cost"][field_name] = value

    with pytest.raises(ContractValidationError, match=field_name):
        validate_bundle(bundle)


@pytest.mark.parametrize("field_name", ("estimated_cost_minor", "actual_cost_minor"))
def test_result_cost_must_not_exceed_the_approved_plan_budget(field_name: str) -> None:
    bundle = valid_bundle()
    result = bundle["research-result"]
    assert isinstance(result["cost"], dict)
    result["cost"][field_name] = 501

    with pytest.raises(ContractValidationError, match=field_name):
        validate_bundle(bundle)


@pytest.mark.parametrize("field_name", ("request_id", "plan_id", "job_id"))
def test_result_rejects_embedded_source_evidence_with_foreign_references(
    field_name: str,
) -> None:
    result = load_fixture("valid", "research_result")
    sources = result["source_evidence"]
    assert isinstance(sources, list)
    assert isinstance(sources[0], dict)
    sources[0][field_name] = f"foreign-{field_name}"

    with pytest.raises(ContractValidationError, match=field_name):
        validate_document("research-result", result)


def test_source_evidence_rejects_url_userinfo_offline() -> None:
    source_evidence = load_fixture("valid", "source_evidence")
    source_evidence["source_url"] = "https://user:secret@example.org/research"

    with pytest.raises(ContractValidationError, match="userinfo"):
        validate_document("source-evidence", source_evidence)


def test_result_rejects_embedded_source_evidence_url_userinfo_offline() -> None:
    result = load_fixture("valid", "research_result")
    sources = result["source_evidence"]
    assert isinstance(sources, list)
    assert isinstance(sources[0], dict)
    sources[0]["source_url"] = "https://user:secret@example.org/research"

    with pytest.raises(ContractValidationError, match="userinfo"):
        validate_document("research-result", result)


@pytest.mark.parametrize("field_name", ("locator", "passage"))
def test_result_rejects_citation_that_does_not_match_its_source_evidence(
    field_name: str,
) -> None:
    result = load_fixture("valid", "research_result")
    citations = result["citations"]
    assert isinstance(citations, list)
    assert isinstance(citations[0], dict)
    citations[0][field_name] = f"different-{field_name}"

    with pytest.raises(ContractValidationError, match=field_name):
        validate_document("research-result", result)
