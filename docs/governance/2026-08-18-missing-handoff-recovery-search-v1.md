# Recovery search for the nine merged tasks without a findable handoff (2026-08-18)

Produced by session `task-governance-0038-missing-handoff-recovery-search-v1`
(parent `cockpit-observability`), request
`docs/governance/session-requests/task-governance-0038-missing-handoff-recovery-search-v1.json`,
authority `standing-autonomy:v1`.

Base: `origin/master` at `7c47980426c6eac9dd99f5790b68670dd515e0f2`. The brief names that
commit; it was measured, not adopted — a fresh full clone's `HEAD` and `git rev-parse
origin/master` both return `7c47980426c6eac9dd99f5790b68670dd515e0f2`.

This document **searches and reports**. It writes, amends and reconstructs **no handoff**.
Where a task genuinely has none, that is recorded as a finding and put to the user, not
repaired here.

## 0. Headline

`task-governance-0036` §7.3 found nine merged tasks with no findable handoff. Searching by
content and by history rather than by filename settles all nine:

- **Two have a handoff.** It is titled "handoff", names its task, and was merged by that
  task's own PR. Only the *filename* omits the task ID, which is why a filename search
  missed it — the same defect class as `task-governance-0034`, one degree worse.
- **Three have a per-task completion document** written by the task's own session and
  merged by its own PR, self-titled "execution evidence" rather than "handoff". Whether
  that satisfies §11 is a naming ruling, not a search result — see F1 and question Q1.
- **Four have no per-task document at all.** Their result is nonetheless evidenced
  elsewhere: the completed-task register, the merged artefacts, and — for three of the
  four — commit-message bodies carrying the verification the session actually ran.
- **None of the nine is an evidence void.** Category 3 ("nothing") is empty.

So condition 6's handoff limb fails for **four** tasks on the strict reading, not nine —
and for **seven** it fails only as a naming defect, if at all.

## 1. Why filename search had to fail

The measurement already knew filenames were unreliable: `task-governance-0034` carries
`docs/operations/2026-08-17-task-governance-0034-validator-gitlink-coverage-handoff.md`,
breaking the `<date>-<task-id>-handoff.*` pattern. This search found that the naming is
worse than "sometimes has a slug appended". Four naming schemes are in live use:

| Scheme | Example | Carries task ID? |
|---|---|---|
| `<date>-<task-id>-handoff.*` | `2026-08-17-task-git-0032-handoff.md` | yes |
| `<date>-<task-id>-<slug>-handoff.md` | `2026-08-17-task-governance-0034-validator-gitlink-coverage-handoff.md` | yes |
| `<date>-<chain-slug>-handoff.md` | `2026-08-17-current-chain-reconciliation-handoff.md` | **no** |
| `<date>-<slug>-evidence.md` | `2026-08-13-submodule-readiness-evidence.md` | **no** |

Handoffs also live in **three** directories, not one: `docs/operations/`,
`docs/governance/handoffs/`, and `docs/governance/session-handoffs/` (the last using
`<session-id>.yaml` with no date at all).

Searching by the request *slug* instead of the task ID does not rescue it either. The slug
of `task-deployment-0018` is `current-chain-regate`; its handoff is named
`current-chain-deployment-regate`. The slug of `task-git-0026` is
`submodule-readiness-workflow`; its document is `submodule-readiness-evidence`. A slug
search (S10 below) misses both. **Only a content search over the object database found
every artefact.**

## 2. Searches actually run

Every search below was run against three full, non-shallow clones, at separate paths, with
`vibemind-os` never initialised inside the superproject working tree. All `refs/pull/*/head`
were fetched first, so unmerged and deleted PR branches are inside the search space.

| Repo | Refs searched | Commits | Objects |
|---|---|---|---|
| `Flissel/vibemind_v1` | 482 (214 branches/tags + 268 PR heads) | 1076 | 6574 |
| `Flissel/vibemind-os` | 200 | 563 | 11797 |
| `Flissel/openfang` | 48 | 633 | 7479 |

| # | Search | Scope | Result |
|---|---|---|---|
| S1 | `git ls-files \| grep -E <ids>` | working tree, 3 repos | superproject: the 9 request JSONs only. Child repos: nothing. |
| S2 | `ls docs/operations/`, `docs/governance/handoffs/`, `docs/governance/session-handoffs/` | all 3 known handoff directories | no file for any of the nine |
| S3 | `git rev-list --objects --all \| grep -E <ids>` — every path in every tree reachable from every ref, incl. paths that no longer exist | 3 repos | superproject: the 9 request JSONs only. Child repos: **zero paths**. |
| S4 | `git log --all --diff-filter=A --name-only` | 3 repos | no handoff/evidence path carrying any of the nine IDs was ever added |
| S5 | `git log --all --diff-filter=D --name-only`, filtered `handoff\|handover\|evidence\|<ids>` | 3 repos | **no governance handoff or evidence document has ever been deleted** in any ref of any of the three repos. (`vibemind-os` shows deletions of `moire_agents/agents/handoff/*.py` — Automation_ui agent code, not governance artefacts.) |
| S6 | **Full-content scan of every blob in the object database** — `git cat-file --batch-all-objects`, reachable *and* unreachable, packed *and* loose — for the nine IDs | 3 repos | superproject: 133 of 2093 blobs match, resolved to paths in §3. `vibemind-os`: 2 blobs (both `scripts/verify_openfang_mcp_registration.py` and its test, mentioning `task-integration-0005b`). **`openfang`: 0 of 2895 blobs.** |
| S7 | **Full-message scan of every commit and tag object** for the nine IDs | 3 repos | `vibemind-os`: 5 commits. `openfang`: 3 commits. Contents in §5. |
| S8 | `git log --all -S<id> --name-only` (pickaxe) per ID | superproject | subsumed by S6; no path beyond S3 |
| S9 | Every path ever named `*handoff*`/`*handover*` under any `docs/` tree, over all refs | 3 repos | complete inventory: 84 matching paths in the superproject, of which 80 are handoff artefact files (`.md`/`.yaml`, excluding two directory entries, the unrelated `docs/contracts/brain-openfang-handoff-v1.md`, and this task's own request JSON); 0 in `vibemind-os`; 1 in `openfang` (`docs/operations/2026-08-12-openfang-tool-only-runtime-handoff.md`, which S6 confirms mentions none of the nine and which predates the work) |
| S10 | Path universe over all refs for the nine request **slugs** rather than IDs | 3 repos | found 2 of the 5 existing documents; **missed 3**. Recorded because it demonstrates that slug search is not a sufficient fallback. |
| S11 | `git diff --name-only <merge>^1 <merge>` — the complete file list each task's branch delivered | 9 merges across 3 repos | definitive per-task delivery lists, §4 |
| S12 | Completed-task register, `docs/governance/session-request-queue-v1.md` §3.3 and §3.4 | superproject | 7 of 9 in §3.3; the other 2 in §3.4, both marked `abgeschlossen` with PR and merge commit |
| S13 | GitHub PR bodies for #157, #162, `vibemind-os#139`, `openfang#17` | GitHub API | **NOT RUN — blocked.** `api.github.com` is reachable but returns `403 {"message":"GitHub access is not enabled for this session. An org admin must connect the Claude GitHub App for this organization."}`. This is the one search the brief asks for that could not be executed; see F3. |

S13's gap is bounded rather than open: GitHub's merge commits for this repository carry the
PR *title* as their body, and those were read from git (§5). Only the PR *description* is
unread.

## 3. Verdict per task

`FOUND` = a per-task completion document exists, with its exact path and the commit that
introduced it. `NONE` = no such document exists anywhere in any ref of any of the three
repositories, on the searches listed above.

| Task | Verdict | Artefact | Introduced by | Merged by |
|---|---|---|---|---|
| `task-deployment-0016` | **NONE** — result otherwise evidenced | — | — | #157 `c5aa093c8eab7e065a38f9acdafc0f9f5a8d7853` |
| `task-deployment-0018` | **FOUND — handoff** | `docs/operations/2026-08-17-current-chain-deployment-regate-handoff.md` | `adaabf90bfe2e221a59de8d71173c7ed18858737` | #214 `903cc4754b67cffe4911e558117be6c895f8e99a` |
| `task-git-0026` | **FOUND — evidence document** | `docs/operations/2026-08-13-submodule-readiness-evidence.md` | `41164b6f3e6804976b019798251eb5a8d85e1e10` | #156 `9c6f591d4daa5ecdff34f22fff55bffb0ba8c2c8` |
| `task-git-0027` | **FOUND — evidence document** | `docs/operations/2026-08-13-vibemind-os-pin-a92ccd3-evidence.md` | `8ad1cf62d7d7aa6a8c34213a739f58669b96df2d` | #167 `792c6a27f16768509b9dbc2630b6ff6b0e2c7e6b` |
| `task-git-0028` | **NONE** — result otherwise evidenced | — | — | `vibemind-os#139` `c5cba961126523bed39d0d94e8fd0c982cb9cbe2` |
| `task-integration-0005a` | **NONE** — result otherwise evidenced | — | — | #162 `71cc6afaf385f36ad5d265a189e1fdc62c1cea1a` |
| `task-integration-0005b` | **FOUND — evidence document** | `docs/operations/2026-08-13-openfang-mcp-registration-stage2-evidence.md` | `f17d2628ea82e36a6fd026d6e02be6a0af38a2b1` | #164 `292f92c24dc0407b7987f6e1f6e294cdf40b9858` |
| `task-observability-0012` | **FOUND — handoff** | `docs/operations/2026-08-17-current-chain-reconciliation-handoff.md` | `92ae76d85efc45afa705784c0673ad79a596484a` | #213 `23a7bcffaaf0301bb591f0b89cb982f66bc7d8cc` |
| `task-openfang-0008` | **NONE** — result otherwise evidenced | — | — | `openfang#17` `5d38662f9fa596c8f145e4f6a45a09edf4504837` |

**Chain of custody for all five FOUND artefacts.** Each was introduced by a commit that sits
on its own task's branch and reached `master` through that task's own merge PR — verified
with `git merge-base --ancestry-path`, not inferred from the filename. Four of the five
merge commits match the register in §3.3 exactly (`9c6f591`, `292f92c`, `23a7bcf`,
`903cc47`); the fifth, `task-git-0027`, matches its §3.4 row (PR #167, `792c6a2`). **No
verdict here rests on name similarity.**

## 4. What the five found documents contain

The two `-handoff.md` files are handoffs in the ordinary sense and are not ambiguous:

- `2026-08-17-current-chain-deployment-regate-handoff.md` opens with
  `Task: task-deployment-0018-current-chain-regate-v1`, authority, base commit, then
  outcome, RED/GREEN TDD evidence, a single final complete Pester run (47 passed), further
  gates, a no-model invariant section, and explicit non-claims.
- `2026-08-17-current-chain-reconciliation-handoff.md` opens with
  `Task: task-observability-0012-current-chain-reconciliation-v1`, base commit, outcome,
  baseline/RED/GREEN pytest evidence, and states that all merge SHAs were read from local
  Git objects rather than substituted from PR heads.

The three `-evidence.md` files each name their session, request, branch, base commit and
authority in the opening paragraph, and carry verbatim command output, gate results,
deviations, blockers and follow-ups:

- `2026-08-13-submodule-readiness-evidence.md` — eight sections of verbatim console output,
  a key finding (`--init` without `--recursive` cannot satisfy the gate), the coupled
  `manifest validate` blocker reported rather than worked around, and three numbered
  follow-up proposals.
- `2026-08-13-vibemind-os-pin-a92ccd3-evidence.md` — tree-level verification of the pin,
  the manifest changes justified entry by entry, gate output, and a five-point "deviations,
  blockers, open questions" section that itself records the missing `task-git-0027` request
  JSON.
- `2026-08-13-openfang-mcp-registration-stage2-evidence.md` — a declared fail-closed
  Stage 2 with an explicit "no live-registration claim is made anywhere in this delivery".

On substance these are handoffs. On naming and schema they are not: none is called a
handoff, and none has the `schema_version: 2` YAML companion. That gap is a **ruling for
the user (Q1)**, not something this search can settle, and emphatically not something to
close by writing files today.

## 5. Where the substance of the four NONE tasks is recorded

For all four, `git diff --name-only <merge>^1 <merge>` (S11) confirms the branch delivered
**no** document to `docs/operations/`, `docs/governance/`, or anywhere else.

**`task-deployment-0016`** — PR #157 delivered 10 files (`docs/contracts/proxmox-image-determinism-v1.md`,
`docs/runbooks/proxmox-image-pinning.md`, `infra/proxmox/image-determinism-policy.json`,
`infra/proxmox/image_determinism.py`, four compose/stack manifests, and two test suites).
Register row: §3.3, #157, `c5aa093`. The three branch commits carry method and scope in
their bodies — digests "resolved read-only over the registry HTTP API (no docker, no pull,
no host access)" and "The gate reads only tracked, committed, unmodified repository
content". They do **not** name the task ID; only the register links them.

**`task-integration-0005a`** — PR #162 delivered 4 files
(`docs/contracts/openfang-mcp-authority-v1.md`, `shared/contracts/openfang-mcp-authority-v1.json`,
`tests/integration/test_openfang_mcp_authority_contract_v1.py`, `tests/integration/.gitignore`).
Register row: §3.3, #162, `71cc6af`. This is the **thinnest** of the nine: no per-task
document, no task ID in any commit message, and the merge body is only the PR title. The
task is evidenced by its merged contract, its register row, and downstream references
(queue §3.1b, §3.1c, §3.1f and `architecture-decisions-2026-08-16-v1.md` line 36, which
binds Research's allowlist vocabulary to "the MCP authority contract (`task-integration-0005a`,
merged in #162)").

**`task-git-0028`** — `vibemind-os#139` delivered exactly two gitlink bumps (`coding-engine`,
`openfang`) and no documentation. Its evidence is in the two commit-message bodies, which
S7 found and which are substantial: both record `git ls-remote` and `git merge-base
--is-ancestor` verification performed *before* pinning, a grep for stale references to the
old pin, the task ID, and the authority reference
(`maintenance delegation claude-user-message:session_01SdA3ftgP3wciDbcFzKw4uk@2026-08-13T13:09:00Z`).
Register row: §3.3, `vibemind-os#139`, `c5cba96`.
- `75c0f63b02f608fd652fc42cab1db5c9c9cc5e1f` — coding-engine `be1994b` → `81ab938`
- `a18644bd6966642d6fb88818421f8e438c226380` — openfang `33be359` → `5d38662`

**`task-openfang-0008`** — `openfang#17` delivered three files
(`crates/openfang-types/src/agent.rs`, `openfang.vibemind.toml`, `openfang.vibemind.toml.template`).
Commit `a9d95b47d1c45d23a63a2778e98a14684e514af6` carries the fullest commit-message record
of the four: the mechanism (OpenFang spawns stdio MCP servers with a cleared environment),
the root cause, the consequence (`spaces-ideas` returned `configuration_error`;
`vibemind-db` silently fell back to `localhost:54321`), the fix, the explicit note that
only variable *names* and no values were added, the guard test, the linkage to blocker B1
of `task-integration-0005b`, and `Task: task-openfang-0008-mcp-env-whitelist-v1`.
Register row: §3.4 line 585, marked `abgeschlossen`, `openfang#17`, merge `5d38662`.

**Beware the ID collision here.** `openfang` contains a second merge whose branch carries
the same task ID with a different slug —
`fac8e429f5ad`, "Merge pull request #6 from Flissel/codex/openfang/task-openfang-0008-mcp-servers-manifest-migration-v1",
which touched ten `agents/*/agent.toml` files. This is the collision recorded in queue
§3.1w. `openfang#17` is the merge that §3.4 names; `openfang#6` is a different piece of
work under a colliding ID. A search that matched branch names alone would conflate them.

