# Current Integration Chain Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the historical reconciliation ledger from chain 14 to the current committed Outer `e804e946`, Child `731288b4`, OpenFang `75067d8c`, and unchanged Voice `2a457625` heads without making runtime or live claims.

**Architecture:** Treat Git commit objects as the only evidence source. Append every missing first-parent merge in chronological ledger order, mirror the exact records in the closed-world Python validator, then append one final gitlink-chain record whose three links are checked against committed trees. Existing entries and external references remain byte-for-byte/structurally unchanged.

**Tech Stack:** Git object database, JSON, Python 3.11+, pytest, `tools.v1_governance.reconciliation`.

---

### Task 1: Establish the exact missing history

**Files:**
- Read: `docs/governance/cockpit-reconciliation-ledger-v1.json`
- Read: `tools/v1_governance/reconciliation.py`
- Test: `tests/v1_governance/test_cockpit_reconciliation_ledger.py`

- [x] **Step 1: Enumerate missing first-parent merges**

Run Git object queries from the last ledger heads through `origin/master`, `vibemind-os/origin/master`, and `openfang/origin/main`. Record exact merge SHA, both parents, PR number and next per-domain ordinal. Reject non-merge commits or gaps.

- [x] **Step 2: Verify the final tree edges**

Run:

```text
git ls-tree e804e94610c804a459aa1fb00711290acc5722f7 vibemind-os
git -C vibemind-os ls-tree 731288b4e36ac172dfb902e22627c6f937760a3e openfang voice
```

Expected targets are Child `731288b4`, OpenFang `75067d8c`, and Voice `2a457625`.

### Task 2: Add contract tests first

**Files:**
- Modify: `tests/v1_governance/test_cockpit_reconciliation_ledger.py`

- [x] **Step 1: Write the failing append-only tail test**

Add a test that asserts the previous 79-entry prefix is unchanged, the exact new ordered suffix is present, and the final chain has the four expected commits.

- [x] **Step 2: Write tamper-negative tests**

Add parameterized mutations for the current Outer, Child, OpenFang, and Voice edges. Each mutation must raise `ReconciliationError` with the historical gitlink mismatch message.

- [x] **Step 3: Run RED**

```powershell
python -m pytest tests/v1_governance/test_cockpit_reconciliation_ledger.py -q
```

Expected: failures caused only by missing current records and chain.

### Task 3: Append ledger facts and mirror the validator

**Files:**
- Modify: `docs/governance/cockpit-reconciliation-ledger-v1.json`
- Modify: `tools/v1_governance/reconciliation.py`

- [x] **Step 1: Append JSON records**

Append the missing Outer, Child, and OpenFang merge records followed by the final `historical-gitlink-chain`. Do not reorder or rewrite the 79-entry prefix and do not change `external_references`.

- [x] **Step 2: Extend closed-world constants**

Append the same facts to `OUTER_MERGE_RECORDS`, `CHILD_MERGE_RECORDS`, `OPENFANG_MERGE_RECORDS`, `GITLINK_CHAINS`, and `LEDGER_ENTRY_ORDER`. Preserve exact cross-kind order.

- [x] **Step 3: Run GREEN**

```powershell
python -m pytest tests/v1_governance/test_cockpit_reconciliation_ledger.py -q
```

Expected: all ledger tests pass.

### Task 4: Verify real Git objects and hand off

**Files:**
- Create: `docs/operations/2026-08-17-current-chain-reconciliation-handoff.md`

- [x] **Step 1: Materialize only required read-only Git objects**

Use isolated/detached Child and OpenFang worktrees or existing clean object stores. Do not initialize unrelated submodules.

- [x] **Step 2: Run the real validator**

```powershell
python -c "from pathlib import Path; from tools.v1_governance.reconciliation import validate_reconciliation_ledger; validate_reconciliation_ledger(Path('.'), child_repo_root=Path('<child>'), openfang_repo_root=Path('<openfang>'))"
```

Expected: exit 0 against exact committed objects.

- [x] **Step 3: Verify scope and append-only preservation**

Check the 79-entry JSON prefix, external references, allowed file list, `git diff --check`, and clean worktree after commit.

- [ ] **Step 4: Document and publish**

Record exact RED/GREEN counts, commit SHAs, object roots, non-claims, and remaining deployment-gate drift. Create one Conventional Commit, push the task branch, open a PR to `master`, and merge only after current checks are green.
