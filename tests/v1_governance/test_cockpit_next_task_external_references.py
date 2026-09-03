from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_PATH = (
    REPOSITORY_ROOT
    / "docs/governance/cockpit-next-task-external-references-v1.json"
)
REGISTRY_PATH = REPOSITORY_ROOT / "docs/governance/session-portfolio-registry-v1.json"
REGISTER_PATH = REPOSITORY_ROOT / "docs/governance/cockpit-next-task-register-v1.json"
RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TASK_ID_RE = re.compile(r"^task-[a-z0-9]+-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*-v\d+$")
GATE_ID_RE = re.compile(r"^gate-[a-z0-9]+-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*-v\d+$")
EXPECTED_REFERENCES = [
    ("cockpit-openfang", "task", "task-openfang-0008-mcp-servers-manifest-migration-v1"),
    ("cockpit-openfang", "task", "task-openfang-0009-child-openfang-gitlink-pin-v1"),
    ("cockpit-integration", "task", "task-integration-0015-mcp-provenance-legacy-regression-v1"),
    ("cockpit-agentfarm", "task", "task-agentfarm-0009-versioned-runtime-source-artifact-v1"),
    (
        "cockpit-git",
        "gate",
        "gate-integration-0016-vibemind-os-pr115-postpin-regate-v1",
    ),
]
FORBIDDEN_CLAIM_KEYS = {
    "activation",
    "admission",
    "approval",
    "execution",
    "handoff",
    "lifecycle",
    "live",
    "merge",
    "pr",
    "runtime",
    "status",
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


def test_current_external_references_are_closed_nonclaiming_and_separate() -> None:
    sidecar = _json(REFERENCES_PATH)
    registry = _json(REGISTRY_PATH)
    register = _json(REGISTER_PATH)

    assert set(sidecar) == {
        "schema_version",
        "membership_source",
        "evidence_class",
        "nonclaims",
        "references",
    }
    assert sidecar["schema_version"] == 1
    assert sidecar["membership_source"] == "docs/governance/session-portfolio-registry-v1.json"
    assert sidecar["evidence_class"] == "external-not-git-verified"
    assert sidecar["nonclaims"] == [
        "not-a-task-request-or-approval",
        "does-not-prove-task-execution-or-gate-outcome",
        "does-not-prove-admission-handoff-pr-merge-runtime-or-live-evidence",
    ]
    assert not (_walk_keys(sidecar) & FORBIDDEN_CLAIM_KEYS)

    cockpit_ids = {
        cockpit["cockpit_session_id"] for cockpit in registry["cockpits"]
    }
    references = sidecar["references"]
    assert isinstance(references, list)
    assert [
        (reference["cockpit_session_id"], reference["reference_kind"], reference["reference_id"])
        for reference in references
    ] == EXPECTED_REFERENCES

    register_task_ids = {
        row["task_id"] for row in register["rows"] if "task_id" in row
    }
    external_task_ids = {
        reference_id
        for _, reference_kind, reference_id in EXPECTED_REFERENCES
        if reference_kind == "task"
    }
    assert not (register_task_ids & external_task_ids)

    for reference in references:
        assert set(reference) == {
            "cockpit_session_id",
            "reference_kind",
            "reference_id",
            "evidence_scope",
            "evidence_source",
            "observed_at",
            "source_thread_id",
        }
        assert reference["cockpit_session_id"] in cockpit_ids
        assert reference["reference_kind"] in {"task", "gate"}
        if reference["reference_kind"] == "task":
            assert TASK_ID_RE.fullmatch(reference["reference_id"])
        else:
            assert reference["reference_id"] == (
                "gate-integration-0016-vibemind-os-pr115-postpin-regate-v1"
            )
            assert GATE_ID_RE.fullmatch(reference["reference_id"])
        assert reference["evidence_scope"] == "external-not-git-verified"
        assert reference["evidence_source"] == "external-user-owned-thread"
        assert RFC3339_UTC_RE.fullmatch(reference["observed_at"])
        assert UUID_RE.fullmatch(reference["source_thread_id"])
