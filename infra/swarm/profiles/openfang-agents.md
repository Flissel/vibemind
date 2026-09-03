# OpenFang + Agents

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

OpenFang is the MCP aggregator hub and agent orchestration runtime (:4200) that integrates VibeMind's cognitive Brain with 30+ specialized MCP tool servers (security, system, devops, web/code, voice, and custom spaces). VibeMind Brain routes intents to 10+ brain-* OpenFang agents (coder, devops, researcher, planner, writer, knowledge, monitor, security, orchestrator, fallback), each with scoped MCP tool access and Claude Code base models. The ecosystem connects via HTTP (Brain → OpenFang agent API), stdio (OpenFang → MCP servers), and SSE (OpenFang → Brain for cognitive state queries).

## Services / Components

### Docker Swarm (vibemind-stack.yml)

- **qdrant** — Shared vector DB (port 6333 in-stack, :6730 host-published). Single overlay service resolving 3-way collision. image: `qdrant/qdrant:latest@sha256:b3063c673...` (Phase A verified digest). (`infra/swarm/vibemind-stack.yml:32-65`)
- **brain-core** — Brain cognitive system (port 5000). Command: `python start_server.py 5000`. Environment: `INSANE_AUTOGEN=1`, `BRAIN_BACKGROUND_LOOPS=0`, `BRAIN_HTTP_WORKERS=2`. (`infra/swarm/vibemind-stack.yml:67-100`)

### Native Processes (Host / VirtualEnv)

- **OpenFang daemon** — Agent OS kernel written in Rust. Native binary `vibemind-os/openfang/target/release/openfang.exe`. Start: `openfang.exe start --config openfang.vibemind.toml`. Port: **:4200** (HTTP API). Config: `vibemind-os/openfang/openfang.vibemind.toml` (merged with `~/.openfang/config.toml`). (`vibemind.config.json:55`, `openfang.vibemind.toml:9-10`)
- **Brain server** (Tahlamus) — Python FastAPI. Start: `python -m web.brain_server` from `vibemind-os/brain/the_brain`. Ports: :5000 (main), :5001 (API), :5003 (unified), :8900 (SSE for MCP). Multihop execute: `/api/multihop/execute` (routes intents through capability pipelines). (`vibemind.config.json:50-54`, `VIBEMIND_INTEGRATION.md:170-176`)
- **Bridge** — Python FastAPI. Port :5150. Translates OpenFang agent requests to Brain multihop calls. Location: `vibemind-os/bridge/src/bridge/`. (`vibemind.config.json:54`, `openfang_client.py:25-71`)

### MCP Servers (32+, Registered in openfang.vibemind.toml)

**Always-On (Python stdio, no external deps):**
- **brain** — SSE transport, url=`http://localhost:8900`. Cognitive state queries. (`openfang.vibemind.toml:66-71`)
- **issue-detector** — Python stdio. Auto-scan logs + file issues. (`openfang.vibemind.toml:74-80`, `vibemind-os/issue-detector/`)
- **Security (7 servers):** network-monitor, firewall, event-log, botnet-detector, endpoint-hardening, site-verifier. Python stdio. (`openfang.vibemind.toml:86-132`, `vibemind-os/security/poc_*/`)
- **System (8 servers):** driver-manager, power-manager, display-audio, process-manager, registry, scheduled-tasks, update-manager, env-manager. Python stdio. (`openfang.vibemind.toml:138-200`, `vibemind-os/system/poc_*/`)
- **DevOps (1 server):** backup-sync. Python stdio. (`openfang.vibemind.toml:206-212`, `vibemind-os/devops/poc_backup_sync/`)
- **Business (1 server):** pitch-deck. Python stdio. (`openfang.vibemind.toml:218-224`, `vibemind-os/business/poc_pitch_deck/`)
- **Desktop-Knowledge split (4 servers):** desktop-knowledge, desktop-document, perception, messenger. Python stdio. Replaced monolithic "desktop-automation" 2026-06-02. (`openfang.vibemind.toml:428-465`, `spaces/desktop/Automation_ui/backend/moire_agents/`)
- **rowboat-ui** — Electron app chat via CDP :9223. Python stdio. (`openfang.vibemind.toml:470-476`)
- **Spaces:** spaces-ideas, space-navigator. Python stdio. (`openfang.vibemind.toml:483-505`)

