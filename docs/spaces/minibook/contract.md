# Minibook V1 offline projection contract

`minibook` is the sole persisted Space identity for this contract family. It
is a deterministic, offline read model for internal display. It neither owns
nor changes Brain lifecycle state, Shared contracts, execution, approvals,
costs, providers, databases, APIs, runtimes, credentials, prompts, or code.

The exact Draft 2020-12 bundle contains four closed documents:

1. `MinibookProjectionRequestV1` (`minibook-projection-request`) fixes opaque
   project, task, and trace references; requested display views and filters;
   an as-of cursor and source-ledger reference; finite row/event bounds; and
   a hash. `read_only` is always `true`. Quote, approval, and idempotency
   references are provenance only: this request cannot contain an approval
   decision or action.
2. `MinibookProjectionSnapshotV1` (`minibook-projection-snapshot`) is an
   immutable projection version/hash at one source cursor. Ordered project and
   task rows carry copied lifecycle status plus an `authority_ref`, references
   to briefs, todos, sessions, approvals, cost provenance, logs, PRs, results,
   handoffs, and source evidence. They are references, not Minibook-owned
   records or decisions.
3. `MinibookProjectionDeltaV1` (`minibook-projection-delta`) appends one or
   more ordered projections of source events between strictly advancing
   cursors. Each source revision is greater than `from_cursor`, no greater than
   `to_cursor`, strictly increasing, and the final revision equals
   `to_cursor`. Each event retains its source event reference, its exact
   project/task snapshot-row pair, and a row hash. It has no lifecycle command.
4. `MinibookProjectionEvidenceV1` (`minibook-projection-evidence`) ties the
   snapshot and delta references/cursors to source evidence and log references,
   exact row counts, cost-provenance references, generation/completion times,
   and stale/completeness markers.

Selected project/task identities are the nonempty matching filter set, or the
request set when that filter is empty. Snapshot rows are always subsets of
those selected sets. An incomplete snapshot may be partial; a complete snapshot
must exactly cover every selected project and task row.

The evidence document uses exact provenance closure: its source-evidence,
source-log, and cost-provenance reference sets exactly equal the respective
unions in task rows. Every cost-provenance reference must also appear in source
evidence. This deliberately rejects both omitted and foreign aggregate refs.

`validate_minibook_projection_bundle(...)` rejects non-canonical space IDs or
read/write drift; request/snapshot/delta/evidence reference, hash, cursor, and
time discontinuity; duplicate projects, tasks, or source events; noncontiguous
task or event order; undeclared or cyclic parent/dependency references;
out-of-interval or non-monotonic source revisions; project/task event-pair
drift; unbounded row/event counts; approval provenance outside the request
chain; incomplete provenance closure; and stale or incomplete data claiming
completion. Copied `succeeded` task rows require source evidence and log
references.

All schemas use `additionalProperties: false`. Consequently, lifecycle or
approval authority and raw mutation/execution fields such as command, execute,
approve, reject, retry, cancel, status update, database, SQL, provider, model,
credential, runtime, URL, prompt, and code are rejected. A `2xx`, mock,
registry entry, or status-only record does not establish a live projection or
Golden Path. This contract intentionally provides no Minibook runtime, API,
submodule, UI, database, or deployment implementation.
