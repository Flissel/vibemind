from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tools.v1_governance.errors import GovernanceError


REGISTRY_PATH = Path("docs/governance/session-portfolio-registry-v1.json")
APPROVAL_LEDGER_PATH = Path("docs/governance/cockpit-approval-ledger-v1.json")
ACTIVATION_EVIDENCE_PATH = Path("docs/governance/cockpit-activation-evidence-v1.json")
EXTERNAL_OBSERVATIONS_PATH = Path("docs/governance/cockpit-external-observations-v1.json")
_APPROVAL_LEDGER_KEYS = {
    "schema_version",
    "membership_source",
    "approval_policy",
    "approvals",
}
_APPROVAL_RECORD_KEYS = {
    "cockpit_session_id",
    "visible_title",
    "approval_reference",
    "created_at",
}
_INDIVIDUAL_APPROVAL_REFERENCE = re.compile(
    r"^(?:codex-user-message:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
    r"|claude-user-message:session_[0-9A-Za-z]{16,64})@"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)
_RFC3339_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_REGISTRY_KEYS = {"schema_version", "authority", "cockpits"}
_REGISTRY_AUTHORITY = {
    "normative_membership": "portfolio",
    "current_lifecycle": "main-orchestrator-external",
}
_REGISTRY_RECORD_KEYS = {"cockpit_session_id", "historical_observations"}
_HISTORICAL_OBSERVATION_KEYS = {
    "evidence_scope",
    "evidence_source",
    "observation",
    "thread_id",
}
_ACTIVATION_EVIDENCE_KEYS = {
    "schema_version",
    "external_observations_sidecar",
    "authority",
    "cockpits",
}
_ACTIVATION_AUTHORITY = {
    "membership_source": str(REGISTRY_PATH).replace("\\", "/"),
    "membership_authority": "portfolio",
    "standing_activation_authority": "standing-autonomy:v1",
    "standing_activation_authority_scope": "authority-available-not-activation-proof",
    "current_lifecycle_authority": "main-orchestrator-external",
}
_ACTIVATION_RECORD_KEYS = {
    "cockpit_session_id",
    "membership_evidence",
    "standing_activation_authority",
    "historical_observation",
    "current_evidence",
}
_CURRENT_EVIDENCE_KEYS = {
    "activation",
    "interactivity",
    "approval",
    "durable_evidence_reference",
}
# Closed recording vocabulary. Every class other than "not-git-evidenced" exists
# only where a durable, strictly shaped reference form exists: session creation is
# referenced as ccr-session:<session-id>@<rfc3339>; an approval claim is backed by
# the closed cockpit approval ledger. Interactivity has no durable reference form
# and therefore stays not-git-evidenced only.
_ACTIVATION_EVIDENCE_CLASSES = frozenset({"not-git-evidenced", "git-evidenced-creation"})
_INTERACTIVITY_EVIDENCE_CLASSES = frozenset({"not-git-evidenced"})
_APPROVAL_EVIDENCE_CLASSES = frozenset(
    {"not-git-evidenced", "git-evidenced-approval-ledger"}
)
_DURABLE_CREATION_REFERENCE = re.compile(
    r"^ccr-session:session_[0-9A-Za-z]{16,64}@"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)
_EXTERNAL_OBSERVATIONS_KEYS = {
    "schema_version",
    "membership_source",
    "evidence_class",
    "observations",
}
_EXTERNAL_OBSERVATION_KEYS = {
    "cockpit_session_id",
    "evidence_scope",
    "evidence_source",
    "observation",
    "observed_at",
    "thread_id",
}
_CANONICAL_COCKPIT_IDS = frozenset(
    {
        "cockpit-agentfarm",
        "cockpit-brain",
        "cockpit-bubbles",
        "cockpit-channels",
        "cockpit-coding",
        "cockpit-deployment",
        "cockpit-desktop",
        "cockpit-flowzen",
        "cockpit-git",
        "cockpit-ideas",
        "cockpit-integration",
        "cockpit-marketing",
        "cockpit-minibook",
        "cockpit-mirofish",
        "cockpit-n8n",
        "cockpit-observability",
        "cockpit-openfang",
        "cockpit-research",
        "cockpit-rowboat",
        "cockpit-schedule",
        "cockpit-shared",
        "cockpit-video",
    }
)


