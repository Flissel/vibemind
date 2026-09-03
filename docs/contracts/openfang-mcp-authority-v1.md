# OpenFangMcpAuthorityV1

## Purpose and authority

`OpenFangMcpAuthorityV1` is the durable, versioned declaration of the OpenFang
MCP authority: canonical MCP server identities, per-agent scopes, tool
allowlists per server, and who authorizes a registration and how a
registration is proven. It is the static half of `task-integration-0005`
(program focus directive, `docs/governance/session-request-queue-v1.md`
§3.1a). Every claim is grounded in the real `vibemind-os` checkout at gitlink
pin `82127e44944495e5cb47d22e597cee9c51bbee83` (OpenFang nested pin
`8a4904b3ff622d7ffda1e8cb01a509d2db430904`); statements the checkout does not
support are recorded as explicit gaps, never inferred.

The machine-readable form is
[`shared/contracts/openfang-mcp-authority-v1.json`](../../shared/contracts/openfang-mcp-authority-v1.json),
statically validated by
`tests/integration/test_openfang_mcp_authority_contract_v1.py` — first for
internal fail-closed consistency, then against the live sources whenever the
submodule is initialized per `docs/runbooks/submodule-checkout-workflow.md`.

This contract performs and authorizes **no** live MCP registration, no runtime
activation, no OpenFang mutation and no deployment. Live registration and its
runtime evidence are owned by the separate, runtime-authority-gated
`task-integration-0005b`.

## Role semantics (E1)

Per `docs/governance/architecture-decisions-2026-08-13-v1.md` E1, the agent
names in this contract (`brain-ideas`, `brain-bubbles`, …) are canonical
agent **roles** named by Brain. OpenFang alone binds a role to a concrete
instance, provider and model. In the current checkout that binding is still
static: `scripts/sync_openfang_agents.py:32-37` defaults every generated
manifest to `provider = "openai"`, `model = "gpt-4o-mini"`, and a per-space
`model:` override in the registry may narrow that at generation time
(`sync_openfang_agents.py:117-129`). At the pinned revision `provider` is
`openai` in all 49 manifests, and `model` is `gpt-4o-mini` in all but
`brain-researcher`, which the `research` space dimensions to `gpt-4o`
(`space_agent_registry.yml:187`). OpenFang's manifest test pins the pair for
the hand-curated `brain-coder` manifest alone
(`crates/openfang-types/src/agent.rs:1428-1439`).
The re-specification of dynamic role→instance binding belongs to
`task-brain-0018-agent-role-selection-contract-v1`; this contract adopts role
semantics without changing `execution_target` or any existing schema.

## N1 — Canonical MCP server identity

A server identity is canonical if and only if it appears as a
`[[mcp_servers]]` entry (`McpServerConfigEntry`,
`crates/openfang-types/src/config.rs:1180`) in the merged OpenFang
configuration — `openfang/openfang.vibemind.toml`, merged with
`~/.openfang/config.toml` at startup (`openfang.vibemind.toml:1-2`). The
pinned checkout registers **36** servers (full catalog with per-entry line
references in the JSON). Configuration changes to `mcp_servers` are observed
by hot-reload (`crates/openfang-kernel/src/config_reload.rs:228`).

Registration states used by this contract, all evidenced per entry:

| State | Meaning | Examples |
| --- | --- | --- |
| `registered` | active entry in the live config | `spaces-ideas` (387-394), `vibemind-db` (352-359) |
| `template-only` | entry only in `openfang.vibemind.toml.template` | `spaces-rowboat` (template:396-403; required by `agent.rs:1714-1730`) |
| `commented-out` | entry present but disabled pending a credential | `github` (246-254), `postgres` (328-336) |
| `unregistered` | referenced by a scope but registered nowhere in the checkout | `vibemind` |

Fail-closed rule: a server that is not `registered` MUST NOT be treated as
routable, regardless of appearing in an agent scope.

## N2 — Per-agent MCP scopes

The single source of truth for Brain-routed scopes is
`config/space_agent_registry.yml` (`spaces.<space>.mcp_servers`); the
registry header names itself the SoT and both consumers
(`voice/python/swarm/routing/space_agent_registry.py`,
`scripts/sync_openfang_agents.py`) derive from it. The generator writes the
scope as the top-level `mcp_servers` allowlist of
`openfang/agents/<agent>/agent.toml`; OpenFang pins all seventeen brain
manifest scopes in its own test
(`crates/openfang-types/src/agent.rs:1484-1709`).

