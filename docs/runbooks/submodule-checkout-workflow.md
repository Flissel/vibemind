# Submodule checkout workflow (vibemind-os)

Bring the `vibemind-os` submodule tree into a session-ready state so the read-only readiness gate reports `ready: true`, without deleting, forcing, resetting or repinning anything.

Git CLI, the committed `repo-manifest.yaml` and `python -m tools.v1_governance` are the source of truth. This runbook only *checks out* what the parent repository already pins; it never changes a pin.

## Scope and prohibitions

This workflow is strictly additive: it clones and checks out commits that are already recorded as gitlinks in the parent tree.

Do not, under this runbook: delete or deinitialize a submodule (`git submodule deinit`, `rm -rf vibemind-os`); use any force operation (`--force`, `git checkout -f`, `git reset --hard`, force-push); run `git clean`; reset a submodule onto a branch tip or any state other than its recorded pin; edit `.gitmodules`, `repo-manifest.yaml` or a gitlink; or discard foreign or pre-existing work. `git submodule update` without `--init` is also out of scope here, and `--remote` is forbidden outright — it moves submodules to branch tips and *is* a pin change.

If the desired end state cannot be reached with the commands below, stop and report the blocker. Do not improvise a workaround.

## Preconditions

1. A clean parent working tree on an approved task branch. Verify with `git status --porcelain` (empty output).
2. `git` and Python with the repository's `tools/` package importable from the repository root.
3. Network and credential access to the submodule remotes (see *Network and authentication failures*). `vibemind-os` is a **private** repository; the twelve second-level modules and the six third-level modules are reachable anonymously.

## Step 1 — Record the starting state

Run from the repository root:

```bash
python -m tools.v1_governance audit --repo .
python -m tools.v1_governance submodules readiness --repo .
git submodule status
```

On an uninitialized checkout the readiness gate exits `2` and reports:

```json
{"findings": [{"code": "uninitialized", "path": "vibemind-os"}], "ready": false}
```

and `git submodule status` shows the pin with a leading `-`, which means "gitlink present, not checked out":

```
-<expected_gitlink_pin> vibemind-os
```

The expected `vibemind-os` pin is **always the current `expected_gitlink_pin` value in `repo-manifest.yaml`** — read it from there, never from this runbook. If the leading pin from `git submodule status` differs from the manifest value, stop: that is a pin question, not a checkout question, and it is out of scope for this runbook.

## Step 2 — Initialize the top level

```bash
git submodule update --init
```

Expected output on first run:

```
Submodule 'vibemind-os' (https://github.com/Flissel/vibemind-os.git) registered for path 'vibemind-os'
Cloning into '/<repo>/vibemind-os'...
Submodule path 'vibemind-os': checked out '<expected_gitlink_pin>'
```

`--recursive` is deliberately omitted here so that an authentication or network failure surfaces on the single private remote first, before eighteen further clones are attempted.

## Step 3 — Initialize nested submodules

**This step is required.** The readiness gate recurses: it walks every tracked gitlink inside each initialized submodule, to unlimited depth. A top-level-only checkout therefore still fails, with one `nested-uninitialized` finding per second-level module:

```json
{"findings": [{"code": "nested-uninitialized", "path": "vibemind-os/brain/the_brain/tribe"}, ..., {"code": "nested-uninitialized", "path": "vibemind-os/voice"}], "ready": false}
```

Complete the tree:

```bash
git submodule update --init --recursive
```

This registers and checks out the twelve second-level modules and, transitively, six third-level modules (`.../Automation_ui/moire_tracker`, `.../swe_desgine/external/arch_team`, `.../voice/electron-app/clawport-ui`, `.../voice/external/Autogen_AgentFarm`, `.../voice/external/openclaw`, `.../voice/external/zeroclaw`) — nineteen gitlinks over three levels. Each line ends in `checked out '<pin>'`.

Steps 2 and 3 may be collapsed into the single recursive command once the environment is known to have access to the private remote.

## Step 4 — Verify

```bash
python -m tools.v1_governance submodules readiness --repo .
git status --porcelain
```

The gate must print exactly:

```json
{"findings": [], "ready": true}
```

and exit `0`. `git status --porcelain` must stay empty: a correct run changes no tracked content in the parent repository. Do not report readiness as green on the basis of clone output alone — only the gate's `ready: true` counts.

`python -m tools.v1_governance audit --repo .` then lists all nineteen submodules with their checked-out pins and `dirty_paths: []`.

The workflow is idempotent: re-running the recursive command on a ready tree produces no output, exits `0`, and leaves the gate green.

## Interaction with the manifest gate

