# AgentFarm V1 Offline Contract

`agentfarm` is the sole persisted Space identity. `autogen` is permitted only as
the optional `ingress_alias` on `AgentTeamRequestV1`; it is never a `space_id`.

The offline validator accepts exactly these six Draft-2020-12 documents:

1. `AgentTeamRequestV1`
2. `AgentTeamPlanV1`
3. `AgentTeamRunRequestV1`
4. `AgentTaskEventV1`
5. `AgentTeamRunStateV1`
6. `AgentTeamRunEvidenceV1`

Use `validate_agentfarm_bundle()` for cross-document validation. It validates
immutable plan identity, request-to-plan bounds (including team size), bounded
declarative members and DAG tasks, resolved clarification,
approval/quote/idempotency continuity, and exact queued-to-terminal lifecycle
history. Terminal evidence uses aware timestamp instants, requires a running
penultimate lifecycle event no later than `evidence.started_at`, and keeps task
events inside the execution window.
Task-event counters, costs, and refs are bounded by the run and terminal state;
member summaries are derived from owned task outcomes. A successful run requires
every required task and every member to succeed plus non-empty evidence,
artifact, and log refs.

`clarification.status=required` represents a pre-execution request: it carries
non-empty unanswered questions and no resolution time. `resolved` carries no
unanswered questions and an aware `resolved_at`. Only resolved clarification is
eligible for the exact executable six-document bundle.

This is schema and offline semantic validation only. It neither selects a
provider nor activates AutoGen, OpenFang, a runtime, network, database, or
deployment integration. Provider, credential, runtime, endpoint, command,
prompt, code, and similar execution fields are forbidden.

## Runtime source admission

`AgentFarmRuntimeSourceProvenanceV1` is a separate offline admission document;
it does not extend the exact six-document execution bundle. Use
`validate_agentfarm_runtime_admission_bundle()` with exactly one
`AgentTeamRequestV1` and one `AgentFarmRuntimeSourceProvenanceV1`. The validator
requires resolved clarification and exact `request_id` and canonical
`space_id=agentfarm` continuity. The provenance capture must not predate the
request or its clarification resolution.

The provenance pins a repository identity, a full lower-case Git SHA-1 commit
and tree object ID, a source-tree digest, a repository-relative entrypoint and
build-manifest path with their byte digests, and a digest of the provenance
record. `revision.kind` is always `commit`; branch and tag references are not
admissible. Paths use `/`, contain no absolute prefix, backslash, empty segment,
or dot-prefixed segment.

All `sha256:` values are lower-case SHA-256 digests. `identity_digest` hashes
the UTF-8 bytes of `repository.canonical_identity`; the offline validator
recomputes this relation. `record_digest` hashes the RFC 8785 canonical JSON
form of the provenance document with `record_digest` omitted and is also
recomputed offline. This schema contains ASCII-only strings, so its canonical
form is the UTF-8 encoding of JSON with sorted keys and no insignificant
whitespace. Entrypoint and build-manifest digests declare hashes of the exact
blob bytes at `revision.tree_sha`. `source_tree_digest` declares a hash of the
raw byte stream from `git archive --format=tar <commit_sha>`; these Git-backed
relations require a later source resolver and are not recomputed here.

### Local provenance resolver

`shared.contracts.agentfarm_runtime_source_resolver` is that later, local-only
resolver. Its
`resolve_agentfarm_runtime_source_admission(documents, local_repository,
allowed_root, expected_canonical_repository_identity)` API first calls
`validate_agentfarm_runtime_admission_bundle()` on the exact two-document
bundle. It then uses bounded argv-only local Git commands with a sanitized
environment; it does not use remotes, network, fetch, checkout, `git status`,
or worktree mutation.

Git is resolved once at module import: fixed system locations take precedence,
with the importing process's `PATH` as the explicit fallback trust boundary.
Every invocation disables replace objects by argv and environment, disables
lazy object fetch, ignores system/global Git configuration and system
attributes, and overrides `core.attributesFile` with the platform null device.
Repository configuration therefore cannot redirect the resolver to replacement
objects, on-demand fetches, or an external attributes file that changes the
archive projection.

The canonical archive profile also forces `tar.umask=0002` and rejects a
non-empty common Git `info/attributes` file before object verification. Empty
or absent common attributes are admissible, and committed `.gitattributes`
remain part of the pinned tree and therefore retain their normal archive
semantics.

