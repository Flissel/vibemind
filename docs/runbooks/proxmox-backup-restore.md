# Proxmox backup and restore operations boundary

## Scope and boundaries

This versioned, static runbook defines review gates for backups and a possible
later restore of the managed Proxmox system classes. It intentionally contains
no live target, address, credential, runtime name, command, or execution
sequence.

This document does not perform or prove a runtime operation. It neither
creates nor validates a backup, snapshot, restore, database action, volume
action, deployment, network action, or provider action. `deployment_proven=false`
and `golden_path_proven=false` remain true in every state described here.

## Static inventory

The static inventory to review consists of the following repository-defined
data classes, not a claim about a current runtime:

- PostgreSQL restore artifacts and their associated database role/configuration
  inputs;
- MongoDB and Neo4j data classes identified by the versioned Proxmox compose
  artifacts;
- application volumes declared in the versioned phase compose artifacts;
- versioned configuration manifests, compose artifacts, and required-variable
  name lists, without reading variable values.

The inventory is a planning boundary. A live inventory requires its own
authorized observation and cannot be inferred from historical documentation.

## Backup evidence gate

Before an operation can be proposed, the evidence record must contain a backup
reference, creation timestamp, checksum, origin, scope, and retention decision.
The review must state whether that reference covers the intended system class
and whether its provenance is independently understandable. A backup reference
is not evidence of a successful restore or of data integrity.

Fail closed if the backup is absent, its origin is unknown, the checksum is
missing, the timestamp is unavailable, or the intended target environment
cannot be validated. Do not replace any missing evidence with a historical
report, a nominal filename, or an unverified operator statement.

## Restore is separate high-risk work

Restore is a separate high-risk action with its own authority. It requires a
new request-specific decision, a named decision owner, and a separately
approved maintenance window. This document does not authorize, perform, or
simulate restore work.

If separately approved, a Restore probe is a bounded evidence stage and does
not itself establish data integrity. Data integrity evidence must be recorded
separately from the Restore probe. An independent readback by the designated
evidence owner is a further separate stage; health, reachability, transport,
or operator acknowledgement cannot substitute for it.

## Escalation boundary

Any unknown origin, absent checksum, unavailable validated environment, failed
Restore probe, or unavailable independent readback is a stop condition. Preserve
the evidence already available, avoid further state changes, and escalate to
the decision owner for a new explicit decision.
