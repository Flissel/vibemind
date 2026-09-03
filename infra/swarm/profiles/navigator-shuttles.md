# _Navigator + Shuttles (Space-Registry/Resolver)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

**_navigator** is a smart MCP (Model Context Protocol) server that manages navigation across the 14-space VibeMind multiverse, coordinating between voice/UI input and the Electron renderer. It provides three-layer resolution (keyword → embedding → LLM tiebreaker) to map natural language to canonical space IDs, broadcasts navigation state to the Electron UI via CDP/HTTP/stdout, and maintains file-backed navigation history. **Shuttles** is a stub space wrapping SWE Design (a git submodule) that orchestrates bubble→project promotion via a wizard-driven requirements engineering pipeline; it has no dedicated backend agent—shuttle events are handled by BubblesAgent in the ideas space.

## Components

### _navigator MCP Server

| File | Purpose | Lines |
|------|---------|-------|
| `spaces/_navigator/mcp_server.py` | Entry point; defines 11 MCP tools (space_list, space_goto, space_resolve, space_navigate_intent, etc.); runs as `FastMCP("Space-Navigator")` | 15–262 |
| `spaces/_navigator/registry.py` | Single source of truth: SPACES dict with 14 canonical space definitions + metadata (label, event_prefix, stream, aliases, description, use_when, capabilities, renderer_id) | 1–257 |
| `spaces/_navigator/resolver.py` | 3-layer resolver: (1) keyword/alias (instant), (2) Qwen3 embedding cosine similarity, (3) LLM tiebreaker via OpenRouter when top-2 scores within 0.05 delta | 1–295 |
| `spaces/_navigator/state.py` | File-backed navigator state: current space, history stack (max 20), visit_counts; persists to `state.json` next to mcp_server.py; isolated per repo clone | 1–99 |
| `spaces/_navigator/electron_bridge.py` | Broadcast navigation changes to Electron UI via 3 channels: (1) CDP Runtime.evaluate to window.multiverseApp.navigateToSpace (most reliable), (2) HTTP POST to electron_backend bridge, (3) stdout JSON (fallback) | 1–229 |
| `spaces/_navigator/llm_config.py` | Minimal OpenRouter HTTP client for tiebreaker LLM calls; uses `NAVIGATOR_LLM_MODEL` (default gpt-4o-mini), 2s timeout | 1–72 |
| `spaces/_navigator/__init__.py` | Module docstring only | 1–1 |

### Shuttles Space

| File | Purpose | Lines |
|------|---------|-------|
| `spaces/shuttles/wizard_handler.py` | `ShuttleWizardHandler` class orchestrating 4-step wizard (mining → requirements → knowledge_graph → techstack); lazy-loads SWE Design agent teams (ContextEnricher, StakeholderTeam, RequirementGapTeam, ConstraintTeam); manages per-shuttle state, persists to DB | 1–743 |
| `spaces/shuttles/README.md` | Shuttle architecture: pipeline stages (Evaluate → Requirements → Design → Promote), data model (shuttle_id, bubble_id, current_stage, stage_data), BubblesAgent handles events | 1–67 |
| `spaces/shuttles/swe_desgine/` | Git submodule (github.com/Flissel/swe_desgine) — **17-stage enterprise requirements pipeline**, not native to VibeMind | — |

### Data/Config

| File | Purpose |
|------|---------|
| `spaces/_navigator/state.json` | Runtime state: `{"current": "coding", "since": 1780384652.9851196, "history": [...], "visit_counts": {...}}` |
| `data/space_capabilities/shuttles.yml` | Auto-generated inventory: 0 tools, no registry agent, no MCP servers (shuttles is a stub) |

## Dependencies

### UPSTREAM (what _navigator needs)

- **Electron UI + CDP** (Chrome DevTools Protocol on port 9223): Navigator broadcasts via `window.multiverseApp.navigateToSpace(renderer_id)` (set via `NAVIGATOR_USE_CDP=1`; requires `--remote-allow-origins=*` in electron main.js since 2026-06-02: `electron_bridge.py:40–43`)
- **OpenRouter API** (optional, for LLM tiebreaker layer): `OPENROUTER_API_KEY` env var; falls back to keyword/embedding-only if unavailable (`resolver.py:117–139`, `llm_config.py:23–24`)
- **sentence-transformers + numpy** (lazy import for embedding layer): Qwen/Qwen3-Embedding-0.6B model; if missing, resolver falls back to alias-only (`resolver.py:54–81`)
- **FastMCP framework**: MCP server bootstrap (`mcp_server.py:39`, `line 45`)

### DOWNSTREAM (callers of _navigator)

