from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIEF = ROOT / "docs/operations/2026-08-01-codex-briefs-llm-konsolidierung.md"


def _brief() -> str:
    return BRIEF.read_text(encoding="utf-8").lower().replace("*", "")


def test_openfang_is_the_only_llm_gateway_and_fails_closed() -> None:
    brief = _brief()

    for invariant in (
        "openai",
        "openfang",
        "/v1/chat/completions",
        "vibemind_shared.get_client(role)",
        "fail-closed",
        "kein stiller bypass",
        "bounded-retry",
        "kosten- und approval-pfad",
    ):
        assert invariant in brief


def test_space_execution_keeps_deterministic_and_cognitive_paths_separate() -> None:
    brief = _brief()

    for invariant in (
        "54 openfang-agenten",
        "alle 13 space-agenten",
        "openfang-mcp-hub",
        "kein llm im pfad",
        "openfang-chat-agent",
        "tool-scope-allowlist",
        "truth:",
        "executor-agnostisch",
        "1,05 s end-to-end",
    ):
        assert invariant in brief


def test_migration_order_and_declared_exceptions_remain_bounded() -> None:
    brief = _brief()

    assert "brain (2)" in brief
    assert "la-fungus-search (4" in brief
    assert "ops (7)" in brief
    assert "security (7)" in brief
    assert "spaces (55)" in brief
    assert "voice (140" in brief
    for exception in ("voice_realtime", "tribe", "eventroutinghead", "openclaude-cli"):
        assert exception in brief
