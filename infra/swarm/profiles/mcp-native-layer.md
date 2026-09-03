# MCP-Server + Native-Support-Services

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

MCP Servers and Native Support Services form VibeMind's distributed brain-agent infrastructure. This layer bridges the Brain decision engine (Docker) to OpenFang agents (native Rust binary) and Claude Code through semantic code search. It consists of HTTP-based MCP servers for code retrieval, REST bridges for capability routing, real-time venv services for embeddings and automation, and host processes (Ollama) for local inference.

## Services / Components

### Docker Services (infra/swarm/vibemind-stack.yml)

| Service | Port | Image | Tier | Component | Purpose |
|---------|------|-------|------|-----------|---------|
| **qdrant** | 6730 (host) / 6333 (overlay) | qdrant:latest@sha256:b3063... | infra | datastore | Shared vector DB; resolves 3-way qdrant collision (automation_ui, la-fungus, brain) |
| **brain-core** | 5000 | vibemind-brain-core:latest | tier-1 | api | Brain dashboard + inference router; HTTP :5000 with 2 uvicorn workers |
| **brain-api** | 5001 | vibemind-brain-core:latest | tier-1 | api | ProductionPlanner REST API; routing matrix learner (distinct from brain-core) |
| **brain-autotrain-drain** | (no port) | vibemind-brain-core:latest | tier-2 | worker | Drains routing autotrain queue to brain-api; runs every 30min |
| **brain-loops** | (no port) | vibemind-brain-core:latest | tier-2 | worker | Background loops (ContinuousThinking, ConsolidationEngine); CPU-bound worker process |
| **media** | 9877 | nginx:alpine | infra | proxy | Static media server for video/uploads (port 80→9877) |
| **n8n** | 127.0.0.1:15678 (host loopback, E6) | vibemind-n8n:latest | space | api | Workflow engine (n8n); replaces direct n8n compose |
| **rowboat-mongo** | 127.0.0.1:27017 (host loopback) | mongo:latest@sha256:d6566... | space | datastore | Rowboat doc/conversation storage |
| **rowboat-redis** | (overlay only) | redis:latest@sha256:0c341... | space | datastore | Rowboat session/queue cache |
| **rowboat** | 3100 | vibemind-rowboat-rowboat:latest | space | frontend | Rowboat chat UI + CDP (Next.js) → :3000 → 3100 |
| **rowboat-agents** | 3101 | vibemind-rowboat-rowboat_agents:latest | space | api | Rowboat agents service (replicas: 0 — disabled; source missing) |
| **rowboat-jobs-worker** | (no port) | vibemind-rowboat-jobs-worker:latest | space | worker | Rowboat queue job processor (npm run jobs-worker) |
| **rowboat-rag-worker** | (no port) | vibemind-rowboat-jobs-worker:latest | space | worker | Rowboat data-source embedding worker (setupQdrant + rag-worker.ts loop) |
| **neo4j-mirofish** | 7475 (browser), 7688 (bolt) | neo4j:5.18-community | space | datastore | Mirofish KG + Brain decision_graph.py writes via bolt :7688 |
| **mirofish** | 5101 (api), 3001 (frontend) | vibemind-mirofish-mirofish:latest | space | api | Mirofish KG + entity/episode evaluation (Flask :5001 + Vue :3000) |
| **coding-postgres** | (overlay only) | postgres:16-alpine | space | datastore | Coding-engine app DB (coding_engine) |
| **coding-redis** | (overlay only) | redis:7-alpine | space | datastore | Coding-engine queue + cache |
| **gitea-postgres** | (overlay only) | postgres:16-alpine | space | datastore | Gitea Git server DB |
| **coding-gitea** | 3002, 2222 | gitea/gitea:1.23 | space | frontend | Self-hosted Git (port 3000→3002 due to ingress collisions) |
| **coding-vscode** | 8444 | codercom/code-server:latest | space | frontend | Browser-based VS Code (port 8443→8444) |
| **coding-egress-proxy** | (internal overlay) | vimagick/tinyproxy:latest | space | proxy | Egress firewall for coding-api/openclaude (port 8888 internal) |
| **coding-api** | 8000 | davefelix-coding-engine-api:latest | space | api | Coding engine REST API (uvicorn :8000) |
| **supabase-postgres** | (overlay) | postgres:15-alpine | infra | datastore | Supabase database |
| **supabase-kong** | 54321 (host), 8000 (overlay) | kong:3.4.1-alpine | gateway | proxy | Supabase API gateway / PostgREST relay |
| **supabase-studio** | 54323 | supabase/studio:2026.04.08 | gateway | frontend | Supabase admin dashboard |

