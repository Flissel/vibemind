# Worktree Portfolio Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a current, reproducible, read-only classification of every registered Outer and Child worktree without deleting or modifying any existing worktree or branch.

**Architecture:** Treat `Flissel/Vibemind_V1` and `Flissel/vibemind-os` as separate Git authorities. Enumerate their registered worktrees, compare every HEAD with the repository's fetched `origin/master`, inspect working-tree dirt without changing it, and join open pull-request heads before assigning a disposition. Publish only aggregate and actionable evidence in one operations report; destructive cleanup remains a separately authorized follow-up.

**Tech Stack:** Git CLI, GitHub CLI, PowerShell, Markdown, pytest

---

### Task 1: Freeze the read-only audit boundary

**Files:**
- Create: `docs/operations/2026-08-25-worktree-portfolio-reconciliation.md`

- [x] **Step 1: Fetch and record both integration bases**

Run:

```powershell
git fetch --prune origin
git rev-parse origin/master
git -C vibemind-os fetch --prune origin
git -C vibemind-os rev-parse origin/master
```

Expected: two complete commit SHAs; neither command changes a worktree checkout.

- [x] **Step 2: Record protection inputs**

Run:

```powershell
gh pr list --repo Flissel/Vibemind_V1 --state open --limit 500 --json number,headRefName,url
gh pr list --repo Flissel/vibemind-os --state open --limit 500 --json number,headRefName,url
git worktree list --porcelain
git -C vibemind-os worktree list --porcelain
```

Expected: the live open-PR heads and complete registered worktree lists for both repositories.

### Task 2: Classify every registered worktree

**Files:**
- Modify: `docs/operations/2026-08-25-worktree-portfolio-reconciliation.md`

- [x] **Step 1: Collect one record per worktree**

For every `worktree` record emitted by Git, collect repository, absolute path,
HEAD SHA, branch or detached state, path availability, porcelain dirty count,
whether HEAD is an ancestor of the frozen `origin/master`, whether the branch
has an Origin remote head, and whether it is an open-PR head.

- [x] **Step 2: Assign exactly one disposition**

Use this precedence:

1. `unavailable` when the registered path cannot be read;
2. `detached-dirty` or `detached-clean` for detached HEADs;
3. `open-pr` for a branch backing an open pull request;
4. `current-task` for this audit's own worktree, regardless of its expected
   documentation dirt;
5. `unmerged-dirty` or `unmerged-clean` when HEAD is not on `origin/master`;
6. `merged-dirty` when HEAD is on `origin/master` but the checkout is dirty;
7. `merged-clean-base` for a clean `master` or `main` checkout;
8. `merged-clean-candidate` for all other clean, merged, non-base branches.

Expected: every registered worktree appears in exactly one class. A candidate
is evidence for later review, not deletion authority.

### Task 3: Publish the reconciliation report

**Files:**
- Modify: `docs/operations/2026-08-25-worktree-portfolio-reconciliation.md`

- [x] **Step 1: Add aggregate reconciliation tables**

Record total worktrees, attached versus detached state, clean versus dirty
state, merged versus unmerged state, open-PR protection, and disposition counts
for Outer, Child, and the combined portfolio.

- [x] **Step 2: Add actionable lists**

List every `merged-clean-candidate` with repository, branch, path, and HEAD SHA.
List every protected or review-required worktree with its exact disposition and
reason. Do not include secret contents or untracked file names.

- [x] **Step 3: State explicit non-actions**

Document that no worktree, branch, file, PR, submodule pin, runtime, deployment,
database, Proxmox host, OpenFang process, or model was changed by the audit.

### Task 4: Verify and integrate the evidence

**Files:**
- Modify: `docs/operations/2026-08-25-worktree-portfolio-reconciliation.md`
- Modify: `docs/superpowers/plans/2026-08-25-worktree-portfolio-reconciliation.md`

- [x] **Step 1: Reconcile counts**

Run the inventory a second time and require identical total and disposition
counts. Re-fetch immediately before the second run; any base movement or changed
worktree state must be reported instead of hidden.

- [x] **Step 2: Run repository gates**

Run:

```powershell
git diff --check
python -m pytest tools/mcp_sync -q
python -m pytest tests/v1_governance/test_manifest.py tests/v1_governance/test_gitlink_coverage.py -q
```

Expected: no whitespace errors, 12 sync tests passed, and 41 governance tests passed.

- [x] **Step 3: Commit and publish**

Run:

```powershell
git add -- docs/operations/2026-08-25-worktree-portfolio-reconciliation.md docs/superpowers/plans/2026-08-25-worktree-portfolio-reconciliation.md
git commit -m "docs(git): reconcile worktree portfolio"
git push -u origin codex/git/task-git-0042-worktree-portfolio-reconciliation-v1
```

Expected: one narrow documentation commit on the task branch. Open a PR to
`master`, merge only after required checks pass, and verify the merge commit is
an ancestor of `origin/master`. Keep the task worktree and branch intact.
