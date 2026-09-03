# Brain-Core Embedder: Local Model → External API Design

Status: approved (design), not yet implemented
Date: 2026-07-13
Related: `VIBEMIND-DEPLOY-RECON.md` §0.2 (no-local-inference violation), `docs/ARCHITECTURE.md`

## Problem

`brain-core` (and the 5 services sharing its image/code — `brain-core`, `brain-api`,
`brain-autotrain-drain`, `brain-loops`, and the opt-in `brain-learner`/`brain-inference`)
loads `Qwen/Qwen3-Embedding-0.6B` locally via `sentence-transformers`
(`vibemind-os/brain/the_brain/core/qdrant_kg.py:60-62,212,227`) on every container start.
This violates the hard "no local inference" constraint for the target Proxmox deployment
(CPU-only VM — see `VIBEMIND-DEPLOY-RECON.md` §0.2) and has no existing config switch to
an external API. Unlike `mirofish` (also a violation, but trivially omittable), `brain-core`
is load-bearing KG infrastructure and cannot simply be dropped from the deploy.

Nine (soon possibly ten) Qdrant collections share this same 1024-dim vector space
(`COLLECTIONS` dict, `qdrant_kg.py:98-108`): `episodic`, `semantic`, `procedural`, `state`,
`artifacts`, `aggregated`, `mirofish`, `decisions`, `self`, and the opt-in `execlog`.

## Decision

Extract the embedder into its own microservice (`embedding-service`) that wraps the
OpenAI Embeddings API (`text-embedding-3-large`, full 3072-dim output). `brain-core`'s
`Embedder` class becomes a thin HTTP client with the same public interface it has today,
so its four call sites need no changes. Existing KG history is preserved via a one-time
re-embedding migration using Qdrant collection aliases for a safe, reversible cutover.

### Options considered

1. **Direct API calls from each of the 5 brain-core variants** (no new container). Simplest
   to write, but duplicates the OpenAI client/retry/secret-handling code five times, and each
   variant independently mounts `openai_api_key`. Rejected — doesn't serve future consumers
   (mirofish, rowboat) and spreads the credential further than necessary.
2. **In-process OpenAI SDK call, no new container** (library import, no network hop). Genuinely
   simpler operationally (no extra container to deploy/monitor/scale), but the same
   credential-spreading problem as option 1, and no shared reusable interface for other
   consumers. Considered, not chosen — user explicitly wants a dedicated, scalable unit.
3. **Dedicated `embedding-service` microservice** (chosen). One container, one place holding
   the OpenAI credential for embeddings, one interface other consumers (mirofish, rowboat-rag-worker)
   could adopt later without a redesign, independently scalable/swappable from `brain-core`
   itself. Trade-off: one more container to deploy and one more network hop per embed call.

## Architecture

```
brain-core (+4 sibling services)          embedding-service                OpenAI API
┌─────────────────────────┐   HTTP    ┌──────────────────────┐   HTTPS   ┌──────────┐
│ qdrant_kg.Embedder       │ ────────▶ │ POST /embed          │ ────────▶ │ text-     │
│  .encode(text)           │           │ POST /embed/batch    │           │ embedding-│
│  .encode_batch(texts)    │ ◀──────── │ GET  /health          │ ◀──────── │ 3-large   │
└─────────────────────────┘  vectors  └──────────────────────┘  vectors  └──────────┘
                                         holds openai_api_key
                                         secret (sole consumer
                                         for embedding purposes)
```

- New container `embedding-service`: own Dockerfile, no `torch`/`sentence-transformers`,
  a thin Python (or Node) HTTP wrapper around the OpenAI SDK. Runs on `vibemind-shared`
  overlay network. Lightweight resource footprint (no model weights in memory) — expect a
  small fraction of `brain-core`'s current CPU/memory limit; size this from real measurement
  during implementation rather than guessing a number up front.
- Interface:
  ```
  POST /embed        {"text": str}          -> {"vector": [float; 3072]}
  POST /embed/batch   {"texts": [str, ...]}  -> {"vectors": [[float; 3072], ...]}
  GET  /health        -> 200 if the OpenAI client is configured and reachable
  ```
- `qdrant_kg.py` changes:
  - `SEMANTIC_DIM` raised from `1024` to `3072`.
  - New env var `EMBEDDING_SERVICE_URL` (default `http://embedding-service:8080`).
  - `Embedder.__init__`/`encode`/`encode_batch` replace the `SentenceTransformer` call with
    an HTTP call to `embedding-service`. Method signatures unchanged.
  - The four existing call sites (`web/brain_server.py`, `core/tool_scope_selector.py`,
    `core/difficulty_router.py`, `qdrant_kg.py:499,756,929`) require **no changes** — they only
    know `Embedder.get().encode(...)`.
