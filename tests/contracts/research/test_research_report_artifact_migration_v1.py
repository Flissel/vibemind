"""Offline checks on the Deep Research report-artifact migration.

The migration is a *file*. Nothing here connects to a database, starts one, or
executes SQL: every assertion is made against the migration text and against the
service-tier declaration that describes it. That is the whole point of the
staging the authoring task worked under — the migration is written and reviewed
as source, and applying it is a separate user action.

What these tests defend is the one property the linked-artifact shape depends
on: the report artifact must not reach into `public.ideas`. The moment the
migration adds a column, a trigger, or an outbox row on that table, the ideas
sync payload changes and the reason for choosing an artifact over a long idea
body is gone. The declaration claims that property; this file proves the SQL
keeps it.

Locating the migration
----------------------
The file lives in the `vibemind-os` submodule, which CI checks out with
`submodules: false`. These tests therefore skip when the file cannot be found,
and accept `VIBEMIND_OS_ROOT` so a standalone clone can be pointed at:

    VIBEMIND_OS_ROOT=/path/to/vibemind-os python -m pytest \
        tests/contracts/research/test_research_report_artifact_migration_v1.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[3]
DECLARATION = (
    ROOT / "shared" / "contracts" / "research" / "v1" / "research-service-tiers-v1.json"
)

MIGRATION_RELATIVE_PATH = "supabase/migrations/20260817_research_report_artifacts.sql"
TABLE = "research_report_artifacts"

# The table the artifact must never touch, and the sync machinery bound to it
# (vibemind-os @ a9a48af, supabase/migrations/20260610_ideas_sync_triggers.sql).
PROTECTED_TABLE = "ideas"
IDEAS_SYNC_OUTBOX = "ideas_sync_outbox"
IDEAS_SYNC_TRIGGER = "trg_emit_ideas_sync"

# Closed upstream value sets (openfang @ 5d38662, bundled researcher HAND.toml).
HAND_RESEARCH_DEPTH = ["quick", "thorough", "exhaustive"]
HAND_OUTPUT_STYLE = ["brief", "detailed", "academic", "executive"]

SUBJECT_KINDS = ["topic", "idea", "bubble"]


def _vibemind_os_root() -> Path | None:
    override = os.environ.get("VIBEMIND_OS_ROOT")
    candidates = [Path(override)] if override else []
    candidates.append(ROOT / "vibemind-os")
    for candidate in candidates:
        if (candidate / MIGRATION_RELATIVE_PATH).is_file():
            return candidate
    return None


def _strip_sql_comments(sql: str) -> str:
    """Drop `--` comments, leaving single-quoted string literals intact.

    The migration's header, rationale, and rollback recipe are all comments, and
    they legitimately name `public.ideas`, `ALTER PUBLICATION`, and `DROP TABLE`
    in prose. Executable-statement assertions have to look at the code only.
    """
    out: list[str] = []
    in_string = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if in_string:
            out.append(char)
            if char == "'":
                if sql[index + 1 : index + 2] == "'":  # escaped quote
                    out.append("'")
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == "'":
            in_string = True
            out.append(char)
            index += 1
            continue
        if sql.startswith("--", index):
            newline = sql.find("\n", index)
            index = len(sql) if newline == -1 else newline
            continue
        out.append(char)
        index += 1
    return "".join(out)


@pytest.fixture(scope="module")
def migration_text() -> str:
    root = _vibemind_os_root()
    if root is None:
        pytest.skip(
            "vibemind-os checkout not found; set VIBEMIND_OS_ROOT or initialise the submodule"
        )
    return (root / MIGRATION_RELATIVE_PATH).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def statements(migration_text: str) -> str:
    return _strip_sql_comments(migration_text)


@pytest.fixture(scope="module")
def declaration() -> dict[str, object]:
    return json.loads(DECLARATION.read_text(encoding="utf-8"))


# ── The declaration points at this file, and calls it unapplied ─────────────


def test_declaration_names_this_migration(declaration: dict[str, object]) -> None:
    artifact_side = declaration["report_persistence"]["artifact_side"]
    assert artifact_side["migration"] == MIGRATION_RELATIVE_PATH
    assert artifact_side["repo"] == "Flissel/vibemind-os"
    assert artifact_side["record"] == TABLE


def test_migration_declares_itself_unapplied(migration_text: str) -> None:
    # A reviewer opening the file must see the staging before the SQL.
    header = migration_text[: migration_text.index("BEGIN;")]
    assert "NOT APPLIED" in header


# ── public.ideas is not touched. This is the load-bearing property. ─────────


def test_migration_does_not_alter_the_ideas_table(statements: str) -> None:
    altered = re.findall(r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w.\"]+)", statements, re.I)
    for target in altered:
        assert target.split(".")[-1].strip('"') != PROTECTED_TABLE, (
            f"migration alters {target}; that changes the ideas sync payload"
        )


def test_migration_creates_no_trigger_and_no_function(statements: str) -> None:
    # The ideas sync fires from a trigger on public.ideas. Adding one here — on
    # either table — would put report writes into a sync chain that D3 has not
    # been decided on yet.
    assert not re.search(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\b", statements, re.I)
    assert not re.search(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\b", statements, re.I)


def test_migration_does_not_write_into_the_ideas_sync_outbox(statements: str) -> None:
    assert IDEAS_SYNC_OUTBOX not in statements
    assert IDEAS_SYNC_TRIGGER not in statements


def test_migration_writes_no_rows_at_all(statements: str) -> None:
    # No seed data, no backfill: a schema change only.
    for verb in (r"\bINSERT\s+INTO\b", r"\bUPDATE\s+\w", r"\bDELETE\s+FROM\b", r"\bCOPY\b"):
        assert not re.search(verb, statements, re.I), f"migration executes {verb}"


def test_migration_drops_nothing_but_its_own_policy(statements: str) -> None:
    drops = re.findall(r"\bDROP\s+(\w+)", statements, re.I)
    assert [drop.upper() for drop in drops] == ["POLICY"], (
        f"migration issues unexpected DROP statements: {drops}"
    )


# ── One table, and the foreign key points from it to ideas ─────────────────


def test_migration_creates_exactly_one_table(statements: str) -> None:
    created = re.findall(r"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([\w.\"]+)", statements, re.I)
    assert [name.split(".")[-1] for name in created] == [TABLE]


def test_the_foreign_keys_point_at_ideas_from_this_side(statements: str) -> None:
    references = re.findall(r"REFERENCES\s+([\w.\"]+)\s*\(\s*(\w+)\s*\)", statements, re.I)
    assert references, "the artifact declares no link to an idea"
    for table, column in references:
        assert table.split(".")[-1].strip('"') == PROTECTED_TABLE
        assert column == "id"


def test_both_bubble_shapes_remain_storable(statements: str) -> None:
    # D2 is open: a single cluster report sets bubble_id alone, a per-member
    # report sets both. Neither column may be NOT NULL.
    for column in ("idea_id", "bubble_id"):
        match = re.search(rf"^\s*{column}\s+TEXT[^,]*", statements, re.I | re.M)
        assert match, f"{column} is missing"
        assert "NOT NULL" not in match.group(0).upper()


def test_the_artifact_row_carries_no_updated_at(statements: str) -> None:
    # Write-once. A re-run appends a row rather than editing the first report.
    assert not re.search(r"^\s*updated_at\b", statements, re.I | re.M)


# ── Fail-closed guards the declaration promises ────────────────────────────


def test_citation_count_cannot_be_zero(statements: str) -> None:
    assert re.search(r"citation_count\s*>=\s*1", statements)
    # No default either: the writer has to state the count.
    match = re.search(r"^\s*citation_count\s+INTEGER[^,]*", statements, re.I | re.M)
    assert match and "DEFAULT" not in match.group(0).upper()


def test_missing_internal_context_must_be_disclosed(statements: str) -> None:
    # E12 forbids silent degradation.
    assert re.search(
        r"CHECK\s*\(\s*internal_context_used\s+OR\s+context_disclosure\s+IS\s+NOT\s+NULL\s*\)",
        statements,
        re.I,
    )


@pytest.mark.parametrize("value", HAND_RESEARCH_DEPTH)
def test_depth_check_carries_the_hand_value_set(statements: str, value: str) -> None:
    depth_check = re.search(r"depth\s+IN\s*\(([^)]*)\)", statements, re.I)
    assert depth_check and f"'{value}'" in depth_check.group(1)


@pytest.mark.parametrize("value", HAND_OUTPUT_STYLE)
def test_output_style_check_carries_the_hand_value_set(statements: str, value: str) -> None:
    style_check = re.search(r"output_style\s+IN\s*\(([^)]*)\)", statements, re.I)
    assert style_check and f"'{value}'" in style_check.group(1)


@pytest.mark.parametrize("value", SUBJECT_KINDS)
def test_subject_type_check_carries_the_contract_subject_model(
    statements: str, value: str
) -> None:
    subject_check = re.search(r"subject_type\s+IN\s*\(([^)]*)\)", statements, re.I)
    assert subject_check and f"'{value}'" in subject_check.group(1)


def test_contract_ids_are_validated_at_the_storage_boundary(
    statements: str, declaration: dict[str, object]
) -> None:
    # artifact_ref is the join key to ResearchResultV1.artifact_refs; a typo
    # that reaches storage is unrecoverable.
    assert "^artifact_v1_[0-9A-HJKMNPQRSTVWXYZ]{26}$" in statements
    assert declaration["report_persistence"]["artifact_side"]["join_key"] == "artifact_ref"


# ── Idempotency and the rollback path ──────────────────────────────────────


def test_every_created_object_is_guarded(statements: str) -> None:
    for keyword in ("CREATE TABLE", "CREATE INDEX"):
        occurrences = re.findall(rf"\b{keyword}\b(?:\s+IF\s+NOT\s+EXISTS)?", statements, re.I)
        assert occurrences, f"no {keyword} found"
        for occurrence in occurrences:
            assert "IF NOT EXISTS" in occurrence.upper(), f"unguarded {occurrence!r}"


def test_the_policy_is_dropped_before_it_is_created(statements: str) -> None:
    drop_at = statements.upper().find("DROP POLICY IF EXISTS")
    create_at = statements.upper().find("CREATE POLICY")
    assert 0 <= drop_at < create_at


def test_the_publication_change_is_guarded(statements: str) -> None:
    # The neighbouring migrations issue a bare `ALTER PUBLICATION ... ADD TABLE`,
    # which aborts with 42710 on a re-run. Here it must sit behind an existence
    # check, or the file is not re-runnable end to end.
    assert re.search(r"ALTER\s+PUBLICATION", statements, re.I)
    assert re.search(r"pg_publication_tables", statements, re.I)
    assert re.search(r"NOT\s+EXISTS\s*\(", statements, re.I)


def test_the_file_documents_its_own_rollback(migration_text: str) -> None:
    # Written as a comment on purpose: a rollback is an operator action, and the
    # neighbouring migrations set no precedent for a separate down-migration file.
    tail = migration_text[migration_text.index("NOTIFY pgrst") :]
    assert "Rollback" in tail
    assert f"DROP TABLE IF EXISTS public.{TABLE}" in tail
    assert "ALTER PUBLICATION supabase_realtime DROP TABLE" in tail
    assert "Idempotency" in tail


def test_the_rollback_states_what_happens_to_written_artifacts(migration_text: str) -> None:
    tail = migration_text[migration_text.index("NOTIFY pgrst") :]
    assert "CSV HEADER" in tail, "no preservation step for artifacts already written"
    assert "public.ideas" in tail, "the rollback does not say what happens to the ideas side"


# ── The grammar itself, when a parser is available ─────────────────────────


def test_migration_parses_under_the_postgres_grammar(migration_text: str) -> None:
    pglast = pytest.importorskip("pglast", reason="pglast not installed; grammar check skipped")
    pglast.parse_sql(migration_text)
