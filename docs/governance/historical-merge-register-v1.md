# Historical merge register v1

This register is a retrospective Git record only. Each row was read from the local `origin/master` first-parent merge history at `47e61bc0e0f16c35ffe258dd3a1a252706a21c6a`. The merge SHA, second parent, source branch text, and author timestamp are Git facts. Git history does not establish approval, parent cockpit, durable request reference, handoff, or dependency-gate evidence; each is explicitly recorded as `evidence-unavailable`.

The register test derives PR #3–#25 directly from the local first-parent history of `origin/master` and compares every merge SHA, source-head SHA, and source branch text. A shallow checkout that does not retain all 23 merge objects fails the test; it never skips verification or falls back to a static register assertion.

## Reconciliation boundary

The closed offline reconciliation ledger records PR #102 merge
`b144452efb3f1d5b8d716015381d215b4bb84350`, PR #103 merge
`206afd2488e8bdfde4c2a25e8ee2eee5dc07e25a`, and the historical Gitlink chain
`b144452efb3f1d5b8d716015381d215b4bb84350` → `vibemind-os`
`459a5a4f6fa7aba65bc69973f04b98d31b300aff` → `voice`
`30ce9cc3892f674fa40fcc1d9df6de59a7501437`. These are historical Git facts
only for the locally verified Outer → `vibemind-os` link. The second
`vibemind-os` → `voice` link is `external-not-locally-git-verified`: the
offline Outer-repository model has no portable Child Gitdir to read its tree
without initializing a submodule checkout, so it must not be described as a
locally verified Git fact. The ledger does not establish runtime, live,
approval, or merge-success claims. The canonical OpenFang task dispositions
`task-openfang-0001-brain-bridge-fail-closed-v1` and
`task-openfang-0002-voice-bridge-fail-closed-v1` are expressly
`external-not-git-verified`.