Timeout cleanup kills only the resolver-owned Git parent process, then performs
bounded reader joins and process waits. It closes stdout only after the reader
has finished; if an inherited writer keeps the pipe open, cleanup returns
fail-closed within its bound. The fixed allowed Git commands together with
disabled lazy fetch are the boundary preventing resolver-triggered remote
helpers.

The resolver requires the repository, Git directory, shared Git directory,
object directory, and every recursively discovered object alternate to resolve
under `allowed_root`. It reads the full pinned commit directly, independently
derives that commit's tree, rejects every non-regular blob in the committed
tree (including symlinks and gitlinks), hashes the two declared blobs as raw
bytes, and hashes the raw tar byte stream from `git archive`. The checked-out
`HEAD`, staged changes, unstaged changes, and untracked files do not affect
this object-based verification. All rejection reasons are stable redacted
codes; no Git stderr or source contents are returned.

On success, the frozen receipt claims only `verified_local_source`. It does
not establish repository ownership, runtime enablement, build success,
routing, deployment, reachability, approval, execution, or a Golden Path.

### OpenFang handoff admission

`AgentFarmOpenFangHandoffAdmissionV1` is a separate document after
runtime-source admission. Use
`validate_agentfarm_openfang_handoff_bundle()` only with the exact closed
composite containing `ChannelIntentV1`, `BrainPlanV1`, the complete list of
`SpaceExecutionContractV1` documents for that plan, `AgentTeamRequestV1`,
`AgentFarmRuntimeSourceProvenanceV1`, and the handoff admission. The validator
composes the existing Brain-plan and runtime-source admission validators; the
legacy three-document handoff shape is not admissible.

The AgentTeam request's `brain_plan_ref` must equal the admitted Brain
`plan_id`. The Channel intent must explicitly request `agentfarm`; the admitted
handoff's `brain_task_node_id` must select exactly one admitted Brain task whose
`space_ids` include `agentfarm`; and its single AgentFarm Space execution
contract must name `executor:openfang`, `approval-policy:openfang`, and
`cost-policy:openfang`. The handoff's `task_ref` exactly matches the AgentTeam
request, making the explicit mapping from request task reference to admitted
Brain node part of the closed handoff. The Channel intent must be received no
later than the AgentTeam request; together with the existing request-to-source
and source-to-handoff checks this creates one monotonic chronology. The handoff
also preserves the Channel `correlation_id` and the request's `request_id`,
`trace_id`, canonical `space_id=agentfarm`, `approval_ref`, `quote_ref`, and
`idempotency_key`.
`source_provenance_id` must name the admitted provenance record, and the handoff
cannot predate its source capture. `trace_id` is the AgentTeam lineage while
`correlation_id` is the existing Channel lineage; the Brain schemas do not
conflate those distinct identifiers.

The document names only `executor=openfang` and
`handoff_status=pending_openfang_admission`. Its closed execution boundary fixes
direct provider access, direct application access, and fallback to `false`.
There is deliberately no provider, endpoint, agent, tool, application,
credential, command, or runtime field. A valid document is therefore a
request-bound, fail-closed admission handoff only: it neither dispatches to
OpenFang nor proves that OpenFang accepted, approved, costed, routed, or
executed work. `quote_ref` and `approval_ref` preserve opaque OpenFang-owned
cost-offer and approval lineage; they do not prove a policy decision, billing,
or settlement.

`fixtures/v1/local-source-admission-record-v1.json` is a versioned,
request-bound example of this exact two-document admission bundle. It records
the local Captain Cook candidate's pinned objects and a resolver receipt scope
only. Its sibling commits are explicitly unreconciled and non-authoritative;
the fixture establishes neither remote freshness nor a canonical runtime
selection. Its archive digest is generated only under the resolver's sanitized
Git configuration. A system-configuration-dependent pre-observation is kept
as rejected evidence, not admitted provenance.

Passing the admission validator proves only that a request-bound source
description is structurally valid and that its repository identity and complete
record are internally self-consistent. It does not prove that the repository or
objects exist, that the declared Git/blob digests were independently observed,
or that AgentFarm is enabled, built, routed, deployed, reachable, approved, or
executed. The legacy six-document execution-shaped bundle also remains
independently valid; a later composed consumer must require both bundles before
enabling execution. Those checks require their own authority.
