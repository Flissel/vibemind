# Flowzen (Blaue Rose — Circadiane Intelligenz)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

Flowzen (Blaue Rose / Blue Rose) is a **passive circadian intelligence layer** that observes all system activity in VibeMind without proactively asking users for input. It tracks activity patterns, infers circadian state, and sends periodic situation summaries to the Brain/Tahlamus for cognitive decision-making. When users explicitly ask "Was soll ich machen?" (What should I do?), the system generates neuroscience-backed task recommendations based on circadian rhythm analysis.

## Components

**Core Files (voice/python/)**
- `/spaces/flowzen/` (git submodule: `https://github.com/Flissel/flowzen.git`)
  - `activity_tracker.py` — Passive broadcast listener, circadian matrix, periodic summary generation
  - `config.py` — FlowzenConfig dataclass, env-driven configuration  
  - `agents/flowzen_agent.py` — Minimal BackendAgent (only 2 tools: rose.recommend + rose.status)
  - `tools/flowzen_tools.py` — Task recommendation engine, status reporting
  - `brain_bridge.py` — (stub/referenced in tests) Bridges flowzen summaries to Brain cognitive layer

**Data Layer (voice/python/data/)**
- `flowzen_repository.py` — CRUD for circadian tracking (checkins, activity log, diary entries, recommendations)
- `models.py` — FlowzenCheckin, FlowzenActivity, FlowzenDiaryEntry dataclasses (lines 903-1020)
- `supabase_database.py` — Drop-in DB abstraction (Supabase PostgREST or SQLite)

**UI/Electron (voice/electron-app/)**
- `flowzen-manager.js` — BrowserView overlay for diary display
- `flowzen-diary.html` — HTML diary UI with page-flip book design
- `flowzen-preload.js` — IPC bridge for diary → Python communication
- `renderer/flowzen-panel.js` — 3D Electron panel (glass dome rose visual)

**Event Routing & Registry**
- `swarm/event_team/event_router.py:46` — STREAM_TASKS_FLOWZEN constant + rose.* mappings (lines 215-218)
- `swarm/backend_agents/__init__.py` — get_flowzen_agent() lazy loader
- `swarm/orchestrator/intent_classifier.py` — Intent → rose.recommend, rose.status classification guidance
- `data/space_capabilities/flowzen.yml` — Auto-generated tool inventory (7 tools declared)

**Configuration & Docs**
- `data/space_capabilities/flowzen.md` — Tool documentation
- `voice/docs/superpowers/plans/2026-03-20-blaue-rose-flowzen-space.md` — Complete TDD plan (1739 lines)

**Testing**
- `voice/python/tests/test_flowzen_*.py` — 8 test files (models, repository, tracker, agent, brain_bridge, diary, diary_generation, integration)

**No Ports**: Flowzen is in-process; uses Redis streams + Python async callbacks for inter-space communication.

## Dependencies

**Upstream (what Flowzen needs)**
- `swarm.event_team.event_router` — Registers rose.* events to STREAM_TASKS_FLOWZEN (event_router.py:215-218)
- `data.flowzen_repository.FlowzenRepository` — Database access for activity logging + recommendation tracking (flowzen_repository.py:14-193)
- `data.models.FlowzenCheckin/Activity/DiaryEntry` — Data models (models.py:902-1020)
- `llm_config.get_async_client()` — LLM for neuroscience-backed reasoning generation (activity_tracker.py:796-830)
- `spaces.ideas.repository.IdeasRepository` — Fetches ideas for recommendation matching (flowzen_tools.py:165)
- Redis (implicit) — EventRouter publishes to events:tasks:flowzen stream (event_router.py:46)

**Downstream (what calls Flowzen)**
- `swarm.orchestrator.intent_orchestrator` — Must wire ActivityTracker.on_intent() for broadcast (as per Task 6 in plan)
- `brain.tahlamus` / Brain cognitive layer — Receives periodic summaries → decides action
- Desktop/UI handlers — Consume rose.* event responses, trigger Electron UI updates
- Voice/Rachel — User says "Was soll ich machen?" → intent_classifier → rose.recommend event

**Related but separate**
- `tribev2` (TriBE submodule) — Bio-personalization system (mentioned in memory hint "flowzen-loop=next")
- `rowboat` — Knowledge graph (not directly coupled, but Brain may reference rowboat context)
- `coding`, `ideas`, `bubbles` spaces — Send intents that Flowzen observes passively

