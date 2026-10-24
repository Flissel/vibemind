# Changelog

Notable user-facing changes to VibeMind will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and release versions should follow [Semantic Versioning](https://semver.org/)
when the public release process is adopted.

## [Unreleased]

### Changed

- README rewritten for the open beta: product summary, "What works today" and
  "Known limitations" lists, hardware notes, community links and a clearer
  license summary (MIT core, some optional components under other licenses).
- Removed the outdated note that the root repository and `vibemind-os` were
  private; every repository in the recursive tree is public.
- Fixed the CI badge and the push trigger of the open-source checks to use the
  `main` branch.
- The optional `vibevideo_deepfake` (private) and TriBE v2 (CC BY-NC 4.0)
  submodules are no longer fetched by a recursive clone (`update = none` in
  `vibemind-os/.gitmodules`).

## [0.1.0] - 2026-09-03

First public release — an early one. The version says 0.1 on purpose:
the system runs, but the public tree is a subset and several parts are still
being reconciled. Read these limitations before relying on it:

- **The V1 governance layer is not included.** The contract core, per-space
  JSON schemas and governance CI gate live on a separate line that is not yet
  reconciled with the operational one.
- **Every submodule is now public.** The face-swap component
  (`spaces/video/vibevideo_deepfake`) is licensed under a RAIL-based
  synthetic-media license with binding restrictions on consent, labelling of
  synthetic output, impersonation, intimate imagery and surveillance — not
  under this repository's MIT. The OpenClaude runtime was removed entirely.
- **Third-party skill collections are not shipped.** They carried no license
  and are development tooling rather than product; `THIRD_PARTY.md` records
  where they came from.
- **Licensing is MIT with exceptions** — one AGPL subtree, one non-commercial
  subtree, one non-OSI license. See `THIRD_PARTY.md`.
- **The supported path is the documented quickstart**, not the full service
  swarm, which needs substantially more resources than a laptop.

Release-preparation changes since the last snapshot:

- Added the third-party inventory, a secret-hygiene CI gate, a root
  `.env.example`, and the missing build recipe for the `vibemind-brain-core`
  image that six services share.
- Fixed recursive clones: stale `.gitmodules` entries removed, the renamed
  coding-engine URL corrected, and submodule pins that pointed at commits
  published nowhere repaired.
- Removed personal data from the source tree; the Telegram send allowlist is
  now environment-configured and fails closed when unset.

## Development history before 0.1.0

### Added

- Binding multi-session program charter: per-session individual user approval
  for cockpit and implementation sessions, central PR/merge/verification
  orchestration, and the bounded-parallelism model.
- Repo-first derived session-request queue for the cockpit portfolio and the
  registered implementation task proposals, pending individual user approval.
- Governance validator support for the orchestrator-brokered individual
  approval reference form `claude-user-message:<session-id>@<timestamp>`.
- Recorded wave-1 cockpit creation approvals (Git, Shared, Brain, Deployment)
  in the cockpit approval ledger.
- Captain Cook naming directive for the AgentFarm Space (display name now,
  canonical rename queued as its own task).
- Maintenance delegation (charter amendment 4a): the orchestrator activates
  the remaining cockpit portfolio and admits routine docs/code implementation
  sessions under a durable user directive; high-risk classes stay user-gated.
- Architecture decisions of 2026-08-13 on agent-role selection, arch-gap
  dispatch, multi-verb decomposition and non-space intents, with their
  derived implementation tasks.
- Safe submodule checkout workflow runbook with recorded evidence.
- Deterministic image references across the Proxmox compose manifests, with a
  fail-closed determinism gate and the re-pinning procedure.

- Root onboarding and recursive clone documentation.
- Public architecture overview and standalone visual diagram.
- Detailed system, deployment, data-ownership, failure and evidence architecture.
- Source-backed documentation for all 13 canonical Spaces.
- Repository-first documentation coverage and drift audit.
- Open-source contribution, conduct, security, support, and release policies.
- Dependency-light pull-request checks and GitHub contribution templates.
