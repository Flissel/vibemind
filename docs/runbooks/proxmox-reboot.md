# Proxmox reboot operations boundary

## Scope and boundaries

This is a versioned, static review artifact for a later reboot decision affecting
the Proxmox host class, managed virtual-machine class, and the application
workloads hosted by those classes. It intentionally names no current target,
address, container, volume, or runtime instance.

This document does not perform or prove a runtime operation. It neither
authorizes nor performs a reboot, shutdown, start, deployment, snapshot,
backup, restore, network action, database action, or provider action.
`deployment_proven=false` and `golden_path_proven=false` remain true in every
state described here.

## Authority and decision boundary

A reboot is a request-specific authority action. Standing documentation or
static-readiness approval is not authority to execute it. The approved request
must identify the decision owner, target-system class, maintenance window,
operator, and escalation contact before any operational work is considered.

## Preconditions and stop criteria

Record these references before the request can progress beyond planning:

- a current inventory for the affected system classes and their consumers;
- a backup or snapshot reference with its origin, timestamp, and retention
  decision recorded independently;
- the separately approved maintenance window and an explicit change freeze for
  affected consumers;
- known dependencies, health expectations, and the responsible decision owner;
- stop criteria, including a missing inventory, missing backup or snapshot
  reference, any unexpected dependency, or an unavailable decision owner.

Meeting static prerequisites is not a go signal. If any prerequisite is absent,
ambiguous, or cannot be independently recorded, stop and escalate; do not
substitute an assumed target or a historical report.

## Evidence stages

Health and reachability evidence is a narrow transport observation only. It is
not operational verification, authenticated service validation, data-integrity
evidence, or proof that a workload restarted correctly.

Operational verification, when separately authorized, must be recorded as a
distinct later stage against the approved inventory. An independent readback by
the designated evidence owner is another distinct later stage; it must not be
replaced by operator assertion, transport success, or a dashboard screenshot.

## Restart escalation boundary

The restart escalation boundary applies if an approved workload does not return
to its declared expected state, an independent readback is unavailable, or a
stop criterion occurs. Stop further changes, preserve the available evidence
and prior data basis, notify the decision owner, and obtain a new explicit
decision. This runbook does not prescribe or simulate a rollback.
