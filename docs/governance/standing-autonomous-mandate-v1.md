# Standing Autonomous Mandate V1

## Authority

`standing-autonomy:v1` records the user's standing instruction from 2026-08-01
to run routine VibeMind development processes without routine user interaction.
A secondary supervisory process observes the orchestrator and
reports incorrect behavior to the user; it is oversight, not an execution or
approval authority.

## Autonomous scope

The V1 orchestrator may perform the following without pausing for per-session
confirmation when the request is classified as `docs` or `code`:

- repository-first read-only audits and bounded planning;
- cockpit/task activation and coordination;
- isolated worktree and `codex/*` branch creation;
- scoped edits, tests, commits, pushes, PR creation and PR maintenance;
- merge of green, non-breaking PRs in declared dependency order; and
- post-merge verification and status reporting.

Each task still requires a concrete objective, repositories, allowed paths,
dependencies, merge position, tests, evidence, and a fail-closed risk class.
The session request records `approval_status: approved` and
`approval_reference: standing-autonomy:v1`; this references real standing user
authority and is not a fabricated per-task approval.

## Safety boundary

Standing autonomy does not authorize secrets, force-pushes, foreign-change
discard, destructive production actions, deployments, breaking contracts,
database migrations, Proxmox mutations, large repository moves, or branch and
worktree deletion. It does not authorize destructive production actions. Those
risk classes require request-specific authority that
explicitly covers the action. If it is absent, the autonomous process fails
closed, records the blocker, and continues other safe in-scope work without
repeatedly interrupting the user.

Product-runtime approvals remain owned by OpenFang and are unaffected by this
Codex development-process mandate.