- **voice/python/electron_backend.py** (lines not fully read, but references wizard_handler): Python backend that receives voice commands, routes to spaces via IntentClassifier (`voice/docs/03_spaces.md` and `architecture/space-communication.md` confirm intent dispatch architecture)
- **Electron renderer** (glass_bubbles.js, Multiverse JS scene): Listens for `navigate_to_space` / `space_changed` messages on `window.multiverseApp` namespace; maintains `window.currentSpace` state and `window.multiverseApp.isNavigating` flag (`electron_bridge.py:104–124`)
- **BubblesAgent** (ideas space): Handles `bubble.evaluate` and `bubble.promote` events; calls wizard_handler to enrich shuttle state before promoting to SWE Design (`spaces/shuttles/README.md:12`)
- **SWE Design submodule**: Receives finalized work_package JSON (project metadata, stakeholders, requirements, constraints) from wizard finalization; outputs 17-stage enterprise spec (`wizard_handler.py:303–334`, `INTEGRATION.md`)
- **Rowboat** (knowledge graph space): Receives published wizard results + MiroFish readiness scores via `publish_shuttle_data()` or `publish_wizard_results()` (`wizard_handler.py:549–577`)
- **MiroFish** (predictive space): Optional 30s evaluation of bubble readiness during shuttle init, pre-populates constraints with missing_items (`wizard_handler.py:458–484`)

## Possible Usages

### MCP Tools (_navigator)

**Direct navigation (deterministic):**
- `space_goto(space="n8n")` — Jump to n8n (or any alias: "workflow", "automation-graph", "zapier")
- `space_next(direction="next"|"prev")` — Cycle alphabetically through 14 spaces
- `space_back()` — Pop history stack
- `space_home()` — Reset to "ideas" (multiverse hub)
- `space_current()` — Return active space + since_ts + history[-10:]
- `space_list()` — Enumerate all 14 spaces + metadata
- `space_info(space="coding")` — Detailed space metadata

**Smart resolution (3-layer):**
- `space_resolve(query="I want to research something", top_k=3)` — Returns ranked candidates + which layer decided (alias/embed/llm/fuzzy), no navigation
- `space_navigate_intent(query="where can I research something?")` — Smart resolve + goto in one call (voice-friendly); broadcasts to UI
- `space_suggest(query="build a workflow", top_k=3)` — Top-k with reasoning per candidate (non-mutative)

**Status:**
- `space_recent(limit=5)` — Spaces ranked by visit count
- `space_index_status()` — Embedding index readiness, LLM availability, cache size

### Shuttle Capabilities

Via `wizard_handler.py` singleton:
- **`init_from_bubble(shuttle_id, bubble_id)`** — Pre-populate wizard from bubble metadata (child ideas, canvas nodes, tags); infer domain/target_users/description via LLM; optional MiroFish readiness evaluation
- **`submit_step(shuttle_id, step, data)`** — Save user input for mining/requirements/knowledge_graph/techstack steps
- **`run_agent(shuttle_id, team_name, input_data)`** — Execute ContextEnricher, StakeholderTeam, RequirementGapTeam, or ConstraintTeam; return suggestions
- **`approve_suggestion(suggestion_id)` / `reject_suggestion(suggestion_id, reason)`** — Route suggestions through WizardSuggestionQueue
- **`finalize(shuttle_id)`** — Package wizard data as work_package JSON; mark shuttle as complete in DB; publish to Rowboat; clean up in-memory state
- **`get_state(shuttle_id)` / `load_state_from_shuttle(shuttle_id)`** — State getters for frontend

### Voice Triggers

From `registry.py` SPACES definitions + intent mapping:
- "navigate to n8n" / "go to workflow" / "show me automation" → `space_navigate_intent("build a workflow")` → n8n
- "where can I research something?" → `space_navigate_intent("research")` → research
- "show me bubbles" / "go to ideas" → `space_goto("ideas")`
- "what's next?" → `space_next("next")`
- "go back" → `space_back()`
- "promote this bubble" → BubblesAgent intercepts → `wizard_handler.init_from_bubble()` → shuttle pipeline

### API/MCP Tools (Invocation)

```python
# Direct Python import (not typical MCP pattern)
from spaces._navigator.resolver import resolve, suggest
from spaces._navigator.state import goto, current, back
from spaces._navigator.registry import resolve_alias, SPACES

# MCP client call (e.g., from voice/electron_backend.py)
result = mcp_client.call("space_navigate_intent", {"query": "I want to code something"})
# Returns: {"ok": True, "space": "coding", "confidence": 0.95, "layer": "embed", ...}
```

## Integration Points

### brain / rowboat / bubbles / coding / openfang

