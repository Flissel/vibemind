# Deployment readiness preflight

`scripts/deployment-readiness.ps1` writes a deterministic, redacted inventory of
deployment prerequisites. It is a read-only preflight: it neither deploys nor
changes Docker, Swarm, Proxmox, Supabase, Qdrant, volumes, backups, or databases.

## Static preflight

Run the static inventory from the repository root:

```powershell
pwsh -NoProfile -File .\scripts\deployment-readiness.ps1
```

It writes `results/deployment-readiness.json` by default. The report contains
only check identifiers, statuses, and fixed explanatory text. It does not read
environment files, secret values, or runtime target values. Docker Engine is
not required and is deliberately not queried in this mode.

`-OutputPath` is fail-closed: it is resolved before any directory or report is
created, and must remain inside the resolved `-RepositoryRoot`. Relative paths
are interpreted beneath that repository. An external path is rejected without
creating or overwriting a file.

Static checks verify that the repository boundary and the committed Proxmox
compose/configuration artifacts exist. They also require the committed
`repo-manifest.yaml` pins to align with the tracked Gitlinks and consume the
existing offline `python -m tools.v1_governance submodules readiness --repo .`
result. The validator process is started with the resolved `-RepositoryRoot`
as its working directory (and the caller's working directory is restored
afterward), so Python module resolution cannot silently select a caller-local
`tools` package. A manifest/Gitlink mismatch, an unavailable validator,
malformed validator output, or a blocked validator result is `blocked` and
causes exit code `1`. This check does not initialize, update, or otherwise
modify submodules.

The `static.proxmox-no-model-runtime` check enforces the versioned
[`Proxmox No-Model Runtime V1`](../contracts/proxmox-no-model-runtime-v1.md)
contract against every committed `infra/proxmox/*-docker-compose.yml` artifact.
It blocks model-runtime services and images, model-server commands, and known
model-weight/cache configuration. Remote provider model identifiers are allowed
only as configuration: the actual LLM, embedding, vision, speech, or generative
model must execute outside the Proxmox host and all of its guests. This policy
check is one of the aggregate Golden-Path predeploy prerequisites.

`verified` for `static.submodule-readiness` is only a static prerequisite: it
does not prove a deployment or live service. The report contains no pins,
validator payload, target values, or secrets.

### Static Golden-Path predeploy gate

The static preflight adds eight deterministic, redacted Golden-Path checks:

- `static.golden-path-outer-child-pin`
- `static.golden-path-child-openfang-pin`
- `static.golden-path-child-voice-pin`
- `static.golden-path-contract-chain`
- `static.golden-path-approval-cost-authority`
- `static.golden-path-evidence-authority`
- `static.proxmox-no-model-runtime`
- `static.golden-path-predeploy`

The outer check requires the checked-out `HEAD` to equal `origin/master`, then
requires the reviewed base and required predecessors to be ancestors of that
authoritative master state. The baseline is therefore immutable while master
may advance through a later merge. The reviewed baseline and Gitlink pins are
versioned script constants; callers cannot override them through CLI
parameters. The check verifies the outer `vibemind-os` Gitlink, manifest pin,
and committed offline reconciliation ledger together. The two nested checks
require a readable, clean, materialized `vibemind-os` Git repository at that
Gitlink and inspect its Git tree for the reviewed OpenFang and Voice Gitlinks.
A ledger entry or a manifest alone never verifies a nested Gitlink when the
child Git object is not locally materialized.

The versioned contract checks are repo-first and fail closed. They preserve
Brain's intent, plan, DAG, lifecycle, and truth responsibility; keep
execution, agent/tool scope, approvals, and costs at OpenFang; require the
ordered Brain -> OpenFang -> canonical Space-Agent or deterministic adapter ->
Application -> independent Truth/Evidence boundary; and reject direct
Brain-to-Application, provider, or database fallbacks. Approval and cost
references are checked against the versioned Space-Execution contract and
correlation matrix: OpenFang must retain execution, permissions, approvals,
providers, and costs; the matrix's `What it does not prove` header requires
`approval_id` and `cost_id` to be OpenFang owned, while retaining the explicit
non-proofs of an external action and cost settlement or provider billing. They
do not by themselves establish approval,
execution, booking, or provider billing. Receipt, transport, HTTP, and
registry-only signals likewise cannot substitute for independent evidence.

`static.golden-path-predeploy` is `verified` only when all seven detail checks
are verified. Any absent, off-pin, contradictory, modified, or unreadable
input blocks the aggregate and returns exit code `1`. These are static
contract and Git-object checks only; they do not initialize a submodule or
perform a runtime, provider, Docker, WSL, Proxmox, database, or network action.

### Pinned OpenFang and operational-artifact gates

The preflight also fails closed unless the `vibemind-os` working tree is
available at the Gitlink tracked by the outer repository and its committed
OpenFang routing artifacts are readable:

- `llm_config.yml.example`
- `config/space_agent_registry.yml`

It never initializes, fetches, changes, or executes the submodule. An absent,
off-pin, or unreadable submodule produces `blocked` for the corresponding
OpenFang check.

Three versioned, readable operational runbooks are separate prerequisites:

- `docs/runbooks/proxmox-reboot.md`
- `docs/runbooks/proxmox-backup-restore.md`
- `docs/runbooks/proxmox-cutover-rollback.md`

Each must be present in `HEAD`, tracked in the index, and unmodified in the
working tree. These gates prove only that the named, versioned artifacts are
available for later review. They do not perform or prove a reboot, backup,
restore, cutover, rollback, Proxmox action, Docker action, host reachability,
or database state.

## Opt-in live reachability probes

Only use live probes after a separately approved operational window:

```powershell
pwsh -NoProfile -File .\scripts\deployment-readiness.ps1 `
  -LiveProbes `
  -ProxmoxUri 'https://proxmox.example.invalid:8006/' `
  -SupabaseUri 'http://supabase.example.invalid:54321/' `
  -QdrantUri 'http://qdrant.example.invalid:6333/'
```

The URI values are used only in memory for TCP connection attempts and are
omitted from the report. They must be absolute HTTP/HTTPS URIs without
credentials. Any missing, malformed, or unreachable live target is `blocked`
and causes exit code `1`.

Live probes establish TCP reachability only. A successful probe does not prove
authentication, service health, data integrity, deployment success, or a
Golden Path.

## Reading results

Every check has exactly one status:

- `verified`: this preflight observed the stated prerequisite.
- `blocked`: a required prerequisite is missing, malformed, or unreachable in
  opt-in live mode.
- `unverified`: the prerequisite is intentionally outside the selected
  read-only scope.

The top-level `deployment_proven` and `golden_path_proven` values are always
`false`, including when every static predeploy detail is `verified`. Use this
report as evidence for a later, explicitly approved deployment decision; do
not treat it as proof that a deployment or Golden Path is ready.

## Rollback

The preflight has no runtime rollback because it performs no runtime mutation.
Delete only the generated report if it is no longer needed; it is a local,
ignored evidence artifact.
