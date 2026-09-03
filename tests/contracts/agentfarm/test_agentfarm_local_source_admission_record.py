from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from shared.contracts.agentfarm_runtime_source_resolver import (
    resolve_agentfarm_runtime_source_admission,
)
from shared.contracts.validate import validate_agentfarm_runtime_admission_bundle


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RECORD_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "spaces"
    / "agentfarm"
    / "fixtures"
    / "v1"
    / "local-source-admission-record-v1.json"
)
CANONICAL_IDENTITY = "github.com/Flissel/Autogen_AgentFarm"
PINNED_COMMIT = "9ac6fe9fa2f2a2b48baafacc50b35781218d7b07"
CANONICAL_ARCHIVE_DIGEST = (
    "sha256:f0ba80fcf865dca6ad9adf91ccac3739e260ce60f87f0731e42e189d93610d01"
)
EXPECTED_NONCLAIMS = [
    "runtime_enabled",
    "built",
    "routed",
    "deployed",
    "reachable",
    "approved",
    "executed",
    "identity_ownership",
    "remote_freshness",
    "sibling_reconciliation",
]


def load_record() -> dict[str, object]:
    return json.loads(RECORD_PATH.read_text(encoding="utf-8"))


def test_local_source_admission_record_is_versioned_request_bound_and_offline() -> None:
    record = load_record()

    assert record["record_version"] == "v1"
    assert record["verification_scope"] == "offline_local_git_only"
    assert record["claims"] == ["verified_local_source"]
    assert record["nonclaims"] == EXPECTED_NONCLAIMS
    assert record["source_candidate"]["canonical_identity"] == CANONICAL_IDENTITY
    assert record["source_candidate"]["commit_sha"] == PINNED_COMMIT
    assert record["unreconciled_siblings"] == [
        {
            "commit_sha": "73b00888d31486df3e3fad3dfc5cd953bbd26bd4",
            "status": "unreconciled_non_authoritative",
        },
        {
            "commit_sha": "fab103447bfff0e9c49cf9c9e0249ee9d33cbaf9",
            "status": "unreconciled_non_authoritative",
        },
    ]

    bundle = record["admission_bundle"]
    assert isinstance(bundle, dict)
    validate_agentfarm_runtime_admission_bundle(bundle)
    provenance = bundle["agentfarm-runtime-source-provenance"]
    assert provenance["request_id"] == bundle["agent-team-request"]["request_id"]
    assert provenance["repository"]["canonical_identity"] == CANONICAL_IDENTITY
    assert provenance["revision"]["commit_sha"] == PINNED_COMMIT
    assert record["source_candidate"]["tree_sha"] == provenance["revision"]["tree_sha"]
    assert provenance["revision"]["source_tree_digest"] == CANONICAL_ARCHIVE_DIGEST
    assert record["rejected_preobservations"] == [
        {
            "archive_digest": (
                "sha256:2fbc5def528a8411a8fd9097b930d8f3593c9f284aac421e32340caced42a8b6"
            ),
            "reason": "system_config_autocrlf_dependent",
            "status": "rejected_noncanonical",
        }
    ]


def test_local_source_admission_record_resolves_existing_opt_in_candidate() -> None:
    candidate = os.environ.get("VIBEMIND_AGENTFARM_LOCAL_SOURCE")
    allowed_root = os.environ.get("VIBEMIND_AGENTFARM_ALLOWED_ROOT")
    if not candidate or not allowed_root:
        pytest.skip("local AgentFarm candidate was not explicitly provided")

    record = load_record()
    bundle = record["admission_bundle"]
    assert isinstance(bundle, dict)

    receipt = resolve_agentfarm_runtime_source_admission(
        bundle,
        Path(candidate),
        Path(allowed_root),
        CANONICAL_IDENTITY,
    )

    assert receipt.commit_sha == PINNED_COMMIT
    assert receipt.claims == ("verified_local_source",)
    assert "runtime_enabled" in receipt.nonclaims
