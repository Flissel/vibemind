# Desktop-Automation (Automation_ui · eyeTerm · perception)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

Desktop automation is VibeMind's unified system for detecting, analyzing, and controlling desktop UI through LLM-powered agents. It combines perception (screen capture + OCR/vision), handoff orchestration (planning + execution + validation), direct mouse/keyboard actions, messaging integration (Clawdbot), VibeMind bubble/brain bridges, and experimental eye-tracking (eyeterm). The system exposes 19 perception tools via MCP (`mcp_server_perception.py`), integrates with Automation_ui's FastAPI backend (port 8007), and connects to multiple downstream systems: Rowboat (Electron UI), voice control, coding automation, and bubbles/ideas.

## Components

**Core MCP Servers (stdio-based, in `backend/moire_agents/`):**
- `mcp_server_perception.py:33-117` — Main perception MCP entry point. Wraps `mcp_server_handoff.py` handlers. Exposes 19 tools: handoff_*, vision_analyze, claude_cli_*, app_launch, app_focus, skill_*.
- `mcp_server_handoff.py:1-650` — Shared handler library (144-650 TOOLS list). Contains dual handler dicts: `_ASYNC` (13 async tools) and `_SYNC` (10 sync tools). Singletons: PlanningTeam, ValidationTeam, AgentRuntime, ClaudeCLIWrapper.
- `mcp_server_messenger.py` — Clawdbot messaging bridge (routed through handoff_clawdbot_* tools).
- `mcp_server_document.py` — Document scanning (visual/file-based).
- `mcp_server_data.py` — Data analytics/reporting.
- `mcp_server_git.py` — Git operations.

**Automation_ui FastAPI Backend (port 8007):**
- `/backend/app/main.py:1-230` — FastAPI factory with routers: api_v1, client_manager, desktop, health, mcp_bridge, workflows, automation, clawdbot, clawhub, configs, llm_intent, eyeterm, shell, websocket, e2e_tests.
- `/backend/app/routers/mcp_bridge.py:1-80` — HTTP bridge proxying to mcp_server_handoff handlers. Maps REST endpoints to _SYNC/_ASYNC handlers. Phase 0.2 cleanup (imported from in-tree moire_agents).
- `/backend/app/routers/eyeterm.py:1-38` — Status proxy for eyeterm process (port 8099), toggles cursor control.
- `/backend/app/routers/automation.py:1-60` — Click, type, hotkey, scroll REST endpoints.
- `/backend/app/routers/desktop.py:1-80` — Live desktop streaming status + configure.
- `/backend/app/core/config.py:15-107` — Settings. Default port 8000 (overrideable via env). CORS allows localhost:3000, :3003, :8007, :5173.
- `/backend/app/routers/websocket.py` — WebSocket manager + task queue bridge (Redis → WebSocket for voice).

**Agent System (`backend/moire_agents/agents/`):**
- `handoff/orchestrator_agent.py` — Top-level handoff orchestrator. Calls planning, execution, validation teams.
- `handoff/planning_team.py:1-60` — LLM-powered planner + critic (Society of Mind). Uses OpenRouterClient for Claude Sonnet 4.
- `handoff/validation_team.py` — Validates UI state post-action (screenshot → vision analysis).
- `handoff/runtime.py:56-610` — AgentRuntime singleton (session state, event queue, recovery agent, pattern store, memory collector).
- `handoff/execution_agent.py` — Executes plan steps (hotkey, sleep, write, press, click, find_and_click).
- `handoff/recovery_agent.py` — Phase 2 recovery: retries failed steps via replan.
- `handoff/vision_handoff_agent.py` — Vision-based UI analysis (Gemini via OpenRouter).
- `handoff/window_focus.py` — Window focus + title matching.
- `orchestrator_v2.py` — Event-driven orchestrator (legacy; also in module tree for backward compat).
- `reasoning.py`, `interaction.py`, `vision_agent.py` — Component agents for reasoning, mouse/keyboard, vision.
- `subagents/` — Specialist subagents (background, planning, vision, vision tasks).

