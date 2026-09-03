from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPOSITORY_ROOT / "docs/governance/session-portfolio-registry-v1.json"
PORTFOLIO_PATH = (
    REPOSITORY_ROOT
    / "docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md"
)

EXPECTED_THREAD_IDS = {
    "cockpit-brain": "019fb3e4-0b82-7ef1-b722-883d480d2fea",
    "cockpit-shared": "019fb3e3-ec49-77c2-a91c-1d43d9f086e2",
    "cockpit-git": "019fb354-f120-7363-8214-ee9e493fe7b4",
    "cockpit-deployment": "019fb3e4-2acc-7cc0-94bf-09e12d32a3bc",
    "cockpit-integration": "019fb3f1-b382-7b61-bddc-0ba2c12c93ad",
    "cockpit-observability": "019fb3f1-d690-7312-95ec-d02c71f13def",
    "cockpit-channels": "019fb3f1-f5c3-74d3-b3e4-e1a23b2bf033",
    "cockpit-ideas": "019fb3f5-7c0c-7961-b1d7-ac35a01d5214",
    "cockpit-bubbles": "019fb3f5-a75a-7601-a976-5e3fa406f845",
    "cockpit-coding": "019fb3f5-d21a-7aa0-892c-e5cc3ef53e46",
    "cockpit-desktop": "019fb3f5-f91a-70e0-ae9d-33526136c161",
    "cockpit-research": "019fb3f6-280b-7a71-b797-f643df388b92",
    "cockpit-n8n": "019fb743-0fcc-7191-b8a2-1812ed51464f",
    "cockpit-agentfarm": "019fcf2c-9249-7040-abc7-a0bdf0e1cabc",
    "cockpit-openfang": "019fcdb3-d021-73a0-9d8b-7b93ee5be965",
    "cockpit-schedule": "019fb743-1772-7eb0-8541-e449c7519b3d",
    "cockpit-rowboat": "019fb3f6-d434-7b52-b331-5bb02b155343",
    "cockpit-minibook": "019fb3f6-ff51-7050-83e5-ba191851ae00",
    "cockpit-video": "019fb3f7-2a8d-7340-90c1-4bffd4795bea",
    "cockpit-flowzen": "019fb3f7-5543-7ec0-b582-47a9ffd52b85",
    "cockpit-mirofish": "019fb477-35b2-7aa3-9fc6-bd97c35b9bc3",
    "cockpit-marketing": "019fb743-0598-7132-aedd-9ff460a5942f",
}

FORBIDDEN_KEYS = {
    "current_status",
    "status",
    "approval_ref",
    "acceptance_ref",
    "closure_ref",
    "handoff_ref",
    "pr_ref",
    "merge_ref",
    "runtime_status",
    "live_status",
}

ALLOWED_OBSERVATION_KEYS = {
    "evidence_scope",
    "evidence_source",
    "observation",
    "thread_id",
}


def _registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _portfolio_cockpit_ids() -> set[str]:
    portfolio = PORTFOLIO_PATH.read_text(encoding="utf-8")
    platform, space = portfolio.split("### 4.2 Fachliche Space-Cockpits", maxsplit=1)
    return set(re.findall(r"\| `(cockpit-[a-z0-9-]+)` \|", platform + space))


def _keys_recursively(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _keys_recursively(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _keys_recursively(nested)


def test_registry_exactly_matches_the_22_normative_portfolio_cockpits() -> None:
    registry = _registry()
    cockpits = registry["cockpits"]

    assert registry["schema_version"] == 1
    assert isinstance(cockpits, list)
    cockpit_ids = [cockpit["cockpit_session_id"] for cockpit in cockpits]
    assert len(cockpit_ids) == 22
    assert len(cockpit_ids) == len(set(cockpit_ids))
    assert set(cockpit_ids) == _portfolio_cockpit_ids()
    assert set(cockpit_ids) == set(EXPECTED_THREAD_IDS)


def test_registry_records_only_fixed_external_final_reported_observations() -> None:
    registry = _registry()

    for cockpit in registry["cockpits"]:
        cockpit_id = cockpit["cockpit_session_id"]
        observations = cockpit["historical_observations"]
        assert isinstance(observations, list)
        assert len(observations) == 1
        observation = observations[0]
        assert set(observation) == ALLOWED_OBSERVATION_KEYS
        assert observation == {
            "evidence_scope": "external-not-git-verified",
            "evidence_source": "external",
            "observation": "final_reported",
            "thread_id": EXPECTED_THREAD_IDS[cockpit_id],
        }


def test_registry_authority_keeps_membership_normative_and_lifecycle_external() -> None:
    authority = _registry()["authority"]

    assert authority == {
        "current_lifecycle": "main-orchestrator-external",
        "normative_membership": "portfolio",
    }


def test_registry_forbids_lifecycle_and_outcome_claim_keys_recursively() -> None:
    registry = _registry()

    assert FORBIDDEN_KEYS.isdisjoint(_keys_recursively(registry))
