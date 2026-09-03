# Proxmox Homelab Offload Implementation Plan

> **For agentic workers:** This plan is infrastructure work (Proxmox VM provisioning, Docker Compose deployment), not application code — steps are exact SSH/qm/docker commands with expected output instead of test code, but the same discipline applies: bite-sized steps, exact commands, verify after every step, commit config changes to git.

**Goal:** Provision one Debian 12 VM on the Proxmox homelab box and move a deliberately-scoped subset of the local Docker stack there in two phases, with a rollback point established before Phase 2 begins.

**Architecture:** Single VM (id 100, static IP 192.168.178.65), Docker Engine + Compose (no Swarm join), one growing `docker-compose.yml` per phase. Full design/rationale: `docs/superpowers/specs/2026-07-13-proxmox-homelab-offload-design.md` — read it before starting.

**Tech Stack:** Proxmox VE 9.2.4 (`qm`/`pvesm` CLI over SSH), Debian 12 cloud image + cloud-init, Docker Engine + Compose plugin, existing service definitions in `infra/swarm/vibemind-stack.yml`.

**Constants used throughout this plan:**
- Proxmox host: `root@192.168.178.64`, SSH key `~/.ssh/proxmox_key` (already verified working — do not recreate it)
- New VM: id `100`, static IP `192.168.178.65/24`, gateway `192.168.178.1`
- Windows host LAN IP (for cross-machine service references): `192.168.178.50`
- Storage: `local-lvm` (VM disks), `local` (ISOs/backups)

---

## Phase 1: VM provisioning + Loki/Grafana/Gitea + rollback baseline

### Task 1: Provision the Debian 12 VM with cloud-init

**Files:** none (Proxmox host state only)

- [ ] **Step 1: Download the Debian 12 generic cloud image on the Proxmox host**

Run (via SSH):
```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "cd /var/lib/vz/template/iso && wget -q https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-generic-amd64.qcow2 && ls -la debian-12-generic-amd64.qcow2"
```
Expected: a file listing showing `debian-12-generic-amd64.qcow2` (~400-600MB).

- [ ] **Step 2: Create the VM shell**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm create 100 --name vibemind-offload-1 --memory 24576 --cores 12 --cpu host --net0 virtio,bridge=vmbr0 --ostype l26 --agent enabled=1"
```
Expected: no output (success) or `VM 100 created`. Verify: `ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm status 100"` → `status: stopped`.

- [ ] **Step 3: Import the cloud image as the VM's disk and attach it**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm importdisk 100 /var/lib/vz/template/iso/debian-12-generic-amd64.qcow2 local-lvm && qm set 100 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-100-disk-0 && qm set 100 --boot order=scsi0 && qm resize 100 scsi0 32G"
```
Expected: `Successfully imported disk as 'unused0:local-lvm:vm-100-disk-0'` then confirmation lines from each `qm set`/`qm resize`. Verify: `ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm config 100 | grep scsi0"` shows a 32G disk on `local-lvm`.

- [ ] **Step 4: Add cloud-init drive, SSH key, and static network config**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm set 100 --ide2 local-lvm:cloudinit --sshkey ~/.ssh/proxmox_key.pub --ciuser debian --ipconfig0 ip=192.168.178.65/24,gw=192.168.178.1"
```
Expected: `update VM 100: -ide2 local-lvm:cloudinit ...` confirmation.

- [ ] **Step 5: Start the VM and verify SSH access**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm start 100"
```
Wait ~30s for boot, then from the Windows machine:
```bash
timeout 10 ssh -i ~/.ssh/proxmox_key -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 debian@192.168.178.65 "hostname && cat /etc/debian_version"
```
Expected: `vibemind-offload-1` (or the cloud-init default hostname) and a Debian 12 version string (`12.x`). If it times out, wait another 20s and retry (cloud-init can take a minute on first boot).

- [ ] **Step 6: Install Docker Engine + Compose plugin**

```bash
timeout 60 ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker debian"
```
Expected: script output ending in `Client: Docker Engine - Community` version banner, no errors.

- [ ] **Step 7: Verify Docker works**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "sudo docker run --rm hello-world"
```
Expected: `Hello from Docker!` banner text.

### Task 2: Generate the Phase 1 compose file

**Files:**
- Create: `infra/proxmox/phase1-docker-compose.yml`
- Create: `infra/proxmox/extract_compose.py`

- [ ] **Step 1: Write the extraction script**

Create `infra/proxmox/extract_compose.py`:
```python
"""Extract named services from infra/swarm/vibemind-stack.yml into a plain
(non-Swarm) docker-compose.yml for a remote host, stripping Swarm-only keys
and applying the cross-machine env var overrides needed for that host.

Usage: python extract_compose.py <phase1|phase2> > output.yml
"""
import sys
import yaml

