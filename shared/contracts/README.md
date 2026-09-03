# V1 Shared Contract Core

This directory contains language-neutral JSON Schema contracts for exchanging
task context. It has no runtime, execution, approval, permission,
provider, cost, database, or projection authority.

Use `validate_document(document_type, parsed_json)` from `validate.py` for
deterministic offline validation. The accepted `document_type` values are
`task-brief`, `task-event`, `evidence-ref`, `task-handoff`, `brain-plan`,
`channel-intent`, `channel-result`, `space-execution-contract`, `research-request`,
`research-plan`, `research-job`, `source-evidence`, `citation`,
`research-result`, and `research-idea-handoff`.

Schedule V1 schemas live under `schedule/v1/`. Use `schedule-request`,
`schedule-definition`, `schedule-change`, `schedule-state`, and
`schedule-run-evidence` with `validate_document(...)`; use
`validate_schedule_bundle(...)` for their complete offline reference chain.
They are documented in [Schedule V1](../../docs/spaces/schedule/contract.md).

n8n V1 schemas live under `n8n/v1/`. Use `workflow-request`,
`workflow-definition-ref`, `workflow-change`, `workflow-run-request`,
`workflow-run-state`, and `workflow-run-evidence` with
`validate_document(...)`; use `validate_n8n_bundle(...)` for the exact
six-document offline reference chain. They are documented in
[n8n V1](../../docs/spaces/n8n/contract.md).

AgentFarm V1 schemas live under `agentfarm/v1/`. Use `agent-team-request`,
`agent-team-plan`, `agent-team-run-request`, `agent-task-event`,
`agent-team-run-state`, and `agent-team-run-evidence` with
`validate_document(...)`; use `validate_agentfarm_bundle(...)` for the exact
six-document offline reference chain. Runtime-source admission is deliberately
separate: validate `agentfarm-runtime-source-provenance` and its bound
`agent-team-request` with `validate_agentfarm_runtime_admission_bundle(...)`.
The subsequent exact composite OpenFang handoff admission uses
`agentfarm-openfang-handoff-admission` with
`validate_agentfarm_openfang_handoff_bundle(...)`. It composes the existing
Channel/Brain/Space admission with source, request, trace, correlation,
approval, quote/cost, and idempotency continuity while declaring only a pending
OpenFang admission. Its request `task_ref` is explicitly mapped to one admitted
Brain task node. The AgentFarm Space contract must carry the OpenFang executor,
approval-policy, and cost-policy identities, and Channel receipt must not follow
request creation. It has no dispatch or execution authority.
They are documented in
[AgentFarm V1](../../docs/spaces/agentfarm/contract.md).

`agentfarm_runtime_source_resolver.py` composes that exact admission validator
with bounded, local-only Git object checks. Call
`resolve_agentfarm_runtime_source_admission(documents, local_repository,
allowed_root, expected_canonical_repository_identity)` only with a
caller-trusted canonical identity. On success it returns an immutable
`AgentFarmVerifiedLocalSourceReceipt` claiming only `verified_local_source`.
It never selects or owns a repository, nor claims that a runtime is enabled,
built, routed, deployed, reachable, approved, or executed.

Rowboat V1 schemas live under `rowboat/v1/`. Use `knowledge-request`,
`knowledge-plan`, `knowledge-run-request`, `knowledge-run-state`, and
`knowledge-result` with `validate_document(...)`; use
`validate_rowboat_bundle(...)` for the exact five-document, source-grounded
offline knowledge chain. They are documented in
[Rowboat V1](../../docs/spaces/rowboat/contract.md).

Coding V1 schemas live under `coding/v1/`. Use `code-job-request`,
`code-job-plan`, `code-job-run-request`, `code-job-run-state`, and
`code-job-result` with `validate_document(...)`; use
`validate_code_job_bundle(...)` for the exact five-document, bounded offline
code-job chain. They are documented in
[Coding V1](../../docs/spaces/coding/contract.md).

Video V1 schemas live under `video/v1/`. Use `video-job-request`,
`video-job-plan`, `video-job-run-request`, `video-job-run-state`, and
`video-job-result` with `validate_document(...)`; use
`validate_video_job_bundle(...)` for the exact five-document, bounded offline
video, audio, and vision job chain. They are documented in
[Video V1](../../docs/spaces/video/contract.md).

MiroFish V1 schemas live under `mirofish/v1/`. Use
`mirofish-simulation-request`, `mirofish-simulation-plan`,
`mirofish-simulation-run-request`, `mirofish-simulation-run-state`,
`mirofish-simulation-evidence`, and `mirofish-simulation-result` with
`validate_document(...)`; use `validate_mirofish_simulation_bundle(...)` for
the exact six-document, external-evidence-gated offline chain. They are
documented in [MiroFish V1](../../docs/spaces/mirofish/contract.md).

