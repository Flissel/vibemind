# Rowboat (core / immer)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

ROWBOAT is a local-first knowledge graph AI coworker that runs as a containerized 5-service stack within the VibeMind Docker Swarm overlay. It maintains an Obsidian-compatible Markdown vault (~/.rowboat/knowledge with git-tracked notes) synced to a MongoDB datastore, uses Qdrant vector DB for semantic RAG over documents, Redis for session/job caching, and exposes itself via Next.js UI (:3100) + REST chat API (:3001, disabled in current config). Rowboat integrates with VibeMind through the Electron app (Automation_ui CDP :9223 BrowserView) and supplies 33 voice-triggerable tools to Brain via OpenFang agents for meeting prep, email drafting, knowledge search, and deck generation.

## Services / Components

All services run in the vibemind-swarm overlay network (hostname-based DNS) and persist data via named volumes. From vibemind-stack.yml:

1. **rowboat-mongo** — MongoDB 5.x, host-published on loopback :27017 only (voice/Python backend RowboatMongoPublisher access). In-stack uses `rowboat-mongo:27017/rowboat` database. Named volume `rowboat_mongo` (314MB live data pre-migrated into Swarm). Single-Writer constraint (manager-pinned). Healthcheck: mongosh ping. Deploy labels: `vibemind.service=rowboat-mongo`, `vibemind.tier=space`, `vibemind.component=datastore`, `vibemind.space=rowboat` (vibemind-stack.yml:640-679).

2. **rowboat-redis** — Redis 7-alpine, ephemeral (no persistence). In-stack only at `rowboat-redis:6379`. Used for session tokens + job queue. Healthcheck: redis-cli ping. Deploy labels same pattern (vibemind-stack.yml:681-709).

3. **rowboat** (Next.js app) — `vibemind-rowboat-rowboat:latest` image, published as ingress :3100 → container :3000 (PORT=3000 env override; .env_file has PORT=8007, override required). ENV: `MONGODB_CONNECTION_STRING=mongodb://rowboat-mongo:27017/rowboat`, `REDIS_URL=redis://rowboat-redis:6379`, `QDRANT_URL=http://qdrant:6333` (shared overlay Qdrant). Volume: `rowboat_uploads:/app/uploads` (RAG document scratch). Healthcheck: node HTTP client GET /:3000 (no python/curl in image; verified toolset per container). No /health route; root route returns 200 (Next.js app root). 40s start_period (vibemind-stack.yml:711-768).

4. **rowboat-agents** — `vibemind-rowboat-rowboat_agents:latest` image, published :3101 → :3001 (Quart/Hypercorn). ENV: `MONGODB_URI=mongodb://rowboat-mongo:27017/rowboat`, `REDIS_URL=redis://rowboat-redis:6379`, `QDRANT_URL=http://qdrant:6333`, `API_KEY=${AGENTS_API_KEY}` (inter-service auth). Healthcheck: Python urllib GET http://127.0.0.1:3001/health. **Currently replicas: 0** — disabled. Original upstream Rowboat repo removed this service in mid-2025; modern Rowboat runs UI+API+jobs+rag from single rowboat image. VibeMind consumes Rowboat via UI (:3100) and CDP only (not this service). Re-enable if matching source restored (vibemind-stack.yml:770-825).

5. **rowboat-jobs-worker** — `vibemind-rowboat-jobs-worker:latest` image, **no published HTTP port** (queue worker). CMD: `npm run jobs-worker` (critical fix 2026-05-19 — earlier cmd was bare `node` → REPL → exit 0 on start). ENV: `MONGODB_CONNECTION_STRING`, `REDIS_URL`, `QDRANT_URL` from stack overlay DNS. Healthcheck: `pgrep -f jobs-worker.ts` (honest liveness — verifies the actual script is running, not just any node process). 30s start_period. Deploy labels: `vibemind.component=worker` (vibemind-stack.yml:827-877).

