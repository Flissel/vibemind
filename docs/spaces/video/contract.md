# Video V1 offline VideoJob contract

`video` is the sole persisted Space identity for this contract family. The
contract is provider-neutral and validates data offline. It does not invoke a
video engine, voice system, vision service, provider, model, network, database,
Application, deployment, or OpenFang.

The exact bundle contains five closed JSON Schema Draft 2020-12 documents:

1. `VideoJobRequestV1` records opaque request, project, task, trace, quote, and
   approval references; the `video`, `audio`, or `vision` job kind; requested
   media artifacts; resolved clarification; and finite time, cost, artifact,
   byte, duration, retry, concurrency, and step limits.
2. `VideoJobPlanV1` fixes the plan identity, version, SHA-256 hash, ordered
   acyclic steps, provider-neutral capabilities, declared artifacts, success
   criteria, and unchanged request limits.
3. `VideoJobRunRequestV1` binds one dry-run or manual run to the request and
   plan, input artifact references, approved limits, and opaque quote and
   approval references.
4. `VideoJobRunStateV1` records a revisioned, timezone-aware monotonic
   lifecycle and bounded resource counters and cost. Terminal states cannot
   reopen. Failed and unavailable states use only a closed redacted error
   class.
5. `VideoJobResultV1` records the terminal outcome, concrete media artifacts
   with content hashes and sizes, evidence and log references, exact cost and
   counters, and a terminal result reference.

`validate_video_job_bundle(...)` validates the exact chain and rejects identity,
plan version/hash, job kind, approval/quote, limit, lifecycle, result, artifact,
cost, and evidence drift. A success requires a prior running event, exact
terminal timing, every declared media artifact, content hashes, matching byte
and artifact counters, evidence, logs, cost accounting, all declared criteria,
and a terminal result reference. Queue, dispatch, healthcheck, mock, or generic
`ok` fields are not accepted and cannot establish success.

Schema validation only proves structural and cross-document consistency of an
offline bundle. Opaque `quote_ref` and `approval_ref` values do not prove quote
validity, approval authority, provider execution, runtime availability,
Application readback, or a live/Golden Path.

Opaque `evidence_refs` do not prove source content, consent, disclosure, human
review, output integrity, or retention. A policy-specific evidence family for
those claims requires a separate explicit approval.
