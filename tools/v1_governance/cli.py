from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.git_state import audit_repository, run_git
from tools.v1_governance.handoff import load_task_handoff
from tools.v1_governance.manifest import validate_manifest
from tools.v1_governance.models import SessionRequest
from tools.v1_governance.portfolio import (
    cockpit_portfolio_status,
    require_individual_cockpit_approval,
    require_registered_parent_cockpit,
)
from tools.v1_governance.pr_gate import evaluate_pr_readiness
from tools.v1_governance.session import (
    create_task_worktree,
    load_session_request,
    plan_task_worktree,
)
from tools.v1_governance.submodule_readiness import assess_submodule_readiness


def _require_current_writing_provenance(request: object) -> None:
    """Reject legacy request schemas before a writing CLI operation can proceed."""
    if not isinstance(request, SessionRequest):
        raise GovernanceError("invalid session request")
    if request.writes_allowed and request.schema_version != 2:
        raise GovernanceError("writing CLI operations require session request schema_version 2")


def _require_registered_task_parent(repo_root: Path, request: SessionRequest) -> None:
    if request.schema_version == 2 and request.session_type == "task":
        require_registered_parent_cockpit(repo_root, request.parent_cockpit)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tools.v1_governance")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit")
    audit.add_argument("--repo", type=Path, default=Path("."))
    audit.add_argument("--format", choices=("json",), default="json")
    audit.add_argument("--fetch", action="store_true")
    manifest = commands.add_parser("manifest")
    manifest_commands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_validate = manifest_commands.add_parser("validate")
    manifest_validate.add_argument("--repo", type=Path, default=Path("."))
    manifest_validate.add_argument("--manifest", type=Path)
    manifest_validate.add_argument("--format", choices=("json",), default="json")
    submodules = commands.add_parser("submodules")
    submodule_commands = submodules.add_subparsers(dest="submodule_command", required=True)
    readiness = submodule_commands.add_parser("readiness")
    readiness.add_argument("--repo", type=Path, default=Path("."))
    readiness.add_argument("--format", choices=("json",), default="json")
    cockpit = commands.add_parser("cockpit")
    cockpit_commands = cockpit.add_subparsers(dest="cockpit_command", required=True)
    approval_check = cockpit_commands.add_parser("approval-check")
    approval_check.add_argument("--repo", type=Path, default=Path("."))
    approval_check.add_argument("--cockpit", required=True)
    portfolio_check = cockpit_commands.add_parser("portfolio-check")
    portfolio_check.add_argument("--repo", type=Path, default=Path("."))
    session = commands.add_parser("session")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    validate = session_commands.add_parser("validate")
    validate.add_argument("--repo", type=Path, default=Path("."))
    validate.add_argument("--request", type=Path, required=True)
    start = session_commands.add_parser("start")
    start.add_argument("--repo", type=Path, default=Path("."))
    start.add_argument("--request", type=Path, required=True)
    start.add_argument("--worktrees-root", type=Path, default=Path(".worktrees"))
    execution = start.add_mutually_exclusive_group()
    execution.add_argument("--dry-run", action="store_true")
    execution.add_argument("--execute", action="store_true")
    pr = commands.add_parser("pr")
    pr_commands = pr.add_subparsers(dest="pr_command", required=True)
    check = pr_commands.add_parser("check")
    check.add_argument("--repo", type=Path, default=Path("."))
    check.add_argument("--request", type=Path, required=True)
    check.add_argument("--handoff", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "manifest" and args.manifest_command == "validate":
        manifest_path = args.manifest or args.repo / "repo-manifest.yaml"
        try:
            findings = [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "path": issue.path,
                    "severity": issue.severity,
                }
                for issue in sorted(
                    validate_manifest(args.repo, manifest_path),
                    key=lambda issue: (issue.code, issue.path, issue.message),
                )
            ]
        except GovernanceError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 1
        except Exception as exc:
            print(json.dumps({"error": f"technical error: {type(exc).__name__}"}, sort_keys=True))
            return 1
        print(json.dumps({"findings": findings}, sort_keys=True))
        return 0 if all(finding["severity"] == "warning" for finding in findings) else 2
    if args.command == "submodules" and args.submodule_command == "readiness":
        result = assess_submodule_readiness(args.repo)
        print(json.dumps(result.to_mapping(), sort_keys=True))
        return 0 if result.ready else 2
    if args.command == "pr" and args.pr_command == "check":
        try:
            request = load_session_request(args.request)
            handoff = load_task_handoff(args.handoff, args.repo)
            _require_registered_task_parent(args.repo, request)
            require_registered_parent_cockpit(args.repo, handoff.parent_cockpit)
            result = evaluate_pr_readiness(request, handoff, audit_repository(args.repo))
            report: dict[str, object] = {"ready": result.ready, "reasons": result.reasons}
            if result.unexecuted_tests:
                report["unexecuted_tests"] = result.unexecuted_tests
            if result.pre_existing_failures:
                report["pre_existing_failures"] = result.pre_existing_failures
            if result.deferred_decisions:
                report["deferred_decisions"] = result.deferred_decisions
            # Disclosure, never a gate. What a task checked at an OpenFang boundary is
            # surfaced beside readiness the way unexecuted tests and deferred decisions
            # already are; blocking on it would make the honest record cost something.
            if result.openfang_boundary_verifications:
                report["openfang_boundary_verifications"] = [
                    item.to_mapping() for item in result.openfang_boundary_verifications
                ]
            print(json.dumps(report, sort_keys=True))
            return 0 if result.ready else 2
        except GovernanceError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 1
    if args.command == "cockpit" and args.cockpit_command == "approval-check":
        try:
            approval = require_individual_cockpit_approval(args.repo, args.cockpit)
            print(
                json.dumps(
                    {
                        "approved": True,
                        "approval_reference": approval.approval_reference,
                        "cockpit_session_id": approval.cockpit_session_id,
                        "created_at": approval.created_at,
                        "visible_title": approval.visible_title,
                    },
                    sort_keys=True,
                )
            )
            return 0
        except GovernanceError as exc:
            print(
                json.dumps(
                    {
                        "approved": False,
                        "cockpit_session_id": args.cockpit,
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
            )
            return 2
    if args.command == "cockpit" and args.cockpit_command == "portfolio-check":
        try:
            for row in cockpit_portfolio_status(args.repo):
                print(json.dumps(row.to_mapping(), sort_keys=True))
            return 0
        except GovernanceError as exc:
            print(json.dumps({"error": str(exc)}, sort_keys=True))
            return 2
    try:
        if args.command == "audit":
            if args.fetch:
                run_git(args.repo, "fetch", "origin", "--prune")
            print(json.dumps(audit_repository(args.repo).to_mapping(), sort_keys=True))
            return 0
        if args.command == "session" and args.session_command == "validate":
            request = load_session_request(args.request)
            _require_current_writing_provenance(request)
            _require_registered_task_parent(args.repo, request)
            print(
                json.dumps(
                    {"approved": request.is_approved, "session_id": request.session_id},
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "session" and args.session_command == "start":
            request = load_session_request(args.request)
            _require_current_writing_provenance(request)
            worktrees_root = args.worktrees_root
            if not worktrees_root.is_absolute():
                worktrees_root = args.repo / worktrees_root
            plan = plan_task_worktree(args.repo, request, worktrees_root)
            if args.execute:
                create_task_worktree(args.repo, plan)
            output = dict(plan.to_mapping())
            output["executed"] = bool(args.execute)
            print(json.dumps(output, sort_keys=True))
            return 0
    except GovernanceError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 2
