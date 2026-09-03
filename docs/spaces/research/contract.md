# Research V1 contract family

## Purpose and boundary

Research V1 is a provider-neutral, versioned, data-only contract family for
an offline research request, collection plan, lifecycle record, source
evidence, citations, result, and reviewable idea handoff. All seven schemas
use JSON Schema Draft 2020-12 and reject unknown fields.

The contracts do not invoke a provider, scrape a source, make an HTTP call,
access a database, execute an Idea action, grant approval, settle costs, prove
provider health, or prove a Golden Path. `approval_ref` and `quote_ref` are
opaque correlation references only. They are not authorities or proof that an
approval or quota decision occurred.

## Documents and opaque references

| Document | Registered type | Core references |
| --- | --- | --- |
| `ResearchRequestV1` | `research-request` | request, task, trace, quote, approval |
| `ResearchPlanV1` | `research-plan` | plan, request, task, trace, quote, approval |
| `ResearchJobV1` | `research-job` | job, request, plan, task, trace |
| `SourceEvidenceV1` | `source-evidence` | evidence, request, plan, job, artifact |
| `CitationV1` | `citation` | citation, claim, source evidence |
| `ResearchResultV1` | `research-result` | result, request, plan, job, task, trace, evidence, artifact, quote, approval |
| `ResearchIdeaHandoffV1` | `research-idea-handoff` | handoff, result, evidence, approval |

Shared IDs use `<kind>_v1_<ULID>` with an uppercase 26-character Crockford
Base32 ULID. The available Research kinds are `request`, `plan`, `job`,
`result`, `task`, `trace`, `approval`, `quote`, `evidence`, `artifact`, and
`citation`. No credential, provider, runtime, URL endpoint, or direct database
field is permitted by these closed objects.

## Hard bounds and deterministic costs

Both request and plan require finite `collection_limits`: `max_sources` is
1–50, `max_depth` is 1–5, and `max_duration_seconds` is 1–3600. `null`, zero,
negative values, and values above these caps are rejected. The plan must not
exceed the request's bounds when the complete chain is validated.

Costs are non-floating integer minor units plus an ISO-style three-letter
currency code. Request and plan carry a maximum cost; a result carries both
estimated and actual cost. They are accounting data only, never a runtime cost
authority.

## Offline semantic validation

`validate_document(document_type, document)` validates one document
structurally and applies local semantic checks, including a closed job lifecycle
and the requirement that a succeeded result includes evidence, citations,
artifact references, and evidence references. Allowed lifecycle statuses are
`clarification_required`, `queued`, `running`, `waiting_for_approval`,
`paused`, `succeeded`, `failed`, `cancelled`, and `unavailable`.

Each `status_history` record may optionally carry a closed
`transition_context` with required `actor` and `action`. Actors are limited to
the provider-neutral values `chat`, `brain`, and `research_space`. Actions map
fail-closed to their target status: `pause` -> `paused`, `resume` -> `queued`,
`cancel` -> `cancelled`, `complete` -> `succeeded`, `fail` -> `failed`, and
`mark_unavailable` -> `unavailable`. Unknown or missing values, foreign context
fields, and action/status mismatches are invalid.

If `transition_context` is absent, provenance is unknown; a UI or consumer must
not infer an actor or reason. The context is offline declarative status
provenance only. It does not prove execution, persistence, cancellation,
approval, a cost decision, provider or runtime activity, Application readback,
evidence acceptance, or a Golden Path.

`validate_research_bundle(documents)` requires exactly one of each seven
document types and deterministically checks request/plan/job/result IDs,
collection bounds, citation-to-source-to-claim integrity, verified-claim source
status, result/job status consistency, and the handoff's result, evidence, and
approval references. It also requires plan currency, quote, approval, and
maximum cost to match or stay within the request budget; result currency,
quote, approval, estimated cost, and actual cost must match or stay within the
plan budget. These comparisons are offline consistency checks, not cost or
approval authority. A ResearchIdeaHandoffV1 is valid only for a succeeded
result. It remains an idea candidate for a separate owner to review; it cannot
perform a direct Idea/database action.

Run the focused offline suite with:

```powershell
python -m pytest tests/contracts/research/test_research_v1_contracts.py -q
```

The suite was added test-first: the initial Request fixture failed because the
document type was unregistered, then passed after its schema and registry were
added; the full seven-document suite failed before the remaining schemas and
bundle validator existed, then passed once they were implemented.
