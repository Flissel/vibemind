# ChannelIntentV1

## Purpose and authority

`ChannelIntentV1` is a versioned, language-neutral, data-only envelope for an
inbound user intent that a Channel has already normalized before it reaches
Brain. It records no lifecycle transition and does not make a call to an
application. Brain alone interprets the message, plans work, owns the task
lifecycle, and determines whether any resulting evidence is sufficient.
Shared owns this schema, fixtures, the existing V1 ID grammar, and deterministic
offline validation.

| Owner | Responsibility in this contract | Explicitly not owned here |
| --- | --- | --- |
| Channels | ingress, authentication, transport, and alias normalization before emission | Brain planning, lifecycle, or application calls |
| Brain | interpretation, planning, lifecycle, and result validation | Channel transport or Shared schema changes |
| Shared | `ChannelIntentV1` schema, existing ID grammar, fixtures, offline validation | registry lookup, normalization, routing, or execution |
| Applications | jobs and evidence production after Brain planning | direct Channel calls |
| OpenFang | downstream MVP execution boundary after Brain admission | agents, targets, approvals, permissions, providers, or costs in this ingress envelope |

## Data shape

The root object requires `contract_version: "v1"`, a `correlation_id`, a
`channel_kind`, non-secret actor and session context, the user `message`, a
`received_at` timestamp, and explicit `user_facing_expectations`.

- `correlation_id` reuses the existing Shared V1 identifier grammar; this
  contract deliberately introduces no new identifier kind. It is a correlation
  reference only and grants no authority.
- `channel_kind` is exactly one of `voice`, `desktop-chat`, `openclaw`, or
  `space-chat`.
- `actor_context` carries a required opaque `actor_id` and optional locale.
  `session_context` carries a required opaque `session_id` and optional
  conversation identifier. Both are closed, identifier-only objects: they do
  not admit credentials, tokens, passwords, profile records, or arbitrary
  metadata.
- `requested_space_id` is optional. When present, it is an already-canonical,
  lower-case Space identifier supplied by the ingress Channel.
- `user_facing_expectations.reply` and `.evidence` record the requested reply
  and evidence presentation expectations. They neither prove a reply nor
  require execution.

The envelope deliberately has no application target, execution target, agent,
approval, permission, cost, provider, network, or dispatch field. Every object
is closed (`additionalProperties: false`), so direct targets and credential-like
fields are rejected offline.

## Canonical Space and alias ingress rule

Channels must normalize aliases at ingress before emitting
`requested_space_id`. They must not send a `requested_space_alias` field or
ask Shared to translate one. Shared does not read, look up, modify, or embed a
Space registry. It validates only the supplied identifier's structural syntax;
whether a syntactically valid value is currently registered and canonical is
the ingress producer's and canonical registry's responsibility.

This boundary means a malformed Space identifier and an explicit alias-bearing
input are rejected deterministically, while registry truth is intentionally not
claimed by this offline contract.

## Offline validation

`validate_document("channel-intent", parsed_json)` uses JSON Schema Draft
2020-12 only. It performs no Channel, registry, Brain, application, provider,
database, network, or service access. Passing validation proves only that the
data matches this envelope; it does not authenticate an actor, dispatch work,
create a plan, execute a target, produce evidence, or prove a user-facing
reply.

Run the scoped deterministic suite from the repository root:

```powershell
python -m pytest tests/contracts/test_v1_contracts.py -q
```
