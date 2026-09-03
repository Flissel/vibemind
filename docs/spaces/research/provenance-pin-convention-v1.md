# Provenance pins — the convention

**Status:** decided for the research contract family; **not yet program-wide**
**Task:** `task-research-0004-provenance-pin-convention-v1`
**Applies to:** `shared/contracts/research/`, `tests/contracts/research/`,
`docs/spaces/research/`
**Enforced by:** `tests/contracts/research/test_research_provenance_pins_v1.py`

## The rule

> **A cited pin is written once, at the commit where the claim was actually
> read, and is never rewritten. A later re-reading is recorded next to it, not
> in place of it.**

Three obligations follow.

1. **`pin` is write-once.** It names the commit at which somebody opened the
   file. A pin lift does not touch it. A refresh pass does not touch it. A
   `sed` over SHAs is a defect, not maintenance.
2. **Every upstream reference declares a `role`.** `observation` records where
   a claim was read. `binding` asserts something about what upstream says
   *now*. Only `binding` carries a standing re-verification obligation.
3. **Re-verification is additive.** A verification pass appends an entry naming
   the pin it checked against, the date, and per reference an outcome —
   `holds`, `holds_with_locator_drift`, or `diverged`. It never edits `pin`.

And the rule that makes rule 3 mean something:

4. **Divergence is a finding, not a licence.** If a claim no longer holds at
   the checked pin, the pass records `diverged` and says what changed. It does
   **not** adjust what the contract asserts to match the new upstream. That is
   a separate change, with its own reasoning and its own authority.

## Why frozen, and not refreshed

The choice was between *frozen-at-observation* and
*refreshed-with-re-verification*. The deciding question is not which is tidier
but which makes the contract's claim **checkable**.

**A frozen pin is permanently checkable.** A SHA is immutable, so
"open `config/space_agent_registry.yml` at `c5cba96`, lines 162-176" is a
complete instruction that will still work in a year. It checks exactly the
proposition the author is making: *this is what I read, and here is where*.

**A refreshed pin is also checkable — of a different proposition.** Rewriting
the SHA turns "I read this at `c5cba96`" into "I read this at `731288b`", which
is false unless somebody actually did. Refresh does not make the citation
easier to verify; it makes it verify the wrong claim. The honest-provenance
argument and the verifiability argument point the same way, which is unusual
and worth noticing: freezing is not a concession to honesty at the cost of
usefulness.

**The cost of freezing is navigational, and navigation costs are paid by adding
information, never by deleting it.** The objection to freezing is real — with
every link of a pin chain, a frozen citation sits further behind the live pin
and gets harder to follow. But the cure for "hard to follow" is a record of
what happened in between. A swapped SHA erases that record; a verification
entry *is* that record. The verification block tells a reader both where the
claim came from and how fresh it is. A refreshed SHA tells them neither.

**The evidence from this pass settles it.** Twelve upstream references were
checked against the live pins. Eleven point at files that are **byte-identical**
at the live pin — same blob hash, same lines. Under a refresh convention all
twelve SHAs would have moved and the diff would have looked like work, while
recording nothing that was not already true. Under this convention one pass
recorded that eleven held unchanged and one drifted in locator only. That single
drift — `lines 162-176` → `lines 162-203`, because E9/E10 grew the registry's
research block from 15 lines to 42 — is the entire information content of two
pin chains as far as this contract is concerned. A bulk replace would have
buried it.

## Why `binding` references need more than freezing

Freezing alone is not sufficient everywhere, and this is where the answer
genuinely differs by citation type.

`settings.depth.invention_policy` says: *"closed set; no step may be added,
renamed, or reordered without changing the Hand first."* That is a claim in the
present tense about the Hand as it stands. A frozen pin cannot support it on its
own — the Hand could have changed the day after the pin was taken, and the
contract would go on asserting a closed set that upstream had already reopened.
Same for `evidence_policy.precedent`, whose rationale says the execution target
"**already** refuses" to pass uncited prose off as research.

So for `binding` references the pin is still frozen — it still records where the
claim was read — but the reference carries an obligation the observation
entries do not: it must be re-checked, and the check must be on the record. That
is what converts "somebody once read this" into "this is still true, as of a
named commit on a named date".

