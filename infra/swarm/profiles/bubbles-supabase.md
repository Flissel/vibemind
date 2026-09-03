# Bubbles / Supabase (core / immer)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Ideas/Bubbles feature is a Supabase-backed canvas-based ideation system with hierarchical containers (bubbles) holding nested ideas (nodes). Bubbles are top-level organizational spaces; ideas are the leaf nodes within them. Both live in `public.ideas` and `public.canvas_nodes` (Postgres tables in Supabase), synchronized via REST endpoints at :5102 (Ideas-HTTP, HOST-only, often offline) or direct Supabase PostgREST at :54321 (Kong proxy). Brain reads/writes via `SupabaseIdeasClient` (async REST). Voice/Electron sync via `supabase-client.js` + realtime subscriptions. Scoring is MiroFish-driven (Neo4j KG at :7688); embeddings live in Qdrant (6730/6333 overlay).

## Services / Components

**Docker Stack Services (infra/swarm/vibemind-stack.yml:1820–2388):**

| Service | Port(s) | Image | Role |
|---------|---------|-------|------|
| **supabase-db** | 5432 (internal) | postgres:17.6.1.106 | Ideas/projects/canvas Postgres DB (30GB tables: ideas, canvas_nodes, canvas_edges, projects, shuttles, exploration_sessions, flowzen_*, videos, persistent_tasks, user_preferences, conversation_*) |
| **supabase-kong** | 54321 (host) | kong:2.8.1 | HTTP gateway (auth :9000, rest :8000, realtime :8001, storage :5000) |
| **supabase-rest** | 8000 (overlay) | postgrest:v14.8 | REST API to Postgres (reads/writes public.ideas, canvas_nodes, etc. via authenticated paths) |
| **supabase-realtime** | 8001 (overlay) | realtime:v2.82.0 | WebSocket for canvas changes (Electron subscriptions) |
| **supabase-auth** | 9000 (overlay) | gotrue:v2.188.1 | JWT auth (demo credentials, anon key from secrets) |
| **supabase-storage** | 5000 (overlay) | storage-api:v1.48.28 | File uploads (bubbles/ideas attachments) |
| **supabase-pg-meta** | 8080 (overlay) | postgres-meta:v0.96.4 | Schema introspection (Studio needs this) |
| **supabase-analytics** | 4000 (overlay) | logflare:1.37.1 | Logging/analytics (_supabase DB) |
| **supabase-studio** | 3000 (overlay, published :54323) | studio:2026.04.08 | Web UI (admin console for DB inspection) |
| **supabase-inbucket** | 1025/9001 (overlay) | mailpit:v1.22.3 | SMTP/web for auth emails (dev only) |
| **qdrant** | 6730 (host), 6333 (overlay) | qdrant:latest | Vector DB (brain-* and rowboat collections; bubble embeddings) |
| **brain-core** | 5000 (host) | vibemind-brain-core:latest | Brain API (reads /api/bubbles/list, /api/ideas/state via IdeasClient.bubbles_list() + Supabase fallback) |
| **brain-loops** | (none, worker) | vibemind-brain-core:latest | Background loops (BRAIN_ROLE=learner; has SUPABASE_URL, SUPABASE_ANON_KEY for sync) |
| **mirofish** | 5101 (host), 3001 (frontend) | vibemind-mirofish-mirofish:latest | Bubble scoring engine (Neo4j KG sync; scoring via Flask @/health :5001) |
| **neo4j-mirofish** | 7688 (bolt, brain decision_graph writer), 7475 (browser :7475 host) | neo4j:5.18-community | Mirofish KG store (Entity/Episode nodes; Brain writes Plan/Hop/Dispatch) |
| **rowboat** | 3100 (host :3000) | vibemind-rowboat-rowboat:latest | Chat + knowledge management (own Qdrant "embeddings" collection) |
| **rowboat-mongo** | 27017 (127.0.0.1:27017 loopback only) | mongo:latest | Rowboat data (separate from ideas DB) |
| **rowboat-redis** | (internal) | redis:latest | Rowboat cache/queue |
| **rowboat-rag-worker** | (none, worker) | vibemind-rowboat-jobs-worker:latest | Embeddings pending data sources → Qdrant |

**Native Host Services (NOT in stack, but referenced):**