SOURCE = "infra/swarm/vibemind-stack.yml"

PHASE1_SERVICES = ["loki", "grafana-vibemind", "coding-gitea", "gitea-postgres"]
PHASE2_SERVICES = [
    "rowboat-mongo", "rowboat-redis", "rowboat", "rowboat-agents",
    "rowboat-jobs-worker", "rowboat-rag-worker", "neo4j-mirofish", "n8n",
    "supabase-db", "supabase-auth", "supabase-rest", "supabase-realtime",
    "supabase-storage", "supabase-pg-meta", "supabase-analytics",
    "supabase-kong", "supabase-studio", "supabase-inbucket",
]

# Env var rewrites keyed by service name: {old_value_prefix: new_value}
ENV_REWRITES = {
    "coding-gitea": {
        "GITEA__server__ROOT_URL=http://localhost:3002/": "GITEA__server__ROOT_URL=http://192.168.178.65:3002/",
    },
    "rowboat": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-agents": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-jobs-worker": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
    "rowboat-rag-worker": {"QDRANT_URL=http://qdrant:6333": "QDRANT_URL=http://192.168.178.50:6730"},
}

STRIP_KEYS = ["deploy", "secrets", "extra_hosts", "configs", "healthcheck"]


def main():
    phase = sys.argv[1]
    names = PHASE1_SERVICES if phase == "phase1" else PHASE2_SERVICES

    with open(SOURCE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    out_services = {}
    out_volumes = {}
    all_services = data["services"]

    for name in names:
        cfg = dict(all_services[name])
        for key in STRIP_KEYS:
            cfg.pop(key, None)
        cfg["restart"] = "unless-stopped"
        cfg.pop("networks", None)

        rewrites = ENV_REWRITES.get(name, {})
        if rewrites and isinstance(cfg.get("environment"), list):
            new_env = []
            for entry in cfg["environment"]:
                new_env.append(rewrites.get(entry, entry))
            cfg["environment"] = new_env

        out_services[name] = cfg

        for vol in cfg.get("volumes", []):
            if ":" in vol and not vol.startswith("/"):
                vol_name = vol.split(":")[0]
                if vol_name in data.get("volumes", {}):
                    out_volumes[vol_name] = {}

    result = {"services": out_services}
    if out_volumes:
        result["volumes"] = out_volumes

    print(yaml.dump(result, sort_keys=False, default_flow_style=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it for Phase 1 and save the output**

```bash
cd /c/Users/User/Desktop/Vibemind_V1
"/c/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe" infra/proxmox/extract_compose.py phase1 > infra/proxmox/phase1-docker-compose.yml
cat infra/proxmox/phase1-docker-compose.yml
```
Expected: valid YAML with exactly 4 services (`loki`, `grafana-vibemind`, `coding-gitea`, `gitea-postgres`), no `deploy:`/`networks:` keys, and `coding-gitea`'s `GITEA__server__ROOT_URL` showing `192.168.178.65`.

- [ ] **Step 3: Validate the compose file parses**

```bash
scp -i ~/.ssh/proxmox_key infra/proxmox/phase1-docker-compose.yml debian@192.168.178.65:/home/debian/docker-compose.yml
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "cd /home/debian && sudo docker compose config -q && echo COMPOSE_OK"
```
Expected: `COMPOSE_OK` with no errors.

- [ ] **Step 4: Commit**

```bash
git add infra/proxmox/extract_compose.py infra/proxmox/phase1-docker-compose.yml
git commit -m "feat(infra): add Proxmox compose extraction script + phase 1 compose file"
```

### Task 3: Deploy Phase 1 services and verify

**Files:** none (remote deployment)

- [ ] **Step 1: Deploy**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "cd /home/debian && sudo docker compose up -d"
```
Expected: 4 containers created and started (`loki`, `grafana-vibemind`, `gitea-postgres`, `coding-gitea`).

- [ ] **Step 2: Verify each service responds**

```bash
sleep 15
curl -s -o /dev/null -w "Loki: %{http_code}\n" http://192.168.178.65:3102/ready
curl -s -o /dev/null -w "Grafana: %{http_code}\n" http://192.168.178.65:3030/api/health
curl -s -o /dev/null -w "Gitea: %{http_code}\n" http://192.168.178.65:3002/
```
Expected: `Loki: 200`, `Grafana: 200`, `Gitea: 200` (or `302` for Gitea's first-run redirect — both acceptable).

### Task 4: Redirect local Promtail to the remote Loki

**Files:**
- Modify: `infra/swarm/vibemind-stack.yml` (promtail's Loki client config, if defined via command/config file — locate the actual client URL first)

- [ ] **Step 1: Find Promtail's current Loki target**

```bash
cd /c/Users/User/Desktop/Vibemind_V1
grep -rn "loki:3100\|localhost:3100\|clients:" infra/ --include="*.yml" --include="*.yaml" -A3 | grep -B3 "url:"
```
This locates the Promtail config (likely a mounted config file, not inline in the compose command — find its actual path before editing).

- [ ] **Step 2: Update the target to the remote Loki, redeploy locally**

Edit whatever config file Step 1 found so the `clients: - url:` line points to `http://192.168.178.65:3102/loki/api/v1/push` instead of the local address. Then:
```bash
cd /c/Users/User/Desktop/Vibemind_V1
docker compose -f infra/swarm/vibemind-stack.yml restart promtail 2>&1 || echo "adjust command for actual local orchestration (swarm vs compose)"
```
Expected: promtail restarts cleanly. Verify logs are arriving: query the remote Loki from the Windows machine:
```bash
curl -s "http://192.168.178.65:3102/loki/api/v1/labels" | head -c 300
```
Expected: a JSON body listing label names (proves Loki has received at least one log stream).

- [ ] **Step 3: Commit**

```bash
git add infra/
git commit -m "fix(infra): point local Promtail at the remote Proxmox Loki instance"
```

### Task 5: Establish the rollback baseline

**Files:** none (Proxmox host state only)

- [ ] **Step 1: Snapshot the VM now that Phase 1 is verified working**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm snapshot 100 phase1-complete --description 'Loki+Grafana+Gitea working, before Phase 2'"
```
Expected: `snapshotting 'drive-scsi0' ... 100%` then success (no error).

- [ ] **Step 2: Verify the snapshot exists**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm listsnapshot 100"
```
Expected: a line showing `phase1-complete`.

- [ ] **Step 3: Set up a scheduled vzdump backup job**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "pvesh create /cluster/backup --starttime 03:00 --dow 'mon,tue,wed,thu,fri,sat,sun' --storage local --vmid 100 --mode snapshot --prune-backups 'keep-daily=7,keep-weekly=4' --enabled 1"
```
Expected: a job ID returned, no error. Verify: `ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "pvesh get /cluster/backup"` shows the new job.

---

## Phase 2: Rowboat + Neo4j + n8n + Supabase

### Task 6: Copy required secrets to the VM

**Files:** none (remote `.env` file, never committed)

- [ ] **Step 1: Identify the exact env var names needed**

The Phase 2 services need these variables (values live in the Windows machine's `c:\Users\User\Desktop\Vibemind_V1\.env` — do not print or commit their values): `POSTGRES_PASSWORD`, `JWT_SECRET`, `N8N_API_KEY`, `N8N_ENCRYPTION_KEY`, `AGENTS_API_KEY`, `MIROFISH_NEO4J_USER`, `MIROFISH_NEO4J_PASSWORD`.

- [ ] **Step 2: Extract just those keys into a temp file and copy it over**

```bash
cd /c/Users/User/Desktop/Vibemind_V1
grep -E "^(POSTGRES_PASSWORD|JWT_SECRET|N8N_API_KEY|N8N_ENCRYPTION_KEY|AGENTS_API_KEY|MIROFISH_NEO4J_USER|MIROFISH_NEO4J_PASSWORD)=" .env > /tmp/phase2.env
scp -i ~/.ssh/proxmox_key /tmp/phase2.env debian@192.168.178.65:/home/debian/.env
rm /tmp/phase2.env
```
Expected: file transferred, local temp copy removed immediately after.

- [ ] **Step 3: Verify it landed without displaying contents**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "wc -l /home/debian/.env && chmod 600 /home/debian/.env"
```
Expected: a line count matching the number of keys copied (7), permissions locked to owner-only.

### Task 7: Generate and deploy the Phase 2 compose file

**Files:**
- Create: `infra/proxmox/phase2-docker-compose.yml`

- [ ] **Step 1: Run the extraction script for Phase 2**

```bash
cd /c/Users/User/Desktop/Vibemind_V1
"/c/Users/User/Desktop/Vibemind_V1/.venv/Scripts/python.exe" infra/proxmox/extract_compose.py phase2 > infra/proxmox/phase2-docker-compose.yml
```
Expected: valid YAML with all 18 Phase 2 services, `rowboat*` services' `QDRANT_URL` rewritten to `http://192.168.178.50:6730`.

- [ ] **Step 2: Copy it over as a second compose file (kept separate from Phase 1's, both apply to the same running Docker Engine)**

```bash
scp -i ~/.ssh/proxmox_key infra/proxmox/phase2-docker-compose.yml debian@192.168.178.65:/home/debian/docker-compose.phase2.yml
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "cd /home/debian && sudo docker compose -f docker-compose.phase2.yml --env-file .env config -q && echo COMPOSE_OK"
```
Expected: `COMPOSE_OK`.

- [ ] **Step 3: Deploy**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "cd /home/debian && sudo docker compose -f docker-compose.phase2.yml --env-file .env up -d"
```
Expected: 18 containers created and started.

- [ ] **Step 4: Verify the key entry points respond**

```bash
sleep 20
curl -s -o /dev/null -w "Rowboat: %{http_code}\n" http://192.168.178.65:3100/
curl -s -o /dev/null -w "Neo4j: %{http_code}\n" http://192.168.178.65:7475/
curl -s -o /dev/null -w "n8n: %{http_code}\n" http://192.168.178.65:15678/
curl -s -o /dev/null -w "Supabase Studio: %{http_code}\n" http://192.168.178.65:54323/
curl -s -o /dev/null -w "Supabase Kong: %{http_code}\n" http://192.168.178.65:54321/
```
Expected: all `200` (or `302`/`401` for auth-gated ones — anything except `000`/connection-refused means the service is up).

- [ ] **Step 5: Verify Rowboat can actually reach the remote Qdrant**

```bash
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "sudo docker compose -f docker-compose.phase2.yml logs rowboat --tail 30" | grep -i "qdrant\|error"
```
Expected: no connection-refused/timeout errors referencing Qdrant in the recent logs.

- [ ] **Step 6: Commit**

```bash
git add infra/proxmox/phase2-docker-compose.yml
git commit -m "feat(infra): deploy phase 2 (Rowboat/Neo4j/n8n/Supabase) to Proxmox VM"
```

### Task 8: Post-Phase-2 snapshot

**Files:** none

- [ ] **Step 1: Snapshot again now that both phases are live**

```bash
ssh -i ~/.ssh/proxmox_key root@192.168.178.64 "qm snapshot 100 phase2-complete --description 'Full phase 1+2 stack running'"
```
Expected: success, verified via `qm listsnapshot 100` showing both `phase1-complete` and `phase2-complete`.

---

## After all tasks

Update `docs/superpowers/specs/2026-07-13-proxmox-homelab-offload-design.md` if any step deviated from the spec during execution (exact IPs, VMID, or resource sizing that changed). Then report the final state: which services are now remote, their URLs, and the two snapshot names available for rollback.

## Final status (2026-07-13)

**Deployed and verified, running on VM 100 (192.168.178.65):** Loki (3102), Grafana (3030), Gitea+Postgres (3002), Rowboat core+Mongo+Redis (3100), rowboat-jobs-worker, rowboat-rag-worker, Neo4j/MiroFish (7475), n8n (15678). Rollback snapshots `phase1-complete` and `phase2a-complete` exist; daily `vzdump` backup job configured (03:00, 7 daily + 4 weekly retention).

**Scope closed out, not deployed — with reasons, not left as vague TODOs:**

1. **`rowboat-agents`** — permanently descoped from this plan. Its `Dockerfile` (`vibemind-os/spaces/rowboat/rowboat/apps/rowboat_agents/Dockerfile`) exists only on the `feat/aisalesorgcore-integration` branch/worktree, not on `feat/mcp-tool-hub` where this work happened. No image was ever built locally on this branch, so there was nothing to transfer. Re-scope this in a future plan once that branch's work lands here (or is cherry-picked deliberately, as its own decision).
2. **Supabase (all 10 services)** — permanently descoped from this plan. This is not a simple redeploy: `infra/swarm/supabase/initdb/` contains committed SQL snapshots of real production data (with an explicit `--exclude-table-data=public.face_target_blobs` carve-out noted in `infra/swarm/supabase/README.md`), and a JWT secret baked into `00-bootstrap.sql` at the Postgres level that the ~90 application-level env vars (GOTRUE_*, PGRST_*, KONG_*, storage keys, etc.) would need to match exactly. That migration already has its own tracked plan (referenced in `infra/swarm/supabase/README.md` as `~/.claude/plans/k-nnnen-wir-adative-skills-splendid-mochi.md`) with its own cutover/rollback procedure. Grafting a Proxmox move onto it here, without reading that plan and coordinating explicitly, would risk a real data migration — out of scope for this plan.
3. **Local Promtail redirect** — code-complete (`infra/swarm/logging/promtail-config.yml` points at the remote Loki, `infra/swarm/vibemind-stack.yml`'s `promtail_config_v1` bumped to `v2`), committed, but not yet activated: applying it requires `docker stack deploy -c infra/swarm/vibemind-stack.yml vibemind` against the full local 40-service stack, which needs a human to explicitly run or approve given this project's documented history of Swarm commands taking down the whole stack (see project memory `feedback_never_service_update_vibemind`, `feedback_swarm_config_immutable`). This is the one remaining action item, and it is a single approve-or-run decision, not open design work.

This plan's implementable scope (Phase 1 fully + Phase 2 narrowed to Rowboat-core/Neo4j/n8n) is complete. Items 1 and 2 are deliberate exclusions requiring separate future plans, not unfinished work within this one.
