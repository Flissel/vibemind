# Schedule (Scheduling-Schicht systemweit)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Schedule Space is a voice-controlled task scheduling system for VibeMind that combines APScheduler (a robust Python job engine), German natural language time parsing, and SQLite persistence. It enables users to create reminders, alarms, and recurring tasks via voice commands like "Erinnere mich in 5 Minuten an den Termin" (remind me in 5 minutes about the appointment), with automatic execution through either direct voice injection or multi-space Minibook collaboration.

## Components

### Core Files

| File | Purpose | LOC |
|------|---------|-----|
| `spaces/schedule/__init__.py` | Module exports + setup | 67 |
| `spaces/schedule/config.py` | `ScheduleConfig` dataclass, env loading | 52 |
| `spaces/schedule/agents/schedule_agent.py` | `ScheduleBackendAgent` — Redis stream router | 126 |
| `spaces/schedule/nlp/time_parser.py` | Regex-based German time expression parser | 300+ |
| `spaces/schedule/tools/schedule_tools.py` | 6 tool functions (create/list/cancel/modify/status/snooze) | 538 |
| `spaces/schedule/workers/schedule_worker.py` | `ScheduleWorker` — APScheduler wrapper + job lifecycle | 369 |

**Data layer** (voice/python/):
- `data/models.py:ScheduledTask` — dataclass with id, title, action_text, trigger_type, trigger_config, execution_mode, timezone, status, run_count, max_runs
- `data/schedule_repository.py:ScheduledTaskRepository` — SQLite CRUD + active task loader

**Brain agent config**:
- `brain/the_brain/configs/agents/brain-scheduler.yaml` — Routes schedule.* events to brain-scheduler agent

### Ports & Services

| Service | Port | Role |
|---------|------|------|
| Redis Streams | (via REDIS_URL) | Event stream: `events:tasks:schedule` |
| SQLite | (via `data/` dir) | Task persistence (survives restarts) |
| APScheduler | In-process | Job execution engine (MemoryJobStore) |
| Electron IPC | Native | Result delivery via `session.inject_system_message()` |
| Minibook | localhost:3480 | Multi-space collaboration (if execution_mode=complex) |
| OpenFang | localhost:4200 | Agent dispatch (via Brain bridge) |

## Dependencies

### Upstream (What Schedule Needs)

- **APScheduler >=3.10.0** — Job scheduling; installed via `pip install APScheduler>=3.10.0` (spaces/schedule/workers/schedule_worker.py:66)
- **Redis** — Event stream consumer (voice/python/ipc/voice_manager.py uses get_redis() for stream reading)
- **SQLite** — Task persistence (data/schedule_repository.py uses Database from data/supabase_database.py)
- **IntentOrchestrator** — SIMPLE execution mode dispatch (spaces/schedule/workers/schedule_worker.py:_execute_task calls _get_orchestrator().process_intent_sync(action_text))
- **Minibook** — COMPLEX execution mode (spaces/schedule/workers/schedule_worker.py:_execute_task calls Minibook.start_collaboration() for multi-space tasks)
- **OpenAI Realtime Session** — Voice injection target (voice_manager.py:_get_session() provides session for job callback)

### Downstream (Who Calls Schedule)

- **Brain (brain-scheduler agent)** — Routes schedule.* events from IntentClassifier (brain/the_brain/configs/agents/brain-scheduler.yaml registers 6 event types)
- **Voice Manager** — Initializes ScheduleWorker on app startup, passes session + orchestrator getters (voice/python/ipc/voice_manager.py:_schedule_worker startup)
- **Backend Agent Registry** — Auto-registers `ScheduleBackendAgent` from `get_schedule_agent()` (voice/python/swarm/backend_agents/__init__.py)
- **Tool Registry** — Exposes 6 schedule tools to orchestrator (voice/python/swarm/orchestrator/tool_registry.py imports schedule_tools)
- **Rowboat Scheduled Jobs** (TypeScript, separate domain) — Independently manages scheduled-job-rules in MongoDB (spaces/rowboat/.../scheduled-job-rules/) — NOT integrated with this Python Schedule Space; different lifecycle/UI

