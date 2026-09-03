# Security Policy

## Supported versions

Security fixes are applied to the current default branch and, when practical,
the latest published release. Older snapshots and third-party submodules may
require fixes in their upstream repositories.

## Report a vulnerability privately

Please do not disclose vulnerabilities in public issues, discussions, or pull
requests.

Use GitHub's **Report a vulnerability** option on the repository Security page
to open a private security advisory. Include:

- the affected component and commit or version;
- impact and realistic attack scenario;
- steps to reproduce or a minimal proof of concept;
- suggested mitigation, if known;
- whether the report concerns a nested submodule or upstream project.

The maintainer will acknowledge the report, assess scope, and coordinate a fix
and disclosure. Response times are best effort; this community project does not
currently provide a formal security SLA or bug bounty.

## Credentials and personal data

If a live credential was exposed, revoke and rotate it immediately before doing
anything else. Rewriting Git history alone does not invalidate a compromised
secret. Do not attach raw `.env` files, access tokens, production logs, or
personal data to a report.

## Scope

Reports about code owned by a Git submodule should also be sent to that
component's upstream security contact. The root project can coordinate a safe
Gitlink update but cannot promise fixes for independent upstream projects.
