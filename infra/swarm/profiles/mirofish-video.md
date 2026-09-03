# MiroFish + Video / Media

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

MiroFish + Video/Media is a two-part subsystem within VibeMind: (1) MiroFish is an idea-scoring knowledge graph engine (Neo4j + Flask API on :5101/:5001) that models simulation scenarios and agents across platforms (Twitter, Reddit), with embeddings and LLM reasoning integrated via host Ollama; (2) Video/Media is a lightweight nginx-based static server (:9877) that serves video/audio assets from Rowboat's uploads volume, with support for streaming ranges, CORS, and multiple formats. Both are integrated into the publishing pipeline (vibemind-os/voice/python/publishing) and the Brain's decision history (Neo4j bolt :7688 shared with MiroFish).

## Services / Components

### Docker Swarm Stack Services (from infra/swarm/vibemind-stack.yml)

#### MiroFish Area
- **neo4j-mirofish** (Neo4j 5.18-community)
  - Port 7475 (Browser UI)
  - Port 7688 (Bolt — shared with Brain decision_graph.py)
  - Environment: NEO4J_AUTH, heap/pagecache tuning for restore (2G heap, 1G pagecache)
  - Volume: neo4j_mirofish_data, neo4j_mirofish_plugins
  - Resource: 2 CPU / 4G memory limit (2026-06-03 note: 3114 nodes preserved on migration)

- **mirofish** (vibemind-mirofish-mirofish:latest)
  - Port 5101:5001 (Flask backend API)
  - Port 3001:3000 (Vue.js frontend)
  - Environment: NEO4J_URI=bolt://neo4j-mirofish:7687, LLM_BASE_URL=http://host.docker.internal:11434/v1, EMBEDDING_BASE_URL (host Ollama), LLM_MODEL_NAME (default llama3.1:latest)
  - Extra hosts: host.docker.internal:host-gateway (reaches host Ollama :11434)
  - Resource: 2 CPU / 2G memory limit
  - Depends on: neo4j-mirofish healthy

#### Media Area
- **media** (nginx:alpine)
  - Port 9877:80 (HTTP static server)
  - Volume: rowboat-videos:/usr/share/nginx/html:ro (read-only mount)
  - Config: nginx_media_conf_v2 (infra/swarm contains /spaces/video/nginx-media.conf)
  - Healthcheck: wget http://127.0.0.1/health (IPv4 explicit, not localhost — 2026-05-28 fix for IPv6 fallback)
  - Resource: 0.5 CPU / 256M memory limit
  - Labels: vibemind.space: "video"

#### Related Core Services (shared dependencies)
- **qdrant** (qdrant:latest@sha256:...)
  - Port 6730:6333 (shared vector DB for Brain + Rowboat + all spaces)
  - Volume: qdrant_storage
  - Used by: Brain, Brain-loops, Rowboat RAG-worker, MirofishKGSync (read mirofish-kg collection)

- **brain-core** (vibemind-brain-core:latest, inference role)
  - Port 5000 (HTTP API)
  - Env: QDRANT_URL=http://qdrant:6333, DECISION_GRAPH_NEO4J_URI=bolt://127.0.0.1:7688 (host, not overlay)
  - Writes to neo4j-mirofish via decision_graph.py (Plan/Hop/Dispatch history)
  - Reads MiroFish KG via MirofishKGSync worker thread (5 min tick)

- **brain-api** (ProductionPlanner REST, port 5001)
- **brain-loops** (background loops + learner role, feeds MirofishKGSync)

#### Rowboat Services (knowledge base publisher)
- **rowboat-mongo** (mongo:latest@..., port 127.0.0.1:27017)
- **rowboat-redis** (redis:latest@..., no publish port)
- **rowboat** (vibemind-rowboat-rowboat:latest, port 3100:3000)
- **rowboat-jobs-worker** (jobs-worker npm run)
- **rowboat-rag-worker** (setupQdrant + rag-worker, embeds data-source docs to Qdrant collection `embeddings`)

## Dependencies

### Upstream (what MiroFish + Video/Media need)

#### Required Always-Up
- **neo4j-mirofish** (Bolt :7688): MiroFish backend cannot start without NEO4J_URI connectivity validation (Config.validate() at boot, infra/swarm/vibemind-stack.yml:1005)
- **host Ollama** (:11434): MiroFish LLM_BASE_URL and embeddings point here; gracefully degrades on timeout (infra/swarm/vibemind-stack.yml:1012, marked extra_hosts)
- **Qdrant** (port 6730 overlay, :6333 internal): Brain's MirofishKGSync reads here; publishing pipeline may write to mirofish-kg collection

