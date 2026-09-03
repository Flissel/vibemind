# Research service tiers V1 — contract draft

**Status:** draft, behaviour-neutral, unregistered
**Task:** `task-research-0002-space-definition-contract-v1`
**Basis:** decisions E11, E12, E13 (`docs/governance/architecture-decisions-2026-08-16-v1.md`)
**Declaration:** [`shared/contracts/research/v1/research-service-tiers-v1.json`](../../shared/contracts/research/v1/research-service-tiers-v1.json)
**Tests:** `tests/contracts/research/test_research_service_tiers_v1.py`

## What this document does and does not do

This is a contract draft. It writes down what a Research service grade *is*, so
that a later task can bind it. It changes no behaviour.

| This draft | Explicitly not this draft |
| --- | --- |
| defines two service tiers and their execution forms | registering, renaming, or removing a registry event |
| binds `depth` and `output_style` to the values the Hand already declares | changing the Hand, its settings, or its defaults |
| defines the subject model that replaces today's ad-hoc parameters | rewiring any caller to the new parameters |
| proposes an event cut for both tiers | mutating `config/space_agent_registry.yml` — that is `task-research-0001` |
| states the fail-open/fail-closed rule | implementing the runtime that enforces it |
| carries two open questions to the user | deciding them |

Nothing here routes, executes, persists, or approves. The accompanying
declaration is deliberately **not** registered in `shared/contracts/validate.py`,
so it cannot be picked up as an active document type by accident.

### Authoring note on the basis document

At authoring time `docs/governance/architecture-decisions-2026-08-16-v1.md` was
not present on `origin/master` (the admissions PR carrying it, and this task's
own session request, were unmerged; the E-numbering on `master` ends at E8 in
`architecture-decisions-2026-08-15-v1.md`). Every substantive claim below was
therefore re-derived from the repository at pinned commits rather than from the
decision text, and the decision content was taken from the task brief. If the
merged E11–E13 wording diverges from what is written here, this draft is wrong
and must be corrected before anything binds to it. See the handoff for the full
assumption record.

## 1. Two service tiers

Research today offers one shape of service: a single tool call that answers
inside the caller's turn. Deep Research is a different shape entirely, and the
distinction is not a matter of degree.

### Lookup

One synchronous tool call. It answers now and keeps nothing.

Today's `research.web` and `research.scrape` are exactly this
(`config/space_agent_registry.yml:171-172` at vibemind-os pin `c5cba96`): each
binds to the `fetch` tool with one parameter and returns within the call.

- **Execution form:** synchronous tool call
- **Job identity:** none — there is nothing to ask about afterwards
- **Persistence:** none
- **Bounded by:** the caller's request/response turn
- **Settings:** none
- **Evidence:** at least one source URL

### Deep Research

An asynchronous job carried by the bundled OpenFang Researcher Hand
(`crates/openfang-hands/bundled/researcher/HAND.toml` at openfang pin
`5d38662`).

- **Execution form:** asynchronous job
- **Job identity:** required — status, result, and cancellation all address it
- **Persistence:** a report artifact (where it lives is **open decision D1**)
- **Bounded by:** the job lifecycle, not the caller's turn
- **Settings:** `depth`, `output_style`
- **Evidence:** at least one citation carrying a source URL

There is no event for this tier today. That gap is the reason this draft exists.

### Why they cannot be one service grade

A synchronous tool call and a long-running autonomous job are incompatible
execution forms. Collapsing them would force one of the two to lie about itself:

1. **Duration.** A synchronous call must return inside the caller's turn. The
   Hand declares `max_iterations = 25` and raises its heartbeat to 120s
   specifically because "30s (kernel default) causes false-positive recovery
   triggers" — its calls routinely outlive a turn by design.
2. **Identity.** A synchronous call needs no id; a job cannot be asked about
   without one. Bolting an optional `job_id` onto a synchronous event gives
   callers a parameter that is meaningless half the time.
3. **Persistence.** Lookup keeps nothing. A deep run produces a report that must
   live somewhere and be referenced later.
4. **Parameters.** `depth` and `output_style` are meaningless for a single
   fetch: there is no multi-pass budget to spend and no report to format. A
   shared tier would carry parameters that are inert on one side.

So: two tiers, two event shapes, one shared subject model.

## 2. Parameters are bound, not invented

`depth` and `output_style` are not new. The Researcher Hand already declares
both. This contract binds to those declarations verbatim — it does not define
its own scale.

Verified at `Flissel/openfang` pin
`5d38662f9fa596c8f145e4f6a45a09edf4504837`, path
`crates/openfang-hands/bundled/researcher/HAND.toml`:

