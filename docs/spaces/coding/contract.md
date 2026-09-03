# Coding V1 offline CodeJob contract

`coding` is the sole persisted Space identity for this contract family. It is
an offline data contract and semantic validator; it does not start, cancel,
resume, run, or integrate a Coding Engine, OpenFang, provider, model, network,
database, worktree, branch, pull request, or deployment.

The exact Draft 2020-12 bundle contains five closed documents:

1. `CodeJobRequestV1` (`code-job-request`) records opaque project, task,
   trace, repository, and base references; the objective/change kind; requested
   outputs; risk class; resolved clarification; finite execution, cost,
   changed-file, artifact, and test-profile limits; and quote, approval, and
   idempotency continuity.
2. `CodeJobPlanV1` (`code-job-plan`) fixes a positive version and SHA-256 hash,
   an ordered acyclic phase/task DAG, exact capabilities, declared artifact
   kinds, approved opaque test-profile references, success criteria, and the
   immutable request bounds. Test profiles are references, never shell commands.
   Declared tasks, distinct/required test profiles, and required artifact kinds
   must each fit their respective immutable bounds; every required artifact kind
   must be emitted by a declared task. Requested outputs are binding: change
   sets, review records, and generic artifacts require their matching artifact
   kind, while test evidence requires an approved test profile.
3. `CodeJobRunRequestV1` (`code-job-run-request`) fixes exact request/plan
   identity, accepts only `dry_run` or `manual` mode, opaque input artifacts,
   bounded approved limits, and an optional opaque resume checkpoint.
4. `CodeJobRunStateV1` (`code-job-run-state`) records a revisioned,
   timezone-aware lifecycle. It supports `queued`, `waiting_for_approval`,
   `running`, `paused`, `cancelled`, `failed`, `unavailable`, and `succeeded`.
   Terminal states cannot reopen; pauses need checkpoints, resume must use the
   preceding checkpoint, and cancellation needs a cancellation reference. An
   initial resume carries its immutable checkpoint on the first `running` event;
   in-run resume carries the immediately preceding paused checkpoint. Checkpoints
   are otherwise forbidden.
5. `CodeJobResultV1` (`code-job-result`) records one terminal outcome using
   opaque repository/base/head/branch/commit/PR/worktree/artifact/evidence/log,
   and test-summary references. Its head must resolve to its declared commit.

`validate_code_job_bundle(...)` applies the offline cross-document rules. It
rejects unresolved clarification; ref, version, hash, repository, base,
approval, quote, idempotency, capability, and bound drift; duplicate or unknown
phase/task dependencies; cycles and order errors; lifecycle/time/revision
errors; terminal reopening; invalid resume/cancel chronology; timeout or limit
overruns; result/state mismatch; duplicate artifacts; and a success without
immutable required artifacts, passing test profiles, evidence, logs, or exact
success criteria. Request, clarification, plan, and first queued event are
chronological; any worked terminal result has a preceding running event no later
than its terminal completion, and its result start equals the first `running`
event as a timezone-aware instant. Pause/resume never resets that start, so the
timeout covers the full worked interval, including pauses. Requested outputs are
checked again against successful result artifacts, evidence, and test summaries.
Comparisons use timezone-aware instants.

Every object is closed. Provider/model/credential/runtime/URL/endpoint/webhook,
raw command/shell/prompt/code/patch/diff, `ok`, and mock fields are not part of
the contract. Failed and unavailable outcomes require a redacted error class;
success cannot be inferred from an `ok` field or a mock and requires the
declared evidence instead.