## Possible Usages

### Voice Triggers (German + English)

| Phrase | Event | Tool | Example |
|--------|-------|------|---------|
| "Erinnere mich in 5 Minuten" | schedule.create | create_scheduled_task | "Erinnere mich in 5 Minuten an den Termin" |
| "um 14 Uhr" | schedule.create | create_scheduled_task | "um 14 Uhr anrufen" (at 2 PM call) |
| "jeden Montag um 9" | schedule.create | create_scheduled_task | "jeden Montag um 9 Uhr Standup" (every Monday 9 AM standup) |
| "täglich um 8" | schedule.create | create_scheduled_task | "täglich um 8 Uhr aufwachen" (daily 8 AM wake up) |
| "in einer halben Stunde" | schedule.create | create_scheduled_task | "in einer halben Stunde erinnern" (in 30 min remind) |
| "alle 2 Stunden" | schedule.create | create_scheduled_task | "alle 2 Stunden Status check" (every 2 hours status check) |
| "Zeige mir meine Aufgaben" | schedule.list | list_scheduled_tasks | Show all active tasks |
| "Abbrechen, Aufgabe XYZ" | schedule.cancel | cancel_scheduled_task | Cancel task by title or ID |
| "Ändere die Zeit auf..." | schedule.modify | modify_scheduled_task | Modify trigger time or action |
| "Schedule Status" | schedule.status | get_schedule_status | Summary: active count, next 3 upcoming |
| "Verschiebe um 10 Minuten" | schedule.snooze | snooze_scheduled_task | Snooze by N minutes |

### NLP Time Patterns (time_parser.py:45-250)

| Pattern | Regex Match | Result Trigger Type | Example |
|---------|-------------|-------------------|---------|
| `in X Minuten/Stunden/Tagen` | `\bin\s+(\d+\|eine[mnr]?...)\s+(minuten?\|stunden?\|...)` | DateTrigger(now + duration) | "in 5 Minuten" → now+5min |
| `in einer halben Stunde` | `\bin\s+einer?\s+halben\s+stunde` | DateTrigger(now + 30min) | "in einer halben Stunde" → now+30min |
| `um HH:MM / HH Uhr` | `\bum\s+(\d{1,2})(?::(\d{2}))?\s*(?:uhr)?` | DateTrigger(today@HH:MM or tomorrow) | "um 14 Uhr" → today 14:00 or tomorrow if past |
| `jeden [Wochentag] um HH` | `\b(?:jeden?)\s*(?:woche\s+)?(montag\|dienstag\|...)\s+um\s+(\d{1,2})` | CronTrigger(day_of_week, hour) | "jeden Montag um 9" → every Mon 09:00 |
| `täglich um HH` | `\b(?:täglich\|jeden\s+tag)\s+um\s+(\d{1,2})` | CronTrigger(hour) | "täglich um 8" → daily 08:00 |
| `alle X [Einheiten]` | `\balle\s+(\d+\|eine[mnr]?...)\s+(minuten?\|stunden?\|...)` | IntervalTrigger(hours/days) | "alle 2 Stunden" → every 2hrs |

### API/Tool Interface

**Tool signatures** (spaces/schedule/tools/schedule_tools.py:83-514):

