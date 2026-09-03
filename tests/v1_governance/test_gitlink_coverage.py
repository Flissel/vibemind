"""Manifest coverage for gitlinks, including gitlinks absent from `.gitmodules`.

`validate_manifest` derives its `undeclared-submodule` check from `.gitmodules`
entries, so a gitlink that a tree carries *without* a matching `.gitmodules` entry
is invisible to it. Under `submodule_policy.validator_network_access: forbidden`
it also cannot read a pinned child tree at all. Finding B2 lived exactly in that
blind spot: `coding-engine@81ab938` carried five gitlinks, only `la_fungus_search`
was mapped in its `.gitmodules`, and until task-git-0034 the manifest declared no
child of `coding-engine` whatsoever -- so `manifest validate` stayed green through
the pin chains of task-git-0029, 0031 and 0033 while the gap persisted.

Both halves of B2 are now closed at `coding-engine@352a858`: task-git-0034 added the
manifest declarations, and task-coding-0006 mapped `external/Automation_ui` and
`external/minibook` upstream and retired `external/NemoClaw` and
`external/free-llm-api-resources`, leaving three gitlinks with no unmapped
remainder.

The blind spot in `validate_manifest` is closed as of
task-governance-0034: its coverage check now keys on the union of `.gitmodules`
paths and mode-160000 index entries, and runs for every locally available parent
rather than only those that already have a declared child. That reaches exactly
one parent in the canonical CI state -- the superproject, the only tree the
validator may read while `validator_network_access: forbidden` stands and
`vibemind-os` is uninitialized. The recorded-inventory tests below therefore
still carry the claim for every *pinned* parent; the validator cannot, and the
last four tests in this module state precisely where its reach ends.

These tests close the coverage half of that gap offline, without network access
and without initializing a submodule, by checking the manifest against the
recorded inventory in `fixtures/observed_gitlinks.yaml`. Each record is keyed to the
pin it was measured at, so a pin lift invalidates the record and fails the suite
until the tree is re-measured -- the file cannot be used to freeze today's state.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Mapping

import pytest
import yaml

from tools.v1_governance.manifest import validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
# Deliberately not under a `data/` directory: the repository's .gitignore ignores
# `data/` wholesale, which would keep this file out of the commit and leave the
# suite passing locally while failing in CI on a missing fixture.
OBSERVATIONS_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "observed_gitlinks.yaml"
)

# `coding-engine/la_fungus_search` pins f731c19a, which is not reachable from any
# ref on Flissel/la_fungus_search, so its tree cannot be fetched. Pinned here as a
# literal so a second unreadable tree cannot join the set unnoticed.
KNOWN_UNREADABLE_PINS: frozenset[str] = frozenset(
    {"coding-engine-la-fungus-search"}
)

# The B2 paths, as a standing regression claim about coding-engine@352a858. Three,
# down from the five carried at 81ab938: `external/NemoClaw` (3ba517dd) and
# `external/free-llm-api-resources` (c3ac9113) were retired in task-coding-0006.
# Automation_ui and minibook keep their 81ab938 pins -- the retirement moved no
# surviving pin, it only added their `.gitmodules` mapping.
CODING_ENGINE_GITLINKS: Mapping[str, str] = {
    "external/Automation_ui": "3a413ae2886e2b83379e0eea9e4729cc1d3a4573",
    "external/minibook": "b19c61e27bb3ac2ca8a4f06addb541819bfbe9a0",
    "la_fungus_search": "f731c19afa08ddc84874669fb96faef9bd6d1a69",
}

# Which of those paths coding-engine's own `.gitmodules` maps, measured at 352a858
# with `git config -f .gitmodules --get-regexp '^submodule\..*\.path$'`. Held as an
# enumerated literal, exactly as the unmapped set was before it emptied, so that the
# closing claim stays per-path: re-introducing one unmapped gitlink fails the
# comparison below instead of being absorbed into a count.
CODING_ENGINE_MAPPED_PATHS: tuple[str, ...] = (
    "external/Automation_ui",
    "external/minibook",
    "la_fungus_search",
)


def _manifest() -> Mapping[str, object]:
    return yaml.safe_load((REPO_ROOT / "repo-manifest.yaml").read_text(encoding="utf-8"))


def _repositories() -> dict[str, Mapping[str, object]]:
    return {
        repository["id"]: repository for repository in _manifest()["repositories"]
    }


def _observations() -> list[Mapping[str, object]]:
    document = yaml.safe_load(OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    observations = document["observations"]
    assert observations, "the observation inventory must not be empty"
    return observations


def _children(parent: str) -> list[Mapping[str, object]]:
    return [
        repository
        for repository in _repositories().values()
        if repository["parent"] == parent
    ]


def _tracked_gitlinks(root: Path) -> dict[str, str]:
    """Every mode-160000 index entry, keyed by path.

    Reads gitlinks straight out of the index rather than out of `.gitmodules`,
    which is the distinction the manifest validator currently misses.
    """
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=root,
        check=True,
        shell=False,
        text=True,
        capture_output=True,
    )
    gitlinks: dict[str, str] = {}
    for record in result.stdout.split("\0"):
        if not record:
            continue
        metadata, separator, relative_path = record.partition("\t")
        fields = metadata.split()
        assert separator and len(fields) == 3, f"unexpected index record: {record!r}"
        mode, object_id, _stage = fields
        if mode == "160000":
            gitlinks[relative_path.replace("\\", "/")] = object_id
    return gitlinks


def test_every_pinned_manifest_repository_has_a_gitlink_observation() -> None:
    """A new declaration cannot ship without a recorded look at its tree."""
    pinned = {
        repository_id
        for repository_id, repository in _repositories().items()
        if repository["expected_gitlink_pin"] != "absent"
    }
    observed = [observation["parent"] for observation in _observations()]

    assert len(observed) == len(set(observed)), "duplicate observation records"
    assert set(observed) == pinned


def test_observations_are_recorded_at_the_current_manifest_pins() -> None:
    """A pin lift must invalidate the record instead of silently outliving it.

    This is what stops the inventory from being a snapshot of today: when a pin
    moves, the stale record fails here until the tree is re-measured at the new
    pin.
    """
    repositories = _repositories()

    # A record whose parent is gone from the manifest is reported by
    # test_every_pinned_manifest_repository_has_a_gitlink_observation; skipping it
    # here keeps this test's failure message about pin staleness only.
    stale = [
        (observation["parent"], observation["parent_pin"])
        for observation in _observations()
        if observation["parent"] in repositories
        and observation["parent_pin"]
        != repositories[observation["parent"]]["expected_gitlink_pin"]
    ]

    assert stale == [], (
        "these observations were recorded at a pin the manifest no longer "
        f"declares; re-measure the tree at the new pin: {stale}"
    )


def test_every_observed_gitlink_is_declared_in_the_manifest() -> None:
    """The blind spot itself: a gitlink with no `.gitmodules` entry still counts.

    Before task-git-0034 this failed for all five gitlinks under `coding-engine`.
    """
    repositories = _repositories()
    undeclared: list[str] = []

    for observation in _observations():
        if not observation["tree_available"]:
            continue
        parent = observation["parent"]
        declared = {
            child["path"]: child["expected_gitlink_pin"]
            for child in _children(parent)
        }
        for gitlink in observation["gitlinks"]:
            path, pin = gitlink["path"], gitlink["pin"]
            if path not in declared:
                undeclared.append(
                    f"{parent}@{repositories[parent]['expected_gitlink_pin'][:8]}"
                    f":{path} ({pin[:8]}) is not declared in repo-manifest.yaml"
                )
            elif declared[path] != pin:
                undeclared.append(
                    f"{parent}:{path} is declared at {declared[path][:8]} "
                    f"but the pinned tree carries {pin[:8]}"
                )

    assert undeclared == [], "\n".join(undeclared)


def test_manifest_declares_no_gitlink_the_pinned_tree_does_not_carry() -> None:
    """The other direction: a declaration must correspond to a real gitlink."""
    phantom: list[str] = []

    for observation in _observations():
        if not observation["tree_available"]:
            continue
        parent = observation["parent"]
        observed = {gitlink["path"] for gitlink in observation["gitlinks"]}
        for child in _children(parent):
            path, state = child["path"], child["gitlink_state"]
            if state == "present" and path not in observed:
                phantom.append(
                    f"{parent}:{path} is declared gitlink_state: present but the "
                    "pinned tree carries no such gitlink"
                )
            elif state == "declared-without-gitlink" and path in observed:
                phantom.append(
                    f"{parent}:{path} is declared without a gitlink but the "
                    "pinned tree carries one"
                )

    assert phantom == [], "\n".join(phantom)


def test_unreadable_pinned_trees_are_limited_to_the_known_dangling_pin() -> None:
    """An unreadable tree is an admitted blind spot, so the set stays pinned."""
    unreadable = {
        observation["parent"]
        for observation in _observations()
        if not observation["tree_available"]
    }

    assert unreadable == KNOWN_UNREADABLE_PINS
    for observation in _observations():
        if not observation["tree_available"]:
            assert observation["unavailable_reason"]
            assert observation["gitlinks"] == []


def test_coding_engine_gitlinks_are_declared_and_the_mapping_gap_is_closed() -> None:
    """Finding B2 closed, stated so a partial fix still cannot pass as a full one.

    The predecessor of this test asserted the inverse -- that only
    `la_fungus_search` was mapped and four `external/*` paths were not -- and was
    worded to enumerate all four, because the gap covered four paths and not just
    the alphabetically first one, so a one-path fix would have moved the recursive
    init's abort rather than removed it. task-coding-0006 closed the gap the other
    way round: two paths mapped, two retired. The successor claim is therefore that
    the unmapped remainder is *empty*, and it keeps the same shape -- every
    surviving path enumerated, compared per path -- so that dropping one mapping
    again fails here rather than hiding inside an aggregate.

    Declaration in the manifest and mapping in coding-engine's `.gitmodules` stay
    separate assertions. `la_fungus_search` was the case that proved the two layers
    drift independently: it was mapped upstream all along and still missing from
    the manifest until task-git-0034.
    """
    observation = next(
        record for record in _observations() if record["parent"] == "coding-engine"
    )
    observed = {gitlink["path"]: gitlink["pin"] for gitlink in observation["gitlinks"]}

    assert observed == dict(CODING_ENGINE_GITLINKS)

    declared = {child["path"]: child for child in _children("coding-engine")}
    assert set(declared) == set(CODING_ENGINE_GITLINKS)
    for path, pin in CODING_ENGINE_GITLINKS.items():
        assert declared[path]["expected_gitlink_pin"] == pin
        assert declared[path]["gitlink_state"] == "present"
        assert declared[path]["evidence"]["parent_pin"] == (
            "352a858eab252ddc4f4a2f25d9dd3549e798fc80"
        )

    # Every gitlink the pinned tree carries is mapped in coding-engine's own
    # `.gitmodules`, enumerated path by path in alphabetical order rather than
    # counted, so a single mapping regressing is caught here and not averaged away.
    assert sorted(CODING_ENGINE_GITLINKS) == sorted(CODING_ENGINE_MAPPED_PATHS)
    unmapped = sorted(set(CODING_ENGINE_GITLINKS) - set(CODING_ENGINE_MAPPED_PATHS))
    assert unmapped == []

    # Closing the mapping gap is not the same as a working recursive init:
    # la_fungus_search is mapped and declared, yet its pin is dangling on the remote,
    # so the abort survives this commit. KNOWN_UNREADABLE_PINS still records it.
    assert "coding-engine-la-fungus-search" in KNOWN_UNREADABLE_PINS


def test_superproject_gitlinks_are_declared_in_the_manifest() -> None:
    """Live, generic guard at the one level this repository can read offline.

    Keyed on index gitlinks rather than `.gitmodules`, so a stray gitlink
    committed into the superproject without a submodule mapping is caught here
    instead of passing `manifest validate`.
    """
    declared = {
        repository["path"].replace("\\", "/")
        for repository in _repositories().values()
        if repository["parent"] == _manifest()["superproject"]["id"]
    }

    gitlinks = _tracked_gitlinks(REPO_ROOT)

    assert gitlinks, "the superproject is expected to carry at least one gitlink"
    assert set(gitlinks) <= declared, (
        f"undeclared superproject gitlink(s): {sorted(set(gitlinks) - declared)}"
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, shell=False, text=True, capture_output=True
    )


_TEST_REMOTE = "https://github.com/v1-tests/{name}.git"


def _build_superproject(
    root: Path,
    *,
    gitlinks: Mapping[str, str],
    mapped: tuple[str, ...] = (),
    declared: tuple[str, ...] = (),
) -> Path:
    """Commit `gitlinks`, map only `mapped` in `.gitmodules`, declare only `declared`.

    Separating the three sets is the whole point: the validator's blind spot had
    two independent halves, and only a fixture that can vary "carries a gitlink",
    "is mapped in `.gitmodules`" and "is declared in the manifest" independently
    can hold one half still while exercising the other.

    Returns the manifest path.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-b", "master")
    _git(root, "config", "user.name", "V1 Tests")
    _git(root, "config", "user.email", "v1-tests@example.invalid")
    (root / "README.md").write_text("root\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "test: initialize superproject")

    if mapped:
        (root / ".gitmodules").write_text(
            "".join(
                f'[submodule "{path}"]\n'
                f"\tpath = {path}\n"
                f"\turl = {_TEST_REMOTE.format(name=path)}\n"
                for path in mapped
            ),
            encoding="utf-8",
        )
        _git(root, "add", ".gitmodules")
    # A gitlink is staged straight into the index, with or without a matching
    # .gitmodules entry -- how coding-engine's external/ paths were committed
    # (commit ddcd412 added four at once and never touched .gitmodules).
    for path, pin in gitlinks.items():
        _git(root, "update-index", "--add", "--cacheinfo", f"160000,{pin},{path}")
    _git(root, "commit", "-m", "test: add gitlinks")

    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    manifest_path = root / "repo-manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "superproject": {
                    "id": "test-superproject",
                    "path": ".",
                    "current_integration_branch": "master",
                    "target_integration_branch": "main",
                    "branch_rename_status": "approval-required",
                },
                "repositories": [
                    {
                        "id": f"declared-{path}",
                        "parent": "test-superproject",
                        "path": path,
                        "kind": "submodule",
                        "expected_gitlink_pin": gitlinks[path],
                        "remote": _TEST_REMOTE.format(name=path),
                        "remote_role": "canonical-origin",
                        "owner": "platform",
                        "required": False,
                        "migration_state": "nested-legacy",
                        "initialization_state": "uninitialized",
                        "gitlink_state": "present",
                        "evidence": {
                            "source": "local-git",
                            "parent_pin": head,
                            "validation_state": "local",
                        },
                    }
                    for path in declared
                ],
                "submodule_policy": {"validator_network_access": "forbidden"},
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _undeclared(root: Path, manifest_path: Path) -> list[str]:
    return sorted(
        issue.path
        for issue in validate_manifest(root, manifest_path)
        if issue.code == "undeclared-submodule"
    )