## Possible usages

**Voice Triggers (German)**
- "Was soll ich machen?" → `rose.recommend` → recommend_task() with circadian matrix
- "Blaue Rose Status" / "Flowzen Status" → `rose.status` → get_flowzen_status()
- (Passive broadcast) Any intent → ActivityTracker.on_intent() silently logged

**API/Tools (space_capabilities/flowzen.yml:1-98)**
1. `set_electron_sender(sender: Callable)` — Register IPC callback for 3D rose state updates (flowzen_tools.py:18)
2. `recommend_task(mood: str)` — LLM-powered circadian recommendation (flowzen_tools.py:28, 157-243)
3. `accept_recommendation(recommendation_log_id)` — Mark recommendation as accepted for preference learning (flowzen_tools.py:207, 237-254)
4. `get_flowzen_status()` — Tracker state + circadian info (flowzen_tools.py:237, 1257-1273)
5. `FlowzenAgent.name`, `.stream` — Agent properties (flowzen_agent.py:33, 37, 1322-1327)
6. `get_flowzen_agent()` — Singleton accessor (flowzen_agent.py:65, 1353-1357)

**Capabilities Invocation Pattern**
- EventRouter.get_stream("rose.recommend") → "events:tasks:flowzen" (event_router.py:216)
- FlowzenAgent listens to stream, calls EVENT_TO_TOOL["rose.recommend"] → "recommend_task" (flowzen_agent.py:1311-1314)
- Tools access global state (tracker, repo) + generate response via LLM

## Integration points

**Brain Bridge** — Flow of circadian state to cognitive layer
- ActivityTracker.send_periodic_summary() → builds JSON summary with intent_count, time_window, event_types (activity_tracker.py:911-967)
- Summary sent to Brain via _brain_callback (activity_tracker.py:958-966)
- Brain responds with {"action": "suggest_task"|"suggest_rest"|"do_nothing"} → on_brain_response() updates 3D rose state (activity_tracker.py:994-1009)
- Tests: test_flowzen_brain_bridge.py validates rule-based fallback when Brain unavailable (line 10-42)

**Rowboat Integration** — Knowledge context for recommendations
- recommend_task() fetches IdeasRepository to pick best-scored child idea (flowzen_tools.py:1246-1254)
- Future: Could query rowboat for semantic context (not yet implemented)

**Bubbles & Ideas Spaces** — Passive observation target
- All intents (idea.create, bubble.enter, code.generate) copied to ActivityTracker.on_intent() broadcast
- Tracker buffers event_types in memory, counts frequency for circadian patterns

**Openfang/Coding Engine** — Not directly integrated; Flowzen observes code.* events passively

**Electron UI** — 3D Rose Visualization
- FlowzenManager (flowzen-manager.js:17-150) creates BrowserView for diary
- Tools call `_broadcast_to_electron({"type": "flowzen_rose_state", "state": "active"|"recommending"|"rest"})` (flowzen_tools.py:1226-1229)
- Rose visual updates in real-time as activity/recommendations flow

## Isolated startup

**Minimal Standalone Test (no Brain/UI needed)**

```bash
# 1. Database + models ready
cd vibemind-os/voice/python
python -c "from data.models import FlowzenCheckin, FlowzenActivity; print('Models OK')"

# 2. Repository works
python -c "from data.flowzen_repository import FlowzenRepository; print('Repo OK')"

# 3. ActivityTracker runs
python -c "
from spaces.flowzen.activity_tracker import get_activity_tracker
t = get_activity_tracker()
t.on_intent('idea.create', {})
print('Tracker:', t.get_status())
"

# 4. Agent loads
python -c "from spaces.flowzen.agents.flowzen_agent import FlowzenAgent; a = FlowzenAgent(); print(a._load_tools().keys())"

# 5. Full tools work
python -m pytest voice/python/tests/test_flowzen_*.py -v
```

**What Must Be Up to Run Isolated**
- Python 3.9+ with dependencies (dataclasses, asyncio, sqlite3 or Supabase SDK)
- Database (SQLite via supabase_database.py or Supabase cloud)
- Optional: LLM via llm_config (GPT 5.4 or configured model) for reasoning generation; falls back to static template if unavailable