### `depth` — Hand setting `research_depth`

| Value | Hand's own label | Default |
| --- | --- | --- |
| `quick` | Quick (5-10 sources, 1 pass) | |
| `thorough` | Thorough (20-30 sources, cross-referenced) | **default** |
| `exhaustive` | Exhaustive (50+ sources, multi-pass, fact-checked) | |

### `output_style` — Hand setting `output_style`

| Value | Hand's own label | Default |
| --- | --- | --- |
| `brief` | Brief (executive summary, 1-2 pages) | |
| `detailed` | Detailed (structured report, 5-10 pages) | **default** |
| `academic` | Academic (formal paper style with citations) | |
| `executive` | Executive (key findings + recommendations) | |

Both sets are **closed**. No step may be added, renamed, or reordered here; the
Hand is the source, and a change starts there. The contract tests assert exact
list equality against these values precisely so that a future edit that invents
a fourth depth or a fifth style fails rather than drifts.

Both apply to **Deep Research only**.

### Settings deliberately left Hand-side

The Hand declares six further settings — `source_verification`, `max_sources`,
`auto_follow_up`, `save_research_log`, `citation_style`, `language`. E11 named
`depth` and `output_style`; these are not lifted into the contract surface and
remain Hand configuration. Recorded so that their absence reads as a decision
rather than an oversight.

Note one interaction: `source_verification` and `citation_style` shape *how*
citations appear, but they cannot switch citations off. The evidence rule in
section 5 sits above them.

## 3. Subject model

Today the research events take whatever parameter each tool happened to need:
`query`, `url`, `idea_id`, `title` (`config/space_agent_registry.yml:171-174`).
There is no shared notion of what a research request is *about*. Three subject
kinds replace those ad-hoc parameters.

### `topic` — free text

The plain case: a question with no record behind it.

- **Required:** `text`
- **Question:** the text itself
- **Result:** returned to the caller
- **Replaces:** `query`
- **Tiers:** Lookup, Deep Research

### `idea` — a reference to an existing idea

- **Required:** `idea_id`
- **Question:** derived from the idea's `title` and `description`
- **Result:** enriches the subject idea
- **Replaces:** `idea_id`, `title`
- **Tiers:** Lookup, Deep Research

Repo evidence: `ideas` carries `title TEXT NOT NULL` and
`description TEXT DEFAULT ''`
(`supabase/migrations/20260411_init_vibemind.sql:11-26`). Those two columns are
the question; nothing else in the row is prose. Note that today's
`research.summarize` takes `idea_id` and `research.to_idea` takes `title` — two
different views of the same subject, which is exactly the incoherence this model
removes.

### `bubble` — a cluster of ideas

- **Required:** `bubble_id`
- **Members:** resolved through `ideas.parent_id`
- **Question:** derived from the member ideas
- **Result:** **open decision D2**
- **Tiers:** Deep Research only

Repo evidence, and this one matters: a bubble is **not a separate table**. It is
an idea that has children. `shuttles.bubble_id` and
`exploration_sessions.root_bubble_id` both declare
`REFERENCES ideas(id)` (`supabase/migrations/20260411_init_vibemind.sql:129`,
`:156`), and `ideas.parent_id` is a self-referencing foreign key with an index
(`:23`, `:31`). The registry already treats the bubble as ambient context:
`research.default_context` is `[current_space, current_bubble]`
(`config/space_agent_registry.yml:169`).

Two consequences follow. First, a bubble subject needs no new storage — the
cluster is already expressible. Second, because a bubble *is* an idea, a bubble
subject and an idea subject can address the same row; the contract distinguishes
them by intent (research the cluster vs. research this one idea), not by type.

Bubble is Deep-Research-only: fanning a synchronous single call across a cluster
has no coherent meaning.

## 4. Proposed event cut

**Draft only.** Registry mutation belongs to `task-research-0001`. Names and
shapes below are a proposal for that task to accept, amend, or reject.

The style follows what the registry already does for asynchronous work:
`mirofish.status` keys on `job_id` (`:343`); `agentfarm.run` starts and
`agentfarm.results` reads back, both keyed on `run_id` (`:289`, `:291`).

### Lookup — unchanged shape

| Event | Required today | Proposed | Change |
| --- | --- | --- | --- |
| `research.web` | `query` | `subject_type`, `subject_ref` | parameter rename; result still inline |
| `research.scrape` | `url` | `locator` | parameter rename; result still inline |

No new event, no job id, no lifecycle. `research.scrape` keeps a locator rather
than a subject because it addresses one document, not a question.

