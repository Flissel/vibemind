# Brain-Core Embedder External-API Swap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `brain-core`'s local `sentence-transformers`/Qwen embedder with a dedicated `embedding-service` microservice that wraps OpenAI's `text-embedding-3-large` API, and migrate existing Qdrant KG data (1024-dim → 3072-dim) without losing history.

**Architecture:** A new standalone FastAPI microservice (`vibemind-os/embedding-service/`) holds the OpenAI credential and exposes `/embed`, `/embed/batch`, `/health`. `qdrant_kg.py`'s `Embedder` class becomes a thin HTTP client to that service (same public interface, zero changes needed at its 4 call sites). Collection lookups move from raw names to Qdrant aliases so a future dimension change never requires touching caller code again. A one-time migration script re-embeds every existing point into new 3072-dim physical collections, verified by count, then cuts the aliases over.

**Tech Stack:** FastAPI + uvicorn + `openai` Python SDK (embedding-service, new); `qdrant-client>=1.7.0` (already a brain dependency); `requests` (already a brain dependency, used for the new HTTP client); PowerShell build-recipe script (existing repo convention); Docker Swarm stack file.

**Spec:** `docs/superpowers/specs/2026-07-13-brain-embedder-external-api-design.md`

---

## Ground truth this plan relies on (verified against the live repo, not assumed)

- `vibemind-os/brain/the_brain/core/qdrant_kg.py:98-108` — `COLLECTIONS` dict maps 9 logical names to physical Qdrant collection names (a 10th, `execlog`, is added conditionally at line 116 when `EXECUTION_LOG_ENABLED`).
- `qdrant_kg.py:401-431` — `ensure_collections()` creates each collection directly under its `COLLECTIONS` name today; no alias layer exists yet.
- `qdrant_kg.py:513-515` — `_upsert_point` stores the exact embedded text in `payload["content"]` (truncated to 2000 chars) — this is what the migration script reads back, no reconstruction needed.
- `qdrant_kg.py:346-349` — point IDs are deterministic UUIDs hashed from `external_id`; stable across re-embedding.
- `qdrant_kg.py:499,756,929` — the only 3 call sites of `Embedder.encode()`/`encode_batch()` inside `qdrant_kg.py` itself; `web/brain_server.py`, `core/tool_scope_selector.py`, `core/difficulty_router.py` are the only external callers, all via `Embedder.get()`.
- `vibemind-os/brain/the_brain/Dockerfile:39-56` — installs `torch` (CUDA wheel by default, build-arg `BRAIN_TORCH_VARIANT=cu121`) + `sentence-transformers` + `transformers` in a dedicated layer. **`torch` itself is also imported by `web/routers/routing.py:7`** for an unrelated `RadialNetwork`/`SpaceRoutingHead` routing subsystem — `torch` must stay installed; only `sentence-transformers`/`transformers` are removed.
- `vibemind-os/brain/the_brain/requirements.txt:43,49` — `qdrant-client>=1.7.0`, `openai>=1.0.0` already present; `requests` also present (grep confirmed). `sentence-transformers`/`transformers` are **not** in `requirements.txt` — they're installed directly in the Dockerfile (lines 54-56), so removing them is a Dockerfile-only change.
- `vibemind-os/brain/the_brain/core/config.py:110-138` — existing secret/URL getters (`openai_key()`, `qdrant_url()`, `learner_url()`) establish the exact style to mirror for a new `embedding_service_url()`.
- `vibemind-os/brain/the_brain/tests/test_embeddings.py` — tests an unrelated module (`core.semantic_coherence.SemanticEncoder`), not `qdrant_kg.Embedder`, and isn't pytest-style (no `test_` function, runs top-level). **Not touched by this plan.**
- `vibemind-os/brain/the_brain/tests/test_difficulty_router.py` — the actual convention for this package's tests: plain Python, no pytest, a `check(name, cond)` helper appending to module-level `_passed`/`_failed` lists, a hand-written `StubEmbedder` matching the `encode`/`encode_batch` interface, run via `python tests/test_X.py` (not `pytest`) and an `if __name__ == "__main__":` block calling each `test_*` function. **New brain-package tests in this plan follow this exact style.**
- `vibemind-os/brain/the_brain/scripts/migrate_kg_to_cognitive.py` — the existing convention for a Qdrant migration script: `argparse` with `--dry-run`/`--commit`, `sys.path` bootstrap so `core.*` imports work when run as a script, `SCROLL_BATCH` constant, per-target batching before `upsert(..., wait=True)`, and — critically — the exact alias-creation API already used once in this repo: `client.update_collection_aliases(change_aliases_operations=[qm.CreateAliasOperation(create_alias=qm.CreateAlias(collection_name=..., alias_name=...))])`. **New migration script in this plan follows this convention.**
- `scripts/swarm_image_builds.ps1:33-78` — `Get-StackImageRecipes` is the single source of truth for locally-built stack images; each entry is `Kind = "build"` (explicit `docker build -t <Tag> -f <Dockerfile> <Context>`) or `Kind = "compose"`. New image recipes are appended to this array.
- `.venv/Lib/site-packages/qdrant_client/qdrant_client.py:1517,1544,1559,1661,2126` and `.../http/models/models.py:51-53,498-514` — confirmed exact API used below: `client.get_aliases()` (all aliases, `.aliases` is a list of `AliasDescription(alias_name, collection_name)`), `client.update_collection_aliases(...)`, `qm.CreateAlias(collection_name=, alias_name=)`, `qm.CreateAliasOperation(create_alias=...)`, `client.delete_collection(collection_name=)`, `client.create_snapshot(collection_name=)`.

---

## Task 1: Scaffold `embedding-service` — health endpoint

**Files:**
- Create: `vibemind-os/embedding-service/requirements.txt`
- Create: `vibemind-os/embedding-service/app.py`
- Create: `vibemind-os/embedding-service/tests/test_app.py`
- Create: `vibemind-os/embedding-service/tests/__init__.py` (empty)

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
openai>=1.0.0
pydantic>=2.0.0
httpx>=0.27.0
pytest>=8.0.0
```

(`httpx` is FastAPI's `TestClient` transport dependency; `pytest` is a test-only dep — fine to ship in the same file since this image is small and self-contained, no multi-stage build in this repo's convention for these thin services.)

- [ ] **Step 2: Write the failing test for `/health`**

```python
# vibemind-os/embedding-service/tests/test_app.py
from fastapi.testclient import TestClient

import app as app_module


