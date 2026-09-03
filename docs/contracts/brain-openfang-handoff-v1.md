# BrainOpenFangHandoffV1

## Purpose and authority

`BrainOpenFangHandoffV1` is Brain's closed, provider-neutral control-plane
record for handing one admitted cognitive plan node to OpenFang after the
associated `BrainPlanLifecycleV1` has reached `execution_deferred`. It is a
Draft 2020-12 data contract, validated entirely offline.

Brain remains the planning, routing, and Truth authority for the admitted
plan. The handoff preserves only the identifiers and declarative constraints
that OpenFang must resolve later: `correlation_id`, `plan_id`, lifecycle
revision, the selected Brain task node, canonical Space, its exact roles and
`required_agent_count`, opaque `approval_ref` and `cost_ref`, and a closed
bounded retry declaration. OpenFang alone may later select agents, tools, and
providers within its separately established execution authority.

The normative source for this closure remains the Outer repository at
`f0001e40f306745f60818a5bbd3065377dacd443`. The precisely pinned
`vibemind_shared.contracts` package is only its importable, offline runtime
representation: its five bundled schemas and manifest are parity-checked
against that normative source. The package does not replace, extend, or
independently govern the Outer contracts.

Every handoff explicitly declares `execution_mode: cognitive` and
`execution_boundary: openfang`. These closed values preserve the admitted
cognitive/OpenFang boundary in the data contract; they neither identify an
agent, tool, URL, provider, nor begin runtime execution.

## Closed handoff shape

The handoff has no extension fields. `retry.classification` is either `none`
with exactly one attempt or `transient` with two or three attempts. This
describes a bounded classification; it neither performs a retry nor converts a
permanent, invalid, denied, or unavailable condition into a fallback.

`approval_ref` and `cost_ref` are opaque continuity values. Their presence
does not establish an approval, authorization, cost quote, billing event, or
spend.

## Bundle validation

Use:

```python
validate_brain_openfang_handoff_bundle(
    channel_intent,
    brain_plan,
    space_execution_contracts,
    lifecycle,
    handoff,
)
```

The validator calls `validate_brain_plan_lifecycle_bundle(...)` first. Only if
that existing admission and lifecycle chain validates does it check that the
lifecycle is `execution_deferred` and that the handoff exactly preserves its
correlation ID, plan ID, and revision. It then verifies that the selected task
exists, routes to the selected canonical Space, and that the Space roles are
unchanged from the admitted plan.

## Explicit non-claims

This contract does not implement or authorize an executor, client, bridge,
OpenFang activation, agent spawn, tool/MCP/provider/database/Application
access, direct route, fallback, deployment, runtime availability, approval,
cost outcome, execution, evidence acceptance, or success. Validation is not a
runtime call and does not establish any Golden Path claim.

In particular, package validation does not create a productive Brain consumer,
call OpenFang, select an MCP route, decide approval or cost, establish runtime
reachability, deploy anything, or prove a Golden Path.
