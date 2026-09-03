from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Mapping, cast

from tools.v1_governance.errors import GovernanceError


SessionType = Literal["space-cockpit", "task"]
ApprovalState = Literal["pending", "approved", "denied"]
RiskClass = Literal[
    "docs",
    "code",
    "deployment",
    "destructive",
    "breaking-contract",
    "database-migration",
    "secrets",
    "proxmox",
    "repo-move",
]

SESSION_TYPES = {"space-cockpit", "task"}
APPROVAL_STATES = {"pending", "approved", "denied"}
RISK_CLASSES = {
    "docs",
    "code",
    "deployment",
    "destructive",
    "breaking-contract",
    "database-migration",
    "secrets",
    "proxmox",
    "repo-move",
}
BRANCH_PATTERN = re.compile(
    r"^codex/[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$"
)
COCKPIT_PATTERN = re.compile(r"^cockpit-[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUEST_REFERENCE_PATTERN = re.compile(
    r"^task-request:[a-z0-9]+(?:-[a-z0-9]+)*-v[1-9][0-9]*$"
)
SESSION_ID_PATTERN = re.compile(r"^task-[a-z0-9]+(?:-[a-z0-9]+)*$")
APPROVAL_REFERENCE_PATTERN = re.compile(
    r"^(?:standing-autonomy:v1|"
    r"(?:codex-user-message:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|claude-user-message:session_[0-9A-Za-z]{16,64})@"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))$"
)
STANDING_AUTONOMY_REFERENCE = "standing-autonomy:v1"
STANDING_AUTONOMY_RISK_CLASSES = {"docs", "code"}
FORBIDDEN_SCOPES = {"*", "**", "/", ".", "./"}


def _integer(data: Mapping[str, object], field: str) -> int:
    value = data.get(field)
    if type(value) is not int:
        raise GovernanceError(f"{field} must be an integer")
    return value


def _boolean(data: Mapping[str, object], field: str) -> bool:
    value = data.get(field)
    if type(value) is not bool:
        raise GovernanceError(f"{field} must be a boolean")
    return value


def _string(data: Mapping[str, object], field: str, *, allow_empty: bool = False) -> str:
    value = data.get(field)
    if not isinstance(value, str):
        raise GovernanceError(f"{field} must be a string")
    if not allow_empty and not value.strip():
        raise GovernanceError(f"{field} must be non-empty")
    return value


def _string_list(data: Mapping[str, object], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value:
        raise GovernanceError(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise GovernanceError(f"{field} must contain non-empty strings")
    return tuple(cast(list[str], value))


def _optional_string_list(data: Mapping[str, object], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list):
        raise GovernanceError(f"{field} must be a list")
    if any(not isinstance(item, str) or not SESSION_ID_PATTERN.fullmatch(item) for item in value):
        raise GovernanceError(f"{field} must contain valid task session IDs")
    result = tuple(cast(list[str], value))
    if len(result) != len(set(result)):
        raise GovernanceError(f"{field} must contain unique session IDs")
    return result


@dataclass(frozen=True)
class SessionRequest:
    schema_version: int
    session_id: str
    session_type: SessionType
    space: str
    parent_cockpit: str
    request_reference: str
    objective: str
    repositories: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    writes_allowed: bool
    approval_status: ApprovalState
    approval_reference: str
    base_ref: str
    branch: str
    risk_class: RiskClass
    dependencies: tuple[str, ...]
    merge_position: int

    @property
    def is_approved(self) -> bool:
        return self.approval_status == "approved"

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> SessionRequest:
        schema_version = _integer(data, "schema_version")
        if schema_version not in {1, 2}:
            raise GovernanceError("schema_version must be 1 or 2")

        session_type_value = _string(data, "session_type")
        if session_type_value not in SESSION_TYPES:
            raise GovernanceError("unknown session_type")
        session_type = cast(SessionType, session_type_value)

        approval_value = _string(data, "approval_status")
        if approval_value not in APPROVAL_STATES:
            raise GovernanceError("unknown approval_status")
        approval_status = cast(ApprovalState, approval_value)

        risk_value = _string(data, "risk_class")
        if risk_value not in RISK_CLASSES:
            raise GovernanceError("unknown risk_class")
        risk_class = cast(RiskClass, risk_value)

        writes_allowed = _boolean(data, "writes_allowed")
        approval_reference = _string(data, "approval_reference", allow_empty=True)
        branch = _string(data, "branch", allow_empty=True)
        allowed_paths = _string_list(data, "allowed_paths")
        parent_cockpit = (
            _string(data, "parent_cockpit", allow_empty=True)
            if schema_version == 2
            else ""
        )
        request_reference = (
            _string(data, "request_reference", allow_empty=True)
            if schema_version == 2
            else ""
        )
        dependencies = _optional_string_list(data, "dependencies") if schema_version == 2 else ()
        merge_position = _integer(data, "merge_position") if schema_version == 2 else 1

        if session_type == "space-cockpit" and writes_allowed:
            raise GovernanceError("space-cockpit sessions are read-only")
        if writes_allowed and approval_status != "approved":
            raise GovernanceError("writing sessions require approved status")
        if approval_status == "approved" and not approval_reference.strip():
            raise GovernanceError("approved sessions require an approval reference")
        if (
            schema_version == 2
            and approval_status == "approved"
            and not APPROVAL_REFERENCE_PATTERN.fullmatch(approval_reference)
        ):
            raise GovernanceError("approved sessions require a verifiable approval_reference")
        if (
            schema_version == 2
            and approval_reference == STANDING_AUTONOMY_REFERENCE
            and risk_class not in STANDING_AUTONOMY_RISK_CLASSES
        ):
            raise GovernanceError("standing autonomy permits only docs or code risk classes")
        if writes_allowed and not BRANCH_PATTERN.fullmatch(branch):
            raise GovernanceError("writing sessions require a valid codex branch")
        if (
            schema_version == 2
            and session_type == "task"
            and not COCKPIT_PATTERN.fullmatch(parent_cockpit)
        ):
            raise GovernanceError("task sessions require a valid parent_cockpit")
        if (
            schema_version == 2
            and session_type == "task"
            and not REQUEST_REFERENCE_PATTERN.fullmatch(request_reference)
        ):
            raise GovernanceError("task sessions require a durable request_reference")
        if schema_version == 2 and merge_position < 1:
            raise GovernanceError("merge_position must be a positive integer")
        if any(scope.strip() in FORBIDDEN_SCOPES for scope in allowed_paths):
            raise GovernanceError("broad scope is forbidden")

        return cls(
            schema_version=schema_version,
            session_id=_string(data, "session_id"),
            session_type=session_type,
            space=_string(data, "space"),
            parent_cockpit=parent_cockpit,
            request_reference=request_reference,
            objective=_string(data, "objective"),
            repositories=_string_list(data, "repositories"),
            allowed_paths=allowed_paths,
            writes_allowed=writes_allowed,
            approval_status=approval_status,
            approval_reference=approval_reference,
            base_ref=_string(data, "base_ref"),
            branch=branch,
            risk_class=risk_class,
            dependencies=dependencies,
            merge_position=merge_position,
        )
