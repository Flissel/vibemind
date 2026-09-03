# TriBE (fMRI-Encoder / neuronale Signatur)

_Auto-generiert 2026-06-23 via fungus-Deep-Crawl (Subagent). Teil des [Startup-Profile-Doc-Sets](../STARTUP_PROFILES.md)._

## Overview

TriBE (a Foundation Model of Vision, Audition, and Language for In-Silico Neuroscience, Meta/Facebook research) is an fMRI brain encoder that predicts cortical activation patterns on the fsaverage5 mesh (~20,484 vertices) for any text input. In VibeMind, TriBE produces biologically-plausible neural signatures for every thought, enabling Brain's bridges (limbic, defense, cortex, motor, etc.) to modulate routing and activation based on predicted fMRI patterns rather than heuristics alone.

## Components

### Core Files
- **`C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py`** (596 lines) — Singleton lazy-loaded wrapper exposing `TribeEncoder.get().predict(text) -> np.ndarray` and bridge-aggregation methods. This is the PRIMARY integration point for Brain.
- **`C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/tribe/tribev2/`** — Vendored Meta TriBE v2 source (git submodule), including `demo_utils.py`, `model.py`, `eventstransforms.py`, studies, and plotting utilities. Only `tribev2.demo_utils.TribeModel` and `tribev2.eventstransforms.ExtractWordsFromAudio` are called from Brain.
- **`C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/modulation_context.py`** (285 lines) — Modulation system that wires TriBE's 8-bridge profiles into the RadialAttentionNetwork's 4 composite factors (attention_gain, precision_boost, ffn_throughput, threshold_mod) via learnable hooks (H30-H33, Phase 2).
- **`C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/qdrant_kg.py`** (lines 76-89, 270-273, 668-703, 859-895) — Knowledge graph integration that batches TriBE predictions in the async flush worker (no hot-path impact). Flags: `TRIBE_PROFILE_ENABLED`, `TRIBE_NEURAL_VECTOR_ENABLED`, `TRIBE_INTENT_GROUNDING`, `TRIBE_ROI_ENABLED`.

### Services & Data Structures
- **TribeEncoder** (tribe_encoder.py:203-559) — Thread-safe singleton with lazy-loading on first `predict()` call. Model weights (~1GB) downloaded from HuggingFace Hub on demand, cached to `~/.cache/tribev2`.
  - **Methods**: `predict(text) -> Optional[np.ndarray]` (shape ~20484), `predict_via_tts(text)` (legacy TTS+whisperx path), `aggregate_roi(vec)`, `bridge_levels(vec)`, `status()`
  - **Stats tracking**: `predictions`, `failures`, `last_error`, `last_predict_ms`, `model_loaded`
- **Embedder** (qdrant_kg.py:198-251) — Qwen3-Embedding-0.6B (1024-dim) for semantic indexing; separate from TriBE.
- **ThoughtDoc** (qdrant_kg.py:258-277) — Payload dataclass with `bridge_levels: Dict[str,float]` and `rois: Dict[str,float]` fields (both optional, populated only when flags enabled).

### Ports & Environment
- TriBE uses no dedicated port (in-process model).
- **HuggingFace Hub access**: Pre-downloads `facebook/tribev2` checkpoint on startup (can be overridden via `TRIBE_CHECKPOINT` env).
- **Qdrant** (port 16333 by default) — Stores semantic + neural vectors in `brain-episodic`, `brain-semantic` collections.

## Dependencies

### UPSTREAM (TriBE needs)
1. **PyTorch + torch.cuda** (tribe_encoder.py:258, 316-318) — Lazy-imported on first predict. Device auto-detected (CUDA if available, else CPU).
2. **HuggingFace Hub** (tribe_encoder.py:326-338) — Downloads `facebook/tribev2` config.yaml + best.ckpt on first load. Network required; can be cached locally.
3. **faster-whisper** (tribe_encoder.py:151-196) — Optional; used only if real audio/video is passed (not the default text-only path). Bypass via in-process transcript synthesis.
4. **neuralset, neuraltrain** (tribev2/pyproject.toml:15-16) — TriBE's ML framework (vendored).
5. **Qwen/Qwen3-Embedding-0.6B** (qdrant_kg.py:60) — Separate from TriBE; lazy-loaded by Embedder singleton for semantic indexing.

