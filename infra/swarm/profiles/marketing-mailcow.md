# Marketing + n8n + Mailcow

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

The Marketing + N8N + Mailcow area is VibeMind's multi-channel marketing operations system integrated with workflow automation and self-hosted email infrastructure. It orchestrates lead discovery, audience building, campaign management, and email/multi-channel delivery (28 production-ready OpenFang channels: Telegram, Slack, LinkedIn, Discord, Mastodon, etc.) with a 12-gate security pipeline that enforces DSGVO compliance and prevents accidental external sends. The system is phase-1 (read-only for end-user operations, but the infrastructure stack is deployment-ready).

## Services / Components

**Docker Swarm Stack Services** (from `infra/swarm/vibemind-stack.yml:579-623`):

- **n8n** (Workflow Engine)
  - Image: `vibemind-n8n:latest`
  - Port: `127.0.0.1:15678:5678` (host-published, loopback only per E6; on Swarm the bind address is dropped — see `docs/runbooks/n8n-loopback-binding.md`)
  - Container port: `5678`
  - Volumes: `n8n_data:/home/node/.n8n`
  - Network: `vibemind-shared`
  - Environment: N8N_API_DISABLED=false, N8N_API_KEY, N8N_ENCRYPTION_KEY (from .env), GENERIC_TIMEZONE=Europe/Berlin
  - Health probe: `wget --spider -q http://localhost:5678/healthz` (10s interval, 30s start_period)

**External Services** (NOT in stack, native/WSL deployment):

- **Mailcow** (WSL native)
  - URL: https://127.0.0.1:8443 (admin), SMTP:465 (TLS)
  - Domain: `vibemind.space` with DKIM 2048-bit keys
  - Service accounts: `marketing@vibemind.space`, `noreply@vibemind.space`
  - 50 test audience mailboxes (Faker-generated, credentials in `docs/test-audience.json`)
  - Loopback-mode active: Postfix rejects external recipients with `554 LOOPBACK-MODE`
  - Environment: MAILCOW_URL, MAILCOW_API_KEY (in .env)

- **Mailpit (in-stack, from supabase-inbucket service)**
  - Web UI: http://127.0.0.1:54324
  - SMTP receive: 127.0.0.1:54325
  - API: http://127.0.0.1:54324/api/v1/messages
  - Environment: MAILPIT_WEB_URL, MAILPIT_SMTP_HOST, MAILPIT_SMTP_PORT (in .env)

**Native Python Services** (launched from `Vibemind.debug.ps1` or standalone):

