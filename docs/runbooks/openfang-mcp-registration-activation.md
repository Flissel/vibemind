# OpenFang MCP registration — activation and readback

Activation and readback procedure for the live MCP registration of the
**Ideas golden path** per `docs/contracts/openfang-mcp-authority-v1.md` /
`shared/contracts/openfang-mcp-authority-v1.json`
(`task-integration-0005b-openfang-mcp-live-registration-v1`, runtime
authority `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T19:42:00Z`,
recorded in `docs/governance/session-request-queue-v1.md` §3.1c).

The OpenFang runtime binds `api_listen = "127.0.0.1:4200"`
(`vibemind-os/openfang/openfang.vibemind.toml`), so every step below runs
**on the host that runs OpenFang** — it cannot be executed from a remote
session. A registration claim is valid **only** with a correlated status
readback (contract N6): `GET /api/mcp/servers` listing the golden-path
servers as connected plus per-agent allowlist readback. A config file on
disk, a green health ping, or clean logs prove nothing.

## Scope and prohibitions

This runbook activates and *verifies* the registration plane only. It does
not write any space data: the test `idea_connect`/`bubble_create` execution
with database readback (contract `remaining_for_0005b` item 4) belongs to
the separate data-authority task and MUST NOT be performed under this
runbook. Do not create or modify secrets here — the Supabase values are
expected to exist already in the root `.env`; if they are missing, stop and
report. No Proxmox mutation, no force operations, no pin changes.

## Preconditions

1. `Vibemind_V1` checkout with `vibemind-os` initialized per
   `docs/runbooks/submodule-checkout-workflow.md` (readiness gate green).
2. The `vibemind-os` checkout contains
   `scripts/verify_openfang_mcp_registration.py` (service branch
   `codex/integration/task-integration-0005b-mcp-registration-v1`, commit
   `ea0126b13585c84fcbfe2306c1ad7882519a299a`, until it is merged and the
   superproject pin is updated by the follow-up pin task).
3. Root `.env` (loaded by `Vibemind.debug.ps1` into the daemon process
   environment) already contains `SUPABASE_URL`,
   `SUPABASE_SERVICE_ROLE_KEY` (spaces-ideas fails closed without them —
   `spaces/ideas/mcp_server.py:336-343`) and `SUPABASE_ANON_KEY`
   (vibemind-db falls back to `http://localhost:54321` without it —
   `voice/python/vibemind_db_mcp.py:23-24`, the wrong data plane).
   Verify presence only; do not print values:

   ```powershell
   Select-String -Path .env -Pattern '^(SUPABASE_URL|SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ANON_KEY)=' | ForEach-Object { ($_ -split '=')[0] }
   ```

4. OpenFang release binary built
   (`vibemind-os/openfang/target/release/openfang.exe`).

## Step 0 — Apply the env-allowlist registration fix (blocker B1)

**Without this step the registration readback will fail.** OpenFang spawns
stdio MCP servers with a cleared environment and passes only the variables
whitelisted in the entry's `env` array
(`openfang/crates/openfang-runtime/src/mcp.rs:235-260`,
`McpServerConfigEntry.env`, `config.rs:1442-1444`). At pin `33be359` the
`spaces-ideas` and `vibemind-db` entries declare **no** `env` whitelist, so
the Supabase credentials never reach either server: `spaces-ideas` connects
but every tool call returns `configuration_error`; `vibemind-db` silently
talks to `localhost:54321` instead of the Proxmox Supabase.

The fix belongs to the `Flissel/openfang` repository (template **and**
rendered config), which is outside the 0005b session's repository scope —
apply it as a commit in `openfang` (follow-up service change) or, for a
first activation, directly in the working tree on this host. TOML
placement matters: `env` is an **entry-level** key and must appear before
the `[mcp_servers.transport]` sub-table header.

In `vibemind-os/openfang/openfang.vibemind.toml.template` **and** (until
re-rendered) `vibemind-os/openfang/openfang.vibemind.toml`:

```toml
[[mcp_servers]]
name = "vibemind-db"
timeout_secs = 10
env = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]
[mcp_servers.transport]
# ... unchanged ...

[[mcp_servers]]
name = "spaces-ideas"
timeout_secs = 60
env = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
[mcp_servers.transport]
# ... unchanged ...
```

Success criterion: `GET /api/mcp/servers` later shows
`"env": ["SUPABASE_URL", ...]` on both `configured` entries.

## Step 1 — Render the host-specific config (contract gap: host-bound paths)

The registration entries carry absolute paths; the template is the
cross-platform source of truth. Render it for this host (resolves
`remaining_for_0005b` item 5):

