"""Agreement guard between the OpenFang MCP authority contract and its own
declared normative document.

`shared/contracts/openfang-mcp-authority-v1.json` names
`docs/contracts/openfang-mcp-authority-v1.md` in its `normative_document`
field, but until this file existed nothing read that markdown: a grep for
`openfang-mcp-authority-v1.md` and for `normative_document` across the Python
tree returned nothing. The two halves of one contract could therefore disagree
about which servers are registered with nothing going red — which is exactly
how `task-openfang-0022` came to correct the JSON while leaving the markdown
asserting the opposite in three places.

Every expectation here is **derived from the JSON**, which is the
machine-readable side and the one a registration change edits first. Nothing
below hardcodes a server name or a count; a hardcoded list would go stale on
the next registration change, which is the same failure this guard exists to
prevent, one level up.

Scope note: this file reads only two superproject documents. It needs no
`vibemind-os` submodule and makes no live-registration claim. It is a local
guard, not a CI gate — the required checks run only
`tests/architecture/test_v1_ci_contract.py` and
`tests/v1_governance/test_manifest.py`, so `tests/contracts/` is not collected
by CI.

Style follows tests/contracts/test_v1_contracts.py and tests/v1_governance:
plain pytest, paths resolved from the repository root, assertions phrased as
authority claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "shared" / "contracts" / "openfang-mcp-authority-v1.json"

# The three registration states whose membership the markdown enumerates
# exhaustively, mapped to the bold label the conflict register gives each one.
# The labels are structural anchors used to find the prose item; the server
# sets they are checked against come from the JSON, never from this table.
CONFLICT_REGISTER_LABELS = {
    "unregistered": "Unregistered but scoped",
    "template-only": "Template-only",
    "commented-out": "Commented-out but scoped",
}


def load_contract() -> dict:
    assert CONTRACT_PATH.exists(), (
        f"missing contract document {CONTRACT_PATH.relative_to(ROOT)}"
    )
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def normative_document_path() -> Path:
    """Resolve the markdown the contract itself points at, not a path we chose."""
    declared = load_contract().get("normative_document")
    assert isinstance(declared, str) and declared, (
        "contract declares no normative_document"
    )
    return ROOT / declared


def load_normative_document() -> str:
    path = normative_document_path()
    assert path.exists(), (
        f"contract names normative_document {path.relative_to(ROOT)} "
        "but no such file exists"
    )
    return path.read_text(encoding="utf-8")


def servers_by_registration(contract: dict) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for name, entry in contract["servers"].items():
        grouped.setdefault(entry["registration"], set()).add(name)
    return grouped


def backticked_server_tokens(cell: str, known_servers: set[str]) -> set[str]:
    """Backticked tokens in `cell` that have the shape of a server identity.

    Evidence references such as `agent.rs:1714-1730` and `template:393-401`
    also appear in backticks; they carry a `:`, `/` or `.` and are dropped.
    What survives is asserted against the contract's own server catalog, so a
    token that is neither evidence nor a known server fails loudly rather than
    being silently filtered away.
    """
    tokens = set()
    for token in re.findall(r"`([^`]+)`", cell):
        if any(character in token for character in ":/."):
            continue
        tokens.add(token)
    unknown = tokens - known_servers
    assert not unknown, (
        f"normative document names {sorted(unknown)} as server identities, "
        "but the contract's server catalog does not declare them"
    )
    return tokens


def state_table_rows(document: str) -> dict[str, str]:
    """Map each registration state to the Examples cell of its state-table row."""
    rows: dict[str, str] = {}
    for line in document.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        # A state-table row is `| `state` | meaning | examples |`.
        if len(cells) != 5:
            continue
        state_match = re.fullmatch(r"`([a-z-]+)`", cells[1])
        if state_match is None:
            continue
        rows[state_match.group(1)] = cells[3]
    return rows


def conflict_register_items(document: str) -> dict[str, str]:
    """Map each bold conflict-register label to that item's full text.

    Items are numbered and wrap across lines, so continuation lines are folded
    back into the item they belong to before matching.
    """
    section = document.split("## Conflict and gap register", 1)
    assert len(section) == 2, "normative document has no conflict and gap register"
    body = section[1].split("\n## ", 1)[0]

    items: dict[str, str] = {}
    current: list[str] | None = None
    for line in body.splitlines():
        if re.match(r"^\d+\.\s", line):
            if current is not None:
                _record_item(items, " ".join(current))
            current = [re.sub(r"^\d+\.\s", "", line)]
        elif current is not None and line.startswith("   "):
            current.append(line.strip())
        elif current is not None and not line.strip():
            _record_item(items, " ".join(current))
            current = None
    if current is not None:
        _record_item(items, " ".join(current))
    return items


def _record_item(items: dict[str, str], text: str) -> None:
    label = re.match(r"\*\*(.+?):?\*\*", text)
    if label is not None:
        items[label.group(1).rstrip(":")] = text


def test_contract_names_a_normative_document_that_exists() -> None:
    """The `normative_document` field must resolve to a real file.

    This is the assertion whose absence let the two halves drift: nothing in
    the Python tree read this field at all.
    """
    path = normative_document_path()

    assert path.exists(), (
        f"contract declares normative_document '{path.relative_to(ROOT)}' "
        "but that file does not exist"
    )
    assert path.suffix == ".md"


def test_registered_server_count_in_the_normative_document_matches_the_contract() -> None:
    """`registers **N** servers` must equal the number the JSON declares."""
    contract = load_contract()
    document = load_normative_document()
    expected = len(servers_by_registration(contract).get("registered", set()))

    match = re.search(r"registers \*\*(\d+)\*\* servers", document)
    assert match is not None, (
        "normative document no longer states a registered server count"
    )
    declared = int(match.group(1))

    assert declared == expected, (
        f"normative document says the pinned checkout registers {declared} "
        f"servers, but the contract declares {expected} servers as "
        "'registered'"
    )


@pytest.mark.parametrize("state", sorted(CONFLICT_REGISTER_LABELS))
def test_state_table_examples_carry_the_registration_state_they_illustrate(
    state: str,
) -> None:
    """No server may be named under a state the contract does not give it.

    Soundness, asserted for every state: the `registered` row samples 2 of its
    members and is not exhaustive, so this checks that each named server really
    does carry that state, not that the row lists all of them.
    """
    contract = load_contract()
    document = load_normative_document()
    grouped = servers_by_registration(contract)
    known = set(contract["servers"])

    rows = state_table_rows(document)
    assert state in rows, f"normative document has no state-table row for '{state}'"

    named = backticked_server_tokens(rows[state], known)
    misfiled = {
        server: contract["servers"][server]["registration"]
        for server in sorted(named)
        if server not in grouped.get(state, set())
    }

    assert not misfiled, (
        f"normative document's '{state}' state-table row names "
        f"{sorted(misfiled)}, but the contract declares them "
        f"{sorted(set(misfiled.values()))}"
    )


@pytest.mark.parametrize("state", sorted(CONFLICT_REGISTER_LABELS))
def test_conflict_register_enumerates_exactly_the_contract_membership(
    state: str,
) -> None:
    """Completeness, where the document claims it.

    The conflict register summarises the JSON's `gaps` and enumerates each
    state's membership, so here set equality is the right assertion: a server
    listed that the contract no longer places in this state is a false claim,
    and one omitted is a missing disclosure.
    """
    contract = load_contract()
    document = load_normative_document()
    expected = servers_by_registration(contract).get(state, set())
    known = set(contract["servers"])

    label = CONFLICT_REGISTER_LABELS[state]
    items = conflict_register_items(document)
    assert label in items, (
        f"conflict register has no '{label}' item; found {sorted(items)}"
    )

    named = backticked_server_tokens(items[label], known)

    assert named == expected, (
        f"conflict register's '{label}' item names {sorted(named)}, but the "
        f"contract declares '{state}' for {sorted(expected)}"
    )


# ---------------------------------------------------------------------------
# Space scopes: mcp_servers, mcp_tools and mcp_events
#
# `task-openfang-0023` closed the registration-status half of this agreement.
# `task-openfang-0025` then aligned the research space's scope in the JSON and
# found the markdown stale about it in three further places, none of which the
# assertions above could see: they read registration states, and a scope is not
# a registration. What follows widens the same guard to the per-space scope
# fields, so the two halves of the contract must also agree about which servers
# a space may reach, which tools it is granted on them, and which events run
# over MCP.
#
# The derivation discipline is unchanged and is the whole point: no space name,
# server name, tool name, event name or count appears here as an expectation.
# Column headings and prose anchors are used to *locate* claims; the values
# every claim is measured against come from the JSON.
# ---------------------------------------------------------------------------

# Column headings of the two tables that carry per-space scope claims. These
# are structural anchors — the document's own column names — used to find the
# tables without depending on section titles or line numbers. They assert
# nothing about content.
SCOPE_TABLE_HEADERS = ("Space", "Agent role", "MCP scope")
GRANT_TABLE_HEADERS = ("Space", "Server", "Granted tools")

# A lexicon, not an expectation: the document spells small counts as words, so
# a word has to be turned back into a number before it can be compared with a
# number the JSON derives.
NUMBER_WORDS = {
    word: value
    for value, word in enumerate(
        (
            "zero", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
            "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
        )
    )
}

# Cell values the document uses to mean "nothing here", so that an empty scope
# reads as a deliberate statement rather than a blank.
EMPTY_CELL_MARKERS = {"", "-", "–", "—"}


def markdown_table(document: str, headers: tuple[str, ...]) -> list[dict[str, str]]:
    """Return the rows of the one pipe table whose header row is `headers`.

    Rows come back as dicts keyed by the document's own column names. Anchoring
    on the header rather than on a section title or a line number keeps the
    guard working when the prose around a table is rewritten, and makes it fail
    loudly — rather than silently checking nothing — if a table is renamed away.
    """
    tables: list[list[dict[str, str]]] = []
    rows: list[dict[str, str]] = []
    matched = False
    for line in document.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if matched:
                tables.append(rows)
            matched, rows = False, []
            continue
        cells = tuple(cell.strip() for cell in stripped.strip("|").split("|"))
        if cells == headers:
            matched, rows = True, []
            continue
        if not matched:
            continue
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
            continue
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    if matched:
        tables.append(rows)

    assert len(tables) == 1, (
        f"normative document should carry exactly one table with columns "
        f"{list(headers)}; found {len(tables)}"
    )
    return tables[0]


def scope_cell_servers(cell: str, known_servers: set[str]) -> set[str]:
    """Servers named in a bare comma-separated MCP-scope cell.

    Unlike the registration tables, this column carries plain names rather than
    backticked ones. Anything that survives the empty-cell markers is asserted
    against the contract's own server catalog, so a stray or misspelt token
    fails loudly instead of being quietly discarded.
    """
    if cell.strip() in EMPTY_CELL_MARKERS:
        return set()
    named = [token.strip().strip("`") for token in cell.split(",")]
    named = [token for token in named if token not in EMPTY_CELL_MARKERS]
    duplicates = sorted({token for token in named if named.count(token) > 1})
    assert not duplicates, (
        f"normative document names {duplicates} more than once in one MCP "
        "scope cell"
    )
    unknown = sorted(set(named) - known_servers)
    assert not unknown, (
        f"normative document names {unknown} as scoped servers, but the "
        "contract's server catalog does not declare them"
    )
    return set(named)


def contract_grants(contract: dict) -> dict[tuple[str, str], list[str]]:
    """Every (space, server) tool grant the contract declares, from the JSON."""
    return {
        (space, server): tools
        for space, entry in contract["spaces"].items()
        for server, tools in (entry.get("mcp_tools") or {}).items()
    }


def qualified_event_name(event: dict) -> str:
    """The space-qualified name of one MCP-bound event, derived from the JSON.

    `mcp_events[].event` copies the registry's own event key, and the registry
    keys are not uniform: `bubbles` keys its event `bubble.create` while
    `research`, whose block declares `prefixes: [research.]`, keys its events
    `research.summarize` and `research.to_idea` — already space-qualified. So
    the space is prefixed only when it is not there already, which is what the
    registry's prefix semantics mean and what avoids inventing a name like
    `research.research.summarize` that no source uses.
    """
    space, name = event["space"], event["event"]
    return name if name.startswith(f"{space}.") else f"{space}.{name}"


def mcp_bound_event_claim(document: str) -> tuple[int, set[str]]:
    """The count and the membership the N4 prose claims for MCP-bound events.

    The sentence names its events in backticks and ends at the first backtick
    followed by a full stop, which is what bounds the list — event names contain
    full stops themselves, so a sentence split on '.' would cut them in half.
    """
    matches = list(
        re.finditer(
            r"\b(\w+)\s+MCP-bound events\b[^`]*?\bare\s+(.*?`)\.\s",
            document,
            re.DOTALL,
        )
    )
    assert len(matches) == 1, (
        "normative document should state its MCP-bound events exactly once; "
        f"found {len(matches)} such statements"
    )
    word, listing = matches[0].group(1).lower(), matches[0].group(2)
    assert word in NUMBER_WORDS, (
        f"normative document counts its MCP-bound events as '{word}', which is "
        "not a number word this guard can read"
    )
    return NUMBER_WORDS[word], set(re.findall(r"`([^`]+)`", listing))


def _scope_ids(contract: dict) -> list[str]:
    return sorted(contract["spaces"])


_CONTRACT = load_contract()
SPACE_IDS = _scope_ids(_CONTRACT)
GRANT_IDS = sorted(contract_grants(_CONTRACT))


def test_scope_table_covers_exactly_the_spaces_the_contract_declares() -> None:
    """The N2 table enumerates the canonical spaces, so set equality holds.

    A space the contract declares and the document omits is an undisclosed
    scope; one the document keeps after the contract drops it is a false claim.
    """
    contract = load_contract()
    document = load_normative_document()

    tabled = {row["Space"] for row in markdown_table(document, SCOPE_TABLE_HEADERS)}
    declared = set(contract["spaces"])

    assert tabled == declared, (
        f"normative document's scope table lists {sorted(tabled)}, but the "
        f"contract declares the spaces {sorted(declared)}"
    )


@pytest.mark.parametrize("space", SPACE_IDS)
def test_scope_table_row_names_the_mcp_servers_the_contract_scopes(space: str) -> None:
    """Per space, the MCP scope cell must be the contract's `mcp_servers`.

    Membership is the authority claim — a server named here may be reached and
    one omitted may not — so this is set equality rather than list equality;
    ordering carries no authority and a reordering is not a disagreement. The
    duplicate check lives in the cell parser so that ordering being unasserted
    cannot hide a name written twice.
    """
    contract = load_contract()
    document = load_normative_document()
    expected = set(contract["spaces"][space]["mcp_servers"])
    known = set(contract["servers"])

    rows = {row["Space"]: row for row in markdown_table(document, SCOPE_TABLE_HEADERS)}
    assert space in rows, f"normative document's scope table has no row for '{space}'"

    named = scope_cell_servers(rows[space]["MCP scope"], known)

    assert named == expected, (
        f"normative document scopes '{space}' to {sorted(named)}, but the "
        f"contract declares mcp_servers {sorted(expected)}"
    )


@pytest.mark.parametrize("space", SPACE_IDS)
def test_scope_table_row_names_the_agent_role_the_contract_binds(space: str) -> None:
    """Per space, the agent-role cell must name the contract's `agent_role`.

    Not one of the three scope fields this guard was widened for, but it is the
    third column of the same row and the same parse, and a scope stated against
    the wrong role is as false as a wrong scope. A trailing parenthetical is an
    annotation rather than part of the name, and the contract's `enabled` flag
    is what decides whether the row must carry the disabled note.
    """
    contract = load_contract()
    document = load_normative_document()
    entry = contract["spaces"][space]

    rows = {row["Space"]: row for row in markdown_table(document, SCOPE_TABLE_HEADERS)}
    assert space in rows, f"normative document's scope table has no row for '{space}'"

    cell = rows[space]["Agent role"]
    named = re.sub(r"\s*\([^)]*\)\s*$", "", cell).strip().strip("`")

    assert named == entry["agent_role"], (
        f"normative document binds '{space}' to agent role '{named}', but the "
        f"contract declares '{entry['agent_role']}'"
    )
    assert ("disabled" in cell.lower()) == (not entry["enabled"]), (
        f"normative document's '{space}' row reads '{cell}', which disagrees "
        f"with the contract's enabled={entry['enabled']}"
    )


def test_tool_grant_table_enumerates_exactly_the_contract_grants() -> None:
    """The N3 table introduces itself as *the* explicit grants, so it must be
    complete.

    A (space, server) pair the contract grants and the table omits is an
    undisclosed grant — which is precisely how the research space's two grants
    went unstated — and a pair the table keeps after the contract drops it
    claims an authority that no longer exists.
    """
    contract = load_contract()
    document = load_normative_document()

    tabled = {
        (row["Space"], row["Server"])
        for row in markdown_table(document, GRANT_TABLE_HEADERS)
    }
    declared = set(contract_grants(contract))

    assert tabled == declared, (
        f"normative document's tool-grant table enumerates {sorted(tabled)}, "
        f"but the contract declares the grants {sorted(declared)}"
    )


@pytest.mark.parametrize("grant", GRANT_IDS, ids=lambda grant: f"{grant[0]}-{grant[1]}")
def test_tool_grant_row_names_the_tools_the_contract_grants(
    grant: tuple[str, str],
) -> None:
    """Per (space, server) grant, the granted tools must be the contract's.

    Set equality again, and for the same reason: which tools are reachable is
    the claim, the order they are written in is not.
    """
    space, server = grant
    contract = load_contract()
    document = load_normative_document()
    expected = set(contract_grants(contract)[grant])

    rows = {
        (row["Space"], row["Server"]): row
        for row in markdown_table(document, GRANT_TABLE_HEADERS)
    }
    assert grant in rows, (
        f"normative document's tool-grant table has no row granting '{space}' "
        f"tools on '{server}', but the contract grants "
        f"{sorted(expected)} there"
    )

    named = set(re.findall(r"`([^`]+)`", rows[grant]["Granted tools"]))

    assert named == expected, (
        f"normative document grants '{space}' the tools {sorted(named)} on "
        f"'{server}', but the contract grants {sorted(expected)}"
    )


def test_mcp_bound_event_count_in_the_normative_document_matches_the_contract() -> None:
    """The spelled-out count in N4 must equal the number of `mcp_events`."""
    contract = load_contract()
    document = load_normative_document()
    expected = len(contract["mcp_events"])

    declared, _ = mcp_bound_event_claim(document)

    assert declared == expected, (
        f"normative document says there are {declared} MCP-bound events in the "
        f"pinned checkout, but the contract declares {expected}"
    )


def test_mcp_bound_event_prose_names_exactly_the_contract_events() -> None:
    """N4 enumerates its MCP-bound events, so set equality holds there.

    An event the contract binds over MCP and the document omits is an
    undisclosed MCP call path with a provenance requirement attached; one the
    document names after the contract drops it is a false claim.
    """
    contract = load_contract()
    document = load_normative_document()
    expected = {qualified_event_name(event) for event in contract["mcp_events"]}

    _, named = mcp_bound_event_claim(document)

    assert named == expected, (
        f"normative document names the MCP-bound events {sorted(named)}, but "
        f"the contract declares {sorted(expected)}"
    )


# ---------------------------------------------------------------------------
# Source-pin agreement (task-openfang-0028)
#
# The markdown grounds *every* claim it makes in two named gitlink pins. The
# JSON carries the same two under `source_pins`, and `repo-manifest.yaml`
# carries them a third time as `expected_gitlink_pin`. When `task-openfang-0024`
# advanced the JSON's pins and its 24 stale line references, the markdown was
# left behind: it kept naming the superseded trees while its own line locators
# were silently re-interpreted against them.
#
# That is the expensive failure, because it invalidates the document wholesale
# rather than in one cell — a reader resolving any of its 46 line locators
# resolves them against the wrong checkout. The assertion below is two string
# comparisons and would have gone red the moment `0024` merged.
#
# What it deliberately does NOT do is check that the individual line locators
# resolve. That needs both submodules populated, and this file is submodule-free
# by design (see the module docstring); a submodule-gated assertion here would
# SKIP in most environments, and a SKIP read as a pass is precisely the trap
# this chain keeps documenting. Locator resolution belongs in the integration
# suite, which is already submodule-gated. Recorded as a recommendation, not
# built here.
# ---------------------------------------------------------------------------

GROUNDING_ANCHOR = "grounded in the real"
PIN_IN_BACKTICKS = re.compile(r"`([0-9a-f]{40})`")
ANY_PIN = re.compile(r"\b[0-9a-f]{40}\b")


def source_pin_keys(contract: dict) -> tuple[str, str]:
    """Split `source_pins` into its superproject key and its nested key.

    Derived from the JSON rather than written down here: the nested checkout is
    the one whose key carries a path separator. A third pin, or a second nested
    one, fails loudly instead of being silently ignored.
    """
    pins = contract.get("source_pins")
    assert isinstance(pins, dict) and pins, "contract declares no source_pins"
    roots = sorted(key for key in pins if "/" not in key)
    nested = sorted(key for key in pins if "/" in key)
    assert len(roots) == 1 and len(nested) == 1, (
        f"expected one root and one nested source pin, got {sorted(pins)}"
    )
    return roots[0], nested[0]


def grounding_paragraph(document: str) -> str:
    """Return the paragraph in which the markdown states what grounds it."""
    paragraphs = re.split(r"\n\s*\n", document)
    matching = [para for para in paragraphs if GROUNDING_ANCHOR in para]
    assert len(matching) == 1, (
        f"expected exactly one paragraph containing {GROUNDING_ANCHOR!r} in the "
        f"normative document, found {len(matching)}"
    )
    return matching[0]


def grounding_pins(document: str, contract: dict) -> dict[str, str]:
    """Map each `source_pins` key to the pin the markdown states for it.

    The paragraph names the superproject checkout and its pin first, then the
    nested OpenFang pin. That ordering is asserted from the surrounding labels
    rather than assumed, so a document that swapped the two would fail here
    instead of comparing each pin against the wrong repository.
    """
    root_key, nested_key = source_pin_keys(contract)
    paragraph = grounding_paragraph(document)
    pins = PIN_IN_BACKTICKS.findall(paragraph)
    assert len(pins) == 2, (
        f"expected the grounding statement to name 2 pins, found {len(pins)}: {pins}"
    )
    root_pin, nested_pin = pins

    nested_label = nested_key.rsplit("/", 1)[-1]
    assert paragraph.index(f"`{root_key}`") < paragraph.index(root_pin), (
        f"grounding statement does not name {root_key!r} before its pin"
    )
    assert (
        paragraph.lower().index(f"{nested_label} nested pin")
        < paragraph.index(nested_pin)
    ), f"grounding statement does not label the nested {nested_label!r} pin"

    return {root_key: root_pin, nested_key: nested_pin}


@pytest.mark.parametrize("repository", ["vibemind-os", "vibemind-os/openfang"])
def test_normative_document_grounds_itself_at_the_contract_source_pin(
    repository: str,
) -> None:
    """The markdown must name the same checkout the JSON is pinned to.

    Every line locator in the document is only meaningful relative to the tree
    the document says it was read from. If the two halves of the contract name
    different trees, the document's locators point into a checkout nothing else
    in the repository reads, and no amount of per-locator accuracy rescues it.
    """
    contract = load_contract()
    document = load_normative_document()
    expected = contract["source_pins"][repository]

    stated = grounding_pins(document, contract)[repository]

    assert stated == expected, (
        f"normative document grounds its claims in {repository} at {stated}, "
        f"but the contract's source_pins declare {expected}"
    )


def test_normative_document_states_no_pin_outside_its_grounding_statement() -> None:
    """No superseded pin may survive elsewhere in the prose.

    The grounding paragraph is not the only place a 40-character revision could
    be written, and a stale one left in a footnote would re-introduce exactly
    the ambiguity the paragraph resolves.
    """
    contract = load_contract()
    document = load_normative_document()
    declared = set(grounding_pins(document, contract).values())

    found = set(ANY_PIN.findall(document))

    assert found == declared, (
        f"normative document states the pins {sorted(found)}, but its grounding "
        f"statement declares {sorted(declared)}"
    )
