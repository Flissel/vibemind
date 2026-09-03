# Contributing to VibeMind

Thanks for helping improve VibeMind. This repository coordinates many languages,
services, and Git submodules, so small, focused pull requests are the easiest to
review and integrate safely.

## Before you start

- Search existing issues and pull requests for related work.
- Open an issue before a large architectural change, migration, or new runtime
  dependency.
- Never include API keys, tokens, private URLs, personal data, or generated
  `.env` files.
- Read the component-level contribution guide when working inside a submodule.

## Set up a development checkout

Fork the repository, then clone your fork recursively:

```powershell
git clone --recurse-submodules https://github.com/<your-user>/Vibemind_V1.git
Set-Location Vibemind_V1
git remote add upstream https://github.com/Flissel/Vibemind_V1.git
pwsh -File .\setup.ps1
```

Create a branch from the current upstream default branch:

```powershell
git fetch upstream
git switch -c feat/short-description upstream/master
```

Use a suitable prefix such as `feat/`, `fix/`, `docs/`, `test/`, or `chore/`.

## Make focused changes

- Follow the style of the component you are modifying.
- Add or update tests for behavior changes.
- Keep unrelated formatting and cleanup out of the pull request.
- Use project-local logging; do not add committed `console.log` debugging.
- Prefer strict types. In TypeScript, do not introduce `any`; use `unknown` and
  narrow it.
- Use Conventional Commit messages, for example `docs: add public setup guide`.

### Submodule changes

Changes inside a submodule belong to that component repository:

1. Create a branch and pull request in the submodule.
2. Test and merge the component change there.
3. Update the parent repository's Gitlink in a separate, explicit change.
4. State the old and new component commit IDs in the parent pull request.

Do not accidentally commit a dirty submodule or update a Gitlink as part of an
unrelated change.

## Test your change

Run the smallest relevant test first, followed by the broader component suite.
The root's dependency-light test is:

```powershell
python -m pytest tools/mcp_sync -q
```

For PowerShell scripts, verify parsing and run their `-DryRun` mode when one is
available. Never use production credentials or external side effects in tests.

## Pull-request checklist

- [ ] The change has one clear purpose.
- [ ] Tests cover changed behavior and pass locally.
- [ ] Setup, configuration, and user-facing behavior are documented.
- [ ] No secrets or sensitive data are present in the diff or history.
- [ ] Submodule pointers are intentional and separately explained.
- [ ] Breaking changes and migration steps are called out prominently.
- [ ] The changelog is updated when the change is user-visible.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
