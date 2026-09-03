import re
import subprocess
from pathlib import Path


REGISTER = Path("docs/governance/historical-merge-register-v1.md")
ROW_PATTERN = re.compile(
    r"^\| #(\d+) \| ([0-9a-f]{40}) \| ([0-9a-f]{40}) \| (.+) \| ([^|]+) \|$"
)
SUBJECT_PATTERN = re.compile(r"^Merge pull request #(\d+) from (.+)$")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _first_parent_merges() -> list[tuple[str, str, str, str]]:
    merges: list[tuple[str, str, str, str]] = []
    output = _git("log", "--first-parent", "--format=%H%x1f%P%x1f%s", "origin/master")
    for line in output.splitlines():
        merge_sha, parents, subject = line.split("\x1f", maxsplit=2)
        subject_match = SUBJECT_PATTERN.fullmatch(subject)
        if subject_match is None:
            continue
        number, source_branch = subject_match.groups()
        if not 3 <= int(number) <= 25:
            continue
        parent_shas = parents.split()
        assert len(parent_shas) == 2
        merges.append((number, merge_sha, parent_shas[1], source_branch))
    return sorted(merges, key=lambda record: int(record[0]))


def test_historical_register_preserves_only_git_facts_and_evidence_gaps() -> None:
    text = REGISTER.read_text(encoding="utf-8")

    for number in range(3, 26):
        assert f"| #{number} |" in text
    assert text.count("evidence-unavailable") >= 23 * 4
    assert "reconstructed" not in text.lower()
    assert "inferred approval" not in text.lower()


def test_historical_register_rows_match_local_origin_master_merge_history() -> None:
    rows = [
        ROW_PATTERN.fullmatch(line)
        for line in REGISTER.read_text(encoding="utf-8").splitlines()
        if ROW_PATTERN.fullmatch(line)
    ]

    assert len(rows) == 23
    register_records = [
        (row.group(1), row.group(2), row.group(3), row.group(4)) for row in rows if row
    ]
    assert _first_parent_merges() == register_records


def test_historical_register_records_the_reconciliation_merge_boundary() -> None:
    text = REGISTER.read_text(encoding="utf-8")

    assert "PR #102" in text
    assert "b144452efb3f1d5b8d716015381d215b4bb84350" in text
    assert "PR #103" in text
    assert "206afd2488e8bdfde4c2a25e8ee2eee5dc07e25a" in text
    assert "459a5a4f6fa7aba65bc69973f04b98d31b300aff" in text
    assert "30ce9cc3892f674fa40fcc1d9df6de59a7501437" in text