Desktop V1 schemas live under `desktop/v1/`. Use `desktop-action-request`,
`desktop-action-plan`, `desktop-action-run-request`, `desktop-action-run-state`,
and `desktop-action-result` with `validate_document(...)`; use
`validate_desktop_bundle(...)` for their exact five-document offline reference
chain. They are documented in [Desktop V1](../../docs/spaces/desktop/contract.md).

Minibook V1 schemas live under `minibook/v1/`. Use
`minibook-projection-request`, `minibook-projection-snapshot`,
`minibook-projection-delta`, and `minibook-projection-evidence` with
`validate_document(...)`; use `validate_minibook_projection_bundle(...)` for
their exact four-document offline projection chain. They are documented in
[Minibook V1](../../docs/spaces/minibook/contract.md). The bundle has no
lifecycle, approval, execution, provider, runtime, or persistence authority.

Flowzen V1 schemas live under `flowzen/v1/`. Use `flowzen-checkin`,
`flowzen-recommendation`, `flowzen-acceptance`, and
`flowzen-acceptance-evidence` with `validate_document(...)`; use
`validate_flowzen_bundle(...)` for the exact four-document, offline chain.
Check-in and recommendation are read-only; acceptance is a separate explicit
mutation and succeeds only with terminal acceptance readback evidence. They are
documented in [Flowzen V1](../../docs/spaces/flowzen/contract.md).

Install the scoped validator dependency with:

```powershell
python -m pip install -r shared/contracts/requirements.txt
```

The authoritative grammar, ownership boundaries, and compatibility policy are
in [the contract documentation](../../docs/contracts/v1-shared-contract-core.md).
The declarative Brain plan contract and its offline graph checks are documented
in [BrainPlanV1](../../docs/contracts/brain-plan-v1.md).
The closed Brain-owned planning lifecycle through the explicit
`execution_deferred` boundary is documented in
[BrainPlanLifecycleV1](../../docs/contracts/brain-plan-lifecycle-v1.md). Use
`validate_brain_plan_lifecycle_bundle(channel_intent, brain_plan,
space_execution_contracts, lifecycle)` to reuse admission validation first,
then require exact correlation, plan, participating-Space, revision,
timestamp, transition, and terminal-state continuity. This is offline
control-plane validation only; it provides no execution, provider,
application, approval, evidence-acceptance, or success authority.

`BrainOpenFangHandoffV1` is the separate closed, provider-neutral handoff of
one admitted cognitive Brain plan node after its lifecycle reaches
`execution_deferred`. Use
`validate_brain_openfang_handoff_bundle(channel_intent, brain_plan,
space_execution_contracts, lifecycle, handoff)`: it delegates to the existing
Brain lifecycle bundle validator first, then requires exact correlation, plan,
lifecycle revision, task node, canonical Space, and role continuity. The
required `execution_mode: cognitive` and `execution_boundary: openfang` bind
the declared handoff boundary without adding an execution mechanism. Opaque
approval/cost references and the bounded retry declaration are continuity data
only. They do not approve, price, dispatch, select agents/tools/providers, or
claim a runtime result.
The inbound data-only channel envelope is documented in
[ChannelIntentV1](../../docs/contracts/channel-intent-v1.md).
The corresponding outbound user projection is documented in
[ChannelResultV1](../../docs/contracts/channel-result-v1.md). Use
`validate_channel_result_route_bundle(channel_intent, brain_plan,
space_execution_contracts, channel_result)` only after constructing the
complete offline admission bundle. It reuses Brain-plan admission, then
requires exact channel context, plan, and participating-Space continuity. It
does not send a reply, decide approval, dispatch work, evaluate evidence, or
prove application or live success.
The declarative Space-to-policy reference contract and its pinned canonical
identity snapshot are documented in
[SpaceExecutionContractV1](../../docs/contracts/space-execution-contract-v1.md).
Use `validate_brain_plan_admission_bundle(channel_intent, brain_plan,
space_execution_contracts)` to validate one ChannelIntentV1, one BrainPlanV1,
and the complete matching SpaceExecutionContractV1 set as an offline admission
bundle. It validates each document first, then requires the requested and task
spaces to participate, canonical plan spaces, exactly one contract per
participant, no extra contracts, and non-empty task evidence requirements.
Admissible means only that the offline bundle is structurally eligible for
admission; it does not execute, approve, route, health-check, or establish a
Golden Path for any operation.
Research V1 schemas live under `research/v1/`; use
`validate_research_bundle(...)` to validate the complete offline Research
request-to-idea-handoff reference chain. Its contract and authority boundary
are documented in [Research V1](../../docs/spaces/research/contract.md).
