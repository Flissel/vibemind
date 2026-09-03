# Deep Research — open decisions for the user

**Status:** D1 decided (E14); **D2 and D3 open, awaiting a user decision**
**Tasks:** `task-research-0002-space-definition-contract-v1` (D1, D2),
`task-research-0003-report-artifact-migration-v1` (D1 record, D3)
**Contract:** [`docs/contracts/research-service-tiers-v1.md`](../../contracts/research-service-tiers-v1.md)

Questions the service-tier contract deliberately leaves open, each laid out with
options, consequences, and repository evidence. Their `resolved` flags live in
`shared/contracts/research/v1/research-service-tiers-v1.json`, and contract
tests keep the flags and this document in step: an unresolved decision may not
carry a resolution, and a resolved one may not be recorded without naming both
the option it chose and the decision entry that chose it.

| | Question | State |
| --- | --- | --- |
| **D1** | Where does a Deep Research report physically live? | **decided** — `short_idea_plus_linked_artifact` (E14) |
| **D2** | One report across a bubble, or one per member idea? | open |
| **D3** | Does the report artifact join the ideas sync chain? | open — recommendation recorded |

Repository evidence for D1 and D2 was read at the pinned commits
`Flissel/vibemind-os @ c5cba96` and `Flissel/openfang @ 5d38662`. D3's evidence
was read at `Flissel/vibemind-os @ a9a48af`; the sync migrations it cites are
byte-identical between those two commits.

Those commits are **where the reading happened**, not what the superproject pins
today — it has since moved on to `vibemind-os @ 731288b` and
`openfang @ 75067d8`. They are left as written on purpose: rewriting them would
claim a re-reading that did not happen at the time.
`task-research-0004-provenance-pin-convention-v1` re-checked every claim on this
page at the live pins and recorded the result under `provenance.verifications`
in `shared/contracts/research/v1/research-service-tiers-v1.json`. Every file
cited here is byte-identical at the live pins, so none of the analysis below has
moved. The rule these citations follow is
[`provenance-pin-convention-v1.md`](provenance-pin-convention-v1.md).

---

# D1 — Where does a Deep Research report physically live?

> **Decided — Option B, `short_idea_plus_linked_artifact`.**
> Decision **E14**, user reference
> `claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-17T07:02:00Z`.
>
> The idea keeps a summary; the full report lives as a linked artifact in a
> table of its own. The migration is written but **not applied to any
> database** — see [`report-artifact-persistence-v1.md`](report-artifact-persistence-v1.md)
> for the shape, and the runbook for applying it.
>
> **The governance record is still missing.** E14 is not present in
> `docs/governance/architecture-decisions-2026-08-16-v1.md`, whose E-series ends
> at E13. `task-research-0003` holds no authority in `docs/governance/` and did
> not write there, so the declaration carries
> `decision_record_status: "pending_governance_entry"` and a test asserts it
> keeps saying so until the entry exists. Recording E14 is the orchestrator's
> step.
>
> The analysis below is kept as written, because it is the reasoning the
> decision rests on. Three of its six findings did the deciding: the outbox
> replay cost (finding 3), the bidirectional-edit conflict surface (finding 5),
> and the 4000-character cap the merged contract family already sets
> (finding 6). Two of Option B's stated costs were paid rather than avoided —
> the migration is the storage decision, and the dangling-reference risk is
> bounded by cascading artifacts from their idea.

A `detailed` run — the Hand's own default — produces a "structured report, 5-10
pages". Where does that text end up?

## What the repository already fixes

Six findings constrain the answer before any option is considered.

**1. The `ideas` row has exactly two prose fields, and no size limit.**
`supabase/migrations/20260411_init_vibemind.sql:11-26` gives `ideas` a
`title TEXT NOT NULL` and a `description TEXT DEFAULT ''`, plus `tags JSONB`
and `metadata JSONB`. Postgres `TEXT` is unbounded, so a 10-page body in
`description` is *schema-legal today* with no migration at all.

