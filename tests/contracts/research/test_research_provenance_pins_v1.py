"""The provenance-pin convention, enforced.

`docs/spaces/research/provenance-pin-convention-v1.md` decides that a cited pin
is written once — at the commit where the claim was actually read — and is never
rewritten. A later re-reading is appended to `provenance.verifications` instead.

The convention is only worth writing down if something fails when it is broken,
and the failure mode it exists to prevent is a *silent* one: a bulk replace over
SHAs looks like maintenance and asserts a re-verification that never happened.
So the three observation pins are pinned here as literals. A find-and-replace
across the declaration turns them red, and the only honest way to make them
green again is to record a verification pass that says what was re-read.

Nothing here reaches the network or a submodule checkout. It asserts the shape
and the frozen values of the declaration's own provenance block.
"""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[3]
DECLARATION = (
    ROOT / "shared" / "contracts" / "research" / "v1" / "research-service-tiers-v1.json"
)
CONVENTION_DOC = "docs/spaces/research/provenance-pin-convention-v1.md"

import pytest

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ROLES = {"observation", "binding"}
OUTCOMES = {"holds", "holds_with_locator_drift", "diverged"}

# A reference has to name the file it cites. Most call that key `path`;
# report_persistence.artifact_side already called it `migration` before this
# convention existed, and renaming it would change what the block reads like
# for no gain.
PATH_KEYS = ("path", "migration")

# The pins the authoring tasks actually read at. These are write-once. They are
# NOT the live gitlinks and are not meant to become them: vibemind-os has since
# advanced to 731288b and openfang to 75067d8, and every claim below was
# re-checked there by task-research-0004 without any of these moving.
OBSERVATION_PINS = {
    "registry-research-block": "c5cba961126523bed39d0d94e8fd0c982cb9cbe2",
    "execution-target-fail-closed": "c5cba961126523bed39d0d94e8fd0c982cb9cbe2",
    "ideas-table-and-bubble": "c5cba961126523bed39d0d94e8fd0c982cb9cbe2",
    "hand-settings": "5d38662f9fa596c8f145e4f6a45a09edf4504837",
    "swe-design-artifacts": "a9a48af05cf509009775a7d5d144e2200f827f02",
    "ideas-sync-triggers": "a9a48af05cf509009775a7d5d144e2200f827f02",
    "ideas-sync-columns": "a9a48af05cf509009775a7d5d144e2200f827f02",
    # Live claims. Frozen at the commit each was first read at — which for the
    # report-artifact migration is 731288b, because the file existed at no
    # earlier pinned commit.
    "hand-depth-binding": "5d38662f9fa596c8f145e4f6a45a09edf4504837",
    "hand-output-style-binding": "5d38662f9fa596c8f145e4f6a45a09edf4504837",
    "registry-default-context": "c5cba961126523bed39d0d94e8fd0c982cb9cbe2",
    "evidence-precedent": "c5cba961126523bed39d0d94e8fd0c982cb9cbe2",
    "report-artifact-migration": "731288b4e36ac172dfb902e22627c6f937760a3e",
}

BINDING_REFS = {
    "hand-depth-binding",
    "hand-output-style-binding",
    "registry-default-context",
    "evidence-precedent",
    "report-artifact-migration",
}


@pytest.fixture(scope="module")
def declaration() -> dict[str, object]:
    return json.loads(DECLARATION.read_text(encoding="utf-8"))


