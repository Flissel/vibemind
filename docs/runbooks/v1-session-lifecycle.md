# V1 session lifecycle

Git CLI, committed contracts, the repository manifest, and governance tests are authoritative for session state.

## State model

```text
draft -> standing-autonomy-admitted -> active -> handoff-ready
      -> pending-user-approval -> approved -> active
      -> denied                         -> blocked
handoff-ready -> pr-open -> checks-green -> merged -> verified -> closed
```

- `draft`: objective, scope, risks, definition of done, and test strategy are being defined interactively.
- `standing-autonomy-admitted`: a bounded `docs` or `code` request cites `standing-autonomy:v1`, has complete provenance and may continue without per-session user interaction.
- `pending-user-approval`: a high-risk request lacks request-specific authority; the affected task pauses fail-closed without repeatedly interrupting the user.
- `approved`: request-specific authority, parent cockpit, durable request reference, declared dependencies, and merge position have been recorded.
- `active`: the approved task runs in its isolated worktree and branch.
- `blocked`: progress stopped with the blocker and available evidence recorded.
- `handoff-ready`: scoped commits, exact test evidence, request-bound provenance, dependencies, merge position, deployment status, and remaining blockers are recorded.
- `pr-open` through `closed`: the V1 orchestrator owns checks, dependency order, merge, post-merge verification, and closure.

`standing-autonomy:v1` is committed evidence of a real standing user mandate, not tool-generated approval. It authorizes bounded `docs` and `code` tasks, including routine session activation, worktrees, commits, pushes, PR maintenance, green merges, and post-merge verification. It cannot be inferred, renamed, or expanded. High-risk work—deployment, destructive actions, breaking contracts, database migrations, secrets, Proxmox mutations, large repository moves, or cleanup—requires request-specific authority and fails closed when that authority is absent.

A `space-cockpit` is read-only. It can refine a plan and prepare a bounded task request, but cannot itself write application code. Routine `docs`/`code` task requests may be admitted under the standing mandate. Material scope or risk changes require reclassification; high-risk changes leave standing autonomy and fail closed.

## Current MVP governance precedence

Die aktuelle MVP-Governance hat Vorrang vor historischen Spezifikationen. Das aktuelle Portfolio in `docs/superpowers/specs/2026-07-30-v1-codex-session-portfolio-design.md` bestimmt den MVP-Scope; dieses Lifecycle-Runbook bestimmt die Session- und Task-Governance.

Für die **Erstellung** von Sessions gilt zusätzlich `docs/governance/multi-session-program-charter-v1.md` (2026-08-13): jede Session — Cockpit wie Implementierung — wird nur nach individueller User-Freigabe erstellt. `standing-autonomy-admitted` bezieht sich auf die Zulassung begrenzter `docs`-/`code`-Arbeit innerhalb bestehender, freigegebener Sessions, nicht auf die Erstellung neuer Sessions.

`docs/governance/session-portfolio-registry-v1.json` is the versioned static registry of
the 22 normative cockpit memberships from that portfolio. Its membership authority is
the portfolio itself. Each registry entry is limited to one historical external
`final_reported` observation with `evidence_scope: external-not-git-verified`; it is
not Git verification. Current lifecycle remains main-orchestrator-external. The
registry does not establish approval, acceptance, closure, handoff, PR, merge, runtime,
live, or Golden-Path evidence.

`docs/governance/cockpit-activation-evidence-v1.json` is the fail-closed evidence
ledger for the same 22 cockpit IDs. It separates normative membership, standing
activation authority, historical observation, and current activation or interactivity
evidence. `standing-autonomy:v1` means authority available for bounded activation; it
does not prove activation, interactivity, or approval. The 22 historical external observations
remain historical-only, and every current claim remains `not-git-evidenced` unless a durable
evidence reference is recorded.

Since `task-governance-0031` the ledger is recordable through a closed, narrowly
shaped vocabulary that does not weaken the fail-closed principle:
`activation: "git-evidenced-creation"` is valid only together with a strictly
shaped durable reference `ccr-session:<session-id>@<rfc3339>` naming the recorded
session creation, and `approval: "git-evidenced-approval-ledger"` is valid only
together with that creation claim and a well-formed entry for the same cockpit in
the closed approval ledger. Interactivity has no durable reference form and stays
`not-git-evidenced` only. An entry without a durable reference remains mandatorily
`not-git-evidenced` in every field; any other vocabulary, any reference without a
creation claim, and any malformed reference shape are rejected. A creation record
is configured evidence of the recorded session creation at the referenced time
only — it is not activation, interactivity, runtime, reachable, `verified_live`,
or Golden-Path evidence. On this basis the eleven wave-1 to wave-3 cockpit
creation records from `docs/governance/session-request-queue-v1.md` section 2.1
are recorded as `git-evidenced-creation` entries; the remaining eleven entries
stay fully `not-git-evidenced` with a null reference.

`docs/governance/cockpit-external-observations-v1.json` is the only Git-durable
sidecar for fresh observations supplied from external User-Owned Codex threads. Its
records are limited to a thread identifier, observed time, and the fixed
`external-not-git-verified` vocabulary. They do not claim status, activation,
interactivity, approval, acceptance, handoff, PR, merge, runtime, or live evidence.
Observing an existing User-Owned thread does not authorize creation, mutation, or use
of a new User-Owned thread: each such thread requires the user's individual approval.

`docs/governance/cockpit-next-task-external-references-v1.json` is a separate,
closed sidecar for current task or gate references observed in those external threads.
It deliberately does not rewrite the static next-task register, which remains a
historical planning snapshot. A reference is not a task request, approval, execution,
admission, handoff, PR, merge, runtime, live, or gate-outcome claim.