**Screen Capture + OCR Stack:**
- `handoff/geometry_ocr.py` — Layered text extraction (UIA → Tesseract → MoireServer).
- `/backend/moire_agents/stream_frame_cache.py` — Frame cache for live streaming.
- OCR Engine container (Dockerfile.ocr, port 8008): Tesseract + EasyOCR.

**MoireTracker (UI Detection, TypeScript/WebSocket):**
- `moire_tracker/` — Standalone TypeScript server (port 8765 default). Detection pipeline, OCR service, CNN classification.
- Canvas embed (Electron integrable via iframe/webview), postMessage API, WebSocket API.
- Communicates with Python backend via WebSocket client in `backend/moire_agents/bridge/websocket_client.py`.

**EyeTerm (Eye-Tracking, SEPARATE SPACE):**
- Location: `vibemind-os/spaces/desktop/eyeterm/` (NOT in Automation_ui).
- Proxied through Automation_ui at `http://localhost:8007/api/eyeterm/*` (status proxy).
- Direct endpoints at `http://localhost:8099/*` (MJPEG stream + future /gaze, /dwell-wait, /calibrate).
- Bridge: `agents/handoff/eyeterm_bridge.py:1-100` — 5 tools (handoff_eyeterm_*). Gaze tracking, dwell detection, calibration. INCOMPLETE: /gaze, /dwell-wait, /calibrate NOT YET implemented in eyeterm space (line 19-20).

**Voice Control:**
- `voice/main.py:1-50` — Interactive/listen/command modes.
- `voice/intent_parser.py`, `voice/command_executor.py`, `voice/speech_to_text.py`, `voice/text_to_speech.py`.
- `voice/serve_vapi.py` — Vapi.ai bridge for real-time voice.

**VibeMind Bridges:**
- `handoff/vibemind_bridge.py:1-80` — Phase 7 COM. Accesses bubbles (IdeasRepository), brain (classify/train/stats), UI (Electron IPC), minibook (agent dispatch). Path: `vibemind-os/voice/python/` (try/except fallback for missing modules).

**Database + Caching (Docker Compose):**
- PostgreSQL (port 5432): Automation_ui state.
- Redis (port 6379/6381): PubSub, task queue, sessions.
- Qdrant (port 6333): Vector DB for skill embeddings.

**Skills & Patterns:**
- `_SKILL_LIB_ROOT` = `C:\Users\User\Desktop\Vibemind_V1\vibemind-os\skills` (handoff/mcp_server_handoff.py:106).
- Indexed via skill_search, skill_list, skill_save_and_index tools.

**Services:**
- `services/manager.py` — ServiceManager: initializes all background services (live_desktop, action_router, etc.).
- `services/action_router.py` — Routes action types to handlers.
- `service/service_manager.py`, `service/process_manager.py`, `service/health_monitor.py` — Process lifecycle.

## Dependencies