- `brain-core`'s Dockerfile drops `sentence-transformers` and `transformers` — but **not**
  `torch` itself: `web/routers/routing.py:7` hard-imports `torch` at module load for
  `RadialNetwork`/`SpaceRoutingHead` (a separate, unrelated routing subsystem), so `torch`
  stays installed. What *can* change is the `BRAIN_TORCH_VARIANT` build-arg default
  (`Dockerfile:49`, currently `cu121` specifically because the Qwen embedder benefited from
  CUDA) — once the embedder is gone, the routing heads are the only remaining `torch`
  consumer and there's no evidence they need CUDA, so the default can likely drop to a CPU-only
  wheel, still shrinking the image meaningfully even though `torch` itself remains. This should
  be verified against `routing.py`'s actual model usage during implementation, not assumed.
  Its `deploy.resources` memory limit (currently 6G, sized partly for "2 uvicorn workers ×
  ~1.5GB local model", stack-file comment at line 233) should be re-measured and lowered once
  the embedding model is out of the image, not assumed to shrink by a specific amount.

## Error handling

Per explicit decision: **hard fail, no silent degradation** — this deliberately departs from
the module's existing "Qdrant unreachable → no-op" philosophy for the embedding call specifically.

- `embedding-service` performs 1-2 short retries on transient network errors / 5xx / timeouts
  from OpenAI (tolerating a brief blip is not the same as silently degrading), then returns
  an error status if still failing.
- `Embedder.encode()`/`encode_batch()` propagate that failure as an exception — this boundary
  is the actual scope of the "hard fail" guarantee. **Correction (2026-07-13, added after the
  final holistic review):** the guarantee does NOT extend further up the call stack than that.
  `qdrant_kg.py`'s own internal call sites (`_upsert_point`, `_flush_thoughts`, `_build_edges`,
  `search`) catch the propagated exception and degrade gracefully (log + return `None`/`[]`,
  same as their existing "Qdrant unreachable" handling) rather than re-raise — a deliberate,
  separately-justified decision made during implementation (see commit `5de50f0` in the
  `vibemind-os` submodule) to avoid an unpredictable blast radius on callers elsewhere in the
  codebase that rely on that existing graceful-degradation behavior for other reasons (e.g.
  tolerating a Qdrant hiccup during bulk imports). Both real external callers
  (`difficulty_router.py`, `tool_scope_selector.py`) also catch-and-fall-back to a heuristic
  rather than propagate. So in practice: an embedding-service outage is loud (ERROR-level,
  distinguishable logs) but not fatal anywhere in the request path — it degrades the same way
  a Qdrant outage always has, it just now also covers embedding failures specifically.
- No local fallback path is kept anywhere in the code or image — dev on the Windows machine
  uses the same `embedding-service` call as production. One code path, not two.

## Scope

V1 covers only the `brain-core` family. `rowboat-rag-worker` already calls
`text-embedding-3-small` directly (stack-file line 898) and is left as-is — it isn't part of
the compliance violation and touching it isn't justified by this work. `mirofish` is already
slated for removal from the default deploy (recon §0.1) and is out of scope. The
`embedding-service` interface is generic enough that either could adopt it later without a
redesign, but that is explicitly not part of this change.

## Migration (preserving existing KG history)

Qdrant does not support changing a collection's vector dimension in place, so this uses a
blue-green cutover via Qdrant collection aliases:

1. For each of the collections in the `COLLECTIONS` dict (`qdrant_kg.py:98-108`), create a new
   physical collection with a version suffix, e.g. `brain-episodic-3072-v1`, at 3072-dim.
2. Introduce an alias layer: application code continues to reference the existing logical
   names (e.g. `brain-episodic`); that name becomes a Qdrant alias pointing at the new physical
   collection once cutover happens. No code beyond collection-creation/lookup needs to know
   about physical vs. alias names.
3. One-time migration script (`vibemind-os/brain/the_brain/scripts/migrate_embeddings_v3072.py`,
   following the existing `scripts/` convention):
   - `scroll()` through every point in each old collection.
   - Recover the text that was originally embedded: prefer reading it verbatim from the
     payload if stored there; otherwise reconstruct it via the same text-assembly logic used
     at write time (call sites `qdrant_kg.py:499,756,929`) — confirm which applies per
     collection during implementation planning, so the re-embedded text is guaranteed
     semantically identical to the original.
   - Batch the texts (~100 per call) through `embedding-service:/embed/batch`.
   - Upsert into the new collection using the **same point IDs** (deterministic UUIDs derived
     from `external_id`, `qdrant_kg.py:346-349` — stable across the migration) and the
     unmodified payload; only the vector changes.
   - Compare point counts old vs. new per collection as a sanity check.