@pytest.fixture()
def superproject_with_unmapped_gitlink(tmp_path: Path) -> tuple[Path, Path]:
    """A repository carrying a gitlink that `.gitmodules` does not mention."""
    root = tmp_path / "superproject"
    manifest_path = _build_superproject(root, gitlinks={"vendored": "a" * 40})
    return root, manifest_path


def test_validator_reports_a_gitlink_absent_from_gitmodules(
    superproject_with_unmapped_gitlink: tuple[Path, Path],
) -> None:
    """The successor of the characterisation test for the root cause behind B2.

    Until task-governance-0034 this asserted the *opposite* -- that
    `validate_manifest` reports nothing at all here -- because it built its
    `undeclared-submodule` check from `.gitmodules` entries alone, so an
    undeclared gitlink with no mapping produced no finding. That was recorded as
    current behaviour, not desired behaviour, and the fix has now landed: the
    check keys on the union of `.gitmodules` paths and mode-160000 index entries.

    This fixture happens to exercise *both* halves of the blind spot at once --
    the gitlink is unmapped, and the parent has no declared child either -- which
    is why the two tests below hold one half still to prove each independently.
    """
    root, manifest_path = superproject_with_unmapped_gitlink

    assert _tracked_gitlinks(root) == {"vendored": "a" * 40}

    assert _undeclared(root, manifest_path) == ["vendored"]