```python
create_scheduled_task(user_text: str = '', title: str = '') → dict
  # Returns: {"status": "created", "task_id": "...", "next_run": "...", "trigger": "..."}

list_scheduled_tasks(status: str = '') → dict
  # Returns: {"tasks": [...], "active": N, "paused": N}

cancel_scheduled_task(task_id: str = '', title: str = '') → dict
  # Returns: {"status": "cancelled", "task_id": "..."}

modify_scheduled_task(task_id: str = '', title: str = '', new_time: str = '', new_action: str = '') → dict
  # Returns: {"status": "modified", "task_id": "...", "new_trigger": "..."}

get_schedule_status() → dict
  # Returns: {"active": N, "paused": N, "next_3": [task, ...], "summary": "..."}

snooze_scheduled_task(task_id: str = '', title: str = '', minutes: int = 5, user_text: str = '') → dict
  # Returns: {"status": "snoozed", "task_id": "...", "new_run_at": "..."}
```

### Capabilities (data/space_capabilities/schedule.yml)

| Registry Event | Tool Hint | Required Params |
|----------------|-----------|-----------------|
| `schedule.create` | db_schedule_create | title, trigger_config |
| `schedule.list` | db_schedule_list | – |
| `schedule.cancel` | db_update | task_id |
| `schedule.modify` | db_update | task_id |
| `schedule.status` | db_schedule_list | – |
| `schedule.snooze` | db_update | task_id |
| `openclaw.cron` | db_schedule_create | cron_expr |

## Integration Points

### Brain → Schedule

**Routing path** (brain-scheduler agent):
1. IntentClassifier detects `schedule.*` event
2. Brain forwards to `events:tasks:schedule` Redis stream (config: spaces/schedule/config.py:22)
3. ScheduleBackendAgent consumes stream (schedule_agent.py:78)
4. EVENT_TO_TOOL map routes to correct tool (schedule_agent.py:32-39)
5. PARAM_MAPPING normalizes German aliases to English params (schedule_agent.py:42-70)

**Event mapping** (schedule_agent.py):
- schedule.create → create_scheduled_task(user_text, title)
- schedule.list → list_scheduled_tasks(status)
- schedule.cancel → cancel_scheduled_task(task_id, title)
- schedule.modify → modify_scheduled_task(task_id, title, new_time, new_action)
- schedule.status → get_schedule_status()
- schedule.snooze → snooze_scheduled_task(task_id, title, minutes)

### Rowboat (Separate Scheduled Job Rules)

**Note: Rowboat's scheduled-job-rules (TypeScript) are INDEPENDENT and NOT integrated with this Python Schedule Space.**

- **Rowboat model** (scheduled-job-rule.ts): MongoDB document with projectId, nextRunAt, workerId, status, input/output
- **Purpose**: Manage project-level automation rules (CI/CD workflows, project triggers)
- **Execution**: Rowboat's own worker pool (infrastructure/repositories/mongodb.scheduled-job-rules.repository.ts)
- **Different UI**: Manage-triggers UI at `/projects/[projectId]/manage-triggers/scheduled`
- **No Voice Integration**: Rowboat scheduled rules are configured programmatically, not via voice

### Minibook Collaboration (Multi-Space)

If action_text requires >1 space (detected via SPACE_KEYWORDS match):
1. execution_mode auto-detects as COMPLEX (schedule_tools.py:59-76)
2. APScheduler triggers _execute_task(task_id)
3. _execute_task calls Minibook.start_collaboration(task.action_text) (schedule_worker.py:200-220)
4. Minibook orchestrates parallel space execution
5. Result captured, awaited, then injected via session.inject_system_message()

### Coding Engine (Independent Schedulers)

**Note: Coding Engine has its own scheduler hierarchy (SEPARATE from Schedule Space):**
- task_scheduler.py:TaskScheduler — DAG-based task scheduling for job pipelines
- agent_priority_scheduler.py:AgentPriorityScheduler — Priority queue for agent dispatch
- agent_batch_scheduler.py — Batch execution of tasks
- These handle code generation pipelines, NOT user-facing reminders/alarms

## Isolated Startup

To test Schedule Space in isolation:

### Prerequisites

