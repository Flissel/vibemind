# Rowboat V1 offline knowledge contract

`rowboat` is the sole persisted Space identity for this contract family.
`roarboot` may appear only as the optional `ingress_alias` on a knowledge
request; it is never accepted as `space_id` and is never carried forward into
the plan, run, state, or result.

The exact Draft 2020-12 bundle contains five closed documents:

1. `RowboatKnowledgeRequestV1` (`knowledge-request`) records a clarified
   objective/query, opaque project/task/trace references, requested output,
   source policy, finite hard bounds, quote/approval correlation, and
   idempotency continuity.
2. `RowboatKnowledgePlanV1` (`knowledge-plan`) fixes a positive version and
   SHA-256 hash, ordered acyclic retrieval/composition stages, declared opaque
   sources, citation/evidence requirement, and output artifact reference. Each
   retrieval stage names at least one source, every declared source is retrieved,
   and every composition stage has a transitive dependency on retrieval.
3. `RowboatKnowledgeRunRequestV1` (`knowledge-run-request`) fixes the exact
   request/plan identity, opaque input artifact/evidence references, and a
   bounded offline execution envelope.
4. `RowboatKnowledgeRunStateV1` (`knowledge-run-state`) records a revisioned,
   monotonic lifecycle beginning at `queued`, counters, cost, and symmetric
   cancellation state. Terminal states have zero active stages.
5. `RowboatKnowledgeResultV1` (`knowledge-result`) records one terminal
   outcome with opaque source, citation, artifact, evidence, and log
   references. A success must carry the declared output artifact and sufficient
   source-grounded citations; failed and unavailable results need a redacted
   error class, while a successful result cannot carry one.

`validate_rowboat_bundle(...)` applies offline cross-document consistency. It
rejects unresolved executable requests; alias persistence; source/stage
duplicates, unknown dependencies, invalid order, and cycles; plan/hash/ref
drift; overrun limits; invalid timestamps/lifecycle/cancellation; citation or
source-evidence mismatch; duplicate source/citation identities; and terminal
success without required source, citation, artifact, evidence, or log truth.
Clarification resolution, immutable-plan creation, and the queued lifecycle are
chronological; a terminal result cannot exceed its run timeout. Result source
count is bounded by examined and immutable-plan sources. Timestamp comparisons
use timezone-aware instants, not lexical strings.

Every object is closed. Provider, model, credentials, secrets, runtime, raw
URLs/endpoints, commands, prompts, code, and other application-execution data
are rejected. URLs are intentionally absent: sources, citations, artifacts,
evidence, and logs use opaque versioned references only.

This is an offline contract and semantic validator, not Rowboat runtime,
OpenFang, provider, network, database, service, deployment, or approval
implementation. It does not claim retrieval, composition, persistence, or
live execution behavior.