| Service | Port | Notes |
|---------|------|-------|
| **Supabase CLI** (legacy) | 54321 | Replaced by swarm supabase-kong; kept for reference on old installs |
| **OpenFang** | 4200 (HTTP API), 50051 (gRPC) | Host binary (referenced in stack via host.docker.internal:4200); routes brain dispatches to agents |
| **Ollama** | 11434 | Host LLM (mirofish LLM_BASE_URL, brain OLLAMA_BASE_URL for subagent_dispatcher) |
| **Ideas-HTTP** | 5102 | Voice service (host-bound, often offline per stack.yml line 142–145); Brain falls back to Supabase REST |

## Dependencies

**UPSTREAM (what bubbles/ideas need to exist/run):**

1. **Supabase Stack (core data layer)**
   - `supabase-db:5432` (Postgres 17.6) — table: `public.ideas` (title, description, status, score, parent_id, embedding_vector, embedding_hash, promoted_to_project_id, tags, metadata, agent_id, source, created_at). File: infra/swarm/vibemind-stack.yml:1830–1877. Env: POSTGRES_PASSWORD via secret `postgres_password` (demo: "postgres"). Init scripts at infra/swarm/supabase/initdb/*.sql.
   - `supabase-rest:8000` (PostgREST v14.8) — exposes public.ideas / public.canvas_nodes / public.canvas_edges over REST at `/rest/v1/ideas`, `/rest/v1/canvas_nodes`, `/rest/v1/canvas_edges`. Depends_on: supabase-db. File: line 1923–1947. Auth: `apikey` header (anon key from secret `supabase_anon_key`, demo JWT hardcoded line 2125).
   - `supabase-kong:54321` — HTTP router (proxies :8000/rest to PostgREST, :9000/auth to Auth, :8001/realtime). File: line 2073–2111. Config: infra/swarm/supabase/kong.yml. Depends_on: all supabase services.
   - `supabase-auth:9000` — JWT generation (GOTRUE_JWT_SECRET from secret, demo value). File: line 1878–1920.
   - `supabase-realtime:8001` — WebSocket subscriptions to canvas_nodes/canvas_edges changes. File: line 1949–1981.
   - `supabase-storage:5000` — File API (bubble attachments). File: line 1983–2013.

2. **Qdrant Vector DB (for embeddings)**
   - `qdrant:6333` (overlay DNS), `localhost:6730` (host) — Collections: `brain-*`, `rowboat-artifacts`, (bubble embeddings stored here). File: line 36–65. Volume: qdrant_storage. Env: default (no auth in demo). Used by: brain-core (QDRANT_URL), MiroFish scoring, Rowboat RAG.

3. **Neo4j (MiroFish KG for bubble scoring)**
   - `neo4j-mirofish:7687` (bolt), `7475` (browser) — Entity/Episode KG. Stores bubble metadata for scoring algorithms. File: line 943–987. Creds: NEO4J_USER/NEO4J_PASSWORD from .env or defaults (neo4j/mirofish). Heap: 2G (line 956–958). Brain writes decision_graph via bolt :7687.

4. **OpenFang + LLM stack (for routing intents to bubble tools)**
   - OpenFang :4200 (host.docker.internal:4200 from stack line 127) — routes `bubble.create`, `idea.create`, etc. intents from voice/brain to the Ideas agent. File: ~/openfang/docker-compose.yml (not in this stack, HOST-only).
   - Ollama :11434 (host.docker.internal:11434 line 155, 351) — subagent_dispatcher uses OLLAMA_BASE_URL for the planner LLM (fallback to Groq/OpenAI if available).

5. **Brain Core (:5000) — for indirect cascades**
   - Reads /api/ideas/* via IdeasClient (fallback to Supabase when Ideas-HTTP :5102 is down). File: core/ideas_client.py. Env: IDEAS_URL (default 127.0.0.1:5102), SUPABASE_URL (host.docker.internal:54321 line 141), SUPABASE_ANON_KEY (secret, line 148).

**DOWNSTREAM (what calls bubbles/ideas):**

1. **Voice / Electron UI** (vibemind-os/voice)
   - Subscribes to realtime canvas_nodes/canvas_edges changes via supabase-client.js (WebSocket to supabase-realtime:8001).
   - REST writes: POST /rest/v1/canvas_nodes (create node), POST /rest/v1/canvas_edges (connect), DELETE /rest/v1/canvas_edges/{id}.
   - Tools: spaces/ideas/tools/bubble_tools.py, idea_tools.py (register_bubble_tools, list_bubbles, create_bubble, etc. at line 319, 1517).

2. **Brain Agents (OpenFang-routed)**
   - `brain-ideas` agent (configs/agents/brain-ideas.yaml) — handles idea.* events (create, update, delete, connect, auto_link, convert_format, summarize, whitepaper, etc.).
   - `brain-bubbles` agent (configs/agents/brain-bubbles.yaml) — handles bubble.* events (list, create, enter, exit, score, promote, etc.).
   - Both route through MCP tools (vibemind-db MCP server provides db_ideas_*, db_canvas_* operations). Capabilities file: data/space_capabilities/ideas.yml (163 tools), bubbles.yml (33 tools).

3. **Rowboat Chat** (:3100)
   - Shares same Supabase (canvas_nodes are embedded in rowboat knowledge context via CDP protocol).
   - RAG worker embeds pending data-source docs into Qdrant "embeddings" collection.

4. **MiroFish Scoring Engine** (:5101, line 989–1042)
   - Reads ideas from Neo4j (Decision graph).
   - Scores bubbles using entity/episode reasoning.
   - Writes back to ideas.score in Postgres via Brain's consolidation loop.

5. **Shuttles (requirement pipeline, spaces/shuttles)**
   - Create shuttles from bubbles (idea.to_project + create_stage_shuttles in summary_tools.py:2211).
   - Stores shuttle state in public.shuttles table (bubble_id FK, stage_data JSONB).

## Possible Usages

**Capabilities:**

1. **Bubble Management** (spaces/ideas/tools/bubble_tools.py)
   - `list_bubbles()` — fetch all top-level bubbles (public.ideas WHERE status != 'archived' ORDER BY score DESC)
   - `create_bubble(title, description)` — INSERT into public.ideas, return UUID
   - `enter_bubble(bubble_name)` — set session context, route to bubble-specific agent
   - `exit_bubble()` — return to multiverse (all-bubbles) view
   - `update_bubble(bubble_name, new_title, new_description)` — UPDATE public.ideas
   - `delete_bubble(bubble_name)` — DELETE CASCADE public.ideas + all linked canvas_nodes
   - `score_bubble()` — calculate richness score (idea count + connection density) via MiroFish or LLM
   - `promote_bubble()` — create public.projects entry, link ideas → project

2. **Idea/Canvas Node Operations** (spaces/ideas/tools/idea_tools.py)
   - `list_ideas()` — fetch all canvas_nodes in current bubble
   - `create_idea(title, content, type='note')` — INSERT canvas_node
   - `update_idea(idea_name, new_content)` — UPDATE canvas_node
   - `delete_idea(idea_name)` — DELETE canvas_node (CASCADE canvas_edges)
   - `find_idea(query)` — full-text search or embedding similarity
   - `connect_ideas(idea1, idea2)` — INSERT canvas_edge (from_node_id, to_node_id, edge_type='default' or 'related')
   - `auto_link_ideas()` — generate edges via LLM (embedding similarity > threshold)
   - `generate_white_paper(start_node)` — traverse canvas graph, compose markdown
   - `format_idea_as_table()` — reformat canvas_node.content_json to structured format (table, pros_cons, hierarchy, specs, kanban, mindmap, swot, user_story, flowchart)

3. **Exploration / Discovery** (spaces/ideas/tools/exploration_tools.py)
   - `start_exploration(bubble_id, depth=4, mode='auto')` — begin inter/intra-bubble semantic link discovery, populate public.exploration_sessions + public.exploration_nodes
   - `accept_connection(connection_id)` — save discovered edge to public.discovered_edges
   - `explore_bubble_complete()` — one-shot combo: inter-bubble (other bubbles semantically related) + intra-bubble (within this bubble, generate missing edges) + AI-Scientist paper generation

4. **API Endpoints** (Brain, line 142–148 notes)
   - `GET /api/bubbles/list?limit=100` — IdeasClient.bubbles_list() → Supabase REST on canvas_nodes filtered by type='bubble' (or ideas with is_root)
   - `POST /api/bubbles/create {title, description}` — IdeasClient.bubbles_create()
   - `POST /api/ideas/state` — dump full state (all ideas + edges) for dashboard
   - `POST /api/ideas/sync_full` — re-sync Supabase ↔ Brain caches

5. **Voice Triggers** (capabilities YAML)
   - Bubble: "What bubbles do I have?", "Create a new space for X", "Enter cooking", "Go back", "Score this bubble", "Delete this"
   - Ideas: "What notes do I have here?", "Add an idea about X", "Search for X", "Connect X to Y", "Format as table", "Summarize", "Generate white paper"

6. **MCP Tools** (registry)
   - `vibemind-db` MCP server provides: `db_ideas_list`, `db_ideas_create`, `db_ideas_update`, `db_ideas_delete`, `db_canvas_nodes`, `db_canvas_edge_create`, `db_canvas_edge_delete`
   - Events routed through `brain-ideas` + `brain-bubbles` agents (OpenFang dispatch)

## MCPs & OpenFang Agents Involved

**MCP Servers:**

1. **vibemind-db** (path: unknown, tools register at capabilities scan time)
   - Provides: `db_ideas_list`, `db_ideas_create`, `db_ideas_update`, `db_ideas_delete`, `db_canvas_nodes`, `db_canvas_edge_create`, `db_canvas_edge_delete`
   - Backend: Supabase REST client (uses IdeasClient or direct httpx async calls to supabase-rest:8000)
   - Registry: data/space_capabilities/ideas.yml registry_mcp_servers (line 2337), bubbles.yml (line 1056–1058)

2. **vibemind** (likely same as vibemind-db, or separate handler)
   - Provides: `vibemind_bubbles`, `vibemind_bubble_create`, `vibemind_bubble_enter`, `vibemind_bubble_exit`, `vibemind_bubble_update`
   - Used by bubbles agent registry_events (line 1060–1106 in bubbles.yml)

**OpenFang Agents:**

1. **brain-ideas** (configs/agents/brain-ideas.yaml)
   - Handles: idea.* events (27 total: list, create, update, delete, find, connect, auto_link, format_*, summarize, whitepaper, expand, explain, explore.*, to_project, etc.)
   - Tool provider: brain-ideas agent (spaces/ideas/agents/ideas_swarm_agent.py:41–104)
   - Handoff targets: BubblesAgent (enter/exit bubble), RachelAgent (send intent)
   - Entry: Any intent mentioning "idea", "note", "connect", "link", "format", "summarize", "whitepaper", "explore"

2. **brain-bubbles** (configs/agents/brain-bubbles.yaml)
   - Handles: bubble.* events (13 total: list, create, enter, exit, find, update, delete, delete_all_except, score, evaluate, promote, current, back)
   - Tool provider: BubblesAgent (spaces/ideas/agents/bubbles_agent.py:125–178)
   - Entry: "List my bubbles", "Create bubble X", "Enter Y", "Score this", "Promote to project"

3. **RachelAgent** (spaces/ideas/agents/rachel_agent.py)
   - High-level orchestrator for complex bubble workflows
   - Sends intents through send_intent() → orchestrator
   - Maintains ConversationMemory (10-min window context_store), NotificationQueue

## Isolated Startup — What's Needed

**Minimal stack to test bubbles in isolation:**

```bash
# 1. Start Supabase tier (docker-compose -f infra/swarm/vibemind-stack.yml up)
#    Required services (depends chain):
#    - supabase-db (postgres:17.6) @ 5432
#    - supabase-auth @ 9000
#    - supabase-rest @ 8000
#    - supabase-realtime @ 8001
#    - supabase-storage @ 5000
#    - supabase-pg-meta @ 8080
#    - supabase-analytics @ 4000
#    - supabase-kong @ 54321 (host)
#    - supabase-studio @ 54323 (host, optional for UI)
#    - supabase-inbucket @ 1025/9001 (optional, for auth emails)

# 2. Start Qdrant (for embeddings)
#    - qdrant @ 6730 (host), 6333 (overlay)
#    Volume: qdrant_storage (empty on first run)

# 3. Start Brain Core (for API layer)
#    docker stack deploy -c ... (just brain-core service)
#    - brain-core @ 5000 (host)
#    - depends_on: qdrant
#    - env: SUPABASE_URL=http://host.docker.internal:54321
#    - env: SUPABASE_ANON_KEY=<from secret>
#    - mounts: brain_data:/app/data (empty on first run)

# 4. Start Voice / Electron UI (for canvas UI)
#    python -m voice.main OR Electron app
#    - connects to supabase-realtime (WebSocket)
#    - calls supabase-rest (/rest/v1/ideas, /rest/v1/canvas_nodes, /rest/v1/canvas_edges)

# 5. Start OpenFang (for routing intents to agents)
#    Host binary @ 4200
#    - loads brain-ideas.yaml + brain-bubbles.yaml
#    - dispatches bubble.*/idea.* events to MCP tools
#    - requires: qdrant (for routing embeddings), Ollama or OpenAI key (for LLM)