### DOWNSTREAM (TriBE callers)
1. **qdrant_kg.py** (lines 671-703) — Flushes TriBE predictions into Qdrant payloads in the async writer thread (controlled by `TRIBE_PROFILE_ENABLED`, `TRIBE_NEURAL_VECTOR_ENABLED`, `TRIBE_ROI_ENABLED`).
2. **thought_radial_bridge.py** (lines 64-72) — Calls `bridge_levels_for_text(content[:400])` to modulate RadialAttentionNetwork with TriBE's bridge profile (gated by `TRIBE_MODULATION_ENABLED`).
3. **plan_executor.py** (line 1476) — Calls `bridge_levels_for_text()` for multihop grounding (gated by `MULTIHOP_TRIBE_GROUNDING`).
4. **modulation_context.py** (lines 264-278) — Applies TriBE bridge activations as H30-H33 hooks into composite modulation factors.

## Possible usages

### Capabilities (text-triggerable via Brain's router, capabilities.yaml)
- **No dedicated TriBE capability exists**. TriBE runs as a background process, not as a routed agent. However:
  - **architecture_question** (capabilities.yaml:667-683) can discuss TriBE with fungus-search or brain-coder.
  - **code_search** can locate TriBE usage in the codebase.

### Voice-Triggers & APIs
- **No voice triggers**. TriBE is invoked internally by:
  - Every thought added to Qdrant (if `TRIBE_PROFILE_ENABLED=1`).
  - Every RadialAttentionNetwork forward pass (if `TRIBE_MODULATION_ENABLED=1`).
  - Multihop planner (if `MULTIHOP_TRIBE_GROUNDING=1`).

### Tools / Direct Invocation
- **Module-level API** (tribe_encoder.py:565-595):
  ```python
  from core.tribe_encoder import TribeEncoder, predict_text, bridge_levels_for_text, describe_profile
  
  enc = TribeEncoder.get()
  vec = enc.predict("some text")  # ~20484-dim or None on failure
  bridges = enc.bridge_levels(vec)  # {cortex, limbic, defense, motor, ...}
  profile = describe_profile(bridges)  # "high social + memory, low defense"
  status = enc.status()  # diagnostic snapshot
  ```

### Configuration flags (all default OFF)
- `TRIBE_ENABLED=1` — Enable model loading (default "1"; set "0" to skip and use dummy vectors).
- `TRIBE_DUMMY=1` — Force deterministic pseudo-vectors (for testing without gated weights).
- `TRIBE_CHECKPOINT="facebook/tribev2"` — HuggingFace checkpoint (default); can be a local path.
- `TRIBE_DEVICE="auto"|"cpu"|"cuda"` — Device selection (default "auto").
- `TRIBE_CACHE_FOLDER="~/.cache/tribev2"` — Model cache location.
- `TRIBE_WHISPER_MODEL="small"` — faster-whisper size (default "small"; only for real audio).
- **KG integration** (qdrant_kg.py):
  - `TRIBE_PROFILE_ENABLED=1` — Compute & store 8-bridge profile per thought.
  - `TRIBE_NEURAL_VECTOR_ENABLED=1` — Also write full 20484-dim vector to Qdrant.
  - `TRIBE_INTENT_GROUNDING=1` — Prefix intent to text before encoding.
  - `TRIBE_ROI_ENABLED=1` — Store 16 cortical ROIs (finer granularity than bridges).
  - `TRIBE_PROFILE_MAXLEN=400` — Truncate input text (default 400 chars).
- **Modulation** (modulation_context.py):
  - `TRIBE_MODULATION_ENABLED=1` — Wire TriBE bridges into RadialAttentionNetwork.
  - `TRIBE_MODULATION_GAIN=0.15` — Scalar gain for TriBE's contribution to modulation factors (default 0.15).
- **Plan executor**:
  - `MULTIHOP_TRIBE_GROUNDING=1` — Include TriBE bridge profile in multihop planning.

## Integration points

### Brain's bridges → ROI mapping
TriBE outputs ~20,484 vertex activations on fsaverage5 cortical mesh. `tribe_encoder.py` defines:
- **DEFAULT_ROI_RANGES** (lines 92-111) — Coarse 16 ROIs (left/right): prefrontal, motor, somatosensory, temporal, parietal, occipital, insula, cingulate.
- **BRIDGE_ROI_MAP** (lines 116-131) — 8 Brain-bridges aggregated from ROIs with weighted means:
  - `cortex`: prefrontal (L/R) + parietal (L/R, 0.5x)
  - `limbic`: insula (L/R) + cingulate (L/R, 0.8x)
  - `defense`: insula + cingulate (1.0x)
  - `motor`, `visceral`, `social`, `integration`, `memory` — each mapped to specific ROI(s).
- **aggregate_roi()** (lines 513-529) — Slices the dense vector by ROI ranges, computes mean activations.
- **bridge_levels()** (lines 531-545) — Reduces ROI activations to per-bridge scalars via weighted averaging.

