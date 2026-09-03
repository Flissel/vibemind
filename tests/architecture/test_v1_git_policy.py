from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_local_worktrees_and_runtime_state_are_ignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".worktrees/" in ignored
    assert ".vibemind/state/" in ignored


def test_repo_instructions_enable_bounded_standing_autonomy() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    combined = f"{agents}\n{claude}".lower()
    assert "standing-autonomy:v1" in combined
    assert "without per-session user interaction" in combined
    assert "isolierter worktree" in combined
    assert "nicht direkt" in combined
    assert "commit directly to `master`" not in combined


def test_workboard_is_the_live_lock_under_d1() -> None:
    """D1 (2026-08-18) reconciled the two coordination protocols.

    The Codex line had marked WORKBOARD.md a legacy snapshot that takes no new
    claims; the operational line treated it as mandatory. The user's decision is
    that both layers coexist and WORKBOARD stays the live lock, so the board
    must carry a usable claim protocol and CLAUDE.md must state the resolution.
    """
    board = (ROOT / "WORKBOARD.md").read_text(encoding="utf-8")
    assert "## In Arbeit" in board
    assert "Claim" in board

    guide = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "D1" in guide
    assert "Live-Lock" in guide


def test_v1_session_and_integration_routines_are_documented() -> None:
    required = {
        ".agents/skills/v1-session-start/SKILL.md": [
            "standing autonomy",
            "without pausing",
            "space-cockpit",
            "task",
            "high-risk",
        ],
        ".agents/skills/v1-task-handoff/SKILL.md": [
            "commit sha",
            "test evidence",
            "remaining blockers",
        ],
        ".agents/skills/v1-pr-integration/SKILL.md": [
            "merge order",
            "submodule pin",
            "post-merge",
        ],
        "docs/runbooks/v1-session-lifecycle.md": [
            "standing-autonomy-admitted",
            "handoff-ready",
            "checks-green",
        ],
        "docs/runbooks/smartgit-worktrees.md": [
            "visual client",
            "source of truth",
            "refresh",
        ],
    }

    for relative_path, phrases in required.items():
        content = (ROOT / relative_path).read_text(encoding="utf-8").lower()
        for phrase in phrases:
            assert phrase in content, f"{phrase!r} missing from {relative_path}"


def test_standing_autonomy_contract_is_bounded_and_noninteractive() -> None:
    contract = (ROOT / "docs/governance/standing-autonomous-mandate-v1.md").read_text(
        encoding="utf-8"
    )

    for statement in (
        "`standing-autonomy:v1`",
        "without routine user interaction",
        "docs",
        "code",
        "isolated worktree",
        "secondary supervisory process",
        "does not authorize secrets",
        "does not authorize destructive production actions",
    ):
        assert statement in contract
