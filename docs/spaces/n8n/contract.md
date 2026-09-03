# n8n V1 contract family

n8n V1 is a provider-neutral, versioned, offline contract family. It records
an intended workflow lifecycle and one bounded execution-evidence chain. It
does not contact n8n, construct a workflow, call an API, store credentials,
or claim approval, dispatch, persistence, or live execution authority.

## Space shape (informative)

`n8n` is a canonical routing identity in
`vibemind-os/config/space_agent_registry.yml`, where eight `n8n.*` events are
bound directly to MCP tools under `mcp_servers: [vibemind-db, n8n]`. It is a
registry-routed MCP tool surface addressed through `brain-n8n`, and it is
**not a Space application**: no `spaces/n8n` source root exists in this
repository or in `vibemind-os` at the pinned revision, and no Space-owned data
store belongs to it. Integration code and Compose definitions are owned by the
`voice` component; the `space-n8n` Compose profile starts only the third-party
n8n engine. See [`SPACES.md#n8n`](../../SPACES.md#n8n). This note describes
declaration shape only and changes no event, tool binding or contract below.

## Documents

- `WorkflowRequestV1` accepts a Brain or chat intent through opaque intent,
  task, project, and trace references. It records clarification state, risk
  class, and finite hard caps.
- `WorkflowDefinitionRefV1` is an immutable reference to one positive
  workflow version and definition revision. It contains only an artifact
  reference, evidence references, an exact lowercase SHA-256 digest, a
  declared abstract trigger class, capability references, lifecycle, and an
  opaque approval correlation reference. It never embeds workflow JSON,
  provider details, credentials, URLs, code, or configuration.
- `WorkflowChangeV1` is declarative: `create`, `update`, `activate`,
  `deactivate`, or `archive`. It requires an expected lifecycle, expected
  revision, idempotency key, and approval reference. `create` expects
  `absent` at revision zero; `update` accepts only `draft`, `active`, or
  `inactive`; `activate` only `draft` or `inactive`; `deactivate` only
  `active`; and `archive` only `draft`, `active`, or `inactive`. `archived`
  is never an expected lifecycle, so it cannot be reactivated, changed, or
  archived again. Delete is not an action.
- `WorkflowRunRequestV1` declares test, manual, or production mode plus
  immutable workflow identity, opaque input artifact/evidence references,
  finite timeout/step/retry/cost caps, quote, approval, and idempotency refs.
- `WorkflowRunStateV1` projects the revisioned lifecycle
  `clarification_required`, `queued`, `waiting_for_approval`, `running`,
  `succeeded`, `failed`, `cancelled`, or `unavailable`. Its event history is
  monotonic, revisions are consecutive, begins with `queued` or
  `clarification_required`, and terminal states never reopen. Its
  `cancellation_requested` flag is true exactly for `cancelled`, so a success,
  failure, or unavailable result cannot retain a cancellation request.
- `WorkflowRunEvidenceV1` carries one terminal outcome, aware start and
  completion timestamps, executed-step count, opaque evidence/artifact/log
  references, optional enum-only redacted error class, and integer minor-unit
  actual cost.
- `N8nOperationAuthorityV1` is a separate closed, offline record for exactly
  one `read-status`, `trigger`, or `cancel` operation. It binds the durable
  `WorkflowRunRequestV1` identity to opaque authority and approval references,
  an issued/expiry window, and an idempotency key. `read-status` is
  non-mutating; `trigger` and `cancel` require the same authority, approval,
  expiry, and idempotency fields as every valid authority record.

## Offline bundle validation

`validate_n8n_bundle(...)` accepts exactly the six document types above. It
requires resolved clarification, an active definition produced by an
`activate` change, and a resulting definition revision exactly one above the
change's expected revision. All request, workflow, definition, task, project,
trace, version, hash, mode, idempotency, approval, quote, cap, counter, and
result references must remain consistent across the chain.

The resolved-clarification execution chain must begin `queued`, and evidence
start may not precede its first state event. Its final state event and the
evidence completion timestamp must denote the same aware instant, even when
their offsets differ. For succeeded, failed, and
unavailable evidence, the immediately preceding state event must be `running`
and cannot occur after evidence start. The same rule applies to a cancelled
run that executed one or more steps; a queued or waiting cancellation with
zero steps remains valid without a fabricated running event.

The bundle rejects an unbounded or over-hard-bound run request. Timeouts are
1–3,600 seconds, steps 1–500, retries 0–10, and every cost is a non-negative
integer minor-unit amount capped at 10,000,000. The evidence actual cost may
not exceed the approved run maximum. A successful outcome needs non-empty
evidence, artifact, and log refs and at least one executed step; `failed` and
`unavailable` require a redacted enum error class. State and evidence must
have identical terminal outcome, result references, step count, and cost
envelope. Approval references are opaque correlation only and never prove
authority.

Each object is closed. Thus provider, credential, secret, token, API-key,
runtime, URL, webhook, endpoint, command, shell, database, connection,
inline-workflow, and code fields are rejected rather than carried through an
offline contract.

`validate_n8n_operation_authority(authority, workflow_run_request)` performs
only deterministic local validation. It compares the copied run, definition,
workflow, request, task, project, trace, mode, idempotency, and approval
references with the existing `WorkflowRunRequestV1`, rejects any drift, and
requires `expires_at` to be after `issued_at`. It does not compare either
timestamp with a wall clock, so expiry is not provider-live evidence. The
operation authority is deliberately outside `validate_n8n_bundle(...)`; it
does not alter the six-document execution-evidence chain.

## Non-claims and ownership

This contract family is structural validation only. It is not an n8n adapter,
workflow generator, credential store, MCP client, webhook receiver, database
writer, deployment, OpenFang integration, or Golden Path. A separate,
explicitly approved lifecycle owner must independently implement provider,
approval, persistence, and live-evidence gates before any real workflow
operation can be claimed. VibeMind remains the sole n8n lifecycle, workflow,
credential, runtime, and volume authority; this record grants no capability
and performs no action.