```bash
# 1. Install APScheduler
pip install APScheduler>=3.10.0

# 2. Enable in .env
SCHEDULE_ENABLED=true
SCHEDULE_TIMEZONE=Europe/Berlin
SCHEDULE_MAX_CONCURRENT=5
SCHEDULE_MISFIRE_GRACE=60

# 3. Dependencies must be up
# - Redis (for event stream: events:tasks:schedule)
# - SQLite (automatic, via data/ dir)
```

### Startup Order

**Option A: Native Python (Voice backend directly)**

```bash
cd vibemind-os/voice/python

# 1. Start electron backend (includes ScheduleWorker init)
python -m ipc.electron_backend

# ScheduleWorker starts automatically in voice_manager.py:
#   - Loads active tasks from SQLite
#   - Registers with APScheduler
#   - Wires Electron IPC for result delivery
```

**Option B: Docker Compose (if one exists)**

Currently, no dedicated `docker-compose.schedule.yml` exists. The Schedule Space runs embedded in the voice backend, not as a standalone container.

**Gaps/Incomplete Parts:**

1. **No async startup hooks** — ScheduleWorker.start() is awaited in voice_manager but there's no sentinel or health-check; if Redis is down, the stream never connects
2. **No persistent jobstore** — APScheduler uses MemoryJobStore (fast but lost on restart). SQLite provides recovery, but there's no state machine to track "was this job already running when we crashed?"
3. **No Docker image** — Schedule Space is voice-embedded, not containerized; no isolated testing without spinning up full voice backend
4. **No MCP server bridge** — The MCP servers listed in agent.toml (vibemind-db, scheduled-tasks) are registered but not validated at startup; if they're down, tool execution silently fails

### Minimal Test

```python
# Direct Python test (no voice/IPC needed)
from spaces.schedule.tools.schedule_tools import create_scheduled_task, list_scheduled_tasks
from spaces.schedule.config import get_config

# Override env
import os
os.environ['SCHEDULE_ENABLED'] = 'true'

# Create a task
result = create_scheduled_task(
    user_text="Erinnere mich in 5 Minuten",
    title="Test Task"
)
print(result)  # {"status": "created", "task_id": "...", ...}

# List tasks
tasks = list_scheduled_tasks()
print(tasks)  # {"tasks": [...], "active": 1, ...}
```

## Key Files (Load-Bearing Code)

| File | Critical Lines | Role |
|------|-----------------|------|
| spaces/schedule/config.py:28-40 | ScheduleConfig.from_env() | Loads SCHEDULE_* env vars; if SCHEDULE_ENABLED=false (default), space is inert |
| spaces/schedule/nlp/time_parser.py:65-88 | parse_time_expression() | Entry point; tries each regex parser in priority order; returns ParsedTime or None |
| spaces/schedule/nlp/time_parser.py:95-132 | _parse_in_x_minutes() | Handles "in 5 Minuten", "in einer halben Stunde", etc. |
| spaces/schedule/nlp/time_parser.py:185-208 | _parse_jeden_wochentag() | Handles "jeden Montag um 9" (recurring weekly) |
| spaces/schedule/tools/schedule_tools.py:59-76 | _detect_execution_mode() | Auto-detects SIMPLE vs COMPLEX based on action_text space count |
| spaces/schedule/tools/schedule_tools.py:83-187 | create_scheduled_task() | Parse time + persist to DB + register with APScheduler + broadcast to Electron |
| spaces/schedule/workers/schedule_worker.py:63-99 | ScheduleWorker.start() | Initialize APScheduler, load active tasks from DB, register jobs |
| spaces/schedule/workers/schedule_worker.py:197-240 | _execute_task() | Job callback; fetches task, decides SIMPLE vs COMPLEX, executes, injects result or queues |
| spaces/schedule/agents/schedule_agent.py:32-39 | EVENT_TO_TOOL map | Route schedule.* events to correct tool function |
| voice/python/ipc/voice_manager.py:_worker_init | Schedule space startup | Called on app init; instantiates + awaits ScheduleWorker.start() |
| data/schedule_repository.py:20-65 | ScheduledTaskRepository.create() | Persist task to SQLite; if create() fails, task is lost + not registered with APScheduler |