def test_validator_reports_an_unmapped_gitlink_beside_a_declared_child(
    tmp_path: Path,
) -> None:
    """First half in isolation: the candidate set must include unmapped gitlinks.

    The parent here *does* have a declared child, so it reaches the old check's
    candidate map regardless. What it could not see is `vendored`: absent from
    `.gitmodules`, it never entered `modules`, so the set difference had nothing
    to find. Only keying on the union of both path sources reports it.
    """
    root = tmp_path / "superproject"
    manifest_path = _build_superproject(
        root,
        gitlinks={"declared-child": "b" * 40, "vendored": "a" * 40},
        mapped=("declared-child",),
        declared=("declared-child",),
    )

    assert _undeclared(root, manifest_path) == ["vendored"]


def test_validator_reports_a_mapped_gitlink_under_a_parent_with_no_declared_child(
    tmp_path: Path,
) -> None:
    """Second half in isolation: the check must reach parents with no declared child.

    `mapped-orphan` *is* in `.gitmodules`, so unioning the two path sources would
    be enough to name it -- if the parent were ever visited. It was not: the old
    candidate map was populated only as a side effect of iterating declared
    repositories, so a parent with zero declared children never entered it. That
    is exactly the `coding-engine` case before its children were declared, and it
    is why a fix that only unions the two sources still misses this.
    """
    root = tmp_path / "superproject"
    manifest_path = _build_superproject(
        root,
        gitlinks={"mapped-orphan": "c" * 40},
        mapped=("mapped-orphan",),
        declared=(),
    )

    assert _undeclared(root, manifest_path) == ["mapped-orphan"]