6. **rowboat-rag-worker** — `vibemind-rowboat-jobs-worker:latest` image, **no published HTTP port**. CMD: `sh -c "cd /app && (npm run setupQdrant || true) && npm run rag-worker"`. Idempotent setupQdrant creates Qdrant collection `embeddings` (size 1536) if missing; rag-worker polls pending data-source docs → embeds via OpenAI text-embedding-3-small → stores in Qdrant. **Added 2026-06-03** as persistent core service (was an on-demand profile worker; pending docs were stuck indefinitely before). Healthcheck: `pgrep -f rag-worker.ts`. 45s start_period (setupQdrant overhead) (vibemind-stack.yml:888-930).

**Shared infra dependencies:**
- **qdrant** — shared overlay service at `qdrant:6333` (vibemind-stack.yml:36-66). Rowboat collections namespace: `embeddings` (rowboat RAG docs) vs Brain's `brain-*` / `rowboat-artifacts`. No collision. Digest-pinned to `:latest@sha256:b3063c673...`.
- **vibemind-shared overlay network** — all rowboat services + qdrant + brain + mirofish connected. Overlay DNS enables internal service discovery without host port tunneling.

## Dependencies

**UPSTREAM (Rowboat NEEDS):**
- **MongoDB at rowboat-mongo:27017** — persists projects, conversations, datasources, message history. Live data migrated into named volume `rowboat_mongo` at deployment cutover (Phase 4). Without it: chat state lost, knowledge base queries fail.
- **Redis at rowboat-redis:6379** — session cache, job queue. Ephemeral; regenerated per restart.
- **Qdrant at qdrant:6333** — shared overlay singleton. Rowboat reads `embeddings` collection (RAG docs). Depends_on: qdrant service healthy before rowboat starts (vibemind-stack.yml:738, 791, 904).
- **Shared .env** — File mounted from repo root: `../../.env` (vibemind-stack.yml:721, 779, 838, 892). Supplies `OPENAI_API_KEY`, `PROVIDER_API_KEY`, `AGENTS_API_KEY`, `QDRANT_API_KEY`, `N8N_API_KEY`, Google/AWS keys. No host-shell expansion — `env_file:` is evaluated at swarm deploy time from the `.env` file on disk. Empty shell env must not override it (rowboat lesson 2026-05-19: earlier mistake `OPENAI_API_KEY=${OPENAI_API_KEY}` in `environment:` block expanded from empty deploy shell → overwrote .env value → agents crashed "No LLM Provider API key").
- **Host docker.sock** — NOT mounted (Phase 1 design — rowboat does not spawn containers). Possible future: RAG workers or agents may need egress.
- **Host.docker.internal routes** — No extra_hosts configured; rowboat runs fully inside overlay (no host gateway needed today).

**DOWNSTREAM (What calls Rowboat):**
- **Automation_ui (Electron apps/x BrowserView, CDP :9223)** — Displays Rowboat UI at localhost:3100 in an iframe. BrowserView created by /ipc-handlers which routes ipc.showRowboat → webview.loadURL('http://localhost:3100'). Rowboat frontend + Electron renderer share postMessage boundary.
- **Voice/OpenFang agents** — Brain routes intents to `rowboat-knowledge` agent (capabilities.yaml:57, 96) for:
  - Knowledge search/query (via roarboot_tools.py:search_knowledge, query_knowledge)
  - Email drafting (draft_email, generate_meeting_brief, generate_deck)
  - RAG semantic search (rag_search via Qdrant API)
  - Document upload (upload_document)
  - Graph exploration (explore_graph)
  - Voice-triggered via "search rowboat for X", "prep me for meeting with Y", "generate a deck on Z"
- **Bidi-sync to public.ideas + canvas_nodes** — Rowboat knowledge graph → Supabase public schema (Ideas-HTTP :5102 fallback; Brain consumes via Supabase REST when Ideas-HTTP down). Integration via RowboatSyncAgent (not yet live in stack; planned Phase 4b). Rowboat sends updated bubbles/relationships; Brain decision_graph writes to Neo4j-mirofish (shared by mirofish KG + Brain history).
- **MCP rowboat-ui + desktop-knowledge** — rowboat-ui server (not in this stack) dispatches rowboat.* events → roarboot_tools handlers → broadcast to Electron.

