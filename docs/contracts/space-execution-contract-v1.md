# SpaceExecutionContractV1

## Purpose and authority

`SpaceExecutionContractV1` is a versioned, language-neutral declaration that
ties one canonical Space identity to named policy and verification references.
Shared owns the schema, identity snapshot, fixture set, and offline validation.
It has no execution, approval, health, cost, provider, permission, or Golden
Path authority.

| Owner | Responsibility in this contract | Explicitly not owned here |
| --- | --- | --- |
| Shared | schema, canonical Space snapshot, offline validation | registry mutation, routing, execution, lifecycle |
| Brain | future interpretation and lifecycle decisions | schema ownership or execution proof |
| OpenFang | execution, permissions, approvals, providers, and costs | shared contract ownership |
| Applications | health checks, Golden Paths, artifacts, and evidence | direct contract execution |

## Data shape

The closed root object requires exactly:

- `contract_version: "v1"`;
- `contract_id` matching `space_execution_contract_v1_<ULID>`;
- canonical `space_id`;
- `executor_id` matching `executor:<lowercase-name>`;
- `approval_policy_ref` matching `approval-policy:<lowercase-name>`;
- `cost_policy_ref` matching `cost-policy:<lowercase-name>`;
- `healthcheck_ref` matching `healthcheck:<lowercase-name>`; and
- `golden_path_ref` matching `golden-path:<lowercase-name>`.

The reference fields are opaque declarative names. They are neither URLs nor
commands and do not identify a provider or contain credentials. All objects
are closed, so free `command`, `url`, `provider`, credential, target, and other
runtime fields are rejected.

## Canonical identity snapshot

The schema has a fixed canonical `space_id` enum from
[`space-identity-snapshot-v1.json`](../../shared/contracts/snapshots/space-identity-snapshot-v1.json).
That outer-repository snapshot was captured on 2026-08-01 from the cleanroom
registry at VibeMind-OS gitlink pin
`227f7e6edf2ce6cbec9bcdab45498364dbe9cdfd`, path
`config/space_agent_registry.yml`.

Its complete V1 set is `bubbles`, `ideas`, `coding`, `desktop`, `research`,
`rowboat`, `minibook`, `schedule`, `n8n`, `agentfarm`, `video`, `flowzen`, and
`mirofish`. Ingress aliases `autogen`, `roarboot`, and `shuttles` are explicitly
not canonical and are rejected; alias normalization remains an ingress concern.

When the nested repository is initialized, compare it without mutation:

```powershell
python -c "from pathlib import Path; from shared.contracts.validate import verify_space_identity_snapshot; result = verify_space_identity_snapshot(Path('vibemind-os/config/space_agent_registry.yml')); print(result); raise SystemExit(result.status != 'verified')"
```

The comparison returns `verified`, `drift`, or `registry-unavailable`.
`registry-unavailable` is explicit and exits non-zero in the command above; it
is not a validation success. The checker is read-only and never initializes,
fetches, or changes the submodule.

## Offline validation and non-claims

Use `validate_document("space-execution-contract", parsed_json)` for
deterministic Draft 2020-12 validation. A valid document only proves that the
declaration has the required shape and reference grammar. It does not execute
anything, approve an action, prove approval exists, settle or authorize cost,
run a health check, or prove a Golden Path has succeeded.

`BrainPlanV1` intentionally remains unchanged. A later Brain integration must
be separately designed as an additive, backwards-compatible contract change.

Run the focused checks from the repository root:

```powershell
python -m pytest tests/contracts/test_v1_contracts.py -q
```