## 6. The three answers to condition 6

The brief asks these to be kept apart. They are:

**(1) "A handoff exists" — satisfies §11.** `task-deployment-0018`, `task-observability-0012`.
Two tasks. Both were miscounted by §7.3 purely because the filename omits the task ID.

**(1*) "A per-task completion document exists, not named or schema'd as a handoff."**
`task-git-0026`, `task-git-0027`, `task-integration-0005b`. Three tasks. Whether these fall
in (1) or (2) is Q1.

**(2) "No handoff, but the result is otherwise evidenced."** `task-deployment-0016`,
`task-integration-0005a`, `task-git-0028`, `task-openfang-0008`. Four tasks. Every one has
a register row with PR number and merge commit, and merged artefacts that are themselves
inspectable; three of the four additionally have commit-message bodies recording the
verification actually performed. What is missing is the *narrative* record — gates run,
deviations, non-claims — in the form §11 expects.

**(3) "Nothing." Empty.** No task among the nine lacks both a document and any other record.

Note what §11.3 literally requires of a merge: "Task-Ledger und Evidence vollständig sind" —
ledger and evidence complete. It does not use the word *handoff*. Under that wording the
five FOUND tasks are covered and the four NONE tasks turn on whether a register row plus
merged artefacts plus commit bodies count as complete evidence. The stricter reading — that
§11 requires a handoff artefact — is the one `task-governance-0036` applied. This document
does not choose between them; see Q1.

