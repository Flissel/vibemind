# Coding / SWE-Pipeline

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Coding/SWE pipeline (1063-1660 line range in `vibemind-stack.yml`) is VibeMind's autonomous code generation subsystem — a **distributed, event-driven architecture** consisting of 10+ Docker services (postgres/redis/gitea/vscode/egress-proxy/api/worker/clawcode-router/openclaude/frontend) plus native processes (OpenClaw, clawcode CLI). It transforms high-level requirements into production-ready TypeScript/NestJS applications through a 37+ agent Society of Mind pipeline, coordinated via an EventBus with 6-phase convergence validation. The stack integrates with Brain's routing matrix (Discourse dispatch), MCP servers (20+ tools), and specialized skills system (.claude/skills/). Code flows from specification → domain slicing → parallel generation → merge/validate → E2E → deployment within Docker Swarm overlay networks with egress-proxy firewall control.

## Services / Components

### Docker Swarm Stack Services (from `vibemind-stack.yml:1044-1605`)

**Database/Datastores (coding space):**
- `coding-postgres:5432` — PostgreSQL 16-alpine, database: `coding_engine`, user: `postgres:postgres` (infra/swarm/vibemind-stack.yml:1063-1100)
- `coding-redis:6379` — Redis 7-alpine with appendonly persistence (vibemind-stack.yml:1102-1130)
- `gitea-postgres:5432` — Dedicated Postgres for Gitea DB (vibemind-stack.yml:1136-1169)

**Frontend/IDE:**
- `coding-vscode:8443` → host:8444 — code-server (codercom/code-server:latest, password: `dev123`, generates code workspace at /home/coder/project) (vibemind-stack.yml:1232-1286)

**Version Control:**
- `coding-gitea:3000` → host:3002 — Gitea 1.23 Git server (SSH :2222), auth: `USER_UID=1000`, database: gitea-postgres (vibemind-stack.yml:1171-1218)

**Egress Firewall:**
- `coding-egress-proxy:8888` — tinyproxy (vimagick/tinyproxy:latest), overlay net `coding-egress` (internal:true = no default route), config: tinyproxy.conf + filter allowlist (vibemind-stack.yml:1288-1328)

**Code Generation API (Phase 2a/b):**
- `coding-api:8000` — davefelix-coding-engine-api:latest, command: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 1` (vibemind-stack.yml:1357-1426)
  - Deps: postgres, redis, gitea, clawcode-router (:8090), openclaude (:8091), docker.sock (DinD)
  - Env: `LLM_BACKEND=clawcode-router`, `OPENCLAUDE_URL=http://coding-openclaude:8091`, `CLAWCODE_ROUTER_URL=http://coding-clawcode-router:8090` (fallback)
  - Reaches brain-core:5000, qdrant:6333 via overlay DNS
  - Outputs to `/app/output` (coding_generated vol) and `/data/artifacts` (coding_artifact vol)

- `coding-worker:latest` — vibemind-coding-worker:latest, command: `python -m workers.agent_worker` (queue worker, no HTTP) (vibemind-stack.yml:1428-1476)
  - Deps: postgres, redis, docker.sock
  - Healthcheck: `pgrep -f 'workers.agent_worker'` (no HTTP surface)

- `coding-clawcode-router:8090` — davefelix-coding-engine-clawcode-router:latest (vibemind-stack.yml:1478-1537)
  - Binary LLM routing with role-dispatch to Anthropic/OpenAI/Groq/Ollama backends
  - Config: router.docker.toml (overrides image default), clawcode-providers.toml, kilo settings (MCP server list)
  - Env: `LLM_BACKEND=clawcode-router`, fallback to `OPENAI_API_KEY`=empty (Anthropic credit exhaust 2026-05-20)

