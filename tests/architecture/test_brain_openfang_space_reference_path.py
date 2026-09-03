"""Architecture guard for the provider-neutral Brain-to-Space reference path."""

from pathlib import Path


DOCUMENT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "contracts"
    / "brain-openfang-space-reference-path-v1.md"
)


def _document() -> str:
    return DOCUMENT.read_text(encoding="utf-8")


def test_reference_path_is_ordered_and_fail_closed() -> None:
    document = _document()
    matrix = document.split("## Ordered fail-closed path", maxsplit=1)[1].split(
        "## Correlation and independent proof", maxsplit=1
    )[0]
    stages = (
        "ChannelIntentV1",
        "Brain admission",
        "`execution_deferred`",
        "OpenFang execution engine",
        "Space-Agent",
        "MCP/Service adapter",
        "independent Truth/Evidence",
        "ChannelResultV1",
    )

    positions = [matrix.index(stage) for stage in stages]

    assert positions == sorted(positions)
    assert "no direct fallback" in document.lower()
    assert "must not skip an unavailable or rejected stage" in document


def test_control_plane_execution_and_agent_boundaries_remain_explicit() -> None:
    document = _document()

    for required_text in (
        "Brain is the control plane",
        "OpenFang is the execution engine",
        "deterministic MCP/Service adapter does not use an LLM",
        "cognitive Space-Agent may use an LLM",
        "task_id",
        "approval_id",
        "cost_id",
        "evidence_id",
        "result_id",
        "correlation_id",
    ):
        assert required_text in document


def test_static_and_configured_references_do_not_claim_live_execution() -> None:
    document = _document()

    for required_text in (
        "Static reference",
        "Configured reference",
        "does not prove runtime reachability",
        "does not prove approval",
        "does not prove cost settlement",
        "does not prove evidence acceptance",
        "does not prove a successful result",
    ):
        assert required_text in document