def upstream_references(node: object) -> list[dict[str, object]]:
    """Every dict that cites an upstream repository at a commit."""
    found: list[dict[str, object]] = []
    if isinstance(node, dict):
        if "repo" in node and "pin" in node:
            found.append(node)
        for value in node.values():
            found.extend(upstream_references(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(upstream_references(value))
    return found


@pytest.fixture(scope="module")
def references(declaration: dict[str, object]) -> dict[str, dict[str, object]]:
    found = upstream_references(declaration)
    by_ref = {reference["ref"]: reference for reference in found}
    assert len(by_ref) == len(found), "two upstream references share a ref id"
    return by_ref


@pytest.fixture(scope="module")
def verification(declaration: dict[str, object]) -> dict[str, object]:
    passes = declaration["provenance"]["verifications"]
    assert passes, "the declaration records no verification pass"
    return passes[-1]


# ── The convention is declared, and points at the document that argues it ───


def test_the_declaration_names_its_pin_convention(declaration: dict[str, object]) -> None:
    convention = declaration["provenance"]["pin_convention"]
    assert convention["rule"] == "frozen_at_observation_with_additive_re_verification"
    assert convention["pin_field"] == "write_once"
    assert convention["document"] == CONVENTION_DOC


def test_the_convention_document_exists(declaration: dict[str, object]) -> None:
    document = ROOT / declaration["provenance"]["pin_convention"]["document"]
    assert document.is_file(), f"the convention document is missing: {document}"


def test_the_convention_defines_both_roles(declaration: dict[str, object]) -> None:
    roles = declaration["provenance"]["pin_convention"]["roles"]
    assert set(roles) == ROLES
    for description in roles.values():
        assert description


# ── Shape: every upstream reference is addressable and typed ────────────────


def test_every_upstream_reference_is_addressable_and_typed(
    references: dict[str, dict[str, object]],
) -> None:
    assert references, "the declaration cites no upstream reference at all"
    for ref, reference in references.items():
        assert ref, "an upstream reference carries an empty ref id"
        assert reference["role"] in ROLES, f"{ref} declares role {reference['role']!r}"
        assert any(reference.get(key) for key in PATH_KEYS), f"{ref} names no file"


def test_no_pin_is_abbreviated(references: dict[str, dict[str, object]]) -> None:
    # An abbreviated SHA is ambiguous forever; a citation is not.
    for ref, reference in references.items():
        assert FULL_SHA.match(reference["pin"]), f"{ref} carries a short or malformed pin"


def test_the_reference_inventory_is_complete(
    references: dict[str, dict[str, object]],
) -> None:
    # A reference added or removed without updating this file is a change to
    # what the declaration cites, and has to be looked at rather than absorbed.
    assert sorted(references) == sorted(OBSERVATION_PINS)


# ── The load-bearing test: pins are write-once ──────────────────────────────


def test_observation_pins_are_frozen(references: dict[str, dict[str, object]]) -> None:
    """A bulk find-and-replace over SHAs fails here, by design.

    Advancing a pin asserts that the claim was re-read at the new commit. If it
    was, the honest record is a verification entry — not an edited pin. So this
    test does not ask whether the pin is current; it asks whether it still names
    the commit somebody actually opened.
    """
    for ref, expected in OBSERVATION_PINS.items():
        assert references[ref]["pin"] == expected, (
            f"{ref} was re-pinned from {expected} to {references[ref]['pin']}. "
            "A pin records where a claim was read, not which commit is current. "
            f"If it was re-read, record it in provenance.verifications; see {CONVENTION_DOC}."
        )


def test_the_roles_are_the_ones_the_convention_assigned(
    references: dict[str, dict[str, object]],
) -> None:
    for ref, reference in references.items():
        expected = "binding" if ref in BINDING_REFS else "observation"
        assert reference["role"] == expected, f"{ref} changed role"


# ── Re-verification is additive, and covers what it has to ──────────────────


def test_the_verification_pass_records_what_it_checked_against(
    verification: dict[str, object],
) -> None:
    checked = verification["checked_pins"]
    assert checked, "the verification pass names no pin it checked against"
    for repo, pin in checked.items():
        assert "/" in repo, f"{repo} is not an owner/repo name"
        assert FULL_SHA.match(pin), f"{repo} is checked against a malformed pin"
    assert verification["verified_by_task"]
    assert verification["verified_on"]
    assert verification["method"]


def test_the_verification_pass_covers_every_reference(
    references: dict[str, dict[str, object]], verification: dict[str, object]
) -> None:
    covered = {entry["ref"] for entry in verification["references"]}
    assert covered == set(references), (
        "the verification pass and the declaration disagree about which "
        f"references exist: {sorted(covered ^ set(references))}"
    )


def test_every_binding_reference_is_re_verified(
    references: dict[str, dict[str, object]], verification: dict[str, object]
) -> None:
    # An observation may sit unchecked forever — it is a historical record. A
    # binding reference claims something about upstream *now*, so it may not.
    covered = {entry["ref"] for entry in verification["references"]}
    binding = {ref for ref, value in references.items() if value["role"] == "binding"}
    assert binding <= covered, f"binding references never re-verified: {sorted(binding - covered)}"


def test_every_verification_entry_states_an_outcome_and_its_evidence(
    verification: dict[str, object],
) -> None:
    for entry in verification["references"]:
        assert entry["outcome"] in OUTCOMES, f"{entry['ref']} has outcome {entry['outcome']!r}"
        assert entry["evidence"], f"{entry['ref']} was verified without recording what was read"


def test_the_outcome_vocabulary_is_declared_in_full(verification: dict[str, object]) -> None:
    assert set(verification["outcome_vocabulary"]) == OUTCOMES


def test_locator_drift_names_the_locator_it_drifted_to(
    references: dict[str, dict[str, object]], verification: dict[str, object]
) -> None:
    # Drift is the case where freezing costs the reader something. The record
    # has to pay that cost back, or the frozen locator is just a dead end.
    for entry in verification["references"]:
        if entry["outcome"] != "holds_with_locator_drift":
            assert "locator_at_checked_pin" not in entry, (
                f"{entry['ref']} records drift without declaring it"
            )
            continue
        drifted = entry["locator_at_checked_pin"]
        assert drifted, f"{entry['ref']} drifted without naming the new locator"
        observed = references[entry["ref"]].get("locator")
        assert observed, f"{entry['ref']} claims locator drift but records no observed locator"
        assert drifted != observed, f"{entry['ref']} claims drift but names the observed locator"


def test_a_divergence_is_never_recorded_silently(verification: dict[str, object]) -> None:
    # If a claim stops holding upstream, the pass says so and says what changed.
    # It does not adjust the assertion to match; that needs its own authority.
    for entry in verification["references"]:
        if entry["outcome"] == "diverged":
            assert len(entry["evidence"]) > 40, (
                f"{entry['ref']} diverged without describing what changed"
            )


# ── The pins that moved are the manifest's business, not this contract's ────


def test_the_checked_pins_are_the_live_gitlinks(verification: dict[str, object]) -> None:
    """The pass has to have checked against what the superproject actually pins.

    Read from repo-manifest.yaml rather than hardcoded, so the next pin lift
    makes this test say "a verification pass is due" instead of quietly passing.
    """
    manifest = (ROOT / "repo-manifest.yaml").read_text(encoding="utf-8")
    for repo, pin in verification["checked_pins"].items():
        name = repo.split("/")[-1]
        block = re.search(
            rf"^\s*-\s*id:\s*{re.escape(name)}\s*$.*?^\s*expected_gitlink_pin:\s*([0-9a-f]{{40}})",
            manifest,
            re.M | re.S,
        )
        assert block, f"{name} has no expected_gitlink_pin in repo-manifest.yaml"
        assert block.group(1) == pin, (
            f"the last verification pass checked {name} at {pin}, but the manifest "
            f"now pins {block.group(1)}. A new verification pass is due; see {CONVENTION_DOC}."
        )