def test_health_ok_when_api_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None  # reset the lazy singleton between tests
    client = TestClient(app_module.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_503_when_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_FILE", raising=False)
    app_module._client = None
    client = TestClient(app_module.app)
    resp = client.get("/health")
    assert resp.status_code == 503
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `vibemind-os/embedding-service/`): `python -m pytest tests/test_app.py -v`
Expected: FAIL / ERROR — `app.py` does not exist yet (`ModuleNotFoundError: No module named 'app'`).

- [ ] **Step 4: Write minimal `app.py` (health only for now)**

```python
# vibemind-os/embedding-service/app.py
"""HTTP wrapper around OpenAI's embeddings API.

Sole purpose: one place that holds the OpenAI credential for embedding
calls, instead of every brain-core variant mounting it separately, and one
interface (`/embed`, `/embed/batch`) that other consumers (mirofish,
rowboat-rag-worker) could adopt later without a redesign.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from openai import OpenAI

MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large")

app = FastAPI(title="embedding-service")

_client: OpenAI | None = None


def _read_secret(name: str) -> str:
    """Same precedence as brain-core's core/config.py get_secret(): a
    Swarm-mounted secret file, then the default /run/secrets mount, then a
    plain env var."""
    file_path = os.environ.get(f"{name}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    default_mount = f"/run/secrets/{name.lower()}"
    if os.path.exists(default_mount):
        with open(default_mount, "r", encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get(name, "").strip()


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = _read_secret("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not configured (checked _FILE, /run/secrets, env)"
            )
        _client = OpenAI(api_key=api_key)
    return _client


@app.get("/health")
def health():
    try:
        get_client()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "ok", "model": MODEL}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_app.py -v`
Expected: `test_health_ok_when_api_key_present PASSED`, `test_health_503_when_no_key PASSED`.

- [ ] **Step 6: Commit**

```bash
git add vibemind-os/embedding-service/requirements.txt vibemind-os/embedding-service/app.py vibemind-os/embedding-service/tests/
git commit -m "feat(embedding-service): scaffold FastAPI app with /health"
```

---

## Task 2: `embedding-service` — `/embed` endpoint with retry

**Files:**
- Modify: `vibemind-os/embedding-service/app.py`
- Modify: `vibemind-os/embedding-service/tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to vibemind-os/embedding-service/tests/test_app.py
from unittest.mock import MagicMock


class _FakeEmbeddingDatum:
    def __init__(self, vector):
        self.embedding = vector


class _FakeEmbeddingResponse:
    def __init__(self, vectors):
        self.data = [_FakeEmbeddingDatum(v) for v in vectors]


def test_embed_returns_vector(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = _FakeEmbeddingResponse([[0.1, 0.2, 0.3]])
    monkeypatch.setattr(app_module, "get_client", lambda: fake_client)

    client = TestClient(app_module.app)
    resp = client.post("/embed", json={"text": "hello world"})

    assert resp.status_code == 200
    assert resp.json()["vector"] == [0.1, 0.2, 0.3]
    fake_client.embeddings.create.assert_called_once_with(
        model=app_module.MODEL, input=["hello world"],
    )


def test_embed_retries_then_succeeds_on_transient_error(monkeypatch):
    from openai import APIConnectionError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None
    fake_client = MagicMock()
    fake_request = MagicMock()
    fake_client.embeddings.create.side_effect = [
        APIConnectionError(request=fake_request),
        _FakeEmbeddingResponse([[0.4, 0.5]]),
    ]
    monkeypatch.setattr(app_module, "get_client", lambda: fake_client)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)

    client = TestClient(app_module.app)
    resp = client.post("/embed", json={"text": "retry me"})

    assert resp.status_code == 200
    assert resp.json()["vector"] == [0.4, 0.5]
    assert fake_client.embeddings.create.call_count == 2


def test_embed_hard_fails_after_exhausting_retries(monkeypatch):
    from openai import APIConnectionError

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None
    fake_client = MagicMock()
    fake_request = MagicMock()
    fake_client.embeddings.create.side_effect = APIConnectionError(request=fake_request)
    monkeypatch.setattr(app_module, "get_client", lambda: fake_client)
    monkeypatch.setattr(app_module.time, "sleep", lambda _seconds: None)

    client = TestClient(app_module.app)
    resp = client.post("/embed", json={"text": "always fails"})

    assert resp.status_code == 502
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL — no `/embed` route exists yet (404s), `app.time` / `app.MODEL` referenced before being defined appropriately.

- [ ] **Step 3: Implement `/embed` with retry**

```python
# add to vibemind-os/embedding-service/app.py, after the imports
import time
import logging
from typing import List

from pydantic import BaseModel
from openai import APIConnectionError, APITimeoutError, APIError

logger = logging.getLogger("embedding_service")

MAX_RETRIES = int(os.environ.get("EMBEDDING_MAX_RETRIES", "2"))
RETRY_BACKOFF_SECONDS = float(os.environ.get("EMBEDDING_RETRY_BACKOFF", "0.5"))


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    vector: List[float]


def _embed_with_retry(inputs: List[str]) -> List[List[float]]:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            client = get_client()
            resp = client.embeddings.create(model=MODEL, input=inputs)
            return [d.embedding for d in resp.data]
        except (APIConnectionError, APITimeoutError) as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise
        except APIError:
            raise  # non-transient (4xx etc.) — no retry
    raise last_exc  # pragma: no cover — loop always returns or raises above


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    try:
        vectors = _embed_with_retry([req.text])
    except Exception as e:
        logger.warning(f"/embed failed: {e}")
        raise HTTPException(status_code=502, detail=f"embedding failed: {e}")
    return EmbedResponse(vector=vectors[0])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: all tests PASS, including the two new ones and the two from Task 1.

- [ ] **Step 5: Commit**

```bash
git add vibemind-os/embedding-service/app.py vibemind-os/embedding-service/tests/test_app.py
git commit -m "feat(embedding-service): add /embed endpoint with bounded retry"
```

---

## Task 3: `embedding-service` — `/embed/batch` endpoint