def test_validator_reports_nothing_when_every_gitlink_is_declared(
    tmp_path: Path,
) -> None:
    """The widened candidate set must not manufacture a finding.

    A guard against over-reporting rather than a red-first case: this passed
    before the fix too. It is what keeps the union from turning every correctly
    declared gitlink into noise -- the concrete form of the constraint that no
    existing finding may change.
    """
    root = tmp_path / "superproject"
    manifest_path = _build_superproject(
        root,
        gitlinks={"declared-child": "b" * 40},
        mapped=("declared-child",),
        declared=("declared-child",),
    )

    assert validate_manifest(root, manifest_path) == []


def test_validator_reaches_an_initialized_child_as_a_parent(tmp_path: Path) -> None:
    """The reach claim beyond the superproject, which CI cannot otherwise show.

    In the canonical CI state `vibemind-os` is uninitialized, so the widened check
    visits exactly one parent -- the superproject -- and every test above would
    pass just as well if the fix had been hard-coded to it. This constructs the
    other case: a child that *is* locally initialized becomes a parent in its own
    right, and its own unmapped gitlink is reported. Without it the module could
    not honestly claim the check reaches every locally available parent.

    Built by hand rather than with `git submodule add`, which needs
    `protocol.file.allow` for a file-path remote and would make the test depend on
    a git configuration this repository does not set.
    """
    outer = tmp_path / "outer"
    inner = outer / "inner"

    # The inner repository, carrying a gitlink its own .gitmodules never mentions.
    inner_manifest = _build_superproject(inner, gitlinks={"vendored": "a" * 40})
    inner_manifest.unlink()
    inner_pin = _git(inner, "rev-parse", "HEAD").stdout.strip()

    # The outer repository, with `inner` mapped, staged as a gitlink at that pin,
    # and a real worktree on disk -- which is what `initialized` means here.
    _git(outer, "init", "-b", "master")
    _git(outer, "config", "user.name", "V1 Tests")
    _git(outer, "config", "user.email", "v1-tests@example.invalid")
    (outer / ".gitmodules").write_text(
        f'[submodule "inner"]\n\tpath = inner\n\turl = {_TEST_REMOTE.format(name="inner")}\n',
        encoding="utf-8",
    )
    _git(outer, "add", ".gitmodules")
    _git(outer, "update-index", "--add", "--cacheinfo", f"160000,{inner_pin},inner")
    _git(outer, "commit", "-m", "test: add an initialized child")
    outer_head = _git(outer, "rev-parse", "HEAD").stdout.strip()

    manifest_path = outer / "repo-manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "superproject": {
                    "id": "test-superproject",
                    "path": ".",
                    "current_integration_branch": "master",
                    "target_integration_branch": "main",
                    "branch_rename_status": "approval-required",
                },
                "repositories": [
                    {
                        "id": "inner-child",
                        "parent": "test-superproject",
                        "path": "inner",
                        "kind": "submodule",
                        "expected_gitlink_pin": inner_pin,
                        "remote": _TEST_REMOTE.format(name="inner"),
                        "remote_role": "canonical-origin",
                        "owner": "platform",
                        "required": False,
                        "migration_state": "nested-legacy",
                        "initialization_state": "initialized",
                        "gitlink_state": "present",
                        "evidence": {
                            "source": "local-git",
                            "parent_pin": outer_head,
                            "validation_state": "local",
                        },
                    }
                ],
                "submodule_policy": {"validator_network_access": "forbidden"},
            }
        ),
        encoding="utf-8",
    )

    # `inner` itself is declared, so the only finding is the gitlink one level
    # down -- reported relative to `inner`, the parent it belongs to.
    assert _undeclared(outer, manifest_path) == ["vendored"]
