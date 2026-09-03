# Vibemind Container Standards

> **Status:** Phase B — container-standard foundation. This is **descriptive +
> prescriptive**: it documents the *actual* conventions of the deployed swarm
> stack (`infra/swarm/vibemind-stack.yml`) and sets the target shape for new
> services. It does **not** silently rewrite live services — see the
> [Gap List](#gap-list) for what is intentionally NOT auto-applied.

## Why this exists

The repo grew organically across independent spaces (brain, rowboat, mirofish,
desktop, …). The swarm stack inherited partial patterns from the original
`vibemind-os/coding-engine/infra/docker/docker-stack.yml` reference but was
never harmonised. New services should not have to reverse-engineer the
conventions from 13 divergent service blocks.

Templates here are **grounded in real, working exemplars** (file:line below),
not theory. Adopt them for *new* services; migrate *existing* ones only with
the per-service verification the Gap List demands.

## Exemplars (ground truth)

| Pattern | Exemplar | Why |
|---|---|---|
| Python service (monorepo-aware) | `vibemind-os/brain/the_brain/Dockerfile` | local `vibemind-shared` install, CPU-torch wheel index, parent build context |
| Python service (multi-stage, non-root) | `Automation_ui/backend/Dockerfile` | build/runtime dep split, `appuser`, HEALTHCHECK in image |
| Node service (multi-stage, alpine) | `vibemind-os/spaces/rowboat/rowboat/apps/rowboat/Dockerfile` | 3-stage deps→builder→runner, frozen-lockfile, non-root `nextjs` |
| Swarm reference (secrets/resources) | `vibemind-os/coding-engine/infra/docker/docker-stack.yml` | external secrets, limits+reservations |
| Logger seed | `vibemind-os/brain/the_brain/core/brain_logger.py` | `get_logger()` factory, JSON formatter, `BRAIN_LOG_*` env |

## Conventions

### 1. Base images — pin, don't float

- Python service → `python:3.11-slim`
- Node service → `node:18-alpine` (+ `apk add --no-cache libc6-compat` for
  native modules)
- **Avoid `:latest` for first-party images in the stack.** `qdrant/qdrant:latest`,
  `mongo:latest`, `redis:latest` currently float — acceptable for now (upstream
  images) but new pins are preferred. First-party `vibemind-*:latest` tags are
  built locally on a single-node swarm, so the floating tag is the build output,
  not a registry pull — documented, not a defect.

### 2. Health checks — every service, documented path

Every long-lived service **must** declare a healthcheck in its swarm block.
54% of current services (all 5 rowboat services, mongo, redis) have none — see
Gap List.

**Default contract:** `GET /health` → `200` with JSON body
`{"status":"healthy", ...}`. Services that legitimately differ are
**exception-documented** here rather than forced to conform:

| Service | Health probe (reality) | Notes |
|---|---|---|
| brain-core / -learner / -inference | `GET /api/health` (curl) | also `/health`; FastAPI |
| media (nginx) | `GET /health` (wget, **`127.0.0.1`**) | busybox-wget resolves `localhost`→IPv6; nginx listens IPv4 only — **must** use `127.0.0.1` |
| n8n | `GET /healthz` (wget) | upstream n8n convention, not changeable |
| mirofish | `GET /health` (wget, `127.0.0.1`) | Flask |
| neo4j-mirofish | `GET /` port 7474 (wget) | Neo4j browser; no JSON health endpoint upstream |
| rowboat / -agents / -jobs-worker | (none yet) | Gap List #1 |
| rowboat-mongo / -redis | TCP-only | datastores; use `mongosh`/`redis-cli` ping if added |

**Timing floors** (learned from the media `start_period` and timeout incidents):
- `timeout` ≥ `5s` (3s caused false failures on network jitter — media bug)
- `start_period` must cover real cold start: brain ≈ `60s` (SBERT load),
  Flask/Node ≈ `30-40s`, nginx ≈ `10s`. A `0s` start_period (n8n default)
  health-kills a still-booting container.
- Probe URL uses `127.0.0.1`, never `localhost`, inside busybox/alpine.

### 3. Resource blocks — limits AND reservations

Every service block sets **both** `deploy.resources.limits` and
`deploy.resources.reservations`. Limits-only lets the scheduler over-commit a
node silently (rowboat-redis, rowboat-jobs-worker currently violate this).

### 4. Labels — service metadata

Zero services carry custom labels today. New/migrated services add:

```yaml
deploy:
  labels:
    vibemind.service: "<name>"          # e.g. "mirofish"
    vibemind.tier: "<tier-1|tier-2|infra|space>"
    vibemind.component: "<api|worker|datastore|frontend|proxy>"
    vibemind.space: "<space-or-empty>"  # e.g. "rowboat", "" for shared infra
```

(`deploy.labels` = service labels in Swarm; container `labels:` are per-task.
Use `deploy.labels` for stack metadata.)

### 5. Env handling — env_file XOR explicit, never empty-expansion

The single most expensive recurring bug class in this stack:
`${OPENAI_API_KEY}` in an `environment:` block expands from the **empty deploy
shell** and *overrides* the value an `env_file:` would have supplied.

**Rule:**
- Shared secrets/keys → `env_file: ../../.env` **listed first**.
- Only **stack-topology** overrides go in `environment:` (overlay DNS hostnames,
  pinned `PORT`, role flags) — and those must be literal, not `${VAR}`
  shell-expansions **of keys that also live in `.env` under the same name**.
- Never both-source the same key.

**Audit (Gap List #2, closed by audit not migration):** the stack was
swept for `environment: ${VAR}` expansions that could empty-override an
`env_file` value. Result: the dangerous class (the original rowboat
`OPENAI_API_KEY=${OPENAI_API_KEY}` — target var == source var == an
`.env` key → empty deploy-shell expansion silently nulled the key) was
**already eliminated in the B-next commits** (env_file-first ordering).
Only 3 `${VAR}` expansions remain and **all are compliant by design**,
NOT the bug class:

| Service | Expansion | Why safe |
|---|---|---|
| rowboat-agents | `API_KEY=${AGENTS_API_KEY:-vibemind-local-key}` | target `API_KEY` ≠ source `AGENTS_API_KEY`; `:-` default; agents reads `API_KEY`, env_file delivers `AGENTS_API_KEY` separately |
| mirofish | `LLM_MODEL_NAME=${MIROFISH_LLM_MODEL:-llama3.1:latest}` | target ≠ source; `:-` default = a pulled model |
| mirofish | `EMBEDDING_MODEL=${MIROFISH_EMBEDDING_MODEL:-nomic-embed-text:latest}` | target ≠ source; `:-` default; source not in `.env` |

Each is a *renamed* var with a working `:-default`, so an empty deploy
shell degrades to a safe default — never an empty crash. Verified live:
rowboat-agents `OPENAI_API_KEY` arrives len-164 via env_file (NOT
nulled), `API_KEY` len-18 (the default, by design), mirofish
`LLM_MODEL_NAME=llama3.1:latest`; both services `/health=200`.
**Do not "fix" these into env_file — that would add risk for a bug that
does not exist** (the core Gap-List discipline: don't touch working env
handling without cause).

### 6. Non-root user

Images run as a non-root user (`appuser` / `nextjs:nodejs` pattern). Several
upstream images (qdrant, mongo) run as root by image default — acceptable for
pinned upstream images; **first-party** images must add a non-root user.

### 7. Python runtime hygiene

`ENV PYTHONDONTWRITEBYTECODE=1` + `ENV PYTHONUNBUFFERED=1` on every Python
image (the latter is why container logs stream in real time — missing it makes
debugging a guessing game).

### 8. CMD policy

A first-party image **either** ships a correct default `CMD` (JSON-array form:
`CMD ["uvicorn", "app:app", ...]`) **or** intentionally omits it and the swarm
block supplies `command:`. The failure mode that cost us two services
(rowboat-jobs-worker, mirofish-diagnosis) was a **single-element** CMD like
`CMD npm run dev` collapsing to one argv token, or an image whose CMD is just
`[node]`/`[python3]` → REPL → silent exit 0/1 with no logs. If omitting CMD,
**document it in the Dockerfile** so the orchestrator knows it must inject one.

### 9. Logging — the convention (Gap List #6 closed)

The reference implementation already exists and is grounded in real code:
`vibemind-os/brain/the_brain/core/brain_logger.py` — `get_logger(name)`
factory + `JSONFormatter` + env controls. This section promotes it from
"seed" to the **written convention for new and refactored code**. It does
**not** retro-rewrite existing app code (rowboat `console.log`, mirofish
`print` stay until a separate, verified per-service refactor — that touches
foreign app code in two submodules and is its own risk-bearing change).

**The JSON line schema** (exactly what `JSONFormatter.format` emits —
`brain_logger.py:95-117`, do not invent fields):

```json
{"timestamp":"<ISO8601>Z","level":"INFO","logger":"<name>",
 "message":"<msg>","module":"<mod>","function":"<fn>","line":<n>}
```

Optional, only when present: `"exception":"<traceback>"` (on `exc_info`),
`"data":{…}` (structured extra via the `extra_data` record attribute, set
through the `log_with_context()` helper — `brain_logger.py:271`).

**Rules for new / refactored services:**

1. **No bare `print` / `console.log`** in committed code (already a
   coding-style default; this makes it stack-wide and concrete).
2. **Python:** obtain loggers via `get_logger(__name__)` (the brain
   factory) or, in a non-brain service, a local factory that emits the
   **same JSON schema** above. One logger per module, named by module.
3. **Node/TS:** a project-local structured logger emitting the same JSON
   field names (`timestamp/level/logger/message`); never `console.log`
   in committed code.
4. **Env controls (the brain contract — reuse the same names so ops is
   uniform):** `BRAIN_LOG_LEVEL` (DEBUG|INFO|WARNING|ERROR, default
   INFO), `BRAIN_LOG_FORMAT` (compact|detailed|json, default detailed;
   **containers in the stack SHOULD set `json`** for aggregation),
   `BRAIN_LOG_FILE` / `BRAIN_LOG_TO_FILE` for file sink.
5. **Container default:** stack services that adopt structured logging
   set `BRAIN_LOG_FORMAT=json` in their `environment:` so stdout is
   parseable by a future log aggregator. (Adding that env to existing
   services is part of the deferred per-service refactor, not this doc.)
6. **No secrets in logs** — never log API keys, tokens, full `.env`
   values, request bodies that may carry credentials.

**Trace correlation (forward-looking):** when a request/turn id exists,
pass it via the `data` field (`log_with_context(logger, msg,
trace_id=…)`) rather than string-concatenating into `message`, so a
future aggregator can group by it. Not retrofitted; the rule for new code.

**Status:** convention written and binding for new/refactored code.
Existing-code migration (rowboat/mirofish) remains explicitly deferred —
see Gap List #6.

### 10. GPU services — host-native by default, documented exception path

Most services follow §1 (`python:3.11-slim` / `node:18-alpine`). GPU ML
work does **not** — and that is deliberate, not a gap.

**Rule A — GPU ML stays host-native unless a real GPU server exists.**
The face-swap stack (FaceFusion / InstantID / inswapper, eyeTerm) is
hardware-coupled: GPU + physical webcam + multi-GB CUDA venvs +
Windows-path model caches. It is **intentionally NOT in
`infra/swarm/vibemind-stack.yml`**, same category as the documented
host-bound Bridge-venv / la-fungus-venv (`vibemind-stack.yml:43-45`).
Containerising it on a single-GPU box buys nothing (1 GPU = no
horizontal scale) and breaks portability (`nvidia/cuda` base only runs
on GPU hosts). Rationale + phased plan: `tasks/host-native-ml-tools.md`,
`tasks/gpu-offload-architecture-plan.md`.

**Rule B — when a GPU container IS built, it follows the GPU pattern:**

- Base image: `nvidia/cuda:12.x-runtime-…` (the **documented exception**
  to the §1 slim/alpine pin — GPU userspace libs must be present).
- Device reservation: copy the proven Ollama precedent —
  `openclaw/docker-compose.hotel.yml:76-81`
  (`deploy.resources.reservations.devices: [{driver: nvidia, count: all,
  capabilities: [gpu]}]`). One container **per physical GPU**
  (`--gpus device=N`), not one container "using all".
- Model cache (~30GB HF + insightface) is a **VOLUME, never baked** into
  the image (image-size + rebuild pain). Mount host dirs; first pull
  populates, workers share read-only.
- Healthcheck must prove the GPU is actually visible (`nvidia-smi -L`),
  not just that the port is open — a missing `--gpus` flag otherwise
  surfaces as a confusing CPU-fallback OOM far downstream.
- The API/dispatch contract does not change: `video.py
  _dispatch_swap_job` already has the `FACESWAP_BACKEND` local|remote
  seam, `eyeterm.py _resolve_live_swap_base` the same for live-stream.
  Remote mode fails **loud** when unconfigured (no silent local
  fallback). Reference recipe (NOT in default deploy):
  `vibemind-os/spaces/desktop/Automation_ui/backend/Dockerfile.gpu`.

**Rule C — the API backend stays CPU-slim.** The Automation_ui backend
image (`./Dockerfile`, `python:3.11-slim`, no torch) is correct and must
stay portable. GPU work is dispatched out of it, never linked into it.

## Gap List

These are real inconsistencies a standard *should* normalise, but which touch
**live, working services**. They are recorded here, **not auto-applied**,
because the env-handling and healthcheck changes are exactly the class of edit
that previously regressed rowboat — each needs its own verified change.

| # | Gap | Services | Status / Why deferred |
|---|---|---|---|
| 1 | No healthcheck | rowboat, rowboat-agents, rowboat-jobs-worker, rowboat-mongo, rowboat-redis | **CLOSED** (commit `c0be465`): all 5 have a healthcheck, each probe verified by running the exact `test:` inside the real container. See §2 lesson below. |
| 2 | env_file + `environment:` split | rowboat block vs brain/n8n/mirofish | **CLOSED BY AUDIT** (§5): the dangerous empty-override class was already fixed in B-next (env_file-first). The 3 remaining `${VAR}` expansions are compliant by design (renamed var + `:-default`, not the bug class), verified live. A migration would add risk for a non-existent bug — explicitly NOT done. |
| 3 | Zero labels | all 13 | **CLOSED** (commit `b699234`): vibemind.{service,tier,component,space} on all 13 services per §4; additive (deploy.labels = metadata), redeploy left all replicas at anchor, no restart. |
| 4 | Missing reservations | rowboat-redis, rowboat-jobs-worker | **CLOSED** (commit `c0be465`): both now have reservations (set alongside their healthchecks; conservative values, revisit if footprint measurement warrants) |
| 5 | Floating `:latest` (upstream) | qdrant, mongo, redis | **CLOSED** (commit `7ae4950`): pinned `image:tag@sha256:<digest>` to the exact verified-running digests (not a version bump). Redeploy left container IDs identical (zero recreation), data == baseline. |
| 6 | No structured logging | rowboat (console.log), mirofish (print) | **CONVENTION WRITTEN** (§9): the JSON schema + env contract + rules are now binding for new/refactored code. Existing-code migration (rowboat/mirofish) stays deferred — foreign app code in 2 submodules, own verified refactor. |

### §2 lesson — verify the check tool PER container (the hard way)

Closing Gap #1 cost a regression worth recording. The first `rowboat`
healthcheck used a `python3` probe **assuming** it shared the
`rowboat-agents` toolset. It did not: `rowboat` is `node:18-alpine`
(`node`, **no** python3), `rowboat-agents` has python3. The wrong probe
failed every cycle → Swarm churned the rowboat task to death (`Exited 0`)
→ this is *exactly* the "a wrong probe health-kills a working service"
trap this very document warns about. Fixed with a node-based probe and
re-verified. **Rule, now codified:** before adding a healthcheck, run the
literal `test:` command inside *that specific* running container; never
infer the available tool from a sibling service. (No data lost — churn
was container-level, the named volume persisted.)

**Closing a gap = its own feature branch + per-service verification + plan
update.** This document is the foundation; it does not itself change runtime
behaviour.

## §11. Server-Hardening Backlog (forward-pointer)

All 6 original Gap List items are closed (above). Closing them surfaced a
small number of *follow-up* hardening items — things that work today on a
single-node Docker Desktop swarm but need attention before a true
multi-node / server-grade deploy. They are tracked in **`tasks/gaps.md`**
(repo root) rather than re-opened here, so the Gap List stays a record of
what was closed and the live backlog has one home.

Summary of what's in `tasks/gaps.md`:

- D1 — existing-code logging migration (rowboat `console.log` →
  `brain_logger`-shaped JSON; mirofish `print` → same). Deferred from
  Gap #6 (CONVENTION WRITTEN).
- D2 — docker.sock DinD on `coding-api`/`coding-worker` (manager-pinned
  with documented trade-off today; SDK / rootless refactor for production).
- D3 — multi-node Linux-swarm hardening: `host.docker.internal`,
  `brain_data` named volume, `egress-proxy` internal-overlay isolation.
- Plus the Containerisation backlog (B1 minibook BLOCKED, B2 ideas,
  B3 desktop 6→1, B4 native services bridge/la-fungus/automation-ui).

Everything is **single-node-production-fine right now** — these are
explicit pre-conditions for moving services onto a remote server cluster.

## Files in this package

- `STANDARDS.md` — this document
- `base-python-3.11.Dockerfile` — annotated Python-service template
- `base-node-18.Dockerfile` — annotated Node-service template
- `service-block.template.yml` — copy-paste swarm service block (healthcheck +
  labels + resources + env rule, all conventions applied)
