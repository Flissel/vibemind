# =============================================================================
# Vibemind base Node service Dockerfile  —  TEMPLATE, do not build directly
# =============================================================================
# Copy into a service dir, replace <PLACEHOLDERS>, delete unused branches.
# Distilled from the production exemplar (see infra/standards/STANDARDS.md):
#   - 3-stage deps→builder→runner : vibemind-os/spaces/rowboat/rowboat/apps/rowboat/Dockerfile
#
# Conventions enforced here (STANDARDS.md §1,§6,§8):
#   - pinned node:18-alpine + libc6-compat for native modules
#   - frozen-lockfile install (no package.json drift between build and run)
#   - non-root `appnode` user in the runtime stage
#   - JSON-array CMD (the single-string `CMD npm run dev` collapse is exactly
#     what silently killed rowboat-jobs-worker / mirofish — STANDARDS.md §8)
# =============================================================================

# ---- Stage 1: base ---------------------------------------------------------
FROM node:18-alpine AS base
# libc6-compat: many native node modules need glibc symbols absent in musl
RUN apk add --no-cache libc6-compat
WORKDIR /app

# ---- Stage 2: deps (lockfile-driven, cached independently of source) -------
FROM base AS deps
COPY <SERVICE_PATH>/package.json \
     <SERVICE_PATH>/package-lock.json* \
     <SERVICE_PATH>/yarn.lock* \
     <SERVICE_PATH>/pnpm-lock.yaml* ./
RUN if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
    elif [ -f package-lock.json ]; then npm ci; \
    elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm i --frozen-lockfile; \
    else echo "No lockfile found — refusing unpinned install." && exit 1; fi

# ---- Stage 3: builder ------------------------------------------------------
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY <SERVICE_PATH>/ .
# Build step (skip this stage entirely for a no-build service)
RUN if [ -f yarn.lock ]; then yarn run build; \
    elif [ -f package-lock.json ]; then npm run build; \
    elif [ -f pnpm-lock.yaml ]; then pnpm run build; fi

# ---- Stage 4: runner (lean production image) ------------------------------
FROM base AS runner
ENV NODE_ENV=production
WORKDIR /app

# Non-root user (STANDARDS.md §6)
RUN addgroup --system --gid 1001 appnode \
    && adduser --system --uid 1001 appnode

# Copy ONLY what runtime needs. For Next.js standalone output:
#   COPY --from=builder /app/public ./public
#   COPY --from=builder --chown=appnode:appnode /app/.next/standalone ./
#   COPY --from=builder --chown=appnode:appnode /app/.next/static ./.next/static
# Generic node app:
COPY --from=builder --chown=appnode:appnode /app/node_modules ./node_modules
COPY --from=builder --chown=appnode:appnode /app .

USER appnode

# Pin the listen port explicitly so it cannot leak from an env_file
# (a leaked PORT once made rowboat bind :8007 instead of :3000 — STANDARDS.md §5)
ENV PORT=<PORT> HOSTNAME="0.0.0.0"
EXPOSE <PORT>

# Optional in-image healthcheck (swarm block is the orchestration source of
# truth). 127.0.0.1 not localhost (busybox→IPv6 trap — STANDARDS.md §2).
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:<PORT>/health || exit 1

# CMD policy (STANDARDS.md §8): JSON-array, multi-token. NEVER a single
# string like CMD "npm run dev" — Docker treats it as one binary name and
# the container exits 1 with no logs. If you must `npm run X`, write it as:
#   CMD ["npm", "run", "<SCRIPT>"]
CMD ["node", "server.js"]