**Critical semantics** (`crates/openfang-types/src/agent.rs:459-464`): an
empty `AgentManifest.mcp_servers` list means **all connected MCP servers**;
`no_mcp = true` disables MCP entirely. Therefore every enabled agent MUST
declare a non-empty allowlist or `no_mcp = true`
(`sync_openfang_agents.py:167-198` enforces this at generation time; the
fallback agent `brain-fallback` declares `no_mcp = true`,
`agents/brain-fallback/agent.toml:6`). Implicit-all scopes are forbidden by
this contract.

The 13 canonical spaces and their scopes (registry lines in the JSON):

| Space | Agent role | MCP scope |
| --- | --- | --- |
| bubbles | brain-bubbles | vibemind-db, vibemind, spaces-ideas |
| ideas | brain-ideas | vibemind-db, spaces-ideas |
| coding | brain-coder | vibemind-db, filesystem, git, github, context7, qdrant, fetch, brain, issue-detector |
| desktop | brain-desktop | vibemind-db, desktop-automation |
| research | brain-researcher | fetch, spaces-ideas, qdrant |
| rowboat | rowboat-chat | vibemind-db, fetch, spaces-rowboat |
| minibook | brain-knowledge | vibemind-db, fetch, spaces-minibook |
| schedule | brain-scheduler | vibemind-db, scheduled-tasks |
| n8n | brain-n8n | vibemind-db, n8n |
| agentfarm | vibemind (disabled) | — |
| video | brain-video | vibemind-db |
| flowzen | brain-wellness | vibemind-db |
| mirofish | brain-forecaster | vibemind-db |

Six further OpenFang-native brain agents (`brain-planner`,
`brain-orchestrator`, `brain-monitor`, `brain-security`, `brain-writer`,
`brain-devops`) have scopes pinned only by OpenFang's manifest test; they are
not Brain-routed spaces and carry `binding: openfang-native` in the JSON.

## N3 — Tool allowlists

Capability tools for generated agents are derived **exclusively** from the
registry's `mcp_tools` mapping, never from `mcp_servers`
(`sync_openfang_agents.py:98-110` — fail-closed by design: a space without
`mcp_tools` yields only `memory_store`/`memory_recall`). Tool capability
names follow `mcp_<server>_<tool>` normalization
(`sync_openfang_agents.py:91-95`). The generator validates that every
`mcp_tools` server is inside the space's `mcp_servers`
(`sync_openfang_agents.py:201-258`), and OpenFang's test forbids wildcard
tool scopes and the legacy `[mcp_allowed]` table
(`crates/openfang-types/src/agent.rs:1691-1709`).

Explicit tool grants in the pinned checkout:

| Space | Server | Granted tools |
| --- | --- | --- |
| bubbles | spaces-ideas | `bubble_create` |
| bubbles | vibemind-db | `db_ideas_get`, `db_ideas_update`, `db_projects_create` |
| ideas | spaces-ideas | `idea_connect` |
| research | fetch | `fetch` |
| research | spaces-ideas | `idea_create`, `idea_update` |
| rowboat | spaces-rowboat | `rowboat_status` |
| minibook | spaces-minibook | `minibook_status` |

The `spaces-ideas` server exposes 13 tools
(`spaces/ideas/mcp_server.py:30-183`); the grants above are strict subsets.
No MCP-dimension wildcard exists anywhere in this contract. Known non-MCP
wildcards (`network = ["*"]`, `memory_read = ["*"]` in generated manifests,
`sync_openfang_agents.py:81-82`) are recorded as a gap, not legitimized here.

## N4 — MCP-bound events require closed provenance

Every registry event executed via MCP (`execution: { kind: mcp }`) MUST
declare `required_provenance: [approval_ref, cost_ref]` — validated
fail-closed before any manifest is generated
(`sync_openfang_agents.py:306-372`, provenance check at 367-371). The six
MCP-bound events in the pinned checkout are `bubbles.bubble.create`,
`ideas.idea.connect`, `research.summarize`, `research.to_idea`,
`rowboat.status` and `minibook.status`. `approval_ref` and `cost_ref` remain
opaque continuity values; their presence proves no approval and no cost
settlement (`docs/contracts/brain-openfang-handoff-v1.md:37-39`).

## N5 — Registration authority

Who may register: mutating the merged OpenFang configuration or the agent
manifests is an **OpenFang mutation** and therefore outside
`standing-autonomy:v1` (AGENTS.md authority gates;
`docs/governance/multi-session-program-charter-v1.md`). Registration changes
require request-specific runtime authority and are owned by
`task-integration-0005b`. Within the static plane, agent scope changes flow
only through `config/space_agent_registry.yml` plus
`scripts/sync_openfang_agents.py`, whose four validators must pass before
anything is written (`sync_openfang_agents.py:375-385`). Three hand-curated
manifests are protected from generation: `brain-coder`, `rowboat-chat`,
`brain-fallback` (`sync_openfang_agents.py:160-164`).

## N6 — Registration proof

