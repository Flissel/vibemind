# Release checklist

This checklist prepares a public VibeMind release. It does not authorize a
deployment, data migration, credential rotation, or publication by itself.

## 1. Define the release

- Choose the version and intended audience.
- Summarize included features, fixes, breaking changes, and known limitations.
- Confirm every included component and Gitlink is intentional.
- Freeze unrelated changes until the release candidate is verified.

## 2. Verify source and licensing

- Confirm the root worktree and all included submodules are clean.
- Confirm a fresh recursive clone succeeds without private credentials.
- Review root and component licenses, notices, attribution, and redistribution
  requirements.
- Remove generated artifacts, local paths, personal data, and machine-specific
  configuration.
- Run secret scanning over the complete Git history and release artifacts.

## 3. Verify the product

- Run the root checks and every affected component test suite.
- Record skipped tests and unverified external integrations explicitly.
- Perform setup on a clean Windows environment using only public instructions.
- Run `vibemind-start.ps1 -DryRun` before the release-candidate smoke test.
- Confirm health checks, shutdown behavior, and data-persistence expectations.

## 4. Prepare public materials

- Update `README.md`, `CHANGELOG.md`, screenshots, and architecture references.
- Document prerequisites, required API providers, costs, and resource needs.
- List known issues and experimental components.
- Confirm contribution, security, support, and conduct links work.

## 5. Publish with approval

- Obtain maintainer approval for the exact release commit and notes.
- Create an annotated Git tag without rewriting existing tags.
- Build release artifacts from the approved commit in a clean environment.
- Publish checksums and provenance for downloadable artifacts.
- Create the GitHub release and verify every link and download.

Example tag commands after approval:

```powershell
git tag -a vX.Y.Z -m "release: vX.Y.Z"
git push origin vX.Y.Z
```

## 6. After publication

- Re-test the public clone and installation path.
- Monitor security reports and high-impact setup failures.
- Record urgent fixes under a new changelog version; never replace an existing
  release artifact silently.

## VibeMind v1 cut

The concrete, VibeMind-specific execution of this checklist lives in
[`operations/2026-08-30-v1-cut-runbook.md`](operations/2026-08-30-v1-cut-runbook.md):
exclusion list, orphan-snapshot mechanics, submodule pin check, rollback.
