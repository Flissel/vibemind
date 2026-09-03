"""Offline contract tests for the Research service-tier declaration draft.

The declaration is data-only. These tests prove the draft says exactly what the
verified upstream sources say and nothing more: it may not invent depth or
output-style steps, may not re-introduce the superseded ad-hoc parameters as
subjects, and may not smuggle a runtime field into a declarative document.

Nothing here registers an event, mutates the Space agent registry, or executes
research. The declaration is explicitly unregistered.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "shared" / "contracts" / "research" / "v1"
DECLARATION = CONTRACTS / "research-service-tiers-v1.json"
IDEA_HANDOFF_SCHEMA = CONTRACTS / "research-idea-handoff-v1.schema.json"
RESULT_SCHEMA = CONTRACTS / "research-result-v1.schema.json"

# Verified at the pinned sources; see the provenance block of the declaration.
# Flissel/openfang @ 5d38662f9fa596c8f145e4f6a45a09edf4504837,
# crates/openfang-hands/bundled/researcher/HAND.toml
HAND_RESEARCH_DEPTH = ["quick", "thorough", "exhaustive"]
HAND_RESEARCH_DEPTH_DEFAULT = "thorough"
HAND_OUTPUT_STYLE = ["brief", "detailed", "academic", "executive"]
HAND_OUTPUT_STYLE_DEFAULT = "detailed"

# Flissel/vibemind-os @ c5cba961126523bed39d0d94e8fd0c982cb9cbe2,
# config/space_agent_registry.yml lines 162-176.
LEGACY_AD_HOC_PARAMS = ["idea_id", "query", "title"]
TODAY_LOOKUP_EVENTS = ["research.scrape", "research.web"]

SUBJECT_KINDS = ["bubble", "idea", "topic"]
TIERS = ["deep_research", "lookup"]

# D1 was resolved by E14 (task-research-0003); D2 and D3 are still the user's.
DECISIONS = ["D1", "D2", "D3"]

# shared/contracts/research/v1/research-idea-handoff-v1.schema.json, merged in #194.
IDEA_SUMMARY_MAX_LENGTH = 4000

FORBIDDEN_KEYS = {
    "api_key",
    "command",
    "credential",
    "credentials",
    "endpoint",
    "host",
    "password",
    "port",
    "provider",
    "secret",
    "token",
    "url",
}


@pytest.fixture(scope="module")
def declaration() -> dict[str, object]:
    assert DECLARATION.is_file(), f"service-tier declaration is missing: {DECLARATION}"
    value = json.loads(DECLARATION.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def walk_keys(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append(key)
            found.extend(walk_keys(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(walk_keys(value))
    return found


# ── The declaration binds nothing ───────────────────────────────────────────


def test_declaration_is_an_unregistered_draft(declaration: dict[str, object]) -> None:
    assert declaration["contract_version"] == "v1"
    assert declaration["status"] == "draft"
    assert declaration["binding"] == "none"


def test_declaration_carries_no_runtime_field(declaration: dict[str, object]) -> None:
    offending = sorted(FORBIDDEN_KEYS.intersection(walk_keys(declaration)))
    assert not offending, f"declarative document carries runtime keys: {offending}"


def test_proposed_events_are_not_registered(declaration: dict[str, object]) -> None:
    events = declaration["proposed_events"]
    assert isinstance(events, dict)
    assert events["registration_status"] == "not_registered"
    # Registry mutation belongs to the parallel task, not to this contract draft.
    assert events["registry_owner_task"] == "task-research-0001"


# ── Two service tiers, incompatible execution forms ─────────────────────────


def test_exactly_two_tiers_are_declared(declaration: dict[str, object]) -> None:
    tiers = declaration["tiers"]
    assert isinstance(tiers, dict)
    assert sorted(tiers) == TIERS


def test_tier_execution_forms_are_disjoint(declaration: dict[str, object]) -> None:
    tiers = declaration["tiers"]
    assert tiers["lookup"]["execution_form"] == "synchronous_tool_call"
    assert tiers["deep_research"]["execution_form"] == "asynchronous_job"
    assert tiers["lookup"]["job_identity"] is False
    assert tiers["deep_research"]["job_identity"] is True


def test_lookup_tier_does_not_persist(declaration: dict[str, object]) -> None:
    assert declaration["tiers"]["lookup"]["persistence"] == "none"


def test_deep_research_is_carried_by_the_bundled_researcher_hand(
    declaration: dict[str, object],
) -> None:
    carrier = declaration["tiers"]["deep_research"]["carrier"]
    assert carrier["kind"] == "openfang_bundled_hand"
    assert carrier["hand_id"] == "researcher"


def test_today_lookup_events_are_recorded_unchanged(declaration: dict[str, object]) -> None:
    assert sorted(declaration["tiers"]["lookup"]["today_events"]) == TODAY_LOOKUP_EVENTS
    # Deep Research has no event today; that is the gap this draft describes.
    assert declaration["tiers"]["deep_research"]["today_events"] == []


# ── Settings are bound to the Hand, not invented ────────────────────────────


def test_settings_are_exactly_depth_and_output_style(declaration: dict[str, object]) -> None:
    assert sorted(declaration["settings"]) == ["depth", "output_style"]


def test_depth_matches_the_hand_verbatim(declaration: dict[str, object]) -> None:
    depth = declaration["settings"]["depth"]
    assert depth["values"] == HAND_RESEARCH_DEPTH
    assert depth["default"] == HAND_RESEARCH_DEPTH_DEFAULT
    assert depth["bound_to"]["setting_key"] == "research_depth"


def test_output_style_matches_the_hand_verbatim(declaration: dict[str, object]) -> None:
    style = declaration["settings"]["output_style"]
    assert style["values"] == HAND_OUTPUT_STYLE
    assert style["default"] == HAND_OUTPUT_STYLE_DEFAULT
    assert style["bound_to"]["setting_key"] == "output_style"


@pytest.mark.parametrize("name", ["depth", "output_style"])
def test_settings_declare_their_upstream_pin(declaration: dict[str, object], name: str) -> None:
    bound_to = declaration["settings"][name]["bound_to"]
    assert bound_to["repo"] == "Flissel/openfang"
    assert bound_to["pin"] == "5d38662f9fa596c8f145e4f6a45a09edf4504837"
    assert bound_to["path"] == "crates/openfang-hands/bundled/researcher/HAND.toml"


@pytest.mark.parametrize("name", ["depth", "output_style"])
def test_settings_apply_to_deep_research_only(declaration: dict[str, object], name: str) -> None:
    # A synchronous single tool call has no depth to spend and no report to style.
    assert declaration["settings"][name]["applies_to_tiers"] == ["deep_research"]


@pytest.mark.parametrize("name", ["depth", "output_style"])
def test_settings_default_is_one_of_its_own_values(
    declaration: dict[str, object], name: str
) -> None:
    setting = declaration["settings"][name]
    assert setting["default"] in setting["values"]


# ── Subject model replaces the ad-hoc parameters ────────────────────────────


def test_exactly_three_subject_kinds(declaration: dict[str, object]) -> None:
    assert sorted(declaration["subjects"]) == SUBJECT_KINDS


def test_topic_is_free_text(declaration: dict[str, object]) -> None:
    assert declaration["subjects"]["topic"]["kind"] == "free_text"


def test_idea_subject_derives_the_question_from_title_and_body(
    declaration: dict[str, object],
) -> None:
    idea = declaration["subjects"]["idea"]
    assert idea["kind"] == "reference"
    assert idea["question_source"] == ["title", "description"]
    assert idea["result_disposition"] == "enriches_subject_idea"


def test_bubble_subject_resolves_members_through_the_idea_tree(
    declaration: dict[str, object],
) -> None:
    bubble = declaration["subjects"]["bubble"]
    assert bubble["kind"] == "reference"
    assert bubble["member_resolution"] == "ideas.parent_id"
    # Fan-out is a user decision, not something this draft settles.
    assert bubble["result_disposition"] == "open_decision:D2"


def test_legacy_ad_hoc_params_are_recorded_as_superseded(
    declaration: dict[str, object],
) -> None:
    assert sorted(declaration["supersedes_legacy_params"]) == LEGACY_AD_HOC_PARAMS


def test_no_subject_is_named_after_a_legacy_param(declaration: dict[str, object]) -> None:
    overlap = set(declaration["subjects"]).intersection(LEGACY_AD_HOC_PARAMS)
    assert not overlap, f"subject model re-introduces ad-hoc parameters: {sorted(overlap)}"


# ── Event cut: start / status / result for the asynchronous tier ────────────


def test_deep_research_event_cut_covers_start_status_result(
    declaration: dict[str, object],
) -> None:
    deep = declaration["proposed_events"]["deep_research"]
    assert sorted(deep) == [
        "research.deep.cancel",
        "research.deep.result",
        "research.deep.start",
        "research.deep.status",
    ]


def test_deep_research_start_takes_a_subject_not_a_query(
    declaration: dict[str, object],
) -> None:
    start = declaration["proposed_events"]["deep_research"]["research.deep.start"]
    assert start["required_params"] == ["subject_type", "subject_ref"]
    assert "query" not in start["required_params"]


@pytest.mark.parametrize(
    "event", ["research.deep.status", "research.deep.result", "research.deep.cancel"]
)
def test_deep_research_follow_up_events_key_on_job_id(
    declaration: dict[str, object], event: str
) -> None:
    # Matches the registry's existing asynchronous style: mirofish.status keys on
    # job_id, agentfarm.results keys on run_id.
    assert declaration["proposed_events"]["deep_research"][event]["required_params"] == ["job_id"]


def test_lookup_events_keep_a_single_synchronous_shape(declaration: dict[str, object]) -> None:
    lookup = declaration["proposed_events"]["lookup"]
    assert sorted(lookup) == TODAY_LOOKUP_EVENTS
    for event in lookup.values():
        assert event["result_delivery"] == "inline"
        assert "job_id" not in event["required_params"]


def test_every_proposed_event_uses_the_research_prefix(declaration: dict[str, object]) -> None:
    events = declaration["proposed_events"]
    names = list(events["lookup"]) + list(events["deep_research"])
    assert names, "no proposed events declared"
    for name in names:
        assert name.startswith("research."), f"event outside the research. prefix: {name}"


# ── E12: fail-open on context, fail-closed on evidence ──────────────────────


def test_internal_context_fails_open(declaration: dict[str, object]) -> None:
    policy = declaration["context_policy"]
    assert policy["internal_context_source"] == "rowboat"
    assert policy["mode"] == "fail_open"
    assert policy["on_unavailable"] == "continue_web_only"


def test_failing_open_is_never_silent(declaration: dict[str, object]) -> None:
    policy = declaration["context_policy"]
    assert policy["disclosure_required"] is True
    assert policy["disclosure_target"] == "report"
    assert policy["silent_degradation"] == "forbidden"


def test_evidence_fails_closed(declaration: dict[str, object]) -> None:
    policy = declaration["evidence_policy"]
    assert policy["mode"] == "fail_closed"
    assert policy["on_violation"] == "run_marked_failed"


def test_evidence_policy_cites_the_existing_repo_precedent(
    declaration: dict[str, object],
) -> None:
    precedent = declaration["evidence_policy"]["precedent"]
    assert precedent["repo"] == "Flissel/vibemind-os"
    assert precedent["pin"] == "c5cba961126523bed39d0d94e8fd0c982cb9cbe2"
    assert precedent["path"] == "spaces/research/execution_target.py"


def test_the_two_policies_are_genuinely_opposite(declaration: dict[str, object]) -> None:
    # The whole point of E12: context degrades, evidence does not.
    assert declaration["context_policy"]["mode"] != declaration["evidence_policy"]["mode"]


# ── Open decisions are carried, not silently resolved ───────────────────────


def test_the_three_decisions_are_declared(declaration: dict[str, object]) -> None:
    decisions = declaration["open_decisions"]
    assert sorted(decisions) == DECISIONS
    for decision in decisions.values():
        assert decision["decided_by"] == "user"
        assert len(decision["options"]) >= 2


def test_no_decision_is_resolved_silently(declaration: dict[str, object]) -> None:
    # The guard the predecessor test enforced by keeping every decision open.
    # A resolution is allowed now, but only when it names the option it chose
    # and the decision entry that chose it.
    for name, decision in declaration["open_decisions"].items():
        if not decision["resolved"]:
            assert "resolution" not in decision, f"{name} is unresolved but carries a resolution"
            continue
        assert decision["resolution"] in decision["options"], (
            f"{name} resolves to an option it does not offer"
        )
        assert decision["decision_ref"], f"{name} is resolved without a decision reference"


def test_d1_is_resolved_to_the_linked_artifact_shape(declaration: dict[str, object]) -> None:
    d1 = declaration["open_decisions"]["D1"]
    assert d1["resolved"] is True
    assert d1["resolution"] == "short_idea_plus_linked_artifact"
    assert d1["decision_ref"] == "E14"


def test_d1_records_that_its_governance_entry_is_still_missing(
    declaration: dict[str, object],
) -> None:
    # E14 is cited by the task brief but absent from the E-series document,
    # which ends at E13. The declaration must say so rather than imply that a
    # governance record exists.
    d1 = declaration["open_decisions"]["D1"]
    assert d1["decision_record_status"] == "pending_governance_entry"
    assert "docs/governance/" in d1["decision_record_note"]


@pytest.mark.parametrize("name", ["D2", "D3"])
def test_the_remaining_decisions_stay_open(declaration: dict[str, object], name: str) -> None:
    assert declaration["open_decisions"][name]["resolved"] is False


def test_d2_fan_out_is_still_the_users_to_make(declaration: dict[str, object]) -> None:
    # Resolving D1 must not have quietly settled the bubble fan-out with it.
    d2 = declaration["open_decisions"]["D2"]
    assert sorted(d2["options"]) == ["report_per_member_idea", "single_cluster_report"]
    assert declaration["subjects"]["bubble"]["result_disposition"] == "open_decision:D2"


# ── D1's resolution: short idea plus linked artifact ────────────────────────


def test_report_persistence_implements_the_resolved_option(
    declaration: dict[str, object],
) -> None:
    persistence = declaration["report_persistence"]
    assert persistence["resolves"] == "D1"
    assert persistence["decision_ref"] == "E14"
    assert persistence["shape"] == declaration["open_decisions"]["D1"]["resolution"]


def test_the_migration_is_written_but_not_applied(declaration: dict[str, object]) -> None:
    # The staging the authoring task was bound by: files, never a database.
    persistence = declaration["report_persistence"]
    assert persistence["state"] == "written_not_applied"
    assert persistence["artifact_side"]["applied"] is False


def test_the_idea_side_needs_no_migration(declaration: dict[str, object]) -> None:
    # The summary fits ideas.description as it already stands, and the pointer
    # fits the metadata JSONB column that already exists.
    persistence = declaration["report_persistence"]
    assert persistence["idea_side"]["migration_required"] is False
    assert persistence["idea_side"]["max_length"] == IDEA_SUMMARY_MAX_LENGTH
    assert persistence["idea_side"]["bound_to_contract"] == "ResearchIdeaHandoffV1.idea_summary"
    assert persistence["pointer"]["migration_required"] is False


def test_the_idea_summary_cap_matches_the_merged_handoff_schema(
    declaration: dict[str, object],
) -> None:
    # If the merged schema's cap ever moves, this declaration has to move with it.
    schema = json.loads(IDEA_HANDOFF_SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["idea_summary"]["maxLength"] == IDEA_SUMMARY_MAX_LENGTH
    assert (
        declaration["report_persistence"]["idea_side"]["max_length"]
        == schema["properties"]["idea_summary"]["maxLength"]
    )


def test_the_foreign_key_is_on_the_artifact_side(declaration: dict[str, object]) -> None:
    # The whole reason the sync payload is unaffected: public.ideas gains
    # nothing, so to_jsonb(NEW) keeps its present shape.
    link = declaration["report_persistence"]["link_direction"]
    assert link["value"] == "artifact_references_idea"
    assert link["foreign_key_side"] == "research_report_artifacts"
    assert link["ideas_columns_added"] == 0


def test_the_artifact_joins_the_result_document_by_artifact_ref(
    declaration: dict[str, object],
) -> None:
    artifact = declaration["report_persistence"]["artifact_side"]
    assert artifact["join_source"] == "ResearchResultV1.artifact_refs"
    assert artifact["id_grammar"] == "artifact_v1_<ULID>"
    # The declared grammar has to be the one the merged result schema enforces.
    schema = json.loads(RESULT_SCHEMA.read_text(encoding="utf-8"))
    pattern = schema["$defs"]["artifactId"]["pattern"]
    assert re.fullmatch(pattern, "artifact_v1_" + "0123456789ABCDEFGHJKMNPQRS")


def test_the_artifact_row_is_write_once(declaration: dict[str, object]) -> None:
    # A second run appends a row; it does not edit the first report.
    assert declaration["report_persistence"]["artifact_side"]["write_once"] is True


def test_the_artifact_storage_stays_fail_closed_on_evidence(
    declaration: dict[str, object],
) -> None:
    guards = declaration["report_persistence"]["artifact_side"]["fail_closed_storage_guards"]
    assert guards, "the storage shape declares no evidence guard"
    assert declaration["evidence_policy"]["mode"] == "fail_closed"


def test_the_artifact_shape_does_not_pre_empt_the_fan_out_decision(
    declaration: dict[str, object],
) -> None:
    assert "D2" in declaration["report_persistence"]["artifact_side"]["d2_neutral"]


# ── D3: the sync-chain question the artifact shape raises ───────────────────


def test_the_artifact_is_not_attached_to_the_ideas_sync_chain(
    declaration: dict[str, object],
) -> None:
    sync = declaration["report_persistence"]["sync_chain"]
    assert sync["attached"] is False
    assert sync["emits_into_ideas_outbox"] is False
    assert sync["open_decision"] == "D3"


def test_the_sync_consequence_is_stated_rather_than_left_implicit(
    declaration: dict[str, object],
) -> None:
    # E12 makes Rowboat the internal reference source. What does and does not
    # reach it has to be written down, not discovered later.
    sync = declaration["report_persistence"]["sync_chain"]
    assert sync["what_still_reaches_rowboat"]
    assert sync["what_does_not"]
    assert declaration["open_decisions"]["D3"]["consequence_for_e12"]


def test_d3_recommends_an_option_it_actually_offers(declaration: dict[str, object]) -> None:
    d3 = declaration["open_decisions"]["D3"]
    assert d3["recommended_option"] in d3["options"]
    # A recommendation is not a resolution.
    assert d3["resolved"] is False
