from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPOSITORY_ROOT / "docs/governance/cockpit-activation-evidence-v1.json"
REGISTRY_PATH = REPOSITORY_ROOT / "docs/governance/session-portfolio-registry-v1.json"
MANDATE_PATH = REPOSITORY_ROOT / "docs/governance/standing-autonomous-mandate-v1.md"
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/runbooks/v1-session-lifecycle.md"
PORTFOLIO_PATH = (
    REPOSITORY_ROOT
    / "docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md"
)


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _portfolio_cockpit_ids() -> set[str]:
    portfolio = PORTFOLIO_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"\| `(cockpit-[a-z0-9-]+)` \|", portfolio))


def test_ledger_exactly_matches_registry_and_portfolio_membership() -> None:
    ledger = _json(LEDGER_PATH)
    registry = _json(REGISTRY_PATH)

    ledger_cockpits = ledger["cockpits"]
    registry_cockpits = registry["cockpits"]
    assert isinstance(ledger_cockpits, list)
    assert isinstance(registry_cockpits, list)

    ledger_ids = [entry["cockpit_session_id"] for entry in ledger_cockpits]
    registry_ids = [entry["cockpit_session_id"] for entry in registry_cockpits]
    assert len(ledger_ids) == 22
    assert len(ledger_ids) == len(set(ledger_ids))
    assert ledger_ids == registry_ids
    assert set(ledger_ids) == _portfolio_cockpit_ids()

    for entry in ledger_cockpits:
        assert entry["membership_evidence"] == {
            "status": "normative",
            "source": "docs/governance/session-portfolio-registry-v1.json",
        }


def test_ledger_separates_authority_from_activation_evidence() -> None:
    ledger = _json(LEDGER_PATH)
    mandate = MANDATE_PATH.read_text(encoding="utf-8")

    assert ledger["schema_version"] == 1
    assert ledger["authority"] == {
        "current_lifecycle_authority": "main-orchestrator-external",
        "membership_authority": "portfolio",
        "membership_source": "docs/governance/session-portfolio-registry-v1.json",
        "standing_activation_authority": "standing-autonomy:v1",
        "standing_activation_authority_scope": "authority-available-not-activation-proof",
    }
    assert "`standing-autonomy:v1` records the user's standing instruction" in mandate

    for entry in ledger["cockpits"]:
        assert entry["standing_activation_authority"] == {
            "proves_activation": False,
            "reference": "standing-autonomy:v1",
            "status": "available",
        }


def test_historical_observations_are_copied_without_current_claims() -> None:
    ledger = _json(LEDGER_PATH)
    registry = _json(REGISTRY_PATH)
    ledger_by_id = {
        entry["cockpit_session_id"]: entry for entry in ledger["cockpits"]
    }
    registry_by_id = {
        entry["cockpit_session_id"]: entry for entry in registry["cockpits"]
    }

    expected_thread_ids = {
        "cockpit-openfang": "019fcdb3-d021-73a0-9d8b-7b93ee5be965",
        "cockpit-agentfarm": "019fcf2c-9249-7040-abc7-a0bdf0e1cabc",
    }

    historical_count = 0
    for cockpit_id, registry_entry in registry_by_id.items():
        observations = registry_entry["historical_observations"]
        ledger_observation = ledger_by_id[cockpit_id]["historical_observation"]
        historical_count += 1
        assert len(observations) == 1
        assert ledger_observation == {
            "evidence_scope": "external-not-git-verified",
            "evidence_source": "external",
            "observation": "final_reported",
            "status": "historical_external_only",
            "thread_id": observations[0]["thread_id"],
        }
        if cockpit_id in expected_thread_ids:
            assert observations[0]["thread_id"] == expected_thread_ids[cockpit_id]

    assert historical_count == 22


