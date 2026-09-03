# Brain OpenFang Space Reference Path V1

## Purpose and authority

This provider-neutral reference path describes how a Channel request is
admitted by Brain, deliberately handed to OpenFang, and returned only with
independent evidence. It is an architecture reference, not an executable
contract or a runtime integration.

Brain is the control plane: it interprets `ChannelIntentV1`, owns planning and
admission, and decides when its planning lifecycle reaches
`execution_deferred`. OpenFang is the execution engine: after that boundary it
owns execution policy, runtime permissions, approvals, providers, and cost
handling. A Space owns its agent and adapter selection within OpenFang's
admitted execution scope. No actor takes another actor's authority merely from
a reference in this document.

## Ordered fail-closed path

The reference path is ordered. A later stage is not a substitute for an
earlier stage: no direct fallback is permitted, and an implementation must not skip an unavailable or rejected stage.

| Order | Reference path stage | Required continuity and boundary |
| --- | --- | --- |
| 1 | `ChannelIntentV1` | A Channel creates `correlation_id` and supplies intent only; it does not select a runtime, provider, agent, command, or service. |
| 2 | Brain admission | Brain validates the offline admission bundle and creates or continues `task_id` under the same `correlation_id`; failed admission stops here. |
| 3 | `execution_deferred` | Brain records its explicit handoff boundary. This is neither dispatch nor execution, and it cannot be bypassed by a Channel or Space. |
| 4 | OpenFang execution engine | OpenFang accepts a separately admissible handoff, creates or correlates `approval_id` and `cost_id`, and enforces its execution policy before any runtime work. |
| 5 | Space-Agent | OpenFang addresses the admitted canonical Space and its selected agent only within that policy scope. A cognitive Space-Agent may use an LLM, but it does not obtain approval, provider, or result authority from that use. |
| 6 | MCP/Service adapter | A deterministic MCP/Service adapter does not use an LLM. It performs only the configured adapter operation and returns an auditable receipt or failure to OpenFang; it never replaces a cognitive agent or silently chooses a provider. |
| 7 | independent Truth/Evidence | The independent Truth/Evidence authority validates the relevant receipt, artifact, read-back, or external evidence and records `evidence_id`; transport or tool success alone is insufficient. |
| 8 | `ChannelResultV1` | Only the evidence-qualified result is correlated as `result_id` to the original `correlation_id`, `task_id`, `approval_id`, `cost_id`, and `evidence_id` before the Channel receives a result. |

An unavailable, denied, invalid, or unverifiable stage produces a bounded
failure or pending state at its owning boundary. It must not be converted into
a direct Channel-to-Space call, a Brain-to-provider call, an agent-to-Channel
success, or a substitute evidence claim.

## Correlation and independent proof

The identifiers in the matrix have one correlation purpose only:

| Identifier | Owner at creation | What it correlates | What it does not prove |
| --- | --- | --- | --- |
| `correlation_id` | Channel ingress | the full request/result lineage | admission, execution, or success |
| `task_id` | Brain | the admitted work item | runtime dispatch or completion |
| `approval_id` | OpenFang | the policy decision for executable work | that an external action occurred |
| `cost_id` | OpenFang | the cost-policy or ledger record | cost settlement or provider billing |
| `evidence_id` | independent Truth/Evidence authority | accepted evidence for the asserted result | that a provider or transport was available |
| `result_id` | result authority | the Channel-facing result record | that every static reference is live |

Truth/Evidence is independent of the actor making the claim. It must be able
to reject a missing, contradictory, or insufficient receipt. A deterministic
adapter receipt may be evidence input, but is never by itself an accepted
result; the cognitive Space-Agent is likewise not its own evidence authority.

## Static and configured non-claims

Static reference data may name a contract version, canonical Space identity,
adapter kind, policy reference, or expected evidence type. Configured reference
data may additionally name an installed adapter, a registered agent identity,
or a configured policy. Neither category is a runtime observation.

| Reference state | May establish | Explicit non-claim |
| --- | --- | --- |
| Static reference | declarative shape and identifier grammar | does not prove runtime reachability, a loaded runtime, a provider connection, or an executed operation |
| Configured reference | that configuration was supplied to the inspected boundary | does not prove approval; does not prove cost settlement; does not prove evidence acceptance; and does not prove a successful result |
| Independent evidence | only the claim covered by the accepted evidence | does not prove unrelated live health, future availability, or a Golden Path |

This document does not initialize a child repository, make a network request,
invoke a runtime, call MCP, create an agent, submit approval, authorize or
settle cost, or assert that any static or configured reference is reachable.
It therefore makes no live-execution, provider-health, or successful-result
claim.

## Review use

Review an implementation against the matrix in order: retain the same
`correlation_id`; preserve Brain's admission and `execution_deferred` boundary;
let OpenFang own execution, approval, and cost decisions; select either a
cognitive Space-Agent or a deterministic MCP/Service adapter without conflating
them; require independent Truth/Evidence; and return a correlated
`ChannelResultV1` only to the evidence level actually established.

Offline review of this document is useful for static architecture alignment
only. Runtime, network, child-repository initialization, deployment, and live
provider verification remain separate fail-closed work.