**What IS Stubbed/Incomplete**
1. **Flowzen submodule not cloned** — spaces/flowzen/flowzen/ directory missing (referenced in flowzen_agent.py imports, but entire implementation lives in voice/python/)
2. **Brain Bridge partial** — test_flowzen_brain_bridge.py exists with mock tests, but FlowzenBrainBridge class imports suggest external design (test line 7: `from spaces.flowzen.brain_bridge import FlowzenBrainBridge`)
3. **Three.js Glass Rose** — flowzen-panel.js + flowzen-diary.html are Electron stubs; 3D rendering not implemented (plan Task 8 future extension)
4. **Periodic Summary Timer** — ActivityTracker.send_periodic_summary() is idempotent but no background scheduler integrated (needs APScheduler or threading.Timer from IntentOrchestrator)
5. **Mood Inference Engine** — Always defaults to last checkin or config default_mood; no learned mood detection (plan Task 2 future)

## Key files

| File | Line | Purpose |
|------|------|---------|
| `voice/python/data/flowzen_repository.py` | 14-193 | FlowzenRepository CRUD: checkins, activity, diary, recommendations |
| `voice/python/data/models.py` | 902-1020 | FlowzenCheckin, FlowzenActivity, FlowzenDiaryEntry dataclasses |
| `voice/python/spaces/flowzen/activity_tracker.py` | (entire; plan lines 687-1055) | Core: broadcast listener, circadian matrix, summary builder |
| `voice/python/spaces/flowzen/agents/flowzen_agent.py` | (lines 1287-1361 in plan) | MinimalAgent, EVENT_TO_TOOL, PARAM_MAPPING |
| `voice/python/spaces/flowzen/tools/flowzen_tools.py` | (lines 1125-1274 in plan) | recommend_task(), get_flowzen_status(), LLM reasoning |
| `voice/python/swarm/event_team/event_router.py` | 46, 215-218 | STREAM_TASKS_FLOWZEN constant + rose.* routing |
| `voice/python/tests/test_flowzen_*.py` | (8 files) | Comprehensive test coverage for all layers |
| `voice/docs/superpowers/plans/2026-03-20-blaue-rose-flowzen-space.md` | (lines 1-1739) | Complete TDD spec for full implementation |

## Gotchas

1. **Flowzen is NOT a general router** — Only handles rose.recommend + rose.status. Will return None for rose.mood, rose.history, etc. Tests explicitly verify this (test_flowzen_agent.py:11-14).

2. **Rose NEVER asks proactively** — Passive observation only. Periodic summaries go to Brain, not directly to user. Only explicit user query (Was soll ich machen?) triggers visible recommendation.

3. **Submodule not cloned by default** — `git submodule update --init spaces/flowzen/flowzen` required if implementation is in external repo. Currently all code lives in voice/python/; external space_flowzen reference is for future modular design.

4. **LLM reasoning optional** — If llm_config fails or model unavailable, falls back to category name (activity_tracker.py:829-830). Tests mock LLM to avoid API calls.

5. **Database migrations not applied automatically** — Tests use `db.initialize()` which creates schema, but production needs schema v18+ (flowzen_checkins, flowzen_activity tables). Check supabase_database.py for migration path.

6. **Async/sync boundary** — recommend_task() bridges async LLM calls in sync context using ThreadPoolExecutor workaround (flowzen_tools.py:1195-1207). Can be fragile in event loop.

7. **No built-in scheduler** — send_periodic_summary() is idempotent but requires external timer (APScheduler, threading.Timer). Not hooked into IntentOrchestrator yet (Task 6 in plan).

8. **Circadian matrix hardcoded** — CIRCADIAN_MATRIX (activity_tracker.py:720-761) maps mood × time_window to task categories. No ML-based mood inference; always falls back to last checkin or default_mood = "calm". Future enhancement: learn mood from activity frequency + time gaps.

9. **German-only classifier hints** — intent_classifier.py suggests German keywords ("empfehlung", "vorschlag", "blaue rose"). English support requires separate training.

10. **Memory hint "flowzen-loop=next"** — Related to TriBE bio-personalization (tribev2 submodule). Loop closure not yet implemented; Flowzen → TriBE biometric feedback chain is WIP.