# 6. [OPTIONAL] Start MiroFish (:5101) + Neo4j (:7687)
#    - for bubble scoring (score_bubble invokes Neo4j KG)
#    - otherwise score_bubble falls back to LLM richness heuristic
```

**Gaps if running standalone:**

- **Ideas-HTTP (:5102)** — NOT in stack. Brain falls back to Supabase REST (line 142–145 stack.yml). No code integration needed if Supabase is up.
- **MiroFish scoring** — Optional. Bubble scoring works via LLM heuristic if Neo4j is down (graceful fallback in score_bubble: score = (idea_count * 10 + connection_density * 5) / 100).
- **Rowboat** — Separate stack. Bubbles work without it; knowledge sync is one-way (rowboat reads bubbles for context, not vice versa).
- **Shuttles / Requirement Pipeline** — Requires separate launch (spaces/shuttles service, not in swarm yet per line 2418 comment "ideas — exists as an HTTP service... but has no docker service").

## Key Files

**Core Data / Schema:**
- `infra/swarm/supabase/initdb/00-bootstrap.sql:1–151` — Bootstrap (schemas, auth, pg_net)
- `infra/swarm/supabase/initdb/01-restore.sql:3631–3880` — TABLE definitions (canvas_edges, canvas_nodes, ideas with 16+ columns)
- `infra/swarm/supabase/initdb/02-restore-internal.sql` — Internal system tables (likely empty init)

**Brain Integration:**
- `vibemind-os/brain/the_brain/core/ideas_client.py:32–200+` — IdeasClient REST wrapper (bubbles_list, bubbles_create, ideas_list, ideas_create, search, expand, etc.) with offline fallback
- `vibemind-os/brain/the_brain/core/supabase_ideas_client.py:40–` — SupabaseIdeasClient async REST for canvas_nodes/canvas_edges (used when Ideas-HTTP is down)
- `vibemind-os/brain/the_brain/core/supabase_ideas_ops.py` — Higher-level async ops (find_canvas_node_by_title, create_edge, delete_edge, list_edges)

**Space Tools:**
- `vibemind-os/spaces/ideas/tools/bubble_tools.py:35–1517` — All bubble CRUD + score + promote + evaluate_evolution (1517 lines)
- `vibemind-os/spaces/ideas/tools/idea_tools.py:144–2178` — All idea/canvas node CRUD + format + connect + auto_link + expand + explain (2178 lines)
- `vibemind-os/spaces/ideas/tools/exploration_tools.py:145–1862` — Inter/intra-bubble discovery + paper generation + coherence optimization (1862 lines)
- `vibemind-os/spaces/ideas/tools/format_dispatcher.py:163–1153` — Format conversion engine (note, table, action_list, pros_cons, hierarchy, specs, kanban, mindmap, swot, user_story, flowchart)
- `vibemind-os/spaces/ideas/tools/summary_tools.py:265–2844` — Summary + white paper + project structure extraction + requirement submission to req-orchestrator

**Agents:**
- `vibemind-os/spaces/ideas/agents/bubbles_agent.py:119–178` — BubblesAgent (stream, name, get_bubbles_agent)
- `vibemind-os/spaces/ideas/agents/ideas_agent.py:325–540` — IdeasAgent (stream, name, get_ideas_agent)
- `vibemind-os/spaces/ideas/agents/ideas_swarm_agent.py:41–104` — Factory: create_ideas_agent, get_ideas_tools
- `vibemind-os/spaces/ideas/agents/rachel_agent.py:169–406` — RachelAgent (orchestrator, send_intent, process_input)

**Capabilities / Registry:**
- `vibemind-os/data/space_capabilities/ideas.yml:1–2330` — 163 tools (scan_dirs: tools/, adapted/, agents/; registry_agent: brain-ideas; registry_mcp_servers: [vibemind-db])
- `vibemind-os/data/space_capabilities/bubbles.yml:1–1125` — 33 tools (registry_agent: brain-bubbles; registry_mcp_servers: [vibemind-db, vibemind])

**Configuration:**
- `vibemind-os/brain/the_brain/configs/agents/brain-ideas.yaml:1–22` — agent spec (events: idea.*)
- `vibemind-os/brain/the_brain/configs/agents/brain-bubbles.yaml:1–22` — agent spec (events: bubble.*)
- `infra/swarm/vibemind-stack.yml:141, 148, 258, 349, 412, 475, 1820–2388` — All Supabase + brain-core config (env vars, secrets, depends_on, volumes)

## Gotchas

1. **Ideas-HTTP (:5102) vs Supabase REST (:54321)**
   - Brain has NO hard dependency on Ideas-HTTP. Line 142–145 (stack.yml): "falls back to direct Supabase REST when Ideas-HTTP :5102 is offline (which is most of the time — that service is not in the stack)."
   - IdeasClient gracefully degrades: checks `is_online` property, returns error dict with `ok: false` if Ideas is unreachable.
   - DO NOT assume Ideas-HTTP is running. Always provide SUPABASE_URL + SUPABASE_ANON_KEY to Brain if testing bubble APIs.

2. **Supabase Demo JWT Hardcoded (line 2125–2126, stack.yml)**
   - The anon key and service-role key are hardcoded demo JWTs (NOT from .env secrets).
   - They expire 1 Jan 1970 if checked; Supabase demo mode skips expiry validation (GOTRUE_JWT_EXP not set).
   - DO NOT expose this to production. Replace with real keys from env at cutover.

3. **canvas_nodes vs ideas — Separate hierarchies**
   - `public.ideas` = top-level bubbles + leaf ideas (has parent_id FK, recursive tree).
   - `public.canvas_nodes` = visual board nodes (may link to ideas via linked_idea_id FK, but can exist independently).
   - Both are separate: you can create a canvas_node without an idea, and vice versa.
   - Score_bubble operates on canvas_node count, NOT ideas count (idea_tools.py:573, uses canvas_nodes for richness).

4. **Embedding Persistence**
   - ideas.embedding_vector (FLOAT8[]) is Postgres native array type, stored inline.
   - ideas.embedding_hash (TEXT) caches a hash of the embedding to detect stale vectors.
   - Qdrant vectors are separate (brain-* collections); DO NOT assume ideas.embedding_vector is always synced to Qdrant.
   - generate_bubble_embeddings (bubble_tools.py:1226) explicitly re-embeds and syncs to Qdrant + Postgres.

5. **Realtime Subscriptions Only for Specified Tables**
   - supabase-realtime publishes only to: ideas, projects, canvas_nodes, canvas_edges, conversation_history, scheduled_tasks, shuttles, flowzen_activity, flowzen_diary, videos, video_projects, persistent_tasks (see stack.yml line 2411–2422 ALTER PUBLICATION).
   - Other tables (user_preferences, exploration_sessions, etc.) are NOT realtime-enabled; polling required.

6. **Row-Level Security (RLS) Permissive in Demo**
   - All tables have `CREATE POLICY "allow_all_*" ON table_name FOR ALL USING (true) WITH CHECK (true)` (bootstrap.sql, line 127 ish).
   - This allows anon key to read/write EVERYTHING.
   - Production MUST replace with proper role-based policies (per user_id, project_id, etc.).

7. **MiroFish Scoring — Optional but Preferred**
   - score_bubble defaults to LLM heuristic if Neo4j is down.
   - If MiroFish is up (line 989–1042), scoring uses Neo4j KG entity/episode reasoning → more accurate but slower.
   - Neo4j is NOT in the minimal Supabase-only stack; add it for production scoring.

8. **Consolidation Loop — Slow Async**
   - The brain-loops service (line 338–387) runs background consolidation (BRAIN_CONSOLIDATION_INTERVAL_S=300 = 5 min).
   - This consolidates multiple edits into fewer Supabase writes.
   - If you hammer bubbles/ideas API, expect 5-min lag before Supabase sees consolidated result.

9. **Cascade Deletes — Destructive**
   - delete_bubble CASCADE deletes all linked canvas_nodes, canvas_edges, and discovered_edges.
   - delete_idea CASCADE deletes all canvas_edges.
   - NO soft-delete or undo. Backup your database before bulk deletes.

10. **format_* Operations — In-Place Rewrites**
    - format_idea_as_table, format_idea_as_hierarchy, etc. REPLACE the canvas_node.content_json in-place.
    - Previous format is saved to previous_content_json (single-level undo via revert_format).
    - Do NOT assume format_* is idempotent on deeply nested structures.

---

## Infrastructure Verification Checklist

```bash
# Health checks (per stack.yml healthcheck definitions):

# Supabase DB
docker exec vibemind_supabase-db pg_isready -U postgres

# Supabase REST
curl -s http://localhost:54321/rest/v1/ideas?limit=1 -H "apikey: <anon-key>" | jq .

# Qdrant
curl -s http://localhost:6730/health | jq .status

# Brain
curl http://localhost:5000/api/health

# MiroFish (optional)
curl http://localhost:5101/health

# Realtime (WebSocket, harder to test via curl; check Studio)
# → Dashboard should show live canvas_nodes updates
```
