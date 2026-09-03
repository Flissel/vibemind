from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTER_PATH = (
    REPOSITORY_ROOT / "docs/governance/cockpit-next-task-register-v1.json"
)
REGISTRY_PATH = (
    REPOSITORY_ROOT / "docs/governance/session-portfolio-registry-v1.json"
)
TASK_ID_RE = re.compile(r"^task-[a-z0-9]+-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*-v\d+$")
FORBIDDEN_CLAIM_KEYS = {
    "activation",
    "admission",
    "approval",
    "execution",
    "golden_path",
    "handoff",
    "interactivity",
    "lifecycle",
    "live",
    "merge",
    "pr",
    "request",
    "runtime",
}
ALLOWED_IMPLEMENTATION_AUTHORITIES = {
    "standing-autonomy-eligible",
    "request-specific-breaking-authority",
    "request-specific-runtime-authority",
    "request-specific-data-authority",
    "request-specific-outbound-authority",
}
EXPECTED_TASKS = {
    "cockpit-openfang": "task-openfang-0007-embedding-dimensions-contract-v1",
    "cockpit-shared": "task-shared-0007-openfang-only-provider-policy-v1",
    "cockpit-integration": "task-integration-0005-openfang-mcp-authority-v1",
    "cockpit-ideas": "task-ideas-0004-openfang-edge-runtime-admission-v1",
    "cockpit-bubbles": "task-bubbles-0007-promote-id-cutover-v1",
    "cockpit-coding": "task-coding-0002-openfang-codegen-admission-v1",
    "cockpit-desktop": "task-desktop-0002-canonical-openfang-screenshot-v1",
    "cockpit-n8n": "task-n8n-0003-openfang-mcp-hub-cutover-v1",
    "cockpit-agentfarm": "task-agentfarm-0008-openfang-llm-role-reservation-v1",
    "cockpit-schedule": "task-schedule-0004-vibemind-status-mcp-adapter-v1",
    "cockpit-rowboat": "task-rowboat-0004-openfang-status-runtime-admission-v1",
    "cockpit-minibook": "task-minibook-0003-openfang-status-runtime-admission-v1",
    "cockpit-video": "task-video-0003-status-mcp-cutover-v1",
    "cockpit-flowzen": "task-flowzen-0003-status-mcp-cutover-v1",
    "cockpit-mirofish": "task-mirofish-0003-openfang-embedding-contract-v1",
    "cockpit-marketing": "task-marketing-0003-openfang-only-send-gate-v1",
}
EXPECTED_OBJECTIVES = {
    "cockpit-openfang": "Define the OpenFang embedding dimensions contract.",
    "cockpit-shared": "Enforce the OpenFang-only shared provider policy.",
    "cockpit-integration": (
        "Define and validate durable OpenFang MCP server identity, agent scope, "
        "tool allowlists, and registration authority."
    ),
    "cockpit-ideas": (
        "Register and allowlist the merged spaces-ideas idea_connect tool for "
        "brain-ideas, then prove one live ID-only Brain-to-OpenFang-to-MCP-to-"
        "Supabase edge round trip with independent truth readback."
    ),
    "cockpit-bubbles": (
        "Cut Brain bubble promotion over to the MCP tool using durable bubble_id "
        "and remove legacy title resolution."
    ),
    "cockpit-coding": "Admit code generation through the canonical OpenFang agent.",
    "cockpit-desktop": "Route canonical screenshots through the OpenFang desktop agent.",
    "cockpit-n8n": "Cut n8n deterministic operations over to the OpenFang MCP hub.",
    "cockpit-agentfarm": (
        "Bind the existing space_agentfarm LLM role declaratively to the "
        "reserved brain-agentfarm OpenFang identity while the Space remains "
        "disabled and no agent, Bridge, or runtime state is changed."
    ),
    "cockpit-schedule": (
        "Define a read-only VibeMind ScheduleRepository status MCP adapter with "
        "optional task_id, stable task-or-counts result, and independent Brain "
        "readback validator."
    ),
    "cockpit-rowboat": (
        "Admit the merged Rowboat status MCP tool to the canonical OpenFang agent "
        "with an explicit tool allowlist."
    ),
    "cockpit-minibook": (
        "Align the Minibook bridge identity to brain-knowledge and admit the "
        "status MCP tool to its canonical OpenFang agent."
    ),
    "cockpit-video": (
        "Split provider and durable-job status intents, add independent Brain "
        "truth readbacks, and cut Video status routing to the spaces-video MCP tool."
    ),
    "cockpit-flowzen": (
        "Add an independent Brain Flowzen-status truth observer, normalize the MCP "
        "result envelope, align the bridge identity to brain-wellness, and cut "
        "rose.status routing to the spaces-flowzen MCP tool."
    ),
    "cockpit-mirofish": "Align MiroFish with the OpenFang embedding contract.",
    "cockpit-marketing": "Gate marketing sends behind OpenFang-only execution.",
}
EXPECTED_BLOCKERS = {
    "cockpit-openfang": [
        "request-specific runtime authority is required before a live dimensions change"
    ],
    "cockpit-shared": [
        "request-specific breaking-contract authority is required before a fail-closed provider-policy change"
    ],
    "cockpit-integration": [
        "request-specific runtime authority is required before live registration or activation"
    ],
    "cockpit-ideas": [
        "live brain-ideas registration and the spaces-ideas MCP server allowlist are not evidenced",
        "runtime OpenFang and Supabase credentials plus Proxmox reachability are unverified",
        "request-specific runtime authority is required before registration or activation",
        "request-specific data authority is required before a live edge mutation",
    ],
    "cockpit-bubbles": [
        "request-specific breaking-contract authority is required before replacing legacy bubble-name or title input with durable bubble_id",
        "request-specific runtime authority is required before live OpenFang MCP registration or activation",
    ],
    "cockpit-coding": [
        "request-specific runtime authority is required before live agent-scope activation"
    ],
    "cockpit-desktop": [
        "request-specific runtime authority is required before live desktop-agent activation"
    ],
    "cockpit-n8n": [
        "request-specific runtime authority is required before a live MCP-hub cutover"
    ],
    "cockpit-agentfarm": [],
    "cockpit-schedule": [
        "request-specific runtime authority is required before live MCP registration or activation"
    ],
    "cockpit-rowboat": [
        "request-specific runtime authority is required before live OpenFang Rowboat tool admission"
    ],
    "cockpit-minibook": [
        "the bridge mapping still targets brain-writer instead of canonical brain-knowledge",
        "request-specific runtime authority is required before live OpenFang MCP registration or activation",
    ],
    "cockpit-video": [
        "the current video.status capability mixes provider availability and durable job status",
        "the bridge mapping still targets vibemind instead of canonical brain-video",
        "a shared versioned read-only Video job store between Brain and OpenFang is not evidenced",
        "request-specific runtime authority is required before live OpenFang MCP registration or activation",
    ],
    "cockpit-flowzen": [
        "the current rule:flowzen_result validates the claimed envelope instead of an independent truth readback",
        "the MCP result envelope does not match the legacy direct Flowzen status shape without normalization",
        "the bridge mapping still targets vibemind instead of canonical brain-wellness",
        "request-specific runtime authority is required before live OpenFang MCP registration or activation",
    ],
    "cockpit-mirofish": [
        "request-specific runtime authority is required before consumer migration",
        "request-specific data authority is required before Qdrant or Neo4j reindex",
    ],
    "cockpit-marketing": [
        "request-specific breaking-contract authority is required before a send-gate change",
        "request-specific outbound authority is required before any external send",
    ],
}
EXPECTED_AUTHORITIES = {
    cockpit_id: ["standing-autonomy-eligible"] for cockpit_id in EXPECTED_TASKS
}
EXPECTED_AUTHORITIES.update(
    {
        "cockpit-openfang": ["request-specific-runtime-authority"],
        "cockpit-shared": ["request-specific-breaking-authority"],
        "cockpit-integration": ["request-specific-runtime-authority"],
        "cockpit-ideas": [
            "request-specific-runtime-authority",
            "request-specific-data-authority",
        ],
        "cockpit-bubbles": [
            "request-specific-breaking-authority",
            "request-specific-runtime-authority",
        ],
        "cockpit-coding": ["request-specific-runtime-authority"],
        "cockpit-desktop": ["request-specific-runtime-authority"],
        "cockpit-n8n": ["request-specific-runtime-authority"],
        "cockpit-schedule": ["request-specific-runtime-authority"],
        "cockpit-rowboat": ["request-specific-runtime-authority"],
        "cockpit-minibook": ["request-specific-runtime-authority"],
        "cockpit-video": [
            "request-specific-breaking-authority",
            "request-specific-runtime-authority",
        ],
        "cockpit-flowzen": [
            "request-specific-breaking-authority",
            "request-specific-runtime-authority",
        ],
        "cockpit-mirofish": [
            "request-specific-runtime-authority",
            "request-specific-data-authority",
        ],
        "cockpit-marketing": [
            "request-specific-breaking-authority",
            "request-specific-outbound-authority",
        ],
    }
)
EXPECTED_DEPENDENCIES = {cockpit_id: [] for cockpit_id in EXPECTED_TASKS}
EXPECTED_DEPENDENCIES.update(
    {
        "cockpit-ideas": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-bubbles": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-rowboat": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-minibook": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-video": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-flowzen": ["task-integration-0005-openfang-mcp-authority-v1"],
        "cockpit-mirofish": [
            "task-openfang-0007-embedding-dimensions-contract-v1"
        ],
    }
)
EXPECTED_GAP_REASONS = {
    "cockpit-brain": (
        "no new bounded next implementation task is evidenced"
    ),
    "cockpit-git": "no bounded next implementation task is evidenced",
    "cockpit-deployment": "no bounded next implementation task is evidenced",
    "cockpit-observability": "no bounded next implementation task is evidenced",
    "cockpit-channels": "no bounded next implementation task is evidenced",
    "cockpit-research": "no new bounded next implementation task is evidenced",
}


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        nested = set().union(*(_walk_keys(item) for item in value.values()))
        return {str(key).casefold() for key in value} | nested
    if isinstance(value, list):
        return set().union(*(_walk_keys(item) for item in value))
    return set()


