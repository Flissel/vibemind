# Flowzen V1 contract

Flowzen V1 is a provider-neutral, versioned offline contract family for the
chat-orchestrated Flowzen space. It defines a narrow recommendation and
acceptance chain; it does not contact a provider, database, runtime, or
deployment, and it has no approval authority of its own.

The exact bundle has four closed Draft 2020-12 documents:

1. `FlowzenCheckinV1` (`flowzen-checkin`) records only opaque subject, task,
   intent, and trace references, a bounded signal band, an observation time,
   expiry, and the deterministic idempotency key `checkin:<checkin_id>`. It is
   always `readonly`.
2. `FlowzenRecommendationV1` (`flowzen-recommendation`) projects one bounded
   recommendation from that check-in. Its title and summary are bounded; it
   carries opaque evidence references and an integer minor-unit cost record.
   It is always `readonly` and remains `proposed` until its expiry.
3. `FlowzenAcceptanceV1` (`flowzen-acceptance`) is the only mutation. It needs
   an explicit opaque `approval_ref`, a SHA-256 parameter digest, finite timeout
   and cost limit, and the deterministic idempotency key
   `accept:<recommendation_id>`. It may only target the still-proposed,
   generated and unexpired recommendation from the same check-in chain.
4. `FlowzenAcceptanceEvidenceV1` (`flowzen-acceptance-evidence`) closes the
   acceptance attempt as `succeeded`, `failed`, or `unavailable`. A success
   requires an `accepted` readback at completion and an opaque evidence ref;
   failures are limited to redacted enum classes.

Use `validate_document(...)` for one document or `validate_flowzen_bundle(...)`
for the full chain. Bundle validation rejects broken opaque-reference
continuity, acceptance before recommendation generation or after expiry,
approval/quote/currency or cost drift, non-deterministic idempotency, invalid
time ordering, timeout overruns, and a claimed success without matching
terminal readback evidence.

All identifiers are opaque V1 IDs. The contracts carry neither names, emails,
free personal attributes, free credentials, provider, runtime, endpoint,
transport-status, command, database, nor secret fields. `additionalProperties`
is closed for every document, so a 2xx, mock, or no-op marker cannot establish
success. Evidence and cost provenance use existing `evidence_v1_*` and
`quote_v1_*` references; approval stays the existing `approval_v1_*` reference.

The maximum portable bounds are: check-in/recommendation validity is enforced by
their explicit timestamps; acceptance timeout is 1–300 seconds; recommendation
text is 120/500 characters; recommendation evidence has 1–8 unique refs; and
all cost values are non-negative integers capped at 10,000,000 minor units.

This is a schema/validator/fixture contract only. It does not establish
OpenFang, provider, database, deployment, runtime, or live end-to-end success.
