# n8n loopback port binding (E6)

## Scope and boundaries

This runbook covers applying, verifying, and rolling back the n8n host port
binding change from the interface-wide form `15678:5678` to the loopback form
`127.0.0.1:15678:5678`, decided as **E6** in
`docs/governance/architecture-decisions-2026-08-15-v1.md`.

The repository change is already committed (task `task-deployment-0017`). This
document does not perform or prove a runtime operation: it performs no
redeploy, no restart, no Proxmox action, and no change to any running service.
`deployment_proven=false` and `golden_path_proven=false` remain true in every
state described here. Applying the binding is a **user action** and is not
covered by the task's authorization.

Affected files:

| File | Mode | Effective? |
|---|---|---|
| `infra/proxmox/phase2a-docker-compose.yml:78` | plain `docker compose` on VM 100 | **yes** — bind address honoured |
| `infra/swarm/vibemind-stack.yml:666` (+ comment block) | `docker stack deploy` (Swarm) | **no** — see §1 |

`infra/swarm/vibemind-stack.yml.bak.pre-profiles-removal:568` is a pre-profiles
backup snapshot and is deliberately **not** changed; it is not a deploy input.

## 1. Read this first — Swarm does not honour the bind address

`infra/swarm/vibemind-stack.yml` is applied with `docker stack deploy`
(`scripts/vibemind-start.ps1:231` via `Invoke-FilteredStackDeploy`,
`Vibemind.debug.ps1:373`). The Swarm service port model
(`EndpointSpec.Ports` → `TargetPort`, `PublishedPort`, `Protocol`,
`PublishMode`) has **no bind-address field**, so a host IP in a stack file's
`ports:` entry is dropped during conversion and the port is published on all
interfaces regardless.

The form is *accepted*, not rejected: `rowboat-mongo` in the same file has
carried `"127.0.0.1:27017:27017"` since the stack was introduced and deploys
healthy (`infra/swarm/profiles/marketing-mailcow.md:245`). So the edited line
records intent and is correct for any compose-mode apply of the same file, but
**on Swarm it provides no protection**.

Consequences:

- Do **not** treat a Swarm redeploy as closing the exposure. On the Swarm path
  the effective control is a host firewall rule on the node, which is out of
  scope for this repository change and needs its own authorization.
- Verification (§4) is mandatory precisely because the file content does not
  predict the runtime bind on this path.

Additionally, per `spaces/marketing/docs/GO_LIVE.md:32`, the Swarm variant of
n8n (`vibemind_n8n`) is **defined but not deployed**. The container actually
serving `:15678` today is `vibemind-n8n`, started from
`vibemind-os/voice/docker-compose.n8n.yml` (submodule, launched by
`Vibemind.debug.ps1:1027` as project `vibemind-n8n`). **That file is outside
this repository and was not changed.** A redeploy of either in-scope file
therefore does not, by itself, change the currently listening socket.

## 2. Pre-flight checks on the host

Run before any apply. All commands are read-only.

1. Identify what is actually listening on `15678` and which binding it uses:

   ```powershell
   # Windows host
   netstat -ano | Select-String ":15678"
   docker ps --filter "publish=15678" --format "{{.Names}}\t{{.Ports}}"
   ```

   ```bash
   # Proxmox VM 100
   ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 \
     "sudo ss -lntp '( sport = :15678 )'; sudo docker ps --filter publish=15678 --format '{{.Names}}\t{{.Ports}}'"
   ```

   A `0.0.0.0:15678` or `:::15678` line is the current, interface-wide state.
   Record it verbatim — it is the rollback reference.

2. Establish whether anything off-host is currently using the open binding.
   This cannot be settled from the repository (see §5); check the live socket:

   ```bash
   ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 \
     "sudo ss -tn state established '( sport = :15678 )'"
   ```

   Any peer address that is not `127.0.0.1` is an off-host consumer that this
   change **will break**. Resolve it before applying.

3. Confirm the in-repo consumers all address loopback (already verified for
   task-deployment-0017, re-confirm if the tree moved):

   ```bash
   grep -rn "15678" --include="*.md" --include="*.sql" --include="*.ps1" --include="*.py" .
   ```

   Expected: every functional consumer resolves to `127.0.0.1:15678` or
   `localhost:15678`. The only non-loopback references are the smoke-test
   `curl http://192.168.178.65:15678/` lines in
   `docs/superpowers/plans/2026-07-13-proxmox-homelab-offload.md:333,372`.

## 3. Apply

Only after §2 is clean, and only with separate user authorization.

**Proxmox VM 100 (the effective change):**

```bash
# copy the updated compose file to the VM, then:
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 \
  "cd ~ && sudo docker compose -f docker-compose.phase2.yml up -d n8n"
```

`docker compose up -d n8n` recreates only the n8n container. The named volume
`n8n_data` is unchanged, so workflows and credentials survive.

**Swarm stack:** a redeploy applies the edited file but, per §1, does not change
the bind. If it is redeployed anyway as part of an unrelated batch, the normal
launcher path (`scripts/vibemind-start.ps1`) is sufficient; no n8n-specific
step is needed.

## 4. Verify

1. The socket is loopback-bound:

   ```bash
   ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "sudo ss -lntp '( sport = :15678 )'"
   ```

   Expected: `127.0.0.1:15678`. A remaining `0.0.0.0:15678` means the change did
   not take effect — on the Swarm path this is the expected outcome (§1).

2. On-host access still works:

   ```bash
   ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "curl -fsS http://127.0.0.1:15678/healthz"
   ```

   Expected: `{"status":"ok"}`. This is the probe from
   `infra/swarm/profiles/marketing-mailcow.md:306`.

3. Off-host access is refused (this is the intended change):

   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://192.168.178.65:15678/
   ```

   Expected: `000` / connection refused. Note this inverts the expectation in
   `docs/superpowers/plans/2026-07-13-proxmox-homelab-offload.md:333`, which
   still documents a `200` here; that smoke step is superseded by E6 for n8n.

4. The marketing webhook path still delivers. The delivery worker runs
   host-bound, outside the docker network, and posts to
   `http://127.0.0.1:15678/webhook/marketing-*`
   (`spaces/marketing/docs/GO_LIVE.md:46-48,52`). Trigger one subscription and
   confirm a 2xx in the worker log. Loopback publishing preserves this path;
   only a fully network-internal binding would break it.

## 5. Residual risk

A consumer outside the host that has been reaching n8n over the open binding
without being recorded in the repository would break at redeploy. The
repository cannot rule this out — no inventory of live callers exists here, and
n8n webhook URLs are configurable per workflow inside `n8n_data`, which is not
under version control. §2 step 2 is the only check that can settle it, and only
while the old binding is still live.

This is a standing precondition for the redeploy, not a one-time note: run §2
step 2 immediately before each apply.

## 6. Rollback

Restore the interface-wide binding by reverting the port line and recreating
the container.

```bash
# in the repository
git revert <commit>            # or edit infra/proxmox/phase2a-docker-compose.yml:78
                               # back to `- 15678:5678`
```

```bash
# on the VM, after copying the reverted file
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 \
  "cd ~ && sudo docker compose -f docker-compose.phase2.yml up -d n8n"
ssh -i ~/.ssh/proxmox_key debian@192.168.178.65 "sudo ss -lntp '( sport = :15678 )'"
```

Expected after rollback: `0.0.0.0:15678`, matching the reference recorded in
§2 step 1.

Rollback is container-recreation only. `n8n_data` is a named volume and is not
touched in either direction, so no workflow, credential, or execution history
is at risk in the apply or the rollback.