4. Cutover: scale `brain-core` (+ siblings) to `replicas: 0`, run the migration script against
   the frozen collections, deploy the updated code (`EMBEDDING_SERVICE_URL` set, new
   `SEMANTIC_DIM`), point the aliases at the new collections, scale `brain-core` back up.
   A brief maintenance window is an accepted trade-off here — this is not a high-traffic
   system, and a two-pass delta-sync for zero-downtime would be over-engineering for the
   actual scale involved.
5. Rollback: until the alias is repointed, the old collections are untouched — abort any time
   with zero risk to production data. If problems surface after cutover, repoint the alias
   back to the old 1024-dim collection (kept around for a transition period, not deleted
   immediately).

## Testing

- `Embedder` HTTP client against a mocked `embedding-service`: request/response shape, retry
  behavior, exception propagation on failure.
- `embedding-service` itself against OpenAI (or a mock): `/embed`, `/embed/batch`, `/health`,
  correct 3072-dim output shape.
- Migration script: a dry-run mode that only compares point counts without writing, run before
  any real migration.
- `vibemind-os/brain/the_brain/tests/test_embeddings.py` turns out to test an unrelated module
  (`core.semantic_coherence.SemanticEncoder`, not `qdrant_kg.Embedder`) and isn't a real pytest
  test (no `test_` function, executes top-level) — it needs no changes for this work. There is
  currently no test coverage for `qdrant_kg.Embedder` at all, so implementation adds a new test
  file rather than rewriting an existing one.
- Post-cutover smoke test: a known KG query through `brain-core` returns sane results (no
  NaN/zero vectors, reasonable cosine similarities).

## Addendum (found during implementation, 2026-07-13): EventRoutingHead stays local

While implementing the Dockerfile cleanup task, a **second, independent** local-inference
consumer in `brain-core` was discovered that this spec did not originally account for:
`EventRoutingHead` (`vibemind-os/brain/the_brain/core/event_routing_head.py`, wired up in
`web/brain_server.py:1234-1279`) loads `sentence-transformers`' multilingual
`paraphrase-multilingual-MiniLM-L12-v2` (384-dim) to embed text for real-time intent
classification. This is completely unrelated to the Qwen/KG embedder this spec migrates —
different model, different dimension, different purpose (123-way event-type routing against
learned centroids persisted in `event_routing_head.pt`), and used live per-request from
`web/routers/classification.py`'s `/api/cortex/classify` and `/api/cortex/classify/train`.

**Decision: `EventRoutingHead` stays on local inference. It is not migrated to
`embedding-service`.** `web/routers/classification.py:76` documents a hard **"Target latency:
<100ms"** for this endpoint — real-time interactive use. A network hop to `embedding-service`
(itself calling out to OpenAI, plus its own 1-2 retries on transient failures) realistically
costs 100-500ms+ per call, which would blow that budget outright. Unlike the KG embedder (no
comparable latency SLA anywhere in its call paths), this one has an explicit, documented
real-time requirement that local inference is the only way to meet.

Practical consequence for the Dockerfile-cleanup task: `sentence-transformers`/`transformers`
**stay installed** in `brain-core`'s image (this is now a deliberate, accepted exception to the
no-local-inference goal, not an oversight — see `[[project_eventroutinghead_stays_local]]` in
project memory for future audits). The only change that still lands: `BRAIN_TORCH_VARIANT`'s
default flips from `cu121` to `cpu`, since the Qwen embedder (now migrated) was the sole reason
that build-arg defaulted to a CUDA wheel — `EventRoutingHead`'s MiniLM+cosine-similarity work
has no documented GPU requirement.

## Explicitly out of scope

- Changing `rowboat-rag-worker`'s or `mirofish`'s embedding calls.
- Zero-downtime delta-sync migration tooling.
- A local-inference fallback/dev mode for the KG embedder — deliberately removed, not preserved
  behind a flag. (Does not apply to `EventRoutingHead`'s SBERT — see addendum above, kept local
  by design, not a fallback mode.)
- Migrating `EventRoutingHead`'s SBERT usage to `embedding-service` — see addendum above; ruled
  out by its `<100ms` real-time latency requirement.
- Resizing `brain-core`'s resource limits to a specific new number (measure after the fact).
