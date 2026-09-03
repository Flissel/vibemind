# BrainPlanV1

## Purpose and authority

`BrainPlanV1` is a versioned, language-neutral data contract for a plan owned
by Brain as the control plane. Brain interprets intent, creates and owns the
task lifecycle, and validates results against the plan's success criteria and
evidence requirements. Shared owns the schema, identifier grammar, fixtures,
and deterministic offline validation.

The plan is declarative. It describes work but cannot directly call an
application or provide an execution instruction. OpenFang is the MVP execution
boundary, but remains outside this planning contract: the contract contains no
execution target, agent configuration, provider, cost, permission, or
approval-runtime field. A separately versioned Brain/OpenFang gateway must
translate an admitted plan without weakening Brain's planning authority.

| Owner | Responsibility in this contract | Explicitly not owned here |
| --- | --- | --- |
| Brain | intent interpretation, plan creation, lifecycle, result validation | schema changes, application execution |
| Shared | `BrainPlanV1` schema, IDs, fixtures, offline validation | routing, lifecycle decisions, execution |
| Applications | produce work artifacts and evidence | accepting direct plan calls |
| OpenFang | execute admitted work through separately versioned gateway contracts | provider, permission, approval, or execution data in this plan |

## Data shape

The root object requires `contract_version: "v1"`, a canonical `plan_id`,
`intent`, `participating_spaces`, and `tasks`.

- `intent` records the plan's human-readable `summary`, non-empty `context`,
  and `requested_by` value.
- `participating_spaces` declares every canonical `space_id` that may be used
  by a task. Each entry carries declarative `roles`; a role has a name and its
  `required_agent_count`. It does not configure agents or start them.
- `tasks` is an ordered DAG. Each task has a stable local `node_id`, a unique
  positive `order`, a summary, one or more participating `space_ids`, and its
  `depends_on` node IDs.
- Each task states non-empty `success_criteria` and
  `evidence_requirements`. An evidence requirement names only an expected
  evidence type and description; it is not evidence itself and does not mark
  a result successful.

`plan_id` uses the Shared V1 grammar:

```text
plan_v1_<ULID>
```

## Canonical space and alias rule

`space_id` values in a `BrainPlanV1` must already be canonical. Any alias is
normalized only at the ingress boundary before a plan is created. Shared does
not normalize aliases, look up a registry, or modify a registry; it preserves
the supplied canonical values as data.

Offline validation confirms that each task's `space_ids` is declared in that
same plan's `participating_spaces`. Determining whether a canonical value is
currently registered remains the responsibility of the ingress producer and
the canonical Space registry, not this contract.

## Offline validation

`validate_document("brain-plan", parsed_json)` loads the Draft 2020-12
schema and then, without any external access, rejects:

- direct `application_target` fields;
- duplicate participating `space_id`, task `node_id`, or task `order` values;
- task spaces absent from `participating_spaces`;
- dependencies on missing task nodes;
- cycles in the task graph; and
- dependencies whose `order` does not precede the dependent task.

The schema rejects all unrecognized fields as well. Validation is structural
only: passing it neither executes work nor proves completion, evidence
acceptance, approval, or application success.

## Admission bundle

`validate_brain_plan_admission_bundle(channel_intent, brain_plan,
space_execution_contracts)` validates a deterministic, offline composition of
one `ChannelIntentV1`, one `BrainPlanV1`, and a sequence of
`SpaceExecutionContractV1` documents. It first applies the existing individual
validators, then requires all of the following:

- the channel's `requested_space_id` participates in the plan, when present;
- every participating plan space is canonical according to the pinned Shared
  identity snapshot;
- every participating space has exactly one matching execution contract, with
  no unparticipating execution contracts; and
- every task's spaces participate in the plan and are covered by that contract
  set, while retaining at least one evidence requirement.

The function does not normalize aliases or consult a registry. It has no
OpenFang, executor, adapter, application, ledger, provider, cost, approval,
runtime, health, execution, or Golden-Path authority. A successful return
means only that the supplied documents are *admissible* offline; it never
means that work was executed, approved, live, healthy, succeeded, or completed.

Run the deterministic coverage from the repository root:

```powershell
python -m pytest tests/contracts/test_v1_contracts.py -q
```
