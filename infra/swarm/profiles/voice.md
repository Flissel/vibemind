# Voice-Backend (Host-Glue / electron_backend)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Voice backend is the glue host process that ties together VibeMind's multi-space architecture. It's a native Python service (not Docker) spawned by the Electron main process, communicating via stdin/stdout JSON IPC. It orchestrates voice dialog through OpenAI's Realtime API, manages the 3D canvas/bubble state (ideas storage), routes intents through a multi-agent swarm orchestrator, and synchronizes content bidirectionally with Rowboat (the knowledge graph engine). It hosts Automation_ui (Vapi voice control) and eyeTerm (gaze tracking) as background subprocesses.

## Components

**Core Entry & Host Process**
- `voice/python/electron_backend.py:1` — Main backend (1918 lines). Spawned by Electron, manages IPC message dispatch, initializes all subsystems
- **Port:** stdin/stdout JSON IPC (no explicit port; bidirectional via child process pipes)

**IPC Handlers (extracted from electron_backend into separate modules)**
- `voice/python/ipc/voice_manager.py` — Voice lifecycle (start/stop OpenAI Realtime session, reconnect on timeout)
- `voice/python/ipc/canvas_manager.py` — Bubble CRUD, position tracking, canvas node management, collision detection
- `voice/python/ipc/project_manager.py` — Coding Engine integration, project preview lifecycle, VNC proxy URLs
- `voice/python/ipc/clawport_handlers.py` — Dashboard chat, scheduled tasks, memory search, plugin management
- `voice/python/ipc/n8n_handlers.py` — n8n workflow automation lifecycle and iterative chat builder
- `voice/python/ipc/exploration_handlers.py` — AI-Scientist tree search for idea refinement
- `voice/python/ipc/shuttle_handlers.py` — Requirement validation pipeline visualization
- `voice/python/ipc/eyeterm_handlers.py` — Gaze tracking control
- `voice/python/ipc/auto_layout.py` — 3D bubble position collision avoidance

**Voice & Audio**
- `voice/python/voice/openai_realtime.py` — OpenAI Realtime API session (audio bidirectional streaming, VAD, function calling)
- `voice/python/voice/audio_manager.py` — Microphone capture, speaker playback via sounddevice
- `voice/python/voice/session_config.py` — Tool definitions (send_intent), model/voice config

**Swarm Orchestration (Intent → Tool Execution)**
- `voice/python/swarm/voice_bridge_v2.py` — Pure async voice interface, seeds events to Redis for backend agents
- `voice/python/swarm/orchestrator/` — Intent classification, event routing, response generation
- `voice/python/swarm/event_bus.py` — Pub/sub event distribution to agents
- `voice/python/swarm/logging/space_logger.py` — Space-colored structured JSON logging

**Data Layer (Supabase)**
- `voice/python/data/ideas_repository.py` — Bubbles (top-level ideas), full-text search
- `voice/python/data/canvas_repository.py` — Canvas nodes (notes, images, links inside bubbles), edges
- `voice/python/data/projects_repository.py` — Code generation projects
- `voice/python/data/shuttles_repository.py` — Requirement validation shuttle state
- `voice/python/data/task_memory_repository.py` — Dialog memory per session
- `voice/python/data/supabase_database.py` — PostgREST client factory with retry logic

**Publishing (Bubble ↔ Rowboat Sync)**
- `voice/python/publishing/ideas_publisher.py` — Publishes bubbles to Rowboat knowledge base
- `voice/python/publishing/rowboat_mongo_publisher.py` — Direct MongoDB write (preferred)
- `voice/python/publishing/bubble_sync/worker_db_to_fs.py` — Drain ideas_sync_outbox, push to ~/.rowboat/
- `voice/python/publishing/bubble_sync/worker_fs_to_db.py` — Watch vault, sync user edits back to DB
- `voice/python/publishing/bubble_sync/worker_canvas_reformat.py` — LLM reformatting of edited structured nodes