- **Ideas (bubbles):** BubblesAgent handles `bubble.evaluate` events; calls `wizard_handler.init_from_bubble()` to bootstrap shuttle from bubble metadata. Bubbles are the source of shuttle pipelines (`spaces/shuttles/README.md:3–5`).
- **Rowboat (knowledge graph):** Receives enriched shuttle data + MiroFish results via `publish_shuttle_data()` or `publish_wizard_results()` for long-term storage and cross-space queries. Navigator doesn't directly call Rowboat, but BubblesAgent + shuttle pipeline do.
- **Coding (vibe-coder):** Navigator's `space_goto("coding")` → Coding Workshop agent handles `code.generate` events. SWE Design finalized work_package is consumed by Coding as project_briefs in `.rowboat/coding/` (`voice/docs/architecture/space-communication.md:82`).
- **Brain (Thalamus):** Navigator state persists in file-backed JSON, but Brain's `the_brain/tribe/tribev2/utils.py` imports from `_navigator` (unclear usage—likely diagnostic or metadata sync).
- **OpenFang:** No direct integration found; may use Rowboat as intermediate for context.

### Electron UI / 3D Multiverse

- **Broadcast path:** `space_goto("n8n")` → `state.goto()` saves state.json → `electron_bridge.navigate("n8n")` → tries (1) CDP to `window.multiverseApp.navigateToSpace("n8n")`, (2) HTTP POST to electron_backend bridge, (3) stdout JSON `__NAV_BROADCAST__`
- **Renderer ID mapping:** `registry.py:206–217` maps canonical space IDs to renderer-side names (e.g. "coding" → "projects", "brain" → "thebrain"). Spaces without 3D representation (minibook, n8n, research, schedule) have `renderer_id=None` and skip CDP (return immediately with "no 3D scene" error).
- **Current implementation gap (G2 from audit):** Electron renderer (glass_bubbles.js) listening wiring not yet confirmed live; CDP default port :9223 + `--remote-allow-origins=*` is **critical for MVP** (`electron_bridge.py:14–15, 42, 114`).

## Isolated Startup

### Prerequisites
- Python 3.10+
- `pip install mcp fastapi` (FastMCP server framework)
- Optional: `pip install sentence-transformers numpy` (for embedding layer; if missing, resolver falls back to keyword-only)
- Optional: `OPENROUTER_API_KEY` env var (for LLM tiebreaker; without it, uses embed→fuzzy fallback)
- Optional: `NAVIGATOR_USE_CDP=1` + Electron running on :9223 with `--remote-allow-origins=*` (for UI sync; without it, navigation state still persists to state.json)

### Launch _navigator standalone
```bash
cd vibemind-os/spaces/_navigator
export NAVIGATOR_EMBED_MODEL="Qwen/Qwen3-Embedding-0.6B"  # or disable embedding
python mcp_server.py
# Listens on stdio for MCP calls
```

### Test via MCP client
```python
import json
import subprocess

proc = subprocess.Popen(
    ["python", "spaces/_navigator/mcp_server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
)

# Send MCP call
call = {
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {"name": "space_resolve", "arguments": {"query": "build a workflow"}}
}
proc.stdin.write(json.dumps(call) + "\n")
proc.stdin.flush()

response = proc.stdout.readline()
print(json.loads(response))
# Expected: {"result": {"space": "n8n", "confidence": 0.85, "layer": "embed", ...}}
```

### Test shuttles wizard handler standalone
```bash
cd vibemind-os/spaces/shuttles
python -c "
from wizard_handler import get_wizard_handler
handler = get_wizard_handler()
result = handler.init_from_bubble('shuttle_1', 'bubble_123')
print(result)
"
# Requires: data models (IdeasRepository, ShuttlesRepository) + DB access
# May fail if swe_desgine submodule not initialized or SWE Design agent teams unavailable
```

### Gaps for isolated testing

1. **Navigator without Electron:** State persists to state.json, but CDP broadcast fails silently (non-fatal). Test via direct state.json inspection.
2. **Shuttles without SWE Design:** Agent teams lazy-load from `spaces/shuttles/swe_desgine/requirements_engineer/wizard/wizard_agents.py`; if missing (submodule not cloned), logs warning and continues with reduced functionality. To test fully: `git submodule update --init --recursive`.
3. **Shuttles without DB:** Persistence layer tries to import `data.ShuttlesRepository` and `data.IdeasRepository`; fails gracefully with log message if DB not available. For isolated test, mock the repository or patch imports.
4. **LLM inference for domain/target_users:** `wizard_handler.py:635–713` tries Ollama, OpenRouter, OpenAI in order; needs at least one `OPENAI_API_KEY` or `OPENROUTER_API_KEY` set. Without it, returns empty strings (non-fatal).
5. **MiroFish readiness eval:** Optional 30s ThreadPoolExecutor call to `spaces.mirofish.tools.mirofish_tools.evaluate_bubble_readiness()` (line 464). If MiroFish not available, logs warning and continues.