| PR | Merge SHA | Source head SHA | Source branch text | Merge author timestamp |
| --- | --- | --- | --- | --- |
| #3 | 7f5c1c9fe34080cd5025be555be7b82bbeeb5724 | 08826f4a3a83c96435cfe073a009b8ac655e5465 | Flissel/codex/platform/v1-session-architecture-docs | 2026-07-30T16:55:26+02:00 |
| #4 | b82573234ee683e8cf5e4d7be6a17ad6370084c2 | 8866317094cd7fdca2494b58ed8b3559869e8d13 | Flissel/codex/platform/task-platform-0001-governance-contracts | 2026-07-30T18:14:07+02:00 |
| #5 | 02df18728ce73fc204a295ce873fb1bf21d3b874 | 8482b61c2208d836c824a395d36624059810118b | Flissel/codex/platform/task-platform-0004-session-routines | 2026-07-30T18:33:01+02:00 |
| #6 | 301df5c55b4dd614a7958fed799e2479f7bee94c | 20bca30401b484c361ac74e2fa139f1ef6ca94f4 | Flissel/codex/platform/task-platform-0002-git-worktree-gate | 2026-07-30T18:50:43+02:00 |
| #7 | a400002fbaf20bb47d089acefc34338f75115521 | a5f3fbfd1e24f2bccc212bd2aaaec5aad51c104f | Flissel/codex/platform/task-platform-0003-pr-readiness | 2026-07-31T02:14:10+02:00 |
| #8 | f135f8e581cf2368092e248f13f8f266883d73c1 | aba946b0e9ade2d366ba45603acad5f52c0a22d2 | Flissel/codex/shared/task-shared-0001-contract-core | 2026-07-31T02:27:14+02:00 |
| #9 | 6b10e2847fd4b76e0b89b1457764e0f46d649641 | 9dd65195ac68eef63636c0925b1a394417af0c72 | Flissel/codex/deployment/task-deployment-0001-readiness-preflight | 2026-07-31T02:30:39+02:00 |
| #10 | 332c9d6cbfbd8c90a34cd3ee3a99c58106618aa1 | a56d82a2af53a3fd456c00af116b5409b4ee7780 | Flissel/codex/brain/task-brain-0001-plan-contract | 2026-07-31T02:42:23+02:00 |
| #11 | e44dc4fb554ae194f76c51abb0f0b9472e93dd23 | 116adc65524bbd129739bdbc45f8817d7348ad02 | Flissel/codex/channels/task-channels-0001-intent-contract | 2026-07-31T02:50:07+02:00 |
| #12 | b587ebe48bde670948c8a7b18f564fa51c005a3d | 1bab298b9a22e7c0410f1757cf0722d87990fdfc | Flissel/codex/git/task-git-0003-submodule-readiness | 2026-07-31T03:11:53+02:00 |
| #13 | f1aa0471f76212104dd7c6309d1ec2f82419ef5c | 5c2f533b94d4b4fd39c703d5a5039382f00beac7 | Flissel/codex/shared/task-shared-0002-space-execution-contract-recovery | 2026-07-31T03:46:43+02:00 |
| #14 | c399b0e632384d0c683cd609d8af6419ea162941 | 1a2b422ae03042f1098890e7c71167b5a6124c9f | Flissel/codex/ideas/task-ideas-0002-parent-pin | 2026-07-31T04:17:01+02:00 |
| #15 | c4be8de3dbfa7538ba991d0d10f3fe99b0583cca | 05049bfd16e7b3837c2f34ae801c9141df279ad9 | Flissel/codex/bubbles/task-bubbles-0002-parent-pin | 2026-07-31T04:41:55+02:00 |
| #16 | e17d5024688c2d59d51cea87b0be30d239ade246 | 1670f9a76d4ca614c0715ea7683428791da38192 | Flissel/codex/research/task-research-0001-evidence-contract-v1 | 2026-07-31T05:03:00+02:00 |
| #17 | 5b06422668a21a79b706b553f2405eee8036afd4 | 67d4e6e872b3cbf45f94013857cf301555dde7b4 | Flissel/codex/schedule/task-schedule-0001-contract-v1 | 2026-07-31T05:28:04+02:00 |
| #18 | e83932463dad7d81d5a83298b9f7b4417cfb1d51 | a0373553cf239b6f5cafff9666507229e866a550 | Flissel/codex/n8n/task-n8n-0001-workflow-contract-v1 | 2026-07-31T05:57:22+02:00 |
| #19 | dfbc81727ff0f100ab8114f390177f8e275df852 | b1053b82d585af9e9f73d967b355bdd2721adc88 | Flissel/codex/agentfarm/task-agentfarm-0001-team-contract-v1 | 2026-07-31T06:28:07+02:00 |
| #20 | bff47e032a40121921ccbe89e4f5d61fdce5b1f4 | edeb4608bb6777b414236de7e8e0eb2938882aa2 | Flissel/codex/rowboat/task-rowboat-0001-knowledge-contract-v1 | 2026-07-31T06:51:17+02:00 |
| #21 | a37aced311588f3c673b1243d07990ac1fe2e0c2 | 738bcdfb8fdc2500c2c09b423e01b2f46f3e17e9 | Flissel/codex/coding/task-coding-0001-code-job-contract-v1 | 2026-07-31T07:20:22+02:00 |
| #22 | d389b666bdae98205d74c965cb346ee988c8e05a | 5ddb5edd20ff78600f4282bf6e8f17829b16f6ec | Flissel/codex/desktop/task-desktop-0001-action-contract-v1 | 2026-07-31T07:42:04+02:00 |
| #23 | aeafa247bc30daacdfde931a740b2cc2f5b057dc | ca8e9daee36a51266824a4ac09408f7ed31182d7 | Flissel/codex/minibook/task-minibook-0001-projection-contract-v1 | 2026-07-31T08:01:44+02:00 |
| #24 | b5dfd7bf47b1bbf0955ece1dd28a687a345ade3c | 05f7a638c524f3e615d5e3ba12f160b9d46834e7 | Flissel/codex/flowzen/task-flowzen-0001-recommendation-contract-v1 | 2026-07-31T08:21:24+02:00 |
| #25 | 47e61bc0e0f16c35ffe258dd3a1a252706a21c6a | 0e6a7ce7a6e570e9dc71ed0693bc98b20b2cf22e | Flissel/codex/mirofish/task-mirofish-0001-simulation-contract-v1 | 2026-07-31T08:34:34+02:00 |

| PR | Approval | Parent cockpit | Request reference | Handoff | Dependency gate |
| --- | --- | --- | --- | --- | --- |
| #3 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #4 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #5 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #6 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #7 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #8 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #9 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #10 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #11 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #12 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #13 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #14 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #15 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #16 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #17 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #18 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #19 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #20 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #21 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #22 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #23 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #24 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
| #25 | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable | evidence-unavailable |
