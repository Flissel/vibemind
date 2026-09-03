from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OBSERVATIONS_PATH = (
    REPOSITORY_ROOT / "docs/governance/cockpit-external-observations-v1.json"
)
REGISTRY_PATH = REPOSITORY_ROOT / "docs/governance/session-portfolio-registry-v1.json"
HISTORICAL_OBSERVED_AT = "2026-08-03T06:41:04.835Z"
FRESH_OBSERVED_AT = "2026-08-05T06:32:40Z"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
RFC3339_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
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
FORBIDDEN_CLAIM_KEYS = {
    "outcome",
    "status",
    "activation",
    "interactivity",
    "approval",
    "acceptance",
    "handoff",
    "pr",
    "merge",
    "runtime",
    "live",
}


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_external_observation_sidecar_is_closed_fresh_and_non_claiming() -> None:
    sidecar = _json(OBSERVATIONS_PATH)
    registry = _json(REGISTRY_PATH)

    assert set(sidecar) == {
        "schema_version",
        "membership_source",
        "evidence_class",
        "observations",
    }
    assert sidecar["schema_version"] == 1
    assert sidecar["membership_source"] == "docs/governance/session-portfolio-registry-v1.json"
    assert sidecar["evidence_class"] == "external-not-git-verified"

    registry_cockpits = registry["cockpits"]
    observations = sidecar["observations"]
    assert isinstance(registry_cockpits, list)
    assert isinstance(observations, list)
    permitted_ids = [entry["cockpit_session_id"] for entry in registry_cockpits]
    assert len(permitted_ids) == 22
    assert len(permitted_ids) == len(set(permitted_ids))
    assert set(permitted_ids) == set(EXPECTED_THREAD_IDS) | {"cockpit-openfang"}
    assert len(observations) == 22

    observed_ids = [record["cockpit_session_id"] for record in observations]
    observed_pairs = [
        (record["cockpit_session_id"], record["thread_id"]) for record in observations
    ]
    assert set(observed_ids) == set(EXPECTED_THREAD_IDS)
    assert len(observed_pairs) == len(set(observed_pairs))

    for record in observations:
        assert set(record) == {
            "cockpit_session_id",
            "evidence_scope",
            "evidence_source",
            "observation",
            "observed_at",
            "thread_id",
        }
        assert not (set(record) & FORBIDDEN_CLAIM_KEYS)
        assert record["cockpit_session_id"] in permitted_ids
        assert record["evidence_scope"] == "external-not-git-verified"
        assert record["evidence_source"] == "external-user-owned-thread"
        assert record["observation"] == "thread_observed"
        expected_observed_at = (
            FRESH_OBSERVED_AT
            if record["cockpit_session_id"] in {"cockpit-agentfarm", "cockpit-openfang"}
            else HISTORICAL_OBSERVED_AT
        )
        assert record["observed_at"] == expected_observed_at
        assert isinstance(record["observed_at"], str)
        assert RFC3339_UTC_RE.fullmatch(record["observed_at"])
        assert isinstance(record["thread_id"], str)
        assert UUID_RE.fullmatch(record["thread_id"])
        assert record["thread_id"] == EXPECTED_THREAD_IDS[record["cockpit_session_id"]]