### Deep Research — start, status, result

| Event | Required | Optional | Returns |
| --- | --- | --- | --- |
| `research.deep.start` | `subject_type`, `subject_ref` | `depth`, `output_style` | `job_id` |
| `research.deep.status` | `job_id` | — | `status` |
| `research.deep.result` | `job_id` | — | `report_ref`, `citations`, `context_disclosure` |
| `research.deep.cancel` | `job_id` | — | `status` |

`cancel` is included because the lifecycle already has a `cancelled` state and
an autonomous multi-pass job that cannot be stopped is an operational liability.

**Lifecycle reuse.** The status values are the ones `ResearchJobV1` already
allows — `clarification_required`, `queued`, `running`, `waiting_for_approval`,
`paused`, `succeeded`, `failed`, `cancelled`, `unavailable`
(`shared/contracts/research/v1/research-job-v1.schema.json`). This draft
introduces no new lifecycle.

**Binding note.** Existing research events bind to MCP tools
(`{ tool: fetch, required_params: [query] }`). Deep Research is carried by a
Hand, not an MCP tool, so the binding key differs. The registry already has more
than one execution shape — `rowboat.status` carries an explicit
`execution: { kind: mcp, server: spaces-rowboat }` block (`:198`) — so a
`kind: hand` binding is a natural extension. The exact spelling is
`task-research-0001`'s call, not this draft's.

**Also unaddressed here:** the Hand's own Phase 7 publishes a `research_complete`
event with the report path via `event_publish`. Whether that becomes the
transport for `research.deep.result` or stays Hand-internal is a wiring
question, flagged rather than decided.

## 5. Degradation rule (E12)

Two failure modes, deliberately opposite. Internal context makes a report
better; evidence makes it true.

### Fail **open** on context

If the internal context is missing, or Rowboat is unreachable, or Rowboat
answers with nothing for this subject, the research **continues web-only**.

But the degradation is **never silent**. The report must state that it was
produced without internal context.

- **Mode:** `fail_open`
- **On unavailable:** continue web-only
- **Disclosure:** required, in the report
- **Silent degradation:** forbidden

The reasoning is about how the output gets read. A report that quietly omits
internal context looks identical to one that considered it and found nothing
relevant. A reader cannot distinguish them, so they will trust the degraded
report as much as the complete one. The disclosure is what keeps fail-open
honest — without it, fail-open is just data loss with a clean face.

Repo evidence that internal context is a real expectation and not a hypothetical:
`research.default_context: [current_space, current_bubble]`
(`config/space_agent_registry.yml:169`), and a `research_to_rowboat` tool is
already declared for the space (`data/space_capabilities/research.yml`).

### Fail **closed** on evidence

A report without citations is a **failed run**. Not a degraded one.

- **Mode:** `fail_closed`
- **Requirement:** at least one citation carrying a source URL
- **On violation:** the run is marked failed
- **Prose without a source:** rejected

This is not a new rule — it extends one the codebase already enforces.
`spaces/research/execution_target.py` (vibemind-os pin `c5cba96`) rejects
prose-only answers today. Its module docstring is explicit: "The target
deliberately rejects prose-only agent answers. A successful result must contain
an external tool call and at least one source URL, so unavailable Fetch/Qdrant
infrastructure cannot be mistaken for live research." `ResearchTarget.call`
returns `unverified research result: source evidence is missing` when
`_urls(result)` finds nothing.

The Hand's own guidance points the same way — "NEVER fabricate sources,
citations, or data — every claim must be traceable". The contract makes that a
gate rather than an instruction, because an instruction in a system prompt is
not an enforcement point.

The asymmetry is the whole rule: **a report that lacks internal context is worse;
a report that lacks evidence is not research.**

## 6. Open decisions

Two questions this draft deliberately does not answer. Both are laid out with
options, consequences, and repo evidence in
[`docs/spaces/research/deep-research-open-decisions-v1.md`](../spaces/research/deep-research-open-decisions-v1.md).

- **D1 — Where does a Deep Research report physically live?** Long body on the
  idea, or a short idea plus a linked artifact.
- **D2 — Bubble fan-out.** One report across the cluster, or one report per
  member idea.

Both are marked `resolved: false` in the declaration, and the contract tests
assert they stay that way until a user decides.

## Verification

```bash
python -m pytest tests/contracts/research/test_research_service_tiers_v1.py -q
```

The suite was written test-first: all 36 tests errored against the missing
declaration, then passed once the declaration was added. The full research
family suite (`tests/contracts/research/`, 137 tests) stays green.