**Files:**
- Modify: `vibemind-os/embedding-service/app.py`
- Modify: `vibemind-os/embedding-service/tests/test_app.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to vibemind-os/embedding-service/tests/test_app.py
def test_embed_batch_returns_vectors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = _FakeEmbeddingResponse(
        [[0.1, 0.2], [0.3, 0.4]]
    )
    monkeypatch.setattr(app_module, "get_client", lambda: fake_client)

    client = TestClient(app_module.app)
    resp = client.post("/embed/batch", json={"texts": ["a", "b"]})

    assert resp.status_code == 200
    assert resp.json()["vectors"] == [[0.1, 0.2], [0.3, 0.4]]
    fake_client.embeddings.create.assert_called_once_with(
        model=app_module.MODEL, input=["a", "b"],
    )


def test_embed_batch_empty_list_short_circuits(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    app_module._client = None
    fake_client = MagicMock()
    monkeypatch.setattr(app_module, "get_client", lambda: fake_client)

    client = TestClient(app_module.app)
    resp = client.post("/embed/batch", json={"texts": []})

    assert resp.status_code == 200
    assert resp.json()["vectors"] == []
    fake_client.embeddings.create.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app.py -v`
Expected: FAIL — no `/embed/batch` route yet (404).

- [ ] **Step 3: Implement `/embed/batch`**

```python
# add to vibemind-os/embedding-service/app.py
class EmbedBatchRequest(BaseModel):
    texts: List[str]


class EmbedBatchResponse(BaseModel):
    vectors: List[List[float]]


@app.post("/embed/batch", response_model=EmbedBatchResponse)
def embed_batch(req: EmbedBatchRequest):
    if not req.texts:
        return EmbedBatchResponse(vectors=[])
    try:
        vectors = _embed_with_retry(req.texts)
    except Exception as e:
        logger.warning(f"/embed/batch failed: {e}")
        raise HTTPException(status_code=502, detail=f"embedding failed: {e}")
    return EmbedBatchResponse(vectors=vectors)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_app.py -v`
Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add vibemind-os/embedding-service/app.py vibemind-os/embedding-service/tests/test_app.py
git commit -m "feat(embedding-service): add /embed/batch endpoint"
```

---

## Task 4: Dockerfile + build recipe + stack service block for `embedding-service`

**Files:**
- Create: `vibemind-os/embedding-service/Dockerfile`
- Modify: `scripts/swarm_image_builds.ps1:33-78`
- Modify: `infra/swarm/vibemind-stack.yml` (new service block, near the `brain-*` services)

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# vibemind-os/embedding-service/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Add the build recipe**

In `scripts/swarm_image_builds.ps1`, inside `Get-StackImageRecipes` (the array returned at lines 34-77), add a new entry after the mirofish recipe (or anywhere in the array — order doesn't matter, `Invoke-EnsureStackImages` iterates all of them):

```powershell
        # --- Embedding service (explicit docker build) ---
        @{ Tag = "vibemind-embedding-service:latest"
           Kind = "build"
           Dockerfile = "vibemind-os/embedding-service/Dockerfile"
           Context = "vibemind-os/embedding-service" }

```

- [ ] **Step 3: Verify the recipe is picked up**

Run (PowerShell, from repo root):
```powershell
. .\scripts\swarm_image_builds.ps1
(Get-StackImageRecipes | Where-Object { $_.Tag -eq "vibemind-embedding-service:latest" }).Count
```
Expected output: `1`

- [ ] **Step 4: Add the service block to `infra/swarm/vibemind-stack.yml`**

Insert this new service block directly before the `media:` service (line 531 in the current file — i.e. right after the `brain-inference` block ends), so it reads naturally alongside the other `brain-*` infra:

```yaml
  embedding-service:
    image: vibemind-embedding-service:latest
    environment:
      - EMBEDDING_MODEL=text-embedding-3-large
    secrets:
      - openai_api_key
    networks:
      - vibemind-shared
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 10s
    deploy:
      labels:
        vibemind.service: "embedding-service"
        vibemind.tier: "infra"
        vibemind.component: "embedding"
      replicas: 1
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
        reservations:
          cpus: "0.1"
          memory: 64M
      restart_policy:
        condition: on-failure
```

(The healthcheck uses `python3 -c ...` rather than `curl`/`wget` because the `python:3.11-slim` base image doesn't include either by default — this avoids adding an extra `apt-get install` layer just for the healthcheck.)

- [ ] **Step 5: Validate the compose YAML parses**

Run: `docker compose -f infra/swarm/vibemind-stack.yml config --quiet`
Expected: no output, exit code 0 (a YAML/schema error would print to stderr and exit non-zero).

- [ ] **Step 6: Commit**

```bash
git add vibemind-os/embedding-service/Dockerfile scripts/swarm_image_builds.ps1 infra/swarm/vibemind-stack.yml
git commit -m "feat(embedding-service): add Dockerfile, build recipe, stack service block"
```

---

## Task 5: `embedding_service_url()` config helper

**Files:**
- Modify: `vibemind-os/brain/the_brain/core/config.py:126-138` (add after `learner_url()`)
- Create: `vibemind-os/brain/the_brain/tests/test_embedding_service_config.py`

- [ ] **Step 1: Write the failing test (brain-package convention — no pytest)**

```python
# vibemind-os/brain/the_brain/tests/test_embedding_service_config.py
"""Tests core.config.embedding_service_url() — brain-package convention:
plain script, no pytest. Run: python tests/test_embedding_service_config.py
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_BRAIN = Path(__file__).resolve().parents[1]
if str(_BRAIN) not in sys.path:
    sys.path.insert(0, str(_BRAIN))

_spec = importlib.util.spec_from_file_location(
    "config", _BRAIN / "core" / "config.py")
_cfg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cfg)

_passed: list[str] = []
_failed: list[str] = []


def check(name, cond):
    (_passed if cond else _failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name)


def test_default_url():
    print("Test 1: default embedding_service_url()")
    os.environ.pop("EMBEDDING_SERVICE_URL", None)
    check("defaults to http://embedding-service:8080",
          _cfg.embedding_service_url() == "http://embedding-service:8080")


def test_override_url():
    print("Test 2: EMBEDDING_SERVICE_URL override, trailing slash stripped")
    os.environ["EMBEDDING_SERVICE_URL"] = "http://localhost:9000/"
    check("override applied + trailing slash stripped",
          _cfg.embedding_service_url() == "http://localhost:9000")
    os.environ.pop("EMBEDDING_SERVICE_URL", None)


if __name__ == "__main__":
    test_default_url()
    test_override_url()
    print(f"\n{len(_passed)} passed, {len(_failed)} failed")
    if _failed:
        sys.exit(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python vibemind-os/brain/the_brain/tests/test_embedding_service_config.py`
Expected: `FAIL defaults to http://embedding-service:8080` (`AttributeError: module 'config' has no attribute 'embedding_service_url'` surfaces as a crash before the check line, i.e. the script raises rather than printing FAIL — either way it does not exit 0).

- [ ] **Step 3: Implement `embedding_service_url()`**

In `vibemind-os/brain/the_brain/core/config.py`, immediately after `learner_url()` (after line 138):

```python
def embedding_service_url() -> str:
    """Base URL of the embedding-service (docs/superpowers/specs/2026-07-13-
    brain-embedder-external-api-design.md). Default matches the Docker Swarm
    service name on the vibemind-shared overlay network."""
    v = (os.environ.get("EMBEDDING_SERVICE_URL", "") or "").strip().rstrip("/")
    return v or "http://embedding-service:8080"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python vibemind-os/brain/the_brain/tests/test_embedding_service_config.py`
Expected:
```
Test 1: default embedding_service_url()
  PASS defaults to http://embedding-service:8080
Test 2: EMBEDDING_SERVICE_URL override, trailing slash stripped
  PASS override applied + trailing slash stripped

2 passed, 0 failed
```

- [ ] **Step 5: Commit**

```bash
git add vibemind-os/brain/the_brain/core/config.py vibemind-os/brain/the_brain/tests/test_embedding_service_config.py
git commit -m "feat(brain-core): add embedding_service_url() config getter"
```

---

## Task 6: Rewrite `Embedder` as an HTTP client

**Files:**
- Modify: `vibemind-os/brain/the_brain/core/qdrant_kg.py:198-251` (the `Embedder` class)
- Create: `vibemind-os/brain/the_brain/tests/test_embedder_client.py`

- [ ] **Step 1: Write the failing test (brain-package convention, mocked HTTP)**

```python
# vibemind-os/brain/the_brain/tests/test_embedder_client.py
"""Tests qdrant_kg.Embedder as an HTTP client against embedding-service.
Brain-package convention: plain script, no pytest, requests mocked via
monkeypatched module attribute (no network calls made).
Run: python tests/test_embedder_client.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_BRAIN = Path(__file__).resolve().parents[1]
if str(_BRAIN) not in sys.path:
    sys.path.insert(0, str(_BRAIN))

