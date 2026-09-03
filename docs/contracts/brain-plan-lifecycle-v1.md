# BrainPlanLifecycleV1

## Purpose and authority

`BrainPlanLifecycleV1` is Brain's persisted, provider-neutral planning view
from an existing plan through the explicit `execution_deferred` control-plane
boundary. It is a closed Draft 2020-12 data contract and is validated entirely
offline. OpenFang execution is part of the current MVP, but is intentionally
represented by a separate execution lifecycle rather than added to this
planning-only state machine.

Brain owns the planning-state decisions. Shared owns the schema and
deterministic validation. Space targets and declarative evidence requirements
remain authoritative in the admitted `BrainPlanV1`; this lifecycle records
only their canonical participating-Space projection and never reinterprets
tasks, evidence, agents, applications, providers, or runtime behavior.

## Closed data shape

The root records `correlation_id`, `plan_id`, ordered
`participating_space_ids`, current `revision`, current planning `status`,
`updated_at`, and an append-only `event_history`. Root and event objects reject
unknown properties.

The only statuses are:

- `planned`
- `awaiting_clarification`
- `admitted`
- `execution_deferred`
- `cancelled`

Events use closed reason codes where a reason is required:
`clarification-required`, `admission-validated`,
`execution-engine-deferred`, `user-cancelled`, `policy-cancelled`, or
`clarification-unresolved`. Free-form lifecycle reasons are intentionally not
accepted because they could carry provider or secret-bearing text.

## State machine

Every history begins at revision 1 in `planned`. Revisions are contiguous,
timestamps are timezone-aware and monotonically non-decreasing, and the root
revision, status, and timestamp exactly equal the final event.

Allowed transitions are:

```text
planned -> awaiting_clarification | admitted | cancelled
awaiting_clarification -> planned | cancelled
admitted -> execution_deferred | cancelled
execution_deferred -> terminal
cancelled -> terminal
```

Terminal states cannot be reopened. Runtime states such as `queued`,
`dispatched`, `running`, `succeeded`, and `failed` are not planning statuses
and are rejected.

## Offline bundle validation

`validate_brain_plan_lifecycle_bundle(channel_intent, brain_plan,
space_execution_contracts, lifecycle)` first delegates to
`validate_brain_plan_admission_bundle(...)`. It does not duplicate or weaken
admission. Only after that succeeds does it validate the lifecycle and require:

- exact `correlation_id` continuity with `ChannelIntentV1`;
- exact `plan_id` continuity with `BrainPlanV1`; and
- exact ordered canonical participating-Space continuity with the admitted
  plan.

Thus an `admitted` event is accepted by the bundle only after the existing
offline admission validator succeeds. Standalone schema validation does not
establish admission authority.

## Explicit non-claims

`execution_deferred` means only that this planning contract reached its
execution handoff boundary. It is never dispatch, execution, fallback, Application routing,
approval, evidence acceptance, completion, or success evidence. Neither schema
validation nor bundle validation invokes a provider, runtime, agent, tool,
command, URL, credential, database, network, workflow, or Application. A
successful validation proves only internal offline contract consistency; it
does not prove a Golden Path or any live result.

Run the focused checks from the repository root:

```powershell
python -m pytest tests/contracts/brain/test_brain_plan_lifecycle_contracts.py -q
```
