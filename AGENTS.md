# VibeMind V1 Agent Rules

## Source of truth

Git CLI, committed contracts and repository tests are authoritative. SmartGit is a visual client for the same Git state.

## Autonomous session authority

- `standing-autonomy:v1` authorizes routine `docs` and `code` Cockpit/Task processes without per-session user interaction.
- The orchestrator may coordinate bounded work in existing approved sessions — worktrees, branches, tests, commits, pushes, PRs and green non-breaking merges — under that authority.
- Creating a new session (cockpit or implementation) always requires the user's individual approval; see `docs/governance/multi-session-program-charter-v1.md`.
- Every writing Task Session uses one isolated worktree (isolierter Worktree) and one `codex/<space>/<task-id>-<slug>` branch.
- Every task still declares objective, repositories, allowed paths, dependencies, merge position, risk, tests and evidence.
- Record the real standing authority as `approval_status: approved` plus `approval_reference: standing-autonomy:v1`; never invent another authority reference.

## Git and integration

- Do not commit directly to the protected integration branch (`master` during migration, target `main`); nicht direkt auf dem Integrationsbranch committen.
- Audit worktrees, dirty state, ancestry, remote parity and submodules before edits, merge, cleanup or push claims.
- Preserve unrelated and pre-existing changes.
- Use Conventional Commits and narrowly scoped commits.
- The V1 orchestrator maintains PR metadata, dependencies, CI, reviews, merge order, submodule pins and post-merge verification.
- Never delete a worktree or branch under standing autonomy.

## Authority gates

Normal green `docs` and `code` PRs covered by `standing-autonomy:v1` may be merged by the orchestrator. Deployments, destructive operations, breaking contracts, database migrations, secret changes, Proxmox mutations, large repository moves and cleanup require request-specific authority and cannot use the standing mandate.

## Verification

No task is complete without exact test evidence, commit SHA, integration status and remaining blockers. Live claims must be based on live evidence and fail closed.
