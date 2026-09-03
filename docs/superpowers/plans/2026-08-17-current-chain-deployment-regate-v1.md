# Current Chain Deployment Regate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the static deployment-readiness authority from Child `9ee1cc4` / OpenFang `33be359` to Child `731288b4` / OpenFang `75067d8c` while leaving Voice `2a457625` and all no-model-on-Proxmox controls unchanged.

**Architecture:** Tests declare the new immutable pins first and rewrite only their hermetic fixture substitution sources. Production then updates its two required pin constants. The full Pester contract, manifest suite, reconciliation suite, and real local Git-object validator prove the static chain; no service or infrastructure endpoint is invoked.

**Tech Stack:** PowerShell 7, Pester 5, Git object trees, Python/pytest governance validators.

---

### Task 1: Capture the pin-contract RED

**Files:**
- Modify: `tests/deployment/deployment-readiness.Tests.ps1`

- [x] **Step 1: Update test-only expected pins**

Set the expected Child pin to `731288b4e36ac172dfb902e22627c6f937760a3e` and OpenFang pin to `75067d8c6b375fb70fe677daf78918164caaff41`. Update exactly the old-to-new fixture substitution sources. Add negative assertions that the superseded `9ee1cc4` and `33be359` pins no longer occur in the production preflight.

- [x] **Step 2: Run the focused test and verify RED**

```powershell
Invoke-Pester -Path tests/deployment/deployment-readiness.Tests.ps1 -FullNameFilter '*pins match the current*' -Output Detailed
```

Expected: the production constants still expose the old pins, so the focused contract fails.

### Task 2: Apply the minimal static regate

**Files:**
- Modify: `scripts/deployment-readiness.ps1`

- [x] **Step 1: Replace only the two production constants**

Change `$RequiredOuterChildPin` to `731288b4...` and `$RequiredOpenFangPin` to `75067d8c...`. Do not modify `$RequiredVoicePin`, compose discovery, model detection, service logic, or runtime behavior.

- [x] **Step 2: Run focused GREEN**

Re-run the pin-alignment, superseded-pin, no-model, and off-pin tamper tests. Expected: all selected tests pass.

### Task 3: Run the complete static gate exactly once

**Files:**
- Test: `tests/deployment/deployment-readiness.Tests.ps1`

- [x] **Step 1: Run full Pester without deployment flags**

```powershell
Invoke-Pester -Path tests/deployment/deployment-readiness.Tests.ps1 -Output Detailed
```

Expected: every test passes; do not use `-CI`, do not create `testResults.xml`, and do not retry a completed run.

- [x] **Step 2: Run governance regressions**

```powershell
python -m pytest tests/v1_governance/test_manifest.py tests/v1_governance/test_cockpit_reconciliation_ledger.py -q
```

Expected: all tests pass.

- [x] **Step 3: Run the real ledger validator**

Validate against clean Child `731288b4` and OpenFang `75067d8c` evidence worktrees. Expected: `PASS`.

### Task 4: Document, verify, and publish

**Files:**
- Create: `docs/operations/2026-08-17-current-chain-deployment-regate-handoff.md`

- [x] **Step 1: Record evidence and non-claims**

Document RED/GREEN counts, the single full-Pester result, unchanged Voice/no-model controls, exact diff scope, and that no deployment, model, Docker, MCP, or Proxmox action occurred.

- [ ] **Step 2: Verify scope and commit**

Run PowerShell parse checks, `git diff --check`, V1 PR gate, and a clean-worktree check. Commit only the five allowed paths with a Conventional Commit.

- [ ] **Step 3: Push and integrate**

Push the feature branch, open a PR to `master`, wait for current checks, and merge only with the expected head SHA. Do not delete the branch or worktree.