```powershell
python vibemind-os/openfang/scripts/render_openfang_config.py
```

Expected output: `rendered: ...openfang.vibemind.toml` plus the substituted
`VIBEMIND_ROOT`/`HOME` values, no leftover placeholders. On the current
Windows host (`C:/Users/User/Desktop/Vibemind_V1`) the rendered paths equal
the previously tracked ones; on any other host this step is what makes the
registration valid at all. Note: rendering from an unpatched template
overwrites the Step-0 edit in the rendered file — apply Step 0 to the
template first (or re-apply after rendering).

## Step 2 — Start the runtime

Either the full stack:

```powershell
.\Vibemind.debug.ps1
```

or OpenFang alone from `vibemind-os/openfang`:

```powershell
.\target\release\openfang.exe start --config .\openfang.vibemind.toml
```

Success criterion: `GET http://127.0.0.1:4200/api/health` answers within
10 s. This alone is **not** a registration claim.

## Step 3 — Correlated status readback (the actual proof)

```powershell
python vibemind-os/scripts/verify_openfang_mcp_registration.py `
  --evidence-out docs/operations/task-integration-0005b-live-readback-evidence.json
```

The verifier loads its expectations from
`shared/contracts/openfang-mcp-authority-v1.json` (auto-discovered; or pass
`--contract`) and checks, fail-closed:

| Check | Contract item | Meaning |
| --- | --- | --- |
| `configured:/connected: spaces-ideas`, `vibemind-db` | `remaining_for_0005b` 1 | both golden-path servers registered **and** live-connected |
| `tools:spaces-ideas` | `remaining_for_0005b` 1 | exactly the 13 contract tools (incl. `idea_connect`, `bubble_create`), no missing, no rogue extras |
| `agent-present:` / `allowlist-mode:` / `scope: brain-ideas`, `brain-bubbles` | `remaining_for_0005b` 2 | roles running with `mcp_servers_mode = "allowlist"` and exactly the contract scopes (`mcp_servers_mode = "all"` fails — empty scope means every connected server, contract N2) |

Exit codes: `0` = every check passed (the only state that supports a
"live" claim); `1` = runtime answered but at least one check failed —
registration is **not** proven, see the failure table; `2` = runtime
unreachable — fail-closed, no claim of any kind.

If `api_key` is set in the merged config, export `OPENFANG_API_KEY` first
(`GET /api/mcp/servers` and `GET /api/agents/:id` require auth; the agent
*list* is public).

## Step 4 — Record the evidence

Commit the evidence JSON under `docs/operations/` on the 0005b superproject
branch (or hand it to the orchestrator). The JSON contains UTC timestamp,
endpoint, per-check verdicts and SHA-256 digests of the raw responses —
that is the correlation the contract requires. Only after this readback may
`docs/governance/` records describe the registration as live.

Remaining after this runbook (not covered here, by design):

- `remaining_for_0005b` item 3 (runtime provenance enforcement on
  `idea.connect` / `bubble.create` envelopes) and item 4 (independent
  database readback of a created row) require executing a real intent —
  that is the separate data-authority task on the Ideas golden path.

## Failure modes

| Symptom | Likely cause | Response |
| --- | --- | --- |
| exit 2, connection refused | runtime not started, wrong host, or port ≠ 4200 | Step 2; check `vibemind.config.json` `ports.openfang` |
| `connected:spaces-ideas` FAIL while `configured:` passes | server process failed to spawn/handshake — check OpenFang log (`logs/openfang/openfang.log`), commonly wrong Python path or Step 1 skipped | re-run Step 1, restart |
| `tools:spaces-ideas` missing tools | outdated `spaces/ideas/mcp_server.py` checkout | verify vibemind-os checkout/branch |
| tool calls later fail `configuration_error` despite green readback | Step 0 skipped (env whitelist) — readback proves connection+tools, env only shows in `configured.env` | apply Step 0, restart |
| `agent-present:brain-ideas` FAIL | agent role not installed/running in this instance | start the stack via `Vibemind.debug.ps1` (agents are provisioned by the vibemind boot path), then re-run |
| `allowlist-mode:` FAIL (`mode=all`) | manifest lost its `mcp_servers` allowlist — forbidden implicit-all | run `python scripts/sync_openfang_agents.py --check` in `vibemind-os`, restore manifests |
| `scope:` FAIL | manifest drift vs. registry | same `--check`, then re-sync via the generator (never hand-edit generated manifests) |

Never respond to a failed check by editing the readback expectations, by
claiming partial success, or by inventing output. The evidence JSON of a
failed run is itself a valid governance artifact — record it.
