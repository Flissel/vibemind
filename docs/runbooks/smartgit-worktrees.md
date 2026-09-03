# SmartGit and V1 worktrees

SmartGit is a visual client for the same Git objects managed by the CLI. Git CLI, committed contracts, the repository manifest, and governance tests remain the source of truth.

## Workflow

1. Create and audit an approved task branch and isolated worktree through the V1 CLI workflow.
2. Open the root repository in SmartGit and refresh after CLI worktree creation or any external Git operation.
3. Select the task worktree and visually verify its branch, Working Tree, and submodule pin before commit.
4. Run the authoritative governance tests and commands in the CLI; use SmartGit only to inspect their Git result.
5. Let the V1 orchestrator manage PR dependencies, checks, merge order, post-merge verification, and the request/parent-cockpit/handoff provenance chain.

Do not use SmartGit actions that auto-stash, force-push, delete branches or worktrees, or directly merge a task branch into the protected integration branch. Do not resolve conflicts by discarding foreign or pre-existing changes. Stop and escalate when the displayed state differs from the CLI audit or the approved scope.
