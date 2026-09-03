# Proxmox Split Phase 2 + Deploy Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Operational-plan caveat:** unlike a pure code plan, several tasks here act on LIVE systems
> (the local Swarm stack, the Proxmox VM). Those tasks are marked **[LIVE]** and have explicit
> user-approval gates. A subagent must NOT run a `docker stack deploy`, scale services, or touch
> the VM without the gate being explicitly passed. Commit-only tasks carry no such gate.

**Goal:** Activate and validate all staged local-stack changes (embedder migration, mirofish
disable, Promtail redirect, Brain→Proxmox-Neo4j), re-embed the KG, bound the local Supabase
services, verify the concurrent session's Supabase cutover, and establish the multi-session
coordination protocol.

**Architecture:** Split model (spec: `docs/superpowers/specs/2026-07-14-proxmox-split-phase2-design.md`) — Windows keeps Brain/coding/Qdrant + native host processes; Proxmox VM 100
(192.168.178.65) carries background services. One `docker stack deploy` per change-batch,
never `docker service update`/`scale` on `vibemind_*` (project memory: took the stack down
twice). Maintenance-window operations use temporary stack-file replica flips + redeploy.

**Tech Stack:** Docker Swarm (local), docker compose on Debian VM (remote), Qdrant aliases,
PowerShell + Git Bash on Windows, SSH (`~/.ssh/proxmox_key`, user `debian`).

**Hard constraints (from spec, non-negotiable):**
- No Ollama / local model runtime on the Proxmox box, ever — cloud LLM providers only.
- Host RAM ceiling: VM 100 stays at 24GB; no growth, no second big VM.
- Work directly on `master` (both repos). No feature branches.
- The Supabase migration itself belongs to a concurrent session — verify, don't re-execute.

---

## Ground truth this plan relies on (verified 2026-07-14)

- `vibemind-os/brain/the_brain/core/decision_graph.py:46-48` — reads `DECISION_GRAPH_NEO4J_URI`
  (default `bolt://127.0.0.1:7688`), `DECISION_GRAPH_NEO4J_USER` (default `neo4j`),
  `DECISION_GRAPH_NEO4J_PASS` (default `mirofish`).
- `vibemind-os/brain/the_brain/core/mirofish_kg_sync.py:37-39` — reads `MIROFISH_NEO4J_URI`
  (default `bolt://127.0.0.1:7688`), `MIROFISH_NEO4J_USER`/`MIROFISH_NEO4J_PASSWORD`
  (defaults `neo4j`/`mirofish`). Neither URI var is set anywhere in deploy config today —
  containerized writes silently failed (fail-soft) all along.
