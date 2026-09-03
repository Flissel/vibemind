"""Documentation guard for the n8n Space declaration.

n8n is a registry-routed MCP tool surface, not a Space application. The
catalog must not claim a dedicated Space application, a Space source
directory or Space-owned data, and it must keep the eight `n8n.*` events
and the `brain-n8n` binding intact.

Evidence at the pinned `vibemind-os` revision (`repo-manifest.yaml`
`expected_gitlink_pin`):

- `vibemind-os/config/space_agent_registry.yml:241-259` binds eight
  `n8n.*` events directly to MCP tools with `mcp_servers: [vibemind-db, n8n]`;
- no `spaces/n8n` directory exists in this repository or in `vibemind-os`
  (`vibemind-os/voice/python/spaces` is a symlink to `vibemind-os/spaces`);
- `infra/swarm/vibemind-stack.yml` gates a single third-party `n8n`
  service behind the `space-n8n` Compose profile;
- `infra/swarm/profiles/` carries no n8n operator profile document.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "docs" / "SPACES.md"
CONTRACT = ROOT / "docs" / "spaces" / "n8n" / "contract.md"

REGISTRY_EVENTS = (
    "n8n.generate",
    "n8n.list",
    "n8n.status",
    "n8n.activate",
    "n8n.deactivate",
    "n8n.delete",
    "n8n.execute",
    "n8n.describe",
)


def _catalog() -> str:
    return CATALOG.read_text(encoding="utf-8")


def _n8n_section() -> str:
    document = _catalog()
    return document.split("\n## n8n\n", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]


def _summary_row() -> str:
    for line in _catalog().splitlines():
        if line.startswith("| [n8n](#n8n) |"):
            return line
    raise AssertionError("n8n summary row missing from docs/SPACES.md")


def test_summary_row_does_not_claim_a_space_application_profile() -> None:
    row = _summary_row()

    assert "`space-n8n` Swarm profile" not in row
    assert "MCP tool surface" in row


def test_section_states_the_registry_routed_tool_surface_positively() -> None:
    section = _n8n_section()

    for required_text in (
        "registry-routed MCP tool surface",
        "brain-n8n",
        "space_agent_registry.yml",
        "mcp_servers: [vibemind-db, n8n]",
    ):
        assert required_text in section


def test_section_denies_space_application_directory_and_data_ownership() -> None:
    section = _n8n_section()

    for required_text in (
        "no Space application",
        "no `spaces/n8n` directory",
        "no Space-owned data store",
    ):
        assert required_text in section


def test_section_attributes_integration_code_and_compose_to_voice() -> None:
    section = _n8n_section()

    for required_text in (
        "vibemind-os/voice/docker-compose.n8n.yml",
        "vibemind-os/voice/docker/n8n/Dockerfile",
        "vibemind-os/voice/python/ipc/n8n_handlers.py",
    ):
        assert required_text in section

    assert "voice" in section


def test_section_scopes_the_space_n8n_profile_to_the_third_party_engine() -> None:
    section = _n8n_section()

    assert "space-n8n" in section
    assert "single-service Compose profile" in section
    assert "third-party n8n engine" in section
    assert "infra/swarm/profiles/" in section


def test_section_records_the_generated_inventory_drift_as_non_evidence() -> None:
    section = _n8n_section()

    assert "data/space_capabilities/n8n.yml" in section
    assert "not evidence" in section


def test_events_and_agent_binding_are_preserved() -> None:
    section = _n8n_section()
    document = _catalog()

    for event in REGISTRY_EVENTS:
        assert event in section, f"registry event {event} dropped from the catalog"

    assert "| [n8n](#n8n) | `brain-n8n` | enabled | `n8n.` | 8 |" in document


def test_contract_document_matches_the_corrected_space_shape() -> None:
    contract = CONTRACT.read_text(encoding="utf-8")

    assert "registry-routed MCP tool surface" in contract
    assert "not a Space application" in contract