**2. There is no artifact table for ideas.** The full table list from the init
migration is `ideas, projects, canvas_nodes, canvas_edges,
conversation_sessions, conversation_history, shuttles, exploration_sessions,
exploration_nodes, discovered_edges, mermaid_diagrams, scheduled_tasks,
flowzen_checkins, flowzen_activity, flowzen_diary, videos, video_projects,
video_project_persons, video_pipeline_steps, persistent_tasks,
user_preferences, schema_version`. The only artifact table anywhere in the
schema is `swe_design_artifacts` (`20260521_swe_design.sql:60`), scoped to a
different space. A linked artifact therefore has nowhere to live yet.

**3. Every idea change replays the whole row.** The ideas↔Rowboat sync
(`20260610_ideas_sync_triggers.sql`) fires an `AFTER INSERT OR UPDATE OR DELETE`
trigger on `public.ideas` that writes `to_jsonb(NEW)` — the **complete row** —
into `public.ideas_sync_outbox` and `pg_notify`s a worker. Every later touch of
that idea, including a bare `score` update, carries the entire report through
the outbox again.

**4. An idea is already rendered to a markdown file.** The same sync's
`last_synced_at` column is documented as "timestamp of the last successful
DB->FS markdown render … to `~/.rowboat/knowledge/Projects/`"
(`20260610_ideas_sync_columns.sql`). Whatever sits in `description` already
becomes a file in Rowboat's knowledge base.

**5. The sync is bidirectional, and `description` is the editable surface.**
Worker B applies filesystem edits back to the DB under last-write-wins conflict
ordering keyed on `updated_at`. A report body in `description` is therefore a
hand-editable field with a conflict path, not a write-once record.

**6. The existing contract family already caps the idea-facing text at 4000
characters.** `ResearchIdeaHandoffV1.idea_summary` is
`{"type": "string", "maxLength": 4000}`
(`shared/contracts/research/v1/research-idea-handoff-v1.schema.json`). At
roughly 3000 characters per page, 4000 characters is about 1.3 pages. A
`brief` report (1-2 pages) is borderline; `detailed` (5-10 pages) and `academic`
do not fit. **The already-merged contract family models the idea-side text as a
summary, not as the report.**

One more fact, from the other side: the Hand already writes a report file by
itself — `research_[sanitized_question]_YYYY-MM-DD.md` — and publishes a
`research_complete` event carrying the report path
(`crates/openfang-hands/bundled/researcher/HAND.toml`, Phases 6 and 7). A
physical report artifact exists regardless of which option is chosen. The
question is whether the system references it or copies it.

## Option A — long body in the idea

The report markdown goes into `ideas.description`.

**For**
- Zero migration. Legal under today's schema (finding 1).
- One place to look; no second hop for the reader.
- Free markdown rendering into Rowboat's knowledge base via the existing sync
  (finding 4).
- No dangling-reference risk — the text cannot go missing independently.

**Against**
- Every subsequent touch of that idea replays the full report through the sync
  outbox, permanently (finding 3).
- `description` is a bidirectionally synced, hand-editable field. A 10-page body
  becomes a live conflict surface under last-write-wins (finding 5).
- Contradicts the 4000-character `idea_summary` cap the merged contract family
  already sets (finding 6) — either the cap or this option has to give.
- `ideas` carries `embedding_vector vector(384)` and `embedding_hash`
  (`:24-25`). A report-sized body changes what that row means in semantic
  search over ideas. *Not verified:* which fields feed the embedding — worth
  confirming before choosing this option.
- No natural way to hold two reports on one idea over time; a second run either
  overwrites or appends.

## Option B — short idea plus linked artifact

`description` holds a summary; the full report lives as an artifact the idea
references.

**For**
- The idea stays a human-scale record, so the sync payload and semantic search
  keep their present character.
- Multiple reports over time on the same idea are naturally expressible.
- Matches what the Hand already does — it writes a report file and publishes its
  path (Phases 6-7).
- Matches the merged contract family, which already separates
  `ResearchResultV1` (with `artifact_refs`) from a 4000-character
  `idea_summary` (finding 6).