**File:line evidence:**
- depends_on: vibemind-stack.yml:735-738 (rowboat), 788-791 (rowboat-agents), 847-849 (jobs-worker), 902-905 (rag-worker).
- env_file: vibemind-stack.yml:720-721, 778-779, 838-839, 891-892.
- QDRANT_URL, MONGODB_CONNECTION_STRING: vibemind-stack.yml:728-730, 781-782, 843-844, 896-897.

## Possible usages

**Voice-triggered (via Electron UI, /launch-agent relay, or Brain routing):**

1. **Knowledge Search** — `roarboot_tools.py:36`, voice trigger "search rowboat for [query]"
   - Returns semantic search across the knowledge vault (Obsidian markdown notes in ~/.rowboat/knowledge)
   - Result broadcast to Electron (json stdout via _broadcast_to_electron)

2. **Knowledge Query** — `roarboot_tools.py:67`, query knowledge about a person/project/topic
   - Semantic + structured recall from the knowledge graph
   - Argument: `subject` (required), `question` (optional)

3. **Email Drafting** — `roarboat_tools.py:99`
   - Argument: `recipient`, `topic` (required), `context` (optional)
   - Uses knowledge graph to ground the draft in past commitments/history

4. **Meeting Brief** — `roarboot_tools.py:133`
   - Argument: `meeting` (required), `participants` (optional)
   - Pulls prior decisions, open questions, relevant threads

5. **Deck Generation** — `roarboot_tools.py:165`
   - Argument: `topic` (required), `context` (optional)
   - Generates presentation outline using knowledge graph

6. **Voice Note Processing** — `roarboot_tools.py:197`
   - Argument: text (required)
   - Transcribe → update knowledge graph with key takeaways

7. **Free Chat** — `roarboot_tools.py:337`, core multi-turn interface
   - Argument: `message` (required), `context` (optional, default='general')
   - Rowboat responds with full knowledge graph context
   - Routed via RoarbootClient.chat → POST http://localhost:3100/api/chat

8. **RAG Semantic Search** — `roarboat_tools.py:364`
   - Argument: `query`, `threshold` (default 0.7), `limit` (default 5)
   - Semantic search via Qdrant vector DB (embeddings collection)
   - Returns conceptually similar content from uploaded documents

9. **Document Upload** — `roarboat_tools.py:393`
   - Argument: `file_path` (e.g., PDF, DOCX, MD, TXT) OR `text` (raw content), `title` (optional)
   - Uploads → RAG indexing in Qdrant + MongoDB metadata
   - Pending docs processed by rowboat-rag-worker

10. **Graph Exploration** — `roarboat_tools.py:457`
    - Argument: `subject` (optional)
    - Show relationships, linked notes, context for a subject

11. **Docker Control** — `docker_tools.py:84-199`
    - `start_docker`, `stop_docker`, `restart_docker`, `docker_status`
    - Manage the rowboat stack via `docker compose up/down` in vibemind-os/spaces/rowboat/rowboat

12. **Conversation Management** — `roarboat_tools.py:301, 337`
    - `reset_conversation(context)` — clears conversation state
    - `list_conversations()` — shows active conversation IDs
    - Each context (e.g., "search", "query", "general", "default") is a separate conversation thread

13. **UI Signal** — `roarboat_tools.py:253`, `open_webview(context)`
    - Signal Electron to show the Rowboat WebView (handled via electron ipc-broadcast)

**API endpoints (direct HTTP, not typically voice-triggered):**
- POST `/api/chat` — send message, get streamed response + metadata
- GET `/api/projects` — list projects
- POST `/api/datasources` — register data source (Gmail, Calendar, etc.)
- GET `/health` — NOT PRESENT (Rowboat has no /health; root / returns 200)
- Rowboat agent :3001 `/health` (if enabled; currently replicas:0)

