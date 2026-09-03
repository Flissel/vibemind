import pytest

from tools.v1_governance.errors import GovernanceError
from tools.v1_governance.models import SessionRequest


VALID: dict[str, object] = {
    "schema_version": 2,
    "session_id": "task-coding-1042",
    "session_type": "task",
    "space": "coding",
    "parent_cockpit": "cockpit-coding",
    "request_reference": "task-request:task-coding-1042-v1",
    "objective": "Add the async code-generation start endpoint",
    "repositories": ["vibemind-v1"],
    "allowed_paths": ["tools/v1_governance/**", "tests/v1_governance/**"],
    "writes_allowed": True,
    "approval_status": "approved",
    "approval_reference": "codex-user-message:019fa01e-5cd6-7ac0-b320-7222affb6164@2026-07-30T12:00:00+02:00",
    "base_ref": "origin/master",
    "branch": "codex/coding/task-coding-1042-codegen-start",
    "risk_class": "code",
    "dependencies": ["task-platform-0004"],
    "merge_position": 2,
}


def test_approved_task_request_is_valid() -> None:
    request = SessionRequest.from_mapping(VALID)
    assert request.is_approved


@pytest.mark.parametrize("risk_class", ["docs", "code"])
def test_standing_autonomy_approves_bounded_routine_tasks(risk_class: str) -> None:
    request = SessionRequest.from_mapping(
        {
            **VALID,
            "risk_class": risk_class,
            "approval_reference": "standing-autonomy:v1",
        }
    )

    assert request.is_approved
    assert request.approval_reference == "standing-autonomy:v1"


@pytest.mark.parametrize(
    "risk_class",
    [
        "deployment",
        "destructive",
        "breaking-contract",
        "database-migration",
        "secrets",
        "proxmox",
        "repo-move",
    ],
)
def test_standing_autonomy_rejects_high_risk_tasks(risk_class: str) -> None:
    data = {
        **VALID,
        "risk_class": risk_class,
        "approval_reference": "standing-autonomy:v1",
    }

    with pytest.raises(GovernanceError, match="standing autonomy"):
        SessionRequest.from_mapping(data)


def test_claude_user_message_reference_approves_task_request() -> None:
    reference = (
        "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@"
        "2026-08-13T10:00:00+02:00"
    )

    request = SessionRequest.from_mapping({**VALID, "approval_reference": reference})

    assert request.is_approved
    assert request.approval_reference == reference


@pytest.mark.parametrize(
    "reference",
    [
        "claude-user-message:01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_abc123@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_01SdA3ftgP3wciDbcF!Kw4uk@2026-08-13T10:00:00+02:00",
        "claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk",
        "claude-user-message: session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T10:00:00+02:00",
    ],
)
def test_malformed_claude_user_message_references_are_rejected(reference: str) -> None:
    data = {**VALID, "approval_reference": reference}
    with pytest.raises(GovernanceError, match="approval_reference"):
        SessionRequest.from_mapping(data)


@pytest.mark.parametrize(
    "field", ["approval_reference", "branch", "parent_cockpit", "request_reference"]
)
def test_approved_writing_request_requires_gate_fields(field: str) -> None:
    data = {**VALID, field: ""}
    with pytest.raises(GovernanceError):
        SessionRequest.from_mapping(data)


def test_cockpit_cannot_write() -> None:
    data = {**VALID, "session_type": "space-cockpit", "writes_allowed": True}
    with pytest.raises(GovernanceError, match="read-only"):
        SessionRequest.from_mapping(data)


def test_root_wildcard_scope_is_rejected() -> None:
    data = {**VALID, "allowed_paths": ["**"]}
    with pytest.raises(GovernanceError, match="broad scope"):
        SessionRequest.from_mapping(data)


@pytest.mark.parametrize("field", ["repositories", "allowed_paths"])
def test_required_lists_cannot_be_empty(field: str) -> None:
    data = {**VALID, field: []}
    with pytest.raises(GovernanceError, match="non-empty"):
        SessionRequest.from_mapping(data)


def test_invalid_field_type_is_rejected() -> None:
    data = {**VALID, "writes_allowed": "yes"}
    with pytest.raises(GovernanceError, match="writes_allowed"):
        SessionRequest.from_mapping(data)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parent_cockpit", "coding", "parent_cockpit"),
        ("request_reference", "user-message:2026-07-30", "request_reference"),
        ("approval_reference", "user-message:2026-07-30", "approval_reference"),
        ("dependencies", ["task-platform-0004", "task-platform-0004"], "unique"),
        ("merge_position", 0, "merge_position"),
    ],
)
def test_v2_provenance_fields_are_strictly_validated(
    field: str, value: object, message: str
) -> None:
    data = {**VALID, field: value}
    with pytest.raises(GovernanceError, match=message):
        SessionRequest.from_mapping(data)