**Tools (Voice Command Handlers)**
- `voice/python/tools/idea_tools.py` — Bubble creation, naming, scoring
- `voice/python/tools/bubble_tools.py` — Bubble state tracking for IPC
- `voice/python/tools/navigation_tools.py` — Space/bubble navigation from voice
- `voice/python/tools/session_tools.py` — Dialog turn tracking
- `voice/python/tools/workspace_tools.py` — Electron window state queries

**Electron Main Process (TypeScript/Node.js)**
- `voice/electron-app/main.js:1-150` — Spawns Python backend, manages window/IPC routing
- Port allocator, Docker manager, dashboard/rowboat/swe-design embedded managers

**Subprocesses (Auto-started as daemon threads)**
- Automation_ui (`voice/python/spaces/desktop/Automation_ui/backend/server.py` on port 8007) — FastAPI for Vapi voice control
- eyeTerm (`voice/python/spaces/desktop/eyeterm/headless.py` on port 8099) — MJPEG gaze tracking
- Rowboat Docker health monitor + auto-start
- Embedding model pre-load
- Periodic data flush workers (Rowboat sync every 30s/5m)
- Rowboat update checker

## Dependencies

**UPSTREAM (Voice needs these running or configured)**
1. **Supabase** (PostgreSQL + PostgREST) — Database for bubbles, canvas nodes, projects
   - Connection via `data/supabase_database.py:PostgRESTClient`
   - Schema: `public.ideas` (bubbles), `public.canvas_nodes`, `public.canvas_edges`, `public.projects`, `public.shuttles`
   - Referenced in `electron_backend.py:363-374` (IdeasRepository, CanvasRepository initialization)

2. **OpenAI Realtime API** (voice provider)
   - API key: `OPENAI_API_KEY` env var
   - Model: `gpt-4o-realtime-preview` (from `voice/session_config.py:55`)
   - Referenced in `electron_backend.py:220-238` (OpenAIRealtimeVoiceSession import)

3. **Redis** (event bus for backend agents, TTS queue)
   - For VoiceBridgeV2 to coordinate intent → tool execution
   - Default: `redis://localhost:6379` (can override via `REDIS_URL`)
   - Referenced in `electron_backend.py:765` (auto-populated if not set)

4. **Rowboat Docker** (knowledge graph, Graph Builder)
   - Optional but recommended; auto-start at startup if `ROWBOAT_ENABLED=true` and `auto_start_docker=true`
   - Roarboot health monitor runs every 60s: `electron_backend.py:589-683`
   - MongoDB for direct publishing: `publishing/rowboat_mongo_publisher.py`

5. **Electron Main Process** (parent)
   - Spawns Python backend via `spawn([python, 'electron_backend.py'])`
   - IPC via stdin/stdout (JSON, one per line)
   - Referenced in `electron-app/main.js:300+`

