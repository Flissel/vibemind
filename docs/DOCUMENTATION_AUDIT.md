# Documentation audit

- Audit date: **2026-08-09**
- Baseline revision: `be906aa099c5e09656dd0e342dedc12397f646b7`, plus the documentation changes in this audit
- Scope: root repository, the pinned `vibemind-os` tree, all 13 canonical Spaces, deployment definitions, setup and public project policy

This is a repository-first audit. It records what is present and configured in the checked-out source. It does not claim that a service is reachable or operational unless a fresh runtime probe is explicitly attached.

## Result

The public documentation now has an explicit navigation path from clone and setup to architecture, Space ownership, operations and contribution policy. Every canonical Space in `vibemind-os/config/space_agent_registry.yml` has a source-backed entry in [`SPACES.md`](SPACES.md).

The audit found four material documentation risks:

1. `vibemind-os/data/space_capabilities/` is generated from an older source view and disagrees with the current registry for AgentFarm and Rowboat identity and for several tool hints.
2. `infra/swarm/STARTUP_PROFILES.md` mixes current commands with historical crawl results. Several statements about missing `profiles:` labels are superseded by the current stack, which now contains profile declarations.
3. A Space being enabled in the routing registry is not the same as having a selectable Docker profile or a verified live runtime.
4. The complete recursive checkout is not anonymously reproducible while the root repository and `vibemind-os` remain private. GitHub Actions currently cannot fetch the private `vibemind-os` submodule with its default token.

These risks are documented rather than hidden. No repository visibility, runtime configuration or product behavior was changed by this audit.

## Sources of truth

When documents disagree, use this precedence order:

| Priority | Question | Source |
| ---: | --- | --- |
| 1 | Which Space, agent, prefixes, events and MCP scopes are canonical? | `vibemind-os/config/space_agent_registry.yml` |
| 2 | Which root modules and local ports are configured? | `vibemind.config.json` |
| 3 | Which containers, profiles, replicas, secrets and volumes are declared? | `infra/swarm/vibemind-stack.yml` |
| 4 | Which profiles can the launcher select? | `scripts/vibemind-spaces.ps1` and `scripts/lib/vibemind-helpers.ps1` |
| 5 | Which behavior is implemented? | Source and focused tests at the pinned submodule revisions |
| 6 | Which tools were discovered by a previous extraction? | `vibemind-os/data/space_capabilities/` — secondary, generated inventory only |
| 7 | Which behavior is running now? | A fresh correlated end-to-end probe; never infer this from source alone |

## Coverage matrix