Completing this workflow makes a second gate go red. `repo-manifest.yaml` records `initialization_state: uninitialized` for `vibemind-os`, so once the submodule is checked out, `python -m tools.v1_governance manifest validate --repo .` reports an **error**:

```json
{"code": "initialization-state-mismatch", "path": "vibemind-os", "message": "submodule is initialized", "severity": "error"}
```

This is expected and is not caused by a faulty checkout: the two gates encode contradictory expectations until the manifest field is updated to `initialized` (a value the gate already accepts). Do not resolve it by deinitializing the submodule — that would trade a readiness-green tree for a readiness-red one. Report it and let the manifest be corrected under a task whose allowed paths include `repo-manifest.yaml`.

Run `manifest validate` only on a **full** clone. On a shallow clone (`--depth 1`) it additionally reports a spurious `parent-pin-mismatch` for `vibemind-os`, because the manifest's `evidence.parent_pin` commit is simply not present in a truncated history. `git fetch --unshallow` removes that finding; the pin is a genuine ancestor of `master`.

The three `declared-without-gitlink` **warnings** (`external/minibook`, `spaces/desktop/Automation_ui/moire_tracker`, `spaces/flowzen/flowzen`) are pre-existing and unrelated to this workflow.

## Readiness findings and what they mean

The gate (`tools/v1_governance/submodule_readiness.py`) is read-only and reports:

| Code | Meaning | Response |
| --- | --- | --- |
| `uninitialized` | Top-level gitlink not checked out | Step 2 |
| `nested-uninitialized` | Gitlink inside a submodule not checked out | Step 3 |
| `pin-mismatch` | Checked-out HEAD differs from the recorded gitlink | Stop and escalate — do not "fix" by resetting |
| `dirty-submodule` | Modified or untracked files inside a submodule | Stop and escalate; preserve the work, never `git clean` |
| `submodule-unavailable` | Path exists but Git cannot read it | Stop and escalate |
| `invalid-submodule-path` | Gitlink path escapes the repository | Stop and escalate |
| `repository-unavailable` | `--repo` is not a Git repository | Fix the invocation |

`pin-mismatch` and `dirty-submodule` are the two findings this runbook must never resolve on its own: both can only be cleared by discarding or moving state that may belong to someone else. Note that the dirty check counts untracked files, so stray build artifacts inside a submodule will hold readiness red until their owner removes them.

## Nested submodules

Nested modules are declared `nested-legacy` in `repo-manifest.yaml` and are not separately initializable from the parent: their gitlinks live in the *submodule's* index, not the parent's, so `--recursive` is the only supported path. Two manifest entries are declaration-only records with `expected_gitlink_pin: absent` (`spaces/flowzen/flowzen`, `voice/external/minibook`); no gitlink exists at those paths and none is expected. The `moire_tracker` path is declared twice — once as absent from the `vibemind-os` index and once as a required gitlink inside `Automation_ui`. Both are correct: the gitlink lives in `Automation_ui`'s index.

Third-level modules include two external upstreams (`JohnRiceML/clawport-ui`, `zeroclaw-labs/zeroclaw`). They are pinned like any other module; do not update them to upstream tips.

## Network and authentication failures

A failed submodule fetch is a finding to report, not a problem to work around.

When the environment cannot authenticate to the private `vibemind-os` remote, Step 2 fails as:

```
Cloning into '/<repo>/vibemind-os'...
fatal: could not read Username for 'https://github.com': terminal prompts disabled
fatal: clone of 'https://github.com/Flissel/vibemind-os.git' into submodule path '/<repo>/vibemind-os' failed
Failed to clone 'vibemind-os'. Retry scheduled
...
Failed to clone 'vibemind-os' a second time, aborting
```

Git retries once by itself and then aborts with exit `1`. **This abort is safe and leaves no residue**: the submodule directory stays empty, no `.git/modules/` entry is created, the parent working tree stays clean, and the gate still reports the original `uninitialized` finding. The command can simply be re-run once access exists — no cleanup is needed, and in particular no `rm -rf` and no `deinit`.

Do not respond to this failure by rewriting the remote URL, embedding a token in `.gitmodules`, disabling TLS verification, or substituting a different source. Report `ready: false` with the exact Git output and the affected path, and escalate the access gap.

If only *some* modules fail, the recursive command still checks out the reachable ones and aborts on the first failure; readiness stays red and the findings name precisely which paths are missing. Re-running after access is granted completes the remainder.

## Abort behavior

Stop and escalate rather than continuing when: a pin differs from `repo-manifest.yaml`; the gate reports `pin-mismatch`, `dirty-submodule`, `submodule-unavailable` or `invalid-submodule-path`; the parent working tree is dirty before you start; or a fetch fails for authentication or network reasons. In every one of these cases the correct output is a report with exact command output, not a repaired tree.