### Embedding + routing (qdrant_kg.py)
- Each `ThoughtDoc` carries:
  - `semantic`: 1024-dim Qwen3 embedding (always computed).
  - `bridge_levels`: {cortex, limbic, ...} dict (only if `TRIBE_PROFILE_ENABLED=1`).
  - `rois`: {prefrontal_L, motor_R, ...} dict (only if `TRIBE_ROI_ENABLED=1`).
  - `neural`: 20484-dim TriBE vector (reserved slot in Qdrant schema; only written if `TRIBE_NEURAL_VECTOR_ENABLED=1`).
- Enables **cross-retrieval** — e.g., "find thoughts that would resonate in similar motor cortex regions".

### Modulation → RadialAttentionNetwork (modulation_context.py)
1. `thought_radial_bridge.py` calls `bridge_levels_for_text(content)` on each thought.
2. ModulationContext receives `tribe_bridges` dict as a field.
3. In `compute()` (lines 260-278), applies 4 new hooks (H30-H33):
   - **H30**: `cortex + integration` → `attention_gain` (top-down focus).
   - **H31**: `limbic + defense` → `threshold_mod` (caution).
   - **H32**: `memory + social` → `precision_boost` (relevance weighting).
   - **H33**: `motor + visceral` → `ffn_throughput` (throughput).
4. Each contribution is `1 + gain * (bridge_value + personal_bias)`, clamped to [0.3, 3.0].

### Live per-thought modulation (Phase 2)
When `TRIBE_MODULATION_ENABLED=1`:
- Every thought's TriBE profile nudges the 4 composite factors *during the radial forward pass*.
- No storage — purely live computation.
- Personal bias (Phase 3/Flowzen) can add per-user offsets to TriBE values.

### OpenFang / Bubbles / Rowboat
- No direct integration yet. Bubbles (ideas) don't yet receive TriBE neural signatures; only thoughts (episodic memories) do.
- Future: could profile bubble titles/summaries to guide cross-space ideation.

### Coding Engine / Multimodal paths
- TriBE **supports video, audio, text** inputs but Brain currently only uses **text** (direct events, no TTS).
- Full multimodal path (gTTS → whisperx → TriBE) exists in `predict_via_tts()` and TriBE's demo utilities but is Windows-fragile and not enabled by default.
- `tribe_encoder.py:265-312` patches TriBE's transcript extraction to use faster-whisper in-process (avoiding subprocess DLL hell on Windows).

## Isolated startup

### What must be running to test TriBE alone

**Minimal standalone test** (no Brain service needed):
```python
# No external services required; runs in-process
from brain.the_brain.core.tribe_encoder import TribeEncoder

enc = TribeEncoder.get()  # Lazy-loads model on first call (~1GB download + load, ~30-60s)
vec = enc.predict("The sky is blue")
print(vec.shape)  # (20484,)
bridges = enc.bridge_levels(vec)
print(bridges)  # {cortex: 0.12, limbic: -0.05, ...}
```

**Requirements**:
- Python 3.11+
- PyTorch (auto-downloads if missing)
- HuggingFace Hub access (or pre-cached model)
- GPU optional (CPU works, ~50-200ms per prediction on CPU; ~5-20ms on CUDA).

### Docker / Brain service startup
**To test TriBE inside Brain**:
```bash
cd vibemind-os/brain/the_brain
docker compose up unified-brain -d
# Wait for port 5003 health check to pass (~1min for model load + startup)

# Then test via Brain's internal API (no public endpoint yet)
curl -X POST http://localhost:5003/health
```

**Environment for TriBE integration**:
```bash
export TRIBE_ENABLED=1
export TRIBE_PROFILE_ENABLED=1
export TRIBE_MODULATION_ENABLED=1
export QDRANT_URL=http://127.0.0.1:16333
# Qdrant must be running separately (not in docker-compose.yml)
docker run -d -p 16333:6333 qdrant/qdrant
```

### Gaps in isolated testing
1. **No dedicated TriBE endpoint** in Brain's REST API. You must:
   - Call Python directly (import tribe_encoder, call predict()).
   - OR patch Brain's `/health` or `/status` endpoint to expose `TribeEncoder.status()`.
2. **Qdrant integration** requires running Qdrant separately; it's not in the docker-compose.
3. **Modulation** integration only works if RadialAttentionNetwork is also running (requires full Brain cognitive loop).
4. **No CLI tool** for TriBE predictions; must use Python REPL.

## Key files — load-bearing references

1. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py:203-217** — TribeEncoder singleton pattern.
2. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py:236-363** — Lazy-loading logic; Windows workarounds for PosixPath YAML and whisperx subprocess.
3. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py:92-131** — ROI + bridge mapping (constant data).
4. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py:422-458** — Core `predict(text)` method (direct events, no TTS).
5. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/tribe_encoder.py:531-545** — `bridge_levels(vec)` aggregation logic.
6. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/qdrant_kg.py:76-89** — Integration flags (TRIBE_PROFILE_ENABLED, etc.).
7. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/qdrant_kg.py:668-703** — Async KG flush where TriBE predictions are written.
8. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/modulation_context.py:260-278** — H30-H33 hooks (TriBE → modulation factors).
9. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/core/thought_radial_bridge.py:64-72** — Call site for TriBE in radial bridging.
10. **C:/Users/User/Desktop/Vibemind_V1/vibemind-os/brain/the_brain/tribe/tribev2/demo_utils.py** — TribeModel.from_pretrained(), .predict() (vendored Meta code).

## Gotchas

### 1. Model load is blocking & slow
- First call to `TribeEncoder.predict()` downloads ~1GB from HuggingFace and loads into GPU/CPU (30-60s typical).
- Brain startup is **not blocked** (lazy-loading), but **first thought** in the system will have latency.
- Pre-download via `TRIBE_CHECKPOINT` pointing to a local path if you want zero first-call latency.

### 2. Windows path mangling (tribe_encoder.py:264-268)
- TriBE's YAML loader crashes on Windows because it contains `!!python/object/apply:pathlib.PosixPath`.
- Workaround: tribe_encoder patches `pathlib.PosixPath = pathlib.WindowsPath` at import time. Works but is fragile.
- **Risk**: If PosixPath usage evolves in TriBE upstream, this patch may break.

### 3. Whisperx subprocess fragile on Windows (tribe_encoder.py:270-312)
- TriBE's default `uvx whisperx` external process requires torchcodec + FFmpeg DLLs linked correctly in a subprocess venv.
- Brain works around this by patching `ExtractWordsFromAudio._get_transcript_from_audio` to use faster-whisper in-process.
- **Risk**: Only works if you provide **source text** (TTS case) or pass real audio/video. Hybrid cases may fail silently.

### 4. All flags default OFF
- `TRIBE_PROFILE_ENABLED`, `TRIBE_NEURAL_VECTOR_ENABLED`, `TRIBE_MODULATION_ENABLED` all default to `"0"`.
- You **must** explicitly enable them or TriBE runs but produces no effect.
- In production, TriBE model loads even if all flags are off (waste of resources); consider `TRIBE_ENABLED=0` if you don't need it.

### 5. Bridge mapping is approximate
- ROI ranges (DEFAULT_ROI_RANGES) use coarse hemisphere splits + rough cortical slices; **not** a real atlas (Schaefer, Destrieux).
- BRIDGE_ROI_MAP is hand-tuned heuristics, not neuroscience literature (e.g., why does "cortex" = prefrontal + parietal?).
- **Future work**: Swap in proper atlas via roi_bridge_mapper.py (noted in tribe_encoder.py:87-90 but not yet done).

### 6. Dummy mode deterministic but not realistic
- If model fails to load or `TRIBE_DUMMY=1`, `predict()` returns hashed pseudo-vectors (seed = SHA256(text)[:8]).
- These are **not biologically meaningful** — just stable enough that downstream code paths execute.
- Good for testing; bad for production grounding.

### 7. Thread safety depends on lock discipline
- TribeEncoder holds a `_model_lock` (mutex) around predict() calls.
- Multiple Brain threads calling predict() will queue (sequential execution), not parallel.
- **Performance**: On high thought-volume, TriBE becomes a bottleneck (single model, shared GPU).
- **No pooling**: Only one TribeEncoder instance ever exists (singleton).

### 8. Incomplete integrations
- **Audio/video** paths exist in TriBE but untested in Brain (only text used).
- **Qdrant neural vector storage** — flag exists, but slot is rarely filled in practice (TRIBE_NEURAL_VECTOR_ENABLED rarely on).
- **Flowzen personal bias** (TRIBE_PERSONAL_BIAS in modulation_context.py:90) — structure exists, no UI or learning loop yet.
- **ROI-level granularity** — TRIBE_ROI_ENABLED flag exists but only 8 bridges are used in practice; 16 ROIs not exposed to user-facing tools.

### 9. No retraining / fine-tuning
- TriBE model is **inference-only** in Brain (weights frozen).
- Training infrastructure (tribev2/main.py, grids/, studies/) exists but is **not integrated** into the live Brain.
- Future work: Adapt TriBE to finetuned Brain-specific fMRI (not yet available).

### 10. Memory overhead
- Model weights: ~1GB on disk, ~3-4GB in VRAM (or ~6GB on CPU).
- Per-thought storage: bridge_levels dict (~100 bytes), full neural vector (20484 * 4 bytes = ~80KB if TRIBE_NEURAL_VECTOR_ENABLED).
- On high-volume thought generation, Qdrant storage grows quickly if neural vectors are enabled.
