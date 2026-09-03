# Deep Research report artifacts — persistence shape

**Status:** written, **not applied to any database**
**Task:** `task-research-0003-report-artifact-migration-v1`
**Basis:** decision **E14** (resolves open decision D1 to `short_idea_plus_linked_artifact`)
**Migration:** `Flissel/vibemind-os @ 731288b` → `supabase/migrations/20260817_research_report_artifacts.sql`
(first pinned commit containing the file; anchored by `task-research-0004` under
[`provenance-pin-convention-v1.md`](provenance-pin-convention-v1.md))
**Declaration:** [`shared/contracts/research/v1/research-service-tiers-v1.json`](../../../shared/contracts/research/v1/research-service-tiers-v1.json) → `report_persistence`
**Runbook:** [`docs/operations/2026-08-17-research-report-artifacts-migration-runbook-v1.md`](../../operations/2026-08-17-research-report-artifacts-migration-runbook-v1.md)
**Tests:** `tests/contracts/research/test_research_report_artifact_migration_v1.py`

## Staging

This task wrote files. It executed no SQL, opened no database connection, ran no
`psql`, no PostgREST call, no `supabase db push`, and no `docker exec`. No
database was reachable from the session and none was contacted. Applying the
migration is a live action reserved to the user; the runbook describes it, and
nothing in this task performed it.

Verification therefore stops where files stop: the migration was parsed with the
real Postgres grammar offline (`pglast`, `parse_sql`), and its text is held to
the properties this document claims by a test file. **Constraint behaviour,
foreign-key enforcement, and RLS were not observed at runtime, because that
would require applying the migration.** That gap is deliberate and is the first
thing the runbook asks an operator to close.

## What E14 decided, and what it left open

D1 asked where a 5-to-10-page report physically lives. E14 chose **Option B —
short idea plus linked artifact**: the idea keeps a summary, the report lives as
its own record that the idea points at.