- **Marketing API HTTP** (`spaces/marketing/api/server.py`)
  - Port: 5510 (default, via MARKETING_HTTP_PORT)
  - Bind: 127.0.0.1 (default, via MARKETING_HTTP_BIND)
  - Routes: /api/health, /api/stats, /api/audiences, /api/templates, /api/campaigns, /api/inbox, /api/n8n/* (audit gates)
  - Auth: Optional via MARKETING_API_KEY (X-API-Key header)

- **Marketing Agent Runner** (`spaces/marketing/agents/runner.py`)
  - Standalone Redis stream consumer
  - Stream: `events:tasks:marketing`
  - Consumer group: `marketing-runner`
  - Redis URL: `redis://localhost:6379/0` (default, via REDIS_URL)
  - Dispatches 13 event types to tools in `spaces.marketing.tools.marketing_tools`

- **Marketing Sync Workers** (`spaces/marketing/sync/`)
  - Worker A (`worker_db_to_fs.py`): Drains `marketing.sync_outbox`, renders .md files to `~/.rowboat/knowledge/Marketing/People/`
  - Worker B (`worker_fs_to_db.py`): Watches vault folder, propagates deletes to DB
  - Worker C (`worker_imap_sync.py`): Mailcow IMAP → `marketing.inbound_messages` table (Phase 2)
  - Postgres access: `docker exec psql` via SSH

- **Marketing Send Worker** (`spaces/marketing/workers/send_worker.py`)
  - CLI: `python -m spaces.marketing.workers.send_worker --campaign-id <uuid> --mode dry_run|shadow|live`
  - Modes: dry_run (no SMTP, returns token), shadow (redirects to Mailpit), live (Mailcow SMTP + 12-gate enforcement)
  - SMTP config: SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_PORT (465 TLS, from .env)

- **Marketing Delivered Webhook Worker** (`spaces/marketing/workers/delivered_webhook.py`)
  - Only writer of `campaign_sends.delivered_at` (rule: hard-coded write gate)
  - Listener for webhook callbacks from Mailcow/Mailpit

## Dependencies

**UPSTREAM (what Marketing needs)**:

- **Supabase** (Stack service `supabase-kong:54321`)
  - Schema: `marketing.*` with 13 tables (deployed 2026-05-26)
  - DDL: `spaces/marketing/db/001_marketing_schema.sql`
  - Tables: accounts, emails, strategies, runs, tags, email_tags, audiences, audience_members, templates, campaigns, campaign_sends, inbound_messages, audit_log
  - Auth: Phase-1 admin-only (service-role-key); Phase-2 Supabase-Auth + RLS
  - Access: SUPABASE_URL=http://host.docker.internal:54321, SUPABASE_ANON_KEY_FILE

- **Redis** (Stack service `rowboat-redis:6379` OR host `redis://localhost:6379/0`)
  - Queue: `events:tasks:marketing` stream (consumer-group: `marketing-runner`)
  - Status: `events:tasks:marketing:status` stream
  - Maximum retention: STREAM_MAXLEN=~1000 (approximate)

- **Qdrant** (Stack service `qdrant:6333`)
  - Collections: `brain-artifacts`, `rowboat-embeddings` (marketing uses via rowboat Rowboat RAG context for reply enrichment in Phase 2)
  - Marketing doesn't write directly; only reads via Rowboat client

- **Rowboat** (Stack service `rowboat:3100`)
  - API: http://rowboat-mongo:27017/rowboat (MongoDB), Redis: rowboat-redis:6379
  - Marketing reads knowledge base for context enrichment (`tools/rowboat_client.py`)
  - Vault sync: `~/.rowboat/knowledge/Marketing/People/` (markdown, synced by Worker A/B)

- **n8n** (Stack service `n8n:15678`)
  - Workflows: 4 JSON files in `spaces/marketing/n8n_workflows/`
  - API: http://localhost:15678 (via N8N_API_URL from .env)
  - Credentials: Header Auth with N8N_API_KEY (from .env)
  - Webhooks: POST /webhook/marketing-* (inbound_classifier, reply_enrichment, approval_orchestrator, linkedin_broadcast)

- **OpenFang** (Native binary, host :4200)
  - API: http://host.docker.internal:4200 (or http://127.0.0.1:4200 from native processes)
  - Agent: `marketing-sender` (`vibemind-os/openfang/agents/marketing-sender/agent.toml`)
  - Tool: `channel_send` (single-purpose, strictly JSON-parsed, hardcoded to refuse non-channel_send calls)

- **Ollama** (Native, host :11434)
  - Model: `phi3:mini` (for inbound email classification, Phase 1)
  - Access: http://host.docker.internal:11434/v1 (from containers) or http://127.0.0.1:11434 (from native)
  - Gate: MARKETING_CLASSIFIER_ALLOW_OLLAMA=true enables classification

- **Mailcow SMTP** (External, WSL native)
  - Host: `localhost:465` (TLS)
  - Credentials: SMTP_USER=marketing@vibemind.space, SMTP_PASS (32-char random, from .env)
  - Block: Postfix loopback-block rejects external recipients

**DOWNSTREAM (what calls Marketing)**:

- **Brain Core** (Stack service `brain-core:5000`)
  - Can invoke marketing.* events via voice-assistant or desktop UI (not yet wired Phase 1)
  - Reads marketing capabilities from `capabilities.yaml` (config mounted at brain-core:/app/data/capabilities.yaml)

- **Telegram Bot / Discord Bot / Slack Workspace** (via OpenFang channels)
  - Approval-handler agent sends cards for curator approval (Phase 2)
  - Callback webhooks fire on curator decision

- **Email Clients / List Recipients**
  - Receive campaign sends (Mailcow outbound), inbound replies (Mailcow IMAP → marketing.inbound_messages)

## Possible usages

**What you can actually DO with Marketing-Ops in Phase 1**:

1. **List audiences, templates, campaigns** (read-only)
   - HTTP: `GET /api/audiences?q=name_substr` → marketing_tools.list_audiences()
   - Event: `marketing.list_audiences` → agent runner → tool
   - Data: `marketing.audiences` table rows with member_count, filter_dsl, created_at

2. **Get audience member count**
   - HTTP: `GET /api/audiences/{id}/count`
   - Event: `marketing.audience_count {audience_id}` → marketing_tools.audience_count()
   - Security: Applies investor-lockout filter in real-time (not just at send time)

3. **List templates**
   - HTTP: `GET /api/templates?q=name_substr`
   - Event: `marketing.list_templates` → marketing_tools.list_templates()
   - Data: channel (email/telegram/linkedin/mastodon/discord/etc.), subject, body_text, body_html, variables

4. **Check inbox** (inbound mails from last 7 days)
   - HTTP: `GET /api/inbox`
   - Event: `marketing.inbox` → marketing_tools.get_inbox_unread()
   - Data: from_email, subject, received_at, is_bounce, is_autoreply, linked_send_id

5. **Get marketing stats**
   - HTTP: `GET /api/stats`
   - Event: `marketing.stats` → marketing_tools.get_stats()
   - Data: total audiences, templates, campaigns, inbound_count, etc.

6. **Create audience** (add filter_dsl + name)
   - HTTP: `POST /api/audiences` (requires MARKETING_PROPOSAL_API_KEY)
   - Event: `marketing.create_audience {name, filter_dsl}` → marketing_tools.create_audience()
   - Write: Inserts into `marketing.audiences`, triggers `marketing.emit_sync_event()`

7. **Create template** (email/channel body + variables)
   - HTTP: `POST /api/templates` (requires MARKETING_PROPOSAL_API_KEY)
   - Event: `marketing.create_template {name, channel, subject, body_text, body_html, variables}` → marketing_tools.create_template()
   - Write: Inserts into `marketing.templates`

8. **Send campaign (dry-run only in Phase 1)**
   - HTTP: `POST /api/campaigns/{id}/send?dry_run=true` (returns token, never opens SMTP)
   - Event: `marketing.send_campaign {campaign_id, dry_run=true}` → marketing_tools.send_campaign()
   - Gate-checks: All 12 gates applied, but SMTP blocked by MARKETING_SEND_ENABLED=false (default)

9. **Voice triggers** (when voice-swarm integration lands Phase 2)
   - "Show me my marketing inbox"
   - "How many people in the designers audience?"
   - "Create a template for LinkedIn outreach"
   - Routes via Brain intent classifier → MarketingBackendAgent → tools

10. **n8n Webhooks** (already wired)
    - `POST /webhook/marketing-inbound-classifier` (schema: event_kind, data.needs_review, data.pre_classification)
    - `POST /webhook/marketing-reply-enrichment` (for Reply-workflow, Phase 2)
    - `POST /webhook/marketing-approval-orchestrator` (for Curator-approval, Phase 2)
    - `POST /webhook/marketing-linkedin-broadcast` (LinkedIn campaign dispatch, Phase 2)

11. **MCP Tools** (listed in Brain capabilities, when wired)
    - `marketing_list_audiences()`, `marketing_audience_count()`, `marketing_list_templates()`, `marketing_list_campaigns()`, `marketing_inbox()`, `marketing_create_audience()`, `marketing_create_template()`, `marketing_send_campaign(dry_run=true)`

12. **Sync Vault (Rowboat Knowledge)**
    - Worker A renders each account/email pair to `~/.rowboat/knowledge/Marketing/People/<handle>.md` (markdown)
    - Worker B watches for deletions, propagates back to DB
    - Used by Rowboat RAG engine for context (which emails are "warm" leads, engagement history, etc.)

## MCPs & OpenFang agents involved

**OpenFang Agents** (from `vibemind-os/openfang/agents/`):

- **marketing-sender** (`marketing-sender/agent.toml`, line 1–76)
  - Purpose: Single-purpose dispatcher for VibeMind marketing
  - Module: `builtin:chat`
  - Model: `ollama:qwen2.5-coder:7b` (cheap, deterministic)
  - Temperature: 0.0 (zero randomness)
  - System prompt: Receives strict MARKETING-SEND-V1 JSON instruction, parses, invokes `channel_send` EXACTLY ONCE, refuses any deviation
  - Tool: **channel_send** (ONLY tool, hardcoded in system prompt)
  - Resources: 5k tokens/hour max (single tool call per turn)
  - Network: None (channel_send is kernel-builtin, routes via kernel.outbound_send ACL)
  - MCP servers: None

- **brain-n8n** (`brain-n8n/agent.toml`, line 1–46)
  - Purpose: n8n workflow CRUD + execution router
  - Module: `builtin:chat`
  - Model: `openrouter:anthropic/claude-3.5-sonnet`
  - MCP servers: `vibemind-db`, `n8n` (from vibemind-os/openfang/agents/brain-n8n/agent.toml line 45)
  - Tools: `memory_store`, `memory_recall`

- **approval-handler** (Phase 2, sends curator-approval cards via Telegram/Slack/Discord)
  - Receives `reply_proposal_created` webhook, dispatches to OpenFang channels
  - Awaits callback with approve/reject decision
  - Not yet live

**MCP Servers** (when Brain wires Marketing):

- **vibemind-db** (Supabase REST API via Kong :54321)
  - Used by brain-n8n for schema queries
  - Marketing integration: read `marketing.*` tables

- **n8n** (n8n API at :15678)
  - Used by brain-n8n to trigger workflows
  - Marketing workflows: 01_inbound_classifier, 02_reply_enrichment, 03_approval_orchestrator, 04_linkedin_broadcast

**Messenger/Clawdbot integration** (for Marketing in ClawPort UI):

- Not yet wired in Phase 1
- Planned Phase 2: ClawPort Marketing-Tab will display campaigns, audiences, inbox
- Messenger MCP (OpenClaw extensions) will relay marketing.* events from Brain to UI

## Isolated startup

**Minimum services to test Marketing-Ops in isolation**:

```
STEP 1: Docker Swarm Stack (core infrastructure)
  docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind
  
  Services to wait for:
  - qdrant:6333 (healthcheck: 1/1)
  - supabase-kong:54321 (healthcheck: 1/1)
  - rowboat-mongo:27017 (healthcheck: 1/1)
  - rowboat-redis:6379 (healthcheck: 1/1)
  - rowboat:3100 (healthcheck: 1/1)
  - n8n:5678 (healthcheck: 1/1, start_period 30s)
  
  CRITICAL: supabase-db must have marketing.* schema deployed
  (503 response if schema missing). Apply if not present:
    docker cp spaces/marketing/db/001_marketing_schema.sql vibemind_supabase-db.1.<task-id>:/tmp/
    docker exec vibemind_supabase-db.1.<task-id> psql -U supabase_admin -d postgres -f /tmp/001_marketing_schema.sql

STEP 2: Native services (host processes)
  A. Redis (if stack rowboat-redis is not accessible)
     redis-server --port 6379
  
  B. Ollama (if using MARKETING_CLASSIFIER_ALLOW_OLLAMA=true)
     ollama serve
     ollama pull phi3:mini
  
  C. OpenFang (for channel_send + approval handler)
     GROQ_API_KEY=<key> target/release/openfang.exe start &
     curl http://127.0.0.1:4200/api/health  # verify running

STEP 3: Marketing API server
  cd c:\Users\User\Desktop\Vibemind_V1
  python -m spaces.marketing.api.server
  
  Expected output:
    [INFO] INFO:     Uvicorn running on http://127.0.0.1:5510
  
  Test: curl http://127.0.0.1:5510/api/health
  Response: {"success": true, "message": "OK"}

STEP 4: Marketing Agent Runner (optional, for voice-driven events)
  cd c:\Users\User\Desktop\Vibemind_V1
  python -m spaces.marketing.agents.runner
  
  Expected output:
    [INFO] Created consumer group marketing-runner
    [INFO] Listening for events...

STEP 5: Marketing Sync Workers A+B (optional, for vault sync)
  Terminal A:
    cd c:\Users\User\Desktop\Vibemind_V1
    PYTHONIOENCODING=utf-8 python -m spaces.marketing.sync.worker_db_to_fs
  
  Terminal B:
    cd c:\Users\User\Desktop\Vibemind_V1
    PYTHONIOENCODING=utf-8 python -m spaces.marketing.sync.worker_fs_to_db

STEP 6: Mailcow (EXTERNAL, WSL native — if testing SMTP)
  # If not already running:
  cd ~/mailcow-deployment
  docker-compose up -d
  # Wait for Postfix ready: docker logs mailcow_postfix-mailcow* | grep "ready to accept mail"

STEP 7: Test connectivity
  # Supabase
  curl http://127.0.0.1:54321/rest/v1/marketing.audiences \
    -H "Authorization: Bearer $(jq -r .anon_key ~/.supabase/config.toml)" 2>/dev/null || echo "OK (auth gate)"
  
  # n8n
  curl http://127.0.0.1:15678/healthz
  
  # Marketing API
  curl http://127.0.0.1:5510/api/stats
  
  # Rowboat
  curl http://127.0.0.1:3100/
  
  # OpenFang
  curl http://127.0.0.1:4200/api/health
```

**GAPS / Known Missing Pieces** (Phase 1 limits):

- [ ] IMAP sync (Worker C) not deployed — `marketing.inbound_messages` is empty
  - Requires IMAP_* credentials in .env (user: marketing@vibemind.space, pass: SMTP_PASS)
  - Run manually: `python -m spaces.marketing.sync.worker_imap_sync` (one-shot poll)

- [ ] Live send (MARKETING_SEND_ENABLED=true) blocked by design until consent_given_at gate is implemented
  - Phase 2: add CHECK constraint to enforce `consent_given_at IS NOT NULL` before inserting campaign_sends rows
  - Current: send_worker raises NotImplementedError on live mode

- [ ] n8n workflows (4 JSON files) require manual UI import + webhook subscription setup
  - See `spaces/marketing/n8n_workflows/README.md` for step-by-step

- [ ] Brain integration not yet wired
  - No capabilities.yaml entry for marketing.* events
  - Voice-commands won't route to MarketingBackendAgent until vibemind-os/voice wires the agent pool

- [ ] ClawPort Marketing-Tab not yet built (Electron UI mockup exists only as HTML/CSS)
  - File: `spaces/marketing/mockup/index.html`

## Key files

**Schema & Migrations**:
- `spaces/marketing/db/001_marketing_schema.sql:25–240` — DDL for 13 tables (accounts, emails, audiences, campaigns, etc.)
- `spaces/marketing/db/_live_marketing_dump_2026-06-02.sql` — pg_dump snapshot (reference only)

**Core Agents/Tools**:
- `spaces/marketing/agents/marketing_agent.py:1–100` — BaseBackendAgent shim + PARAM_MAPPING for 13 event types
- `spaces/marketing/agents/runner.py` — Standalone Redis stream consumer (MARKETING_CONSUMER_GROUP)
- `spaces/marketing/tools/marketing_tools.py:1–150` — Tool façade: list_audiences, list_templates, list_campaigns, audience_count, get_inbox_unread, etc.
- `spaces/marketing/tools/_send_paranoid.py` — 12-gate Phase-2 send-worker (currently dry-run only)

**API & HTTP Routes**:
- `spaces/marketing/api/server.py:1–100` — FastAPI server, /api/health, /api/stats, /api/audiences, /api/templates, /api/campaigns, /api/inbox, /api/n8n/* (with _require_n8n_key auth gate)

**Sync & Vault**:
- `spaces/marketing/sync/_db.py` — Postgres access via docker exec psql (fallback from long-lived Connection)
- `spaces/marketing/sync/render_md.py` — Pure function: handle → markdown string (frontmatter + body)
- `spaces/marketing/sync/worker_db_to_fs.py` — Drains `marketing.sync_outbox`, writes .md files
- `spaces/marketing/sync/worker_fs_to_db.py` — Watches `~/.rowboat/knowledge/Marketing/People/`, propagates deletes
- `spaces/marketing/sync/worker_imap_sync.py` — Mailcow IMAP → `marketing.inbound_messages` (Phase 2, undeployed)

**N8N Workflows**:
- `spaces/marketing/n8n_workflows/01_inbound_classifier.json` — Webhook → Filter → Ollama classify → PATCH /api/n8n/inbound_messages/{id}/classify
- `spaces/marketing/n8n_workflows/02_reply_enrichment.json` — (Phase 2 plan) Classified reply → Rowboat context → proposal draft
- `spaces/marketing/n8n_workflows/03_approval_orchestrator.json` — (Phase 2 plan) Approval card → OpenFang → awaits curator decision
- `spaces/marketing/n8n_workflows/04_linkedin_broadcast.json` — (Phase 2 plan) LinkedIn campaign execution

**OpenFang Agents**:
- `vibemind-os/openfang/agents/marketing-sender/agent.toml:1–76` — Single-purpose dispatcher, `channel_send` only, JSON-enforcement system prompt
- `vibemind-os/openfang/agents/brain-n8n/agent.toml:1–46` — n8n workflow router, MCP servers: vibemind-db, n8n

**Environment & Config**:
- `.env` — SMTP_*, MAILCOW_*, MAILPIT_*, MARKETING_*, N8N_* variables (from grep output above)
- `infra/swarm/vibemind-stack.yml:579–623` — n8n service definition, ports, volumes, healthcheck
- `spaces/marketing/README.md` — High-level overview, architectural decisions, next steps
- `spaces/marketing/AGENTS.md` — Hard Rules (7 critical), Gate graph (15 layers), Module map (8 blocks)

## Gotchas

**Known Traps** (from code comments and testing):

1. **Loopback-Mode Active** — Postfix rejects ANY recipient not `@vibemind.space` with `554 LOOPBACK-MODE`. This is intentional, not a bug. To test live sending, disable with `scripts/_mailcow_outbound_block.sh` (requires manual command on host, not containerized).
   - File: `spaces/marketing/AGENTS.md:85-86` mentions the gate + reference to postfix check_recipient_access PCRE.
   - Verify: `curl -X POST http://127.0.0.1:5510/api/campaigns/{id}/send -d '{"dry_run":false}'` should fail with "554 LOOPBACK-MODE" error in logs.

2. **Consent Gate NOT YET ENFORCED** — `consent_given_at` is never written by Phase-1 code (by design). Phase-2 must add a CHECK constraint forcing `consent_given_at IS NOT NULL` before send. Until then, any inserted email is treated as "consented" (assumption). 
   - Rule from `spaces/marketing/AGENTS.md:15-16`: "Never write `consent_given_at` to non-NULL from code."
   - Tests guard this: `test_*.py` files in `spaces/marketing/tools/tests/` will fail CI if any path violates this.

3. **`investor_already_sent` Trigger-Only** — Only the DB trigger `trg_flip_investor_sent` (migration 005) can set this. Worker D is the only process calling `mark_delivered()` (which updates the linked campaign_send row's delivered_at, firing the trigger). Manually setting this column = instant audit-log violation.
   - Rule from `spaces/marketing/AGENTS.md:17-19`.
   - Defense: FK + CHECK constraints.

4. **N8N Workflows Require Manual Import** — The 4 JSON files in `n8n_workflows/` are NOT auto-deployed. Manual UI import needed via http://127.0.0.1:15678 (Workflows → Import from File) + credential wiring (Header Auth with MARKETING_N8N_API_KEY).
   - Workflow: `01_inbound_classifier.json` activated first; 02/03/04 are Phase-2 placeholders.
   - Gotcha: If import fails, check Kong proxy reachability (supabase-kong must be 1/1 healthy).

5. **Docker-Exec Postgres Access is Slow** — `_db.query_via_docker()` spawns `docker exec` for each query (~150ms latency per render). Phase-1 acceptable for 14k handles / 80 minutes rendering. Phase-2 must switch to long-lived `psycopg.Connection` + LISTEN/NOTIFY for push-based updates.
   - File: `spaces/marketing/sync/_db.py` and `spaces/marketing/sync/README.md:84`.

6. **Rowboat Vault Path Must Exist** — Workers A/B expect `~/.rowboat/knowledge/Marketing/People/` to exist. If path is missing, Worker B's watchdog fails silently (no startup error). Create manually if needed: `mkdir -p ~/.rowboat/knowledge/Marketing/People`.
   - Env: `MARKETING_VAULT_DIR` (default: `~/.rowboat/knowledge/Marketing/People/`).
   - Verify: `ls -la ~/.rowboat/knowledge/Marketing/` should show `People/` and `.sync_hashes.json`.

7. **Redis Consumer Group Lifecycle** — The `marketing-runner` consumer group is created on first run (`_ensure_group()` in `agents/runner.py`). If the group exists with old consumers, `xreadgroup` may block on old entries. To reset: `redis-cli XGROUP DESTROY events:tasks:marketing marketing-runner` then restart runner.
   - Known issue: Multiple runner instances (Phase-2 swarm wiring) must coordinate to avoid double-processing.

8. **n8n API Key Rotation** — N8N_API_KEY in .env must match the key in n8n UI (Settings → Users → Your User → API token). If mismatch, marketing API's _require_n8n_key() gate returns 503 "service misconfigured". To rotate: generate new token in n8n UI, update .env, restart marketing-api.
   - File: `spaces/marketing/api/server.py:141-155` (_require_n8n_key logic).

9. **Mailcow SMTP Credentials Weak Before 2026-05-26** — Legacy felix@vibemind.space used password `Felix1234,1234` (insecure). Rotated 2026-05-26 to `marketing@vibemind.space` with 32-char random in .env. Old scripts/tests referencing `felix@` will fail auth.
   - Cleanup: `grep -r "felix@vibemind" .` should return only comments / .env.bak (backup).

10. **Supabase Schema Not Auto-Created** — `001_marketing_schema.sql` must be manually applied to supabase-db after `docker stack deploy`. If missing, any tool calling `_db.query_via_docker()` gets `ERROR: schema "marketing" does not exist`.
    - Fix: `docker exec vibemind_supabase-db.1.<task-id> psql -U supabase_admin -d postgres -f /tmp/001_marketing_schema.sql`
    - Verify: `docker exec vibemind_supabase-db.1.<task-id> psql -U supabase_admin -d postgres -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='marketing';"`
    - Expected: 13 rows.

11. **OpenFang marketing-sender Refuses Non-JSON** — The agent's system prompt enforces strict MARKETING-SEND-V1 instruction format. If n8n sends malformed JSON or missing `action` field, the agent returns `{"ok": false, "error": "instruction-format"}` with NO retry. n8n must handle error + log for manual review.
    - File: `vibemind-os/openfang/agents/marketing-sender/agent.toml:36-50` (rule #5, #6).

12. **Phase-1 Tests Skip Send-Worker** — `test_send_paranoid.py` has `@pytest.mark.skip("send-worker gates are intentionally dry-run-only in Phase 1")`. Live-send tests deferred to Phase-2. To manually test: `python -m spaces.marketing.workers.send_worker --campaign-id <uuid> --mode dry_run` (returns token, no SMTP).

---

This reference document is now ready for a developer to start/test the Marketing+N8N+Mailcow area in isolation. Every claim is grounded in actual file lines from the codebase.