**Against**
- Requires a storage decision, and every candidate has a cost:
  - **a new artifact table** — a DB migration, which is a user-gated risk class
    under `CLAUDE.md`, not routine `code` work;
  - **the filesystem** — host-bound, and not covered by the ideas↔Rowboat sync,
    so the report would not reach Rowboat's knowledge base the way an idea body
    does;
  - **`metadata` JSONB on the idea** — no migration, but it re-creates Option
    A's outbox-payload problem (finding 3) with a less readable field.
- Dangling-reference risk: the idea claims a report that may no longer exist.
- Two hops for a reader.

## What would tip the choice

- If the 4000-character `idea_summary` cap is meant to stand, Option A needs
  that contract changed first.
- If reports should reach Rowboat's knowledge base, note that only the idea body
  gets there automatically today; an artifact would need its own path.
- If a subject may be researched more than once, Option A needs an overwrite or
  append rule that Option B does not.
- Option A is implementable at risk class `code`. Option B's cleanest form (a
  new table) is a DB migration and needs request-specific authority.

---

# D2 — Bubble fan-out: one report or many?

A bubble is a cluster of ideas. When Deep Research runs on a bubble, does it
produce one report over the cluster, or one report per member idea?

## What the repository already fixes

**1. A bubble is an idea with children.** There is no bubble table.
`shuttles.bubble_id` and `exploration_sessions.root_bubble_id` both declare
`REFERENCES ideas(id)`
(`20260411_init_vibemind.sql:129`, `:156`), and `ideas.parent_id` is a
self-referencing foreign key with its own index (`:23`, `:31`).

**2. The sync already attributes member changes to the owning bubble.** The
emit function computes
`v_bubble_id := COALESCE(payload_json->>'parent_id', v_idea_id)` — "owning
bubble: parent_id if a child idea, else the idea is itself a bubble"
(`20260610_ideas_sync_triggers.sql`). Per-idea results would route into the
bubble's stream without any new plumbing.

**3. The repository has a precedent for *both* shapes.** This is the useful
finding: the codebase has already solved this problem twice, in opposite
directions.

- **Aggregate, one row per bubble** — `shuttles` holds one row per
  `bubble_id` with cluster-level rollups: `score`, `passed_count`,
  `failed_count`, `total_count` (`:129-140`). One artifact describing the whole
  cluster.
- **Per-member, under a session wrapper** — `exploration_sessions` keys on
  `root_bubble_id` and tracks `total_nodes_explored` and `best_score`
  (`:156-168`), with a separate `exploration_nodes` table holding the per-member
  work. Many artifacts, one parent record tying them together.

Neither precedent is more canonical than the other; they serve different
purposes. That is the choice in front of the user.

**4. The cost difference is concrete and large.** From the Hand's own labels,
`thorough` (the default) means "20-30 sources, cross-referenced" and
`exhaustive` means "50+ sources, multi-pass, fact-checked". For a ten-idea
bubble:

| | Single cluster report | Report per member idea |
| --- | --- | --- |
| `quick` (5-10 sources) | 5-10 sources | 50-100 sources |
| `thorough` (20-30) | 20-30 sources | 200-300 sources |
| `exhaustive` (50+) | 50+ sources | 500+ sources |

The fan-out multiplies the source budget by the member count. At `exhaustive`
on a large bubble this is the difference between one long job and a very
expensive one.

## Option A — one report across the cluster

**For**
- One artifact, one job id, one lifecycle. The event cut in the contract draft
  works unchanged.
- Cost scales with depth only, not with cluster size (finding 4).
- Cross-cutting findings — what the ideas share, where they conflict — are the
  natural output, and are exactly what a per-idea run cannot produce.
- Matches the `shuttles` precedent (finding 3).

**Against**
- A large or thematically loose bubble yields a report too diffuse to be useful.
- No per-idea enrichment: individual ideas gain nothing, which breaks the
  symmetry with the `idea` subject, where the result enriches the subject.
- One failure fails everything.

## Option B — one report per member idea