| Area | Public entry point | Coverage | Audit note |
| --- | --- | --- | --- |
| Product and clone | [`../README.md`](../README.md) | Complete | Recursive clone, update, setup, dry-run and policy links |
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) | Complete at system level | Context, layers, authority, lifecycle, data, deployment and extension model |
| Space catalog | [`SPACES.md`](SPACES.md) | Complete for 13/13 canonical Spaces | Identity, events, source, storage, runtime, safety and verification |
| Visual architecture | [`architecture.html`](architecture.html) | Complete at overview level | Standalone, accessible visual companion |
| Setup | [`../README.md`](../README.md) | Complete for supported root workflow | Component-specific installs remain owned by submodules |
| Operations | `infra/swarm/STARTUP_PROFILES.md` | Partial / mixed-age | Useful operational detail, but historical claims must be checked against current YAML |
| Contribution | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Complete | Includes nested-submodule workflow |
| Release | [`RELEASING.md`](RELEASING.md) | Complete | Includes recursive checkout and policy checks |
| Security | [`../SECURITY.md`](../SECURITY.md) | Complete | Private reporting and secret handling |
| Support and conduct | [`../SUPPORT.md`](../SUPPORT.md), [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | Complete | Public support boundaries and community expectations |
| License | [`../LICENSE`](../LICENSE) | Root complete | Nested repositories retain their own licenses |

## Space coverage

Registry count at audit time: **13**. Enabled: **12**. Disabled and blocked: **1** (`agentfarm`).

| Space | Registry | Events | Source located | Swarm-selectable | Documentation |
| --- | --- | ---: | --- | --- | --- |
| bubbles | enabled | 14 | `vibemind-os/spaces/ideas/`, Brain/voice adapters | Core data plane | [`SPACES.md#bubbles`](SPACES.md#bubbles) |
| ideas | enabled | 25 | `vibemind-os/spaces/ideas/`, Brain/voice adapters | Core data plane | [`SPACES.md#ideas`](SPACES.md#ideas) |
| coding | enabled | 8 | `vibemind-os/coding-engine/` | `space-coding` | [`SPACES.md#coding`](SPACES.md#coding) |
| desktop | enabled | 28 | `vibemind-os/spaces/desktop/Automation_ui/` | Native module | [`SPACES.md#desktop`](SPACES.md#desktop) |
| research | enabled | 6 | `vibemind-os/spaces/research/` and routing adapters | No dedicated profile | [`SPACES.md#research`](SPACES.md#research) |
| rowboat | enabled | 8 | `vibemind-os/spaces/rowboat/` | `space-rowboat` | [`SPACES.md#rowboat`](SPACES.md#rowboat) |
| minibook | enabled | 4 | `vibemind-os/spaces/minibook/` | Separate Compose entry | [`SPACES.md#minibook`](SPACES.md#minibook) |
| schedule | enabled | 7 | `vibemind-os/spaces/schedule/` | Native/in-process | [`SPACES.md#schedule`](SPACES.md#schedule) |
| n8n | enabled | 8 | Voice integration and n8n image/Compose | `space-n8n` | [`SPACES.md#n8n`](SPACES.md#n8n) |
| agentfarm | disabled / blocked | 8 contracts | `vibemind-os/spaces/agentfarm/` manifest only | Disabled | [`SPACES.md#agentfarm`](SPACES.md#agentfarm) |
| video | enabled | 9 | `vibemind-os/spaces/video/` | `space-media` for media serving | [`SPACES.md#video`](SPACES.md#video) |
| flowzen | enabled | 3 | `vibemind-os/spaces/flowzen/` | No dedicated profile | [`SPACES.md#flowzen`](SPACES.md#flowzen) |
| mirofish | enabled | 7 | `vibemind-os/spaces/mirofish/` | `space-mirofish`, replicas default to 0 | [`SPACES.md#mirofish`](SPACES.md#mirofish) |

“Swarm-selectable” describes configuration only. It is not a live-health assertion.

## Confirmed drift and contradictions

### Generated capability inventory

`vibemind-os/data/space_capabilities/_index.md` is useful for locating historical tool implementations, but it is not canonical:

- it lists AgentFarm agent `brain-orchestrator`; the registry now maps AgentFarm to `vibemind` and disables it;
- it retains the aliases `autogen`, `roarboot` and `shuttles` as separate inventory pages;
- its AgentFarm paths refer to the removed `spaces/autogen` runtime;
- its event tool hints differ from current registry contracts in several Spaces;
- Rowboat identity is split between `rowboat`, `roarboot` and `rowboat-knowledge` in generated material.

Action: regenerate the inventory from the current registry and pinned source in a separate product-code change, then make the generator fail when canonical agent/event mappings drift.

### Startup profiles

`infra/swarm/STARTUP_PROFILES.md` says most services lack profile tags. In the audited stack, `space-coding`, `space-rowboat`, `space-mirofish`, `space-n8n`, `space-media`, `space-logging` and `core-phase-d` are present. The launcher exposes only a subset as user-selectable logical profiles, and some services intentionally have zero replicas.

Action: regenerate the operational profile guide from `vibemind-stack.yml` and `scripts/vibemind-spaces.ps1`. Until then, treat its command examples as guidance and its status claims as historical.

### Open-source checkout

Update 2026-10-25: the recursive topology now has 26 submodule paths backed by 24 distinct repositories. All of them, including the root repository and `vibemind-os`, answered an unauthenticated GitHub API request and an anonymous `git ls-remote`, and `git clone --recurse-submodules` completed. The private-checkout gap described below is closed.

Original finding (2026-08-09): the recursive topology contained 19 repositories. An anonymous GitHub API check found 17 public repositories and two private repositories: the root repository and `vibemind-os`. The public-facing clone command was structurally correct, but anonymous users and the default GitHub Actions token could not complete the private recursive checkout.

## Evidence vocabulary

Every status-bearing document should use these terms consistently:

| Level | Required evidence |
| --- | --- |
| Static | Source, contract or documentation exists at the pinned revision. |
| Configured | A registry, launcher or deployment file references the component. |
| Historical | A prior report recorded a result; it may be stale. |
| Reachable | A current transport probe received a response. |
| Verified live | A current end-to-end request reached its intended terminal state and returned correlated outcome evidence. |

Do not promote one level to another. In particular, an enabled registry entry, a healthy container or an HTTP 200 response alone does not prove a successful domain operation.

## Documentation acceptance checklist

A new or changed Space is documentation-complete only when all applicable items are present:

- canonical ID, aliases, agent, prefixes and enabled state;
- purpose, non-goals and user-visible event families;
- MCP/tool allowlist and approval requirements;
- source roots and runtime/deployment entrypoints;
- owned data stores, artifacts and retention boundary;
- required configuration and secret names without secret values;
- health/readiness definition and a terminal outcome check;
- failure behavior, retries and forbidden fallbacks;
- focused tests and reproducible validation commands;
- license and external-service constraints;
- an explicit evidence level and audit date.

## Next bounded documentation tasks

1. Regenerate and validate `vibemind-os/data/space_capabilities/` from the current registry.
2. Replace historical assertions in `infra/swarm/STARTUP_PROFILES.md` with generated current-state tables.
3. Add an automated documentation gate that checks every canonical registry Space has an anchor in `docs/SPACES.md` and that all local Markdown links resolve.
4. After a safe publication review, validate the documented clone flow from a machine with no existing credentials.