## Key Files

Load-bearing files (do not delete):

| File | Line | Reason |
|------|------|--------|
| `spaces/_navigator/registry.py:36–177` | SPACES dict | Single source of truth; every navigation decision depends on this canonical list |
| `spaces/_navigator/resolver.py:54–81` | `_ensure_embed_index()` | Lazy-loads embedding model; critical for layer-2 resolution |
| `spaces/_navigator/electron_bridge.py:47–84` | `_cdp_navigate()` | CDP WebSocket to Electron UI; if removed, navigation doesn't reach renderer |
| `spaces/_navigator/state.py:58–73` | `goto()` function | Persists state to state.json; without it, history/visit_counts lost on restart |
| `spaces/shuttles/wizard_handler.py:66–82` | `_ensure_teams()` | Lazy-loads SWE Design agent teams from submodule; silent no-op if submodule missing |
| `spaces/shuttles/wizard_handler.py:359–499` | `init_from_bubble()` | Collects bubble metadata for shuttle initialization; bridges ideas→shuttles pipeline |

## Gotchas

1. **Embedding model download on first run:** `resolver._ensure_embed_index()` downloads Qwen3-Embedding-0.6B (~380MB) on first layer-2 resolve call. Takes 30–60s, locks the resolver thread. Set `NAVIGATOR_EMBED_MODEL=""` to disable if bandwidth-constrained.

2. **LLM tiebreaker timeout:** OpenRouter calls have 2s default timeout (`llm_config.py:20`). If slow, layer-3 LLM call silently returns None and falls back to layer-2 embed-best. Adjust `NAVIGATOR_LLM_TIMEOUT` env var.

3. **CDP requires Electron remote debug enabled:** If Electron launched without `--remote-allow-origins=*`, CDP WebSocket connection fails with "origin block" error. Navigator will fall back to HTTP/stdout, but UI won't sync reliably. **This was fixed in electron main.js on 2026-06-02** (ref: `electron_bridge.py:114`), but older Electron instances will fail silently.

4. **Renderer ID mismatch:** If a space is registered in `registry.py` but has no corresponding 3D scene in Electron's `window.multiverseApp.spaces`, navigation state.json updates but the 3D renderer doesn't jump (silent no-op on renderer side). Test with `space_info()` to check `renderer_id` before `space_goto()`.

5. **SWE Design submodule must be initialized:** `wizard_handler.py:71` tries to import agent teams from `spaces.shuttles.swe_desgine.requirements_engineer.wizard.wizard_agents`. If submodule not cloned, import fails and `_teams_loaded` is set to True without loading—subsequent `run_agent()` calls return `{"success": False, "error": "Unknown team or team unavailable"}`. Fix: `git submodule update --init --recursive`.

6. **Shuttles has NO tools or dedicated agent:** Unlike coding/ideas/desktop, shuttles has no `tools/` or `agents/` subdirectory (confirmed by `data/space_capabilities/shuttles.yml:tool_count=0`). All shuttle logic is in wizard_handler.py and delegated to SWE Design. This is by design—shuttles is purely a UI + orchestration layer around the swe_desgine submodule. **Do not expect native space events like `shuttle.create` or `shuttle.run`.**

7. **Navigator state.json is **per-repo-clone**:** Each checkout has its own `spaces/_navigator/state.json`. Switching branches/checkouts will reset history + visit_counts. This is intentional for isolation, but can confuse users expecting global nav history.

8. **Wizard handler state is **in-memory only** (after `init_from_bubble`):** The `_states` dict in wizard_handler.py is not persisted during wizard steps unless explicitly `_persist_state()` is called. If the process crashes mid-wizard, in-memory state is lost. State recovery is via `load_state_from_shuttle()` which reads from DB `shuttle.stage_data`, so **DB must be up for crash recovery**.

9. **Voice routing to shuttles is implicit:** There's no direct voice trigger like "start shuttle". Instead, voice says "promote this bubble" → BubblesAgent intercepts `bubble.promote` event → calls wizard_handler → launches wizard UI. The shuttle is created on-demand by BubblesAgent, not by navigator. **Navigator doesn't directly control shuttle lifecycle—it only enables navigation to the Shuttles space UI.**

10. **Embedding cache size is fixed at 256:** `resolver.py:34` has `_CACHE_SIZE = 256` hardcoded. High-volume query patterns (>256 unique queries) will evict old cache entries (LRU). For production scale, consider making this configurable.

---

**Last verified:** 2026-06-02 (navigator CDP integration, electron_bridge.py v1.0). Shuttles is **integration in progress**—scaffold complete, submodule linked, but not yet fully integrated into voice/electron workflows. Test in isolation first; expect gaps in cross-space event routing (G2 from audit).