**For**
- Each idea is enriched individually, consistent with the `idea` subject's
  `result_disposition`.
- Partial success is possible; one member failing does not sink the run.
- Results route into the bubble's sync stream for free (finding 2).
- Matches the `exploration_sessions` + `exploration_nodes` precedent
  (finding 3).

**Against**
- Cost multiplies by member count (finding 4).
- Needs a parent/child job model the contract draft does not currently have:
  one `research.deep.start` would return one `job_id` but produce N reports, so
  `research.deep.status` and `research.deep.result` need an aggregate answer.
- Cross-cutting insight is lost — nothing compares the members.
- Membership is dynamic. An idea re-parented mid-run has no defined treatment.
- Multiplies D1 by the member count: whatever D1 decides happens N times.

## What would tip the choice

- If bubbles are typically small and tightly themed, per-idea is affordable and
  the loss of cross-cutting analysis is the main cost. If they are large or
  loose, the cost table (finding 4) dominates.
- Option B requires extending the proposed event cut to a parent/child job
  model; Option A does not. That extension is `task-research-0001`'s surface,
  so choosing B has a scheduling consequence for that task.
- A third shape exists and is not costed here: a cluster report **plus** a short
  per-idea note. It is mentioned for completeness, not proposed — it inherits
  the cost profile of B and the aggregation work of A.

D1's resolution does not narrow this choice. The artifact row carries both
`idea_id` and `bubble_id`, so a single cluster report and a per-member report
are both storable with no further migration, and a contract test keeps those
columns nullable so they stay that way.

---

# D3 — Does the report artifact join the ideas sync chain?

**Raised by:** `task-research-0003-report-artifact-migration-v1`

D1's answer put the report in a table of its own. That table is not `ideas`, and
the ideas↔Rowboat sync fires from a trigger on `public.ideas` alone. So the
report is outside the sync chain **by default, as a side effect** — and a side
effect of that size should be a decision rather than an accident.

## What the repository already fixes

**1. The trigger is bound to one table.** `trg_emit_ideas_sync` is
`AFTER INSERT OR UPDATE OR DELETE ON public.ideas`
(`20260610_ideas_sync_triggers.sql`). An insert into any other table emits
nothing. The migration adds no trigger of its own, so today's answer is
"outside" unless something is added.

**2. Only idea rows are rendered to Rowboat.** `last_synced_at` is documented as
"timestamp of the last successful DB→FS markdown render … to
`~/.rowboat/knowledge/Projects/`" (`20260610_ideas_sync_columns.sql`). Worker A
drains the ideas outbox and renders idea markdown. There is no renderer for any
other record.

**3. The outbox payload is idea-shaped, and the schema says so.** `payload` is
documented as "full NEW row (or OLD on DELETE)" of `public.ideas`, `operation`
is `CHECK (operation IN ('INSERT','UPDATE','DELETE'))`, and the table comment
names the ideas sync as its sole purpose. It is a single-producer log, not a
general event bus.

**4. The summary side is already covered, for free.** E14 keeps a summary in
`ideas.description`. Writing that summary *is* an update to `public.ideas`, so
it fires the existing trigger and reaches Rowboat's knowledge base through the
path that already works. The question below is therefore only about the
**report body**, not about whether Rowboat learns that research happened.

**5. E12 makes this matter in one specific direction.** Rowboat is the
*internal reference source* a later run reads first — "what do we already
know?". Reports that never reach it cannot answer that question next time. E12's
fail-open rule means the next run still succeeds; it just runs web-only and says
so. Nothing breaks. Something is merely never learned.

## Option A — stay outside the sync chain *(recommended)*

The migration as written. No trigger, no outbox row, no worker.

**For**
- Zero cost and zero risk to a working sync. Nothing that exists changes.
- The ideas outbox keeps its single-producer meaning (finding 3).
- The summary and the artifact pointer reach Rowboat anyway (finding 4), so a
  reader browsing the knowledge base still sees that a report exists and what it
  concluded in brief.