**Installed On Demand (npm/uvx/pip, lazy-loaded):**
- **Web/Research:** tavily, brave-search, playwright, fetch, context7 (npm). (`openfang.vibemind.toml:230-267`)
- **Code:** filesystem, git, github (npm + uvx). (`openfang.vibemind.toml:273-311`)
- **Infrastructure:** docker, time, qdrant (uvx). (`openfang.vibemind.toml:314-339`)
- **Memory/Productivity:** memory, redis, postgres, taskmanager (npm). (`openfang.vibemind.toml:346-381`)
- **VibeMind DB:** vibemind-db (Python MCP wrapping Supabase PostgREST). (`openfang.vibemind.toml:387-393`)

## Dependencies

### Upstream (What OpenFang Needs)

**Host dependencies:**
- Rust toolchain (for building OpenFang). (`vibemind-os/openfang/Cargo.toml`)
- Python 3.11+ (for MCP servers, Bridge, Brain). Shared venv at `.venv`. Voice-specific venv at `vibemind-os/voice/.venv312`.
- Node.js 18+ (for npm-based MCP servers: playwright, filesystem, github, context7, redis, postgres, memory, taskmanager, tavily-mcp).
- Docker (for Docker MCP server, Qdrant container, optional coding-engine/automation containers).
- uvx/uv (for uvx-installed MCP servers: fetch, git, time, qdrant, docker-mcp).

**Database:**
- **Qdrant** (port 6730 host, 6333 in-stack) — Vector DB for embedding search (mind, qdrant MCP). Persistent volume: `qdrant_storage`.
- **Redis** (port 6379 host, optional) — Event bus, locks, cache. Configured in redis MCP.
- **PostgreSQL** (optional, for postgres MCP) — SQL queries, schema inspection.
- **Supabase PostgREST** — VibeMind DB (22 tables), queried via vibemind-db MCP.

**Internal services:**
- **Brain server** (port 8900 SSE, 5000 main API) — Routing decisions, cognitive state, multihop execute.
- **Bridge** (port 5150) — OpenFang ↔ Brain translator.

**External APIs (env vars in openfang.vibemind.toml):**
- `ANTHROPIC_API_KEY` — Claude Code LLM (default provider in openfang.vibemind.toml:60-62).
- `OPENROUTER_API_KEY` — space-navigator layer 3 tiebreaker (gpt-4o-mini). (`openfang.vibemind.toml:505`)
- `TAVILY_API_KEY`, `BRAVE_API_KEY` — Web search.
- `TELEGRAM_BOT_TOKEN` — Channel input (polling enabled in openfang.vibemind.toml:41-58).
- `GITHUB_PERSONAL_ACCESS_TOKEN`, `POSTGRES_CONNECTION_STRING`, `SUPERMEMORY_API_KEY` (optional).

### Downstream (What Calls OpenFang)

**Voice / Electron UI:**
- Voice engine (Python, electron_backend.py) — Auto-starts OpenFang on app launch.
- Electron app (TUI Multiverse) — Communicates with OpenFang for space-navigator events + rowboat-ui integration.

**Brain capability routing:**
- Brain's `/api/multihop/execute` → decides which OpenFang agent to dispatch to. (`openfang_brain_gateway_wrapper.py:8-29`)

**Channels:**
- Telegram bot (polling, :4200/channels/telegram endpoint, routes to `brain-gateway` agent via Telegram consumer). (`openfang.vibemind.toml:41-58`, `VIBEMIND_INTEGRATION.md:217-225`)

**External MCP clients:**
- Claude Desktop, Cursor, VS Code (via MCP Server mode — OpenFang exposes agents as MCP tools). (`openfang-agents-server.py` wraps :4200 HTTP API for MCP consumers).

