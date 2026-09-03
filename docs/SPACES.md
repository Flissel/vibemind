# Canonical Space catalog

This catalog documents every canonical Space declared in `vibemind-os/config/space_agent_registry.yml` at the audited revision. The registry is the source of truth for identity, routing prefixes, canonical agents, event contracts and MCP scope.

An enabled Space is **configured for routing**. It is not automatically a separately deployable service and it is not proof of live operation. Runtime statements below are static or configured unless explicitly marked otherwise.

## How to read a Space entry

- **Identity** is persisted and routed under the canonical Space name. Aliases are accepted only at ingress.
- **Events** summarize the public event surface. Required parameters remain authoritative in the registry.
- **Execution** names the intended agent and bounded MCP/application boundary.
- **Data** identifies the stores or artifacts the Space owns or modifies.
- **Runtime** distinguishes Swarm profiles, native processes, in-process adapters and blocked runtimes.
- **Safety** records approvals, terminal validation and important failure behavior.
- **Verify** gives a bounded static or dry-run check. It does not assert live health.

## Catalog summary

| Space | Canonical agent | State | Prefixes | Events | Runtime shape |
| --- | --- | --- | --- | ---: | --- |
| [bubbles](#bubbles) | `brain-bubbles` | enabled | `bubble.` | 14 | Logical Space on core Supabase/Brain data plane |
| [ideas](#ideas) | `brain-ideas` | enabled | `idea.` | 25 | Logical Space and MCP adapter on core data plane |
| [coding](#coding) | `brain-coder` | enabled | `code.` | 8 | `space-coding` Swarm profile plus coding engine |
| [desktop](#desktop) | `brain-desktop` | enabled | `desktop.`, `web.`, `messaging.`, `openclaw.` | 28 | Native Automation UI and external applications |
| [research](#research) | `brain-researcher` | enabled | `research.` | 6 | Routing/tool integration, no dedicated profile |
| [rowboat](#rowboat) | `rowboat-chat` | enabled | `rowboat.` | 8 | `space-rowboat` multi-service profile |
| [minibook](#minibook) | `brain-knowledge` | enabled | `minibook.` | 4 | Separate voice Compose integration |
| [schedule](#schedule) | `brain-scheduler` | enabled | `schedule.` | 7 | Native/in-process APScheduler worker |
| [n8n](#n8n) | `brain-n8n` | enabled | `n8n.` | 8 | Registry-routed MCP tool surface over a third-party engine |
| [agentfarm](#agentfarm) | `vibemind` | **disabled / blocked** | `agentfarm.`, `autogen.` | 8 | Reserved manifest; persistent runtime missing |
| [video](#video) | `brain-video` | enabled | `video.` | 9 | Native tools plus `space-media` publishing service |
| [flowzen](#flowzen) | `brain-wellness` | enabled | `rose.` | 3 | Lightweight MCP/data integration |
| [mirofish](#mirofish) | `brain-forecaster` | enabled | `mirofish.` | 7 | `space-mirofish`, default replicas 0 |

## Bubbles

**Purpose.** Canvas-level containers for idea clusters: list, create, enter, leave, find, update, score, evaluate and promote. `shuttles` is a legacy input alias; canonical persisted identity remains `bubbles`.

**Execution.** `brain-bubbles` receives `bubble.*` intents. The allowlisted server scope is `vibemind-db`, `vibemind` and `spaces-ideas`. The explicit MCP mutation `bubble.create` is bound to `spaces-ideas:bubble_create` and requires approval and cost provenance in its execution envelope.

**Event groups.** Navigation (`list`, `enter`, `exit`, `back`, `current`), lifecycle (`create`, `update`, `delete`, `delete_all_except`), discovery (`find`, `stats`) and evaluation (`score`, `evaluate`, `promote`). Destructive event names exist in the contract; callers must apply the governing approval policy before execution.

**Source and data.** Primary Space adapter: `vibemind-os/spaces/ideas/mcp_server.py`. Routing and context live under `vibemind-os/voice/python/swarm/`; Brain reads and writes the shared Supabase Ideas/Bubbles data plane declared in `infra/swarm/vibemind-stack.yml`.

**Runtime.** There is no separate `space-bubbles` profile. Supabase and Brain services are core stack services. This is a logical domain boundary over shared infrastructure.

**Verify.** Validate the registry entry and run the focused Ideas/Bubbles routing and MCP tests in the component that changes. A database readback of the intended terminal row/state is required for a live claim.

## Ideas

**Purpose.** Notes inside Bubbles, including CRUD, links, formatting, exploration, summarization, document generation and conversion into a project.

**Execution.** `brain-ideas` handles `idea.*`. Its MCP scope is `vibemind-db` and `spaces-ideas`; `idea.connect` is explicitly bound to `spaces-ideas:idea_connect` with approval and cost provenance.

**Event groups.** CRUD/search (`list`, `create`, `update`, `delete`, `find`), graph operations (`connect`, `auto_link`, `analyze_links`), presentation (`add_image` and format/convert events), cognition (`summarize`, `whitepaper`, `expand`, `explain`), exploration (`explore.start`, `explore.stop`), output (`generate_doc`) and promotion (`to_project`). There are 25 registry events.

**Source and data.** `vibemind-os/spaces/ideas/` exposes the MCP adapter and tests. Voice routing/context is in `vibemind-os/voice/python/swarm/`. Ideas, canvas nodes/edges and project promotion use the shared Supabase/PostgreSQL data plane.

**Runtime.** Logical core Space; no dedicated launcher profile. The core Supabase services and Brain provide its configured data/runtime dependencies.

**Safety.** Delete, cross-link and project-promotion operations change durable state. Success should be based on correlated database readback, not a generated response.

**Verify.** Check all 25 registry events resolve to known bounded operations, then run focused Ideas MCP/routing tests. For live verification, create a disposable idea, read it back and remove it through an approved cleanup path.

## Coding

**Purpose.** Code generation, modification, job status/log access, preview lifecycle, project listing and cancellation.

**Execution.** `brain-coder` routes `code.*` events to the coding-engine HTTP surface. Its declared MCP scope includes database, filesystem, Git, GitHub, Context7, Qdrant, fetch, Brain and issue detection. Tool access remains allowlisted by the execution boundary.

**Event groups.** Generation/modification call `POST /api/start`; status and logs use read endpoints; preview create/stop has an explicit project boundary; list and cancel complete the eight-event contract.

**Source and data.** `vibemind-os/coding-engine/` owns the application. The `space-coding` Swarm profile declares Postgres, Redis, Gitea/Postgres, code-server, egress proxy, API, worker, OpenClaude service and frontend. Named volumes hold database, Git, generated project and artifact state.

**Runtime.** Select with `-Spaces "coding"`. Preview the plan first:

```powershell
.\scripts\vibemind-start.ps1 -Spaces "coding" -DryRun
```

**Safety.** Coding can mutate files, repositories and external Git hosting. Keep work scoped to an approved repository/worktree, reject secrets before staging, never force-push protected branches and require terminal job/artifact evidence before reporting success.

**Verify.** Run coding-engine unit/integration tests for changed components, validate Compose/stack configuration, and verify job state plus produced artifact. An API process being healthy is not sufficient.

## Desktop

**Purpose.** Desktop and window automation, screenshots, Moiré perception, browser fetching, OpenClaw operations and messaging actions.

**Execution.** `brain-desktop` handles four prefix families: `desktop.*`, `web.*`, `messaging.*` and `openclaw.*`. Its configured MCP scope is `vibemind-db` and `desktop-automation`.

**Event groups.** Application/window actions, pointer/keyboard/scroll, task lifecycle, screenshot/perception, web search/fetch, OpenClaw browser/prompt/form/message operations and WhatsApp/Telegram/general messaging. There are 28 events.

**Source and runtime.** `vibemind-os/spaces/desktop/Automation_ui/` is a nested repository with backend, Electron/desktop clients and perception components. The root launcher treats Automation UI as a native module, configured on port `8007`; it is not a Swarm Space profile.

**Safety.** State-changing UI and outbound-message events in the registry require confirmation and `external_receipt` validation. Screenshot/read-only events do not. A successful tool return without an external receipt must not be presented as a completed click, form submission or message send.

**Verify.** Parse/configure the Automation UI component, run its focused perception/automation tests, then use a harmless visible target for an approved end-to-end receipt check. Never test against a destructive or production UI action by default.

## Research

**Purpose.** Web research and scraping, summarization into an existing idea, creation of a new idea and OpenClaw-assisted comparison.

**Execution.** `brain-researcher` handles `research.*` and two `openclaw.*` research events. MCP scope is `vibemind-db`, `fetch` and `qdrant`.

**Source and data.** The execution target is under `vibemind-os/spaces/research/`; routing adapters are in the voice swarm. Results may be persisted as Ideas and vector context may be retrieved from Qdrant.

**Runtime.** No dedicated Swarm profile. It composes existing fetch, Brain, database and optional OpenClaw capabilities.

**Safety.** External content is untrusted input. Preserve source attribution, enforce URL/network policy, avoid treating retrieved text as instructions and verify the durable Idea record when persistence is requested.

**Verify.** Run routing tests with a mocked fetch boundary, then separately test a current fetch if network access is authorized. A mock or cached response is static/test evidence only.

## Rowboat

**Purpose.** Knowledge-graph search and query, email drafting, meeting briefs, deck generation, status and controlled Docker lifecycle operations.

**Identity.** Canonical Space name is `rowboat`; canonical agent is `rowboat-chat`. Historical generated files may say `roarboot`, `rowboat-knowledge` or show no agent. Those values are not canonical.

**Execution.** MCP scope is `vibemind-db`, `fetch` and `spaces-rowboat`. `rowboat.status` is explicitly bound to `spaces-rowboat:rowboat_status` with approval and cost provenance.

**Source and data.** `vibemind-os/spaces/rowboat/` includes the Space adapter and the nested Rowboat application. The `space-rowboat` profile declares MongoDB, Redis, Rowboat UI/API, jobs worker and RAG worker; Qdrant is shared core infrastructure. Mongo, uploads and vector collections are distinct durability boundaries.

**Runtime.** The stack profile exists, while `rowboat-agents` is intentionally configured with zero replicas. The main Rowboat application does not require that removed/optional legacy service.

**Safety.** Draft generation is not message delivery. Docker start/stop operations are infrastructure mutations and require operational authority even though the registry contract does not currently mark confirmation fields.

**Verify.** Validate the `space-rowboat` stack render, run focused adapter tests and require a query result tied to ingested test content for verified-live RAG evidence.

## Minibook

**Purpose.** Collaboration discussions, project collaboration, service status and project listing.

**Execution.** `brain-knowledge` handles `minibook.*` with `vibemind-db`, `fetch` and `spaces-minibook`. `minibook.status` is an explicit MCP operation requiring approval and cost provenance.

**Source and data.** `vibemind-os/spaces/minibook/` owns the MCP adapter and tools. The root configuration points to `vibemind-os/voice/docker-compose.minibook.yml` and ports `3480`/`3481`, so deployment is separate from the main Swarm profile selector.

**Runtime.** Configured as an optional voice-integrated Compose application, not a `space-minibook` service group in the main stack.

**Safety.** Collaboration text and project lists may contain sensitive data. Bound external fetches, preserve provenance and do not equate a status response with successful collaboration persistence.

**Verify.** Validate the Minibook Compose file and adapter contract, then confirm a disposable collaboration artifact through its durable API/store for a live claim.

## Schedule

**Purpose.** Create, list, cancel, modify, inspect and snooze scheduled tasks; also accepts an OpenClaw cron contract.

**Execution.** `brain-scheduler` handles `schedule.*`. MCP scope is `vibemind-db` and `scheduled-tasks`. The source integrates natural-language time parsing, persistence and APScheduler job registration.

**Source and data.** `vibemind-os/spaces/schedule/` contains agent, NLP, tools, worker and execution modules. Schedule records are durable database state; APScheduler registrations are runtime state and must be reconciled after restart.

**Runtime.** Native/in-process integration without a dedicated main-stack profile.

**Safety.** Time zone, recurrence, idempotency and crash recovery are part of correctness. Creating a database row alone does not prove a future action is registered; a live success claim requires both persisted schedule state and scheduler readback.

**Verify.** Run the component tests, parse a deterministic time in an explicit timezone and verify create/list/cancel against an isolated store and scheduler.

## n8n

**Purpose.** Generate, list, inspect, activate, deactivate, delete and execute n8n workflows.

**Shape.** n8n is a **registry-routed MCP tool surface**, not a Space application. It is a canonical routing identity whose eight events are bound directly to MCP tools in the registry; every operation is executed by the third-party n8n engine through the `n8n` MCP server. Concretely, at the pinned `vibemind-os` revision recorded in `repo-manifest.yaml`:

- there is **no Space application** and **no `spaces/n8n` directory** — neither in this repository nor in `vibemind-os`, whose `spaces/` tree holds twelve directories (`_navigator` plus eleven Spaces) and no `n8n` entry. `vibemind-os/voice/python/spaces` is a symlink to that same `vibemind-os/spaces` tree, so it adds no n8n source root either;
- there is **no Space-owned data store**. The named `n8n_data` volume belongs to the third-party engine container, and the registry MCP scope is `vibemind-db` plus the external `n8n` server.

**Execution.** `brain-n8n` handles `n8n.*` with `mcp_servers: [vibemind-db, n8n]`. `vibemind-os/config/space_agent_registry.yml:241-259` binds each event to one MCP tool: `n8n.generate` → `n8n_generate_workflow`, `n8n.list` → `n8n_list_workflows`, `n8n.status` → `n8n_health_check`, `n8n.activate` and `n8n.deactivate` → `n8n_update_partial_workflow`, `n8n.delete` → `n8n_delete_workflow`, `n8n.execute` → `n8n_test_workflow`, `n8n.describe` → `n8n_get_workflow`. The registry remains authoritative for these contracts; this catalog entry changes none of them.

**Source and data.** Integration code and Compose definitions are owned by the `voice` component: `vibemind-os/voice/docker-compose.n8n.yml`, `vibemind-os/voice/docker/n8n/Dockerfile`, `vibemind-os/voice/configs/services/n8n.yml`, `vibemind-os/voice/python/ipc/n8n_handlers.py` and `vibemind-os/voice/python/publishing/n8n_publisher.py`. The main Swarm stack declares a single `n8n` service with named `n8n_data` storage and host port `15678`.

**Runtime.** `space-n8n` is a **single-service Compose profile**, not a Space service group: in `infra/swarm/vibemind-stack.yml` it gates exactly one service — the **third-party n8n engine** (`vibemind-n8n:latest`) — and `scripts/vibemind-spaces.ps1` maps the logical space `n8n` to that profile with the single service `n8n`. `infra/swarm/profiles/` carries no n8n operator profile document. Selecting the profile starts the engine; it does not start a Space application.

```powershell
.\scripts\vibemind-start.ps1 -Spaces "n8n" -DryRun
```

**Known drift.** The generated inventory `vibemind-os/data/space_capabilities/n8n.yml` reports `exists: true` with thirty-six tools under `spaces/n8n/tools/` and `spaces/n8n/agents/`, and `vibemind-os/voice/docs/python/spaces/n8n/README.md` describes the same tree; those paths do not exist at the pinned revision, and `vibemind-os/voice/python/ipc/n8n_handlers.py` still imports from `spaces.n8n.tools`. Treat all three as stale generated or historical material — they are **not evidence** of an n8n Space application.

**Safety.** Activation, deletion and execution can cause external side effects. Apply credential scoping, explicit action approval and execution receipts. Workflow JSON validity or n8n health alone does not prove an intended external outcome.

**Verify.** Confirm the eight registry event-to-tool bindings resolve, validate generated workflow JSON, inspect it before activation, execute only against test credentials/endpoints and correlate the n8n execution record with the expected terminal state. A rendered `space-n8n` profile proves engine configuration only, never Space-application existence.

## AgentFarm

**Purpose.** Contract surface for multi-agent team creation, runs, status, results, templates and collaboration.

**Identity and state.** Canonical name is `agentfarm`; `autogen` is an ingress alias. Canonical agent is currently `vibemind`, while `brain-agentfarm` is reserved. The registry explicitly sets `enabled: false` and runtime status `blocked` because a durable persistent AgentFarm runtime is missing.

**Source.** `vibemind-os/spaces/agentfarm/runtime-manifest-v1.json` records the reserved runtime contract. The root config also disables the module and documents a missing server build path. Older generated capability pages refer to removed `spaces/autogen` code and `brain-orchestrator`; do not use those as current execution evidence.

**Runtime.** No supported runtime should route or claim completion for AgentFarm today. The event contracts are documentation/reservation only.

**Safety.** Fail closed with a clear blocked/unavailable result. Do not silently fall back to a different multi-agent implementation or interpret a manifest as a running service.

**Verify.** Registry validation should confirm disabled state, canonical `vibemind` mapping and blocker metadata. Re-enablement requires restored versioned source, persistent state, focused lifecycle tests, deployment/health contracts and a new audit.

## Video

**Purpose.** Video pipeline status/run, vision analysis, demo analysis/build, lip sync, voice cloning and TTS.

**Execution.** `brain-video` handles nine `video.*` events. Its current registry MCP scope is `vibemind-db`; event hints use database-backed query/update/project operations.

**Source and data.** `vibemind-os/spaces/video/` includes the Space adapter, media server, pipeline tools and two nested video repositories. Video projects and metadata use database records; large media artifacts are served from the `rowboat-videos` named volume through the `space-media` nginx service.

**Runtime.** `-Spaces "media"` starts only the static publishing service. GPU/media generation dependencies remain component-specific native or container workloads and are not implied by that profile.

**Safety.** Voice cloning, lip sync and synthetic media require consent, provenance and responsible-use controls. Retain the nested `RESPONSIBLE_AI.md` policies. Publishing a file is a separate external action from generating it.

**Verify.** Run focused pipeline checks on non-sensitive fixtures, validate output media, then confirm database/project status and artifact existence. Never use real identities or voices without authorization.

## Flowzen

**Purpose.** Wellness recommendation, acceptance and current activity/status through the `rose.*` event family.

**Execution.** `brain-wellness` uses the `vibemind-db` scope. Three events map to Flowzen check-in/activity database operations.

**Source and data.** `vibemind-os/spaces/flowzen/mcp_server.py` exposes the Space boundary. Check-ins and activities are sensitive personal data and belong to the configured database owner.

**Runtime.** Lightweight logical/MCP integration without a dedicated main-stack profile.

**Safety.** Treat wellness output as non-medical guidance, minimize sensitive data, enforce access controls and never infer emergency/medical capability. Acceptance must be recorded only when explicitly provided by the user.

**Verify.** Run contract tests with synthetic data and verify a check-in/activity readback. Do not use production wellness records in development tests.

## MiroFish

**Purpose.** Forecast simulations and predictions, graph build/search, status, evaluation and agent interviews.

**Execution.** `brain-forecaster` handles seven `mirofish.*` events. Tool hints address the MiroFish application boundary; the registry MCP server list currently contains only `vibemind-db`, so runtime transport wiring must be validated rather than inferred.

**Source and data.** `vibemind-os/spaces/mirofish/` contains the nested application. The `space-mirofish` profile declares MiroFish and Neo4j with dedicated named volumes. Brain also references the graph endpoint, making schema and ownership boundaries important.

**Runtime.** Both MiroFish and Neo4j are profile-scoped and configured with zero replicas by default. Selecting the profile does not by itself override that deployment intent.

**Safety.** Forecasts are model outputs, not facts. Preserve input/model/provenance metadata, clearly label uncertainty and require terminal simulation/job state before reporting completion.

**Verify.** Validate profile rendering and registry transport mapping, run application tests, then use a disposable simulation to correlate job state, graph artifacts and prediction output.

## Cross-Space rules

1. Brain owns intent, planning and routing; OpenFang owns bounded execution and approvals.
2. Canonical IDs come from the registry. Aliases are accepted at ingress only and must not become new persisted identities.
3. Missing agents, tools, approvals, transport or terminal evidence fail closed.
4. Shared stores do not erase domain ownership: every write still needs a Space-level contract and correlated outcome.
5. External systems, messages, desktop actions and publication require explicit authority and receipts.
6. Static, configured, historical, reachable and verified-live evidence must remain distinct.

## Adding or changing a Space

Update all of the following in one reviewed change:

1. `vibemind-os/config/space_agent_registry.yml` for canonical identity and contracts;
2. implementation and focused tests at the owning source root;
3. OpenFang/MCP allowlists and approval rules;
4. stack/Compose/launcher definitions if a runtime is required;
5. this catalog and the architecture/deployment references;
6. generated capability inventories, after fixing their drift gate;
7. verification evidence that matches the claimed status level.