#### Conditional (fail-soft)
- **Rowboat** (Port 3100 + :27017 Mongo + :6379 Redis): Publishing pipeline (voice/python/publishing/mirofish_publisher.py:34-44) tries to create RowboatMongoPublisher; if MongoDB unavailable, falls back to IdeasPublisher (filesystem)
- **Brain API** (:5001): Routing autotrain feedback loop; MiroFish projects appear as capabilities in capabilities.yaml

### Downstream (what depends on this area)

#### Direct Consumers
- **Brain Router** (core/capabilities.yaml): bubble_evaluate capability → supabase:bubble.evaluate; mirofish_publisher writes project metadata that Brain's DiscourseEngine can route to
- **OpenFang Agents**: bubble-evaluate → feedback loop agents (brain-coder, fungus-search, poc-security-scanner, rowboat-knowledge) receive MiroFish project scores
- **Publishing Pipeline** (voice/python/publishing/__init__.py:38, mirofish_publisher.py): get_mirofish_publisher() → reads HTTP API (:5001), publishes to Rowboat MongoDB or filesystem
- **Video Gallery** (rowboat UI at :3100): queries rowboat-videos volume for playback

#### Network Topology
- **Overlay network** vibemind-shared: brain-core, neo4j-mirofish, mirofish, qdrant all on this network
- **Brain ↔ MiroFish**: Brain writes decision_graph to neo4j-mirofish (bolt://127.0.0.1:7688 ENV in container, host Bolt forwarded 7688:7687), reads via MirofishKGSync from Qdrant collection mirofish-kg
- **Mirofish ↔ Ollama**: host.docker.internal:11434 (extra_hosts, host-gateway mapping)
- **Media ↔ Rowboat**: rowboat-videos named volume (shared, no network call)

## Possible usages

### MiroFish (HTTP API on :5101, frontend on :3001)

#### Via Web Browser
- Navigate to http://localhost:3001 (Vue frontend)
- View knowledge graph visualization (Neo4j data)
- Create/edit simulation projects
- Run OASIS simulations (Twitter/Reddit agent platforms)

#### Via HTTP API (:5001)
- **GET /api/projects** — list all projects
- **POST /api/projects** — create new project
- **GET /api/projects/{id}/report** — generate agent simulation report (report_agent.py, reads from Neo4j, uses LLM)
- **POST /api/simulation** — run simulation (simulation_runner.py delegates to simulation_manager + IPC)
- **GET /api/graph** — query graph subgraph (cypher search)
- **GET /api/status** — service health (health endpoint 5001/health)

#### Voice/Publishing Trigger
- `publishing.get_mirofish_publisher().publish_project(project_dict)` (voice/python/publishing/mirofish_publisher.py:60-100)
  - Calls mirofish_tools.list_projects() (imports from spaces.mirofish.tools.mirofish_tools — CURRENTLY MISSING, returns None on ImportError)
  - On success: writes mirofish project metadata to Rowboat MongoDB collection `rowboat` → RAG worker embeds and indexes
  - Metadata includes: project ID, node/edge counts, status, score

#### Brain Dispatch (capabilities.yaml)
- No direct capability routing to MiroFish yet
- Decision graph writes to neo4j-mirofish (Plan/Hop/Dispatch nodes), which Mirofish frontend could visualize

### Video/Media (:9877)

#### Via nginx Server
- **GET http://localhost:9877/{filename}** — stream video/audio files
  - Supports Range requests for seeking (Accept-Ranges: bytes, Content-Range headers)
  - CORS enabled for BrowserView / Electron cross-origin access
  - Formats: .mp4, .webm, .avi, .mov, .wav, .mp3, .png, .jpg
- **GET http://localhost:9877/health** — healthcheck endpoint (returns 200 'ok')

#### Integration Points
- **Video Gallery** (rowboat :3100): displays videos from rowboat-videos volume
- **Video Production Pipeline** (vibemind-os/spaces/video/tools/video_tools.py): generates video files → written to ~/.rowboat/Videos → migrated to rowboat-videos volume on first-time setup
  - team_run_step(step) — run team video pipeline (analyze, backgrounds, composite, build, split, final)
  - vision_generate() — generate Sora AI vision video
  - demo_analyze() / demo_build() — screenrecording demo video
  - faceswap_batch() — face-swap deepfake (vibevideo_deepfake)

#### File Volume
- Source: ~/.rowboat/Videos/ (host, developer machine)
- Container volume: rowboat-videos (Docker named volume)
- First-time migration: `docker compose -f docker-compose.media.yml run --rm migrate` (copies ~/.rowboat/Videos → volume)

## MCPs & OpenFang agents involved

### MCP Servers
- **No native MCP for MiroFish** — mirofish_tools.py (spaces.mirofish.tools.mirofish_tools) does not exist in repo yet; references in publishing pipeline (voice/python/publishing/mirofish_publisher.py:34, ideas_publisher.py) are ImportError-safe (try/except, fail gracefully)
- **Qdrant MCP** (future): MirofishKGSync could integrate with Qdrant MCP for direct collection reads
- **Brain MCP tools**: decision_graph writes are internal (no MCP layer); Neo4j bolt protocol direct

### OpenFang Agents
- **bubble-evaluate feedback loop** (capabilities.yaml:55-57):
  - Primary: (none specified for mirofish directly)
  - Supporting: brain-coder, fungus-search, poc-security-scanner, rowboat-knowledge
  - Called after bubble readiness eval to synthesize recommendations

- **brain-video** agent (openfang/agents/brain-video/): could integrate video tools (infra/swarm/vibemind-stack.yml has no brain-video capability route yet; currently listed as available agent but no routing rule)

### Publishing Pipeline MCPs
- **rowboat_mongo_publisher** (voice/python/publishing/rowboat_mongo_publisher.py): writes to Rowboat MongoDB directly (no MCP, direct pymongo)
- **mirofish_publisher** (voice/python/publishing/mirofish_publisher.py): tries HTTP API calls via mirofish_tools (ImportError fallback)

## Isolated startup

To test MiroFish + Video/Media in isolation, you need:

### Minimal Docker Stack (docker stack deploy)
```
docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind
  (includes: qdrant, neo4j-mirofish, mirofish, media)
+ optionally: rowboat, rowboat-mongo, rowboat-redis, rowboat-rag-worker
  (for publishing pipeline integration)
```

### Host Native Processes
- **Ollama** (:11434) — REQUIRED for MiroFish LLM/embeddings
  - Ensure models are pulled: `ollama pull llama3.1:latest` (mirofish LLM_MODEL_NAME default)
  - Ensure embedding model: `ollama pull nomic-embed-text:latest` (EMBEDDING_MODEL default in swarm stack line 1011, docker-compose.mirofish.yml line 31)
  - Swarm stack has extra_hosts mapping to reach it from containers

### Environment Variables (.env or docker stack config)
- **Required for MiroFish**:
  - MIROFISH_NEO4J_USER=neo4j (default)
  - MIROFISH_NEO4J_PASSWORD=mirofish (default)
  - LLM_BASE_URL=http://host.docker.internal:11434/v1 (stack default, line 1009)
  - LLM_MODEL_NAME=llama3.1:latest (default, line 1010)
  - EMBEDDING_MODEL=nomic-embed-text:latest (default, line 1011)

- **Required for Media** (none, nginx is self-contained)

- **Optional for Publishing**:
  - OPENAI_API_KEY (for rowboat fallback if Ollama unavailable)

### MCPs / Extra Services (optional)
- **No MCP servers strictly required** (mirofish_tools.py missing, publishing pipeline is fire-and-forget)
- **Desktop Automation MCP** (if running Brain's full DiscourseEngine): enables Telegram bot routing to OpenFang agents (currently commented out in capabilities.yaml feedback_loop, phase 11.U.H note)

### Known Gaps
1. **mirofish_tools.py missing**: spaces.mirofish.tools.mirofish_tools does not exist; publishing pipeline references are ImportError-safe but the tool layer is stubbed (voice/python/publishing/mirofish_publisher.py:34-44 try/except)
2. **Video tools import path unclear**: video_tools.py exists (spaces/video/tools/video_tools.py) but no corresponding MCP or OpenFang agent routing to invoke it
3. **No Brain → MiroFish routing**: capabilities.yaml has no capability that routes to mirofish_publisher or mirofish HTTP API; only one-way (publishing pipeline → Rowboat)
4. **decision_graph depends on host Neo4j**: Phase 8.B connects to bolt://127.0.0.1:7688 from INSIDE brain-core container, but Brain explicitly doesn't join the overlay DNS overlay (DECISION_GRAPH_NEO4J_URI env is hardcoded to host, not to overlay neo4j-mirofish:7687 DNS)

## Key files

### MiroFish
- **infra/swarm/vibemind-stack.yml:932-1042** — Docker Swarm service definitions (neo4j-mirofish, mirofish)
- **vibemind-os/voice/docker-compose.mirofish.yml** — Standalone compose (dev/test), mirrors swarm config
- **vibemind-os/spaces/mirofish/mirofish/backend/app/config.py:27-89** — Flask config, LLM/Neo4j validation
- **vibemind-os/spaces/mirofish/mirofish/backend/app/storage/neo4j_storage.py** — Neo4j Cypher queries (Entity/Episode/Simulation nodes)
- **vibemind-os/spaces/mirofish/mirofish/backend/app/services/simulation_runner.py** — OASIS simulation executor
- **vibemind-os/brain/the_brain/core/decision_graph.py:1-80** — Neo4j-backed decision history (Cluster/Thought/Plan/Hop/Dispatch nodes, writes to :7688)
- **vibemind-os/brain/the_brain/core/mirofish_kg_sync.py:1-80** — Periodic sync of Neo4j mirofish-kg collection into Brain's Qdrant
- **vibemind-os/voice/python/publishing/mirofish_publisher.py** — Publishing pipeline integration (HTTP API → Rowboat MongoDB)
- **vibemind-os/voice/python/publishing/__init__.py:58-74** — get_mirofish_publisher() singleton factory

### Media / Video
- **infra/swarm/vibemind-stack.yml:530-574** — Docker Swarm media service definition
- **vibemind-os/spaces/video/docker-compose.media.yml** — Standalone compose (dev/test)
- **vibemind-os/spaces/video/nginx-media.conf** — nginx config (CORS, range requests, MIME types)
- **vibemind-os/spaces/video/tools/video_tools.py:1-100** — Video production CLI wrappers (team_pipeline_status, team_run_step, vision_generate, demo_analyze/build, faceswap_batch)
- **vibemind-os/spaces/video/vibevideo/** — Team video pipeline (analyze, backgrounds, composite, split, build, final steps)
- **vibemind-os/spaces/video/vibevideo_deepfake/** — Face-swap + lipsync modules (faceswap, lipsync, voice)

### Capabilities & Routing
- **vibemind-os/brain/the_brain/data/capabilities.yaml:1-150** — Brain router capability registry (no mirofish_* capabilities yet; bubble_evaluate feedback loop includes rowboat-knowledge agent)
- **vibemind.config.json:60, 76** — Port mapping (mirofish: 5101, media_server: 8977)

### Publishing Pipeline
- **vibemind-os/voice/python/publishing/__init__.py:15-45** — Publishing module registry, MongoDB vs filesystem fallback
- **vibemind-os/voice/python/publishing/config.py** — Publishing env checks (is_publishing_enabled, is_mongo_enabled)
- **vibemind-os/voice/python/publishing/rowboat_mongo_publisher.py** — Direct Mongo writer (schema semaphore validation)

## Gotchas

### MiroFish-Specific
1. **Config.validate() at boot** (backend/app/config.py:80-89): MiroFish exits 1 if LLM_API_KEY or NEO4J_URI/PASSWORD are unset; the stack has LLM_API_KEY=ollama (placeholder), not a real key. If Ollama is not running, the startup health check (:5001/health) times out → Swarm kills → container 0/1. Verify `ollama serve` is running on host :11434 before bringing up the stack.

2. **Neo4j heap overflow on restore** (stack comment, line 951-955): 29MB cypher dump in one transaction → default 512M heap OOM. Swarm stack sets 2G heap explicitly (NEO4J_server_memory_heap_max__size). If you restore from backup manually without this, increase heap first or split the dump into smaller transactions.

3. **mirofish_tools.py missing** (voice/python/publishing/mirofish_publisher.py:34): The import `from spaces.mirofish.tools.mirofish_tools import list_projects` will raise ImportError on current checkout. Publishing gracefully degrades (try/except, returns None), but the tool layer is stubbed. To enable MiroFish → Rowboat publishing, implement mirofish_tools.py with HTTP API wrappers.

4. **LLM model availability**: MIROFISH_LLM_MODEL=llama3.1:latest assumes the model is pulled locally. If you change the default or add a new model, run `ollama pull <model>` on the host first. Fallback to OpenAI API requires OPENAI_API_KEY secret (not yet in stack).

5. **Decision graph NEO4J_URI hardcoded to host** (brain/the_brain/core/decision_graph.py:46): Brain connects to bolt://127.0.0.1:7688 (host, not overlay DNS neo4j-mirofish:7687). This works because Swarm stack publishes neo4j-mirofish port 7688:7687 to the host, and Brain runs with extra_hosts: host.docker.internal. However, the design is fragile — if Brain is ever containerized, the bolt connection fails. Phase 8.B TODO: switch to overlay DNS once Brain runs in-stack.

### Media-Specific
1. **Healthcheck IPv6 fallback** (stack line 552-554, nginx-media.conf flow): busybox-wget in nginx:alpine prefers IPv6 [::1] if localhost is not explicitly IPv4 (127.0.0.1). The earlier healthcheck used `localhost` → permanent 0/1 until start_period expired (2026-05-28 debug). Solution: use `http://127.0.0.1` explicitly, not localhost.

2. **rowboat-videos volume must exist**: If this named volume is missing, the media container binds an empty volume. The first-time migration command `docker compose -f docker-compose.media.yml run --rm migrate` copies ~/.rowboat/Videos into the volume. If ~/.rowboat/Videos does not exist, the migration silently does nothing (`cp -a ... || true`). Populate videos manually or run team_run_step() to generate them.

3. **nginx MIME types incomplete**: nginx-media.conf lists common video formats but may not cover all. If a file type returns 404 or application/octet-stream, add it to the types block. Default type is application/octet-stream (browser downloads instead of playing).

4. **No authentication**: Media server (:9877) has no auth; CORS is fully open (Access-Control-Allow-Origin: *). This is fine for dev/local; for production, add reverse proxy auth (nginx upstream, API gateway).

### Shared Integrations
1. **Qdrant collection collision** (stack comment, line 629-633): Brain uses `brain-*` collections, Rowboat uses `embeddings`, MirofishKGSync uses `mirofish-kg`. No collision today, but if collections are auto-created with overlapping names, one can shadow the other. Manually verify collections via Qdrant HTTP :6730 before going to production.

2. **Publishing pipeline fire-and-forget** (voice/python/publishing/__init__.py:15-21): All publishing is async/threaded; errors are logged but not raised. If a publish fails (e.g., MongoDB down), the application continues. Check logs to debug missing Rowboat content. The MongoDB schema semaphore (rowboat_mongo_publisher.py) auto-disables itself if schema mismatches, falling back to filesystem — this is a safety measure but may mask underlying DB issues.

3. **Rowboat MongoDB schema drift** (voice/python/publishing/rowboat_mongo_publisher.py:is_available check): The publisher validates its expected schema on every write. If Rowboat schema changes (e.g., new fields, renamed collections), the check fails → falls back to filesystem → content no longer indexes. Keep Rowboat version in sync with the publishing schema expectations.

4. **Brain/OpenFang routing has no mirofish capability**: capabilities.yaml has no entry that routes to `mirofish_publisher` or invokes MiroFish HTTP API. Bubble evaluation, simulations, and project creation are manual (HTTP API) or via publishing (fire-and-forget from voice pipeline). To add voice/chat triggers ("run a Twitter simulation on topic X"), add a new capability entry with agents: [brain-video, ...] and execution_target: http://mirofish:5001/api/simulation.

5. **Host Ollama coupling for MiroFish**: If Ollama goes down or the host machine reboots, MiroFish containers stay Up but /health checks fail silently (timeouts to :11434 are retried internally, no explicit error on 5s timeout). The frontend becomes unresponsive. Monitoring should flag "MiroFish health check > start_period" and verify host:11434 reachability.

---

**Note**: This document reflects the state as of 2026-06-23 (stack.yml revision). Phases are numbered per internal roadmap (Phase A/B/C/D learner/inference topology; Phase 8.B decision graph; Phase 11.U.H OpenRouter credit exhausted → groq + direct OpenAI fallback). Consult git history (vibemind-stack.yml blame) for migration timeline.