**A2A protocol:**
- Inter-agent calls (brain-orchestrator dispatches to specialist agents via A2A). (`openfang.vibemind.toml:511-517`, `docs/mcp-a2a.md`)

## Possible Usages

### Capabilities / API Endpoints

**OpenFang HTTP API (:4200):**
- `POST /api/agents` — Spawn agent from template. `{"template": "brain-coder"}` → `{"id": "...", "name": "brain-coder"}`. (`openfang_agents_server.py:54-64`)
- `GET /api/agents` — List all running agents. (`openfang_agents_server.py:41-50`)
- `POST /api/agents/{id}/message` — Send task to agent. `{"message": "..."}` → `{"response": "...", "id": ...}`. (`openfang_client.py:74-94`)
- `GET /api/agents/{id}` — Agent details (status, uptime, model, capabilities).
- `DELETE /api/agents/{id}` — Kill agent.
- `POST /a2a` — Agent-to-agent task delegation (A2A protocol). (`openfang.vibemind.toml:511-517`)
- `GET /api/health` — Daemon health + MCP server status.
- `GET /api/models` — Registered LLM provider models.
- `POST /api/approvals` — Approval gate for human-in-the-loop tasks (e.g., marketing broadcasts). Timeout: 300s (configurable). (`openfang.vibemind.toml:34-35`)

**Brain multihop integration:**
- `POST /api/multihop/execute` (Brain :5000) — Route intent through capability pipelines → determine agent + execute. Called by `openfang_brain_gateway_wrapper.py`. (`openfang_brain_gateway_wrapper.py:11-29`)

**MCP Tools (via agent system prompts):**
- **brain-coder** — file_read, file_write, git, github, context7, qdrant, filesystem, fetch. (`VIBEMIND_INTEGRATION.md:41`)
- **brain-devops** — docker, redis, postgres, filesystem, git, driver-manager, power-manager, process-manager, registry, env-manager, scheduled-tasks. (`VIBEMIND_INTEGRATION.md:42`)
- **brain-researcher** — tavily, brave-search, fetch, playwright, context7, filesystem, memory, qdrant. (`VIBEMIND_INTEGRATION.md:43`)
- **brain-planner** — taskmanager, memory, qdrant, filesystem, time. (`VIBEMIND_INTEGRATION.md:44`)
- **brain-writer** — filesystem, memory, context7, tavily. (`VIBEMIND_INTEGRATION.md:45`)
- **brain-knowledge** — qdrant, memory, context7, filesystem, issue-detector. (`VIBEMIND_INTEGRATION.md:46`)
- **brain-monitor** — docker, process-manager, event-log, issue-detector, network-monitor, redis, postgres. (`VIBEMIND_INTEGRATION.md:47`)
- **brain-security** — botnet-detector, endpoint-hardening, firewall, network-monitor, event-log, site-verifier, issue-detector. (`VIBEMIND_INTEGRATION.md:48`)
- **error-monitor** (autonomous) — file_read, shell_exec (curl), issue-detector, time, brain (scans Loki + logs every 20min). (`agents/error-monitor/agent.toml:60,69`)
- **email-assistant** — file_read, file_write, file_list, memory_store, memory_recall, web_fetch. (`agents/email-assistant/agent.toml:59`)
- **approval-handler** — Processes approvals for Telegram/broadcast actions. Used by marketing curator bridge. (`agents/approval-handler/agent.toml`)

