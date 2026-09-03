# Proxmox Split — Phase 2 & Deploy Validation — Design Spec

Status: approved (design), not yet implemented
Date: 2026-07-14
Related: `VIBEMIND-DEPLOY-RECON.md`, `docs/superpowers/specs/2026-07-13-proxmox-homelab-offload-design.md`,
`docs/superpowers/specs/2026-07-13-brain-embedder-external-api-design.md`

## Context and target model

The user has decided: the **split model continues** — it is NOT the goal to move the whole
stack to Proxmox. The Windows machine stays the dev/GPU box (Brain cluster, coding-engine,
Qdrant, and the native host processes Ollama/OpenFang/ProductionPlanner/openclaw); the
Proxmox VM (VM 100, `192.168.178.65`, 12 vCPU / 24GB on host `pve` `192.168.178.64`) takes
background load. Consequence: the recon's "host-process coupling" blocker is **resolved by
design, not by work** — the services that need those processes stay on Windows. This is a
deliberate decision, recorded here so no future session re-derives "host.docker.internal is
a Proxmox blocker" for services that are never moving.

**Live state on the VM, verified empirically 2026-07-14 (not from docs — docs lagged reality
by a day):** Loki, Grafana, Gitea+Postgres, Rowboat core (Mongo/Redis/app/jobs/rag), Neo4j,
n8n — AND the full 10-service Supabase stack, deployed by a concurrent session today. Two of
its services (auth, storage) crash-looped on a grants/ownership bug in the restored DB; this
session diagnosed and fixed that live (see "Supabase grants incident" below). All 10 run now.

**Host resource ceiling (from the Proxmox UI, 2026-07-14):** host RAM 81% used (24.77/30.59
GiB) with VM 100 allocated 24GB; CPU idle; storage plentiful. **Rule: no VM memory growth and
no significant second VM without rebalancing** — Supabase fit because it was pre-budgeted
inside the existing 24GB allocation. Anything beyond requires shrinking allocations or
ballooning/KSM work first.

**Hard rule (user, 2026-07-14): no LLM inference via Ollama — or any other local model
runtime — on the Proxmox box, ever.** All LLM actions from services running there go through
cloud providers (OpenAI/Anthropic/OpenRouter/Groq) only. This extends the existing
no-local-inference constraint from the recon explicitly to the Proxmox side: spare CPU on the
VM is not an invitation to host models. (Ollama on the Windows dev machine is unaffected —
it serves Windows-local consumers only.)

## Phase 0 (first, cross-cutting): multi-session coordination protocol

Multiple Claude Code sessions work this repo concurrently. Today alone this produced: silently
diverged branches, a lost working-tree edit, one session nearly re-planning a migration another
session was mid-way through executing, and a live conflict window on `vibemind-stack.yml`.