6. **LLM Provider Keys** (Anthropic, OpenAI, Groq, or OpenRouter)
   - For swarm agents (Orchestrator, Ideas, Coding, Roarboot agents)
   - Set via `.env` or environment: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`

**DOWNSTREAM (Consumers of Voice backend)**
1. **Electron Renderer (3D UI)**
   - Receives IPC: `bubbles_sync`, `voice_status`, `agent_response`, `canvas_node_added`, etc.
   - Sends IPC: `start_voice`, `stop_voice`, `enter_bubble`, `add_canvas_node`, etc.
   - File: `electron-app/main.js` → ipcMain handlers

2. **Brain Server** (optional, port 5000)
   - Receives intent classification results if wired (currently disabled in favor of Orchestrator)
   - Not actively used in current architecture

3. **OpenFang** (optional, port 50051)
   - Receives tool execution requests from backend agents
   - Via OpenFang bridge if `OPENFANG_URL` set

4. **Coding Engine** (Spaces/coding/)
   - Code generation projects triggered via ProjectManager
   - Docker container or native Python runner
   - Referenced in `electron_backend.py:318-340` (CodingEngineRunner initialization)

5. **Spaces** (ideas, desktop, rowboat, mirofish, shuttles, etc.)
   - Each space can register tools callable from voice
   - Tools live in `voice/python/tools/` and `voice/python/spaces/*/tools/`
   - Agent dispatch via Orchestrator: `swarm/orchestrator/` (not shown in 1918-line limit; in extended files)

## Possible Usages

**Voice Triggers (OpenAI Realtime → send_intent → Orchestrator)**
- Create bubble: `"Create a bubble for my project idea"`
- Navigate: `"Go to rowboat"`, `"Enter the ideas space"`
- Canvas editing: `"Add a note to this bubble"`, `"Link these nodes"`
- Task management: `"Schedule a meeting for tomorrow"`
- Search memory: `"What did I say about machine learning?"`
- Code generation: `"Generate a Python server"` → Coding Engine
- Exploration: `"Explore this idea deeply"` → AI-Scientist tree search

**Tools Available (via Orchestrator dispatch)**
- `send_intent(transcript)` — Only tool Rachel can call; routes to Orchestrator
- Orchestrator then calls backend agents which can invoke:
  - `idea_tools` — create_bubble, update_bubble, search_ideas
  - `bubble_tools` — get_bubble_info, set_current_bubble
  - `navigation_tools` — navigate_to_space, enter_selection
  - `task_memory_tools` — add_memory, search_memory
  - `session_tools` — mark_user_speech
  - Space-specific tools (rowboat, coding, desktop, etc.)

**API/HTTP Entry Points**
- stdin/stdout JSON from Electron (not HTTP)
- Automation_ui backend: HTTP `http://localhost:8007` (internal to Electron context)
- eyeTerm MJPEG: `http://localhost:8099` (for gaze preview)

**Invocation Methods**
1. Voice command via Electron UI "Start Voice" button → `start_voice` IPC → OpenAI Realtime session
2. Text input via Electron chat box → `chat_text_input` IPC → Orchestrator directly (FORCE_SYNC_MODE)
3. Manual tool trigger via Electron toolbar → `tool_action` IPC → Orchestrator
4. Programmatic: Import `swarm.orchestrator` and call `get_orchestrator()._process_sync()`

## Integration Points

**Brain (Optional Routing)**
- Currently disabled; was intended for neuroscience-inspired routing
- `electron_backend.py:10` references brain but no active integration
- Fallback: Direct Orchestrator classification (no Brain hop)

**Rowboat (Knowledge Graph)**
- Bidirectional sync enabled via `VIBEMIND_BUBBLE_SYNC_ENABLED=1`
- Workers: DB→FS (outbox drain), FS→DB (vault watch)
- MongoDB direct write (preferred): `publishing/rowboat_mongo_publisher.py`
- Fallback: Filesystem to `~/.rowboat/vibemind/`
- Referenced in `electron_backend.py:517-564`

**Bubbles (3D Canvas)**
- Stored in `data/ideas_repository.py` (Supabase)
- Positions tracked with collision detection in `ipc/canvas_manager.py:28-69`
- 3D rendering in Electron renderer (Three.js)
- Electron callback: `get_bubbles` → `canvas_mgr.get_all_bubbles()` → JSON → renderer

**Coding Engine (Project Generation)**
- Lifecycle manager: `ipc/project_manager.py`
- Runner: `CodingEngineRunner` from `coding_engine_runner.py`
- Status callbacks re-wired: `electron_backend.py:430-433`
- VNC preview URLs: `project_manager.py` (either proxy or direct host)

**OpenFang (Agent Dispatch)**
- Not directly called; OpenFang runs standalone
- Bridge layer intended but disabled (Brain was intermediary)
- Fallback: Direct tool execution via swarm agents

**Openfang/Brain Agents (Disabled)**
- Stub references in voice_bridge_v2.py but agents not initialized
- Intent routing happens purely in-process via swarm Orchestrator

## Isolated Startup

**What Must Be Running**
1. **Supabase (PostgREST API)** — Database for bubbles/canvas
   - Docker: `docker run -d -p 3000:3000 postgrest/postgrest`
   - Or use cloud Supabase project with connection string in `.env`

2. **Redis** — For event bus (if using VoiceBridgeV2)
   - Docker: `docker run -d -p 6379:6379 redis:latest`
   - Or set `REDIS_URL` to cloud instance

3. **Electron Parent Process** — Spawns Python backend
   - Run: `cd voice/electron-app && npm start`
   - Or: `electron .` in voice/electron-app/

**Optional (but recommended)**
4. **Rowboat Docker** — Knowledge graph
   - Auto-starts if configured: `ROWBOAT_ENABLED=true`, `auto_start_docker=true`
   - Manual: `docker run -d -p 5173:5173 rowboat/rowboat`

5. **Automation_ui** — Vapi voice control backend
   - Auto-starts at `http://localhost:8007` if `voice/spaces/desktop/Automation_ui/backend/server.py` exists
   - Requires: SQLite database, Redis for queues

**Minimal Standalone Test (Python-only, no Electron)**
```bash
cd voice/python
export OPENAI_API_KEY=sk-...
export SUPABASE_URL=https://...
export SUPABASE_KEY=...
python electron_backend.py  # Waits for Electron stdin; will fail on first IPC read
```
Instead, simulate Electron sending JSON:
```bash
echo '{"type": "get_bubbles"}' | python electron_backend.py
```

**Gaps & Incomplete Areas**
- **No native STT**: Voice input handled by OpenAI Realtime API (no offline fallback)
- **No native TTS**: Voice output handled by OpenAI Realtime (no offline alternative)
- **Docker-first spaces**: Rowboat, MiroFish, AgentFarm require Docker; no native Python equiv
- **Brain routing disabled**: Orchestrator direct classification only (no Hebbian learning fallback)
- **OpenFang not wired**: All agent dispatch via in-process swarm, not external OpenFang service
- **No mobile/CLI mode**: Desktop Electron UI only; no headless voice-only mode
- **Sync workers optional**: Bubble↔Rowboat sync requires `VIBEMIND_BUBBLE_SYNC_ENABLED=1`; default OFF
- **Canvas reformat LLM cost**: Separate `VIBEMIND_CANVAS_REFORMAT_ENABLED=1` (default OFF) to save API calls

## Key Files

**Glue/Router**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:1-100` — Init all subsystems, IPC dispatch
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:886-940` — Message handler entry, IPC router
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/ipc/voice_manager.py:29-150` — Voice lifecycle orchestration

**Canvas State**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/ipc/canvas_manager.py:75-150` — Bubble load from DB with retry logic
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:248-275` — Bubble data structure (id, title, position, db_id, score)

**Voice Pipeline**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/voice/openai_realtime.py:68-150` — Session init and WebSocket connect
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/swarm/voice_bridge_v2.py:54-100` — Voice→Intent→Tool dispatch

**Publishing/Sync**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:450-568` — Rowboat sync thread spawn and periodic flush
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/publishing/__init__.py:1-100` — Publisher factory with MongoDB/filesystem fallback

**Subprocesses**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:699-836` — Automation_ui auto-start with health check
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/python/electron_backend.py:839-867` — eyeTerm MJPEG launch

**Electron Bridge**
- `C:/Users/User/Desktop/Vibemind_V1/vibemind-os/voice/electron-app/main.js:1-150` — Electron entry, .env loading, Python spawn

## Gotchas

1. **PostgREST Schema Cache Warm-up (30-60s startup delay)**
   - On Electron launch, PostgREST may return 503 PGRST002 for ~30s while building schema cache
   - Bubble loader retries with exponential backoff (0/1/2/4/8/16s): `canvas_manager.py:95-128`
   - First-time users see empty 3D canvas until retry succeeds; normal behavior

2. **OpenAI Realtime Session Timeout (30 minutes)**
   - After 30min of voice, session auto-disconnects
   - Auto-reconnect on next `start_voice` call; no graceful handoff mid-sentence
   - Long conversations require periodic manual restart or session ping

3. **Thread Safety in Module-Level State**
   - `_bubbles`, `_current_bubble_id`, `_backend_instance` are global for tool access
   - Races possible if Electron sends IPC while tool is reading state
   - Mitigated by single-threaded event loop in voice_manager (asyncio)

4. **Redis Required for Full Voice Delivery**
   - VoiceBridgeV2 depends on Redis event bus for background agent tasks
   - No Redis = intents classified but tools may not execute
   - Auto-fallback: If Redis unavailable, status listeners time out silently
   - `voice/python/swarm/voice_bridge_v2.py:80-95` does not check Redis health

5. **Bubble Sync Workers Are Opt-In**
   - Default: `VIBEMIND_BUBBLE_SYNC_ENABLED=0` (OFF)
   - Rowboat sync does NOT run unless explicitly enabled
   - Canvas edits in Electron do not persist to Rowboat vault by default
   - User must set env var and restart to enable bidirectional sync

6. **Automation_ui Subprocess Crash Silent**
   - If FastAPI server dies, Electron does not auto-restart it
   - Stderr is drained to prevent pipe deadlock but not logged persistently
   - Workaround: Manual restart via `start_automation_ui` IPC or Electron restart

7. **eyeTerm Requires Camera + MediaPipe**
   - MJPEG stream at `http://localhost:8099` only works if `EYETERM_ENABLED=true`
   - Camera must be available; no fallback to cursor-only mode
   - Import error silently disables eyeTerm (no hard fail)

8. **Coding Engine Runner Expects Subprocess or HTTP API**
   - If Docker Coding Engine unavailable, project preview URLs still generated (but broken)
   - No validation that backend container is running before spawning jobs
   - VNC proxy fallback: If `VNC_BASE_URL` set, uses proxy; otherwise direct `localhost:XXXX` (won't work remotely)

9. **Electron IPC Message Queue Not Bounded**
   - If Python backend falls behind, stdin buffer can fill
   - Electron may block sending new IPC until backend drains queue
   - No backpressure mechanism; just hope Python processes messages fast enough

10. **Supermemory Integration Fragile**
    - LLM-powered long-term memory stored in external Supermemory service
    - No offline fallback; if service down, memory operations fail silently
    - `SUPERMEMORY_API_KEY` in `.env` but no validation at startup

11. **Rowboat Update Checker Runs Every 60s**
    - Background thread polls GitHub every 60s for new Rowboat releases
    - On slow connections, health check can time out (5s) and mark service as "unhealthy" even if fine
    - Can be disabled by not initializing `_rowboat_update_checker` (but code doesn't support this)

12. **Canvas Node ID Mapping Can Desync**
    - Local int IDs mapped to DB UUIDs in `node_id_map` and `db_id_map`
    - If Electron sends node_id that wasn't loaded from DB, map lookup returns None
    - Canvas node operations silently fail if ID mismatch (no warning logged)

13. **Spaces Not All Implemented as Python**
    - Ideas, Desktop, Coding, Shuttles exist as Python spaces
    - Rowboat, MiroFish, AgentFarm are Docker-only (no native Python equiv)
    - Voice commands for Docker spaces will fail if containers not running

## Summary

The Voice backend is a 1918-line Python coordinator that glues Supabase (bubbles), OpenAI Realtime (voice), Redis (event bus), Rowboat (knowledge graph), and a swarm of backend agents into a cohesive 3D AI workspace. It runs as a subprocess of the Electron main process, communicating via JSON IPC on stdin/stdout. Isolated testing requires Supabase + Redis + OpenAI key minimum. Full feature set (Rowboat sync, Automation_ui, eyeTerm) requires additional Docker services and camera hardware. Several critical pieces are optional, env-gated, or incomplete (Brain routing, OpenFang dispatch, native STT/TTS).
