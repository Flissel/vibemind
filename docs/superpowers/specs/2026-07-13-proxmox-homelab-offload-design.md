# Proxmox Homelab Offload — Design Spec

## Purpose

The local Windows dev machine runs a 40-service Docker Swarm stack (`infra/swarm/vibemind-stack.yml`) whose combined memory limits exceed 50GB, contributing to a bloated WSL2/Docker Desktop footprint (~12GB `docker_data.vhdx` observed). A second machine — a Geekom AS 6 mini PC (AMD Ryzen 9 6900HX, 16 threads, 30GiB RAM, no dedicated GPU) — is now running Proxmox VE 9.2.4, freshly installed with no VMs/containers. This spec moves a deliberately-chosen subset of the stack there to reduce local load, in two phases, without touching anything that needs the local NVIDIA GPU or is too latency/dev-iteration sensitive to move.

Verified via direct root SSH (`~/.ssh/proxmox_key`, host `root@192.168.178.64`):
- Storage: `local-lvm` (LVM-thin, ~348GB free) for VM disks; `local` (~94GB) for ISOs/backups
- Network: `vmbr0`, static `192.168.178.64/24`, gateway `192.168.178.1`
- No existing VMs or containers

## What stays local (and why)

- **Brain cluster** (`brain-core`, `brain-api`, `brain-loops`, `brain-learner`, `brain-inference` — ~18.5GB) — actively iterated core cognitive engine; `brain-inference` needs the local NVIDIA GPU (Qwen embedder, CUDA) which the Proxmox box does not have (integrated Radeon 680M only, no dedicated VRAM).
- **Qdrant** — queried by Brain in a tight routing loop; stays local. Already exposes host port `6730:6333`, so Phase 2's remote Rowboat cluster can still reach it over LAN (`http://<windows-host-lan-ip>:6730`) without duplicating the vector DB.
- **Coding-engine compute core** (`coding-api`, `coding-worker`, `coding-openclaude` — ~10GB) — actively-iterated pipeline; moving it would complicate day-to-day debugging.

## Phase 1 — Observability + Gitea

**Services:** `loki`, `grafana-vibemind`, `coding-gitea`, `gitea-postgres` (~4GB total). `promtail` stays local (it reads `/var/run/docker.sock` and `/var/lib/docker/containers` — it can only scrape logs from containers running on the same host) but gets reconfigured to ship to the new remote Loki instead of the local one.

**Infrastructure:**
1. One Debian 12 VM on Proxmox (not LXC — plain Docker-in-VM avoids LXC/Docker nesting friction for long-lived stateful services), provisioned via `qm create` + cloud-init (SSH key injection, Docker Engine + Compose plugin install via cloud-init script or `curl -fsSL https://get.docker.com | sh` on first boot).
2. Static IP on `vmbr0` (e.g. `192.168.178.65`, DHCP reservation or cloud-init static config — exact free IP to confirm against the router at implementation time).
3. Standalone `docker-compose.yml` (not a Swarm join) on the VM, containing the 4 Phase 1 services, extracted from `infra/swarm/vibemind-stack.yml` with the same pinned image digests.

