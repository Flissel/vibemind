# Desktop V1 offline action contract

`desktop` is the sole persisted Space identity for this contract family. This
is an offline data contract and semantic validator. It does not activate or
operate Desktop automation, browsers, OpenClaw, OpenFang, applications, input
devices, networks, databases, deployments, or providers.

The exact Draft 2020-12 bundle contains five closed documents:

1. `DesktopActionRequestV1` (`desktop-action-request`) records opaque project,
   task, trace, target/application/window references; an objective; action,
   risk, and mutation classes; resolved clarification; hard limits; a request hash; and
   quote, approval, and idempotency continuity. It carries neither a URL,
   selector, text to type, command, prompt, code, coordinates, keystrokes,
   payload, credential, nor secret.
2. `DesktopActionPlanV1` (`desktop-action-plan`) is immutable: it fixes a
   positive version, SHA-256 plan hash, request and parameter hashes, exact
   bounds, and a contiguous ordered acyclic action DAG. Actions name opaque
   capability profiles, target references, preconditions, postconditions,
   evidence requirements, stop conditions, and parameter digests. `observe`
   is read-only; `input` and `application_control` are explicit mutations;
   the requested action class must appear in the plan.
3. `DesktopActionRunRequestV1` (`desktop-action-run-request`) fixes the exact
   request and plan chain and allows only `dry_run` or `manual`. Mutating work
   requires both a confirmation reference and an exactly matching confirmed
   parameter digest; read-only work may not carry either. Its limits cannot
   exceed the requested hard bounds.
4. `DesktopActionRunStateV1` (`desktop-action-run-state`) is a revisioned,
   timezone-aware lifecycle: `queued`, `waiting_for_confirmation`,
   `waiting_for_approval`, `running`, `paused`, `succeeded`, `failed`,
   `cancelled`, or `unavailable`. Transitions are monotonic and terminal states
   cannot reopen. A mutating run must pass `waiting_for_confirmation` and then
   `waiting_for_approval` before its first `running` event; read-only runs may
   not enter the confirmation state. Pauses and matching resumes retain the same opaque pause
   reference; cancellation requires a cancellation reference; terminal states
   have `active_actions: 0`. Failed and unavailable states require a redacted
   error class.
5. `DesktopActionResultV1` (`desktop-action-result`) records the exact terminal
   result with continuous target/application/window refs, visible evidence,
   artifact/evidence/log refs, counters, costs, and external verification. A
   mutating success needs a matching confirmation digest, before and after
   distinct before/after screenshots, externally verifiable evidence, and non-empty artifact,
   evidence, and log references. An observe success needs truth evidence plus a
   before or current screenshot. Failed and unavailable results require a
   redacted error class. Terminal counters exactly equal their evidence: artifact
   count equals artifact refs and screenshot count equals distinct non-null visual refs.

`validate_desktop_bundle(...)` rejects alias/space drift, unresolved or
chronologically invalid clarification, duplicate/unknown/unordered/cyclic
actions, action/mutation mismatches, hash/digest/reference drift, confirmation
or approval continuity failures, lifecycle reopening and invalid pause/cancel
chronology, limit overruns, terminal/result mismatches, visual/evidence gaps,
and closed-object raw execution or shortcut fields. Worked results begin at the
first running event and include pauses in their timeout. All comparisons use
timezone-aware instants, including offset-equivalent timestamps.

A transport response, `2xx`, no-op, mock, or status-only record is not success
evidence. This contract intentionally supplies no runtime dispatch path.