Mechanism (convention, not lock — its job is making conflicts visible before they're expensive):
1. **`WORKBOARD.md` at repo root.** Sections: *In Arbeit* (session claims: scope + timestamp +
   one-line description) and *Erledigt* (one line + commit ref). Protocol: before starting work
   on an area, `git pull`, read the board, add your claim, **commit the claim immediately to
   master**. On finish, move the entry to Erledigt. If someone else's active claim covers your
   target area: don't touch it — ask the user or pick something else.
2. **Rule anchored in `CLAUDE.md`** (auto-loaded by every session) so new sessions follow the
   protocol without being told.
3. Honest limit: a session that ignores the board still collides. The board makes redundancy
   visible; the user remains the ultimate coordinator.

## Phase 1: local deploy validation

Four changes are committed but inactive, all waiting on the same `docker stack deploy` of the
local stack: (a) embedder-migration wiring (new `embedding-service` + `EMBEDDING_SERVICE_URL`
on 6 brain services), (b) mirofish + neo4j-mirofish `replicas: 0`, (c) the other session's
Promtail→remote-Loki redirect (config already bumped to v2), (d) NEW in this spec:
Brain→Proxmox-Neo4j re-pointing.

**(d) detail — decided:** local `neo4j-mirofish` stays disabled; Brain's graph writes go to
the Proxmox Neo4j (`bolt://192.168.178.65:7688`, data already restored there). Implementation:
set `DECISION_GRAPH_NEO4J_URI` and `MIROFISH_NEO4J_URI` env vars on the brain services in
`infra/swarm/vibemind-stack.yml`. **Finding that motivated this:** neither var was ever set in
any deploy config — inside Swarm containers both fell back to `bolt://127.0.0.1:7688` (the
container itself), so the containerized Brain's decision-graph/kg-sync writes have been
silently failing all along (fail-soft). The local Neo4j served native-Windows processes at
most. Re-pointing is therefore a repair, not just a move. (Native Brain processes on Windows
need the same env vars set in their environment — separate small task.)

Sequence:
1. Pre-flight: images present (`vibemind-embedding-service`, rebuilt `vibemind-brain-core`),
   secrets exist, `docker compose config` clean, (d) committed.
2. **One** `docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind` — user-approved,
   single risk event (this project's history: Swarm commands have taken the stack down before;
   deploy runs WITHOUT `--prune`, and the operator watches for the known auth/realtime/storage
   DNS-race crash-loop pattern per project memory).
3. Smoke checks: embedding-service `/health` from inside the overlay network; brain-core
   healthy + logs show embedding-service client configured; promtail shipping to remote Loki
   (visible in Proxmox Grafana); mirofish/neo4j-mirofish at 0/0; no new crash-loops
   stack-wide; decision-graph write path reaches Proxmox Neo4j.
4. KG re-embedding (separate maintenance window, per the migration script's own documented
   workflow): scale `brain-*` to 0 → `migrate_embeddings_v3072.py --dry-run` (first ever run
   against real data) → `--commit` → verify per-collection counts + ID sets → `--cutover`
   (archive-alias flow, never auto-deletes) → scale `brain-*` back up → KG smoke query
   (sane similarity results, no zero-vectors).
5. Rollback paths, per change: embedding-service (scale to 0; brain Embedder fails soft with
   loud ERROR logs), replicas/env changes (revert commit + redeploy), promtail (config back to
   v1 + redeploy), KG cutover (repoint alias back to archived old collection — kept, not
   deleted).

## Phase 2a: resource limits for the local Supabase services

The 10 local Supabase services have no `deploy.resources` blocks (recon §5). Even though
Supabase is migrating to Proxmox, the local stack keeps running until the cutover is verified
(Phase 2b) — and per the recon, unbounded services on a 32GB host with known OOM history are
a real stability risk. Add conservative limits mirroring what comparable services in the same
file use (postgres ≈ gitea-postgres's 1G, kong/studio/realtime ≈ 512M-1G each; exact numbers
set during implementation from observed `docker stats`). This work is NOT wasted when local
Supabase is later decommissioned: the limit values transfer to the VM compose file as
documentation of real usage.

## Phase 2b: Supabase cutover — verification and local decommission gate

The migration itself is **already executed** by a concurrent session (discovered live today,
mid-flight). This phase deliberately does NOT re-plan it. Remaining work in THIS plan:

1. **Feed back the grants fix into the restore tooling.** Incident: the VM's restored DB had
   all 33 `auth`/`storage` tables owned by `supabase_admin` with **zero schema grants** for
   `supabase_auth_admin`/`supabase_storage_admin` → GoTrue died with SQLSTATE 3F000 ("no
   schema has been selected to create in" — schema present but invisible to the role),
   storage with 42P01. Fixed live by mirroring the local DB's ACLs (GRANT USAGE/CREATE +
   ownership transfer, executed as `supabase_admin` — note: `postgres` is NOT a superuser in
   Supabase images; first attempt as `postgres` no-op'd with warnings). The fix lives only in
   the VM's DB: any future fresh init from `infra/swarm/supabase/initdb/` hits the same wall.
   Add a `z3-grants.sql` (or fix the dump generator) codifying exactly the applied grants.
2. **Independent cutover verification** (after the executing session reports done): all 10
   services healthy AND stay healthy across one VM reboot (validates compose `restart:` +
   wait-for-db entrypoints); row-count spot-check of key tables (`public.ideas`,
   `canvas_nodes`, `marketing.*`) VM vs. local; auth login round-trip via Kong; storage
   upload/download round-trip.
3. **Consumer inventory + re-pointing:** every local consumer of `localhost:54321/54322/54323`
   (brain services' supabase env, marketing workers, bidi-sync, MCP servers, native scripts)
   inventoried and switched to `192.168.178.65`. Gate: no consumer still writes to the LOCAL
   Supabase before decommissioning it — otherwise silent data divergence between two live DBs.
4. **Local decommission, reversibly:** local Supabase services to `replicas: 0` (definitions
   kept), `supabase_db` volume kept untouched as rollback reserve for **14 days** after the
   verification in (2) passes (default; user can shorten/extend). Only after this gate is the
   local stack's footprint actually reduced.

## Phase 2c: operations runbook

One document (`docs/OPERATIONS.md`) unifying update + rollback methods per deployment target —
today this knowledge is scattered across stack-file comments, project memory, and two specs:

- **Local Swarm:** config `_vN` bump pattern (configs are immutable), `VIBEMIND_RESTART_NONCE`
  label-bump for forced reschedules, `:latest` images don't re-pull without a spec change,
  launcher stop/start vs. `stack deploy` (never `docker service update` on vibemind_*, never
  `--prune` casually), known DNS-race crash-loop pattern + wait-for-db gates.
- **Proxmox VM:** `qm snapshot` before risky changes / `qm rollback`; daily `vzdump` (03:00,
  7d+4w retention); compose-file changes via git-committed edits + `docker compose up -d`;
  pinned digests, deliberate bumps only; app-level dumps (pg_dump, neo4j-admin dump,
  mongodump) for granular restore.
- **Host-level rules:** RAM ceiling note (81% — no VM growth without rebalancing);
  **standalone node is deliberate, not an omission** — Proxmox clustering needs ≥2 physical
  hosts (realistically 3 or 2+QDevice for quorum) and provides nothing on one node; revisit
  only if a second Proxmox box (e.g. the future GPU box) materializes.

## Phase 2d: docs hygiene

The offload spec's "What stays local" rationale for the Brain cluster cites the Qwen/CUDA
embedder — stale since the embedder migration (brain-core is CPU-torch + external
embedding-service now). Add a dated addendum: Brain stays local for dev-iteration/latency
reasons and the remaining native-host-process integrations (and EventRoutingHead's local
SBERT), not for GPU reasons. Prevents a future session from "discovering" Brain is movable
and re-litigating the split decision without the user.

## Explicitly out of scope

- Full stack migration to Proxmox (split model is the decision; revisit only on user request).
- Decoupling Ollama/OpenFang/ProductionPlanner/openclaw from the Windows host (moot under the
  split model — they serve services that stay local). A mirofish LLM/embedding adapter
  container was discussed and deliberately deferred: mirofish stays disabled unless the user
  decides it's needed again.
- Joining the Proxmox VM to the Docker Swarm (reaffirmed from the offload spec).
- `rowboat-agents` (still gated on the `feat/aisalesorgcore-integration` branch decision).
- Proxmox clustering / HA / PBS (single node; see runbook note).
- Re-planning or re-executing the Supabase migration itself (another session's work; this plan
  only verifies, feeds back the grants fix, and gates the local decommission).
