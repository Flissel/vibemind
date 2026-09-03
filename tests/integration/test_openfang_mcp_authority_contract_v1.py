"""Static validator for the durable OpenFang MCP authority contract.

Validates `shared/contracts/openfang-mcp-authority-v1.json` — first for
internal fail-closed consistency (always), then against the real
`vibemind-os` sources (registry, OpenFang config, agent manifests, the
spaces-ideas MCP server) whenever the submodule is initialized per
`docs/runbooks/submodule-checkout-workflow.md`.

Style follows tests/v1_governance: plain pytest, no fixtures beyond paths,
assertions phrased as authority claims. This suite performs no live MCP
registration, no runtime activation and no OpenFang mutation of any kind
(task-integration-0005b owns those).
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "shared" / "contracts" / "openfang-mcp-authority-v1.json"
REGISTRY_PATH = ROOT / "vibemind-os" / "config" / "space_agent_registry.yml"
OPENFANG_TOML_PATH = (
    ROOT / "vibemind-os" / "openfang" / "openfang.vibemind.toml"
)
OPENFANG_TEMPLATE_PATH = (
    ROOT / "vibemind-os" / "openfang" / "openfang.vibemind.toml.template"
)
AGENTS_DIR = ROOT / "vibemind-os" / "openfang" / "agents"
IDEAS_MCP_SERVER_PATH = ROOT / "vibemind-os" / "spaces" / "ideas" / "mcp_server.py"

SUBMODULE_REASON = (
    "vibemind-os submodule not initialized — run "
    "docs/runbooks/submodule-checkout-workflow.md first"
)

requires_submodule = pytest.mark.skipif(
    not REGISTRY_PATH.exists(), reason=SUBMODULE_REASON
)

PROVENANCE = ["approval_ref", "cost_ref"]


def load_contract() -> dict:
    assert CONTRACT_PATH.exists(), (
        f"missing contract document {CONTRACT_PATH.relative_to(ROOT)}"
    )
    with open(CONTRACT_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_registry() -> dict:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def registered_server_names(path: Path) -> set[str]:
    with open(path, "rb") as handle:
        config = tomllib.load(handle)
    return {entry["name"] for entry in config.get("mcp_servers", [])}


# ─── Contract-internal fail-closed consistency (always runs) ───────────


def test_contract_declares_v1_identity() -> None:
    contract = load_contract()

    assert contract["contract_version"] == "v1"
    assert contract["contract_id"] == "openfang-mcp-authority-v1"
    assert contract["source_pins"]["vibemind-os"].startswith("82127e4")


def test_contract_has_no_wildcard_server_or_tool_scope() -> None:
    contract = load_contract()

    def assert_no_wildcard(value: str, where: str) -> None:
        assert "*" not in value, f"wildcard scope {value!r} in {where}"

    for name in contract["servers"]:
        assert_no_wildcard(name, "servers catalog")
    for space, spec in contract["spaces"].items():
        assert_no_wildcard(spec["agent_role"], f"spaces.{space}.agent_role")
        for server in spec["mcp_servers"]:
            assert_no_wildcard(server, f"spaces.{space}.mcp_servers")
        for server, tools in spec.get("mcp_tools", {}).items():
            assert_no_wildcard(server, f"spaces.{space}.mcp_tools")
            for tool in tools:
                assert_no_wildcard(tool, f"spaces.{space}.mcp_tools[{server}]")
    for agent, spec in contract["additional_openfang_agents"].items():
        for server in spec["mcp_servers"]:
            assert_no_wildcard(server, f"additional_openfang_agents.{agent}")


def test_every_scoped_server_exists_in_the_server_catalog() -> None:
    contract = load_contract()
    catalog = set(contract["servers"])

    for space, spec in contract["spaces"].items():
        for server in spec["mcp_servers"]:
            assert server in catalog, (
                f"spaces.{space} scopes unknown server {server!r}"
            )
    for agent, spec in contract["additional_openfang_agents"].items():
        for server in spec["mcp_servers"]:
            assert server in catalog, (
                f"additional agent {agent} scopes unknown server {server!r}"
            )


def test_tool_grants_are_subsets_of_the_server_scope() -> None:
    contract = load_contract()

    for space, spec in contract["spaces"].items():
        scope = set(spec["mcp_servers"])
        for server, tools in spec.get("mcp_tools", {}).items():
            assert server in scope, (
                f"spaces.{space} grants tools on {server!r} outside its scope"
            )
            assert tools, f"spaces.{space} has an empty tool grant for {server!r}"
        for server, tools in spec.get("mcp_tools", {}).items():
            server_tools = contract["servers"][server].get("tools")
            if server_tools is not None:
                missing = set(tools) - set(server_tools)
                assert not missing, (
                    f"spaces.{space} grants {sorted(missing)} which "
                    f"{server!r} does not expose"
                )


def test_scopes_are_explicit_never_empty_without_no_mcp() -> None:
    """OpenFang treats an empty mcp_servers list as ALL connected servers
    (openfang-types agent.rs:459-464). The contract must therefore never
    contain an implicit-all scope."""
    contract = load_contract()

    for space, spec in contract["spaces"].items():
        if spec.get("enabled", True):
            assert spec["mcp_servers"] or spec.get("no_mcp") is True, (
                f"spaces.{space} has an implicit-all MCP scope"
            )
    fallback = contract["fallback_agent"]
    assert fallback["no_mcp"] is True
    assert fallback["mcp_servers"] == []


def test_every_mcp_event_is_fully_bound_with_provenance() -> None:
    contract = load_contract()

    events = contract["mcp_events"]
    assert events, "contract declares no MCP-bound events"
    for event in events:
        space = contract["spaces"][event["space"]]
        assert event["agent_role"] == space["agent_role"]
        assert event["server"] in space["mcp_servers"], (
            f"{event['space']}.{event['event']} uses server outside the scope"
        )
        assert event["tool"] in space["mcp_tools"][event["server"]], (
            f"{event['space']}.{event['event']} uses an ungranted tool"
        )
        assert event["required_provenance"] == PROVENANCE, (
            f"{event['space']}.{event['event']} must require closed "
            f"provenance {PROVENANCE}"
        )


def test_ideas_golden_path_is_complete_and_consistent() -> None:
    contract = load_contract()
    golden = contract["golden_path_ideas"]
    by_key = {
        (event["space"], event["event"]): event
        for event in contract["mcp_events"]
    }

    idea_connect = by_key[("ideas", "idea.connect")]
    assert idea_connect["agent_role"] == "brain-ideas"
    assert idea_connect["server"] == "spaces-ideas"
    assert idea_connect["tool"] == "idea_connect"
    assert idea_connect["required_provenance"] == PROVENANCE

    bubble_create = by_key[("bubbles", "bubble.create")]
    assert bubble_create["agent_role"] == "brain-bubbles"
    assert bubble_create["server"] == "spaces-ideas"
    assert bubble_create["tool"] == "bubble_create"
    assert bubble_create["required_provenance"] == PROVENANCE

    assert golden["server"] == "spaces-ideas"
    assert contract["servers"]["spaces-ideas"]["registration"] == "registered"
    assert set(golden["events"]) == {"ideas.idea.connect", "bubbles.bubble.create"}
    assert golden["remaining_for_0005b"], (
        "golden path must state the 0005b live-registration remainder"
    )


def test_registration_authority_is_fail_closed() -> None:
    contract = load_contract()
    authority = contract["registration_authority"]

    assert authority["mutation_requires"] == "runtime-authority"
    assert authority["mutation_task"] == "task-integration-0005b"
    assert authority["standing_autonomy_sufficient"] is False
    assert set(authority["protected_hand_curated_agents"]) == {
        "brain-coder",
        "rowboat-chat",
        "brain-fallback",
    }
    evidence = authority["registration_evidence"]
    assert evidence["static"], "static registration evidence must be declared"
    assert evidence["live"]["verified_here"] is False, (
        "this static contract must never claim live registration evidence"
    )


def test_unregistered_scoped_servers_are_declared_as_gaps() -> None:
    contract = load_contract()

    unregistered = {
        name
        for name, spec in contract["servers"].items()
        if spec["registration"] != "registered"
    }
    scoped = set()
    for spec in contract["spaces"].values():
        scoped.update(spec["mcp_servers"])
    for spec in contract["additional_openfang_agents"].values():
        scoped.update(spec["mcp_servers"])
    gap_servers = {
        gap["server"] for gap in contract["gaps"] if "server" in gap
    }
    undeclared = (unregistered & scoped) - gap_servers
    assert not undeclared, (
        f"scoped but unregistered servers missing from gaps: {sorted(undeclared)}"
    )


# ─── Cross-checks against the real vibemind-os sources ─────────────────


@requires_submodule
def test_registered_servers_match_the_openfang_config() -> None:
    contract = load_contract()
    live = registered_server_names(OPENFANG_TOML_PATH)
    template = registered_server_names(OPENFANG_TEMPLATE_PATH)

    for name, spec in contract["servers"].items():
        if spec["registration"] == "registered":
            assert name in live, (
                f"contract claims {name!r} registered but it is missing from "
                "openfang.vibemind.toml"
            )
        elif spec["registration"] == "template-only":
            assert name in template and name not in live, (
                f"contract claims {name!r} template-only, config disagrees"
            )
        else:
            assert name not in live, (
                f"contract claims {name!r} unregistered but the live config "
                "declares it"
            )

    catalog_registered = {
        name
        for name, spec in contract["servers"].items()
        if spec["registration"] == "registered"
    }
    assert catalog_registered == live, (
        "contract server catalog and openfang.vibemind.toml diverge: "
        f"only-contract={sorted(catalog_registered - live)} "
        f"only-config={sorted(live - catalog_registered)}"
    )


@requires_submodule
def test_space_scopes_match_the_registry() -> None:
    contract = load_contract()
    registry = load_registry()
    registry_spaces = registry["spaces"]

    assert set(contract["spaces"]) == set(registry_spaces), (
        "contract spaces diverge from the registry"
    )
    for space, spec in contract["spaces"].items():
        entry = registry_spaces[space]
        assert spec["agent_role"] == entry["agent"], f"{space} agent role drift"
        assert spec["enabled"] == entry.get("enabled", True)
        assert spec["mcp_servers"] == list(entry.get("mcp_servers") or []), (
            f"{space} mcp_servers drift against the registry"
        )
        assert spec.get("mcp_tools", {}) == {
            server: list(tools)
            for server, tools in (entry.get("mcp_tools") or {}).items()
        }, f"{space} mcp_tools drift against the registry"


@requires_submodule
def test_mcp_events_match_the_registry_exactly() -> None:
    """Every registry event with execution.kind == mcp must appear in the
    contract with identical binding and provenance — and nothing more."""
    contract = load_contract()
    registry = load_registry()

    expected = set()
    for space, entry in registry["spaces"].items():
        for event_name, event in (entry.get("events") or {}).items():
            if not isinstance(event, dict):
                continue
            execution = event.get("execution")
            if isinstance(execution, dict) and execution.get("kind") == "mcp":
                expected.add(
                    (
                        space,
                        event_name,
                        entry["agent"],
                        execution["server"],
                        event["tool"],
                        tuple(event.get("required_provenance") or []),
                    )
                )

    declared = {
        (
            event["space"],
            event["event"],
            event["agent_role"],
            event["server"],
            event["tool"],
            tuple(event["required_provenance"]),
        )
        for event in contract["mcp_events"]
    }
    assert declared == expected, (
        f"only-contract={sorted(declared - expected)} "
        f"only-registry={sorted(expected - declared)}"
    )


@requires_submodule
def test_generated_agent_manifests_match_contract_scopes() -> None:
    contract = load_contract()

    for space, spec in contract["spaces"].items():
        manifest_path = AGENTS_DIR / spec["agent_role"] / "agent.toml"
        if spec["manifest"] is None:
            assert not manifest_path.exists(), (
                f"{space} declares no manifest but {manifest_path} exists"
            )
            continue
        with open(manifest_path, "rb") as handle:
            manifest = tomllib.load(handle)
        assert manifest.get("mcp_servers", []) == spec["mcp_servers"], (
            f"{manifest_path.relative_to(ROOT)} scope drift against contract"
        )
        expected_mcp_capabilities = sorted(
            "mcp_{}_{}".format(
                server.lower().replace("-", "_"), tool.lower().replace("-", "_")
            )
            for server, tools in spec.get("mcp_tools", {}).items()
            for tool in tools
        )
        if spec["manifest"]["generated"]:
            actual = [
                tool
                for tool in manifest["capabilities"]["tools"]
                if tool.startswith("mcp_")
            ]
            assert sorted(actual) == expected_mcp_capabilities, (
                f"{manifest_path.relative_to(ROOT)} capability tools drift"
            )


@requires_submodule
def test_fallback_agent_disables_mcp_in_its_manifest() -> None:
    contract = load_contract()
    fallback = contract["fallback_agent"]
    manifest_path = AGENTS_DIR / fallback["agent"] / "agent.toml"

    with open(manifest_path, "rb") as handle:
        manifest = tomllib.load(handle)
    assert manifest.get("no_mcp") is True
    assert manifest.get("mcp_servers", []) == []


@requires_submodule
def test_golden_path_tools_exist_in_the_ideas_mcp_server() -> None:
    source = IDEAS_MCP_SERVER_PATH.read_text(encoding="utf-8")
    exposed = set(re.findall(r'"name":\s*"([a-z_]+)"', source))

    for tool in ("idea_connect", "bubble_create"):
        assert tool in exposed, (
            f"golden-path tool {tool!r} is not exposed by spaces/ideas/mcp_server.py"
        )


# ─── Coding-space binding gaps (task-coding-0005, additive) ────────────

PRE_EXISTING_GAP_KINDS = {
    "unregistered-but-scoped",
    "template-only",
    "commented-out-but-scoped",
    "dual-source-capabilities",
    "static-provider-pinning",
    "non-mcp-wildcards",
    "host-bound-registration",
    "tool-inventories-not-captured",
}

CODING_GAP_KINDS = {
    "dual-port-8000-binding",
    "dual-dispatch-coding",
    "protected-manifest-not-generated",
}


def coding_gaps(contract: dict) -> dict[str, dict]:
    return {
        gap["kind"]: gap
        for gap in contract["gaps"]
        if gap["kind"] in CODING_GAP_KINDS
    }


def test_coding_binding_gaps_are_declared() -> None:
    """The coding-space binding-chain mismatches (M1, M5, M7 of
    docs/operations/2026-08-14-coding-event-binding-matrix.md) must be
    declared as structured gap records, matching the shape of the
    existing entries (kind + detail + sources)."""
    contract = load_contract()
    declared = coding_gaps(contract)

    missing = CODING_GAP_KINDS - set(declared)
    assert not missing, f"coding gap records missing: {sorted(missing)}"
    for kind, gap in declared.items():
        assert gap["detail"], f"gap {kind} has an empty detail"
        assert gap["sources"], f"gap {kind} declares no evidence sources"


def test_coding_gap_sources_cite_the_binding_evidence() -> None:
    contract = load_contract()
    declared = coding_gaps(contract)

    def sources_of(kind: str) -> str:
        return " ".join(declared[kind]["sources"])

    dual_port = sources_of("dual-port-8000-binding")
    for path in (
        "vibemind-os/coding-engine/infra/control_server/server.py",
        "vibemind-os/coding-engine/infra/docker-compose.yml",
        "vibemind-os/coding-engine/src/api/main.py",
        "vibemind-os/coding-engine/docker-compose.yml",
        "vibemind-os/brain/the_brain/core/capability_targets.py",
    ):
        assert path in dual_port, f"dual-port-8000-binding must cite {path}"

    dual_dispatch = sources_of("dual-dispatch-coding")
    for path in (
        "vibemind-os/brain/the_brain/data/capabilities.yaml",
        "vibemind-os/config/space_agent_registry.yml",
        "intent_validation/cat5_results.json",
    ):
        assert path in dual_dispatch, f"dual-dispatch-coding must cite {path}"

    manifest_gap = sources_of("protected-manifest-not-generated")
    for path in (
        "vibemind-os/scripts/sync_openfang_agents.py",
        "vibemind-os/openfang/agents/brain-coder/agent.toml",
    ):
        assert path in manifest_gap, (
            f"protected-manifest-not-generated must cite {path}"
        )


def test_coding_gap_records_are_purely_additive() -> None:
    """task-coding-0005 may only append gap records: every pre-existing
    gap kind stays declared, and no existing block shape changes."""
    contract = load_contract()
    declared_kinds = {gap["kind"] for gap in contract["gaps"]}

    missing = PRE_EXISTING_GAP_KINDS - declared_kinds
    assert not missing, f"pre-existing gap kinds were dropped: {sorted(missing)}"
    unknown = declared_kinds - PRE_EXISTING_GAP_KINDS - CODING_GAP_KINDS
    assert not unknown, f"undocumented gap kinds appeared: {sorted(unknown)}"