**Voice-triggered invocation (via Telegram/Discord):**
- Telegram user sends message → bot polls :4200 → routes to `brain-gateway` agent (default_agent in openfang.vibemind.toml:58) → agent calls `openfang_brain_gateway_wrapper.cmd` wrapper (Python script that POSTs to Brain's multihop) → Brain routes to appropriate capability → returns result to Telegram. (`openfang.vibemind.toml:44-58`, `openfang_brain_gateway_wrapper.py:1-40`)

**Space-navigation (Multiverse):**
- Natural-language query like "go to the research space" → space-navigator MCP resolves via 3-layer fallback (alias → Qwen3 embedding → gpt-4o-mini LLM) → broadcasts navigate_to_space event → Electron UI reacts. (`openfang.vibemind.toml:498-505`, `VIBEMIND_INTEGRATION.md:80-108`)

## MCPs & OpenFang Agents Involved

### MCP Servers (32+)

**Registered in openfang.vibemind.toml (lines 66-505):**
- Always-on: brain, issue-detector, 7 security POCs, 8 system POCs, backup-sync, pitch-deck, desktop-knowledge, desktop-document, perception, messenger, rowboat-ui, spaces-ideas, space-navigator.
- Lazy-loaded: tavily, brave-search, playwright, fetch, context7, filesystem, git, github, docker, redis, postgres, memory, qdrant, taskmanager, time, vibemind-db.

### OpenFang Agents (21 brain-* / 30+ total)

**Brain-routed (10 core agents, routed by Brain capability decision):**
- brain-coder, brain-devops, brain-researcher, brain-planner, brain-writer, brain-knowledge, brain-monitor, brain-security, brain-fallback, brain-orchestrator. (`VIBEMIND_INTEGRATION.md:35-50`, `agents/brain-*/agent.toml`)

**Specialized agents (30+):**
- email-assistant, error-monitor, approval-handler, code-reviewer, debugger, security-auditor, test-engineer, doc-writer, analyst, architect, hello-world, assistant, and others. (`vibemind-os/openfang/agents/` — 53 total directories)

**Non-brain agents:**
- orchestrator, ops, analyst, architect, coder, researcher, writer, debugger, security-auditor, test-engineer, code-reviewer, etc. (generic OpenFang templates usable outside Brain routing). (`agents/*/agent.toml`)

### Agent Wrappers (scripts/openfang_*_wrapper.py/cmd)

**Brain dispatch wrappers:**
- `openfang_brain_gateway_wrapper.cmd/.py` — Translates Telegram → Brain multihop. stdin: prompt, stdout: Brain multihop result. Env: `BRAIN_MULTIHOP_URL` (default http://127.0.0.1:5000/api/multihop/execute), `BRAIN_GATEWAY_TIMEOUT_S` (default 290s). (`scripts/openfang_brain_gateway_wrapper.py:1-80`, `.cmd:1-24`)

**Other agent wrappers:**
- `openfang_openclaw_wrapper.py` — OpenClaw browser automation agent integration.
- `openfang_openclaude_wrapper.py` — OpenClaude coder integration.
- `openfang_openclaw_visible_wrapper.py` — Visible browser mode for OpenClaw.
- `openfang_som_*_wrapper.py` — SoM (System of Minds) agent wrappers (planner, execute, resume, team). (`scripts/openfang_som_*.py/.cmd`)

### Agent Registration Mechanism

Agents are registered as TOML files in `vibemind-os/openfang/agents/{agent-name}/agent.toml`. Each defines:
- `name`, `version`, `description`, `author`, `module` (typically "builtin:chat").
- `[model]` — LLM provider (default, claude-code, ollama, openai, gemini, groq), model name, system_prompt.
- `[capabilities]` — tools (MCP server allowlist), network (CIDR), memory_read/write (scopes), shell (command patterns), mcp_servers (which MCP servers to connect to).
- `[resources]` — max_llm_tokens_per_hour, max_concurrent_tools.
- `[schedule]` (optional) — continuous, periodic, cron intervals.

OpenFang daemon loads all agent.toml files at startup and makes them available as templates for spawning. (`openfang_agents_server.py:45-64`)

## Isolated Startup

To test OpenFang + Agents in isolation (minimum viable setup):

**Prerequisites:**
```bash
# Install dependencies
pip install -r vibemind-os/openfang/requirements.txt
npm install -g @playwright/mcp @modelcontextprotocol/server-filesystem
uv tool install mcp-server-fetch mcp-server-git mcp-server-time

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export OPENROUTER_API_KEY=sk-or-v1-...
export TELEGRAM_BOT_TOKEN=123:ABC...  # (optional, for Telegram channel)
```

**Start Brain (Terminal 1):**
```bash
cd vibemind-os/brain/the_brain
python -m web.brain_server
# Listen: http://localhost:5000 (main), :8900 (SSE for MCP)
```

**Start OpenFang (Terminal 2):**
```bash
cd vibemind-os/openfang
./target/release/openfang.exe start --config openfang.vibemind.toml
# Listen: http://localhost:4200 (HTTP API), :4200/a2a (A2A protocol)
# Auto-loads 32+ MCP servers defined in openfang.vibemind.toml
# Spawns Telegram consumer if TELEGRAM_BOT_TOKEN env is set
```

**Start vector DB (optional, Terminal 3 if not Docker):**
```bash
docker run -d -p 6730:6333 qdrant/qdrant:latest
```

**Verify (Terminal 4):**
```bash
# Check Brain routing
curl -s http://localhost:5000/api/cortex/route/stats

# Check OpenFang health
curl -s http://localhost:4200/api/health

# List agents
curl -s http://localhost:4200/api/agents | grep brain-

# Spawn brain-coder agent
curl -X POST http://localhost:4200/api/agents \
  -H "Content-Type: application/json" \
  -d '{"template": "brain-coder"}'

# Send task to agent
curl -X POST http://localhost:4200/api/agents/<agent-id>/message \
  -H "Content-Type: application/json" \
  -d '{"message": "List Python files in /tmp"}'
```

**Gaps / Known Missing in Isolated Setup:**
- **Telegram channel** — Requires valid TELEGRAM_BOT_TOKEN. Without it, no incoming messages to route; API still works.
- **Bridge** (port 5150) — Not required for basic OpenFang operation, but needed for Brain ↔ OpenFang translation. Start if testing Brain multihop: `cd vibemind-os/bridge && python -m bridge.main`.
- **Electron app** — Not needed for OpenFang; provides UI. Multiverse space-navigator broadcasts navigate_to_space events to app :9223 (CDP).
- **Docker MCP** — Requires Docker daemon running locally.
- **Playwright MCP** — Requires Chromium/Firefox/WebKit (lazy-installed on first use).
- **Qdrant MCP** — Requires Qdrant on :6340 (or env QDRANT_URL).
- **issue-detector** — Can write to GitHub but requires GITHUB_PERSONAL_ACCESS_TOKEN for fallback.

## Key Files

**Core configuration:**
- `vibemind-os/openfang/openfang.vibemind.toml` — VibeMind-specific OpenFang config: API listen, heartbeat (360s), approval timeout (300s), Telegram channel, all 32+ MCP server registrations, A2A protocol setup. **This file merges with `~/.openfang/config.toml` at startup; VibeMind config takes precedence.** (`openfang.vibemind.toml:1-517`)

**Agent templates:**
- `vibemind-os/openfang/agents/brain-*/agent.toml` — 10 brain-routed agents (coder, devops, researcher, planner, writer, knowledge, monitor, security, fallback, orchestrator). Each defines system_prompt, mcp_servers allowlist, capabilities.
- `vibemind-os/openfang/agents/error-monitor/agent.toml` — Autonomous error scanner (20min poll cycle). (`agents/error-monitor/agent.toml:1-70`)
- `vibemind-os/openfang/agents/email-assistant/agent.toml` — Email triage + drafting. (`agents/email-assistant/agent.toml:1-63`)

**Brain integration:**
- `vibemind-os/brain/the_brain/core/auto_dispatcher.py` — Phase F.4 autodispatch via explicit @mentions. (`auto_dispatcher.py:1-80`)
- `vibemind-os/brain/the_brain/core/capability_router.py` — Routes intents to brain-* agents via capability pipeline. 
- `vibemind-os/brain/the_brain/core/multihop_advisor.py` — Multihop execution logic.

**Wrapper scripts (bridge OpenFang to Brain):**
- `scripts/openfang_brain_gateway_wrapper.py` — Deterministic bridge: Telegram → Brain multihop → OpenFang agent. stdin: prompt, stdout: final_text. (`openfang_brain_gateway_wrapper.py:1-120+`)
- `scripts/openfang_brain_gateway_wrapper.cmd` — Shim launching the Python wrapper. (`openfang_brain_gateway_wrapper.cmd:1-24`)

**MCP servers:**
- `vibemind-os/openfang/mcp/openfang_agents_server.py` — MCP wrapper around OpenFang HTTP API (:4200). Exposes agent_list, agent_send, agent_spawn, agent_kill for MCP clients (Claude Desktop, Cursor, etc.). (`openfang_agents_server.py:1-150+`)
- `vibemind-os/openfang/mcp/agent_hooks.py` — Optional pre/post-spawn lifecycle hooks for agents.

**Bridge (Brain ↔ OpenFang translator):**
- `vibemind-os/bridge/src/bridge/openfang_client.py` — Async HTTP client for OpenFang. ensure_agent(), send_message(), AgentResult. (`openfang_client.py:1-100+`)
- `vibemind-os/bridge/src/bridge/main.py` — FastAPI server (:5150).

**Docker & Infrastructure:**
- `infra/swarm/vibemind-stack.yml` — Docker Swarm stack (qdrant, brain-core). (`vibemind-stack.yml:1-100+`)
- `vibemind-os/openfang/docker-compose.yml` — OpenFang container compose (builds from source). (`docker-compose.yml:1-26`)
- `vibemind-os/openfang/Dockerfile` — OpenFang binary build.
- `vibemind-os/openfang/deploy/openfang.service` — Systemd service unit for Linux deployment. (`openfang.service:1-40`)

**Documentation:**
- `vibemind-os/openfang/VIBEMIND_INTEGRATION.md` — Complete integration guide (agents, MCPs, startup, testing). (`VIBEMIND_INTEGRATION.md:1-250+`)
- `vibemind-os/openfang/docs/mcp-a2a.md` — MCP + A2A protocol reference. (`docs/mcp-a2a.md:1-100+`)
- `vibemind-os/openfang/docs/architecture.md` — OpenFang Rust architecture.
- `vibemind.config.json` — Project-wide service metadata (ports, docker compose files, module enable/disable). (`vibemind.config.json:1-106`)

## Gotchas

**Heartbeat timeout (360s vs default 60s):**
- Brain gateway routes Telegram messages through Brain multihop (browser_automation, coding_task, desktop_skill) which can take 30-300s. OpenFang kernel at 60s heartbeat marked agents "Crashed" mid-request, killing openclaw-visible at 50s during Chrome navigation. 2026-05-29 fix: raised `[heartbeat] default_timeout_secs = 360` (below claude_code driver's 300s timeout ceiling). Without this block, Telegram bot fails spuriously on long-running tasks. (`openfang.vibemind.toml:12-25`)

**Approval timeout (300s hard cap):**
- Marketing approval-gate needs 5min click-window for human review. OpenFang's MAX_TIMEOUT_SECS in `crates/openfang-types/src/approval.rs` is hard-capped at 300s. Default was 60s → operator couldn't reach approval UI in time. Rollback: remove `[approval]` block, default to 60s. (`openfang.vibemind.toml:27-35`)

**Brain-gateway agent routing decision (2026-05-29):**
- Telegram routing was hardcoded to `default_agent = "desktop"` (see `.bak-pre-brain-gateway-fix`). This bypassed Brain capability routing—openclaw browser tasks did not reach openclaw-visible. Fix: created deterministic `brain-gateway` bridge agent (base_url = `scripts/openfang_brain_gateway_wrapper.cmd`) that POSTs every Telegram message to Brain's `/api/multihop/execute` (no intermediate LLM decision). Note: no `vibemind-os/openfang/agents/brain-gateway/` directory; it's a built-in template loaded at runtime by the wrapper. (`openfang.vibemind.toml:44-58`, `.bak-pre-brain-gateway-fix` bak file)

**Desktop-automation refactor (2026-06-02):**
- Monolithic "desktop-automation" MCP server was split into 4 thin entrypoints (desktop-knowledge, desktop-document, perception, messenger) over shared library. Kept old block commented for rollback. Tool prefix collision risk: bare single-word names were too generic. Renamed to mcp_desktop-knowledge_*, mcp_desktop-document_*, mcp_perception_*, mcp_messenger_*. (`openfang.vibemind.toml:404-465`, `plans/pure-wishing-starlight.md`)

**Brain contention (2026-06-08):**
- Brain HTTP server (single-process async) starved under 6+ background loops (ContinuousThinking, Consolidation, MCMP-Gardener, ClusterEngine). Fixes: (1) moved loops to separate `brain-loops` service (BRAIN_BACKGROUND_LOOPS=0), (2) scaled HTTP from 1 to 2 uvicorn workers (BRAIN_HTTP_WORKERS=2). Single-writer constraint maintained. (`infra/swarm/vibemind-stack.yml:80-100`)

**Agent template loading:**
- OpenFang loads all `agents/{name}/agent.toml` files at startup. No dynamic hot-reload; must restart daemon to pick up new agents. Env override for default_agent takes precedence: `~/.openfang/config.toml default_agent = "brain-gateway"` can be overridden by CLI or second config file.

**MCP server lazy-loading:**
- npm/uvx servers (playwright, filesystem, context7, redis, postgres, memory, taskmanager, tavily) are NOT auto-installed. OpenFang lazy-installs on first agent use (via `npx` or `uv tool`), paying CLI startup cost (15-30s). `npm install -g` pre-install speeds up first use. (`openfang.vibemind.toml:230-381`, `VIBEMIND_INTEGRATION.md:110-136`)

**Qdrant vector DB port collision (Phase B):**
- 3-way collision before unification: automation_ui :6333, la-fungus :6339, brain host :6730 all needed their own Qdrant. Phase B Skeleton solution: single in-stack overlay service `qdrant:6333`, host-published to :6730 (same port repo .env already uses). (`infra/swarm/vibemind-stack.yml:1-15`)

**A2A protocol registration:**
- Brain bridge NOT auto-registered in A2A. Manual entry in openfang.vibemind.toml `[[a2a.external_agents]]` required. If Brain goes down, A2A communication fails silently (no fallback). (`openfang.vibemind.toml:511-517`)

**Brain multihop timeout (290s wrapper vs 360s heartbeat):**
- `openfang_brain_gateway_wrapper.py` default TIMEOUT_S = 290s (room under 360s OpenFang heartbeat). Claude Code driver's own ceiling is 300s. If Brain multihop hangs past 290s in wrapper, result returned is empty → OpenFang marks task failed. Test with `BRAIN_GATEWAY_TIMEOUT_S` env override. (`openfang_brain_gateway_wrapper.py:54`, `openfang.vibemind.toml:12-25`)

**Error-monitor RAG-dedup gap:**
- error-monitor agent filters duplicate issues via Brain.kg_search() if Brain is reachable. If Brain is down, RAG dedup skips and only hash-dedup runs, risking duplicate issues. No fallback backend. (`agents/error-monitor/agent.toml:38-39`)

**Approval bridge for marketing (spaces/marketing/workers/openfang_approval_bridge.py):**
- Telegram approval flow: bot message → approval-handler agent → POST /api/approvals → waits for click in UI → timeout 300s. If approval UI unreachable or user doesn't click, task reverts or times out silently. No retry logic.

---

## Summary of Reference

This OpenFang + Agents area is the **orchestration nerve center** of VibeMind: it aggregates 30+ MCP tools, routes Brain intents to 10+ specialized agents, handles Telegram/Discord/Slack channels, and provides the A2A protocol for inter-agent collaboration. The architecture is layered (Channel → Brain routing → OpenFang agent dispatch → MCP tool execution) with deliberate timeouts, approval gates, and fallbacks. Isolation testing requires Brain (:5000), OpenFang (:4200), Qdrant, and env API keys; most gotchas revolve around timeout tuning, heartbeat/approval windows, and lazy MCP initialization.
