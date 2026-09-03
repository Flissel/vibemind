# Proxmox cutover and rollback operations boundary

## Scope and boundaries

This is a versioned, static decision boundary for a possible later transition
between a defined source boundary and target boundary. It intentionally names
no current endpoint, database, machine, container, service, or provider as
the operational target.

This document does not perform or prove a runtime operation. It does not
perform a cutover, rollback, deployment, database action, routing change,
consumer change, network action, or provider action. `deployment_proven=false`
and `golden_path_proven=false` remain true in every state described here.

## Preconditions

No transition proceeds from this static artifact alone. A separately approved
request must document:

- the source boundary, target boundary, and the data authority expected during
  each proposed phase;
- a current consumer inventory and an explicit change freeze for every affected
  consumer class;
- the backup reference and the separately recorded static readiness result;
- the applicable migration or audit result, including unresolved findings;
- a separately approved maintenance window and a named decision owner.

Missing, stale, ambiguous, or historical-only evidence blocks the proposal.
Static readiness is a prerequisite inventory, not proof of a transition.

## Consumer and data-authority controls

No direct database fallback is permitted. No silent dual-write is permitted.
Consumer behavior must follow the separately approved data-authority decision;
an unavailable target or transport error is not permission to write directly to
another data store or to introduce an undeclared parallel path.

Later live gates, if separately authorized, require an independent readback and a consumer divergence comparison against the approved source/target expectation. These are distinct evidence stages. Transport or health success is not cutover success, and neither status alone proves consumer convergence, data integrity, or a completed transition.

## Rollback triggers and decision control

Rollback triggers include a stop criterion, unresolved consumer divergence,
unavailable independent readback, data-integrity concern, or a decision-owner
instruction. The decision owner decides whether a separately authorized
rollback proposal may proceed; this static document does not execute or
simulate it.

Until an explicitly approved conclusion is independently evidenced, preserve the prior data basis and all evidence references. Do not destroy, overwrite, or silently decommission the prior data basis as a consequence of transport, health, or partial consumer observations.