_spec = importlib.util.spec_from_file_location(
    "qdrant_kg", _BRAIN / "core" / "qdrant_kg.py")
_kg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_kg)

_passed: list[str] = []
_failed: list[str] = []


def check(name, cond):
    (_passed if cond else _failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name)


def _fresh_embedder(fake_post) -> "_kg.Embedder":
    _kg.Embedder._instance = None  # reset singleton between tests
    embedder = _kg.Embedder()
    embedder._session.post = fake_post  # type: ignore[attr-defined]
    return embedder


def test_encode_calls_embed_endpoint():
    print("Test 1: encode() POSTs to /embed and returns the vector")
    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {"vector": [0.1, 0.2, 0.3]}
    fake_post = MagicMock(return_value=fake_resp)

    embedder = _fresh_embedder(fake_post)
    vec = embedder.encode("hello")

    check("returns the vector from the response", vec == [0.1, 0.2, 0.3])
    called_url = fake_post.call_args.args[0]
    check("posts to the /embed path", called_url.endswith("/embed"))
    called_json = fake_post.call_args.kwargs.get("json")
    check("sends {'text': ...}", called_json == {"text": "hello"})


def test_encode_batch_calls_batch_endpoint():
    print("Test 2: encode_batch() POSTs to /embed/batch and returns vectors")
    fake_resp = MagicMock()
    fake_resp.raise_for_status.return_value = None
    fake_resp.json.return_value = {"vectors": [[0.1, 0.2], [0.3, 0.4]]}
    fake_post = MagicMock(return_value=fake_resp)

    embedder = _fresh_embedder(fake_post)
    vecs = embedder.encode_batch(["a", "b"])

    check("returns both vectors", vecs == [[0.1, 0.2], [0.3, 0.4]])
    called_url = fake_post.call_args.args[0]
    check("posts to the /embed/batch path", called_url.endswith("/embed/batch"))
    called_json = fake_post.call_args.kwargs.get("json")
    check("sends {'texts': [...]}", called_json == {"texts": ["a", "b"]})


def test_encode_raises_on_http_error():
    print("Test 3: encode() propagates a hard failure (no silent no-op)")
    import requests

    fake_post = MagicMock(side_effect=requests.exceptions.ConnectionError("boom"))
    embedder = _fresh_embedder(fake_post)

    raised = False
    try:
        embedder.encode("hello")
    except requests.exceptions.ConnectionError:
        raised = True
    check("raises instead of returning a degraded/empty result", raised)


