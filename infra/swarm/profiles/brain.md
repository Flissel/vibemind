# Brain

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Brain area is the cognitive core of VibeMind: a production-grade routing and inference system that dispatches user intents to specialized capabilities via a radial attention network, capability registry, and multi-hop plan executor. It runs as either a monolithic service (brain-core) or a learner/inference split (Phase D) sharing a Qdrant vector DB. The autotrain-drain sidecar continuously improves the routing matrix by draining shortcut decisions from a queue. Brain-learner (phase-d, replicas:0 by default) owns all writes; brain-core in production is inference-only with no background loops (they live in brain-loops sidecar).

## Services / Components

From `infra/swarm/vibemind-stack.yml:1-1185` and `vibemind.config.json`:

**Core Brain Services (Tier-1)**
- `brain-core:5000` (Port 5000, image: vibemind-brain-core:latest, command: `python start_server.py 5000`)  
  HTTP API router. By default in stack: BRAIN_ROLE=inference, BRAIN_BACKGROUND_LOOPS=0 (no loops in HTTP process), BRAIN_HTTP_WORKERS=2, replicas:1. Depends on qdrant.  
  Healthcheck: GET /api/health, 360s start_period (cold-start load ML models).  
  Resources: 4 CPU, 6GB memory (BRAIN_HTTP_WORKERS=2 loads embedder twice).

- `brain-api:5001` (Port 5001, image: vibemind-brain-core:latest, command: `python production/api_server.py`)  
  ProductionPlanner REST API for routing-matrix training. Runs HierarchicalPlanner (/predict ~53s), provides /feedback for autotrain.  
  Healthcheck: GET /health, 90s start_period.  
  Resources: 3 CPU, 3GB memory.

- `brain-learner:5000` (Port 5000, image: vibemind-brain-core:latest, phase-d opt-in, replicas:0)  
  Learner instance (BRAIN_ROLE=learner) — single writer for centroids, Qdrant, checkpoints. No HTTP workers in this service variant; the container listens :5000 but is only called via BRAIN_LEARNER_URL by inference replicas forwarding reward/train. Cold-start 60s.