> **Orchestrator-Korrektur vom 2026-08-18, beim Einsammeln nachgemessen.** Der Absatz oben
> zitiert „§11.3" ohne die Spezifikation zu nennen, und der Kontext dieses Dokuments legt das
> Portfolio-Design nahe. Der zitierte Wortlaut steht aber in
> `docs/superpowers/specs/2026-07-30-v1-space-orchestration-design.md:544` (Abschnitt „11.3
> Merge-Gates"). Das **Portfolio-Design**, das die V1-Erfolgsbedingungen definiert, hat in §11
> gar keine Unterpunkte — es ist eine flache Liste, und der maßgebliche Punkt lautet wörtlich:
> *„Session-Ergebnisse ohne Tests, Evidence oder **vollständigen Handoff** sind nicht
> merge-ready."*
>
> Die Zitatstelle ist also echt, stammt aber aus einer anderen Spezifikation. Am Suchergebnis
> ändert das nichts — es ist unabhängig geprüft und steht. An der Rahmung von Q1 schon: die
> Frage ist **nicht** „der Text sagt nicht Handoff", sondern **„zwei verbindliche Dokumente
> formulieren das Merge-Gate verschieden — eines verlangt einen vollständigen Handoff, das
> andere vollständige Evidence."** Das ist der schärfere Befund, und er bleibt eine Frage an
> den User.

## 7. Findings

**F1 — The handoff convention is not one convention.** Four filename schemes and three
directories are in live use, two of the schemes omit the task ID entirely, and two artefact
kinds (`-handoff.md`, `-evidence.md`) carry the same content. Any mechanical assignment
built on filenames will keep producing false negatives. `task-governance-0036` §7.3 produced
five of them out of nine. A content-based or front-matter-based assignment would not.

**F2 — The completed-task register is split and §3.3 is incomplete.** §3.3 is titled
"Abgeschlossene Implementierungs-Tasks" and carries 33 rows, but two of the nine —
`task-git-0027` (PR #167, `792c6a2`) and `task-openfang-0008` (`openfang#17`, `5d38662`) —
are recorded only in §3.4, the *derived follow-up* table, as inline `abgeschlossen` notes. A
reader consulting §3.3 as the register of completed tasks will not find them. Both rows were
independently confirmed against git in this session. **Not repaired here** — see Q2.

**F3 — PR bodies are unreadable from this session.** `api.github.com` answers `403 {"message":
"GitHub access is not enabled for this session. An org admin must connect the Claude GitHub
App for this organization."}`. The brief's hypothesis that "a PR body may carry what a
handoff would have" is therefore **untested** for #157, #162, `vibemind-os#139` and
`openfang#17`. It is bounded, not open: the merge commits carry the PR titles, and those add
nothing beyond the file lists already reported. Confirming or refuting it needs either the
GitHub App connected for this org or a reader with repository access.

**F4 — `task-integration-0005a` is the weakest link of the nine.** It is the only one with
no per-task document, no task ID in any commit message in any repository, and nothing but
its register row tying its four merged files to a task. Everything else has at least one
git-side record naming its task.

**F5 — `task-git-0027` ran without a request JSON, and said so.** Its own evidence document
records at §5.1 that `docs/governance/session-requests/task-git-0027-vibemind-os-pin-a92ccd3-v1.json`
did not exist on any ref at execution time; the task ran under the cockpit brief and the
maintenance-delegation reference. The request JSON exists on `master` today. This is a
provenance detail worth carrying forward, not a defect this task should touch.

## 8. Open user questions

**Q1 — Do the three `-evidence.md` documents satisfy §11, or is a handoff artefact required
by name and schema?** Decides whether the handoff limb of condition 6 fails for four tasks or
for seven. Both readings are defensible, but see the orchestrator correction above for which
document says what: the space-orchestration design's §11.3 asks for complete evidence and
these documents supply it, while the portfolio design's §11 names a *vollständigen Handoff*;
the program's practice since 2026-08-14 is a named handoff pair
with `schema_version: 2` and these predate it. **This session did not decide it and wrote
nothing.**

**Q2 — For the four tasks with no per-task document: accept the gap as recorded, or commission
a reconstruction?** If a reconstruction is commissioned it must be labelled as one —
written today, from git and register evidence, by someone who did not run the original work —
and must never be filed under the original date. Writing an unlabelled handoff today for a
task that ran on 2026-08-13 would fabricate exactly the evidence this convention exists to
protect. This session declined to do it and will not do it without an explicit, so-labelled
instruction.

**Q3 — Should §3.3 absorb the two rows that currently live only in §3.4 (F2)?** A register
edit, not an evidence question. Left untouched here because the brief scopes this session to
searching and reporting.

## 9. What this session did not do

No handoff was written, amended, backfilled or reconstructed. `repo-manifest.yaml` and the
gitlinks were not touched. `shared/contracts/` was not touched in any form, including the
three false agentfarm assertions, which remain an authorization decision for the user. The
worktree limb of condition 6 (F6 of the measurement) was not addressed — it needs a schema
field and is a design change. No workflow file was touched. No PR was opened and nothing was
merged. `vibemind-os` was never initialised inside the superproject working tree; it and
`openfang` were cloned to separate paths outside it, so `manifest validate` saw the declared
`initialization_state: uninitialized` throughout.