## Gotchas

1. **SCHEDULE_ENABLED defaults to false** — If you forget to set `SCHEDULE_ENABLED=true`, all schedule.* events are silently ignored. No warnings or errors (spaces/schedule/config.py:29).

2. **APScheduler MemoryJobStore loss on crash** — If the app crashes, APScheduler loses all in-memory jobs. Recovery relies on ScheduleWorker.start() reloading from SQLite (schedule_worker.py:89-98), but this is only called once at startup; there's no crash-restart watcher.

3. **No time-zone conversion** — Default timezone is Europe/Berlin (config.py:19). If a user in EST creates a task with "um 14 Uhr", it triggers at Berlin 14:00, not EST 14:00. Timezone awareness is not baked into voice parsing.

4. **Regex parsing is fragile** — Time parser uses regex only (no LLM), so edge cases break:
   - "in 1 Minute" (singular) vs "in 2 Minuten" (plural) — both handled, but inconsistent German grammar confuses it
   - "in einer Stunde" → recognized, but "in 1 Stunde" (digit + word) → NOT recognized (expects word or digit, not both)
   - Special chars (ä, ö, ü) handled via raw strings (r"\bfünf"), but user voice input via Whisper may normalize to "funf" → mismatch

5. **No retry on job failure** — If _execute_task(task_id) throws, APScheduler logs it but doesn't retry or escalate. Task status stays ACTIVE but never fires again (schedule_worker.py:214).

6. **No job cancellation from UI** — Tasks can only be cancelled via voice tool or direct DB edit; no Electron UI exists to visually manage active tasks. Rowboat has one (spaces/rowboat/.../manage-triggers/scheduled) but it's separate.

7. **COMPLEX execution blocks the job callback** — When _execute_task() calls Minibook.start_collaboration() (schedule_worker.py:217), it awaits the result synchronously in the job thread. If Minibook hangs, APScheduler job blocks (could back up other jobs if SCHEDULE_MAX_CONCURRENT is small).

8. **No deduplication** — If a user says "in 5 Minuten erinnern" twice in quick succession, TWO tasks are created (same title, same time). User must manually cancel one via voice.

9. **Execution mode detection is naive** — _detect_execution_mode() tries to import SPACE_KEYWORDS from minibook; if minibook is not installed or broken, it defaults to SIMPLE (schedule_tools.py:74). No error reporting.

10. **Electron IPC sender not validated** — set_electron_sender() stores a callback (schedule_tools.py:40), but if Electron crashes or IPC closes, _broadcast_to_electron() silently fails (schedule_tools.py:51-52). Result is not persisted or logged.

11. **No concurrent job limit enforcement** — APScheduler max_instances config (schedule_worker.py:79) is per-job, not global. If 10 jobs all trigger at once and each spawns a Minibook collaboration, all 10 run in parallel regardless of SCHEDULE_MAX_CONCURRENT (which only limits concurrent job slots in the scheduler, not downstream execution).

12. **SQLite auto-vacuuming not configured** — schedule_repository.py uses database.execute() with no VACUUM or ANALYZE; over time (thousands of tasks), SQLite file size grows and queries slow (no index maintenance documented).

## Status

**Completeness**: ~70% (core features shipped, edge cases unfinished)

- ✅ **Complete**: Time parsing (regex, 6 patterns), APScheduler integration, SQLite persistence, Brain routing, voice tool API
- ⚠️ **Partial**: Electron UI (only result injection, no management UI), error recovery (logs errors, no retry), Minibook integration (basic, no timeout/backoff)
- ❌ **Stub/Missing**: Docker image, health checks, time-zone auto-detection, job cancellation UI, concurrent execution metrics, crash-recovery state machine