def test_register_is_closed_static_planning_and_preserves_portfolio_order() -> None:
    register = _json(REGISTER_PATH)
    registry = _json(REGISTRY_PATH)

    assert set(register) == {
        "schema_version",
        "membership_source",
        "scope",
        "nonclaims",
        "rows",
    }
    assert register == {
        **register,
        "schema_version": 1,
        "membership_source": "docs/governance/session-portfolio-registry-v1.json",
        "scope": "static-declarative-planning-only",
        "nonclaims": [
            "not-a-task-request-or-approval",
            "does-not-prove-cockpit-activation-interactivity-or-approval",
            "does-not-prove-admission-execution-handoff-pr-merge-runtime-or-golden-path",
        ],
    }

    rows = register["rows"]
    registry_cockpits = registry["cockpits"]
    assert isinstance(rows, list)
    assert isinstance(registry_cockpits, list)
    row_ids = [row["cockpit_session_id"] for row in rows]
    registry_ids = [entry["cockpit_session_id"] for entry in registry_cockpits]
    assert len(row_ids) == 22
    assert len(row_ids) == len(set(row_ids))
    assert row_ids == registry_ids
    assert not (_walk_keys(register) & FORBIDDEN_CLAIM_KEYS)


def test_proposals_are_actionable_closed_and_dependency_safe() -> None:
    rows = _json(REGISTER_PATH)["rows"]
    assert isinstance(rows, list)
    proposals = {
        row["cockpit_session_id"]: row
        for row in rows
        if row["row_type"] == "task-proposal"
    }
    assert len(proposals) == 16
    assert set(proposals) == set(EXPECTED_TASKS)

    task_ids = [row["task_id"] for row in proposals.values()]
    assert len(task_ids) == len(set(task_ids))
    assert all(isinstance(task_id, str) and TASK_ID_RE.fullmatch(task_id) for task_id in task_ids)
    actual_task_ids = set(task_ids)

    for cockpit_id, row in proposals.items():
        assert set(row) == {
            "cockpit_session_id",
            "row_type",
            "task_id",
            "objective",
            "task_dependencies",
            "external_blockers",
            "authority",
        }
        assert row["task_id"] == EXPECTED_TASKS[cockpit_id]
        assert row["objective"] == EXPECTED_OBJECTIVES[cockpit_id]
        assert isinstance(row["objective"], str) and row["objective"].strip()

        dependencies = row["task_dependencies"]
        assert isinstance(dependencies, list)
        assert len(dependencies) == len(set(dependencies))
        assert all(isinstance(dependency, str) for dependency in dependencies)
        assert all(TASK_ID_RE.fullmatch(dependency) for dependency in dependencies)
        assert dependencies == EXPECTED_DEPENDENCIES[cockpit_id]
        assert set(dependencies) <= actual_task_ids
        assert row["task_id"] not in dependencies

        blockers = row["external_blockers"]
        assert isinstance(blockers, list)
        assert blockers == EXPECTED_BLOCKERS[cockpit_id]
        assert all(isinstance(blocker, str) and blocker for blocker in blockers)

        authorities = row["authority"]
        assert set(authorities) == {"planning", "implementation_authorities"}
        assert authorities["planning"] == "standing-autonomy:v1"
        implementation_authorities = authorities["implementation_authorities"]
        assert isinstance(implementation_authorities, list)
        assert implementation_authorities == EXPECTED_AUTHORITIES[cockpit_id]
        assert implementation_authorities
        assert len(implementation_authorities) == len(set(implementation_authorities))
        assert set(implementation_authorities) <= ALLOWED_IMPLEMENTATION_AUTHORITIES


def test_planning_gaps_are_closed_and_do_not_republish_delivered_brain_task() -> None:
    rows = _json(REGISTER_PATH)["rows"]
    assert isinstance(rows, list)
    gaps = {
        row["cockpit_session_id"]: row
        for row in rows
        if row["row_type"] == "planning-gap"
    }
    assert len(gaps) == 6
    assert set(gaps) == set(EXPECTED_GAP_REASONS)

    for cockpit_id, row in gaps.items():
        assert set(row) == {
            "cockpit_session_id",
            "row_type",
            "reason",
            "task_dependencies",
            "external_blockers",
            "authority",
        }
        assert row["reason"] == EXPECTED_GAP_REASONS[cockpit_id]
        assert row["task_dependencies"] == []
        assert row["external_blockers"] == []
        assert row["authority"] == {
            "planning": "standing-autonomy:v1",
            "implementation_authorities": ["standing-autonomy-eligible"],
        }

    assert "task-brain-0015-deterministic-mcp-precedence-v1" not in {
        row.get("task_id") for row in rows
    }