Note which mechanism does that re-checking today, because they are not equal:

- `report-artifact-migration` is re-verified **on every test run**.
  `test_research_report_artifact_migration_v1.py` reads the SQL out of whatever
  `vibemind-os` checkout is present and asserts against it. Upstream drift
  breaks a test.
- `hand-depth-binding` and `hand-output-style-binding` are **not**.
  `test_depth_matches_the_hand_verbatim` asserts the declaration against
  constants written into the test file, not against `HAND.toml`. Both would stay
  green if the Hand's value set changed tomorrow. That is a known gap, recorded
  here rather than papered over; closing it needs the Hand readable from a
  checkout the research tests can reach, which no test in this family has today.

## Two references had no anchor at all

The pass found something the stale-pin framing did not predict. The riskiest
references were not the three superseded pins; they were the two references that
carried **no pin whatsoever**:

- `context_policy.registry_evidence` named a path, a locator and a value with no
  commit. It is a live claim about the registry — and the registry is the *one*
  cited file that actually moved across the chain. It happened to survive
  unchanged, but nothing in the repository could have caught it if it had not.
- `report_persistence.artifact_side` named a migration file in `vibemind-os` with
  no commit. It could not have carried one when it was written: the file did not
  exist at `c5cba96` or `a9a48af`. It entered `vibemind-os` in `3be78f6` and is
  first reachable from a pinned commit at `731288b`.

Both are now anchored, each at its **first** observation — `c5cba96` and
`731288b` respectively. Neither is a refresh; one of them simply had its first
observation later than the others. This is the case the convention has to
accommodate: not every reference becomes pinnable at the same time.

## What a pin-chain task does

Nothing, to these fields. That is the point.

A `cockpit-git` pin lift changes `repo-manifest.yaml`, the gitlink, and the
manifest contract test. It does **not** rewrite provenance in
`shared/contracts/`, and a growing list of superseded pins there is not a defect
it should report as one. What it may usefully do is note that a verification
pass is due — which is exactly how this task came to exist.

Conversely, a verification pass touches no pin and no gitlink. It appends to
`provenance.verifications` and nothing else. The two kinds of work do not
overlap, which is the practical reason for writing the rule down: it keeps
`cockpit-git` and the owning space from reaching for the same lines.

## Recording format

```json
"pin_convention": {
  "rule": "frozen_at_observation_with_additive_re_verification",
  "pin_field": "write_once"
},
"sources": [
  { "ref": "<stable-id>", "role": "observation",
    "repo": "<owner/repo>", "pin": "<40-hex>",
    "path": "<path>", "locator": "<lines or symbol>", "used_for": "<claim>" }
],
"verifications": [
  { "verified_by_task": "<task-id>", "verified_on": "<YYYY-MM-DD>",
    "checked_pins": { "<owner/repo>": "<40-hex>" },
    "references": [
      { "ref": "<stable-id>", "outcome": "holds", "evidence": "<what was read>" }
    ] }
]
```

Rules the tests enforce:

- every reference carrying a `repo` and a `pin` also carries a `ref` and a
  `role`; `ref` values are unique;
- pins are full 40-character SHAs, never abbreviated;
- the three observation pins are asserted as literals, so a bulk find-and-replace
  fails loudly rather than passing silently;
- every `binding` reference appears in the most recent verification pass;
- every reference named in a verification pass exists in the declaration, and
  every reference in the declaration is covered by the pass;
- a `holds_with_locator_drift` outcome must name the drifted locator, and it must
  differ from the locator recorded at the observation pin.

## Scope of this decision

This convention is decided for the **research contract family** and enforced by
its tests. It is deliberately not written into `docs/governance/`:
`task-research-0004` holds no authority there, the same limit under which
`task-research-0003` declined to record E14. Promoting it to a program-wide rule
— so that every space's contracts and every future pin chain are bound by it —
is the orchestrator's step, and the handoff asks for it.

Until then, other spaces are not bound by this document. They are, however,
welcome to the finding behind it: eleven of twelve citations were unchanged
across two pin chains, and the one thing that moved would have been invisible
under a refresh.
