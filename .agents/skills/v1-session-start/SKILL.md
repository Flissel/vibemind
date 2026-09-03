---
name: v1-session-start
description: Start a bounded V1 cockpit or task under standing autonomy or request-specific authority.
---

# V1 session start

Use this routine autonomously. Git CLI, committed contracts, the repository manifest, and governance tests are the source of truth.

1. Run a read-only audit of the repository, worktrees, dirty state, remote parity, and submodules.
2. Read the existing code and contracts for the affected Space.
3. Define the objective, allowed scope, risks, definition of done, and test strategy from the user's standing goal and repository evidence.
4. For bounded `docs` or `code`, create an approved request with `approval_reference: standing-autonomy:v1`.
5. Validate and activate the request without pausing for routine user interaction.
6. Show the governance dry-run; create the worktree only with the explicit `--execute` option.
7. Keep `space-cockpit` sessions read-only; activate writing only as a separate bounded `task` request.
8. Continue independently through tests, handoff, push, PR maintenance, green merge, and post-merge verification when those actions remain routine and non-breaking.

Standing autonomy is real user authority, not an invented approval. Use only the exact `standing-autonomy:v1` reference and only for `docs` or `code`. High-risk work—deployment, destructive work, breaking contracts, database migrations, secrets, Proxmox mutations, large repository moves, or cleanup—requires request-specific authority and must fail closed without it.

Do not stash, reset, clean, delete, force-push, or discard foreign changes. Stop the affected task when audited state or risk materially differs, record the blocker, and continue other safe work without repeatedly interrupting the user.