E14 did **not** decide D2 (bubble fan-out). The shape below is written so that
both D2 answers remain implementable without a further migration; see
[Neutrality toward D2](#neutrality-toward-d2).

## Where each side lives

| | Idea side | Artifact side |
| --- | --- | --- |
| Record | `public.ideas` | `public.research_report_artifacts` |
| Content | summary, ≤ 4000 characters | the full report |
| Pointer | `metadata.research_artifact_refs` (proposed) | `artifact_ref` |
| Migration needed | **none** | this one |
| Reaches Rowboat today | yes, via the existing DB→FS render | no — see [D3](#d3--the-sync-question) |

The idea side needs **no schema change at all**. `ideas.description` is
unbounded `TEXT` already, and 4000 characters is what
`ResearchIdeaHandoffV1.idea_summary` already caps the idea-facing text at.
`ideas.metadata` is an existing `JSONB` column, so the pointer costs nothing
either.

## The one property everything else rests on

**The foreign key sits on the artifact, never on the idea.**

`public.ideas` gains no column. That is not a stylistic preference; it is the
reason the whole shape is cheap:

- `emit_ideas_sync_event()` writes `to_jsonb(NEW)` — the complete idea row —
  into `public.ideas_sync_outbox` on every insert, update, and delete
  (`20260610_ideas_sync_triggers.sql`). A new column on `ideas` would enter that
  payload permanently, on every future touch of every idea, whether or not it
  was ever researched.
- The sync is bidirectional and `description` is the hand-editable surface under
  last-write-wins (`20260610_ideas_sync_columns.sql`). Keeping the report out of
  that column keeps a 10-page body out of a live conflict surface.
- Worker A and Worker B need no change whatsoever, because nothing they read has
  changed shape.

A test asserts this directly: the migration may not `ALTER TABLE ideas`, may not
create any trigger or function, and may not name the outbox.

## Column provenance

Every column traces to something that already exists. Nothing here is invented
for its own sake.

| Column | Comes from |
| --- | --- |
| `id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text` | `swe_design_artifacts:61`, and every other table in the schema |
| `artifact_ref` | `ResearchResultV1.artifact_refs` — the join key between a result document and a row. Without it nothing connects the contract family to the table |
| `job_id`, `result_id` | `ResearchJobV1.job_id`, `ResearchResultV1.result_id`. No foreign keys: neither document has a table, and inventing one would pre-empt D2's parent/child job model |
| `subject_type`, `subject_ref` | the subject model in the merged service-tier declaration (`topic` / `idea` / `bubble`) |
| `idea_id`, `bubble_id` | `ideas.id` and `ideas.parent_id`; the same pair `ideas_sync_outbox` carries, for the same reason |
| `artifact_type`, `name`, `rel_path`, `format`, `content_text`, `content_json` | `swe_design_artifacts:68-77`, column for column |
| `depth`, `output_style` | the Hand's own `research_depth` and `output_style` settings, as already bound by the merged declaration |
| `citation_count` | the analogue of `swe_design_artifacts.item_count`, tightened — see below |
| `internal_context_used`, `context_disclosure` | E12's disclosure obligation |
| `created_at` | `swe_design_artifacts:79`. There is deliberately no `updated_at` |

### Three deviations from `swe_design_artifacts`, and why

1. **`citation_count INTEGER NOT NULL CHECK (>= 1)`** instead of
   `item_count INTEGER DEFAULT 0`. The research evidence policy is fail-closed:
   an uncited report is a failed run, not an artifact. Dropping the default
   forces the writer to state the count rather than inherit a silent zero.
2. **`UNIQUE (job_id, name)`** instead of `UNIQUE (run_id, rel_path)`. Same
   intent — one artifact per file per run — on a column that can carry it. In
   Postgres two NULLs are distinct, so the neighbour's constraint over the
   nullable `rel_path` does not in fact deduplicate. `name` is `NOT NULL` in
   both tables.
3. **Named `CHECK` constraints on every enumerated column.** The neighbour
   validates none of its text columns. These value sets are closed upstream —
   the ID grammar by the contract family, `depth` and `output_style` by the Hand
   — and a typo that reaches storage is unrecoverable evidence damage.

A fourth difference is not a deviation but a fix: the neighbour's bare
`ALTER PUBLICATION supabase_realtime ADD TABLE` aborts with `42710
duplicate_object` on a re-run. Here it sits behind an existence check, which is
what makes the file re-runnable end to end.

### Write-once

There is no `updated_at`. A report artifact is written once; a second run on the
same subject inserts a second row. That is how "several reports over time on one
idea" is expressed, and it is the thing the long-body option could not do
without an overwrite-or-append rule.

## Neutrality toward D2

D2 — one report across a bubble, or one per member idea — is **not** decided
here and must not be read into this shape. Both answers store cleanly:

| D2 answer | `subject_type` | `idea_id` | `bubble_id` | Rows per run |
| --- | --- | --- | --- | --- |
| single cluster report | `bubble` | NULL | the cluster | 1 |
| report per member idea | `bubble` | the member | the cluster | N |

The subject-linkage `CHECK` admits both: a bubble subject must name its cluster
and may or may not also name a member. Neither `idea_id` nor `bubble_id` is
`NOT NULL`, and a test enforces that they stay nullable.

What choosing D2 Option B would still need is a parent/child **job** model —
one `research.deep.start` returning one `job_id` but producing N reports. That
is the event cut's problem, owned by `task-research-0001`, not this table's:
N rows sharing one `job_id` already store correctly, because the uniqueness key
is `(job_id, name)`.

## D3 — the sync question

`emit_ideas_sync_event()` is bound to `public.ideas` alone. Writing a report
artifact therefore emits nothing, and this migration adds no trigger of its own.

That is a real consequence, not a neutral one, and it is a product question
rather than an engineering one — so it is carried as **open decision D3** in
[`deep-research-open-decisions-v1.md`](deep-research-open-decisions-v1.md)
rather than settled here. The short version:

- **What still reaches Rowboat:** the idea summary and the artifact pointer,
  through the DB→FS markdown render that already exists.
- **What does not:** the report body.
- **Why that matters (E12):** Rowboat is the internal reference source a *later*
  run consults to ask "what do we already know?". A report body that never
  lands there cannot answer that question next time — the reader sees the
  summary and a reference that Rowboat cannot resolve.

The recommendation recorded in D3 is to stay outside the sync chain for now and
add a dedicated lane when the Rowboat wiring lands, which is exactly the
web-first, Rowboat-additive ordering E13 already chose. The reasoning, the
alternatives, and the case against reusing the ideas outbox are set out in full
in the decision document.