**Registry & Routing (capabilities.yaml, roarboot.yml):**
- Space: `rowboat` (vibemind-os/data/space_capabilities/rowboat.yml)
- Registry agent: `rowboat-knowledge` (roarboot.yml:423)
- MCP servers: `vibemind-db`, `fetch` (roarboot.yml:424-426)
- Routed events (all_routed_events roarboot.yml:457-465):
  - `roarboot.deck`, `roarboot.docker.start`, `roarboot.docker.stop`
  - `roarboot.email_draft`, `roarboot.meeting_brief`, `roarboot.query`, `roarboot.search`, `roarboot.status`

## MCPs & OpenFang agents involved

**MCP Servers:**
1. **vibemind-db** — Provides database access for rowboat-knowledge agent (roarboot.yml:425; referenced but server not in this stack — must run on host or separate container).
2. **fetch** — HTTP fetch capability for rowboat agent actions (roarboot.yml:425; tool hint for search/query/email_draft/meeting_brief/deck/status events).

**OpenFang Agents:**
- **rowboat-knowledge** — Registry agent (roarboot.yml:423). Handles all roarboot.* events. Invoked when Brain's capability router matches intent to a roarboot capability (e.g., "search the knowledge for X" → bubble_evaluate feedback loop includes rowboat-knowledge:57).
- **brain-coder, fungus-search, poc-security-scanner** — Also appear in feedback loop (capabilities.yaml:57) for reflective synthesis after bubble evaluation.

**Event Routing:**
- Brain's CapabilityRouter matches user intent (regex patterns in capabilities.yaml) → dispatches to primary agent (e.g., rowboat-knowledge for `code_search` capability:96).
- roarboot.yml registry_events (vibemind-stack.yml:428-450) define event-to-tool mapping:
  - `roarboot.search` → tool_hint: fetch, params: [query]
  - `roarboot.query` → tool_hint: fetch, params: [query]
  - `roarboot.email_draft` → tool_hint: fetch, params: [recipient]
  - etc. (tool hints guide subagent selection; actual tool dispatch handled by RoarbootBackendAgent.stream() or roarboot_tools wrapper)

**Note:** MCP servers are *not* in the Swarm stack (Phase B limitation). They must be running on the host or in separate containers. Rowboat service itself does NOT spawn MCP servers; it consumes them via env config (mcp.json at ~/.rowboat/config, standard MCP client).

## Isolated startup — exactly what must be up to test this area alone

**Minimal setup to test rowboat in isolation (no Brain, no Mirofish, no Coding Engine):**

1. **Docker Swarm single-node (if not already up):**
   ```
   docker swarm init  (if not joined)
   ```

2. **Deploy the minimal rowboat stack block from vibemind-stack.yml:**
   ```
   docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind \
     --with-registry-auth
   ```
   This will deploy:
   - qdrant (shared overlay, :6730 host-published)
   - rowboat-mongo (overlay, loopback :27017)
   - rowboat-redis (overlay, no host port)
   - rowboat (overlay ingress :3100 → :3000)
   - rowboat-jobs-worker (queue worker, no HTTP)
   - rowboat-rag-worker (queue worker, no HTTP)

   **Verify services up:**
   ```
   docker service ls | grep rowboat
   docker service logs vibemind_rowboat --tail 100
   docker service logs vibemind_rowboat-mongo --tail 50
   ```

3. **Host prerequisites:**
   - `.env` file in repo root with at minimum:
     - `OPENAI_API_KEY=sk-...` (or `PROVIDER_API_KEY` if using alternate provider)
     - `AGENTS_API_KEY=...` (any non-empty value for inter-service auth)
   - Docker daemon running with Swarm overlay capability
   - 4GB RAM minimum (rowboat + mongo + redis + qdrant = ~2.5GB at idle)

4. **Access points (from host):**
   - Rowboat UI: `http://localhost:3100` (Next.js app, shows login or onboarding if first run)
   - Qdrant admin: `http://localhost:6730/dashboard` (vector DB status)
   - Mongo: `mongosh localhost:27017/rowboat` (direct query, verify data written)
   - Job worker logs: `docker service logs vibemind_rowboat-jobs-worker --tail 200`
   - RAG worker logs: `docker service logs vibemind_rowboat-rag-worker --tail 200`

