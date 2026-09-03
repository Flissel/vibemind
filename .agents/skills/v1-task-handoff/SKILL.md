---
name: v1-task-handoff
description: Produce an evidence-backed V1 task handoff without overstating readiness.
---

# V1 task handoff

Before handoff, compare the diff with the approved paths and preserve all unrelated work. Use narrowly scoped Conventional Commits.

Record all of the following in `.agents/templates/TASK_HANDOFF.yaml`:

- branch, worktree, and every commit SHA;
- exact test commands, results, counts, and test evidence paths;
- changed files and other evidence paths;
- dependencies and their current integration state;
- deployment status, including `not_required` when applicable;
- remaining blockers, deviations, and unverified claims.

A failed, skipped, interrupted, stale, or unavailable test is never green test evidence. Report it exactly. Re-run the relevant verification immediately before claiming readiness, inspect the final diff and dirty state, and hand control to the V1 orchestrator. The task session does not push, merge, deploy, or clean up unless separately and explicitly authorized.