- `coding-openclaude:8091` — davefelix-coding-engine-openclaude-service:latest (vibemind-stack.yml:1539-1604)
  - OpenAI-compatible (/v1/chat/completions) HTTP API wrapper around OpenRouter free models (z-ai/glm-4.5-air:free as primary 2026-05-20)
  - Env: `PORT=8091`, `OPENAI_BASE_URL=https://openrouter.ai/api/v1`, `OPENAI_MODEL=z-ai/glm-4.5-air:free`
  - Workspace: `/workspace` (coding_generated vol)
  - Preferred primary (no clawcode-binary parse bug, avoids exhausted Anthropic credit)

**Frontend (Phase 2c):**
- `coding-frontend:80` → host:5173 — vibemind-coding-frontend:static (Vite build → nginx static SPA + /api/v1 reverse proxy → coding-api:8000) (vibemind-stack.yml:1616-1655)
  - Nginx config: nginx-frontend.conf (swarm config, SPA root fallback, WS upgrade to /api/v1/engine/generation/ws)

**NOT in Swarm (permanently native):**
- `sandbox` — needs `privileged:true` + `/dev/kvm` (docker stack deploy silently drops these); api degrades gracefully without it (src/api/routes/dashboard.py try/except)
- `openfang` — Rust binary, self-daemonising, host-coupled network; built separately, started by Launcher in Phase-1 block
- `openclaw` — OpenClaw gateway (host :18789), used by api for browser automation integration

### Native Processes / Host Services

- **OpenFang** (:4200, HTTP API; :50051 gRPC bridge) — Native binary agent dispatcher, started by Launcher (Vibemind.debug.ps1), reaches Brain via OPENFANG_URL env
- **OpenClaw** (:18789, TCP gateway) — Browser automation controller, referenced as `OPENCLAW_URL=http://host.docker.internal:18789` in api env
- **Ollama** (:11434, /v1 compatible) — Local LLM fallback (llama3.1:latest, nomic-embed-text), used by mirofish/openclaude when OpenRouter rate-limits
- **Postgres** (host :5432) — Optional host-native DB (coding-engine can also use containerized postgres:5432 via overlay DNS)

## Dependencies

### UPSTREAM (what coding-engine needs)

**Critical stack services (must be running first):**
- `vibemind-shared` overlay network (connects all services via DNS)
- `qdrant:6333` — Vector DB (shared with Brain, rowboat via overlay DNS)
- Brain at `host.docker.internal:4200` (OPENFANG_URL) or brain-core:5000 (BRAIN_URL)
- Supabase Kong gateway at `host.docker.internal:54321` (if ideas/bubble execute targets)