- Matches E13's ordering: web-first, Rowboat additive once it is wired. Rowboat
  is currently unwired on both sides — the publish is one-shot and fail-silent,
  the query path is not exposed over MCP — so building a delivery lane into it
  now is building onto something not yet load-bearing.

**Against**
- The report body is not in Rowboat, so a later run's "what do we already know?"
  phase cannot cite an earlier report of our own. The system re-researches what
  it already investigated.
- The gap is invisible: nothing reports that a report exists but is unreachable.

## Option B — its own outbox and worker

Mirror the ideas machinery: `research_artifact_sync_outbox`, an emit trigger on
`research_report_artifacts`, and a worker that renders reports into Rowboat.

**For**
- Reports reach Rowboat, so E12's reference-source role works fully, including
  for the system's own prior output.
- The ideas outbox stays untouched and single-producer.
- The pattern is proven — it is the ideas sync, once removed.

**Against**
- A second sync lane to build, run, and operate. The first one is Phase-2 work
  that only recently landed.
- Needs a second migration; this one adds no trigger deliberately.
- Reports are write-once, so a bidirectional lane makes little sense — the
  natural shape is DB→FS only, which is a *different* worker rather than a copy
  of the existing one.
- Premature while Rowboat's own publish and query paths are unreliable (E12's
  own finding).

## Option C — reuse the ideas outbox

Have the artifact trigger write an ideas-shaped row into
`public.ideas_sync_outbox`.

**Argued against on the evidence, and not recommended.** `payload` is documented
and consumed as a full `public.ideas` row, and Worker A renders idea markdown
from it. Feeding it foreign rows would either break the renderer or force it to
branch on payload shape, turning a single-producer log into an untyped bus with
no schema to police it. The migration's `CHECK` constraints exist precisely to
keep malformed evidence out of storage; this option would reintroduce the same
class of problem one layer up. It is listed so the option is visibly considered,
not because it is viable.

## Recommendation

**Option A now, Option B when the Rowboat wiring lands.** Finding 4 is what
makes A cheap: the summary already reaches Rowboat, so choosing A loses the
report *body*, not the fact of the report. Combined with E13's decision to treat
Rowboat as additive, that is a small, reversible loss — where Option B is a
second sync lane built against an integration that does not yet work in either
direction.

The pointer is what keeps A honest. `ideas.metadata.research_artifact_refs` —
an existing `JSONB` column, no migration — carries the list of `artifact_ref`
values into the rendered markdown, so the Rowboat copy names the report it
summarises instead of merely implying one. A list of 38-character ids is not
the outbox-payload problem that a report body would be.

## What would tip the choice

- If a later run citing an earlier internal report is a core expectation rather
  than a nice-to-have, Option B is needed and its timing becomes a scheduling
  question against the Rowboat repair work.
- If Rowboat's publish and query paths are repaired soon, Option B's cost drops
  sharply, because a working knowledge base is worth delivering into.
- If reports are expected to be edited by hand after the fact, none of these
  options is right and the write-once assumption behind the artifact table needs
  revisiting first.

---

## How to record a decision

A decision belongs in `docs/governance/` as a numbered entry continuing the
E-series. Neither the task that wrote these questions nor the task that
recorded D1 holds authority there, and neither wrote to that directory.

Recording a decision also flips `resolved` in
`shared/contracts/research/v1/research-service-tiers-v1.json`. That flip is
guarded, so a resolution cannot be recorded silently:

- `test_no_decision_is_resolved_silently` requires a resolved decision to name
  a `resolution` that is one of its own declared options, and a `decision_ref`.
  An unresolved decision may not carry a `resolution` at all.
- `test_the_three_decisions_are_declared` fails the moment a decision is added
  or removed without updating the tests in the same change.

This is how D1 was recorded, and the E14 governance entry it points at does not
exist yet: `open_decisions.D1.decision_record_status` is
`pending_governance_entry`, and
`test_d1_records_that_its_governance_entry_is_still_missing` keeps it saying so.
Writing the E14 entry, and then clearing that status and its test, is the
orchestrator's step — not this space's.
