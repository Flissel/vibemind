from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Mapping, cast

import yaml

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.models import APPROVAL_REFERENCE_PATTERN


# "not_run" exists so a session can declare a gate it could not execute instead of
# guessing a verdict for it. It never counts as evidence: the PR gate still demands at
# least one "passed", and pr_gate names every unexecuted command in its result.
# "failed_at_base" exists so a session can report a failure it measured but did not
# cause: the command fails identically at the base commit, and the change neither
# introduced nor repaired it. Without it the only honest options are to omit the
# measurement or to accept a block for someone else's breakage, and the first is what
# a session learns to do. It is never evidence either - at least one "passed" is still
# required, a genuine "failed" still blocks beside it, and pr_gate names every such
# command in its result so the claim is always visible and can be checked against the
# base commit by hand.
TEST_STATUSES = {"passed", "failed", "not_run", "failed_at_base"}
DEPLOYMENT_STATUSES = {"not_required", "verified", "pending_user_approval"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
COCKPIT_PATTERN = re.compile(r"^cockpit-[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUEST_REFERENCE_PATTERN = re.compile(
    r"^task-request:[a-z0-9]+(?:-[a-z0-9]+)*-v[1-9][0-9]*$"
)
def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise GovernanceError(f"{field} must be a mapping")
    return cast(Mapping[str, object], value)


def _string(data: Mapping[str, object], field: str, *, allow_empty: bool = False) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise GovernanceError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise GovernanceError(f"{field} must be non-empty")
    return value


def _boolean(data: Mapping[str, object], field: str) -> bool:
    value = data.get(field)
    if type(value) is not bool:
        raise GovernanceError(f"{field} must be a boolean")
    return value


def _list(data: Mapping[str, object], field: str) -> list[object]:
    value = data.get(field)
    if not isinstance(value, list):
        raise GovernanceError(f"{field} must be a list")
    return value


def _relative_evidence_path(value: str) -> str:
    candidate = PurePath(value)
    if not value.strip() or candidate.is_absolute() or ".." in candidate.parts:
        raise GovernanceError("evidence path must be a repo-relative path")
    return value


@dataclass(frozen=True)
class CommitEvidence:
    sha: str
    subject: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> CommitEvidence:
        sha = _string(data, "sha")
        if not FULL_SHA.fullmatch(sha):
            raise GovernanceError("commit sha must be a full SHA")
        return cls(sha=sha, subject=_string(data, "subject"))


@dataclass(frozen=True)
class TestEvidence:
    command: str
    status: str
    summary: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> TestEvidence:
        status = _string(data, "status")
        if status not in TEST_STATUSES:
            raise GovernanceError("unknown test status")
        return cls(
            command=_string(data, "command"), status=status, summary=_string(data, "summary")
        )


@dataclass(frozen=True)
class DependencyEvidence:
    session_id: str
    merged: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> DependencyEvidence:
        return cls(session_id=_string(data, "session_id"), merged=_boolean(data, "merged"))


@dataclass(frozen=True)
class EvidenceReference:
    kind: str
    path: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> EvidenceReference:
        return cls(
            kind=_string(data, "kind"),
            path=_relative_evidence_path(_string(data, "path")),
        )


# The five boundaries success condition 8 names for OpenFang. They are fixed here
# rather than read from the contract on purpose: the condition names these five, and a
# task that verified something else has not verified one of them. An unknown name is
# rejected instead of passed through, so the field cannot quietly grow a sixth boundary
# that no condition asks about.
OPENFANG_BOUNDARIES = frozenset({"execution", "provider", "cost", "approval", "evidence"})


@dataclass(frozen=True)
class OpenFangBoundaryVerification:
    """One boundary a task checked, and what it produced while checking it.

    This records an ACT of verification, not a verdict. "The contract asserts nothing
    here that a task could check" is a legitimate and expected entry - several of the
    five boundaries are in exactly that state - but it has to be written down, which is
    why evidence may not be empty.
    """

    boundary: str
    evidence: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> OpenFangBoundaryVerification:
        boundary = _string(data, "boundary")
        if boundary not in OPENFANG_BOUNDARIES:
            raise GovernanceError("unknown OpenFang boundary")
        evidence = _list(data, "evidence")
        if not evidence:
            raise GovernanceError("boundary evidence must not be empty")
        if any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise GovernanceError("boundary evidence must contain non-empty strings")
        return cls(boundary=boundary, evidence=tuple(cast(list[str], evidence)))

    def to_mapping(self) -> dict[str, object]:
        return {"boundary": self.boundary, "evidence": list(self.evidence)}


@dataclass(frozen=True)
class TaskHandoff:
    schema_version: int
    session_id: str
    branch: str
    parent_cockpit: str
    request_reference: str
    approval_reference: str
    commits: tuple[CommitEvidence, ...]
    tests: tuple[TestEvidence, ...]
    evidence: tuple[EvidenceReference, ...]
    dependencies: tuple[DependencyEvidence, ...]
    deployment_status: str
    remaining_blockers: tuple[str, ...]
    deferred_decisions: tuple[str, ...]
    openfang_boundary_verifications: tuple[OpenFangBoundaryVerification, ...]
    merge_position: int
    risk_approval_reference: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> TaskHandoff:
        if data.get("schema_version") != 2:
            raise GovernanceError("schema_version must be 2")
        deployment_status = _string(data, "deployment_status")
        if deployment_status not in DEPLOYMENT_STATUSES:
            raise GovernanceError("unknown deployment status")
        blockers = _list(data, "remaining_blockers")
        if any(not isinstance(blocker, str) or not blocker.strip() for blocker in blockers):
            raise GovernanceError("remaining_blockers must contain non-empty strings")
        # "deferred_decisions" is not a weaker "remaining_blockers". A blocker says the
        # work in this task is unfinished; a deferred decision says the task finished by
        # writing down a decision it was told not to make, and names whose it is. The PR
        # gate discloses them and lets the PR through, because refusing there would
        # punish a fail-closed deliverable for being honest about what it left open.
        deferred = _list(data, "deferred_decisions") if "deferred_decisions" in data else []
        if any(not isinstance(item, str) or not item.strip() for item in deferred):
            raise GovernanceError("deferred_decisions must contain non-empty strings")
        # Optional, exactly like "deferred_decisions". Making it mandatory would
        # invalidate every already-merged handoff at once - a breaking change to a
        # merged provenance corpus, which needs request-specific user authority.
        verifications = tuple(
            OpenFangBoundaryVerification.from_mapping(
                _mapping(item, "openfang boundary verification")
            )
            for item in (
                _list(data, "openfang_boundary_verifications")
                if "openfang_boundary_verifications" in data
                else []
            )
        )
        if len({item.boundary for item in verifications}) != len(verifications):
            raise GovernanceError(
                "openfang_boundary_verifications must contain unique boundaries"
            )
        parent_cockpit = _string(data, "parent_cockpit")
        if not COCKPIT_PATTERN.fullmatch(parent_cockpit):
            raise GovernanceError("parent_cockpit must be a valid cockpit ID")
        request_reference = _string(data, "request_reference")
        if not REQUEST_REFERENCE_PATTERN.fullmatch(request_reference):
            raise GovernanceError("request_reference must be a durable task request reference")
        approval_reference = _string(data, "approval_reference")
        if not APPROVAL_REFERENCE_PATTERN.fullmatch(approval_reference):
            raise GovernanceError("approval_reference must be a verifiable authority reference")
        merge_position = data.get("merge_position")
        if type(merge_position) is not int or merge_position < 1:
            raise GovernanceError("merge_position must be a positive integer")
        dependencies = tuple(
            DependencyEvidence.from_mapping(_mapping(item, "dependency"))
            for item in _list(data, "dependencies")
        )
        if len({dependency.session_id for dependency in dependencies}) != len(dependencies):
            raise GovernanceError("dependencies must contain unique session IDs")
        return cls(
            schema_version=2,
            session_id=_string(data, "session_id"),
            branch=_string(data, "branch"),
            parent_cockpit=parent_cockpit,
            request_reference=request_reference,
            approval_reference=approval_reference,
            commits=tuple(
                CommitEvidence.from_mapping(_mapping(item, "commit"))
                for item in _list(data, "commits")
            ),
            tests=tuple(
                TestEvidence.from_mapping(_mapping(item, "test"))
                for item in _list(data, "tests")
            ),
            evidence=tuple(
                EvidenceReference.from_mapping(_mapping(item, "evidence"))
                for item in _list(data, "evidence")
            ),
            dependencies=dependencies,
            deployment_status=deployment_status,
            remaining_blockers=tuple(cast(list[str], blockers)),
            deferred_decisions=tuple(cast(list[str], deferred)),
            openfang_boundary_verifications=verifications,
            merge_position=merge_position,
            risk_approval_reference=_string(
                data, "risk_approval_reference", allow_empty=True
            )
            if "risk_approval_reference" in data
            else "",
        )


def load_task_handoff(path: Path, repo_root: Path) -> TaskHandoff:
    """Load a handoff without requiring referenced evidence files to exist."""
    try:
        loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GovernanceError(f"cannot load task handoff: {type(exc).__name__}") from exc
    handoff = TaskHandoff.from_mapping(_mapping(loaded, "task handoff"))
    root = repo_root.resolve()
    for evidence in handoff.evidence:
        if not (root / evidence.path).resolve().is_relative_to(root):
            raise GovernanceError("evidence path must remain within the repo root")
    return handoff
