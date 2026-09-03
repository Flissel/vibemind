from __future__ import annotations

from dataclasses import dataclass

from tools.v1_governance.git_state import GitAudit
from tools.v1_governance.handoff import OpenFangBoundaryVerification, TaskHandoff
from tools.v1_governance.models import SessionRequest


HIGH_RISK_CLASSES = {
    "deployment",
    "destructive",
    "breaking-contract",
    "database-migration",
    "secrets",
    "proxmox",
    "repo-move",
}


@dataclass(frozen=True)
class GateResult:
    ready: bool
    reasons: tuple[str, ...]
    unexecuted_tests: tuple[str, ...] = ()
    pre_existing_failures: tuple[str, ...] = ()
    deferred_decisions: tuple[str, ...] = ()
    openfang_boundary_verifications: tuple[OpenFangBoundaryVerification, ...] = ()


def evaluate_pr_readiness(
    request: SessionRequest,
    handoff: TaskHandoff,
    audit: GitAudit,
) -> GateResult:
    """Evaluate deterministic PR gates without mutating Git or remote state."""
    reasons: list[str] = []
    if request.schema_version != 2 or handoff.schema_version != 2:
        reasons.append("unsupported-provenance-schema")
    if not request.is_approved:
        reasons.append("request-not-approved")
    if not request.writes_allowed:
        reasons.append("request-not-writing")
    if request.session_id != handoff.session_id:
        reasons.append("session-mismatch")
    if request.parent_cockpit != handoff.parent_cockpit:
        reasons.append("parent-cockpit-mismatch")
    if request.request_reference != handoff.request_reference:
        reasons.append("request-reference-mismatch")
    if request.approval_reference != handoff.approval_reference:
        reasons.append("approval-reference-mismatch")
    if request.merge_position != handoff.merge_position:
        reasons.append("merge-position-mismatch")
    if {request.branch, handoff.branch, audit.branch} != {request.branch}:
        reasons.append("branch-mismatch")
    if audit.dirty_paths:
        reasons.append("dirty-worktree")
    if not handoff.commits:
        reasons.append("missing-commit-evidence")
    if not handoff.tests:
        reasons.append("missing-test-evidence")
    elif any(test.status == "failed" for test in handoff.tests):
        reasons.append("failed-test-evidence")
    elif not any(test.status == "passed" for test in handoff.tests):
        reasons.append("missing-passed-test-evidence")
    if not handoff.evidence:
        reasons.append("missing-evidence")
    if {dependency.session_id for dependency in handoff.dependencies} != set(request.dependencies):
        reasons.append("dependency-mismatch")
    elif any(not dependency.merged for dependency in handoff.dependencies):
        reasons.append("unmerged-dependency")
    if handoff.remaining_blockers:
        reasons.append("remaining-blockers")
    if request.risk_class in HIGH_RISK_CLASSES and not handoff.risk_approval_reference.strip():
        reasons.append("missing-risk-approval")
    return GateResult(
        ready=not reasons,
        reasons=tuple(reasons),
        unexecuted_tests=tuple(
            test.command for test in handoff.tests if test.status == "not_run"
        ),
        pre_existing_failures=tuple(
            test.command for test in handoff.tests if test.status == "failed_at_base"
        ),
        deferred_decisions=handoff.deferred_decisions,
        openfang_boundary_verifications=handoff.openfang_boundary_verifications,
    )
