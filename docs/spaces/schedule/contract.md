# Schedule V1 contract family

Schedule V1 is a provider-neutral, versioned offline contract family. It
describes a scheduling request, its normalized definition, a declarative
change request, a revisioned lifecycle snapshot, and one execution evidence
record. It does not schedule, persist, approve, dispatch, or execute work.

## Documents

- `ScheduleChatBoundaryV1` is the closed, provider-neutral chat envelope for
  `create`, `list`, `modify`, `cancel`, `snooze`, and `status`. It binds only
  opaque Schedule request, intent, and trace references; an optional or
  operation-required exclusive schedule/task selector; and operation-specific
  declarative preconditions. Mutation approval, idempotency, and revision
  fields express correlation and preconditions only. They do not establish
  approval authority, persistence, registration, or execution.
- `ScheduleRequestV1` accepts a chat or Brain-originated appointment/reminder
  wish. It carries opaque `task_brief_ref` and `intent_ref`, a trace,
  timezone, clarification state, idempotency key, and bounded hard limits.
- `ScheduleDefinitionV1` normalizes exactly one trigger: `one_shot` with
  `run_at`, `interval` with a timezone-aware `starts_at` and `every_seconds`,
  or `cron` with a five-field expression and its explicit timezone. It
  contains opaque request/task/trace references, revision, idempotency key,
  bounded run/retry policy, and an approved cost envelope.
- `ScheduleChangeV1` is a declarative `create`, `update`, `pause`, `resume`,
  `cancel`, or `run_now` request. Every one requires `approval_ref`,
  `expected_revision`, and an idempotency key. It intentionally has no
  read/list/preview/get action and no direct executor, provider, command,
  endpoint, credential, runtime, or database field.
- `ScheduleStateV1` records one revisioned state with transition history,
  timezone-aware next/last run timestamps, and bounded counters. `cancelled`,
  `succeeded`, `failed`, and `unavailable` are terminal; the final state is
  always the last history event.
- `ScheduleRunEvidenceV1` records one completed attempt and its
  `scheduled_for`, `started_at`, `completed_at`, outcome, opaque evidence and
  artifact references, plus deterministic integer minor-unit cost. A success
  needs evidence and artifact references. `failed` and `unavailable` need an
  enum-only redacted error classification, never a free error payload.

## Offline validation

`ScheduleChatBoundaryV1` is an additive offline boundary validated directly
with JSON Schema Draft 2020-12 in its focused contract test. It is deliberately
not registered in `shared/contracts/validate.py`; the existing Schedule schemas
and `validate_schedule_bundle` remain unchanged. Schema validation therefore
does not prove scheduler, calendar/reminder mutation, provider/channel delivery,
database or recurrence execution, Brain/Application routing, cost or approval
authority, runtime/deployment, OpenFang execution, or a Golden Path.

Use `validate_document(...)` for one document or
`validate_schedule_bundle(...)` for the exact five-document chain. Bundle
validation rejects reference, revision, idempotency, clarification, policy,
counter, outcome, and cost drift. Approval references are opaque correlation
only; validation does not claim approval authority.

The exact five-document bundle is an execution-evidence chain, not a generic
change snapshot: its `ScheduleChangeV1` must be `run_now`, the penultimate
state event must be `running`, and the final event must project the included
run outcome. `create`, `update`, `pause`, `resume`, and `cancel` remain valid
single declarative change documents, but cannot be presented as a complete
run-evidence bundle. A bundle fails closed while either the request or
definition requires clarification.

For `succeeded` recurrence evidence, a state with `run_count < max_runs`
returns from `running` to `scheduled` and must contain a timezone-aware,
non-null `next_run_at`; only the final permitted success is terminal
`succeeded`. Terminal `succeeded`, `failed`, `cancelled`, and `unavailable`
states require `next_run_at: null`. In every execution bundle, `last_run_at`
equals the evidence `completed_at`. For one-shot definitions,
`scheduled_for` equals `run_at` after timezone-aware instant normalization.

All timestamps must be RFC3339 with an explicit offset or `Z`. `UTC` and
non-empty IANA-shaped identifiers such as `Europe/Berlin` are accepted. This
offline contract does not contain a timezone database. A local wall time that
is ambiguous or nonexistent at a DST boundary must stay
`clarification.required: true` in the request and
`clarification_required: true` in the definition until an upstream resolver
has normalized it explicitly; it must never be silently guessed.

## Safe V1 caps

The schemas reject zero, negative, null, or unbounded values. The deliberately
small portable caps are: 1,000 runs, 10 retries, retry delay 1–86,400 seconds,
interval 60–2,592,000 seconds (30 days), 128 lifecycle events, 20 evidence or
artifact references, and a maximum approved/result cost of 10,000,000 minor
units. Costs are integers only and result currency, quote, and approval refs
must equal the definition envelope.

The cron grammar is deliberately structural: exactly five non-whitespace
fields plus an explicit timezone. Recurring schedules do not claim a full
cron/TZ next-run calculation; the interval anchor merely makes their intended
sequence deterministic for a later authoritative scheduler.

## Non-claims and ownership

This is structural, deterministic, and offline-only validation. It offers no
provider capability, scheduler runtime, persistence, approval decision,
OpenFang/Voice/Brain adapter, network request, database mutation, or Golden
Path/live-execution evidence. A later authoritative lifecycle owner may use
the contracts only after its own approval, provider, persistence, and evidence
gates are independently implemented and verified.