### Native Processes (Phase 1.5 + Phase 3, vibemind-start.ps1)

| Service | Port | Type | Process | Path | Purpose |
|---------|------|------|---------|------|---------|
| **OpenFang** | 4200 | HTTP | Rust binary (`openfang.exe start`) | vibemind-os/openfang/target/release/ | Agent OS; 49+ agents (brain-coder, code-reviewer, etc.); routes Brain decisions |
| **Ollama** | 11434 | HTTP | External (external/Programs/Ollama/) | — | Host LLM inference; mirofish embeddings + planner fallback (llama3.1, nomic-embed-text) |
| **la-fungus** | 8011 | HTTP (uvicorn) | Python (shared .venv) | vibemind-os/la-fungus-search | Real-time code embeddings (Qwen3-Embedding-0.6B); upstream for MCP HTTP server |
| **fungus-mcp-http** | 8412 | HTTP/SSE (MCP) | Python (shared .venv, mcp_server.py) | vibemind-os/la-fungus-search | MCP server for Claude Code; 56k-doc index + Qwen embedder on GPU (persistent load) |
| **bridge** | 5150 | HTTP (uvicorn) | Python (shared .venv) | vibemind-os/bridge | Brain→OpenFang capability router; dispatches decisions to agents |
| **automation_backend** | 8007 | HTTP | Python (shared .venv, server.py) | vibemind-os/spaces/desktop/Automation_ui/backend | OCR automation + desktop streaming; controls desktop via click/keyboard |
| **moire_server** | 8766 | HTTP (npm start) | Node.js (MoireTracker) | vibemind-os/spaces/desktop/Automation_ui/moire_tracker | Location probe for mouse/focus tracking (Phase 4) |

### MCPs Registered (Claude Code .mcp.json)

| MCP Server | Transport | URL/Port | Started By | Purpose |
|-----------|-----------|----------|-----------|---------|
| **fungus-search** | SSE (HTTP) | http://127.0.0.1:8412/sse | Phase 3 (fungus_mcp_http) | Semantic code search; MCMP-RAG over 56k vibemind-os docs |

## Dependencies

### Upstream (what this area needs)

#### Docker Services
- **Qdrant :6333** (overlay DNS) / :6730 (host): Shared vector DB for Brain + MCP embeddings
- **.env secrets** (OPENAI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY): LLM API keys for OpenFang agents + Brain subagents
- **Docker Swarm** (infra/swarm/vibemind-stack.yml): Stack orchestration; Phase 0 preflight checks for docker + swarm active state

#### Native Processes
- **Ollama :11434** (host): LLM inference for mirofish embeddings, planner fallback (llama3.1, nomic-embed-text)
- **.venv (shared)** (.venv/Scripts/python.exe): Python 3.x runtime for la-fungus, bridge, automation_backend
- **GPU hardware** (optional): FUNGUS_DEVICE=cuda speeds fungus_mcp_http index load (~50s on GPU vs. 120s+ on CPU); NVIDIA_VISIBLE_DEVICES env controls access

#### Infrastructure
- **host.docker.internal** (docker swarm extra_hosts): Bridge from overlay containers to host services
  - brain-core, brain-api, brain-loops reach OpenFang :4200, Ollama :11434, Supabase :54321 via this gateway