`docs/governance/cockpit-approval-ledger-v1.json` is the separate, closed ledger for
that creation authority. An entry records only a normative cockpit ID, its visible
title, a durable `codex-user-message:<thread-id>@<timestamp>` approval reference, and
the creation timestamp. The orchestrator must run `python -m tools.v1_governance
cockpit approval-check --repo . --cockpit <cockpit-id>` before a User-Owned Codex
thread is created. The ledger does not backfill unverified approvals.
All 22 normative cockpits hold creation-authority references:
`cockpit-openfang` and `cockpit-agentfarm` from 2026-08-04/05,
`cockpit-git`, `cockpit-shared`, `cockpit-brain` and `cockpit-deployment` from
the user's wave-1 approval of 2026-08-13, and the remaining 16 portfolio
cockpits from the user's maintenance delegation of 2026-08-13 (charter
section 4a). Historical observations remain non-claiming: the historical
thread creation predates the approval evidence and none of these references
proves activation.

Use `python -m tools.v1_governance cockpit portfolio-check --repo .` for the
read-only portfolio evidence view. It emits one JSON row per normative cockpit,
in deterministic cockpit-ID order, with membership, individual pre-creation
approval availability, historical-observation presence, the recorded current
activation, interactivity, and approval evidence, and any recorded durable
evidence reference. It does not infer current activation or interactivity
from standing authority, historical observations, or external
sidecars; malformed, duplicate, open, or membership-drifting evidence fails closed.

The visible title is display metadata, not proof. The approval reference is a
reference-only pointer: repository validation checks its closed shape and time order,
but does not attest the external message content. This procedural gate does not
intercept the external Codex App API; the main orchestrator must therefore treat a
successful check as a mandatory precondition and must never call the external creation
tool after a denied or unavailable check. Neither an approval reference nor a
historical observation proves activation, interactivity, runtime, or live evidence.

`docs/governance/cockpit-reconciliation-ledger-v1.json` is a closed offline
reconciliation ledger for explicitly named historical merge and Gitlink facts. Its
validator checks local outer-repository merge parents and Gitlinks, then requires an
already initialized local Child checkout (or an explicitly supplied local Child
root) for Child merges and Gitlinks and a separately, explicitly supplied local
OpenFang repository root for OpenFang merges. Both supplied paths must be actual Git
repository roots; it never initializes or fetches either repository. The post-pin
record is fail-closed:
`99d41a7…` must point to `vibemind-os` `26003b95…`, and the recorded Child tree must
name `openfang` `fac8e429…` and `voice` `2a457625…`. PR #115 is represented only by
its merge object `26003b95…`; a PR head is never a substitute. The two leaf commits
are recorded as `not-locally-materialized`, so the ledger makes no leaf-history,
reachable, or `verified_live` claim.

The outer reconciliation chain additionally records the exact local merge objects for
PRs #108 through #112, with each first parent continuing the prior recorded merge.
The PR #112 merge object `b790600…` statically pins `vibemind-os` `7747d3b…`; the
recorded Child tree statically pins `shared` `fe9c31d…`. The shared target is
`not-locally-materialized`: this is tree-entry evidence only, not Child-object,
leaf-history, reachability, or `verified_live` evidence.

The post-authority-pin continuation records outer PRs #113 through #115, Child PRs
#120 through #122, and OpenFang PRs #7 and #8 as exact local merge objects and parent
pairs. The latest outer merge `81200725…` (whose tree matches `cd6f092…`) statically
pins `vibemind-os` `805363f…`; that Child tree statically pins OpenFang `cd3cef…`,
shared `fe9c31d…`, and voice `2a457625…`. OpenFang PR #8 is represented only by the
merge object `cd3cef…`; neither a PR head nor a missing or non-root checkout is an
acceptable substitute. These are local historical/tree facts only and do not prove
runtime, deployment, reachability, or `verified_live` state.

Only `historical-*` and `static-*` evidence classes are allowed. The two external
task references and `gate-integration-0016-vibemind-os-pr115-postpin-regate-v1` are
opaque historical references. The reported `PASS` for that gate is external test
evidence only; it is not runtime, live, approval, acceptance, cost, booking,
execution, or merge-success evidence.

Every schema-v2 task request is checked against this registry during session validation,
worktree planning, and PR readiness. A missing, malformed, or non-member
`parent_cockpit` fails closed. This is a membership gate only: it does not create or
prove a cockpit audit, lifecycle status, approval, handoff, PR, merge, runtime, or
Golden-Path evidence.

OpenFang execution is part of the current MVP wave. Brain remains the control plane and OpenFang is the only Product-Runtime execution boundary for Space agents, MCP/tools, providers, costs, permissions, and runtime approvals. This scope decision authorizes planning and separately approved implementation tasks; it does not by itself prove a live runtime, approve deployment, or waive the normal task-specific user gate.

The repository fork recorded on 2026-08-01 is historical, superseded context rather
than a current repository-state claim. Its former integration-gate language does not
establish the current Gitlink, branch reachability, integration status, runtime, or MVP
baseline. Any new Git task must establish those facts from fresh repository evidence.

## Submodule readiness gate

Before a Space implementation starts, run:

```powershell
python -m tools.v1_governance submodules readiness --repo .
```

The command emits machine-readable JSON with `ready` and redacted `findings`. Exit `0` means ready; exit `2` means unready or unavailable. It is strictly read-only: it never initializes, fetches, resets, checks out, cleans, updates, or otherwise modifies submodules. Do not start Space implementation on an unready result; record the findings and resolve the checkout state through the approved Git workflow first.
