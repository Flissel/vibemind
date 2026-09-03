# Observability Evidence Governance V2

## Status and scope

This is a normative, offline architecture contract for evidence classes and
status truth. It classifies statements about evidence; it neither produces nor
accepts evidence, runs a probe, or changes any system state. No current system is `verified_live` under this contract.

This contract adds no schema, validator, runtime persistence, adapter, database, deployment, live probe, Golden Path, or OpenFang behavior.

## Ownership

| Owner | Responsibility in this contract | Not granted by this contract |
| --- | --- | --- |
| Shared | portable schemas and offline validation | lifecycle, acceptance, or runtime authority |
| Brain | task lifecycle and result validation | evidence production or shared schema ownership |
| OpenFang | execution, approvals, costs, and correlated runtime-evidence production | evidence classification or acceptance authority |
| Applications | job execution and evidence production | global lifecycle or acceptance authority |
| Minibook | read-only projection | task mutation, lifecycle, or acceptance authority |

OpenFang is the MVP execution boundary, but its runtime behavior is outside this evidence-classification contract. This contract does not implement OpenFang execution, approvals, permissions, providers, costs, or evidence acceptance.

## Evidence classes

An evidence statement MUST use exactly one of these classes. The classes are
truth qualifiers, not lifecycle states and not acceptance decisions.

| Class | Normative meaning | Does not establish |
| --- | --- | --- |
| `static` | The statement is derived only from committed documents, schemas, tests, or registry snapshots. | reachability, execution, acceptance, or live success |
| `configured` | The required configuration is present in a reviewed configuration source. | that a component started, can be reached, or executed correctly |
| `historical` | The statement records previously observed, timestamped evidence. | present reachability, freshness, or current success |
| `reachable` | A fresh transport or health observation shows that an endpoint or component responded. | operation-specific completion, acceptance, or live success |
| `verified_live` | Fresh, operation-specific, end-to-end evidence demonstrates the declared success condition against the intended live target. | authority to accept evidence or change lifecycle state |

`verified_live` MUST be assigned only when the evidence identifies the intended
operation and live target, is fresh enough for the claim, demonstrates the
operation's declared terminal success condition end to end, and is available
for an explicit owner decision. It requires fresh, operation-specific, end-to-end evidence.
It is not inferred from a response shape, transport observation, registry
comparison, or offline artifact.

## Forbidden equivalences

The following statements are normative and prevent weaker signals from being
reported as live verification:

- Transport success is not `verified_live`.
- Health success is not `verified_live`.
- An HTTP 2xx response is not `verified_live`.
- Mocks are not `verified_live`.
- No-op results are not `verified_live`.
- Queued status is not `verified_live`.
- Registry matches are not `verified_live`.
- Offline-terminal documents are not `verified_live`.

A transport response or health observation may support `reachable`; it cannot
by itself satisfy an operation-specific terminal success condition. A mock,
no-op, queued result, registry match, or offline-terminal document may support
only the class justified by its own provenance and never upgrades another
claim to `verified_live`.

## References, durability, and acceptance

`EvidenceRefV1` is a durable reference, not acceptance. It provides a stable
reference to application-produced evidence but does not evaluate that evidence,
declare it sufficient, or grant any authority. Evidence acceptance remains an explicit owner decision.

In-memory or event transport is not durable evidence. An in-memory event,
queue notification, or event-bus delivery may carry an evidence reference, but
is not itself the durable evidence that the reference identifies.

## Redaction and retention boundary

Redaction is reference-only in this wave. A redaction reference may identify
that a producer applied redaction, but this contract defines no redaction
format, implementation, or sufficiency judgment.

Retention is explicitly `unassigned` until a separate contract exists. This
contract assigns no retention period, deletion policy, storage owner, or legal
classification.