- Proxmox Neo4j runs on the VM (`192.168.178.65`, bolt published at `7688` per the offload
  plan's final status), `NEO4J_AUTH=${MIROFISH_NEO4J_USER:-neo4j}/${MIROFISH_NEO4J_PASSWORD:-mirofish}`
  defaults match the code defaults — but Task 3 verifies both empirically before the deploy.
- `infra/swarm/vibemind-stack.yml:2302-2305` — network `vibemind-shared` is `attachable: true`,
  so one-off `docker run --network vibemind_vibemind-shared ...` containers can reach in-stack
  services (needed for smoke tests + the migration script, since `embedding-service` publishes
  no host port).
- `infra/swarm/supabase/initdb/` contains `00-bootstrap.sql`, `01-restore.sql`,
  `02-restore-internal.sql`. The VM mounts its copies as `z0-/z1-/z2-*.sql` under
  `/docker-entrypoint-initdb.d/` (verified via `docker inspect` on the VM). New grants file
  becomes `03-grants.sql` locally / `z3-grants.sql` on the VM.
- The exact grants/ownership SQL applied live to the VM DB on 2026-07-14 (fixing GoTrue
  SQLSTATE 3F000 + storage 42P01) is reproduced verbatim in Task 8 — it ran as
  `supabase_admin` (NOT `postgres`, which is not a superuser in Supabase images).
- Local stack name is `vibemind` (services appear as `vibemind_<name>`).
- 4 brain services are active (`brain-core`, `brain-api`, `brain-autotrain-drain`,
  `brain-loops`); `brain-learner`/`brain-inference` are `replicas: 0` opt-ins.
- The migration script `vibemind-os/brain/the_brain/scripts/migrate_embeddings_v3072.py`
  supports `--dry-run` / `--commit` / `--cutover`, `--url` (Qdrant), `--embedding-service-url`;
  cutover never auto-deletes (archive-alias flow with a deliberate manual-deletion step).

---

## Task 1 (Phase 0): WORKBOARD.md + CLAUDE.md coordination rule

**Files:**
- Create: `WORKBOARD.md` (repo root)
- Modify: `CLAUDE.md` (repo root — append one section)

- [ ] **Step 1: Create `WORKBOARD.md`**

```markdown
# WORKBOARD — Multi-Session-Koordination

Mehrere Claude-Code-Sessions arbeiten parallel in diesem Repo (alle auf `master`).
Dieses Board macht sichtbar, wer woran arbeitet, BEVOR Kollisionen teuer werden.

**Protokoll:**
1. Vor Arbeitsbeginn: `git pull`, dieses Board lesen.
2. Claim unter *In Arbeit* eintragen (Session-Kürzel, Datum/Zeit, Scope in einer Zeile)
   und **sofort nach master committen** (`docs: workboard claim <scope>`).
3. Fremder aktiver Claim auf deinem Zielbereich → nicht anfassen; User fragen oder
   anderes Thema wählen.
4. Nach Abschluss: Eintrag nach *Erledigt* verschieben (eine Zeile + Commit-Ref),
   committen.

Grenze: Das ist kooperatives Claiming per Konvention, kein Lock. Der User bleibt
der finale Koordinator.

## In Arbeit

| Session | Seit (Datum/Zeit) | Scope |
|---|---|---|
| _(frei)_ | | |

## Erledigt (jüngste zuerst, max. ~30 Zeilen — ältere löschen)

| Datum | Scope | Commit |
|---|---|---|
| 2026-07-14 | Supabase-VM Grants/Ownership-Fix (auth+storage crash-loop) — live auf VM appliziert | (nur DB, siehe 03-grants.sql) |
| 2026-07-14 | brain-core Embedder → embedding-service, komplett (11 Tasks) | 637ed2c..a167025 + vibemind-os b72a919..6160452 |
```

- [ ] **Step 2: Append the rule to `CLAUDE.md`**

Append after the existing "Still apply normal care" section:

```markdown

## WORKBOARD-Protokoll (Pflicht bei jeder Arbeit an geteilten Bereichen)

Vor Arbeit an geteilten Ressourcen (infra/, vibemind-os-Kern, Proxmox-VM, Stack-Deploys):
`WORKBOARD.md` im Repo-Root lesen, eigenen Claim eintragen und sofort committen, bei
fremdem aktivem Claim auf dem Zielbereich ausweichen oder den User fragen. Details und
Format stehen im Board selbst.
```

- [ ] **Step 3: Verify rendering + commit**

Run: `git add WORKBOARD.md CLAUDE.md && git commit -m "feat: WORKBOARD multi-session coordination protocol (Phase 0)"`
Expected: commit lands on `master`; `git show --stat HEAD` lists exactly 2 files.

---

## Task 2 (Phase 1 prep): Brain→Proxmox-Neo4j env vars

**Files:**
- Modify: `infra/swarm/vibemind-stack.yml` (the 4 active brain services + the 2 opt-in ones, same pattern as `EMBEDDING_SERVICE_URL`)
- Manual (documented, not committed): root `.env` on the Windows host

- [ ] **Step 1: Add the env vars to all 6 brain services**

In each of `brain-core`, `brain-api`, `brain-autotrain-drain`, `brain-loops`, `brain-learner`,
`brain-inference`, add to the `environment:` list (matching the file's existing
`${VAR:-default}` idiom):

```yaml
      - DECISION_GRAPH_NEO4J_URI=${DECISION_GRAPH_NEO4J_URI:-bolt://192.168.178.65:7688}
      - MIROFISH_NEO4J_URI=${MIROFISH_NEO4J_URI:-bolt://192.168.178.65:7688}
```

(User/password vars are NOT set — the code defaults `neo4j`/`mirofish` match the VM's
`NEO4J_AUTH` defaults; Task 3 verifies this empirically. If Task 3 finds different VM
credentials, add `DECISION_GRAPH_NEO4J_USER/_PASS` + `MIROFISH_NEO4J_USER/_PASSWORD` here too.)

- [ ] **Step 2: Validate + commit**

Run: `docker compose -f infra/swarm/vibemind-stack.yml config --quiet; echo $?`
Expected: `0` (warnings about `OPENROUTER_API_KEY`/`JR`/`version` are pre-existing noise).

Run: `docker compose -f infra/swarm/vibemind-stack.yml config | grep -c "DECISION_GRAPH_NEO4J_URI"`
Expected: `6`

```bash
git add infra/swarm/vibemind-stack.yml
git commit -m "feat(brain): point decision-graph + mirofish-kg-sync at the Proxmox Neo4j"
```

- [ ] **Step 3: Document the native-process side (manual, .env is gitignored)**

Append to the Windows root `.env` (NOT committed — .env is gitignored; this is an
instruction to execute, and to note on the WORKBOARD as done):

```
DECISION_GRAPH_NEO4J_URI=bolt://192.168.178.65:7688
MIROFISH_NEO4J_URI=bolt://192.168.178.65:7688
```

Why: native Windows brain processes (ProductionPlanner venv etc.) load `.env` via
`load_env.py` and previously reached the LOCAL Neo4j at `127.0.0.1:7688`, which Phase 1
disables. Without this they silently lose their graph writes (fail-soft, but a real
regression for them).

---

## Task 3 (Phase 1 pre-flight): verify everything the deploy assumes

No files modified — a verification checklist. Every check must pass before Task 4.

- [ ] **Step 1: Images present locally**

Run: `docker image inspect vibemind-embedding-service:latest vibemind-brain-core:latest --format '{{.RepoTags}} {{.Created}}'`
Expected: both resolve; `vibemind-brain-core` created 2026-07-13 or later (the rebuild WITH
cpu-torch + embedding-service client — an older image would silently deploy the pre-migration
code).

- [ ] **Step 2: Swarm secrets exist**

Run: `docker secret ls --format '{{.Name}}' | grep -E 'openai_api_key|anthropic_api_key|openrouter_api_key|groq_api_key|supabase'`
Expected: at minimum `openai_api_key` (embedding-service mounts it), plus the existing brain
secrets. If `openai_api_key` is missing: STOP — run `scripts/swarm_secrets_init.ps1` first.

- [ ] **Step 3: Proxmox Neo4j reachable from Windows with the assumed credentials**

Run (one-off container, cypher-shell ping):
```bash
docker run --rm neo4j:5.18-community cypher-shell -a bolt://192.168.178.65:7688 -u neo4j -p mirofish "RETURN 1"
```
Expected: `1` row returned. If auth fails: read the VM's compose (`ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "grep -A2 NEO4J_AUTH ~/docker-compose*.yml"`),
then set the real credentials via the `*_USER`/`*_PASS(WORD)` env vars in Task 2 Step 1 and
re-commit before deploying.

- [ ] **Step 4: Confirm the 4 staged changes are all in the committed stack file**

Run: `git show master:infra/swarm/vibemind-stack.yml | grep -cE "embedding-service:|EMBEDDING_SERVICE_URL|replicas: 0  # disabled|promtail_config_v2|DECISION_GRAPH_NEO4J_URI"`
Expected: > 10 hits total (embedding-service block + 6 env wirings + 2 disabled replicas +
config v2 + 6 neo4j vars). Also: `git status --porcelain -- infra/swarm/vibemind-stack.yml`
is clean (deploy deploys HEAD, not uncommitted edits).

- [ ] **Step 5: WORKBOARD claim**

Add claim "lokaler Stack-Deploy Phase 1 (embedder/mirofish/promtail/neo4j)" per Task 1's
protocol; commit.

---

## Task 4 (Phase 1) [LIVE — USER GATE]: the one stack deploy

**Gate: the user explicitly approves the moment of deployment** (project history: Swarm
commands have taken the stack down; someone should be around to react).

- [ ] **Step 1: Deploy**

Run: `docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind`
(NEVER with `--prune`. NEVER `docker service update`/`scale` on `vibemind_*` — memory
`feedback_never_service_update_vibemind`, 2× reproduced stack-wipe.)
Expected output: a list of "Updating service ..." lines, no errors. Config-immutability
errors ("only Labels allowed") mean a config name needs a `_vN` bump — fix, commit, re-run.

- [ ] **Step 2: Watch convergence (10 minutes)**

Run (repeat / watch): `docker service ls --format 'table {{.Name}}\t{{.Replicas}}' | sort`
Expected end state (deltas vs. before):
- `vibemind_embedding-service  1/1` (NEW)
- `vibemind_mirofish 0/0`, `vibemind_neo4j-mirofish 0/0` (disabled)
- `vibemind_brain-core 1/1`, `brain-api 1/1`, `brain-autotrain-drain 1/1`, `brain-loops 1/1`
- `vibemind_promtail 1/1`
- everything else unchanged from its pre-deploy replica state.

Known failure mode to watch: `supabase-auth`/`realtime`/`storage` crash-looping right after
a redeploy = the DNS-race pattern (project memory `project_supabase_swarm_dns_race`); the
wait-for-db entrypoint gates normally absorb it — give them 2-3 minutes before intervening.

- [ ] **Step 3: Record on WORKBOARD**

Move the claim to Erledigt with the deploy timestamp.

---

## Task 5 (Phase 1): smoke checks

No files modified. All checks run read-only against the live stack.

- [ ] **Step 1: embedding-service health from inside the overlay**

Run: `docker run --rm --network vibemind_vibemind-shared curlimages/curl -s http://embedding-service:8080/health`
Expected: `{"status":"ok","model":"text-embedding-3-large"}`

- [ ] **Step 2: embedding round-trip (real OpenAI call)**

Run: `docker run --rm --network vibemind_vibemind-shared curlimages/curl -s -X POST http://embedding-service:8080/embed -H "Content-Type: application/json" -d '{"text":"smoke"}' | head -c 80`
Expected: `{"vector":[...` (3072 floats; full check: pipe through a length count if desired).

- [ ] **Step 3: brain-core picked up the new client**

Run: `docker service logs vibemind_brain-core --tail 200 2>&1 | grep -E "embedding-service client configured|KG"`
Expected: a `[KG] embedding-service client configured: http://embedding-service:8080` line;
NO `sentence_transformers` load lines for the KG embedder (EventRoutingHead's SBERT load IS
still expected — that one stays local by design).

- [ ] **Step 4: Promtail ships to the remote Loki**

Run: `curl -s "http://192.168.178.65:3102/loki/api/v1/label/container_name/values" | head -c 400`
Expected: JSON listing LOCAL container names (e.g. `vibemind_brain-core...`) — proof logs
arrive remotely. Also: `docker service logs vibemind_promtail --tail 50 2>&1 | grep -ci error`
returns `0` (or only old pre-deploy noise).

- [ ] **Step 5: Decision-graph writes reach the Proxmox Neo4j**

Run: `docker service logs vibemind_brain-core --tail 300 2>&1 | grep -iE "decision.graph|neo4j" | grep -icE "error|refused|unauthorized"`
Expected: `0`. Positive check (node count moves after brain activity — optional, needs a
brain interaction first):
`docker run --rm neo4j:5.18-community cypher-shell -a bolt://192.168.178.65:7688 -u neo4j -p mirofish "MATCH (n) RETURN count(n)"`

- [ ] **Step 6: Stack-wide health sweep**

Run: `docker service ls --format '{{.Name}} {{.Replicas}}' | awk '$2 ~ /0\/[1-9]/ {print}'`
Expected: empty (no service stuck at 0/N that should be running).

---

## Task 6 (Phase 1) [LIVE — USER GATE]: KG re-embedding maintenance window

**Gate: user approves the window start** (brain services go down for its duration —
realistically 15-60 min depending on collection sizes).

- [ ] **Step 1: Dry-run first (read-only, before the window — no gate needed)**

Run:
```bash
docker run --rm --network vibemind_vibemind-shared \
  -e EMBEDDING_SERVICE_URL=http://embedding-service:8080 \
  vibemind-brain-core:latest \
  python scripts/migrate_embeddings_v3072.py --dry-run --url http://qdrant:6333
```
Expected: per-collection point counts printed (first-ever numbers against real data — record
them on the WORKBOARD), `DRY RUN — <N> points would be migrated.`, exit 0. If a collection is
missing that's fine (skipped); if ALL are missing, STOP — wrong Qdrant URL.

- [ ] **Step 2: Open the window — scale brain services down via stack file (the blessed path)**

Edit `infra/swarm/vibemind-stack.yml`: set `replicas: 0` on `brain-core`, `brain-api`,
`brain-autotrain-drain`, `brain-loops` (temporary, LOCAL EDIT — do NOT commit), then:
`docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind`
Verify: `docker service ls | grep brain` shows `0/0` for all four.
(Why not `docker service scale`: it is a `service update` variant — see the 2×-reproduced
stack-wipe memory. The stack-file flip + deploy is the project-blessed mechanism.)

- [ ] **Step 3: Commit-run the migration**

Same `docker run` as Step 1 with `--commit` instead of `--dry-run`.
Expected: per-collection `re-embedded N points in X s`, then a counts verification table
`old=N new=N [OK]` for every collection. Any `[MISMATCH]`: STOP, investigate, re-run
`--commit` (safe: ID-preserving upserts).

- [ ] **Step 4: Cutover (two-stage by design)**

Same `docker run` with `--cutover`.
Expected first run: per collection, an archive alias is created and the swap attempt prints
`... still exists as a raw collection (already archived as '...') — delete it manually once
you've verified ...`. That is the designed stop, not an error.

Then, per collection, after eyeballing the counts table from Step 3, delete the old raw
collection (example for `brain-episodic`; repeat per collection name from the script output):
```bash
docker run --rm --network vibemind_vibemind-shared curlimages/curl -s -X DELETE http://qdrant:6333/collections/brain-episodic
```
Then re-run the same `--cutover` command.
Expected: `cutover done: '<name>' now aliases '<name>-3072-v1'` for every collection, exit 0.

- [ ] **Step 5: Close the window**

`git restore infra/swarm/vibemind-stack.yml` (drops the temporary replica flips), then:
`docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind`
Verify: all four brain services back to `1/1`.

- [ ] **Step 6: Post-cutover KG smoke**

Run: `curl -s http://localhost:5000/health` → expected healthy JSON.
Run: `docker service logs vibemind_brain-core --tail 100 2>&1 | grep -icE "dimension|3F000|mismatch"` → expected `0`.
A KG search through the brain returning non-empty, sanely-scored results (any established
brain search/introspection endpoint) confirms end-to-end; record the check used on the
WORKBOARD.

---

## Task 7 (Phase 2a) [LIVE at deploy step]: resource limits for the 10 local Supabase services

**Files:**
- Modify: `infra/swarm/vibemind-stack.yml` (the 10 `supabase-*` service blocks)

- [ ] **Step 1: Measure real usage (informs the numbers, 5-minute observation)**

Run: `docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' | grep supabase`
Record the values. Starting limits (adjust upward if measurement exceeds them; limits ≈ 2×
observed, reservations deliberately small):

| Service | limit cpus / memory | reservation cpus / memory |
|---|---|---|
| supabase-db | 2 / 2G | 0.25 / 512M |
| supabase-kong | 1 / 512M | 0.1 / 128M |
| supabase-studio | 0.5 / 512M | 0.1 / 128M |
| supabase-auth | 0.5 / 256M | 0.1 / 64M |
| supabase-rest | 0.5 / 256M | 0.1 / 64M |
| supabase-realtime | 1 / 512M | 0.1 / 128M |
| supabase-storage | 0.5 / 512M | 0.1 / 128M |
| supabase-pg-meta | 0.5 / 256M | 0.1 / 64M |
| supabase-analytics | 1 / 1G | 0.1 / 256M |
| supabase-inbucket | 0.25 / 128M | 0.05 / 32M |

- [ ] **Step 2: Add `deploy.resources` blocks**

For each of the 10 services, inside its existing `deploy:` key, add (example for
`supabase-db`; repeat with the table's values):

```yaml
      resources:
        limits:
          cpus: "2"
          memory: 2G
        reservations:
          cpus: "0.25"
          memory: 512M
```

- [ ] **Step 3: Validate + commit**

Run: `docker compose -f infra/swarm/vibemind-stack.yml config --quiet; echo $?` → `0`.
```bash
git add infra/swarm/vibemind-stack.yml
git commit -m "feat(supabase): resource limits for all 10 local services (recon §5 gap)"
```

- [ ] **Step 4 [USER GATE]: activate via deploy + verify no OOM**

`docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind`, wait for convergence, then:
Run: `docker service ps $(docker service ls --format '{{.Name}}' | grep supabase) --format '{{.Name}} {{.CurrentState}} {{.Error}}' 2>/dev/null | grep -i "oom\|137"`
Expected: empty. Any OOM-killed service: double its memory limit, commit, redeploy.

---

## Task 8 (Phase 2b.1): codify the grants fix as `03-grants.sql`

**Files:**
- Create: `infra/swarm/supabase/initdb/03-grants.sql`
- Modify: `infra/swarm/supabase/README.md` (one paragraph)

- [ ] **Step 1: Write `03-grants.sql`** (exactly what was applied live to the VM on 2026-07-14;
idempotent, safe on both fresh inits and already-fixed DBs)

```sql
-- 03-grants.sql — service-role grants + ownership the restore dumps do NOT carry.
-- Incident 2026-07-14: a fresh VM init from 00-/01-/02- left auth/storage schemas
-- owned by supabase_admin with NO grants for supabase_auth_admin/supabase_storage_admin.
-- GoTrue died with SQLSTATE 3F000 ("no schema has been selected to create in" — the
-- schema existed but was invisible to the role), storage-api with 42P01.
-- NOTE: initdb scripts run as the image superuser (supabase_admin context) — do not
-- run this manually as `postgres`; postgres is NOT a superuser in Supabase images.

GRANT USAGE, CREATE ON SCHEMA auth TO supabase_auth_admin;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role, postgres;
GRANT USAGE, CREATE ON SCHEMA storage TO supabase_storage_admin WITH GRANT OPTION;
GRANT USAGE ON SCHEMA storage TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA storage TO postgres WITH GRANT OPTION;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dashboard_user') THEN
    GRANT USAGE, CREATE ON SCHEMA auth TO dashboard_user;
    GRANT USAGE, CREATE ON SCHEMA storage TO dashboard_user;
  END IF;
END $$;

DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='auth' LOOP
    EXECUTE format('ALTER TABLE auth.%I OWNER TO supabase_auth_admin', r.tablename);
  END LOOP;
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='storage' LOOP
    EXECUTE format('ALTER TABLE storage.%I OWNER TO supabase_storage_admin', r.tablename);
  END LOOP;
END $$;

DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname='auth' LOOP
    EXECUTE format('ALTER SEQUENCE auth.%I OWNER TO supabase_auth_admin', r.sequencename);
  END LOOP;
  FOR r IN SELECT sequencename FROM pg_sequences WHERE schemaname='storage' LOOP
    EXECUTE format('ALTER SEQUENCE storage.%I OWNER TO supabase_storage_admin', r.sequencename);
  END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='auth' LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO supabase_auth_admin', r.sig);
  END LOOP;
  FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='storage' LOOP
    EXECUTE format('ALTER FUNCTION %s OWNER TO supabase_storage_admin', r.sig);
  END LOOP;
END $$;
```

- [ ] **Step 2: README note**

Append to `infra/swarm/supabase/README.md`:

```markdown
## 03-grants.sql (2026-07-14)

The pg_dump-based restore snapshots (01/02) recreate auth/storage objects owned by the
dumping role WITHOUT the schema grants GoTrue/storage-api need. 03-grants.sql re-applies
them; it MUST be included (as the last z*-mount) in any fresh initdb — the Proxmox VM's
first deploy crash-looped auth+storage for exactly this reason. Idempotent; safe to re-run.
```

- [ ] **Step 3: Commit + WORKBOARD handoff entry**

```bash
git add infra/swarm/supabase/initdb/03-grants.sql infra/swarm/supabase/README.md
git commit -m "fix(supabase): codify auth/storage grants+ownership as initdb 03-grants.sql"
```
WORKBOARD note for the migration-owning session: "VM compose: mount 03-grants.sql as
`/docker-entrypoint-initdb.d/z3-grants.sql` alongside z0-z2 (no effect on the existing DB —
already fixed live — but required for any future re-init)."

---

## Task 9 (Phase 2b.2) [LIVE — USER GATE for the reboot]: independent cutover verification

No files modified. Run only after the migration-owning session reports done (check WORKBOARD).

- [ ] **Step 1: All 10 VM services healthy**

Run: `ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "docker ps --filter name=supabase --format '{{.Names}}: {{.Status}}'"`
Expected: 10 lines, all `Up ...`, none `Restarting`.

- [ ] **Step 2 [USER GATE]: reboot survival test**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm snapshot 100 pre-reboot-test && qm reboot 100"
```
Wait ~3 minutes, then repeat Step 1. Expected: all 10 back up WITHOUT manual help (validates
`restart:` policies + wait-for-db entrypoint gates). Any service that needs a manual start is
a finding → WORKBOARD.

- [ ] **Step 3: Data spot-check VM vs. local**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "docker exec debian-supabase-db-1 psql -U supabase_admin -d postgres -tc \"SELECT (SELECT count(*) FROM public.ideas), (SELECT count(*) FROM public.canvas_nodes)\""
LOCAL_DB=$(docker ps --filter name=vibemind_supabase-db --filter status=running --format "{{.Names}}" | head -1)
docker exec $LOCAL_DB psql -U supabase_admin -d postgres -tc "SELECT (SELECT count(*) FROM public.ideas), (SELECT count(*) FROM public.canvas_nodes)"
```
Expected: counts match (or VM ≥ local if writes moved already). Divergence: STOP, report —
means both DBs are being written concurrently (exactly what the Phase 2b.3 gate prevents).

- [ ] **Step 4: auth + storage functional round-trips (via Kong on the VM)**

Auth health + a signup/login round-trip and a storage upload/download using the demo anon/
service keys (same keys as local — they're in the stack file). Minimum bar:
```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "curl -s -o /dev/null -w 'auth: %{http_code}\n' http://localhost:54321/auth/v1/health -H 'apikey: <anon key from stack file>'"
```
Expected: `auth: 200`. Storage: create bucket + upload + download a 1-byte object with the
service key via `http://localhost:54321/storage/v1/...`, expect 200s throughout.

---

## Task 10 (Phase 2b.3): consumer inventory + re-pointing

**Files:** discovered by inventory — the greps below are the step; edits follow the found sites.

- [ ] **Step 1: Inventory every local consumer of the LOCAL Supabase**

```bash
grep -rn --include="*.py" --include="*.ts" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.toml" --include="*.env*" -E "54321|54322|54323|SUPABASE_URL" \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=graphify-out . vibemind-os 2>/dev/null | grep -v "192.168.178.65" | sort
```
Plus the gitignored configs: root `.env`, `~/.openfang/secrets.env`, `~/.openfang/config.toml`.
Write the complete inventory (file:line → what it is) to the WORKBOARD.

- [ ] **Step 2: Re-point, consumer by consumer**

Pattern: `http://localhost:54321` / `http://host.docker.internal:54321` →
`http://192.168.178.65:54321` (same for 54322/54323). In-stack consumers keep working either
way during the transition since BOTH Supabases hold the data — but every consumer must be
moved BEFORE Task 11. Each re-point: one commit (or one .env edit noted on the WORKBOARD).

- [ ] **Step 3 [USER GATE]: the divergence gate**

Present the inventory with every item checked off to the user. Explicit user sign-off required:
"no local consumer writes to the local Supabase anymore." Only then proceed to Task 11.

---

## Task 11 (Phase 2b.4) [LIVE — USER GATE]: reversible local Supabase decommission

**Files:**
- Modify: `infra/swarm/vibemind-stack.yml` (10 supabase services → `replicas: 0`)

- [ ] **Step 1: Flip replicas, commit**

Set `replicas: 0` with a dated comment on all 10 `supabase-*` services:
```yaml
      replicas: 0  # decommissioned 2026-MM-DD: cutover to Proxmox VM verified (Task 9/10); volume retained until +14d
```
```bash
git add infra/swarm/vibemind-stack.yml
git commit -m "feat(supabase): decommission local stack (cutover to Proxmox verified) -- volumes retained"
```

- [ ] **Step 2 [USER GATE]: deploy + verify**

`docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind`
Verify: all `vibemind_supabase-*` at `0/0`; `docker volume ls | grep supabase` still lists
`vibemind_supabase_db` + `vibemind_supabase_storage` (UNTOUCHED — rollback reserve).

- [ ] **Step 3: Retention note**

WORKBOARD entry: "local supabase_db/storage volumes: rollback reserve until <date +14d>;
after that date deletion needs a fresh user OK (never automatic)."

---

## Task 12 (Phase 2c): `docs/OPERATIONS.md` runbook

**Files:**
- Create: `docs/OPERATIONS.md`

- [ ] **Step 1: Write the runbook** — content consolidates what exists in stack-file comments,
project memory, and the two specs; structure (write all sections in full, sourcing the
specifics from: `vibemind-stack.yml` header comments, memory entries
`feedback_never_service_update_vibemind`, `feedback_swarm_config_immutable`,
`feedback_swarm_latest_no_reschedule`, `project_supabase_swarm_dns_race`, and the offload
spec's operations table):

```markdown
# OPERATIONS — Update- & Rollback-Runbook

## Lokaler Docker Swarm (Windows, Stack `vibemind`)
- Deploy: NUR `docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind` (ohne
  `--prune`) oder Launcher. NIE `docker service update`/`scale` auf `vibemind_*` (2×
  reproduzierter Stack-Wipe).
- Configs sind IMMUTABLE: Änderung = neuen Namen `_vN` vergeben + alle Referenzen bumpen.
- `:latest`-Images werden ohne Spec-Änderung NICHT neu gezogen: Reschedule erzwingen via
  `VIBEMIND_RESTART_NONCE`-Env+Label-Bump (Datum+Suffix) oder Launcher stop/start.
- Bekannter Crash-Loop nach Redeploy: supabase auth/realtime/storage DNS-Race — 2-3 min
  warten (wait-for-db-Gates), NICHT sofort eingreifen; Exited-Tasks NIE manuell
  `docker start` (Orphan-Duplikate).
- Rollback: Commit revert + erneuter stack deploy. Secrets via scripts/swarm_secrets_init.ps1.

## Proxmox VM 100 (Debian, docker compose, 192.168.178.65)
- Vor riskanten Änderungen: `qm snapshot 100 <name>` (Host: root@192.168.178.64);
  Rollback: `qm rollback 100 <name>`.
- Backups: täglicher vzdump 03:00 (7 daily + 4 weekly) auf Storage `local`.
- Compose-Änderungen: git-committete Edits + `docker compose up -d` (Digest-Pins, bewusste
  Bumps). App-Level-Dumps für granulare Restores: pg_dump / neo4j-admin dump / mongodump.
- SSH: `ssh -i ~/.ssh/proxmox_key debian@192.168.178.65` (VM), `root@192.168.178.64` (Host).

## Host-Regeln (Proxmox pve)
- RAM-Decke: 81% belegt (Stand 2026-07-14). VM 100 NICHT vergrößern, keine zweite große VM —
  erst Rebalancing (Ballooning/KSM oder Allokation senken).
- HARTE REGEL: kein Ollama / keine lokale Modell-Runtime auf der Proxmox-Box — LLM nur über
  Cloud-Anbieter.
- Standalone-Node ist ABSICHT, kein Versäumnis: Proxmox-Clustering braucht ≥2 physische
  Hosts (Quorum!); erst relevant, falls eine zweite Box kommt (dann mit QDevice).

## Koordination
- Vor Arbeit an geteilten Bereichen: WORKBOARD.md (Repo-Root) — Protokoll dort.
```

- [ ] **Step 2: Commit**

```bash
git add docs/OPERATIONS.md
git commit -m "docs: unified operations runbook (Swarm + Proxmox VM + host rules)"
```

---

## Task 13 (Phase 2d): offload-spec addendum (stale GPU rationale)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-13-proxmox-homelab-offload-design.md` ("What stays local" section)

- [ ] **Step 1: Append the dated addendum** directly under the Brain-cluster bullet:

```markdown

> **Addendum 2026-07-14:** the GPU/Qwen rationale above is stale — the embedder migration
> (`2026-07-13-brain-embedder-external-api-design.md`) moved the Qwen KG-embedder to the
> external `embedding-service` (cloud API); brain-core now ships CPU-only torch. Brain
> stays local anyway: dev-iteration/latency, the native host-process integrations
> (OpenFang/ProductionPlanner/Ollama-for-Windows-consumers), and EventRoutingHead's local
> SBERT (<100ms real-time path). The split decision stands — do not re-litigate it from
> the GPU angle; see `2026-07-14-proxmox-split-phase2-design.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-07-13-proxmox-homelab-offload-design.md
git commit -m "docs: offload spec addendum -- GPU rationale stale post embedder migration, split stands"
```

---

## Plan self-review (performed while writing)

**Spec coverage:** Phase 0 → Task 1; Phase 1 → Tasks 2-6 (env vars, pre-flight, deploy, smoke,
KG window); Phase 2a → Task 7; Phase 2b → Tasks 8-11 (grants codification, verification,
consumer gate, decommission); Phase 2c → Task 12; Phase 2d → Task 13. Hard constraints
surfaced in the header and enforced at the relevant steps (no service update/scale; no VM
growth; verify-don't-re-execute for Supabase; no-Ollama rule embedded in the runbook).

**Placeholder scan:** the two deliberate implementation-time measurements (docker stats
values in Task 7, the exact brain-search endpoint in Task 6 Step 6) are bounded instructions
with recorded outcomes, not open TODOs. Task 9 Step 4's `<anon key from stack file>` points
at a concrete, single source (the literal key sits in `vibemind-stack.yml`'s supabase-storage
block) rather than reproducing a credential into this doc.

**Consistency:** env var names match `decision_graph.py`/`mirofish_kg_sync.py` exactly;
network name `vibemind_vibemind-shared` used consistently; VM paths/users match the verified
SSH facts; the `--cutover` two-stage flow matches the script's actual designed behavior
(archive → manual delete → re-run), not an idealized one-shot.

**Sequencing note:** Phase 2a deploys separately AFTER Phase 1 is verified stable (spec
ordering) — deliberately two deploy events so a mis-sized limit can't muddy Phase 1's smoke
checks.
