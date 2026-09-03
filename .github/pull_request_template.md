## Summary

Describe what changed, why it is needed, and the exact repository or submodule
scope.

## Governance provenance

Codex sessions fill this in. Outside contributors may write `n/a`.

- Approval: `codex-user-message:<source-thread-UUID>@<RFC3339 timestamp>`
- Parent cockpit: `cockpit-<domain>`
- Request reference: `task-request:<task-id>-vN`
- Handoff: repository-relative path to the versioned task handoff
- Dependencies: declared task IDs and their merge evidence, or `none`
- Merge position: positive position from the approved task request

## Verification

List exact commands and results. Include skipped or unavailable checks.

- [ ] `python -m tools.v1_governance pr check --repo . --request <request.yaml> --handoff <handoff.yaml>` passed
- [ ] Tests and evidence are recorded in the handoff.
- [ ] No deployment, destructive action, or other high-risk change is included without its fresh approval.

## Documentation and risk

- [ ] This pull request has one clear purpose.
- [ ] No secrets, personal data, or machine-specific paths are included.
- [ ] Submodule pointer changes are intentional and documented.
- [ ] Breaking changes and migrations are called out.
- [ ] User-facing documentation and `CHANGELOG.md` are updated when needed.

## Related issues

Closes #