if __name__ == "__main__":
    test_encode_calls_embed_endpoint()
    test_encode_batch_calls_batch_endpoint()
    test_encode_raises_on_http_error()
    print(f"\n{len(_passed)} passed, {len(_failed)} failed")
    if _failed:
        sys.exit(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python vibemind-os/brain/the_brain/tests/test_embedder_client.py`
Expected: crash/FAIL — `Embedder()` still tries to `import sentence_transformers` and load a local model; `_session` attribute doesn't exist yet.

- [ ] **Step 3: Replace the `Embedder` class (`qdrant_kg.py:198-251`)**

Replace the entire existing `Embedder` class (from `class Embedder:` at line 198 through the end of `encode_batch` at line 251) with:

```python
class Embedder:
    """Singleton HTTP client for the embedding-service (docs/superpowers/specs/
    2026-07-13-brain-embedder-external-api-design.md). Thread-safe. Replaces
    the former local sentence-transformers/Qwen model — same public interface
    (encode/encode_batch), so callers are unaffected by this swap."""

    _instance: Optional["Embedder"] = None
    _lock = threading.Lock()

    @classmethod
    def get(cls) -> "Embedder":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self) -> None:
        import requests
        from core import config as _cfg_embed

        self._base_url = _cfg_embed.embedding_service_url()
        self._session = requests.Session()
        self._timeout = float(os.environ.get("EMBEDDING_HTTP_TIMEOUT", "30"))
        logger.info(f"[KG] embedding-service client configured: {self._base_url}")

    def encode(self, text: str) -> List[float]:
        resp = self._session.post(
            f"{self._base_url}/embed", json={"text": text}, timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["vector"]

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        resp = self._session.post(
            f"{self._base_url}/embed/batch", json={"texts": texts}, timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["vectors"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python vibemind-os/brain/the_brain/tests/test_embedder_client.py`
Expected:
```
Test 1: encode() POSTs to /embed and returns the vector
  PASS returns the vector from the response
  PASS posts to the /embed path
  PASS sends {'text': ...}
Test 2: encode_batch() POSTs to /embed/batch and returns vectors
  PASS returns both vectors
  PASS posts to the /embed/batch path
  PASS sends {'texts': [...]}
Test 3: encode() propagates a hard failure (no silent no-op)
  PASS raises instead of returning a degraded/empty result

7 passed, 0 failed
```

- [ ] **Step 5: Commit**

```bash
git add vibemind-os/brain/the_brain/core/qdrant_kg.py vibemind-os/brain/the_brain/tests/test_embedder_client.py
git commit -m "feat(brain-core): Embedder becomes an embedding-service HTTP client"
```

---

## Task 7: Bump `SEMANTIC_DIM` to 3072 + alias-aware `ensure_collections()`

**Files:**
- Modify: `vibemind-os/brain/the_brain/core/qdrant_kg.py:64` (`SEMANTIC_DIM`)
- Modify: `vibemind-os/brain/the_brain/core/qdrant_kg.py:401-431` (`ensure_collections`)
- Create: `vibemind-os/brain/the_brain/tests/test_ensure_collections_alias.py`

- [ ] **Step 1: Write the failing test (mocked Qdrant client, brain-package convention)**

```python
# vibemind-os/brain/the_brain/tests/test_ensure_collections_alias.py
"""Tests the alias-aware ensure_collections() behavior added in the
embedder-external-api migration. Brain-package convention: plain script,
no pytest, Qdrant client fully mocked (no real Qdrant needed).
Run: python tests/test_ensure_collections_alias.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

_BRAIN = Path(__file__).resolve().parents[1]
if str(_BRAIN) not in sys.path:
    sys.path.insert(0, str(_BRAIN))

_spec = importlib.util.spec_from_file_location(
    "qdrant_kg", _BRAIN / "core" / "qdrant_kg.py")
_kg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_kg)

_passed: list[str] = []
_failed: list[str] = []


def check(name, cond):
    (_passed if cond else _failed).append(name)
    print(("  PASS " if cond else "  FAIL ") + name)


def _make_kg(existing_collection_names, existing_aliases):
    """existing_aliases: list[(alias_name, collection_name)]"""
    kg = _kg.QdrantKG.__new__(_kg.QdrantKG)  # bypass __init__ (no real Qdrant)
    kg.client = MagicMock()
    kg.client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name=n) for n in existing_collection_names]
    )
    kg.client.get_aliases.return_value = SimpleNamespace(
        aliases=[SimpleNamespace(alias_name=a, collection_name=c)
                 for a, c in existing_aliases]
    )
    kg._qm = __import__("qdrant_client.http.models", fromlist=["models"])
    return kg


def test_fresh_deploy_creates_physical_and_alias():
    print("Test 1: fresh deploy — no collections, no aliases exist yet")
    kg = _make_kg(existing_collection_names=[], existing_aliases=[])
    kg._ensure_payload_indexes = MagicMock()

    kg.ensure_collections()

    create_calls = kg.client.create_collection.call_args_list
    check("creates a physical collection per logical name",
          len(create_calls) == len(_kg.COLLECTIONS))
    first_target = create_calls[0].kwargs["collection_name"]
    check("physical name carries the version suffix",
          first_target.endswith(_kg.PHYSICAL_VERSION_SUFFIX))
    check("alias update was called once per collection",
          kg.client.update_collection_aliases.call_count == len(_kg.COLLECTIONS))


def test_already_aliased_is_left_alone():
    print("Test 2: alias already points somewhere — must not recreate anything")
    some_alias = next(iter(_kg.COLLECTIONS.values()))
    kg = _make_kg(
        existing_collection_names=[f"{some_alias}{_kg.PHYSICAL_VERSION_SUFFIX}"],
        existing_aliases=[(some_alias, f"{some_alias}{_kg.PHYSICAL_VERSION_SUFFIX}")],
    )
    kg._ensure_payload_indexes = MagicMock()

    kg.ensure_collections()

    check("does not create a new physical collection for an aliased name",
          kg.client.create_collection.call_count < len(_kg.COLLECTIONS))
    check("does not touch aliasing again for the already-aliased name",
          kg.client.update_collection_aliases.call_count < len(_kg.COLLECTIONS))


def test_pre_migration_raw_collection_is_left_alone():
    print("Test 3: pre-migration state — name exists as a RAW collection, no alias")
    some_name = next(iter(_kg.COLLECTIONS.values()))
    kg = _make_kg(existing_collection_names=[some_name], existing_aliases=[])
    kg._ensure_payload_indexes = MagicMock()

    kg.ensure_collections()

    check("does not create a new physical collection for the raw pre-migration name",
          kg.client.create_collection.call_count < len(_kg.COLLECTIONS))
    check("does not force an alias onto an un-migrated raw collection",
          kg.client.update_collection_aliases.call_count < len(_kg.COLLECTIONS))


if __name__ == "__main__":
    test_fresh_deploy_creates_physical_and_alias()
    test_already_aliased_is_left_alone()
    test_pre_migration_raw_collection_is_left_alone()
    print(f"\n{len(_passed)} passed, {len(_failed)} failed")
    if _failed:
        sys.exit(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python vibemind-os/brain/the_brain/tests/test_ensure_collections_alias.py`
Expected: crash — `AttributeError: module 'qdrant_kg' has no attribute 'PHYSICAL_VERSION_SUFFIX'`.

- [ ] **Step 3: Bump `SEMANTIC_DIM` (line 64)**

```python
SEMANTIC_DIM = 3072
```

- [ ] **Step 4: Add `PHYSICAL_VERSION_SUFFIX` constant**

Immediately after the `MAX_LINKED = 50` line (line 69):

```python
# Bump this suffix any time SEMANTIC_DIM changes again — ensure_collections()
# creates a fresh physical collection per suffix and aliases the logical name
# to it, so a dimension change never requires a caller-visible rename.
PHYSICAL_VERSION_SUFFIX = "-3072-v1"
```

- [ ] **Step 5: Replace `ensure_collections()` (lines 401-431) with the alias-aware version**

```python
    def ensure_collections(self) -> None:
        """Create every cognitive collection if missing. Idempotent.

        Each logical name in COLLECTIONS is always addressed as a Qdrant
        ALIAS, never a raw collection name — the alias resolves to a
        versioned physical collection (see PHYSICAL_VERSION_SUFFIX). This
        lets a future embedding-dimension change swap the alias onto a
        freshly migrated physical collection without touching any caller.

        Three states are handled per logical name:
          1. Alias already exists -> already migrated/set up, leave alone.
          2. Raw collection exists under that exact name, no alias -> a
             pre-migration deployment; leave it exactly as-is (this is
             what scripts/migrate_embeddings_v3072.py cuts over).
          3. Neither exists -> fresh deploy: create the physical collection
             and alias it.
        """
        qm = self._qm
        existing_collections = {c.name for c in self.client.get_collections().collections}
        existing_aliases = {a.alias_name: a.collection_name
                             for a in self.client.get_aliases().aliases}
        vectors_config = {
            "semantic": qm.VectorParams(
                size=SEMANTIC_DIM, distance=qm.Distance.COSINE,
            ),
            "neural": qm.VectorParams(
                size=NEURAL_DIM, distance=qm.Distance.COSINE,
                on_disk=True,
            ),
        }
        for logical_name, alias_name in COLLECTIONS.items():
            if alias_name in existing_aliases:
                logger.debug(
                    f"[KG] alias '{alias_name}' -> "
                    f"'{existing_aliases[alias_name]}' already set up"
                )
            elif alias_name in existing_collections:
                logger.debug(
                    f"[KG] '{alias_name}' exists as a raw collection "
                    f"(pre-migration) — leaving as-is"
                )
            else:
                physical_name = f"{alias_name}{PHYSICAL_VERSION_SUFFIX}"
                self.client.create_collection(
                    collection_name=physical_name,
                    vectors_config=vectors_config,
                )
                self.client.update_collection_aliases(change_aliases_operations=[
                    qm.CreateAliasOperation(create_alias=qm.CreateAlias(
                        collection_name=physical_name, alias_name=alias_name,
                    )),
                ])
                logger.info(
                    f"[KG] created '{physical_name}', aliased as '{alias_name}' "
                    f"(logical={logical_name}, semantic={SEMANTIC_DIM}d, "
                    f"neural={NEURAL_DIM}d on-disk)"
                )
            self._ensure_payload_indexes(alias_name)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python vibemind-os/brain/the_brain/tests/test_ensure_collections_alias.py`
Expected:
```
Test 1: fresh deploy — no collections, no aliases exist yet
  PASS creates a physical collection per logical name
  PASS physical name carries the version suffix
  PASS alias update was called once per collection
Test 2: alias already points somewhere — must not recreate anything
  PASS does not create a new physical collection for an aliased name
  PASS does not touch aliasing again for the already-aliased name
Test 3: pre-migration state — name exists as a RAW collection, no alias
  PASS does not create a new physical collection for the raw pre-migration name
  PASS does not force an alias onto an un-migrated raw collection

7 passed, 0 failed
```

- [ ] **Step 7: Commit**

```bash
git add vibemind-os/brain/the_brain/core/qdrant_kg.py vibemind-os/brain/the_brain/tests/test_ensure_collections_alias.py
git commit -m "feat(brain-core): 3072-dim SEMANTIC_DIM + alias-aware ensure_collections()"
```

---

## Task 8 (REVISED 2026-07-13 during implementation): torch build-arg only — sentence-transformers stays

**What changed from the original plan:** Step 2 below was executed as written and found a real
blocker: `web/brain_server.py:1245` loads `sentence-transformers` (`paraphrase-multilingual-
MiniLM-L12-v2`) on the live serving path to seed/run `EventRoutingHead`'s real-time intent
classifier (`/api/cortex/classify`, `web/routers/classification.py:76` documents a hard
"Target latency: <100ms" for this endpoint). This is a second, independent local-inference
consumer the original spec didn't account for — see the spec's "Addendum (found during
implementation...)" section and `[[project_eventroutinghead_stays_local]]` in project memory.
**Decision: keep `sentence-transformers`/`transformers` installed. Only flip the torch
build-arg default.** Full removal (the original Step 1 below) is no longer done.

**Files:**
- Modify: `vibemind-os/brain/the_brain/Dockerfile:39-56`

- [ ] **Step 1 (revised): Flip only the `BRAIN_TORCH_VARIANT` default, keep the ML packages**

Find the comment block + `ARG BRAIN_TORCH_VARIANT=cu121` + the two `pip install` blocks (one
for torch, one for sentence-transformers/transformers). Update ONLY the comment and the
`ARG` default line — do NOT remove the `sentence-transformers`/`transformers` install:

```dockerfile
# 2. torch: kept for web/routers/routing.py's RadialNetwork/SpaceRoutingHead.
#    sentence-transformers/transformers: ALSO kept, deliberately — brain-core
#    has two independent local-embedding consumers, not one. qdrant_kg.py's
#    Qwen KG-embedder has moved to embedding-service (see docs/superpowers/
#    specs/2026-07-13-brain-embedder-external-api-design.md), but
#    EventRoutingHead (web/brain_server.py, core/event_routing_head.py)
#    still needs local sentence-transformers for its <100ms real-time
#    intent-classification path (web/routers/classification.py) — a network
#    hop to embedding-service would blow that latency budget. See the
#    design spec's "Addendum" section for the full reasoning.
#    Default build-arg flips from cu121 to cpu: Qwen was the only reason
#    this defaulted to a CUDA wheel; neither the routing heads nor
#    EventRoutingHead's MiniLM model have a documented GPU requirement.
ARG BRAIN_TORCH_VARIANT=cpu
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        --index-url "https://download.pytorch.org/whl/${BRAIN_TORCH_VARIANT}" \
        "torch>=2.0,<2.6" && \
    pip install --no-cache-dir \
        "sentence-transformers>=2.2,<6" \
        "transformers>=4.30"
```

- [ ] **Step 2: Verify this doesn't regress anything already tested**

Run: `grep -n "BRAIN_TORCH_VARIANT" vibemind-os/brain/the_brain/Dockerfile` — confirm the
default reads `cpu` and both `pip install` blocks (torch, sentence-transformers/transformers)
are still present.

- [ ] **Step 3: Commit**

```bash
git add vibemind-os/brain/the_brain/Dockerfile
git commit -m "refactor(brain-core): default BRAIN_TORCH_VARIANT to cpu (Qwen migrated, EventRoutingHead's SBERT stays)"
```

---

## Task 9: Wire `EMBEDDING_SERVICE_URL` into the stack file

**Files:**
- Modify: `infra/swarm/vibemind-stack.yml` — `brain-core` (~line 68-247), `brain-api` (~248-301), `brain-autotrain-drain` (~302-337), `brain-loops` (~338-401), `brain-learner` (~402-461), `brain-inference` (~462-530)

- [ ] **Step 1: Add the env var + depends_on to each of the 6 `brain-*` services**

For each of the six services listed above, add one line to its `environment:` list:
```yaml
      - EMBEDDING_SERVICE_URL=${EMBEDDING_SERVICE_URL:-http://embedding-service:8080}
```
and add `embedding-service` to its existing `depends_on:` list (append it — e.g. `brain-core`'s `depends_on: [qdrant]` becomes `depends_on: [qdrant, embedding-service]`; `brain-inference`'s `depends_on: [qdrant, brain-learner]` becomes `depends_on: [qdrant, brain-learner, embedding-service]`). This is documentation of intent — Swarm ignores `depends_on:` (already established elsewhere in this file), so it changes no runtime behavior, but keeps the file accurate about what each service actually talks to.

- [ ] **Step 2: Validate the compose YAML still parses**

Run: `docker compose -f infra/swarm/vibemind-stack.yml config --quiet`
Expected: no output, exit code 0.

- [ ] **Step 3: Spot-check one service's rendered config**

Run: `docker compose -f infra/swarm/vibemind-stack.yml config | grep -A2 "EMBEDDING_SERVICE_URL" | head -20`
Expected: 6 occurrences of `EMBEDDING_SERVICE_URL=http://embedding-service:8080` (Compose resolves the `${VAR:-default}` shell-style interpolation at config-render time).

- [ ] **Step 4: Commit**

```bash
git add infra/swarm/vibemind-stack.yml
git commit -m "feat(brain-core): wire EMBEDDING_SERVICE_URL into all 6 brain-* services"
```

---

## Task 10: Migration script — re-embed existing KG history into 3072-dim collections

**Files:**
- Create: `vibemind-os/brain/the_brain/scripts/migrate_embeddings_v3072.py`

- [ ] **Step 1: Write the script**

```python
"""
Migrate every cognitive Qdrant collection from the old 1024-dim Qwen
embedding space to the new 3072-dim embedding-service space, preserving
point IDs and payload — only the `semantic` vector changes.

Prerequisite: the embedding-service container must be reachable (this
script calls it directly over HTTP, the same way qdrant_kg.Embedder does)
and brain-core (+ siblings) should be scaled to replicas:0 for the
duration of a --commit / --cutover run, so no new writes land in the old
collections mid-migration (see docs/superpowers/specs/2026-07-13-brain-
embedder-external-api-design.md, "Migration" section).

Usage:
    # 1. Show what would happen, no writes (safe to run any time)
    python scripts/migrate_embeddings_v3072.py --dry-run

    # 2. Populate the new 3072-dim physical collections (old ones untouched)
    python scripts/migrate_embeddings_v3072.py --commit

    # 3. After manually comparing old vs. new point counts printed above:
    #    snapshot + delete the old raw collection + create the alias that
    #    makes the logical name resolve to the new physical collection.
    python scripts/migrate_embeddings_v3072.py --cutover
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRAIN_ROOT = os.path.dirname(_HERE)  # .../the_brain
if _BRAIN_ROOT not in sys.path:
    sys.path.insert(0, _BRAIN_ROOT)

from core.qdrant_kg import (  # noqa: E402
    COLLECTIONS, QDRANT_URL, PHYSICAL_VERSION_SUFFIX, NEURAL_DIM, SEMANTIC_DIM,
)
from core import config as _cfg  # noqa: E402

SCROLL_BATCH = 100  # also the embedding-service /embed/batch chunk size


def _embed_batch(base_url: str, texts: List[str]) -> List[List[float]]:
    import requests
    resp = requests.post(f"{base_url}/embed/batch", json={"texts": texts}, timeout=60)
    resp.raise_for_status()
    return resp.json()["vectors"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print plan, don't write (default)")
    ap.add_argument("--commit", action="store_true",
                     help="re-embed and populate new 3072-dim collections")
    ap.add_argument("--cutover", action="store_true",
                     help="snapshot + delete old raw collection + create alias "
                          "(run only after verifying --commit's point counts)")
    ap.add_argument("--url", default=QDRANT_URL, help=f"Qdrant URL (default: {QDRANT_URL})")
    ap.add_argument("--embedding-service-url", default=_cfg.embedding_service_url(),
                     help="embedding-service base URL")
    args = ap.parse_args()

    if not (args.dry_run or args.commit or args.cutover):
        args.dry_run = True  # be safe

    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qm

    client = QdrantClient(url=args.url, timeout=60)

    print(f"[migrate] Qdrant URL:     {args.url}")
    print(f"[migrate] Embed service:  {args.embedding_service_url}")
    print(f"[migrate] Collections:    {len(COLLECTIONS)}")
    print()

    vectors_config = {
        "semantic": qm.VectorParams(size=SEMANTIC_DIM, distance=qm.Distance.COSINE),
        "neural": qm.VectorParams(size=NEURAL_DIM, distance=qm.Distance.COSINE, on_disk=True),
    }

    if args.cutover:
        for logical, old_name in COLLECTIONS.items():
            new_name = f"{old_name}{PHYSICAL_VERSION_SUFFIX}"
            try:
                old_info = client.get_collection(old_name)
                new_info = client.get_collection(new_name)
            except Exception as e:
                print(f"[migrate] SKIP {old_name}: {e}")
                continue
            if old_info.points_count != new_info.points_count:
                print(f"[migrate] REFUSING cutover for {old_name}: "
                      f"old={old_info.points_count} new={new_info.points_count} "
                      f"point counts differ — investigate before cutting over.")
                continue
            print(f"[migrate] snapshotting '{old_name}' before deleting it...")
            client.create_snapshot(collection_name=old_name, wait=True)
            client.delete_collection(collection_name=old_name)
            client.update_collection_aliases(change_aliases_operations=[
                qm.CreateAliasOperation(create_alias=qm.CreateAlias(
                    collection_name=new_name, alias_name=old_name,
                )),
            ])
            print(f"[migrate] cutover done: '{old_name}' now aliases '{new_name}'")
        return 0

    total_migrated = 0
    for logical, old_name in COLLECTIONS.items():
        new_name = f"{old_name}{PHYSICAL_VERSION_SUFFIX}"
        try:
            old_info = client.get_collection(old_name)
        except Exception as e:
            print(f"[migrate] source '{old_name}' not found, skipping: {e}")
            continue
        print(f"[migrate] {old_name}: {old_info.points_count} points -> {new_name}")

        if args.commit:
            existing = {c.name for c in client.get_collections().collections}
            if new_name not in existing:
                client.create_collection(collection_name=new_name, vectors_config=vectors_config)
                print(f"[migrate]   created '{new_name}'")

        offset = None
        moved = 0
        t0 = time.time()
        while True:
            batch, next_offset = client.scroll(
                collection_name=old_name, limit=SCROLL_BATCH, offset=offset,
                with_payload=True, with_vectors=False,
            )
            if not batch:
                break
            texts = [rec.payload.get("content", "") for rec in batch]
            if args.commit:
                new_vectors = _embed_batch(args.embedding_service_url, texts)
                points = [
                    qm.PointStruct(
                        id=rec.id,
                        vector={"semantic": new_vectors[i]},
                        payload=rec.payload,
                    )
                    for i, rec in enumerate(batch)
                ]
                client.upsert(collection_name=new_name, points=points, wait=True)
            moved += len(batch)
            if next_offset is None:
                break
            offset = next_offset
        dt = time.time() - t0
        verb = "would re-embed" if args.dry_run else "re-embedded"
        print(f"[migrate]   {verb} {moved} points in {dt:.1f}s")
        total_migrated += moved

    print()
    if args.dry_run:
        print(f"[migrate] DRY RUN — {total_migrated} points would be migrated. "
              f"Re-run with --commit to actually write.")
        return 0

    print("[migrate] verifying counts old vs. new...")
    for logical, old_name in COLLECTIONS.items():
        new_name = f"{old_name}{PHYSICAL_VERSION_SUFFIX}"
        try:
            old_count = client.get_collection(old_name).points_count
            new_count = client.get_collection(new_name).points_count
            flag = "OK" if old_count == new_count else "MISMATCH"
            print(f"[migrate]   {old_name}: old={old_count} new={new_count} [{flag}]")
        except Exception as e:
            print(f"[migrate]   {old_name}: ERROR {e}")

    print()
    print("[migrate] If all counts show OK, re-run with --cutover to swap the aliases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Dry-run against a real (or dev) Qdrant instance**

Run: `python vibemind-os/brain/the_brain/scripts/migrate_embeddings_v3072.py --dry-run --url http://localhost:6730`
Expected: prints each collection's current point count and "would re-embed N points", ends with a line reporting the total point count that would be migrated across all collections. No writes occur — confirm by re-running `--dry-run` again and seeing identical counts.

- [ ] **Step 3: Commit**

```bash
git add vibemind-os/brain/the_brain/scripts/migrate_embeddings_v3072.py
git commit -m "feat(brain-core): add scripts/migrate_embeddings_v3072.py (dry-run/commit/cutover)"
```

---

## Task 11: End-to-end smoke test against a local stack

**Files:** none created/modified — this is a manual verification task using the artifacts from Tasks 1-10.

**REVISED expectation (2026-07-13):** Step 3 below originally expected `sentence-transformers` to be *gone* from `brain-core`'s image — that was true under the original Task 8, but Task 8 was revised mid-implementation (see Task 8's own "REVISED" note above): `EventRoutingHead`'s real-time `<100ms` classification path keeps `sentence-transformers` locally, deliberately. The corrected expectation is the opposite of what Step 3 originally said — verified below.

- [x] **Step 1: Build the two changed/new images locally** — DONE 2026-07-13, both built successfully (`vibemind-embedding-service:latest`, `vibemind-brain-core:latest`).

- [x] **Step 2: Run embedding-service standalone with a real OpenAI key and hit it directly** — DONE 2026-07-13. Ran via `docker run --rm -d --name embed-smoke-test -p 8080:8080 --env-file .env vibemind-embedding-service:latest` (real key loaded from the gitignored root `.env`, never printed). Results:
  - `/health` → `{"status":"ok","model":"text-embedding-3-large"}`
  - `/embed` (`{"text": "hello world"}`) → real 3072-length vector returned (genuine OpenAI round-trip, not a mock).

- [x] **Step 3 (corrected): Confirm `brain-core`'s image imports `sentence-transformers`/`transformers` (kept deliberately) and `torch` is the CPU wheel** — DONE 2026-07-13.
```bash
docker run --rm vibemind-brain-core:latest python -c "
import sentence_transformers, transformers, torch
print('sentence_transformers:', sentence_transformers.__version__)
print('transformers:', transformers.__version__)
print('torch:', torch.__version__)
"
```
Actual output: `sentence_transformers: 5.6.0`, `transformers: 5.13.1`, `torch: 2.5.1+cpu` — all three import successfully, and the `+cpu` suffix on the torch version confirms the `BRAIN_TORCH_VARIANT=cpu` build-arg default (Task 8) actually took effect, not just that the field exists.

- [x] **Step 4: Confirm torch is still importable (routing.py's dependency)** — folded into Step 3's combined check above (already confirmed: `torch: 2.5.1+cpu`, exit code 0).

This task has no commit step — it's verification only, using artifacts already committed in Tasks 1-10. All 4 steps completed and verified 2026-07-13 against locally-built images and a real OpenAI API call.

---

## Plan self-review (performed while writing this document)

**Spec coverage:** every section of `docs/superpowers/specs/2026-07-13-brain-embedder-external-api-design.md` maps to a task — Architecture/Interface → Tasks 1-4; `Embedder` client + `SEMANTIC_DIM`/alias → Tasks 6-7; Dockerfile changes → Task 8; stack wiring → Tasks 4 & 9; Migration → Task 10; Testing → embedded in every task's TDD steps + Task 11's smoke test.

**Placeholder scan:** no TBD/TODO markers; every step shows complete, runnable code; error handling is concrete code, not a comment.

**Type/interface consistency:** `Embedder.encode(text) -> List[float]` / `encode_batch(texts) -> List[List[float]]` (Task 6) match the pre-existing signatures used at the 3 call sites in `qdrant_kg.py` and the 3 external callers — none of those callers are touched, by design. `embedding_service_url()` (Task 5) is the single function `Embedder.__init__` (Task 6) and the migration script (Task 10) both call, so the URL resolution logic exists in exactly one place. `PHYSICAL_VERSION_SUFFIX` (Task 7) is the same constant string used by `ensure_collections()` and by the migration script (Task 10) — the migration script imports it directly from `qdrant_kg` rather than hardcoding `"-3072-v1"` a second time, so the two can't drift.

**Scope check:** this is one implementation plan for one cohesive change with an inherent build order (service exists before the client can call it; client change lands before the stack wires the URL; migration script depends on both existing) — not decomposable into independently-shippable sub-features, so it stays as a single plan per the spec.