5. **Manual test flow:**
   - Open `http://localhost:3100` in browser
   - If first run: Rowboat UI shows Gmail/Calendar setup or skip → knowledge vault empty
   - Upload a document via web UI or via tool: `upload_document(file_path="/tmp/test.md", title="Test")`
   - Run RAG search: `rag_search(query="test topic")`
   - Verify Qdrant has embeddings: `docker exec -it $(docker ps -q -f "label=com.docker.swarm.service.name=vibemind_qdrant") curl http://localhost:6333/collections` → should list `embeddings` collection with count > 0

6. **Native processes NOT needed for basic test:**
   - Ollama/LLM (rowboat uses OPENAI_API_KEY for chat; fallback to local Ollama not configured in stack env)
   - Brain (rowboat works standalone; no dependency on Brain being up)
   - OpenFang agents (rowboat works without voice routing; no agent dispatch needed)
   - Automation_ui / Electron (rowboat web UI works standalone; Electron just wraps it in a BrowserView)
   - Neo4j-mirofish (rowboat writes to Mongo, not Neo4j; no graph sync until phase 4b)

7. **Known gaps / gotchas:**
   - **rowboat-agents disabled (replicas: 0)** — upstream Rowboat repo removed this service; if needed, source must be restored to apps/rowboat_agents.
   - **No MCP servers in stack** — rowboat-knowledge agent (if invoked) needs vibemind-db + fetch MCP servers running separately. Test agent dispatch in isolation by running host MCP server, or disable agent routing (test UI only).
   - **No voice input** — web UI lacks Deepgram integration (optional config ~/.rowboat/config/deepgram.json in app, not stack env). Test voice via uploaded transcripts or raw text notes.
   - **Gmail/Google integrations optional** — UI will prompt but don't require them; can test knowledge graph with manual Markdown notes.
   - **RAG requires OpenAI key** — text-embedding-3-small hardcoded in rowboat-rag-worker (vibemind-stack.yml:898). No fallback to local embedder yet.

**Gaps (not in this stack, needed for full VibeMind integration):**
- Brain services (brain-core, brain-api, brain-loops) — capability routing, agent dispatch
- OpenFang (:4200) — agent orchestration
- Automation_ui Electron + Desktop CDP — UI wrapping, voice input relay
- Ollama (:11434) — local LLM fallback (currently stack points to OpenAI)
- MCP servers (vibemind-db, fetch, others) — capability execution
- Mirofish (Neo4j, Flask) — knowledge graph sync, entity KG

## Key files

1. **vibemind-stack.yml:625-930** — Rowboat Swarm service definitions (all 6 services: mongo, redis, rowboat, agents, jobs-worker, rag-worker). Lines 640-930 are the load-bearing section.

2. **vibemind-os/spaces/rowboat/rowboat/docker-compose.yml:1-271** — Standalone dev compose (not used in Swarm stack, reference only). Defines local build contexts + profiles (setup_qdrant, rag-worker, jobs-worker, delete_qdrant).

3. **vibemind-os/spaces/rowboat/tools/roarboot_tools.py:1-500** — 33 voice-triggerable tools. Core: chat (line 337), search_knowledge (36), query_knowledge (67), draft_email (99), generate_meeting_brief (133), generate_deck (165), process_voice_note (197), rag_search (364), upload_document (393), explore_graph (457).

4. **vibemind-os/spaces/rowboat/tools/roarboot_client.py:40-350** — RoarbootClient class. Wraps HTTP calls to rowboat :3100 API. Methods: chat, search_knowledge, query_knowledge, draft_email, generate_meeting_brief, generate_deck, process_voice_note, get_status, reset_conversation, list_conversations. Singleton pattern via get_roarboot_client().

5. **vibemind-os/spaces/rowboat/tools/docker_tools.py:84-199** — Docker Compose lifecycle: start_docker, stop_docker, restart_docker, docker_status (for local testing; stack control is via `docker service` not compose).

6. **vibemind-os/data/space_capabilities/rowboat.yml** — Tool registry (33 tools, no MCP servers, no events). Scanned from spaces/rowboat/tools + spaces/rowboat/agents.