Static proof (this contract's plane):

1. the `[[mcp_servers]]` entry exists at the pinned revision;
2. the agent manifest scope matches the registry (pinned by
   `test_vibemind_brain_manifests_use_top_level_mcp_servers`);
3. `python scripts/sync_openfang_agents.py --check` reports no drift;
4. `python -m pytest tests/integration/test_openfang_mcp_authority_contract_v1.py`
   is green.

Live proof (owned by `0005b`, never claimed here): `GET /api/mcp/servers`
lists configured **and connected** servers with their tool lists
(`crates/openfang-api/src/routes.rs:5179`); `GET /api/agents` exposes each
agent's `mcp_servers` and `mcp_servers_mode` (`all` | `allowlist`)
(`routes.rs:1534-1535`). A registration claim without a connected entry and
correlated readback is invalid (fail-closed).

## Ideas golden path (focus directive point 3)

The path `Intent → Brain → OpenFang → spaces-ideas MCP → Supabase` is
statically complete and contradiction-free in the pinned checkout:

- **`ideas.idea.connect`** — role `brain-ideas`, server `spaces-ideas`, tool
  `idea_connect`, provenance required
  (`space_agent_registry.yml:77-81`; scope 68-69; manifest
  `agents/brain-ideas/agent.toml:7,40`; OpenFang pin `agent.rs:1498-1506`;
  Brain target `mcp:brain-ideas:spaces-ideas:idea_connect`,
  `capabilities.yaml:629`; implementation `spaces/ideas/mcp_server.py:738`).
- **`bubbles.bubble.create`** — role `brain-bubbles`, server `spaces-ideas`,
  tool `bubble_create`, provenance required
  (`space_agent_registry.yml:43-47`; scope 29, grants 36-38; manifest
  `agents/brain-bubbles/agent.toml:7,40`; OpenFang pin `agent.rs:1486-1497`;
  implementation `spaces/ideas/mcp_server.py:552`).
- The server `spaces-ideas` is `registered`
  (`openfang.vibemind.toml:387-394`) and speaks directly to the Supabase
  data plane with database-verified tool calls
  (`spaces/ideas/mcp_server.py:1-30`).

What `0005b` must still deliver for the live golden path is enumerated in the
JSON (`golden_path_ideas.remaining_for_0005b`): connected-server proof via
`GET /api/mcp/servers`, allowlist-mode proof via `GET /api/agents`, runtime
provenance enforcement evidence, an independent database readback correlated
to the intent, and host-specific resolution of the environment-bound absolute
paths in the registration entries.

Known dual-source caveat on this path: Brain's `capabilities.yaml:412` routes
the `bubble_create` capability via `supabase:bubble.create`, while the
registry binds the `bubble.create` event to MCP `spaces-ideas:bubble_create`.
Both are recorded; unification of the dual sources (registry vs.
`capabilities.yaml`) is explicitly deferred to `task-brain-0018`
(architecture decision E1, "Nicht entschieden").

## Conflict and gap register

The complete, evidenced list lives in the JSON under `gaps`. Summary:

1. **Unregistered but scoped:** `vibemind` (bubbles) — no registration
   entry anywhere in the checkout.
2. **Template-only:** `spaces-rowboat` — required by OpenFang's own test but
   absent from the live config.
3. **Commented-out but scoped:** `github` (coding/brain-coder), `postgres`
   (brain-monitor, brain-devops) — pending credentials.
4. **Dual-source routing:** only three active `mcp:` execution targets in
   `capabilities.yaml` (629, 1765, 1956); they embed agent instances,
   predating E1; `bubble_create` routes via Supabase there.
5. **Static provider pinning** in generated manifests (E1 tension).
6. **Non-MCP wildcards** (`network`, `memory_read`) in generated manifests.
7. **Host-bound registration:** absolute Windows paths make every stdio
   registration environment-specific.
8. **Tool inventories:** only `spaces-ideas` has an in-checkout inventory
   captured; `tools: null` in the JSON means "no claim", not an empty
   allowlist.

## Explicit non-claims

This contract does not register, connect, spawn, activate, deploy, approve,
or spend anything; it does not prove runtime reachability of any server or
agent, does not establish a Golden-Path success, and does not modify
`vibemind-os`, its pins, or any OpenFang state. Validation green means
exactly: the declared static authority matches the pinned sources.

## Verification

```bash
python -m pytest tests/integration/test_openfang_mcp_authority_contract_v1.py -q
python -m pytest tests/v1_governance -q
```

The integration validator cross-checks against the real registry, OpenFang
config and agent manifests when `vibemind-os` is initialized; on an
uninitialized checkout the cross-checks skip with an explicit pointer to the
submodule runbook while the contract-internal fail-closed checks still run.