**Upstream (needs to run first):**
- **Brain (port 5000)** — classify/train/stats API (vibemind-os/brain/the_brain/). Called via vibemind_bridge.py.
- **VibeMind Python API** — IdeasRepository, IntentOrchestrator, ElectronIPC bridge. Path: `vibemind-os/voice/python/`. Imports try/except guarded.
- **Rowboat Electron UI** — Frontend (port 5173/3000). Calls backend at :8007/ws, :8007/api/*.
- **OpenRouter API Key** — LLM calls (Claude Sonnet 4, GPT-4V). Set via OPENROUTER_API_KEY env var.
- **Redis** — PubSub, task queue bridge (setup_task_queue_bridge in routers/websocket.py:63-65).
- **PostgreSQL** — DB (initialization in app/main.py:40-47).
- **Qdrant (optional)** — Vector embeddings for skill search.

**Downstream (callers):**
- **Claude Code CLI** — via `claude_cli_run`, `claude_cli_skill` tools. ClaudeCLIWrapper in orchestrator.py.
- **Rowboat Electron** — WebSocket + REST calls to :8007 (desktop_router, mcp_bridge, websocket).
- **Voice agents** — voice/main.py routes intents to CommandExecutor, which calls handoff_execute, handoff_validate.
- **Clawdbot** — Messaging integration (whatsapp, telegram, discord, signal, email). Routed via mcp_server_messenger.
- **Bubbles/Brain** — vibemind_bridge.py creates/updates bubbles, routes intents via process_intent().
- **Coding-Engine** (openfang) — Desktop automation for code generation tasks.

**Real refs:**
- `mcp_server_handoff.py:93-140` — Agent imports + singleton getters.
- `mcp_server_perception.py:31` — Imports mcp_server_handoff as H.
- `mcp_bridge.py:31-35` — Path injection for moire_agents imports.
- `main.py:12-26` — Router imports (15 total).
- `eyeterm_bridge.py:43-45` — HTTP endpoints (:8007/api/eyeterm, :8099).
- `vibemind_bridge.py:43-55` — Python path setup for voice/python.

## Possible usages

**MCP Tools (19 total, from mcp_server_perception.py lines 37-83):**

1. **Handoff Planning/Execution/Validation:**
   - `handoff_plan(goal, context)` — LLM-powered plan creation (Planning + Critic).
   - `handoff_execute(plan, speed_factor=1.0, goal, recovery=False)` — Run steps. Recovery phase 2 opt-in.
   - `handoff_validate(target, expected_state)` — Find UI element + validate state (vision-based).
   - `handoff_action(action_type, params)` — Direct actions: hotkey, type, press, click, sleep, scroll.

2. **Screen & Interaction:**
   - `handoff_read_screen(region, monitor_id=0, include_screenshot=False, with_vision=False, vision_prompt, prefer_uia=True, text_source="auto")` — Multi-monitor OCR (UIA → Tesseract). Returns text, screenshot_path, vision analysis.
   - `handoff_scroll(direction, amount=3, x, y)` — Scroll at position.
   - `handoff_get_focus()` — Get active window.
   - `handoff_status()` — Runtime stats.

3. **Vision Analysis:**
   - `vision_analyze(prompt, mode="custom", json_output=True, monitor_id=0)` — Gemini vision (element_detection, state_analysis, task_planning, custom). Cached frames.

4. **App Lifecycle:**
   - `app_launch(app_name, args)` — Start application.
   - `app_focus(title_substring)` — Bring window to front.
   - `app_list_running()` — List active windows.
   - `app_launch_or_focus(app_name, title_hint, args)` — Launch if missing, else focus.

5. **Skills (Adaptive Skill Library):**
   - `skill_search(query, agent, limit=5)` — Fuzzy search SKILL.md tree.
   - `skill_list(app)` — List skills for app.
   - `skill_save_and_index(app, skill_name, frontmatter, body)` — Add to library + reindex.

6. **Claude CLI:**
   - `claude_cli_run(prompt, skill, output_format="text")` — Run prompt via Claude CLI.
   - `claude_cli_skill(skill_name, inputs, ui_context)` — Execute skill.
   - `claude_cli_status()` — Check if Claude CLI available.

7. **Clawdbot Messaging (via mcp_server_messenger.py):**
   - `clawdbot_send_message(recipient, message, platform)` — Send to whatsapp/telegram/discord/signal/imessage/email.
   - `clawdbot_get_contacts(query, limit=10)` — Search/list contacts.
   - `clawdbot_browser_*` — Open URL, search, read page, report findings.

8. **VibeMind Bridges (via vibemind_bridge.py):**
   - `handoff_vibemind_bubble_create/update/list` — Bubble CRUD + UI broadcast.
   - `handoff_vibemind_intent(text)` — Route through process_intent().
   - `handoff_vibemind_brain(operation, params)` — classify/train/stats.
   - `handoff_vibemind_ui_command(command, params)` — Send IPC to Electron.
   - `handoff_vibemind_agent_dispatch(task)` — Queue to minibook.
   - `handoff_vibemind_agents_list()` — List active agents/spaces.

9. **EyeTerm (INCOMPLETE):**
   - `handoff_eyeterm_status()` — Running/calibrated? (implemented, returns best-effort).
   - `handoff_eyeterm_get_gaze()` — Current gaze (x, y, confidence). (STUB: /gaze NOT YET in eyeterm).
   - `handoff_eyeterm_dwell_request(question, dwell_ms=500, timeout_ms=30000)` — Wait for user to dwell (STUB: /dwell-wait NOT YET).
   - `handoff_eyeterm_calibrate()` — GA calibration loop (STUB: /calibrate NOT YET).
   - `handoff_collaborative_select(question, mode="click"|"gaze", timeout_seconds=30)` — High-level POI (gaze or click fallback).

**Voice triggers:** `python voice/main.py --mode listen --wake-word "Hey Moire"` or `--mode command "Öffne Google"`. Maps to intents → handoff_plan → handoff_execute.

**Integration paths:**
- Claude Code CLI: `/claude-cli-run` → claude_cli_run → MCP perception server.
- Rowboat Electron: WebSocket push + REST /api/* endpoints.
- Bubbles: handoff_vibemind_bubble_* → broadcast to UI.
- Brain: handoff_vibemind_brain → HTTP :5000/classify, :5000/train.

## Integration points

**1. Brain (Knowledge Classification):**
- File: `vibemind_bridge.py:200-260` — Calls Brain HTTP API (:5000).
- Tool: `handoff_vibemind_brain(operation, params)`.
- Use: Intent classification, training, stats queries.

**2. Rowboat (Electron UI):**
- File: `app/main.py:83-90`, `routers/websocket.py` — WebSocket manager + IPC bridge.
- Tools: `handoff_vibemind_ui_command` (Electron IPC), desktop_router (streaming status).
- Use: Real-time screen updates, UI commands, click-to-automate overlay.

**3. Bubbles/Ideas:**
- File: `vibemind_bridge.py:160-195` — IdeasRepository CRUD.
- Tools: `handoff_vibemind_bubble_*`, `handoff_vibemind_intent`.
- Use: Create/update ideas from automation tasks, route text through intent engine.

**4. Voice/Vapi:**
- File: `voice/serve_vapi.py`, `voice/command_executor.py`.
- Flow: Vapi audio → STT → IntentParser → CommandExecutor → handoff_execute.
- Use: Voice-triggered desktop automation.

**5. Coding-Engine (openfang):**
- Via: `claude_cli_run`, `claude_cli_skill` MCP tools.
- Use: Generate code, run skills, output as JSON/text.

**6. Clawdbot (Messaging):**
- File: `mcp_server_messenger.py` (separate MCP, routed via handoff_clawdbot_*).
- Platforms: WhatsApp, Telegram, Discord, Signal, iMessage, email.
- Use: Notify users, report findings, two-way messaging.

**7. EyeTerm (Eye-Tracking):**
- File: `eyeterm_bridge.py` (NOT YET complete).
- Status: endpoints :8099/gaze, /dwell-wait, /calibrate NOT IMPLEMENTED.
- Use (future): Gaze-based POI selection, dwell-triggered actions.

**8. Skill Library:**
- Root: `C:\Users\User\Desktop\Vibemind_V1\vibemind-os\skills`.
- Tools: skill_search, skill_list, skill_save_and_index.
- Use: Adaptive library for reusable automation tasks.

## Isolated startup

To run **desktop automation in isolation without the full VibeMind stack:**

**Minimum Setup (Linux/macOS/Windows):**

1. **Clone & cd:**
   ```bash
   cd vibemind-os/spaces/desktop/Automation_ui/backend/moire_agents
   ```

2. **Install Python + deps:**
   ```bash
   pip install -r requirements.txt  # Lines 1-52
   ```

3. **Set env vars:**
   ```bash
   export OPENROUTER_API_KEY=sk-or-v1-...
   export MOIRE_HOST=localhost
   export MOIRE_PORT=8765
   ```

4. **Run MCP perception server directly:**
   ```bash
   python mcp_server_perception.py
   ```
   Listens on stdio. Tool list on stdout after `initialize` handshake.

**Alternatively, run via FastAPI backend (requires Docker):**

```bash
cd Automation_ui
docker-compose up -d
# Waits for postgres:5432, redis:6379, qdrant:6333 health checks.
# Backend listens on :8007
```

**OR bare native backend (no Docker):**

```bash
cd Automation_ui/backend
python -m app.main --port 8007
# Requires: PostgreSQL, Redis, Qdrant running separately or graceful fallbacks.
```

**MoireTracker (UI Detection) startup (separate process):**

```bash
cd Automation_ui/moire_tracker
npm install
npm run dev  # Listens on :8765 (WebSocket)
```

**Gaps (INCOMPLETE for isolated use):**
- **eyeterm endpoints** (:8099/gaze, /dwell-wait, /calibrate) NOT YET IMPL.
- **Brain (:5000)** required for handoff_vibemind_brain. Fallback returns `{available: false}`.
- **Rowboat Electron** required for full UI integration. Backend works headless.
- **Voice/Vapi** optional (cmd-line testing via voice/main.py works standalone).
- **Clawdbot messaging** requires separate mcp_server_messenger + contact registry.
- **Skills library** works if SKILL.md files exist at `vibemind-os/skills/`.

**Single-tool test (MCP only, no HTTP):**

```bash
python -c "
import asyncio, json, sys
sys.path.insert(0, '.')
import mcp_server_handoff as H

async def test():
    goal = 'Find Firefox in taskbar'
    result = await H.handle_plan(goal=goal, context={})
    print(json.dumps(result, indent=2))

asyncio.run(test())
"
```

## Key files

**MCP Entry Points:**
- `mcp_server_perception.py:1-118` — Main perception MCP (stdio).
- `mcp_server_handoff.py:1-650` — Shared handlers + TOOLS list + singletons.
- `mcp_server_messenger.py` — Clawdbot bridge.

**Orchestration & Agents:**
- `agents/handoff/orchestrator_agent.py` — Top-level handoff flow.
- `agents/handoff/planning_team.py:36-60` — LLM planner + critic.
- `agents/handoff/validation_team.py` — Post-action validation.
- `agents/handoff/runtime.py:56-610` — Session management, event queue, recovery.
- `agents/handoff/execution_agent.py` — Step executor.

**Bridges:**
- `agents/handoff/eyeterm_bridge.py:1-300` — Eye-tracking (INCOMPLETE /gaze, /dwell-wait, /calibrate).
- `agents/handoff/vibemind_bridge.py:1-80` — VibeMind API access (bubbles, brain, UI, agents).
- `agents/handoff/document_tools.py` — Document scanning (visual scanning NOT YET wired).

**UI Detection:**
- `moire_tracker/src/server/moire-server.ts` — TypeScript WebSocket server (port 8765).
- `bridge/websocket_client.py` — Python client to MoireServer.

**Backend FastAPI:**
- `app/main.py:1-230` — FastAPI factory, lifespan, routers, CORS.
- `app/routers/mcp_bridge.py:1-80` — REST bridge to MCP handlers.
- `app/routers/eyeterm.py:1-38` — eyeterm status proxy.
- `app/routers/automation.py:1-60` — Click, type, hotkey, scroll REST.
- `app/routers/desktop.py:1-80` — Desktop streaming status.
- `app/core/config.py:15-107` — Settings (port, CORS, storage).

**Voice Control:**
- `voice/main.py:1-50` — Entry point (interactive/listen/command modes).
- `voice/intent_parser.py` — NLP intent routing.
- `voice/command_executor.py` — Execute intents via handoff.

**Configuration & Infrastructure:**
- `docker-compose.yml:1-228` — Full stack (frontend, backend, OCR, postgres, redis, qdrant).
- `backend/moire_agents/llm_config.yml` — LLM model config.
- `requirements.txt:1-52` — Python deps (autogen, pyautogui, websockets, redis, etc.).

**Skills & Libraries:**
- `C:\Users\User\Desktop\Vibemind_V1\vibemind-os\skills\` — Skill.md tree root (handoff/mcp_server_handoff.py:106).

## Gotchas

1. **eyeterm endpoints INCOMPLETE** — `/gaze`, `/dwell-wait`, `/calibrate` NOT YET implemented in `vibemind-os/spaces/desktop/eyeterm/`. Corresponding MCP tools return `{available: false, reason: "endpoint missing"}`. See eyeterm_bridge.py lines 19-20, 277-291. Workaround: use `mode="click"` for collaborative_select instead of gaze.

2. **DPI awareness overhead** — `mcp_server_perception.py` opts into Per-Monitor DPI on Windows (via mcp_server_handoff module init). Singletons (planning/validation teams, vision agent) stay lazy until first use. Cold start ~2-5 sec.

3. **OpenRouter API key required** — Handoff planning & vision analysis use OpenRouter (Claude Sonnet 4, Gemini). No key → silent failure with `{error: "No API key configured"}`. Set OPENROUTER_API_KEY env var.

4. **UIA text extraction platform-specific** — `handoff_read_screen` prefers UIA (Windows native UI Automation) over Tesseract. On macOS/Linux, falls back to Tesseract pixel OCR (slower, less accurate). Set `text_source="tesseract"` to force OCR.

5. **Skill library root hardcoded** — `_SKILL_LIB_ROOT = r"C:\Users\User\Desktop\Vibemind_V1\vibemind-os\skills"` (mcp_server_handoff.py:106). On different machines, skill_search will return empty if this path doesn't exist. Trust boundary is explicit.

6. **Recovery phase 2 opt-in** — `handoff_execute(..., recovery=True)` enables experimental retry via RecoveryAgent + replanning on failure. Default `recovery=False` keeps legacy linear behavior.

7. **Memory & context limits** — handoff_read_screen by default returns `screenshot_path` (not embedded base64) to stay under MCP token limits. Set `include_screenshot=True` if you need inline image data.

8. **Redis optional but recommended** — Task queue bridge (WebSocket ↔ Redis Streams) for voice commands. If Redis unavailable, backend logs warning, continues without pub/sub. Full websocket functionality (streaming, live updates) works even without Redis.

9. **Document scanning visual path NOT YET wired** — `agents/handoff/document_tools.py` has comment "Visual scanning (no path supplied) is not yet wired through this module". File-based document scanning works; live screen document scanning is a stub.

10. **Nested Docker for desktop capture** — docker-compose.yml explicitly notes "Desktop Capture Client MUSS auf dem Host laufen" (must run on host). OCR engine, backend, DB in containers; capture client (`dual_screen_capture_client.py`) on bare metal for physical monitor access.

11. **eyeterm is separate space** — Not part of Automation_ui subdirectory. Located at `vibemind-os/spaces/desktop/eyeterm/`. Proxied by Automation_ui at `:8007/api/eyeterm/*` (status) and accessed directly at `:8099/*` (MJPEG + future gaze endpoints).

12. **Speed factor multiplier default 1.0** — `handoff_execute(..., speed_factor=1.0)` is real-time. Legacy code mentions "2x speedup" (0.5 factor) — now explicit. Use 2.0 to slow down for debugging.

13. **Vision analysis cached frames** — `vision_analyze` uses `stream_frame_cache.py` for recent screenshots. If no cached frame available, falls back to live capture. Caching not persisted across restarts.

14. **Clawdbot contact fuzzy matching** — `clawdbot_send_message(recipient="Peter")` does fuzzy matching against contact registry. Fails gracefully if contact not found (returns error, doesn't crash agent).

15. **Electron IPC bridge best-effort** — `handoff_vibemind_ui_command` sends Electron IPC messages. If Rowboat not running, returns `{available: false}`. All VibeMind bridge tools graceful-degrade when modules missing.

---

**Summary of Completeness:**
- **Core desktop automation**: Fully functional (plan, execute, validate, direct actions, screen read).
- **Vision analysis**: Fully functional via Gemini/OpenRouter.
- **MoireTracker UI detection**: Fully functional (TypeScript server, WebSocket, canvas embed).
- **Voice control**: Fully functional (intent parsing, command execution, optional Vapi.ai bridge).
- **eyeterm eye-tracking**: INCOMPLETE (status proxy works, gaze/dwell/calibrate endpoints NOT YET implemented).
- **Document scanning**: Mostly complete (file-based works, visual scanning stub).
- **VibeMind bridges**: Fully functional (try/except guarded, graceful fallback).
- **Clawdbot messaging**: Fully functional (depends on separate mcp_server_messenger).
- **Skills library**: Fully functional (indexing, search, save).
- **Recovery phase 2**: Working (opt-in via `recovery=True`).
