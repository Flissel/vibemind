# ChannelResultV1

## Purpose and authority

`ChannelResultV1` is a versioned, language-neutral outbound projection for a
user-facing Channel after Brain has admitted a plan. It is data only: it
preserves the identity of the route that produced the projection but does not
own a task lifecycle, perform a reply, or call an application.

| Owner | Responsibility in this contract | Explicitly not owned here |
| --- | --- | --- |
| Channels | present the projection to the user | planning, lifecycle, approval, execution, or evidence acceptance |
| Brain | admission, planning, lifecycle, and result evaluation | Channel transport or Shared schema changes |
| Shared | schema, fixtures, and offline route validation | routing, dispatch, approval, application, or provider access |
| OpenFang | execution and approval boundary outside this contract | authority encoded in a result projection |
| Applications | produce artifacts and evidence | direct Channel calls or user-projection authority |

## Data shape

The closed root object requires `contract_version: "v1"`, the ingress
`correlation_id`, `channel_kind`, actor and session context, a `plan_id`, the
ordered `participating_space_ids`, a projection `status`, and a short
user-facing `summary`.

- `correlation_id`, `channel_kind`, `actor_context`, and `session_context` are
  copied exactly from the admitted `ChannelIntentV1`.
- `plan_id` and `participating_space_ids` are copied exactly from the admitted
  `BrainPlanV1`; admission has already established that those Spaces are
  canonical and covered by matching execution contracts.
- `status` is solely a user projection (`pending`, `in_progress`,
  `waiting_for_approval`, `succeeded`, `failed`, `cancelled`, or
  `unavailable`). It neither changes nor proves Brain lifecycle state.
- A `waiting_for_approval` projection requires only an opaque `approval_ref`
  with the exact `approval_v1_<ULID>` grammar. It contains no decision, grant,
  permission, or authority claim; the opaque reference does not prove approval.
- A `succeeded` projection requires at least one `evidence_refs` entry. Each
  entry is an `evidence_v1_*` reference, not an embedded acceptance decision.
  It proves neither that evidence was accepted nor that a live application
  action succeeded.

The schema rejects all unknown fields. In particular it carries no runtime,
target, command, URL, provider, agent, credential, token, or dispatch data.

## Offline validation

`validate_channel_result_route_bundle(channel_intent, brain_plan,
space_execution_contracts, channel_result)` first invokes
`validate_brain_plan_admission_bundle(...)`, then validates the closed result
schema and exact route continuity. It performs no Channel, OpenFang, adapter,
application, registry, database, provider, network, service, approval, or
execution access.

Passing validation means only that the supplied documents form a structurally
continuous offline projection. It does not authenticate an actor, send a
message, approve work, dispatch a target, accept evidence, prove application
readback, prove live success, or establish a Golden Path.

Run the scoped deterministic suite from the repository root:

```powershell
python -m pytest tests/contracts/test_v1_contracts.py -q
```
