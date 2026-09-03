"""Static guard: ``tests/contracts`` must be runnable from the pinned requirements.

task-governance-0037 measured that ``python -m pytest tests/contracts -q``, in a
container carrying only ``tools/v1_governance/requirements.txt``, aborted at
COLLECTION with 16 errors and ran zero tests: ``shared/contracts/validate.py``
imports ``jsonschema``, which the pinned set did not contain. Nothing in the
repository noticed, because the required CI checks run only
``tests/architecture/test_v1_ci_contract.py`` and
``tests/v1_governance/test_manifest.py`` -- ``tests/contracts`` is not gated.

This guard closes the hole statically, without installing anything: it walks the
import graph of ``tests/contracts`` (including the repo-local ``shared`` modules
that suite pulls in, which is where the 16 errors actually originated), keeps the
third-party roots, and requires each one to be pinned.

The one third-party root that is deliberately NOT pinned is ``vibemind_shared``.
It is not on PyPI: it ships from the nested ``shared`` submodule inside the
``vibemind-os`` submodule, which ``repo-manifest.yaml`` declares as
``initialization_state: uninitialized``. Every route to making it importable
breaks a declared invariant, so task-governance-0037 enumerated the routes and
stopped rather than choosing one. It is recorded below as a named open item, not
waived silently: when that design question is answered, this guard must be
updated in the same change.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SUITE = REPO_ROOT / "tests" / "contracts"
PINNED_REQUIREMENTS = REPO_ROOT / "tools" / "v1_governance" / "requirements.txt"

# Distribution name (normalised, lowercase) -> import roots it provides.
# Only needed where the two differ, or to be explicit; unknown distributions
# fall back to their own normalised name. A wrong/missing entry makes the guard
# report a pinned dependency as unpinned -- it fails loud, never silent.
_DISTRIBUTION_IMPORT_ROOTS: dict[str, frozenset[str]] = {
    "pyyaml": frozenset({"yaml"}),
    "pytest": frozenset({"pytest"}),
    "jsonschema": frozenset({"jsonschema"}),
}

# Third-party import roots the contracts suite needs that are knowingly absent
# from the pinned set, each with the reason it stays absent. Keep this minimal;
# every entry is an admission that ``tests/contracts`` cannot run clean.
KNOWN_UNPINNED_IMPORT_ROOTS: dict[str, str] = {
    "vibemind_shared": (
        "Ships from the nested 'shared' submodule inside vibemind-os, which "
        "repo-manifest.yaml declares initialization_state: uninitialized. Not "
        "installable from PyPI. See docs/operations/"
        "2026-08-18-task-governance-0037-handoff.md for the enumerated routes "
        "and the open design question."
    ),
}


def _normalise(distribution: str) -> str:
    return distribution.strip().lower().replace("_", "-")


def _pinned_import_roots() -> set[str]:
    """Import roots provided by the pinned requirements file."""
    roots: set[str] = set()
    for raw_line in PINNED_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        # Split the distribution name off any version specifier / extras.
        name = line
        for separator in ("[", "=", "<", ">", "!", "~", ";", " "):
            name = name.split(separator, 1)[0]
        name = _normalise(name)
        if not name:
            continue
        roots |= _DISTRIBUTION_IMPORT_ROOTS.get(name, frozenset({name.replace("-", "_")}))
    return roots


def _import_roots(source: Path) -> set[str]:
    """Top-level module names imported by *source* (absolute imports only)."""
    roots: set[str] = set()
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import: same package, never third-party.
            if node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


def _dotted_imports(source: Path) -> set[str]:
    """Fully dotted absolute module names imported by *source*."""
    names: set[str] = set()
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module)
    return names


def _repo_local_module_path(dotted: str) -> Path | None:
    """Resolve *dotted* to a file inside the repository, or None if external."""
    parts = dotted.split(".")
    module = REPO_ROOT.joinpath(*parts).with_suffix(".py")
    if module.is_file():
        return module
    package = REPO_ROOT.joinpath(*parts, "__init__.py")
    if package.is_file():
        return package
    return None


def _reachable_sources() -> set[Path]:
    """Every ``tests/contracts`` module plus the repo-local modules it imports.

    The 16 collection errors did not come from a direct import in the suite:
    they came through ``shared.contracts.validate``. A guard that only looked at
    the suite's own import lines would have been a weaker guard, so the walk
    follows repo-local imports transitively.
    """
    sources = set(CONTRACTS_SUITE.rglob("*.py"))
    queue = list(sources)
    while queue:
        current = queue.pop()
        for dotted in _dotted_imports(current):
            resolved = _repo_local_module_path(dotted)
            if resolved is not None and resolved not in sources:
                sources.add(resolved)
                queue.append(resolved)
    return sources


def _third_party_import_roots() -> set[str]:
    """Third-party import roots reachable from the contracts suite."""
    import sys

    roots: set[str] = set()
    for source in _reachable_sources():
        roots |= _import_roots(source)
    return {
        root
        for root in roots
        if root not in sys.stdlib_module_names
        and root != "__future__"
        and _repo_local_module_path(root) is None
    }


def test_contracts_suite_has_third_party_imports_to_check() -> None:
    # Guard against the guard silently passing because the walk found nothing.
    assert _third_party_import_roots(), "import walk produced no third-party roots"


def test_every_third_party_import_of_contracts_suite_is_pinned() -> None:
    pinned = _pinned_import_roots()
    unpinned = {
        root
        for root in _third_party_import_roots()
        if root not in pinned and root not in KNOWN_UNPINNED_IMPORT_ROOTS
    }
    assert not unpinned, (
        "tests/contracts imports third-party modules that "
        f"{PINNED_REQUIREMENTS.relative_to(REPO_ROOT)} does not pin: "
        f"{sorted(unpinned)}. Running the suite from the pinned set alone will "
        "abort at collection with ModuleNotFoundError. Pin them, or record them "
        "in KNOWN_UNPINNED_IMPORT_ROOTS with the reason they cannot be pinned."
    )


def test_known_unpinned_imports_are_still_actually_imported() -> None:
    # Keeps the waiver list from outliving the problem it documents.
    stale = set(KNOWN_UNPINNED_IMPORT_ROOTS) - _third_party_import_roots()
    assert not stale, (
        f"KNOWN_UNPINNED_IMPORT_ROOTS lists {sorted(stale)}, which "
        "tests/contracts no longer imports. Drop the entry."
    )


def test_known_unpinned_imports_are_exactly_the_open_design_question() -> None:
    # vibemind_shared is the only admitted gap. If a second one appears, that is
    # a new decision and must be made deliberately, not inherited from here.
    assert set(KNOWN_UNPINNED_IMPORT_ROOTS) == {"vibemind_shared"}
