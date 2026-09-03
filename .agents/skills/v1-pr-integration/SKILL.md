---
name: v1-pr-integration
description: Integrate approved V1 pull requests in dependency order with post-merge verification.
---

# V1 PR integration

Git CLI, committed contracts, the repository manifest, and governance tests determine integration readiness. Validate PR metadata, dependencies, CI, review state, target branch, and current remote parity before each merge.

Use this merge order:

```text
shared contracts
-> Brain/OpenFang gateway
-> service repository
-> Space adapter
-> V1 submodule pin
-> integration tests
-> deployment configuration
-> Golden Path
-> release tag
```

Normal green `docs` and `code` merges covered by `standing-autonomy:v1` may be performed by the V1 orchestrator without routine user interaction. Deployment, destructive actions, breaking contracts, database migrations, secrets, Proxmox mutations, large repository moves, and cleanup require request-specific authority; never expand the standing mandate into a new risk class.

After every merge, refresh remote state and perform post-merge verification before advancing to the next dependency. Verify each submodule pin as its own parent-repository change. Never delete a branch or worktree under standing autonomy, and never auto-stash, force-push, discard foreign changes, or merge directly from a task session.

The sequence documents the required MVP Brain/OpenFang integration chain. Treat OpenFang as the only Product-Runtime execution boundary, while requiring separate task approval and live evidence for every gateway, agent, MCP/tool, provider, cost, approval, and Golden-Path claim.