**Config changes required:**
- `coding-gitea`: `GITEA__server__ROOT_URL` changes from `http://localhost:3002/` to `http://192.168.178.65:3002/` (or whatever the VM's final IP is).
- `promtail` (still local): its Loki client URL changes from the local Loki address to `http://192.168.178.65:<loki-port>/loki/api/v1/push`.
- Any other local consumer of Loki/Grafana by `localhost` address (e.g. the dormant `error-monitor` OpenFang agent's Loki query URL) needs the same host update if/when it's ever wired up.

**No data migration needed** — current local Gitea is empty/unused, so this deploys fresh rather than migrating existing repos.

## Phase 2 — Rowboat + Neo4j + n8n + Supabase

**Services (added to the same VM's compose file, ~17.5GB):**
- Rowboat cluster: `rowboat-mongo`, `rowboat-redis`, `rowboat`, `rowboat-agents`, `rowboat-jobs-worker`, `rowboat-rag-worker` (~7.5GB) — self-contained (own Mongo + Redis), only external dependency is Qdrant (stays local, reachable over LAN at port 6730).
- `neo4j-mirofish` (~4GB, has its own fixed heap/pagecache settings already in the compose config) — background/batch graph workload.
- `n8n` (~2GB) — workflow automation, background/triggered, not interactive-latency-critical.
- Full Supabase stack: `supabase-db`, `supabase-auth`, `supabase-rest`, `supabase-realtime`, `supabase-storage`, `supabase-pg-meta`, `supabase-analytics`, `supabase-kong`, `supabase-studio`, `supabase-inbucket` (~4-5GB) — internally self-contained (all depend only on `supabase-db` or each other), moves as one unit. Moving it alongside Rowboat means their sync traffic (Bubble↔Rowboat bidi-sync tables) becomes local to the Proxmox box instead of round-tripping to Windows.

**Config changes required:**
- `rowboat`/`rowboat-agents`/`rowboat-jobs-worker`/`rowboat-rag-worker`: `QDRANT_URL` changes from `http://qdrant:6333` (Docker-internal service name, only resolves inside the same Docker network) to `http://<windows-host-lan-ip>:6730`.
- Whatever secrets/env vars are currently interpolated from the Windows host's `.env` (`POSTGRES_PASSWORD`, `JWT_SECRET`, `N8N_ENCRYPTION_KEY`, `AGENTS_API_KEY`, etc.) need to be present in an `.env` file on the Proxmox VM too — copied once at deploy time, not committed to git.
- Any local consumer that currently reaches Supabase/Rowboat/n8n via `localhost:<port>` needs to switch to the VM's LAN address.

## VM sizing

Single VM hosts both phases (simpler to patch/back up/snapshot than juggling multiple VMs for what's fundamentally one growing compose file). Starting allocation: **12 vCPU / 24GB RAM**, leaving 4 threads and ~6GB for the Proxmox host itself and future headroom — comfortably covers Phase 1 (~4GB) + Phase 2 (~17.5GB) ≈ 21.5GB with buffer. Can be resized later (`qm set --memory`/`--cores`, requires a VM reboot to take effect) without needing to get this exactly right up front.

## Operations: rollback and update strategy (applies to both phases)

| Concern | Mechanism |
|---|---|
| VM-level rollback | `qm snapshot <vmid> <name>` before any risky change (Docker version bump, compose file change, new service); `qm rollback` to revert. LVM-thin snapshots are fast/cheap on this storage backend. |
| VM-level backup | Scheduled `vzdump` job targeting the `local` storage (94GB), retention e.g. 7 daily + 4 weekly. |
| Docker image updates | Continue the existing project convention of pinned `@sha256:...` digests (already used for `loki`/`promtail`/`grafana`/`mongo`/`redis` in the source compose file) — updates are a deliberate digest bump + commit, never an implicit `:latest` pull. |
| Compose config | Lives in git (the extracted compose file(s) for the VM), same as the source `vibemind-stack.yml` today. |
| Stateful data | App-level backups in addition to VM snapshots, for granular restore without rolling back the whole VM: `pg_dump` (Gitea's postgres, Supabase's postgres), `neo4j-admin database dump` (Neo4j), `mongodump` (Rowboat's Mongo). |

## Non-goals

- Joining the Proxmox VM to the existing Docker Swarm cluster — it runs a standalone `docker compose` deployment, not a Swarm node. Cross-machine Swarm clustering is a separate, much larger undertaking not needed here.
- Moving the Brain cluster, Qdrant, or the coding-engine compute core (see "What stays local" above) — explicitly out of scope for this spec.
- GPU passthrough / eGPU setup for the mini PC — the user's stated future plan ("VRAM for model calls") needs separate hardware (eGPU enclosure or different box) and separate planning; this spec assumes no GPU is available on the Proxmox box.
- Proxmox Backup Server (PBS) — using Proxmox's built-in `vzdump` to local storage instead; PBS would be a separate additional service to stand up.
- **`rowboat-agents`** (discovered during implementation) — its Dockerfile only exists on the `feat/aisalesorgcore-integration` branch, not `feat/mcp-tool-hub`; no local image was ever built here. Needs its own plan once/if that branch's work is merged.

## Phase 2b — Supabase (added 2026-07-14)

Re-scoped after closer investigation: the "90 missing secrets" and "JWT baked into 00-bootstrap.sql" concerns that originally deferred Supabase were both false alarms. `00-bootstrap.sql` reads `$PGPASSWORD`/`$JWT_SECRET` from the environment at init time (no baked-in value); every "secret" across all 10 `supabase-*` services (`<YOUR_JWT_SECRET_AT_LEAST_32_CHARS>`, the `supabase-demo`-issuer anon/service JWTs, `SECRET_KEY_BASE`) is the well-known, publicly documented Supabase self-hosting demo credential set, not a real unique secret. Live local data is trivial (single-digit row counts in a handful of tables) — `01-restore.sql`/`02-restore-internal.sql` are the same committed bootstrap files the local instance already (re-)initializes from, not a separate pg_dump-from-live-db step.

**Deployed to the VM 2026-07-14** via `infra/proxmox/extract_compose.py phase2b` -> `infra/proxmox/phase2b-docker-compose.yml`, same demo secrets as local (rotation deliberately deferred — `kong.yml` embeds the demo JWT 8x in Lua request-transformer templates, rotating it needs its own careful pass). Two real bugs found and fixed along the way:
1. **Init-script ordering bug** (latent, not VM-specific — would hit any *fresh* volume, local included): Postgres's entrypoint runs `/docker-entrypoint-initdb.d/*` alphabetically; the Supabase image's own role-creation script `migrate.sh` sorts *after* our `00-`/`01-`/`02-` prefixed files, so on a truly empty volume `00-bootstrap.sql`'s `ALTER USER postgres ...` ran before the `postgres` role existed. Fixed VM-side only (renamed the container-side mount targets to `z0-`/`z1-`/`z2-`, source filenames untouched) — see `TARGET_OVERRIDES` in `extract_compose.py`.
2. **`supabase-storage` search_path**: `storage-api`'s Node `pg` client didn't inherit the role-level `search_path=storage` default on a fresh DB; fixed by adding `?search_path=storage,public,extensions` to `DATABASE_URL`.

**Open blocker: `supabase-auth` (GoTrue).** Same class of problem (role-level `search_path=auth` not applied) but three different injection mechanisms all failed identically: URL query param, libpq `?options=-c search_path%3D...`, and a dedicated `PGOPTIONS` env var. Strongly suggests GoTrue's `pop` (gobuffalo) ORM issues its own `SET search_path` after connecting, overriding all three. Needs real research into GoTrue 2.188.1's actual config surface, not more trial-and-error. Container is stopped (not crash-looping) on the VM pending that. **9/10 Supabase services are healthy on the VM; local Supabase remains the source of truth and no local consumer has been repointed.**
