# AgentFarm Chat/Application Boundary V2

## Status and scope

This is a binding **future-boundary specification**, not a runtime interface or
deployment record. It defines how a Channel or Space chat is to request and
observe AgentFarm work once an implementation is approved. It adds no endpoint,
provider, credential, database schema, runtime, or application integration.

The current committed authority is the offline AgentFarm team-contract family in
`shared/contracts/agentfarm/v1/` and its bundle validator. That contract carries
the plan, run, task-event, state, and terminal-evidence identities and bounds.
It validates documents offline; it does not select or activate a runtime.

## Required chain

Every future chat operation follows this one directional chain:

```text
Channel / Space-Chat
  -> Brain
  -> OpenFang Execution Adapter
  -> OpenFang space-agentfarm-chat
  -> Application
  -> evidence/result
  -> Brain / Minibook projection
```

`space-agentfarm-chat` is the only AgentFarm application-facing boundary in this
chain and runs under OpenFang. The OpenFang Execution Adapter may dispatch only
to that boundary after Brain has completed routing and OpenFang has validated
the applicable approval, permission, provider, and cost policy. Brain remains
the control-plane authority; Minibook receives projections only and never
becomes a control or execution authority.

There is no permitted direct fallback from Channel, Space-Chat, Brain, the
Execution Adapter, or Minibook to an Application API, database, queue, or
provider. A missing or unavailable boundary is reported as unavailable; it is
not replaced by a direct application or DB operation.

## Operations

The future boundary supports only these operation names:

| Operation | Required boundary behaviour |
| --- | --- |
| `plan` | Brain validates the chat intent, resolves the canonical `agentfarm` space, and creates or projects a bounded plan. If clarification or policy is unresolved, it returns that state without dispatch. |
| `status` | Returns the latest available state projection for the correlated plan/run. It must not infer progress from a missing runtime response. |
| `cancel` | Records a cancellation request through Brain and the adapter for the identified run. A request acknowledgement is not terminal cancellation; the projection waits for the corresponding terminal state/evidence. |
| `resume` | Re-enters an existing, correlated plan/run only after Brain validates its lifecycle, immutable plan identity, bounds, and current authority. It never resumes by issuing a direct Application or DB command. |
| `result` | Returns a terminal result projection only when terminal Application evidence is available. Missing evidence, unavailable execution, and timeouts are surfaced as such, never as success. |

No other operation name is implied by this document. Transport, endpoint, and
provider details remain unspecified until a separately approved implementation
contract defines them.

## Correlation and continuity

The Channel/Space-Chat ingress creates or receives a `correlation_id` and
preserves it across every hop and every projection. It is a boundary-correlation
value; it does not replace the versioned contract identities.

| Identifier | Continuity requirement |
| --- | --- |
| `correlation_id` | Links one chat intent, all operation attempts, and their projections end-to-end. |
| `request_id` | Identifies the AgentFarm request accepted by the offline contract. |
| `plan_id` | Identifies the immutable planned work and remains stable for its plan version/hash. |
| `run_id` | Identifies a concrete execution attempt; it is required for run-scoped status, cancel, resume, and result. |
| `trace_id` | Preserves observability continuity across Brain, adapter, boundary, Application, and returned projections. |

The adapter and `space-agentfarm-chat` must reject a request whose supplied
identities cannot be correlated consistently. They must not manufacture a
replacement plan, run, or terminal result.

## Clarification, authority, cost, and deadline gates

Before dispatch, Brain and OpenFang apply these fail-closed gates at their
respective authority boundaries:

- A request with unresolved clarification is returned as clarification-required;
  the adapter does not dispatch it.
- Brain requires an executable request/run to retain its approval and cost
  references (`approval_ref`, `quote_ref`) and its declared cost currency and
  bound. OpenFang validates their runtime authority before execution. Missing,
  mismatched, expired, or otherwise unvalidated authority/cost material blocks
  execution rather than being inferred or substituted.
- The declared timeout and all other hard bounds flow through the chain unchanged.
  A deadline expiry becomes a non-success terminal outcome with its correlated
  evidence/error classification; it does not trigger a retry through a direct
  Application, DB, or provider path.
- A disabled, missing, malformed, unreachable, or unverified boundary returns
  `unavailable` (or another explicit non-success state). No layer may reinterpret
  it as queued, running, or succeeded.

Schema validation is necessary only for contract shape and bundle semantics. It
does not prove that an approval has authority, that a cost is charged or allowed,
or that an Application, provider, database, or runtime executed work.

## Task, log, artifact, and evidence projections

Application-facing data returns to Brain only as correlated projections:

- **Task projection:** task state and member/task summaries tied to the plan and
  run; no fabricated aggregate progress.
- **Log projection:** opaque log references, not secret-bearing log content;
  absent logs remain absent rather than being reconstructed.
- **Artifact projection:** artifact references associated with the exact plan and
  run; a reference is not evidence that an artifact was consumed successfully.
- **Evidence projection:** terminal evidence references, outcome, and applicable
  error classification. A successful result requires the terminal evidence that
  the committed offline contract requires, including non-empty evidence, artifact,
  and log references.

Brain projects these records to Channel/Space-Chat and Minibook without making
either projection layer authoritative. Terminal Application readback/evidence is
the future success condition; an HTTP acknowledgement, adapter dispatch, queue
entry, static registry, mock, or historical record is not.

## Current state and required dependency

The following observations are strictly static or historical, not runtime proof:

- The offline Team Contract exists and is covered by committed contract tests.
- The top-level `vibemind.config.json` currently declares the `agentfarm` module
  disabled. Its recorded disabled reason names a missing AutoGen server build
  source path; this is static configuration evidence only.
- The configuration contains AgentFarm port values while the module is disabled.
  Any port drift inferred from configuration or earlier records is historical or
  static evidence only, not a reachable service claim.

No AgentFarm runtime connection, Application readback, deployment, or Golden Path
is established by this specification or by the offline contract tests.

OpenFang is a required MVP dependency for this boundary and appears in the
required chain above. This specification does not by itself implement or prove
an OpenFang route, agent, endpoint, approval, cost decision, or live execution.
Those capabilities require separately approved implementation tasks while
retaining the no-direct-fallback rule and the same evidence requirements.

## Authority sources

This document is constrained by:

1. `docs/spaces/agentfarm/contract.md` for the existing offline-contract boundary.
2. `shared/contracts/agentfarm/v1/` for the versioned identities, lifecycle,
   bounds, approval/cost references, and evidence requirements.
3. `vibemind.config.json` for the static disabled-module and historical
   build-path/port observations.

It intentionally makes no claim beyond those committed sources.