- **.env configuration** (repo root): Consolidated from 9 sub-.env files; OPENFANG_URL, BRAIN_URL, OLLAMA_BASE_URL, PLANNER_MODEL centralized here

### Downstream (what calls this area)

#### Brain → Bridge → OpenFang (Capability Dispatch)
- **brain-core** (:5000): Routes intents via capabilities.yaml to Bridge :5150 (POST /bridge/route)
- **Bridge** (:5150): Dispatches to OpenFang agents matching the intent (e.g., `code_search` → fungus-search agent)
- **OpenFang** (:4200): 49+ agents answer; each agent has domain-specific tools (code-reviewer, debugger, brain-coder, etc.)
- **Flow**: User intent → Brain DiscourseEngine → capability_router → Bridge (REST /api) → OpenFang (gRPC/HTTP) → Agent response → Brain

#### Claude Code MCP Interface
- **fungus-search MCP** (:8412/sse): Claude Code fetches via SSE from persistent HTTP server
  - Tools: `fungus_search`, `fungus_search_multi`, `fungus_lookup_file`, `fungus_index_stats`, `fungus_reindex`
  - Cold-start on stdio mode (~50s per call) → persistent server mandatory

#### Frontend/Automation UIs
- **automation_backend** (:8007): Electron app + OpenFang browser agent call this for desktop control
- **Rowboat** (:3100): Calls brain-api :5001 to store conversations + evaluate bubble readiness
- **Mirofish** (:5101, :3001): Neo4j :7688 (bolt) receives Brain decision_graph writes; KG-backed evaluation

#### Data Pipeline
- **rowboat-rag-worker**: Pulls pending data sources from rowboat-mongo → embeds via Qwen (mcp_server process via qdrant :6333)
- **brain-loops**: Continuous consolidation writes to brain_data volume (shared with brain-core/api)

## Possible Usages

### Voice-Triggered Intent → Brain Decision → OpenFang Execution
**Flow**: "Review my code for security" (voice) → Electron app sends to Brain :5000 → capabilities.yaml matches `security_scan` → Bridge dispatches to `poc-security-scanner` agent in OpenFang → OpenFang calls MCP tools (fungus-search for code, etc.) → Agent writes result back → voice response

**Endpoints**:
- Brain: POST /api/message (WebSocket chat or HTTP)
- Bridge: POST /bridge/route (capability routing)
- OpenFang: POST /api/agents/{id}/message (agent execution)

### Interactive Code Search (Claude Code Session)
**Flow**: "Where is the authentication code?" → Claude Code calls fungus-search MCP (:8412/sse) → mcp_server.py queries qdrant for Qwen embeddings of the codebase → returns ranked file chunks

**MCP Tools**:
- `fungus_search(query, top_k=5)`: Semantic search
- `fungus_search_multi(queries)`: Batch search + merge
- `fungus_lookup_file(file_path)`: All chunks from a file
- `fungus_index_stats`: Show index metadata

### Desktop Automation via Moire + Automation UI
**Flow**: Workflow node in automation_backend → click/type actions → moire_server (:8766) tracks focus → OCR via Tesseract/EasyOCR → results back to UI