@dataclass(frozen=True)
class CockpitApproval:
    cockpit_session_id: str
    visible_title: str
    approval_reference: str
    created_at: str


@dataclass(frozen=True)
class CockpitPortfolioStatus:
    cockpit_session_id: str
    membership: str
    pre_creation_approval_available: bool
    historical_observation_present: bool
    current_activation_evidence: str
    current_interactivity_evidence: str
    current_approval_evidence: str
    durable_evidence_reference: str | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "cockpit_session_id": self.cockpit_session_id,
            "membership": self.membership,
            "pre_creation_approval_available": self.pre_creation_approval_available,
            "historical_observation_present": self.historical_observation_present,
            "current_activation_evidence": self.current_activation_evidence,
            "current_interactivity_evidence": self.current_interactivity_evidence,
            "current_approval_evidence": self.current_approval_evidence,
            "durable_evidence_reference": self.durable_evidence_reference,
        }


def _registered_cockpit_ids(repo_root: Path) -> set[str]:
    registry_path = repo_root / REGISTRY_PATH
    try:
        payload: object = json.loads(registry_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GovernanceError("cockpit registry is unavailable") from exc
    except OSError as exc:
        raise GovernanceError("cockpit registry is unavailable") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("cockpit registry is malformed") from exc

    if not isinstance(payload, dict):
        raise GovernanceError("cockpit registry is malformed")
    cockpits = payload.get("cockpits")
    if not isinstance(cockpits, list):
        raise GovernanceError("cockpit registry is malformed")

    cockpit_ids: set[str] = set()
    for cockpit in cockpits:
        if not isinstance(cockpit, dict):
            raise GovernanceError("cockpit registry is malformed")
        cockpit_id = cockpit.get("cockpit_session_id")
        if not isinstance(cockpit_id, str) or not cockpit_id:
            raise GovernanceError("cockpit registry is malformed")
        if cockpit_id in cockpit_ids:
            raise GovernanceError("cockpit registry is malformed")
        cockpit_ids.add(cockpit_id)
    return cockpit_ids


def require_registered_parent_cockpit(repo_root: Path, parent_cockpit: str) -> None:
    """Reject a task whose parent cockpit is absent from the normative registry."""
    cockpit_ids = _registered_cockpit_ids(repo_root)
    if parent_cockpit not in cockpit_ids:
        raise GovernanceError("parent_cockpit is not registered")


def require_individual_cockpit_approval(
    repo_root: Path, cockpit_session_id: str
) -> CockpitApproval:
    """Require durable individual-user authority before a User-Owned cockpit is created."""
    registered_cockpits = _registered_cockpit_ids(repo_root)
    if cockpit_session_id not in registered_cockpits:
        raise GovernanceError("parent_cockpit is not registered")

    ledger_path = repo_root / APPROVAL_LEDGER_PATH
    try:
        payload: object = json.loads(ledger_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GovernanceError("cockpit approval ledger is unavailable") from exc
    except OSError as exc:
        raise GovernanceError("cockpit approval ledger is unavailable") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError("cockpit approval ledger is malformed") from exc

    if (
        not isinstance(payload, dict)
        or set(payload) != _APPROVAL_LEDGER_KEYS
        or payload.get("schema_version") != 1
        or payload.get("membership_source") != str(REGISTRY_PATH).replace("\\", "/")
        or payload.get("approval_policy") != "individual-user-approval-required"
        or not isinstance(payload.get("approvals"), list)
    ):
        raise GovernanceError("cockpit approval ledger is malformed")

    approvals: dict[str, CockpitApproval] = {}
    for record in payload["approvals"]:
        if not isinstance(record, dict) or set(record) != _APPROVAL_RECORD_KEYS:
            raise GovernanceError("cockpit approval ledger is malformed")
        record_cockpit = record.get("cockpit_session_id")
        visible_title = record.get("visible_title")
        approval_reference = record.get("approval_reference")
        created_at = record.get("created_at")
        if (
            not isinstance(record_cockpit, str)
            or record_cockpit not in registered_cockpits
            or record_cockpit in approvals
            or not isinstance(visible_title, str)
            or not visible_title.strip()
            or not isinstance(approval_reference, str)
            or not isinstance(created_at, str)
            or not _RFC3339_TIMESTAMP.fullmatch(created_at)
        ):
            raise GovernanceError("cockpit approval ledger is malformed")
        try:
            parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GovernanceError("cockpit approval ledger is malformed") from exc
        if parsed_created_at.tzinfo is None:
            raise GovernanceError("cockpit approval ledger is malformed")
        if not _INDIVIDUAL_APPROVAL_REFERENCE.fullmatch(approval_reference):
            raise GovernanceError("cockpit approvals require an individual user message")
        try:
            approval_timestamp = datetime.fromisoformat(
                approval_reference.rsplit("@", maxsplit=1)[1].replace("Z", "+00:00")
            )
        except (IndexError, ValueError) as exc:
            raise GovernanceError(
                "cockpit approvals require an individual user message"
            ) from exc
        if approval_timestamp.tzinfo is None:
            raise GovernanceError("cockpit approvals require an individual user message")
        if approval_timestamp > parsed_created_at:
            raise GovernanceError("cockpit approval must not follow creation")
        approvals[record_cockpit] = CockpitApproval(
            cockpit_session_id=record_cockpit,
            visible_title=visible_title,
            approval_reference=approval_reference,
            created_at=created_at,
        )

    try:
        return approvals[cockpit_session_id]
    except KeyError as exc:
        raise GovernanceError("individual cockpit approval is unavailable") from exc


def _read_portfolio_json(repo_root: Path, relative_path: Path, label: str) -> object:
    try:
        return json.loads((repo_root / relative_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError) as exc:
        raise GovernanceError(f"{label} is unavailable") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"{label} is malformed") from exc


def _portfolio_registry(repo_root: Path) -> dict[str, list[dict[str, object]]]:
    payload = _read_portfolio_json(repo_root, REGISTRY_PATH, "cockpit registry")
    if (
        not isinstance(payload, dict)
        or set(payload) != _REGISTRY_KEYS
        or payload.get("schema_version") != 1
        or payload.get("authority") != _REGISTRY_AUTHORITY
        or not isinstance(payload.get("cockpits"), list)
    ):
        raise GovernanceError("cockpit registry is malformed")

    registry: dict[str, list[dict[str, object]]] = {}
    for record in payload["cockpits"]:
        if not isinstance(record, dict) or set(record) != _REGISTRY_RECORD_KEYS:
            raise GovernanceError("cockpit registry is malformed")
        cockpit_id = record.get("cockpit_session_id")
        observations = record.get("historical_observations")
        if (
            not isinstance(cockpit_id, str)
            or not cockpit_id
            or cockpit_id in registry
            or not isinstance(observations, list)
        ):
            raise GovernanceError("cockpit registry is malformed")
        checked_observations: list[dict[str, object]] = []
        for observation in observations:
            if (
                not isinstance(observation, dict)
                or set(observation) != _HISTORICAL_OBSERVATION_KEYS
                or observation.get("evidence_scope") != "external-not-git-verified"
                or observation.get("evidence_source") != "external"
                or observation.get("observation") != "final_reported"
                or not isinstance(observation.get("thread_id"), str)
                or not observation["thread_id"]
            ):
                raise GovernanceError("cockpit registry is malformed")
            checked_observations.append(observation)
        registry[cockpit_id] = checked_observations
    if set(registry) != _CANONICAL_COCKPIT_IDS:
        raise GovernanceError(
            "cockpit registry does not match canonical portfolio membership"
        )
    return registry


def _activation_evidence(
    repo_root: Path, registered_cockpits: set[str]
) -> dict[str, dict[str, object]]:
    payload = _read_portfolio_json(
        repo_root, ACTIVATION_EVIDENCE_PATH, "cockpit activation evidence"
    )
    if (
        not isinstance(payload, dict)
        or set(payload) != _ACTIVATION_EVIDENCE_KEYS
        or payload.get("schema_version") != 1
        or payload.get("external_observations_sidecar")
        != str(EXTERNAL_OBSERVATIONS_PATH).replace("\\", "/")
        or payload.get("authority") != _ACTIVATION_AUTHORITY
        or not isinstance(payload.get("cockpits"), list)
    ):
        raise GovernanceError("cockpit activation evidence is malformed")

    current_evidence: dict[str, dict[str, object]] = {}
    for record in payload["cockpits"]:
        if not isinstance(record, dict) or set(record) != _ACTIVATION_RECORD_KEYS:
            raise GovernanceError("cockpit activation evidence is malformed")
        cockpit_id = record.get("cockpit_session_id")
        membership = record.get("membership_evidence")
        standing_authority = record.get("standing_activation_authority")
        historical = record.get("historical_observation")
        current = record.get("current_evidence")
        if (
            not isinstance(cockpit_id, str)
            or cockpit_id not in registered_cockpits
            or cockpit_id in current_evidence
            or membership
            != {"status": "normative", "source": str(REGISTRY_PATH).replace("\\", "/")}
            or standing_authority
            != {
                "status": "available",
                "reference": "standing-autonomy:v1",
                "proves_activation": False,
            }
            or not isinstance(historical, dict)
            or set(historical) != {
                "status",
                "evidence_scope",
                "evidence_source",
                "observation",
                "thread_id",
            }
            or historical.get("status") != "historical_external_only"
            or historical.get("evidence_scope") != "external-not-git-verified"
            or historical.get("evidence_source") != "external"
            or historical.get("observation") != "final_reported"
            or not isinstance(historical.get("thread_id"), str)
            or not historical["thread_id"]
            or not isinstance(current, dict)
            or set(current) != _CURRENT_EVIDENCE_KEYS
        ):
            raise GovernanceError("cockpit activation evidence is malformed")

        activation_claim = current.get("activation")
        interactivity_claim = current.get("interactivity")
        approval_claim = current.get("approval")
        reference = current.get("durable_evidence_reference")
        if (
            activation_claim not in _ACTIVATION_EVIDENCE_CLASSES
            or interactivity_claim not in _INTERACTIVITY_EVIDENCE_CLASSES
            or approval_claim not in _APPROVAL_EVIDENCE_CLASSES
        ):
            raise GovernanceError("cockpit activation evidence is malformed")
        if reference is None:
            # No durable reference recorded: every claim must stay fail-closed.
            if (
                activation_claim != "not-git-evidenced"
                or approval_claim != "not-git-evidenced"
            ):
                raise GovernanceError("cockpit activation evidence is malformed")
        else:
            # A durable reference is only recordable for a creation claim, and only
            # in the strictly shaped ccr-session:<session-id>@<rfc3339> form.
            if (
                not isinstance(reference, str)
                or not _DURABLE_CREATION_REFERENCE.fullmatch(reference)
                or activation_claim != "git-evidenced-creation"
            ):
                raise GovernanceError("cockpit activation evidence is malformed")
            try:
                reference_timestamp = datetime.fromisoformat(
                    reference.rsplit("@", maxsplit=1)[1].replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise GovernanceError(
                    "cockpit activation evidence is malformed"
                ) from exc
            if reference_timestamp.tzinfo is None:
                raise GovernanceError("cockpit activation evidence is malformed")
        if approval_claim == "git-evidenced-approval-ledger":
            try:
                require_individual_cockpit_approval(repo_root, cockpit_id)
            except GovernanceError as exc:
                if str(exc) != "individual cockpit approval is unavailable":
                    raise
                raise GovernanceError(
                    "cockpit activation evidence approval claim lacks a ledger approval"
                ) from exc

        current_evidence[cockpit_id] = {
            "activation": activation_claim,
            "interactivity": interactivity_claim,
            "approval": approval_claim,
            "durable_evidence_reference": reference,
            "historical_thread_id": historical["thread_id"],
        }
    if set(current_evidence) != registered_cockpits:
        raise GovernanceError("cockpit activation evidence is malformed")
    return current_evidence


def _external_observations(
    repo_root: Path, registered_cockpits: set[str]
) -> dict[str, str]:
    payload = _read_portfolio_json(
        repo_root,
        EXTERNAL_OBSERVATIONS_PATH,
        "cockpit external observations sidecar",
    )
    if (
        not isinstance(payload, dict)
        or set(payload) != _EXTERNAL_OBSERVATIONS_KEYS
        or payload.get("schema_version") != 1
        or payload.get("membership_source") != str(REGISTRY_PATH).replace("\\", "/")
        or payload.get("evidence_class") != "external-not-git-verified"
        or not isinstance(payload.get("observations"), list)
    ):
        raise GovernanceError("cockpit external observations sidecar is malformed")

    observations: dict[str, str] = {}
    for record in payload["observations"]:
        if not isinstance(record, dict) or set(record) != _EXTERNAL_OBSERVATION_KEYS:
            raise GovernanceError("cockpit external observations sidecar is malformed")
        cockpit_id = record.get("cockpit_session_id")
        observed_at = record.get("observed_at")
        thread_id = record.get("thread_id")
        if (
            not isinstance(cockpit_id, str)
            or cockpit_id not in registered_cockpits
            or cockpit_id in observations
            or record.get("evidence_scope") != "external-not-git-verified"
            or record.get("evidence_source") != "external-user-owned-thread"
            or record.get("observation") != "thread_observed"
            or not isinstance(observed_at, str)
            or not _RFC3339_TIMESTAMP.fullmatch(observed_at)
            or not isinstance(thread_id, str)
            or not thread_id
        ):
            raise GovernanceError("cockpit external observations sidecar is malformed")
        try:
            parsed_observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GovernanceError("cockpit external observations sidecar is malformed") from exc
        if parsed_observed_at.tzinfo is None:
            raise GovernanceError("cockpit external observations sidecar is malformed")
        observations[cockpit_id] = thread_id
    if set(observations) != registered_cockpits:
        raise GovernanceError("cockpit external observations sidecar is malformed")
    return observations


def cockpit_portfolio_status(repo_root: Path) -> tuple[CockpitPortfolioStatus, ...]:
    """Return one non-claiming status row for each normative cockpit.

    The check is read-only and deliberately reports evidence availability rather than
    lifecycle state. Historical or external records never establish current activity.
    """
    registry = _portfolio_registry(repo_root)
    registered_cockpits = set(registry)
    activation = _activation_evidence(repo_root, registered_cockpits)
    external_observations = _external_observations(repo_root, registered_cockpits)
    approved_cockpits: set[str] = set()
    for cockpit_id in registered_cockpits:
        try:
            require_individual_cockpit_approval(repo_root, cockpit_id)
        except GovernanceError as exc:
            if str(exc) != "individual cockpit approval is unavailable":
                raise
        else:
            approved_cockpits.add(cockpit_id)

    rows: list[CockpitPortfolioStatus] = []
    for cockpit_id in sorted(registered_cockpits):
        historical_observations = registry[cockpit_id]
        if (
            len(historical_observations) != 1
            or historical_observations[0]["thread_id"] != external_observations[cockpit_id]
            or historical_observations[0]["thread_id"]
            != activation[cockpit_id]["historical_thread_id"]
        ):
            raise GovernanceError("cockpit evidence membership is malformed")
        current = activation[cockpit_id]
        durable_reference = current["durable_evidence_reference"]
        rows.append(
            CockpitPortfolioStatus(
                cockpit_session_id=cockpit_id,
                membership="normative",
                pre_creation_approval_available=cockpit_id in approved_cockpits,
                historical_observation_present=True,
                current_activation_evidence=str(current["activation"]),
                current_interactivity_evidence=str(current["interactivity"]),
                current_approval_evidence=str(current["approval"]),
                durable_evidence_reference=(
                    durable_reference if isinstance(durable_reference, str) else None
                ),
            )
        )
    return tuple(rows)