**External LLM APIs (env vars from root .env file):**
- `OPENROUTER_API_KEY` → OpenRouter (used by clawcode-router, openclaude as fallback)
- `ANTHROPIC_API_KEY` → Anthropic (clawcode-router, currently credit-exhausted 2026-05-20)
- `OPENAI_API_KEY` (also mapped from OPENROUTER_API_KEY for openclaude via OPENAI_BASE_URL=https://openrouter.ai/api/v1)
- `GROQ_API_KEY` → Groq (used as Brain's primary LLM, also available to clawcode-router)

**File references (from vibemind-stack.yml configs:):**
- `../../vibemind-os/coding-engine/infra/egress-proxy/tinyproxy.conf` (coding_tinyproxy_conf config object)
- `../../vibemind-os/coding-engine/infra/egress-proxy/filter` (coding_tinyproxy_filter config object)
- `../../vibemind-os/clawcode/clawcode-router.docker.toml` (coding_clawcode_router_toml config object)
- `../../vibemind-os/clawcode/clawcode-providers.toml` (coding_clawcode_providers_toml config object)
- `../../vibemind-os/coding-engine/config/kilo/settings.json` (coding_kilo_settings config object)
- `../../vibemind-os/coding-engine/config/kilo/cli/global/settings/mcp_settings.json` (coding_kilo_mcp_settings config object)
- `../../vibemind-os/coding-engine/web-app/front/nginx-frontend.conf` (coding_frontend_nginx config object)

**Host directories (docker.sock for DinD):**
- `/var/run/docker.sock` — mounted into api and coding-worker for container spawning (sandbox provisioning)

### DOWNSTREAM (what calls coding-engine / who it talks to)

**From Brain (discourse dispatch):**
- Brain Router (via capabilities.yaml regexes) → dispatches `coding_task` intents to OpenFang agents
- OpenFang `/api/agents` returns list including `brain-coder`, `fungus-search` who may dispatch to coding-engine

**From ClaudeCodeTool (Claude Agent SDK):**
- ClaudeCodeTool (host process in Claude CLI / Agent SDK) communicates with api:8000/health + WebSocket /api/v1/engine/generation/ws for live streaming
- Fallback chain: openclaude:8091 → clawcode-router:8090 → ollama:11434 (if rate-limited)

**From Ideas Space (Supabase execute targets):**
- capabilities.yaml may route to `supabase:component.requirements` (Supabase REST), but coding-engine is NOT called by Ideas/bubble capabilities (decoupled)

**From Rowboat agents**:
- rowboat-agents:3001 may call coding-api:8000 via overlay DNS if integration is configured (not documented in Phase-1 stack)

**From Test/Validation agents:**
- Specialized agents (ValidationTeamAgent, TesterTeamAgent) in coding-engine's own pipeline call back to api via internal event system (EventBus pub/sub)

## Possible usages

### What you can DO with the Coding/SWE Pipeline

**API Entry Points (coding-api:8000):**
- `POST /api/v1/projects` — Create new code generation project (triggers orchestrator pipeline)
- `POST /api/v1/projects/{id}/jobs` — Submit code generation job (e2 phase execution)
- `GET /api/v1/projects/{id}/jobs/{job_id}` — Poll job status
- `WebSocket /api/v1/engine/generation/ws` — Live generation event stream (events: BUILD_STARTED, CODE_GENERATED, TEST_PASSED, E2E_TEST_FAILED, etc.)
- `GET /api/v1/dashboard/generation/{id}/pause` — Pause generation for user review
- `POST /api/v1/dashboard/generation/{id}/resume` — Resume with user feedback (ReviewChat feedback context)
- `GET /health` — Service liveness (returns 200 if postgres, redis, gitea reachable)

**Skills (invocable from coding-engine/.claude/skills/):**
- `/vibemind-os/coding-engine:chunk-planning` — Intelligently slice requirements into parallel tasks
- `/vibemind-os/coding-engine:code-generation` — Generate/fix TypeScript+React code from requirements
- `/vibemind-os/coding-engine:database-schema-generation` — Generate Prisma schemas
- `/vibemind-os/coding-engine:api-generation` — Generate REST APIs from TypeScript contracts
- `/vibemind-os/coding-engine:auth-setup` — Implement JWT/OAuth2/RBAC
- `/vibemind-os/coding-engine:environment-config` — Generate .env, Docker, CI/CD
- `/vibemind-os/coding-engine:e2e-testing` — Run Playwright browser tests against live preview
- `/vibemind-os/coding-engine:docker-sandbox` — Manage Docker container preview with VNC streaming
- `/vibemind-os/coding-engine:debugging` — Diagnose build/test failures
- `/vibemind-os/coding-engine:ux-review` — Claude Vision UI feedback analysis
- `/vibemind-os/coding-engine:validation` — Multi-agent debate completeness verification
- `/vibemind-os/coding-engine:ce-health-check` — Quick infrastructure health (15 sec)
- `/vibemind-os/coding-engine:ce-status-report` — Comprehensive status (DB tasks, generation loop, container health)
- `/vibemind-os/coding-engine:ce-pipeline-doctor` — Diagnose bottlenecks and suggest fixes
- `/vibemind-os/coding-engine:ce-task-audit` — Find over-granular tasks, broken dependencies

**Requirements JSON Format** (from `src/api/main.py:59, run_society_hybrid.py`)
```json
{
  "name": "project-name",
  "type": "electron|react|node|python",
  "description": "User-facing description",
  "features": [
    {
      "id": "feature_1",
      "name": "Feature Name",
      "description": "What it does",
      "priority": "high|medium|low"
    }
  ]
}
```

**Entry Points / Invocation Methods:**
1. **ClaudeCodeTool** (Claude Agent SDK / Claude CLI) — Wraps api via HTTP + WebSocket, streams generation events
2. **Direct REST API** — POST /api/v1/projects (requires auth token or is open in dev mode)
3. **Python CLI** — `python run_society_hybrid.py requirements.json --output-dir ./output` (standalone, direct EventBus, no HTTP)
4. **Electron Dashboard** — dashboard-app UI → API via IPC → FastAPI → EventBus orchestration
5. **Discord Bot** — Voice system may trigger via DISCORD_CHANNEL_ID env var (feature, not primary)

**Orchestration Modes:**
- **Autonomous** (--autonomous flag) — Runs full 6-phase pipeline until 100% requirement coverage
- **Fast** (--fast flag) — Minimal iteration, relaxed convergence criteria
- **Strict** (--strict flag) — 100% test pass, 0 type errors required
- **Review Gate** — Pause at checkpoint, user reviews VNC preview + chat feedback, resumes with context

**Output Artifacts:**
- `/app/output` or `/workspace` (coding_generated volume) — Generated project source code
- `/data/artifacts` (coding_artifact volume) — Build outputs, test reports, logs
- `reports/debug/` — DebugReport JSON (Claude Vision UI analysis)
- `reports/implementation/` — ImplementationPlan JSON (fix strategy)
- `reports/tests/` — TestSpec JSON (test specifications)
- `reports/quality/` — QualityReport JSON (refactoring suggestions)

## MCPs & OpenFang agents involved

### OpenFang Agents (from capabilities.yaml routing, accessed at :4200/api/agents)

These agents are NOT part of coding-engine but can DISPATCH to it:
- `brain-coder` — Code expert, primary dispatch for `code_search`, `code_review` capabilities
- `fungus-search` — Semantic code search (la-fungus-search semantic embeddings)
- `poc-security-scanner` / `poc-vuln-scanner` — Security analysis
- `rowboat-knowledge` — Bubble/ideas knowledge lookup
- `assistant` — Generic chitchat

**Coding-engine agents DO NOT directly call OpenFang**; instead:
1. Brain's discourse engine receives intent (e.g., "debug the build error")
2. Router matches capability pattern, dispatches to OpenFang agent list
3. OpenFang agent may call ClaudeCodeTool (Claude CLI with skills prompt)
4. ClaudeCodeTool wraps coding-api:8000 calls

### MCP Servers (called by coding-engine agents via src/mcp_plugins/servers/)

Located in `vibemind-os/coding-engine/mcp_plugins/servers/`:

**20+ MCP Server Implementations:**
- `filesystem/` — File I/O, directory tree (agent.py wraps pathlib)
- `playwright/` — Browser automation (agent.py wraps playwright Python SDK)
- `docker/` — Container management (docker SDK)
- `redis/` — Redis operations
- `github/` — Git/GitHub API
- `prisma/` — Prisma schema introspection (stdio to prisma CLI)
- `npm/` — Package management (npm CLI)
- `postgres/` — SQL execution (psycopg2)
- `brave-search/` — Web search (Brave API)
- `fetch/` — HTTP requests
- `supabase/` — Supabase REST/Realtime
- `memory/` — Agent memory (LLM context management)
- `n8n/` — Workflow automation
- `context7/` — Library doc fetching (plugin:context7:context7)
- `tavily/` — Search (Tavily API)
- `time/` — System time
- `claude-code/` — Claude CLI wrapper
- `git/` — Git CLI
- `windows-core/` — Windows-specific operations
- `desktop/` — Desktop automation
- `qdrant/` — Vector DB queries (semantic search)
- `supermemory/` — SuperMemory integration (batch context loading)

**Each server's agent.py exports:**
- `class <Name>Agent(AutonomousAgent)` — Inherits from `src/agents/autonomous_base.py`
- `subscribed_events` property — Which events trigger this agent
- `async def should_act()` — Predicate checking (is action needed?)
- `async def act()` — Execute the MCP tool + publish result events

### Brain Routing → Coding-Engine Flow (Phase 11.U.H)

From `vibemind-os/brain/the_brain/data/capabilities.yaml` lines 644-683:
```yaml
- capability: code_review
  description: "review code diff pull request changes"
  agents:
    primary: [brain-coder, fungus-search]
    supporting: [poc-security-scanner, rowboat-knowledge]
```

Flow:
1. User: "review my TypeScript code"
2. Brain routes to `code_review` capability (regex matches "review.*code")
3. DiscourseEngine calls OpenFang `/api/agents` list
4. OpenFang dispatches to `brain-coder` (primary)
5. brain-coder agent (in OpenFang) may call `ClaudeCodeTool` with prompt including coding-engine skills
6. ClaudeCodeTool calls api:8000 via HTTP + WebSocket for live feedback

**Key:** Coding-engine agents (37+ in Society of Mind) are **internal to the pipeline** (src/agents/). OpenFang agents (brain-coder, etc.) are external coordinators that **dispatch TO** coding-engine via ClaudeCodeTool.

## Isolated startup

### Minimal Stack to Test Coding-Engine ALONE

```bash
# Step 1: Start only coding services (no Brain, no rowboat, no mirofish)
docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind \
  --with-registry-auth

# Verify these are running (docker service ls | grep coding):
docker service ls | grep coding-
  vibemind_coding-postgres       1/1  Running
  vibemind_coding-redis          1/1  Running
  vibemind_coding-gitea          1/1  Running
  vibemind_coding-vscode         1/1  Running
  vibemind_coding-api            1/1  Running
  vibemind_coding-worker         1/1  Running
  vibemind_coding-clawcode-router 1/1 Running
  vibemind_coding-openclaude     1/1  Running
  vibemind_coding-frontend       1/1  Running
  vibemind_coding-egress-proxy   1/1  Running

# Step 2: Verify health
curl http://localhost:8000/health      # coding-api
curl http://localhost:8090/health      # coding-clawcode-router
curl http://localhost:8091/health      # coding-openclaude
curl http://localhost:5173/            # coding-frontend (SPA)
curl http://localhost:3002/            # coding-gitea

# Step 3: Check overlay network DNS resolution (inside container)
docker exec vibemind_coding-api-<task-id> \
  curl -v http://coding-postgres:5432

# Step 4: Verify env setup
docker service inspect vibemind_coding-api | grep -A 20 '"Env"'
  # Should show: LLM_BACKEND=clawcode-router, OPENCLAUDE_URL=http://coding-openclaude:8091, ...

# Step 5: Check DB schema (if app-level migrations are run)
docker exec vibemind_coding-postgres-<task-id> \
  psql -U postgres -d coding_engine -c "\dt"  # list tables
```

### Gaps / Known Limitations (Phase 1)

**Missing from Swarm (intentional design):**

| Service | Reason | Impact | Workaround |
|---------|--------|--------|-----------|
| `sandbox` | Needs `privileged:true` + `/dev/kvm` (stack deploy drops these) | Can't run live preview/VNC | api:8000 degrades gracefully (try/except in dashboard.py) |
| `openfang` | Rust binary, host-coupled networking | Can't dispatch to coding agents from Brain | OpenFang started separately by Launcher (Vibemind.debug.ps1) |
| `openclaw` | Browser automation controller (external binary) | Can't do browser automation via clickable UI | Playwright tests work within sandbox/docker (if it were running) |
| `minibook` | Git submodule empty (0 files) | No frontend component generator | tasks/gaps.md B1 — needs source restore |
| Ideas space HTTP service | No Dockerfile yet | Can't call bubble/idea capabilities | Phase 2+ (tasks/gaps.md B2) |
| Automation_ui (backend) | Native venv service | Not containerised yet | Launcher manages it; Phase 2 containerisation on backlog (tasks/gaps.md B4) |

**Required native services (must be running outside stack):**
- Ollama (:11434, /v1 compatible) — LLM fallback when OpenRouter rate-limits
- Postgres (optional host :5432) — Developers may prefer host DB for debugging

### Docker Network Topology

```
┌─────────────────────────────────────┐
│  vibemind-shared (overlay)          │
│  driver: overlay, attachable: true  │
│  enables: service-name DNS          │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ coding-egress (overlay)     │   │
│  │ internal: true = NO default │   │
│  │ route (forces proxy)        │   │
│  │                             │   │
│  │  • api, worker, openclaude  │   │
│  │    + clawcode-router join   │   │
│  │    both vibemind-shared     │   │
│  │    AND coding-egress        │   │
│  │                             │   │
│  │  • egress-proxy bridges     │   │
│  │    both nets = gateway out  │   │
│  └─────────────────────────────┘   │
│                                     │
│  • postgres, redis, gitea, vscode   │
│  • frontend, clawcode-router        │
│  • all on vibemind-shared only      │
│  (not on egress = can reach internet)
└─────────────────────────────────────┘
```

**DNS Resolution (overlay):**
- From inside stack: `curl http://coding-api:8000` → resolves to container IP
- From host: `curl http://localhost:8000` → published ingress port
- coding-egress `internal: true` = services on it CANNOT reach internet except via egress-proxy:8888 (tinyproxy)

## Key files

**Architecture & Configuration:**
- `infra/swarm/vibemind-stack.yml:1044-1605` — Stack deployment manifest (10 services, volumes, configs, networks)
- `vibemind-os/coding-engine/docker-compose.yml` — Dev/legacy compose (not in swarm)
- `vibemind-os/coding-engine/infra/docker/docker-stack.yml` — Older coding-engine stack (superseded by main vibemind-stack.yml)

**API & FastAPI:**
- `vibemind-os/coding-engine/src/api/main.py:1-150` — FastAPI app init, EventBus injection, lifespan handler, CORS, route registration
- `vibemind-os/coding-engine/src/api/routes/dashboard.py` — Generation pause/resume, review gate, sandbox health checks (try/except graceful degradation)
- `vibemind-os/coding-engine/src/api/routes/websocket.py` — WebSocket /api/v1/engine/generation/ws event stream

**Core Orchestration:**
- `vibemind-os/coding-engine/src/mind/orchestrator.py` — Agent lifecycle, convergence loop, 6-phase pipeline coordination
- `vibemind-os/coding-engine/src/mind/event_bus.py` — Pub/sub EventBus (async queues, push architecture, batch delivery)
- `vibemind-os/coding-engine/src/mind/shared_state.py` — Metrics singleton (test pass %, build success, convergence)
- `vibemind-os/coding-engine/src/engine/hybrid_pipeline.py` — 6-phase execution: Architecture→Slice→Merge→Test→Deploy→Validate

**Agents:**
- `vibemind-os/coding-engine/src/agents/autonomous_base.py` — Base class for all 37+ agents (subscribed_events, should_act, act)
- `vibemind-os/coding-engine/src/agents/generator_agent.py` — Main code generation agent (calls Claude via claude_code_tool)
- `vibemind-os/coding-engine/src/agents/continuous_debug_agent.py` — Real-time error diagnosis with hot reload
- `vibemind-os/coding-engine/src/agents/deployment_team_agent.py` — Docker sandbox + VNC streaming

**Skills System:**
- `vibemind-os/coding-engine/.claude/skills/SKILL.md` files — 12 skill definitions (code-generation, test-generation, database-schema-generation, etc.), each with trigger events + tier markers (MINIMAL/STANDARD/FULL)
- `vibemind-os/coding-engine/src/skills/skill.py` — get_tier_content(), get_tier_prompt(), has_tier_support()
- `vibemind-os/coding-engine/src/tools/claude_code_tool.py:1-100` — Wraps Claude CLI with skill-aware prompts

**Tools & Execution:**
- `vibemind-os/coding-engine/src/tools/claude_code_tool.py` — Claude CLI wrapper (fallback), skill tier selection
- `vibemind-os/coding-engine/src/tools/claude_agent_tool.py` — Claude Agent SDK integration (primary LLM)
- `vibemind-os/coding-engine/src/tools/sandbox_tool.py` — Docker sandbox provisioning, VNC stream management
- `vibemind-os/coding-engine/src/tools/test_runner_tool.py` — Vitest/Jest execution, coverage capture

**Validators:**
- `vibemind-os/coding-engine/src/validators/base_validator.py` — ValidationFailure structured error format
- `vibemind-os/coding-engine/src/validators/no_mock_validator.py` — CRITICAL: Rejects jest.mock(), sinon, etc. (Enforced policy: only real integration tests)
- `vibemind-os/coding-engine/src/validators/typescript_validator.py` — TypeScript type checking
- `vibemind-os/coding-engine/src/validators/build_validator.py` — npm/vite build success

**Database & ORM:**
- `vibemind-os/coding-engine/src/models/base.py` — SQLAlchemy session factory, init_db()
- `vibemind-os/coding-engine/prisma/schema.prisma` — Prisma schema (if agent generates Prisma-based projects)

**Testing & Validation:**
- `vibemind-os/coding-engine/tests/mind/` — Push architecture tests (EventBus, async queue delivery)
- `vibemind-os/coding-engine/tests/orchestrator/` — Phase-based orchestrator tests
- `vibemind-os/coding-engine/tests/integration/` — Real Docker, real HTTP integration

**Configuration:**
- `vibemind-os/coding-engine/src/config.py` — get_settings(), environment variables (DATABASE_URL, REDIS_URL, LLM_BACKEND, OPENCLAUDE_URL, CLAWCODE_ROUTER_URL)
- `vibemind-os/coding-engine/.env` (repo root) — API keys (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, GROQ_API_KEY)

**MCP Plugins:**
- `vibemind-os/coding-engine/mcp_plugins/servers/` — 20+ MCP server implementations (filesystem/, playwright/, docker/, postgres/, etc.)
- `vibemind-os/coding-engine/mcp_plugins/models/model_router.py` — Routes LLM calls between backends (claude, openai, groq, ollama)

**Entry Points:**
- `vibemind-os/coding-engine/run_society_hybrid.py` — CLI entry: `python run_society_hybrid.py requirements.json --output-dir ./output`
- `vibemind-os/coding-engine/run_epic001_live.py` — Epic Orchestrator (Layer 2+3 with MCP agents)
- `vibemind-os/coding-engine/run_hybrid.py` — Basic pipeline runner

## Gotchas

**2026-05-20 State Known Issues & Workarounds:**

1. **OpenRouter Credit Exhausted** — OpenRouter free tier hit rate-limit/402 on all openai/* + anthropic/* calls
   - **Workaround:** clawcode-router routes to Groq (groq::llama-3.3-70b) as primary, clawcode falls back to local Ollama (:11434, llama3.1)
   - **Code:** vibemind-stack.yml:164 `PLANNER_MODEL=gpt-4o-mini` (direct OpenAI, bypasses OpenRouter)
   - **Fix:** Restore OpenRouter credit or migrate to direct Claude API

2. **Code-Server Extensions Crash (EACCES)** — coding-vscode with named volume for extensions → root-owned volume + uid 1000 app = permission denied
   - **Root Cause:** Docker named volumes default to root:root ownership; code-server uid 1000 (coder) cannot mkdir inside
   - **Fix:** Dropped extensions volume entirely (vibemind-stack.yml:1240-1254 comment). Extensions re-download on demand; no persistence loss (were 0 files).

3. **No /dev/kvm for Sandbox** — `docker stack deploy` silently drops `privileged: true` and `devices: /dev/kvm`
   - **Impact:** Cannot run live preview/VNC in stack
   - **Workaround:** sandbox runs as native compose or not at all; api degrades gracefully (src/api/routes/dashboard.py try/except → "sandbox unreachable")
   - **Future:** Refactor sandbox as sidecar privileged pod in Kubernetes

4. **OpenFang is Native, Not Containerised** — Rust binary, host-coupled networking, 10-30 min build time
   - **Impact:** Cannot migrate into Swarm stack without losing host-coupled features
   - **Design:** Kept permanently native; Launcher (Vibemind.debug.ps1) manages OpenFang lifecycle

5. **Gitea & Brain Brain Contention (2026-06-08)** — Brain BRAIN_BACKGROUND_LOOPS=1 (ContinuousThinking, Consolidation, MCMP-Gardener, ClusterEngine) GIL-binds single async HTTP server
   - **Symptom:** API responses stalled during high background load
   - **Fix:** brain-core runs `BRAIN_BACKGROUND_LOOPS=0` (HTTP-only, loop-free); brain-loops service runs loops in separate process (vibemind-stack.yml:332-387)
   - **Lesson:** Never run CPU-bound loops + async HTTP in same process on single Python interpreter

6. **Localhost vs 127.0.0.1 in Healthchecks** — BusyBox wget resolves `localhost` to IPv6 [::1] first; nginx-media.conf only listens IPv4 (:80)
   - **Symptom:** Healthcheck fails forever (connection refused) → kill loop
   - **Fix:** Use `http://127.0.0.1` (explicit IPv4) in healthcheck probes (vibemind-stack.yml:552 comment, 1634 coding-frontend probe)
   - **Lesson:** STANDARDS.md §2 — Verify healthcheck tool + address family inside real container, never assume

7. **Kilo CLI MCP Config Path Resolution** — Dockerfile EXPOSE says 8091, but Bun script defaults to hard-coded 8007 if PORT env unset
   - **Symptom:** Port mismatch: stack publishes 8091:8091, but service listens 8007 → health probe times out
   - **Fix:** Force `PORT=8091` in environment (vibemind-stack.yml:1550)

8. **Rowboat Agents Replicas=0** — apps/rowboat_agents source is missing (upstream removed in mid-2025); modern Rowboat doesn't need external agents service
   - **Impact:** rowboat-agents container stays 0/1 (intentional, not a bug)
   - **Design:** Rowboat UI (:3100) + API + jobs + RAG all from single image; external agents is optional legacy

9. **No Secrets in Stack** — Secrets are External (docker secret ls), NOT provisioned by stack file
   - **Root Cause:** `docker stack deploy` requires secrets to exist before deploy (created by scripts/swarm_secrets_init.ps1)
   - **Symptom:** Deploy hangs or fails if secrets are missing
   - **Fix:** Run Launcher's secret provisioning step first

10. **Vivid GPU Support Conditional** — NVIDIA_VISIBLE_DEVICES env only set if Launcher detects NVIDIA GPU + nvidia-runtime active
    - **Symptom:** Embedding (CUDA-accelerated Qwen) falls back to CPU if GPU env empty
    - **Design:** Portable (GPU-less hosts → CPU, no crash); check VIBEMIND_GPU_DEVICES env before relying on CUDA

**Memory Hints:**

- **Where to Read Requirements:** `vibemind.config.json:11-14` defines module paths; brain path = `vibemind-os/brain/the_brain`; coding_engine path = `vibemind-os/coding-engine`
- **Phase Timeline:** Phase 1 (swarm infra only) → Phase 2a/b (code-baked services: api/worker/clawcode/openclaude) → Phase 2c (frontend static build) → Phase 3+ (K8s, cells, distributed)
- **Event Dispatch:** All agent communication via EventBus (src/mind/event_bus.py), NOT direct function calls — enables loose coupling + concurrent scaling
- **Skills are NOT Autonomous Agents:** Skills (.claude/skills/SKILL.md) are instruction sets for LLM (Claude), not agents. Agents (GeneratorAgent, etc.) read + execute skills.
- **NO MOCKS Policy:** Enforced in NoMockValidator — any jest.mock(), sinon, nock, etc. fails validation. All tests must hit real postgres, real HTTP, real sandbox containers.

---

END OF COMPREHENSIVE REFERENCE