- `brain-inference:5000` (Port 5000, image: vibemind-brain-core:latest, phase-d opt-in, replicas:0)  
  Inference replicas (BRAIN_ROLE=inference, BRAIN_LEARNER_URL=http://brain-learner:5000). Read-only: forward reward/train to learner. BRAIN_CKPT_RELOAD_SECS=30 polls brain_data for learner's checkpoint saves.

**Sidecars**
- `brain-autotrain-drain` (Tier-2, replicas:1, image: vibemind-brain-core:latest, command: `sh -c "while true; do python -m production.autotrain_drain --max 20 || true; sleep 1800; done"`)  
  Drains ROUTING_AUTOTRAIN_QUEUE (/app/data/routing_autotrain_queue.jsonl) every 30 min. Calls brain-api:5001 /predict and /feedback to train shortcut routing decisions. Shares brain_data volume. No HTTP.

- `brain-loops` (Tier-2, replicas:1, image: vibemind-brain-core:latest, command: `python brain_loops_worker.py`)  
  Contention-fix (2026-06-08): runs GIL-bound background loops (ContinuousThinking, MemoryConsolidator, etc.) in own process so brain-core HTTP stays responsive. BRAIN_BACKGROUND_LOOPS=1, BRAIN_ROLE=learner (owns writer threads). No HTTP. Healthcheck via heartbeat logs.

**Shared Datastores**
- `qdrant:6333` (Tier-infra, 1 shared instance, all services via overlay DNS)  
  Vector DB for brain embedding storage. Published to host :6730 for host-bound services (legacy venv brain). Image: qdrant/qdrant (digest-pinned). 2GB RAM limit, 512MB reserved. Healthcheck via client ping.  
  Shared volume: qdrant_storage.

**Coupling Services (not in stack, host-native or separate)**
- OpenFang (host :4200, binary native service)  
  LLM agent dispatcher. Brain reaches it via OPENFANG_URL=http://host.docker.internal:4200 from stack. /api/agents lists agents (verified 2026-05-01). gRPC bridge :50051.

- Neo4j mirofish (host or separate docker service :7688 bolt for brain decision_graph writes)  
  Shared knowledge graph: Mirofish KG (Entity/Episode) + Brain's decision history (Plan/Hop/Dispatch). Brain is fail-soft if down. In stack (phase B-next): neo4j-mirofish:5.18, bolt :7688, browser :7475.

## Dependencies

**UPSTREAM (what brain needs)**
- **Qdrant:6333** (in stack, overlay DNS: `qdrant:6333`)  
  Vector DB for embeddings. Mounted at brain_data volume. Environment: QDRANT_URL (default http://qdrant:6333 in stack; dev host: http://127.0.0.1:16333).  
  See: `core/qdrant_kg.py:52` (default), `core/config.py:122-125` (getter).

- **OpenFang :4200** (host native binary, reached via host-gateway)  
  LLM planner, capabilities dispatch. Env: OPENFANG_URL=http://host.docker.internal:4200, OPENFANG_STREAM=0 (forces blocking endpoint).  
  Called by: subagent_dispatcher.py, capability_targets.py, MultiLLMRouter.

- **Supabase :54321** (host Kong, Ideas-HTTP :5102 fallback)  
  Bubble/Idea storage (canvas_nodes, bubbles). Env: SUPABASE_URL=http://host.docker.internal:54321, SUPABASE_ANON_KEY_FILE=/run/secrets/supabase_anon_key.  
  Fallback when Ideas-HTTP offline (read-path: /api/bubbles/list, /api/ideas/state).

- **Ollama :11434** (host native process)  
  Local LLM embeddings + planner fallback. Env: OLLAMA_BASE_URL=http://host.docker.internal:11434 (brain-loops for subagent_dispatcher), model pinned to llama3.1 (2026-06-01).

- **API Keys** (secrets from docker stack /run/secrets/)  
  - openrouter_api_key (for multi-LLM via OpenRouter; 402 exhausted by 2026-06-01)
  - anthropic_api_key
  - groq_api_key (Groq direct, primary after OpenRouter 402)
  - openai_api_key (fallback, gpt-4o-mini via api.openai.com, not OpenRouter)

**DOWNSTREAM (what calls brain)**
- **Router endpoints** (/api/cortex/route, /api/brain/chat)  
  Called by: bridge, spacer, voice, OpenClaw, Electron UI. Brain acts as dispatcher — all intent routing.

- **ProductionPlanner :5001** (/predict, /feedback)  
  Called by: brain-autotrain-drain (queue drain worker), bridge (when manual feedback).

- **Brain-learner :5000** (phase D reward/train forward)  
  Called by: inference replicas when BRAIN_LEARNER_URL set (D2 flow).

## Possible usages

**Direct API usage**

1. **Fast routing** (target <100ms)
   - `POST /api/cortex/route` — user_text → radial embedding → space centroid cosine similarity → space decision
   - Body: `{user_text, event_type?, context?}`
   - Returns: space routing decision, latency_ms
   - See: `web/routers/routing.py:63-130`

2. **Brain chat** (WebSocket stateful)
   - `GET /api/brain/chat` — chat endpoint (SSE or WS, GPT-4o responses colored by live brain state)
   - Multi-turn conversation with thought buffer, emotional state, neuromod gates.

3. **Reward signal** (RL training)
   - `POST /api/cortex/route/reward` — success signal for routing decision  
   - Body: `{routing_id, success: bool}`  
   - Strengthens/weakens space centroid (Hebbian).

4. **Capability registry lookup** (read-only)
   - `GET /api/capabilities` — list of regex-matched capabilities
   - Returns: capability.yaml entries with agents, execution_target.

**Voice/MCP Tools** (via capabilities.yaml)
- `bubble_evaluate`, `code_search`, `security_scan`, `incident_response`, `log_analysis`, `knowledge_query`, `email_action`, `site_check`, `chitchat`
- Routed by: capability router → difficulty_router → OpenFang agent dispatch
- See: `the_brain/data/capabilities.yaml:1-1359` (all routing patterns)

**Background training** (no API, internal loop)
- Autotrain queue drains every 30 min (brain-autotrain-drain sidecar)
- Shortcut decisions (plan_id="shortcut_*", ok=true) queued instantly by hook
- See: `core/routing_matrix_autotrain.py:95-129`, `production/autotrain_drain.py:162-219`

## MCPs & OpenFang agents involved

**MCP Servers (provide tools to Brain)**
- `vibemind-os/la-fungus-search/mcp_server.py` — fungus-search (semantic code search)
- `vibemind-os/ops/mcp/mcp_server_registry.py` — MCP registry (lists all active MCPs)
- `vibemind-os/openfang/mcp/openfang_agents_server.py` — OpenFang agent list provider

**OpenFang Agents** (verified live 2026-05-01, curl http://127.0.0.1:4200/api/agents)
- Primary dispatch agents: `brain-coder`, `fungus-search`, `poc-security-scanner`, `rowboat-knowledge`, `assistant`
- Supporting: `poc-log-analyzer`, `poc-forensics`, `sensor-monitor`, `poc-vuln-scanner`, `poc-site-verifier`, `supermemory`, `poc-email-response`, `poc-email-sender`, `poc-alerter`, `poc-secret-vault`, `poc-red-blue`
- See: `the_brain/data/capabilities.yaml:1-50` (agents.primary, agents.supporting per capability)

**Brain-OpenFang coupling**
- Brain calls OpenFang via OPENFANG_URL :4200/api/agents
- MultihopExecutor (plan_executor.py) dispatches each capability hop to OpenFang
- capability_targets.py maps capability → OpenFang agent selection
- See: `web/brain_server.py:1-50`, `core/subagent_dispatcher.py` (LLM fallback when OpenFang unavailable)

## Isolated startup

**Minimum deployment (brain area ONLY):**

Docker Stack (Swarm) — all overlay DNS, single compose deploy:
```yaml
services:
  qdrant:6333 (mandatory)
  brain-core:5000 (mandatory, BRAIN_ROLE=inference, BRAIN_BACKGROUND_LOOPS=0)
  brain-api:5001 (mandatory for /predict, /feedback)
  brain-autotrain-drain (sidecar, background)
  brain-loops (sidecar, background, BRAIN_BACKGROUND_LOOPS=1)
```

**Native process requirements** (host):
- OpenFang :4200 (must be running for capability dispatch; graceful fallback to subagent if down)
- Ollama :11434 (optional, fallback LLM if Groq/OpenAI unavailable; defaults to subagent_dispatcher paths)
- Supabase :54321 (optional read-only Ideas fallback; required for bubble_create, bubble_score, etc.)

**Environment setup** (.env or docker secrets):
```
QDRANT_URL=http://qdrant:6333        # in stack; host: http://127.0.0.1:16333
OPENFANG_URL=http://host.docker.internal:4200
OPENFANG_STREAM=0
SUPABASE_URL=http://host.docker.internal:54321
SUPABASE_ANON_KEY_FILE=/run/secrets/supabase_anon_key
OLLAMA_BASE_URL=http://host.docker.internal:11434
GROQ_API_KEY=<sk-...>
OPENAI_API_KEY=<sk-...>
ANTHROPIC_API_KEY=<sk-...>
OPENROUTER_API_KEY=<sk-...>
BRAIN_ROLE=inference               # or: mono (default), learner (phase D)
BRAIN_BACKGROUND_LOOPS=0            # brain-core; brain-loops overrides to 1
BRAIN_HTTP_WORKERS=2
ROUTING_AUTOTRAIN=1
ROUTING_AUTOTRAIN_API=http://brain-api:5001
ROUTING_AUTOTRAIN_QUEUE=/app/data/routing_autotrain_queue.jsonl
```

**Gaps / prerequisites:**
- Qdrant must be running before brain-core health probe starts (swarm depends_on: qdrant)
- OpenFang agent list must be populated before first capability dispatch; graceful fallback exists
- Supabase secrets required only if using bubble_create/score/evaluate; ideas in code default to Supabase REST
- API keys: Groq + OpenAI direct (not OpenRouter, exhausted 2026-06-01)
- Phase D split (brain-learner + brain-inference): learner and inference MUST share brain_data volume; replica scaling requires BRAIN_LEARNER_URL set on inference, learner running first

## Key files

**Routing core**
- `web/routers/routing.py:63-130` — POST /api/cortex/route (fast radial + space routing)
- `core/space_routing_head.py` — SpaceRoutingHead class (centroid cosine similarity)
- `web/brain_server.py:1-50` — FastAPI app factory, state init, async context manager
- `start_server.py:1-72` — Entry point, uvicorn runner, BRAIN_HTTP_WORKERS multi-process setup

**Capability dispatch**
- `the_brain/data/capabilities.yaml:1-1359` — regex routing registry, all 60+ capabilities
- `core/capability_targets.py` — capability → execution_target + arg extraction
- `core/plan_executor.py` — MultihopExecutor, runs plan hops via OpenFang

**Autotrain loop**
- `core/routing_matrix_autotrain.py:1-129` — Hook that queues shortcut decisions (on every multihop exec)
- `production/autotrain_drain.py:1-223` — Drain worker, calls /predict + /feedback

**Configuration & identity (Phase D)**
- `core/config.py:1-200+` — get_secret(), brain_role(), is_learner(), learner_url() (D1/D2 layer)
- `brain_loops_worker.py:1-98` — Sidecar process for background loops (BRAIN_BACKGROUND_LOOPS=1, BRAIN_ROLE=learner)

**API server (ProductionPlanner)**
- `production/api_server.py:1-80+` — Flask /predict, /feedback, /stats endpoints for routing-matrix training
- `production/production_planner.py` — HierarchicalPlanner, matrix learning

**Docker & deployment**
- `Dockerfile:1-75` — Multi-layer build, torch variant (cu121/cpu), shared package mount
- `infra/swarm/vibemind-stack.yml:1-1185` — All 4 services (brain-core/api/autotrain-drain/loops), qdrant, rowboat, mirofish stacks

## Gotchas

**Memory & CPU contention (2026-06-08 architecture fix)**
- brain-core MUST have BRAIN_BACKGROUND_LOOPS=0 (HTTP process is loop-free) → brain-loops sidecar carries the GIL-bound loops
- BRAIN_HTTP_WORKERS=2 (not more) — each worker loads embedder (~1.5GB), 2-worker cold-start 360s
- brain-api :5001 /predict is ~53s (HierarchicalPlanner) — keep max 1 replica, only call from autotrain-drain sidecar
- Qdrant initial health probe: swarm waits 60s before checking, allow 360s start_period for brain-core cold-start

**Phase D topology (learner/inference split) — opt-in, replicas:0 by default**
- DO scale brain-learner to 1 FIRST, then brain-core to 0, then brain-inference to N
- brain-learner and brain-inference MUST share brain_data volume (mtime-gated checkpoint reload, D3)
- inference replicas MUST have BRAIN_LEARNER_URL=http://brain-learner:5000 set; unset = 202 "not applied" on reward
- Single-writer invariant: brain-core writes state when mono; brain-learner when phase D

**OpenFang coupling**
- OPENFANG_STREAM=0 forces blocking /message endpoint (not SSE /message/stream) so stdout chunks surface to Brain
- OpenFang unreachable → capability dispatch falls back to subagent_dispatcher (slower, uses LLM planner only)
- Agent names must match capabilities.yaml; name rot detected at Brain startup with warnings

**Supabase fallback (Ideas-HTTP :5102 down)**
- bubble_create, bubble_evaluate, idea_add, etc. all have execution_target: "supabase:*" (2026-06-09 migration from spaces.* import)
- requires SUPABASE_ANON_KEY in /run/secrets (swarm mount) — direct REST fallback, zero spaces/ import
- if anon key missing, bubble operations fail silently (log "Bubble … not found")

**Queue durability**
- routing_autotrain_queue.jsonl is append-only; offset tracking in .offset file (atomic replace)
- if queue truncated/rotated below offset, autotrain-drain resets to 0 (rescan all lines once)
- max 20 entries per run (--max 20) to avoid long-running drain; next run resumes at new offset

**LLM routing (2026-06-01 crisis)**
- OpenRouter exhausted (402 on openai/*, anthropic/*) → no fallback to Claude via OpenRouter
- Groq direct (groq::llama-3.3-70b) primary; fallback gpt-4o-mini via OpenAI direct (api.openai.com)
- llama3.1 (Ollama host) is weak fallback (hallucinates in-context examples for ideas.create)