# Deliberately lifted by task-governance-0031 (eleven wave-1..3 records) and
# task-governance-0033 (eleven wave-4..6 records): all creation records from
# docs/governance/session-request-queue-v1.md section 2.1 are recorded as
# git-evidenced-creation entries with their durable ccr-session references.
# Any entry outside this map stays strictly not-git-evidenced with a null
# reference, and interactivity never carries a claim.
EXPECTED_CREATION_REFERENCES = {
    "cockpit-git": "ccr-session:session_01RPNeXkEKZJxwvm1PgThPiM@2026-08-13T10:07:46Z",
    "cockpit-shared": "ccr-session:session_01QcNtCS4G5WjaisymA2CVtz@2026-08-13T10:08:10Z",
    "cockpit-brain": "ccr-session:session_01QRN26s9tpp4ZfY5G3BKqtT@2026-08-13T10:08:21Z",
    "cockpit-deployment": "ccr-session:session_01FH9V1HccAKFTsg31BnLp1c@2026-08-13T10:08:33Z",
    "cockpit-openfang": "ccr-session:session_015Ljwv8QaWgBhn8hvVXk8j3@2026-08-13T15:24:08Z",
    "cockpit-integration": "ccr-session:session_01RcmRkiDCyKN5tAdw5TLWCH@2026-08-13T15:24:30Z",
    "cockpit-observability": "ccr-session:session_01Vz4R7MWoozMhdnXDKD7o4b@2026-08-13T15:24:43Z",
    "cockpit-channels": "ccr-session:session_0147zJxXhizNHjMRg6shHD8X@2026-08-13T15:24:54Z",
    "cockpit-ideas": "ccr-session:session_011HPbWYGoFkWfJyfsMr9PZg@2026-08-13T18:33:27Z",
    "cockpit-bubbles": "ccr-session:session_01KUPG3WK5XbkmZtgUvmkeyh@2026-08-13T18:33:39Z",
    "cockpit-minibook": "ccr-session:session_01TjehuDCbu3qSVCgxBB9h7T@2026-08-13T18:33:50Z",
    "cockpit-coding": "ccr-session:session_01LGsUreNkJQ9Z95HG3FU5SB@2026-08-14T13:51:49Z",
    "cockpit-desktop": "ccr-session:session_01PfqU6J1ZYxiA3HYwmpBY6A@2026-08-14T13:51:58Z",
    "cockpit-research": "ccr-session:session_01QNovqXMThUdDuUVjgbow7Y@2026-08-14T13:52:16Z",
    "cockpit-rowboat": "ccr-session:session_01C5WQGLwvFaYdndhphoSZc6@2026-08-14T13:52:25Z",
    "cockpit-schedule": "ccr-session:session_017bGa7hswDNfDfXZYd6gEYL@2026-08-14T13:52:43Z",
    "cockpit-flowzen": "ccr-session:session_013nY4TrknvcbSaqZf4fCFWZ@2026-08-14T13:52:51Z",
    "cockpit-mirofish": "ccr-session:session_01WPy2KSna28AmBoCnvh3xLT@2026-08-14T13:53:09Z",
    "cockpit-marketing": "ccr-session:session_01MtcHMpwR87h66oVV85cVrE@2026-08-14T13:53:19Z",
    "cockpit-n8n": "ccr-session:session_01HKiohkamKh5X9FhZrCrWou@2026-08-14T13:53:37Z",
    "cockpit-video": "ccr-session:session_01UtXeMZgGTGbxqSMiUA7Lt1@2026-08-14T13:53:47Z",
    "cockpit-agentfarm": "ccr-session:session_01MVDw1byxFgk7L6rY7C1EL2@2026-08-14T13:54:06Z",
}


def test_current_activation_interactivity_and_approval_fail_closed() -> None:
    ledger = _json(LEDGER_PATH)

    assert ledger["external_observations_sidecar"] == (
        "docs/governance/cockpit-external-observations-v1.json"
    )

    recorded = 0
    for entry in ledger["cockpits"]:
        cockpit_id = entry["cockpit_session_id"]
        current = entry["current_evidence"]
        assert current["interactivity"] == "not-git-evidenced"
        if cockpit_id in EXPECTED_CREATION_REFERENCES:
            recorded += 1
            assert current == {
                "activation": "git-evidenced-creation",
                "approval": "git-evidenced-approval-ledger",
                "durable_evidence_reference": EXPECTED_CREATION_REFERENCES[cockpit_id],
                "interactivity": "not-git-evidenced",
            }
        else:
            assert current == {
                "activation": "not-git-evidenced",
                "approval": "not-git-evidenced",
                "durable_evidence_reference": None,
                "interactivity": "not-git-evidenced",
            }
        for claim in ("activation", "interactivity", "approval"):
            if current[claim] != "not-git-evidenced":
                assert current["durable_evidence_reference"]

    assert recorded == 22


def test_governance_docs_explain_ledger_and_supersede_stale_fork_claim() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    portfolio = PORTFOLIO_PATH.read_text(encoding="utf-8")

    assert "cockpit-activation-evidence-v1.json" in runbook
    assert "authority available" in runbook
    assert "does not prove activation" in runbook
    assert "historical observation" in runbook
    assert "current activation or interactivity" in runbook
    assert "22 historical external observations" in runbook
    assert "maintenance delegation of 2026-08-13" in runbook

    assert "### 2.1 Aktuelles Repository-Fork-Gate" not in portfolio
    assert "origin/master pinnt den ref-losen Child-Commit `394104d`" not in portfolio
    fork_section = portfolio.split("### 2.1", maxsplit=1)[1].split("## 3.", maxsplit=1)[0]
    assert "historisch" in fork_section.lower()
    assert "superseded" in fork_section.lower()
    assert "kein aktueller" in fork_section.lower()