7. **vibemind-os/data/space_capabilities/roarboot.yml** — Same tools (33) + registry_agent: rowboat-knowledge + MCP servers: [vibemind-db, fetch] + routed_events (roarboot.search, roarboot.query, roarboot.email_draft, roarboot.meeting_brief, roarboot.deck, roarboot.status, roarboot.docker.{start,stop}).

8. **~/.rowboat/knowledge** — User's Obsidian vault (plain Markdown + .git history). Contains People/, Projects/, Topics/, Agents/, Organizations/, Workflows/ folders. Synced to MongoDB rowboat collection. Backed by .bubble_sync_hashes.json (tracks integration state).

9. **~/.rowboat/config/mcp.json** — MCP server config (exa, desktop-commander, playwright, filesystem). Rowboat MCP client reads this at startup.

10. **~/.rowboat/config/models.json** — LLM provider config (provider flavor: openai, apiKey, model). Rowboat reads this for chat LLM selection.

11. **vibemind.config.json:44-47, 90** — VibeMind module metadata. rowboat enabled: true, path: vibemind-os/spaces/rowboat/rowboat, docker compose at vibemind-os/spaces/rowboat/rowboat/docker-compose.yml, port 3000 (mapped to host :3100 in stack).

12. **vibemind-os/brain/the_brain/data/capabilities.yaml:57, 96** — Brain capability registry snippets. rowboat-knowledge agent referenced in feedback_loop (line 57) and supporting agents for code_search (line 96). Confirms Brain → Rowboat routing.

## Gotchas — known traps

1. **env_file MUST come first in docker-compose.yml** — If `environment:` block has `OPENAI_API_KEY=${OPENAI_API_KEY}` and shell env is empty, it overrides .env's value with empty string. All env vars then resolve to empty in the app. Rowboat lesson 2026-05-19: agents crashed "No LLM Provider API key" because of this. Fix: use env_file: first, only set overlay-DNS overrides in environment: (vibemind-stack.yml:720-721, comment 715-724).

2. **Healthcheck tool availability varies per image** — rowboat container (node:18-alpine) has `node` but NOT `python3` or `wget/curl`. Earlier healthcheck used wget/python probe → failed. Solution: probe must use tools actually in the image. Use `node -e "require('http').get..."` for Next.js, `python3 urllib` for agents (Quart), `pgrep -f <script>` for queue workers (honest liveness, not just "does a node exist"). STANDARDS.md §2: verify the real surface, never assume (vibemind-stack.yml:747-748, 797-798, 856-857, 909-910).

3. **Queue workers have NO HTTP port; liveness != "is node running"** — jobs-worker and rag-worker run `npm run jobs-worker` / `npm run rag-worker` in an event loop. Earlier healthcheck was bare `node` (REPL) → instant exit 0 → swarm considered it "Complete" + on-failure restart_policy ignored exit 0 (exit 0 = "healthy") → service stayed 0/1 forever (observed: 7h stuck). Fix: probe must verify the real script process is alive, not just any node (vibemind-stack.yml:857, 910: `pgrep -f 'jobs-worker.ts'`).

4. **Container start_period too short → unhealthy churn** — brain-core 2026-06-09: 60s was insufficient for 2-worker cold-start (each worker loads ~109s of embeddings). Every retry failed. Solution: 360s start_period (vibemind-stack.yml:220, comment 217-219). Same pattern for rowboat (40s), rag-worker (45s, includes setupQdrant).

5. **Qdrant collection name collision = silent failure** — rowboat uses "embeddings", brain uses "brain-*" + "rowboat-artifacts". No collision in shared instance. But if rowboat rag-worker tries to POST to a collection that doesn't exist (setupQdrant failed silently), embedding fails with "Collection doesn't exist" → rag-worker retries forever. Fix: setupQdrant is idempotent + `|| true` (vibemind-stack.yml:890). Verified: `pgrep -f setupQdrant` or check logs to confirm collection creation.

