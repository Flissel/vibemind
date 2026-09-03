# MiroFish V1 simulation contract family

MiroFish V1 is an offline, provider-neutral contract family for one bounded
Graph → Simulation → Forecast session. Its sole Space identity is `mirofish`.
It defines data validation only: it does not start a graph build or simulation,
contact MiroFish, select a model, store credentials, call a URL, persist state,
grant approval, control OpenFang, deploy anything, or claim a live Golden Path.

## Documents

1. `MiroFishSimulationRequestV1` (`mirofish-simulation-request`) accepts a
   chat-orchestrated objective plus opaque project/task/trace/input artifact and
   input evidence references. It always requests the three accountable outputs:
   graph, simulation, and forecast artifacts. Its SHA-256 request hash,
   clarification state, hard bounds, quote/approval correlations, and
   idempotency key are immutable inputs to the remainder of the chain. The key
   is deterministic and exact: `mirofish:<request_id>`.
2. `MiroFishSimulationPlanV1` (`mirofish-simulation-plan`) binds those exact
   inputs and bounds to the only permitted phase order: `graph_build`, then
   `simulation`, then `forecast`. Its positive version and SHA-256 plan hash
   prevent a run from silently changing plan or output semantics.
3. `MiroFishSimulationRunRequestV1` (`mirofish-simulation-run-request`) binds
   one opaque external-run reference to the request, plan, inputs, idempotency,
   approval/quote correlations, and exact approved limits.
4. `MiroFishSimulationRunStateV1` (`mirofish-simulation-run-state`) is the
   durable, queryable state projection. It carries consecutive revisions,
   monotonic timezone-aware history, bounded progress with a readback reference,
   counters, and deterministic minor-unit cost. It permits pause only with a
   checkpoint and permits resume only with that same checkpoint. A cancellation
   request must carry a cancellation reference and may resolve only as
   `cancelled` or `unavailable`; it cannot later become successful. A terminal
   `timed_out` is explicit, and a completed success must report full progress.
5. `MiroFishSimulationEvidenceV1` (`mirofish-simulation-evidence`) records one
   terminal observation. A success includes one opaque external receipt plus
   graph, simulation, and forecast artifact records. Each record requires an
   opaque artifact, provenance, readback, verification reference, and an exact
   lowercase SHA-256 content hash.
6. `MiroFishSimulationResultV1` (`mirofish-simulation-result`) repeats the
   bound run identity, evidence identity, terminal timestamps, counters, cost,
   receipt, artifact/readback/verification references, and satisfied criteria.

## Offline bundle validation

`validate_mirofish_simulation_bundle(...)` accepts exactly the six documents.
It rejects unresolved clarification; any identity, input, hash, idempotency,
limit, cost, timestamp, progress, counter, evidence, or result drift; reordered
or incomplete phases; illegal lifecycle transitions or terminal reopening;
resume without the paused checkpoint; success after a cancellation request; and
timeouts above the approved limit.

Success is deliberately fail-closed. It requires all three non-empty artifact
records, unique artifact/readback/verification references, content hashes,
provenance, verification and readback bindings, an external receipt, exactly
three artifact and verification counts, positive bounded work, matching state /
evidence / result costs, and every immutable success criterion. HTTP 2xx,
empty results, a mock, a no-op, a status-code field, or a static registry entry
are not success evidence.

Reference semantics are typed even though all references retain the existing
canonical V1 opaque-ID grammar: request, project, task, trace, plan, run,
session, evidence, artifact, quote, approval, checkpoint, cancellation, and
receipt fields each require their corresponding canonical prefix. A valid
opaque ID of the wrong kind is rejected.

Portable collection limits apply before execution: each input artifact/evidence
list is at most 20 entries, clarification has at most 20 questions of at most
2,000 characters, lifecycle history has at most 128 events, each phase has at
most two dependencies, and result readback/verification lists are at most
three entries. Successful results remain bound to exactly three artifact,
readback, and verification references.

Every document and nested record is closed. There are no provider, credential,
secret, token, API key, runtime, model, URL, endpoint, webhook, command, shell,
or free success fields. Opaque references are correlations only and do not prove
provider availability, authorization, persistence, or execution.

Run the focused offline suite with:

```powershell
python -m pytest tests/contracts/mirofish/test_mirofish_simulation_contracts.py -q
```