**Endpoints**:
- automation_backend :8007/api/health, /api/v1/*, /api/automation/*, /api/workflows/*
- Electron app (Tauri): Communicates with automation_backend over HTTP

### Routing Matrix Auto-Training
**Flow**: Brain hook writes trusted shortcuts to brain_data/routing_autotrain_queue.jsonl → brain-autotrain-drain polls (:30min) → POSTs to brain-api :5001/train/autotrain → ProductionPlanner updates routing matrix

**Endpoints**:
- brain-api :5001/health, /train/autotrain (PUT)

### Vector Search Infrastructure
**Queries** (all route to Qdrant :6333 overlay DNS):
- Brain embedding: ConsolidationEngine writes 384-dim embeddings → qdrant brain-* collection
- Fungus indexing: mcp_server.py queries Qdrant for Qwen embeddings (1536-dim) → top-k code chunks
- Rowboat embeddings: rag-worker writes text-embedding-3-small → qdrant embeddings collection

## MCPs & OpenFang Agents Involved

### MCP Servers
- **fungus-search** (.mcp.json, Python): Semantic code retrieval via MCMP-RAG + Qwen embeddings
  - Runs persistent on :8412 (HTTP/SSE); Claude Code connects via .mcp.json `type: sse`
  - Loads 56k vibemind-os index + embedder ONCE on GPU → no cold-starts on Claude tool calls
  - Excludes: .git, __pycache__, node_modules, .venv, target, .next, .fungus_cache, old Coding_engine, _archive

### OpenFang Agents (vibemind-os/openfang/agents/)
**21 Domain Agents** registered in OpenFang :4200/api/agents:
- `brain-coder` (primary for code generation, debugging)
- `brain-security` (security scanning)
- `brain-researcher` (research, fact-finding)
- `brain-planner` (planning, task breakdown)
- `fungus-search` (code retrieval — agent, NOT MCP)
- `code-reviewer` (code review)
- `debugger` (error diagnosis)
- `poc-security-scanner` (security audit)
- `data-scientist` (data analysis)
- `brain-writer`, `brain-forecaster`, `brain-monitor`, `brain-scheduler`, etc.

**Capability Routing** (capabilities.yaml, Brain :5000):
- `code_search` → primary: [fungus-search], supporting: [brain-coder, rowboat-knowledge]
- `bubble_evaluate` → direct execution (Supabase :54321 REST, no dispatch)
- `security_scan` → primary: [poc-security-scanner], supporting: [brain-security]
- `coding_task` → primary: [brain-coder], supporting: [code-reviewer, debugger]

## Isolated Startup

To test this area ALONE (MCP Servers + Native Support Services), **without the full Vibemind stack**:

### Minimal Docker Services (Phase 1 only)
```powershell
# Start ONLY the core infra (qdrant, Brain, Supabase)
docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind \
  --filter "NOT spaces" --filter "tier=infra,tier=tier-1"
# OR: use ConvertTo-FilteredStack with Spaces=""

# Verify:
docker service ls
# Expected: qdrant, brain-core, brain-api, brain-loops, supabase-*
```

### Native Processes (Phase 1.5 + Phase 3)
```powershell
# Full venv startup
.\scripts\vibemind-start.ps1 -SkipNode -SkipElectron -Spaces ""
# Phases: 0 (preflight), 0.5 (Ollama), 1 (stack), 1.5 (OpenFang), 3 (venv services)
# Skipped: Phase 4 (moire), Phase 5 (Electron)

# OR: Minimal manual startup
# 1. Ollama (host)
$env:OLLAMA_BASE_URL = "http://localhost:11434"
ollama serve

# 2. OpenFang (native binary)
cd vibemind-os\openfang
target\release\openfang.exe start

# 3. venv services (shared .venv)
# a. la-fungus (upstream for MCP)
python -m uvicorn embeddinggemma.realtime.server:app --port 8011

# b. fungus-mcp-http (MCP on :8412)
cd vibemind-os\la-fungus-search
$env:FUNGUS_DEVICE = "cuda"
$env:FUNGUS_CODEBASE = "c:\Users\User\Desktop\Vibemind_V1\vibemind-os"
python mcp_server.py --http 8412

# c. Bridge (:5150)
cd vibemind-os\bridge
python -m uvicorn bridge.main:app --port 5150

# d. automation_backend (:8007)
cd vibemind-os\spaces\desktop\Automation_ui\backend
python server.py
```

### Health Checks (Isolated)
```powershell
# Docker
curl http://localhost:6730/health             # Qdrant
curl http://localhost:5000/api/health         # Brain
curl http://localhost:5001/health             # Brain-API

# Native
curl http://localhost:11434/api/version       # Ollama
curl http://localhost:4200/api/health         # OpenFang
curl http://localhost:8011/health             # la-fungus (GET /)
curl http://localhost:8412/sse                # fungus-mcp (SSE endpoint)
curl http://localhost:5150/bridge/health      # Bridge
curl http://localhost:8007/api/health         # Automation UI
```

### Gap: What Still Depends on Full Stack
- **Rowboat** (`:3100`, `:3101` agents): Needs rowboat-mongo, rowboat-redis
- **Mirofish** (`:5101`, `:3001`): Needs neo4j-mirofish :7688 (Bolt)
- **n8n** (`:15678`): Standalone but not essential for core Brain-Bridge-OpenFang flow

## Key Files

| File | Line/Section | Purpose |
|------|--------------|---------|
| `infra/swarm/vibemind-stack.yml` | 1–66 | Qdrant service + digest pinning |
| `infra/swarm/vibemind-stack.yml` | 68–240 | brain-core (5 workers, BRAIN_BACKGROUND_LOOPS=0) |
| `infra/swarm/vibemind-stack.yml` | 242–294 | brain-api :5001 (ProductionPlanner) |
| `infra/swarm/vibemind-stack.yml` | 332–387 | brain-loops worker (background loops enabled) |
| `scripts/vibemind-start.ps1` | 1–75 | Launcher params (SkipVenv, SkipNode, SkipElectron, Spaces) |
| `scripts/vibemind-start.ps1` | 243–311 | Phase 1.5: OpenFang + Minibook native start |
| `scripts/vibemind-start.ps1` | 321–425 | Phase 3: venv services (la_fungus, fungus_mcp_http, bridge, automation_backend) |
| `.mcp.json` | 1–10 | fungus-search SSE registration for Claude Code |
| `vibemind-os/la-fungus-search/mcp_server.py` | 1–60 | MCP server entry; lazy-load retriever; FUNGUS_CODEBASE, FUNGUS_DEVICE, FUNGUS_EMBED_MODEL env |
| `vibemind-os/bridge/src/bridge/main.py` | 1–62 | Bridge FastAPI app; routes /bridge/route to OpenFang |
| `vibemind-os/openfang/CLAUDE.md` | 1–124 | OpenFang build, test, API endpoints, gotchas |
| `vibemind-os/openfang/agents/*/agent.toml` | — | 49+ agent definitions (brain-coder, code-reviewer, etc.) |
| `vibemind-os/brain/the_brain/data/capabilities.yaml` | 1–300+ | Capability registry (intent → agent mapping); validators; feedback loops |
| `.env` | 50–80 | OPENFANG_URL=:4200, OPENFANG_GRPC_URL=:50051, BRAIN_URL=:5000, OLLAMA_BASE_URL=:11434 |
| `vibemind.config.json` | 3–105 | Module paths, ports, docker compose files (reference; launcher uses .mcp.json) |

## Gotchas

### MCP Server Cold-Start (feedback_fungus_index_corruption)
- **Problem**: Stdio-mode MCP spawns a fresh process per Claude tool call → 50s index+embedder load per call → unusable
- **Solution**: Persistent HTTP server on :8412 (Phase 3: fungus_mcp_http) loads Qwen embedder ONCE on GPU, stays up
- **Symptom**: "SSE Unable to connect :8412" → process crashed or wasn't started; check scripts/logs/la_fungus/mcp_http.log

### Brain BACKGROUND_LOOPS Contention (2026-06-08)
- **Problem**: brain-core had BRAIN_BACKGROUND_LOOPS=1 (default) → 6+ background processes (ContinuousThinking, Consolidation, MCMP-Gardener, DBSCAN) all GIL-bound the async HTTP server → CPU 100%, HTTP timeouts
- **Solution**: BRAIN_BACKGROUND_LOOPS=0 in brain-core; separate brain-loops service (BRAIN_BACKGROUND_LOOPS=1, BRAIN_ROLE=learner) in own process
- **Verify**: brain-core responds in <2s; brain-loops runs CPU-bound without blocking HTTP

### Brain HTTP Workers (2026-06-09)
- **Problem**: Single uvicorn worker stalls on blocking Qwen embed (~10s) + Qdrant queries → all requests queued
- **Solution**: BRAIN_HTTP_WORKERS=2 (default now :1→2); each worker loads ~1.5GB ML models; container limit 6G total
- **Symptom**: Brain :5000/api/health timeout → increase brain-core memory limits or worker count

### Qdrant :6333 vs :6730 Port Collision
- **Problem**: automation_ui :6333, la-fungus :6339, brain :6730 all wanted private qdrant instances
- **Solution**: Single shared Qdrant :6333 on overlay; host publishes :6730 for backward compat with .env QDRANT_URL=...:6730
- **Config**: vibemind-stack.yml line 46: `- "6730:6333"` (host:container mapping)

### host.docker.internal Route (2026-06-01)
- **Problem**: brain-core inside overlay container tried localhost:11434 (Ollama) → loop to container itself
- **Solution**: extra_hosts: `host.docker.internal:host-gateway`; OLLAMA_BASE_URL=http://host.docker.internal:11434
- **Applies to**: OPENFANG_URL, SUPABASE_URL, OLLAMA_BASE_URL (all reach host services via this)

### Supabase PostgREST Anonymous Access (2026-06-02)
- **Problem**: Brain Dashboard fallback read-path (/api/bubbles/list) needed Supabase when Ideas-HTTP :5102 offline
- **Solution**: SUPABASE_ANON_KEY_FILE=/run/secrets/supabase_anon_key; config.get_secret() reads it
- **Not hardcoded**: Real secrets stay out of .env; swarm secrets load via /run/secrets/<name>

### OpenFang Capability Registry Rot (2026-05-01)
- **Problem**: capabilities.yaml lists agents no longer in OpenFang → dispatch fails silently
- **Mitigation**: Brain startup queries OpenFang :4200/api/agents and warns on missing names
- **Recovery**: Update capabilities.yaml agents.primary list to match curl http://127.0.0.1:4200/api/agents output

### Phase 3 venv Service Startup Order
- **Order matters**: la_fungus (:8011) must be ready before fungus_mcp_http (it's the upstream)
- **Defaults**: Launcher Phase 3 loop starts services in table order; auto-waits for port to be free (Test-PortFree)
- **Fallback**: If workdir missing (e.g., la-fungus not checked out), service is skipped with warn

### Electron ELECTRON_RUN_AS_NODE Side-Effect (Phase 5)
- **Problem**: Claude Code IDE sets ELECTRON_RUN_AS_NODE=1 → Electron child process rejects --remote-debugging-port (gdb flag)
- **Solution**: Phase 5 (vibemind-start.ps1:495) clears it via `cmd /c set VAR=&` before spawning Electron
- **Apply only**: If running from Claude Code IDE; normal launcher has no ELECTRON_RUN_AS_NODE set

### brain-api :5001 NOT in Phase 3 (Critical)
- **Why excluded**: Stack owns brain-api; starting it natively would port-conflict and override swarm's :5001 → routing matrix reads would hit wrong instance
- **Guarantee**: Code form (Phase 3 table, vibemind-start.ps1:314–319) has no flag to enable it; bug cannot be re-introduced
- **If you need native brain-api**: Disable stack brain-api (docker service scale vibemind_brain-api=0) and start manually

---

**This document is maintained for Phase B2+ (2026-06). For Phase updates (Supabase re-org, rowboat Agents removal, coding-engine Phase 2), update the stack file and re-run launcher. See memory project_routing_matrix_autotrain, feedback_fungus_index_corruption, and tasks/gaps.md for ongoing issues.**