6. **rowboat-agents disabled (replicas: 0)** — original Rowboat repo removed this service in mid-2025. Image `vibemind-rowboat-rowboat_agents:latest` may not exist. If re-enabling, source must be restored to apps/rowboat_agents (vibemind-stack.yml:809-815, comment 809-816).

7. **BrowserView URL not auto-updated on port change** — Electron Automation_ui hardcodes http://localhost:3100 for rowboat WebView in ipc-handlers. If stack port changes, Electron + host :3100 port mapping must stay in sync (currently hardcoded in swarm ingress :3100 → container :3000).

8. **MongoDB data not auto-migrated into named volume** — First Swarm deploy of rowboat with empty rowboat_mongo volume loses all prior host data. Data migration from ./data/mongo to the named volume rowboat_mongo is a manual ops task (Phase 4 cutover step). Backup verified restorable before migrate (mentioned vibemind-stack.yml:636-638).

9. **OpenAI API key required for RAG** — text-embedding-3-small is hardcoded in rowboat-rag-worker (vibemind-stack.yml:898). No fallback to local embedder (e.g., ollama embeddings). If OPENAI_API_KEY is empty or exhausted, rag-worker silently fails to embed documents. Check logs: `docker service logs vibemind_rowboat-rag-worker | grep -i embed`.

10. **Host :6730 publishes Qdrant, not rowboat** — rowboat :3100 is published via Docker ingress (swarm routing mesh), NOT bind-mounted to the host interface card. From outside the swarm overlay, you cannot reach rowboat:3000 directly (internal DNS). Access via ingress :3100 (published host port). Qdrant :6730 is explicitly host-published so legacy host-bound services (Brain venv) can reach it (vibemind-stack.yml:44-46).

11. **rowboat-rag-worker may hang on first setupQdrant** — setupQdrant creates the embeddings collection and may block if Qdrant is slow. 45s start_period is generous, but in production check if it completes: `docker exec -it <container> npm run setupQdrant` (or tail logs). No timeout implemented — if Qdrant is stuck, worker will block indefinitely.

12. **Knowledge vault is NOT auto-synced to Supabase/public.ideas yet** — bidi-sync mentioned in Brain capabilities (Phase 4b) is not in the current stack. rowboat knowledge stays in MongoDB + local ~/.rowboat/knowledge vault. Brain does not yet consume rowboat bubbles for context augmentation (Ideas-HTTP :5102 is fallback to Supabase direct; Rowboat integration deferred).

13. **No horizontal scaling of rowboat workers (single-node Swarm today)** — rowboat-jobs-worker and rowboat-rag-worker are replicas: 1. In multi-node swarm, they would need a distributed job queue (Redis is already there, but coordination logic not in rowboat codebase yet). Scale-out is Phase C, not Phase B.

14. **Voice input NOT in stack** — Deepgram ASR config (~/.rowboat/config/deepgram.json) is optional app-level config, not Swarm env. Rowboat web UI lacks voice input UI. Voice routing is via Electron UI → voice agent → roarboot_tools wrapper → rowboat HTTP API (async, no direct voice path). Test voice via text input or uploaded transcripts.

15. **Brain capabilities.yaml references "rowboat-knowledge" agent that might not exist in OpenFang** — On startup, Brain's CapabilityRouter validates agent names against `GET http://openfang:4200/api/agents`. If rowboat-knowledge is not registered in OpenFang, router logs a warning but routing still falls back to broadcast. Ensure rowboat-knowledge agent is deployed in OpenFang before enabling rowboat capability routing (Phase C refinement).

---

**Summary:** Rowboat is a fully containerized, Swarm-managed knowledge graph system in this stack. Minimal footprint to test (6 services, ~2.5GB RAM, no external services required except OpenAI API key). Integration points: Brain agent dispatch (capabilities.yaml routing → rowboat-knowledge), Electron BrowserView UI (:3100), voice tools (roarboat_tools via OpenFang), and future bidi-sync to public.ideas. Current gaps: no horizontal scaling, knowledge sync deferred, no in-stack MCP servers, rowboat-agents disabled (source missing). Full VibeMind integration requires Brain + OpenFang + Electron + Ollama + MCP servers running separately.
