# V1 Shared Contract Core

## Scope and ownership

The Shared Contract Core defines only versioned JSON Schemas, canonical IDs,
and offline validation for portable task context. It is intentionally additive:
accepting one of these documents records a reference or a statement; it does
not change any system state and does not grant authority.

| Owner | Responsibility | Not owned by Shared |
| --- | --- | --- |
| Shared | schemas, ID grammar, fixture set, offline validation | lifecycle decisions or runtime orchestration |
| Brain | intent interpretation, planning, task lifecycle, and result validation | schema ownership or execution |
| OpenFang | execution, approvals, permissions, providers, costs | shared schema ownership |
| Applications | jobs and evidence production | global task authority |
| Minibook | read-only projection | task mutation or lifecycle authority |

An `approval_ref` is a correlation identifier only. It neither proves an
approval nor authorizes an action. An `EvidenceRefV1` is a durable reference
to evidence, not a claim that the evidence has been evaluated or accepted.
Evidence status truth, including the distinction between a durable reference
and acceptance, is defined by [the Observability evidence-governance
contract](observability-evidence-governance-v2.md). It remains an offline rule
and does not expand Shared ownership beyond schemas and offline validation.

## Canonical ID grammar

Every Shared V1 identifier uses this grammar:

```text
<kind>_v1_<ULID>
```

`<ULID>` is exactly 26 uppercase Crockford Base32 characters:

```text
[0-9A-HJKMNPQRSTVWXYZ]{26}
```

The permitted V1 kinds are `task`, `event`, `evidence`, `handoff`, `todo`,
`approval`, and `plan`. The full grammar is:

```text
^(?:task|event|evidence|handoff|todo|approval|plan)_v1_[0-9A-HJKMNPQRSTVWXYZ]{26}$
```

The grammar is syntactic. Producers are responsible for generating collision-
resistant ULIDs; validators do not infer time, ownership, ordering, or
lifecycle state from an ID.

## Contract catalog

| Contract | Schema | Purpose |
| --- | --- | --- |
| `TaskBriefV1` | `shared/contracts/schemas/task-brief-v1.schema.json` | Immutable request context, approval references, and todo descriptions |
| `TaskEventV1` | `shared/contracts/schemas/task-event-v1.schema.json` | A non-authoritative reference/note event for shared task context |
| `EvidenceRefV1` | `shared/contracts/schemas/evidence-ref-v1.schema.json` | A content-addressed reference to application-produced evidence |
| `TaskHandoffV1` | `shared/contracts/schemas/task-handoff-v1.schema.json` | A routing envelope that relates a task brief, todo, evidence, approval, and event references |
| `BrainPlanV1` | `shared/contracts/schemas/brain-plan-v1.schema.json` | A declarative Brain-owned plan with intent context, participating spaces, ordered task graph, success criteria, and evidence requirements |
| `ChannelIntentV1` | `shared/contracts/schemas/channel-intent-v1.schema.json` | A normalized, data-only inbound intent envelope from a supported Channel to Brain |
| `ChannelResultV1` | `shared/contracts/schemas/channel-result-v1.schema.json` | A data-only, user-facing projection of an admitted Channel-to-Brain route |
| `SpaceExecutionContractV1` | `shared/contracts/schemas/space-execution-contract-v1.schema.json` | A declarative canonical Space identity with executor and policy/check reference names |

`TaskEventV1.event_type` is deliberately limited to references and notes for
briefs, handoffs, approvals, todos, and evidence. It does not encode task
state transitions. This preserves Brain's lifecycle authority and OpenFang's
approval/execution authority.

`BrainPlanV1` is additive and leaves the four original V1 schemas unchanged.
It is a plan, not an execution envelope: it cannot name an application target,
agent configuration, provider, permission, approval runtime, or cost. Its
offline validator checks only plan structure and graph
integrity; it never calls a router, server, provider, database, or application.
See [the Brain plan contract](brain-plan-v1.md) for its field-level rules and
authority boundary.
See [the Channel intent contract](channel-intent-v1.md) for its ingress-only
field-level rules and authority boundary.
`ChannelResultV1` is the corresponding outbound user projection. Its offline
route validator preserves the admitted channel context, plan identity, and
participating canonical Spaces without creating lifecycle, approval, execution,
or evidence-acceptance authority; see [the Channel result contract](channel-result-v1.md).
`SpaceExecutionContractV1` is similarly declarative: a valid document does not
dispatch an executor, prove approval, settle cost, run a health check, or prove
a Golden Path. Its versioned outer-repository canonical identity snapshot is
checked for drift only when the nested registry is available; see
[the Space execution contract](space-execution-contract-v1.md).

## Versioning and compatibility

Schema filenames and `$id` values are versioned. A V1 consumer must validate
only against the exact V1 schema it declares. Within V1:

- producers must emit only fields allowed by that exact schema;
- consumers must reject missing required fields and unknown fields;
- changing a field meaning, ID grammar, requiredness, validation constraint, or
  authority boundary is breaking and requires a new major contract version;
- additive optional fields also require a new major version because V1 schemas
  reject unknown fields for deterministic cross-language behavior;
- a future version must use new schema filenames and `$id` values, while V1
  schemas and fixtures remain immutable for existing consumers.

These are data-exchange compatibility rules, not a migration instruction.
Adopters choose their own translation boundary and remain responsible for their
authoritative stores and lifecycle actions.

## Offline validation

The validator in `shared/contracts/validate.py` uses JSON Schema Draft 2020-12
and performs no network, adapter, database, provider, or service access. The
valid and invalid fixture pairs in `tests/contracts/fixtures/` are the
deterministic compatibility evidence for V1.

Run the scoped test suite from the repository root:

```powershell
python -m pytest tests/contracts/test_v1_contracts.py -q
```
