# =============================================================================
# Vibemind base Python service Dockerfile  —  TEMPLATE, do not build directly
# =============================================================================
# Copy this into a service dir, replace <PLACEHOLDERS>, delete unused branches.
# Distilled from the production exemplars (see infra/standards/STANDARDS.md):
#   - monorepo-shared install pattern  : vibemind-os/brain/the_brain/Dockerfile
#   - build/runtime split + non-root   : Automation_ui/backend/Dockerfile
#
# Conventions enforced here (STANDARDS.md §1,§6,§7,§8):
#   - pinned python:3.11-slim base (not :latest)
#   - PYTHONUNBUFFERED so logs stream in real time
#   - build deps separated from runtime image (smaller, faster cold start)
#   - runs as non-root `appuser`
#   - explicit CMD policy: ship a correct JSON-array CMD, OR omit it and
#     document that the swarm block MUST supply `command:`
# =============================================================================

# ---- Stage 1: build deps + python packages --------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build-only system deps (compilers, headers). NOT in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# --- (optional) monorepo shared package -----------------------------------
# If this service imports `vibemind-shared`, the build context MUST be
# vibemind-os/ (set `context: ../..` in the compose/stack build block) and
# this block installs it from local source (it is NOT on PyPI).
#   COPY shared/ /opt/vibemind-shared/
#   RUN pip install --no-cache-dir /opt/vibemind-shared/

# --- (optional) special wheel index (e.g. CPU-only torch) -----------------
#   RUN pip install --no-cache-dir \
#       --index-url https://download.pytorch.org/whl/cpu torch

# Requirements first for layer caching (changes less often than source).
COPY <SERVICE_PATH>/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: lean runtime image ------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime-only system deps. `curl` is here ONLY if the healthcheck uses curl;
# alpine/slim images often lack it — wget(busybox) is the lighter alternative.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

# Carry installed packages from the builder (no build toolchain in final image)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Application source
COPY <SERVICE_PATH>/ /app/

# Persistent data mount point (named volume attaches here in the stack)
RUN mkdir -p /app/data

# Non-root user (STANDARDS.md §6)
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE <PORT>

# In-image healthcheck is OPTIONAL — the swarm block also defines one and
# that is the source of truth for orchestration. Keep this for plain
# `docker run` parity. Use 127.0.0.1 (NOT localhost) — busybox/alpine
# resolves localhost→IPv6 while the app listens IPv4 (STANDARDS.md §2).
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:<PORT>/health || exit 1

# CMD policy (STANDARDS.md §8): JSON-array form, never a single string that
# collapses to one argv token. If you OMIT CMD, the swarm block MUST supply
# `command:` — say so explicitly here so the omission is intentional, not a bug.
CMD ["uvicorn", "<MODULE>:app", "--host", "0.0.0.0", "--port", "<PORT>", "--workers", "1"]
