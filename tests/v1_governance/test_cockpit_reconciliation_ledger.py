from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPOSITORY_ROOT / "docs/governance/cockpit-reconciliation-ledger-v1.json"


def _ledger() -> dict[str, object]:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def _validate(repo_root: Path, ledger_path: Path) -> None:
    from tools.v1_governance.reconciliation import _validate_static_reconciliation_ledger

    # Child Git facts are covered by the real temporary-repository tests above.
    # The checked-in worktree deliberately keeps this submodule uninitialized.
    _validate_static_reconciliation_ledger(repo_root, ledger_path)


def _write_ledger(path: Path, ledger: dict[str, object]) -> None:
    path.write_text(json.dumps(ledger), encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit_leaf_repository(path: Path, name: str) -> str:
    path.mkdir()
    _git(path, "init", "-b", "master")
    _git(path, "config", "user.name", "V1 Tests")
    _git(path, "config", "user.email", "v1-tests@example.invalid")
    (path / "README.md").write_text(f"{name}\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", f"test: initialize {name}")
    return _git(path, "rev-parse", "HEAD")


def _arrange_child_git_facts(
    tmp_path: Path,
) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    openfang_pin = _commit_leaf_repository(tmp_path / "openfang", "openfang")
    voice_pin = _commit_leaf_repository(tmp_path / "voice", "voice")
    child = tmp_path / "vibemind-os"
    child.mkdir()
    _git(child, "init", "-b", "master")
    _git(child, "config", "user.name", "V1 Tests")
    _git(child, "config", "user.email", "v1-tests@example.invalid")
    (child / "README.md").write_text("child\n", encoding="utf-8")
    _git(child, "add", "README.md")
    _git(child, "commit", "-m", "test: initialize child")

    _git(child, "checkout", "-b", "child-pin")
    _git(child, "update-index", "--add", "--cacheinfo", f"160000,{openfang_pin},openfang")
    _git(child, "update-index", "--add", "--cacheinfo", f"160000,{voice_pin},voice")
    _git(child, "commit", "-m", "test: pin child gitlinks")
    child_parent = _git(child, "rev-parse", "HEAD")

    _git(child, "checkout", "master")
    (child / "master.txt").write_text("master\n", encoding="utf-8")
    _git(child, "add", "master.txt")
    _git(child, "commit", "-m", "test: advance master")
    _git(child, "merge", "--no-ff", "child-pin", "-m", "test: merge child pin")
    merge_sha = _git(child, "rev-parse", "HEAD")
    merge_parents = _git(child, "show", "-s", "--format=%P", merge_sha).split()
    assert merge_parents[1] == child_parent

    return (
        child,
        {"merge_sha": merge_sha, "parents": merge_parents},
        [
            {"path": "openfang", "target_commit": openfang_pin},
            {"path": "voice", "target_commit": voice_pin},
        ],
    )


def _arrange_openfang_git_facts(
    tmp_path: Path,
) -> tuple[Path, list[dict[str, object]]]:
    openfang = tmp_path / "openfang"
    openfang.mkdir()
    _git(openfang, "init", "-b", "master")
    _git(openfang, "config", "user.name", "V1 Tests")
    _git(openfang, "config", "user.email", "v1-tests@example.invalid")
    (openfang / "README.md").write_text("openfang\n", encoding="utf-8")
    _git(openfang, "add", "README.md")
    _git(openfang, "commit", "-m", "test: initialize openfang")

    records: list[dict[str, object]] = []
    for ordinal in (1, 2):
        branch = f"openfang-pin-{ordinal}"
        _git(openfang, "checkout", "-b", branch)
        (openfang / f"pin-{ordinal}.txt").write_text("pin\n", encoding="utf-8")
        _git(openfang, "add", f"pin-{ordinal}.txt")
        _git(openfang, "commit", "-m", f"test: pin {ordinal}")
        _git(openfang, "checkout", "master")
        (openfang / f"master-{ordinal}.txt").write_text("master\n", encoding="utf-8")
        _git(openfang, "add", f"master-{ordinal}.txt")
        _git(openfang, "commit", "-m", f"test: advance master {ordinal}")
        _git(openfang, "merge", "--no-ff", branch, "-m", f"test: merge pin {ordinal}")
        merge_sha = _git(openfang, "rev-parse", "HEAD")
        records.append(
            {
                "merge_sha": merge_sha,
                "parents": _git(openfang, "show", "-s", "--format=%P", merge_sha).split(),
            }
        )

    return openfang, records


def test_child_git_facts_reject_empty_directory_inside_outer_repository(
    tmp_path: Path,
) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    _git(outer, "init", "-b", "master")
    _git(outer, "config", "user.name", "V1 Tests")
    _git(outer, "config", "user.email", "v1-tests@example.invalid")
    (outer / "README.md").write_text("outer\n", encoding="utf-8")
    _git(outer, "add", "README.md")
    _git(outer, "commit", "-m", "test: initialize outer")
    empty_child_directory = outer / "vibemind-os"
    empty_child_directory.mkdir()

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_child_git_facts,
    )

    with pytest.raises(ReconciliationError, match="child Git repository is unavailable"):
        validate_child_git_facts(
            empty_child_directory,
            {"merge_sha": "0" * 40, "parents": ["0" * 40, "1" * 40]},
            [],
        )


def test_child_git_facts_accept_a_real_local_merge_and_tree(tmp_path: Path) -> None:
    child, merge_record, child_links = _arrange_child_git_facts(tmp_path)

    from tools.v1_governance.reconciliation import validate_child_git_facts

    validate_child_git_facts(child, merge_record, child_links)


def test_child_git_facts_reject_missing_child_gitdir(tmp_path: Path) -> None:
    _, merge_record, child_links = _arrange_child_git_facts(tmp_path)

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_child_git_facts,
    )

    with pytest.raises(ReconciliationError, match="child Git repository is unavailable"):
        validate_child_git_facts(tmp_path / "missing-child", merge_record, child_links)


@pytest.mark.parametrize("mutation", ("not-a-merge", "wrong-parent-pair"))
def test_child_git_facts_reject_invalid_merge_history(
    tmp_path: Path, mutation: str
) -> None:
    child, merge_record, child_links = _arrange_child_git_facts(tmp_path)
    if mutation == "not-a-merge":
        merge_record["merge_sha"] = merge_record["parents"][0]
    else:
        merge_record["parents"] = ["0" * 40, merge_record["parents"][1]]

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_child_git_facts,
    )

    with pytest.raises(ReconciliationError, match="historical child merge facts do not match"):
        validate_child_git_facts(child, merge_record, child_links)


@pytest.mark.parametrize("mutation", ("wrong-pin", "missing-path"))
def test_child_git_facts_reject_invalid_child_tree(tmp_path: Path, mutation: str) -> None:
    child, merge_record, child_links = _arrange_child_git_facts(tmp_path)
    if mutation == "wrong-pin":
        child_links[0]["target_commit"] = "0" * 40
    else:
        child_links[1]["path"] = "missing"

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_child_git_facts,
    )

    with pytest.raises(ReconciliationError, match="historical child gitlink facts do not match"):
        validate_child_git_facts(child, merge_record, child_links)


def test_child_tree_facts_validate_an_exact_non_authoritative_leaf_boundary(
    tmp_path: Path,
) -> None:
    child, merge_record, child_links = _arrange_child_git_facts(tmp_path)

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_child_tree_facts,
    )

    validate_child_tree_facts(child, merge_record["merge_sha"], child_links)

    child_links[0]["target_commit"] = "0" * 40
    with pytest.raises(
        ReconciliationError, match="historical child gitlink facts do not match"
    ):
        validate_child_tree_facts(child, merge_record["merge_sha"], child_links)


def test_openfang_git_facts_require_real_repository_root_and_exact_merges(
    tmp_path: Path,
) -> None:
    openfang, merge_records = _arrange_openfang_git_facts(tmp_path)
    wrong_repository = _commit_leaf_repository(tmp_path / "wrong-repository", "wrong")

    from tools.v1_governance.reconciliation import (
        ReconciliationError,
        validate_openfang_git_facts,
    )

    validate_openfang_git_facts(openfang, merge_records)

    with pytest.raises(
        ReconciliationError, match="historical OpenFang merge facts do not match"
    ):
        validate_openfang_git_facts(tmp_path / "wrong-repository", merge_records)
    with pytest.raises(ReconciliationError, match="OpenFang Git repository is unavailable"):
        validate_openfang_git_facts(tmp_path / "missing-openfang", merge_records)
    assert wrong_repository


def test_full_validator_checks_all_static_child_tree_edges(monkeypatch) -> None:
    from tools.v1_governance import reconciliation

    calls: list[tuple[str, tuple[str, ...]]] = []
    monkeypatch.setattr(
        reconciliation,
        "_validate_static_reconciliation_ledger",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        reconciliation,
        "_resolve_child_repository",
        lambda _repo_root, child_repo_root: child_repo_root,
    )
    monkeypatch.setattr(
        reconciliation,
        "_validate_child_merge_records",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        reconciliation,
        "_resolve_openfang_repository",
        lambda openfang_repo_root: openfang_repo_root,
    )
    monkeypatch.setattr(
        reconciliation,
        "_validate_openfang_merge_records",
        lambda *_args: None,
    )

    def record_tree_facts(_child_repo_root, commit, links) -> None:
        calls.append((commit, tuple(link["path"] for link in links)))

    monkeypatch.setattr(reconciliation, "validate_child_tree_facts", record_tree_facts)

    child_repo = Path("child-repository")
    reconciliation.validate_reconciliation_ledger(
        Path("outer-repository"),
        child_repo_root=child_repo,
        openfang_repo_root=Path("openfang-repository"),
    )

    assert calls == [
        ("26003b952d65359f116b14eba55695dc74d2b528", ("openfang", "voice")),
        ("7747d3b71576f2159a1384aea7eda131f92f7ca7", ("shared",)),
        (
            "805363f068ea854acf8c2b55d572792b388e9c2a",
            ("openfang", "shared", "voice"),
        ),
        (
            "d8093cf590b31d540adf393628108dcc9a3d45d3",
            ("openfang", "shared", "voice"),
        ),
        (
            "ef803b7d53871c52c00dfb17936bf42211c72525",
            ("openfang",),
        ),
        (
            "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
            ("openfang", "voice"),
        ),
        (
            "0ba96011719c61bcb84aab8d38baec9faf583de9",
            ("openfang", "voice"),
        ),
        (
            "a9d0de3f467b45604504642aa0fe577031b61d1e",
            ("openfang", "voice"),
        ),
        (
            "58969c4515e77dc73f06d839e1f9dfe770ed2305",
            ("openfang", "voice"),
        ),
        (
            "87596f0347aaa244353fbbf2dde79f05b29c5070",
            ("openfang", "voice"),
        ),
        (
            "89ba6176a40d190840dd36360a81dfdb3de3b97c",
            ("openfang", "voice"),
        ),
        (
            "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
            ("openfang", "voice"),
        ),
        (
            "9ee1cc42401185824a4f4c624c33a8bde1dc92b8",
            ("openfang", "voice"),
        ),
        (
            "731288b4e36ac172dfb902e22627c6f937760a3e",
            ("openfang", "voice"),
        ),
    ]


def test_committed_ledger_reconciles_exact_offline_git_facts() -> None:
    assert LEDGER_PATH.is_file()

    ledger = _ledger()
    _validate(REPOSITORY_ROOT, LEDGER_PATH)

    entries = ledger["entries"]
    assert isinstance(entries, list)
    assert entries[0] == {
        "domain": "outer-repository",
        "ordinal": 1,
        "kind": "historical-merge",
        "pull_request": 102,
        "merge_sha": "b144452efb3f1d5b8d716015381d215b4bb84350",
        "parents": [
            "206afd2488e8bdfde4c2a25e8ee2eee5dc07e25a",
            "53d94175245512f492b7aac1b19cd42efbced8b9",
        ],
        "evidence_class": "historical-local-git",
    }
    assert entries[1] == {
        "domain": "outer-repository",
        "ordinal": 2,
        "kind": "historical-merge",
        "pull_request": 103,
        "merge_sha": "206afd2488e8bdfde4c2a25e8ee2eee5dc07e25a",
        "parents": [
            "51ed88827a3ebc216868f4535cbaee769bdfcf00",
            "b8136d665913f137b1daaaae6dcc3ea12e67b042",
        ],
        "evidence_class": "historical-local-git",
    }
    assert entries[2] == {
        "domain": "outer-repository",
        "ordinal": 3,
        "kind": "historical-merge",
        "pull_request": 105,
        "merge_sha": "29df499bb9ac0a0efa7353e5a242f1497da0c4d8",
        "parents": [
            "5f32292aab0709c29305e79ac8c0eed0c8ab3119",
            "6651530bc5e353d592676562a886e8ac2dee669d",
        ],
        "evidence_class": "historical-local-git",
    }
    assert entries[3] == {
        "domain": "outer-repository",
        "ordinal": 4,
        "kind": "historical-merge",
        "pull_request": 106,
        "merge_sha": "62b50ce1336ce88fd162c79a66b8ede3b3b43144",
        "parents": [
            "29df499bb9ac0a0efa7353e5a242f1497da0c4d8",
            "c77a4a296b000869d85becaefb0623819c7ab733",
        ],
        "evidence_class": "historical-local-git",
    }
    assert entries[4] == {
        "domain": "outer-repository",
        "ordinal": 5,
        "kind": "historical-merge",
        "pull_request": 107,
        "merge_sha": "99d41a795ac7538fb32927664a301d318d62e725",
        "parents": [
            "62b50ce1336ce88fd162c79a66b8ede3b3b43144",
            "c1ac2ed04022f8e874f03ed13e550b591d43e852",
        ],
        "evidence_class": "historical-local-git",
    }
    child_pr115 = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge" and entry["pull_request"] == 115
    )
    assert child_pr115 == {
        "domain": "vibemind-os-repository",
        "ordinal": 1,
        "kind": "historical-child-merge",
        "pull_request": 115,
        "merge_sha": "26003b952d65359f116b14eba55695dc74d2b528",
        "parents": [
            "c7f311bd5c6a19a78dc64dfb2d6e8426776beff6",
            "f7e2684edacf89f27b46b98bce9fb015a39505b9",
        ],
        "evidence_class": "historical-local-git",
    }
    initial_chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "b144452efb3f1d5b8d716015381d215b4bb84350"
    )
    assert initial_chain == {
        "domain": "gitlink-chain",
        "ordinal": 1,
        "kind": "historical-gitlink-chain",
        "root_commit": "b144452efb3f1d5b8d716015381d215b4bb84350",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "b144452efb3f1d5b8d716015381d215b4bb84350",
                "path": "vibemind-os",
                "target_commit": "459a5a4f6fa7aba65bc69973f04b98d31b300aff",
            },
            {
                "repository": "vibemind-os",
                "commit": "459a5a4f6fa7aba65bc69973f04b98d31b300aff",
                "path": "voice",
                "target_commit": "30ce9cc3892f674fa40fcc1d9df6de59a7501437",
                "evidence_class": "historical-external-not-git-verified",
            },
        ],
    }
    post_pin_chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "99d41a795ac7538fb32927664a301d318d62e725"
    )
    assert post_pin_chain == {
        "domain": "gitlink-chain",
        "ordinal": 2,
        "kind": "historical-gitlink-chain",
        "root_commit": "99d41a795ac7538fb32927664a301d318d62e725",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "99d41a795ac7538fb32927664a301d318d62e725",
                "path": "vibemind-os",
                "target_commit": "26003b952d65359f116b14eba55695dc74d2b528",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "26003b952d65359f116b14eba55695dc74d2b528",
                "path": "openfang",
                "target_commit": "fac8e429f5adfa50ac59dce2360c481290148cad",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "26003b952d65359f116b14eba55695dc74d2b528",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_post_pr112_outer_merge_chain_is_complete_and_exact() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    outer_merges = [
        entry for entry in entries if entry["kind"] == "historical-merge"
    ]
    assert [
        entry for entry in outer_merges if entry["pull_request"] in {108, 109, 110, 111, 112}
    ] == [
        {
            "domain": "outer-repository",
            "ordinal": 6,
            "kind": "historical-merge",
            "pull_request": 108,
            "merge_sha": "1a78d9e42fc90b0463185d7af5442d75a6894a52",
            "parents": [
                "99d41a795ac7538fb32927664a301d318d62e725",
                "9050aa0a829d84a87c2c10cc5e50febd5c2d0b21",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 7,
            "kind": "historical-merge",
            "pull_request": 109,
            "merge_sha": "e061d177e3c4343543e0351871aee40b3fff77ef",
            "parents": [
                "1a78d9e42fc90b0463185d7af5442d75a6894a52",
                "7e3e0f027f0d1b3c304821d1e8374367f8923026",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 8,
            "kind": "historical-merge",
            "pull_request": 110,
            "merge_sha": "100e9651a963917f15ba41f73fce8421545edf64",
            "parents": [
                "e061d177e3c4343543e0351871aee40b3fff77ef",
                "e126ff46bd3c666c1582f627ce1cc6a967830e69",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 9,
            "kind": "historical-merge",
            "pull_request": 111,
            "merge_sha": "f0001e40f306745f60818a5bbd3065377dacd443",
            "parents": [
                "100e9651a963917f15ba41f73fce8421545edf64",
                "96c983e7c4de6e492add76030c746c2d321c54e6",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 10,
            "kind": "historical-merge",
            "pull_request": 112,
            "merge_sha": "b790600ad7804c9048c557a69d84ef0a99a0b4d2",
            "parents": [
                "f0001e40f306745f60818a5bbd3065377dacd443",
                "3c1960112b62c362ca8aee0310f5a90653178a09",
            ],
            "evidence_class": "historical-local-git",
        },
    ]


def test_post_authority_pin_merge_histories_are_complete_and_exact() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    outer_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-merge"
        and 113 <= entry["pull_request"] <= 124
    ]
    assert outer_merges == [
        {
            "domain": "outer-repository",
            "ordinal": 11,
            "kind": "historical-merge",
            "pull_request": 113,
            "merge_sha": "678dff306909f6b5282c1d81c7b53df1fce3875d",
            "parents": [
                "b790600ad7804c9048c557a69d84ef0a99a0b4d2",
                "945635c002061e1916470eea3168cea7f2352bd3",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 12,
            "kind": "historical-merge",
            "pull_request": 114,
            "merge_sha": "cd6f092bcc6558774f9592651d58dbfa64aee019",
            "parents": [
                "678dff306909f6b5282c1d81c7b53df1fce3875d",
                "6f001f2da2a02f108b9d85e6494a41246739ce33",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 13,
            "kind": "historical-merge",
            "pull_request": 115,
            "merge_sha": "81200725aa2ac1f07b1fd15048654b3bef2f53cc",
            "parents": [
                "cd6f092bcc6558774f9592651d58dbfa64aee019",
                "b757cae033a29772f826764af255dd13e7fff510",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 14,
            "kind": "historical-merge",
            "pull_request": 116,
            "merge_sha": "736da5bc4b6740320c6a13484d5776a0c072aaf4",
            "parents": [
                "81200725aa2ac1f07b1fd15048654b3bef2f53cc",
                "b12ed1958e7276f56e78409afe25458574195004",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 15,
            "kind": "historical-merge",
            "pull_request": 117,
            "merge_sha": "525316ad5da1972a5a922db51ad6850aa94e4a6f",
            "parents": [
                "736da5bc4b6740320c6a13484d5776a0c072aaf4",
                "6e1f3205db8d24a2ce67e9be8e9a59d8d5515a72",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 16,
            "kind": "historical-merge",
            "pull_request": 118,
            "merge_sha": "beff1541ecd7183ec980deba82b0cbbf25965f2b",
            "parents": [
                "525316ad5da1972a5a922db51ad6850aa94e4a6f",
                "789b3b721ca07e9f620267a4a4ae5d03b5f10ec1",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 17,
            "kind": "historical-merge",
            "pull_request": 119,
            "merge_sha": "6c243e9ad8a37a06021727f92460d7dea251a6be",
            "parents": [
                "beff1541ecd7183ec980deba82b0cbbf25965f2b",
                "75eba9ab3b1cfae66e41e765653433559289821a",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 18,
            "kind": "historical-merge",
            "pull_request": 120,
            "merge_sha": "d317fb0927a524eae2cef56a8a237abe8a58030d",
            "parents": [
                "6c243e9ad8a37a06021727f92460d7dea251a6be",
                "2c84c214723db0c0fb35819651a1bad62584023a",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 19,
            "kind": "historical-merge",
            "pull_request": 121,
            "merge_sha": "490fafd207caf4c9b9d7599b65364a5244e1d7db",
            "parents": [
                "d317fb0927a524eae2cef56a8a237abe8a58030d",
                "1ff92cc7310e04dc0b8312bec3bc00a4ded3d381",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 20,
            "kind": "historical-merge",
            "pull_request": 122,
            "merge_sha": "b0104d54e4f7ad4d9a31433d3413089e15b11158",
            "parents": [
                "490fafd207caf4c9b9d7599b65364a5244e1d7db",
                "46fb82d029ba0c8440a8f2e2d69e74aff1dd1af2",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 21,
            "kind": "historical-merge",
            "pull_request": 123,
            "merge_sha": "751ba6ea1d1113c2944b2358980226988c96a7f2",
            "parents": [
                "b0104d54e4f7ad4d9a31433d3413089e15b11158",
                "2415f0106bc93b7da3d83794c90ab5d0bd5fda61",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 22,
            "kind": "historical-merge",
            "pull_request": 124,
            "merge_sha": "f0f1c478115ecd5373aa43637985ae4512687d9c",
            "parents": [
                "751ba6ea1d1113c2944b2358980226988c96a7f2",
                "019be6628515b06fe8a9168f874cbb42a41c88f8",
            ],
            "evidence_class": "historical-local-git",
        },
    ]

    child_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge"
        and 120 <= entry["pull_request"] <= 126
    ]
    assert child_merges == [
        {
            "domain": "vibemind-os-repository",
            "ordinal": 2,
            "kind": "historical-child-merge",
            "pull_request": 120,
            "merge_sha": "a64ba5236df2a0cd0e854cde2fa2634387928aeb",
            "parents": [
                "7747d3b71576f2159a1384aea7eda131f92f7ca7",
                "805b9b454bc9222e4ddf2fda8c4fb409b6cba3cc",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 3,
            "kind": "historical-child-merge",
            "pull_request": 121,
            "merge_sha": "3b8bd81121b26fecb4b0b555086d0fe1b04c7d89",
            "parents": [
                "a64ba5236df2a0cd0e854cde2fa2634387928aeb",
                "2bcf0e10e8cbccc5284a828503892bc7d79d2ed4",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 4,
            "kind": "historical-child-merge",
            "pull_request": 122,
            "merge_sha": "805363f068ea854acf8c2b55d572792b388e9c2a",
            "parents": [
                "3b8bd81121b26fecb4b0b555086d0fe1b04c7d89",
                "cbee0750c3f81ba0ca5059d61f8a42a105700ce0",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 5,
            "kind": "historical-child-merge",
            "pull_request": 123,
            "merge_sha": "d8093cf590b31d540adf393628108dcc9a3d45d3",
            "parents": [
                "805363f068ea854acf8c2b55d572792b388e9c2a",
                "08a6de4f63c65dff4e1652b85217edadf41f7704",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 6,
            "kind": "historical-child-merge",
            "pull_request": 124,
            "merge_sha": "d9d44e09d26107ff5f44c1f8fc95999e59cf2072",
            "parents": [
                "d8093cf590b31d540adf393628108dcc9a3d45d3",
                "bd52aedad0c57e9bdbd7e23e50c9aa404fb8aab2",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 7,
            "kind": "historical-child-merge",
            "pull_request": 125,
            "merge_sha": "ef803b7d53871c52c00dfb17936bf42211c72525",
            "parents": [
                "d9d44e09d26107ff5f44c1f8fc95999e59cf2072",
                "05b897117c5234357115fd25922ade2eaa581076",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 8,
            "kind": "historical-child-merge",
            "pull_request": 126,
            "merge_sha": "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
            "parents": [
                "ef803b7d53871c52c00dfb17936bf42211c72525",
                "fcb6b09b16e952317fd9f92bdc6223c3f1d48d40",
            ],
            "evidence_class": "historical-local-git",
        },
    ]

    openfang_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-openfang-merge"
        and entry["pull_request"] <= 9
    ]
    assert openfang_merges == [
        {
            "domain": "openfang-repository",
            "ordinal": 1,
            "kind": "historical-openfang-merge",
            "pull_request": 7,
            "merge_sha": "828a2138cb0fb7548918f0b5f53fe30cc5518838",
            "parents": [
                "fac8e429f5adfa50ac59dce2360c481290148cad",
                "b827149a2fcc8ca8f9b58f54b093245d71fd4331",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "openfang-repository",
            "ordinal": 2,
            "kind": "historical-openfang-merge",
            "pull_request": 8,
            "merge_sha": "cd3cef07f6c126b67a22f26975546141d891f6cf",
            "parents": [
                "828a2138cb0fb7548918f0b5f53fe30cc5518838",
                "30f459ce694327b4e3adaa53b564bdcb5af11b2b",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "openfang-repository",
            "ordinal": 3,
            "kind": "historical-openfang-merge",
            "pull_request": 9,
            "merge_sha": "f2b0fc2d8be90c6877ee96196456fe516815e68c",
            "parents": [
                "cd3cef07f6c126b67a22f26975546141d891f6cf",
                "1cd2abbc73fd313a9332d85b5efc9ae605aaac8a",
            ],
            "evidence_class": "historical-local-git",
        },
    ]


def test_recent_outer_and_child_merges_form_complete_first_parent_sequences() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    outer_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-merge" and entry["pull_request"] <= 124
    ]
    outer_anchor = next(
        index
        for index, entry in enumerate(outer_merges)
        if entry["pull_request"] == 118
    )
    recent_outer = outer_merges[outer_anchor + 1 :]
    actual_outer = _git(
        REPOSITORY_ROOT,
        "rev-list",
        "--first-parent",
        "--reverse",
        "beff1541ecd7183ec980deba82b0cbbf25965f2b..f0f1c478115ecd5373aa43637985ae4512687d9c",
    ).splitlines()
    assert [entry["merge_sha"] for entry in recent_outer] == actual_outer

    child_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge" and entry["pull_request"] <= 126
    ]
    child_anchor = next(
        index
        for index, entry in enumerate(child_merges)
        if entry["pull_request"] == 123
    )
    expected_first_parent = child_merges[child_anchor]["merge_sha"]
    recent_child = child_merges[child_anchor + 1 :]
    for entry in recent_child:
        assert entry["parents"][0] == expected_first_parent
        expected_first_parent = entry["merge_sha"]
    assert expected_first_parent == "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b"


def test_fallback_no_mcp_child_pin_chain_contains_required_consumer_pins() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "5ccca83950069eaacff76868deadf5099ec357d3"
    )
    outer_link = next(
        link for link in chain["links"] if link["repository"] == "Vibemind_V1"
    )
    child_commit = "a9d0de3f467b45604504642aa0fe577031b61d1e"
    assert outer_link["target_commit"] == child_commit

    child_links = {
        link["path"]: link
        for link in chain["links"]
        if link["repository"] == "vibemind-os" and link["commit"] == child_commit
    }
    required_links = {
        "openfang": {
            "repository": "vibemind-os",
            "commit": child_commit,
            "path": "openfang",
            "target_commit": "e004f8a1534250ac26bdeb413440f4ab9740ae5d",
            "evidence_class": "static-local-git-tree",
            "target_object_evidence": "not-locally-materialized",
        },
        "voice": {
            "repository": "vibemind-os",
            "commit": child_commit,
            "path": "voice",
            "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
            "evidence_class": "static-local-git-tree",
            "target_object_evidence": "not-locally-materialized",
        },
    }
    assert required_links.keys() <= child_links.keys()
    for path, expected_link in required_links.items():
        assert child_links[path] == expected_link


def test_current_claude_chain_merges_and_static_pin_records_are_exact() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    requested_pull_requests = {
        "historical-openfang-merge": {12, 13},
        "historical-child-merge": {129, 130, 131, 132, 133},
        "historical-merge": {134, 135},
    }
    observed_records = [
        (
            entry["domain"],
            entry["ordinal"],
            entry["kind"],
            entry["pull_request"],
            entry["merge_sha"],
            tuple(entry["parents"]),
            entry["evidence_class"],
        )
        for entry in entries
        if entry["kind"] in requested_pull_requests
        and entry["pull_request"] in requested_pull_requests[entry["kind"]]
    ]
    assert observed_records == [
        (
            "openfang-repository",
            6,
            "historical-openfang-merge",
            12,
            "10a998a1cb9aaa42024bf780583074ca3d97e032",
            (
                "e004f8a1534250ac26bdeb413440f4ab9740ae5d",
                "93550361b4e67f5af581dda531b6cd5a58fff904",
            ),
            "historical-local-git",
        ),
        (
            "vibemind-os-repository",
            11,
            "historical-child-merge",
            129,
            "58969c4515e77dc73f06d839e1f9dfe770ed2305",
            (
                "a9d0de3f467b45604504642aa0fe577031b61d1e",
                "cb48ad4691f8ad438e86c0113b1883fcc440b5d5",
            ),
            "historical-local-git",
        ),
        (
            "outer-repository",
            25,
            "historical-merge",
            134,
            "b3db11ea9da8fd48892fcf05534ca6d1c00a4437",
            (
                "eea700e67d49cb5b749e0c2a2c57b742f085935b",
                "8e587a7ee45555f6e93db41ad522b01d5aabf983",
            ),
            "historical-local-git",
        ),
        (
            "vibemind-os-repository",
            12,
            "historical-child-merge",
            130,
            "9d389b1f19c3f6be2bceb77cfea99810fa4781a1",
            (
                "58969c4515e77dc73f06d839e1f9dfe770ed2305",
                "e5d1d2fc277124c7861f233bffb49973771e1396",
            ),
            "historical-local-git",
        ),
        (
            "vibemind-os-repository",
            13,
            "historical-child-merge",
            131,
            "802a86682a62adf10124b3fc7a4f2cfd8312219b",
            (
                "9d389b1f19c3f6be2bceb77cfea99810fa4781a1",
                "b043198782d58e24024b591612e00175756f9452",
            ),
            "historical-local-git",
        ),
        (
            "vibemind-os-repository",
            14,
            "historical-child-merge",
            132,
            "b0fac85c579b618c7438e6480f2d3d8f3b2fa868",
            (
                "802a86682a62adf10124b3fc7a4f2cfd8312219b",
                "c53ede820e8ecb8a2b72380d8aa5d0dd36a49e29",
            ),
            "historical-local-git",
        ),
        (
            "openfang-repository",
            7,
            "historical-openfang-merge",
            13,
            "36dc5260e3408b64ad2eb26958549d1faedf78e1",
            (
                "10a998a1cb9aaa42024bf780583074ca3d97e032",
                "7b5e025ad6b71dfddd647053c50f74757bfaa19e",
            ),
            "historical-local-git",
        ),
        (
            "vibemind-os-repository",
            15,
            "historical-child-merge",
            133,
            "87596f0347aaa244353fbbf2dde79f05b29c5070",
            (
                "b0fac85c579b618c7438e6480f2d3d8f3b2fa868",
                "292813ef8dc5a52996c625761297296fbcfd656b",
            ),
            "historical-local-git",
        ),
        (
            "outer-repository",
            26,
            "historical-merge",
            135,
            "2bdacf6dcb1501a75b17d6cbb33ccc72c92abaa0",
            (
                "b3db11ea9da8fd48892fcf05534ca6d1c00a4437",
                "64f574c8dec40f22d8666cf4b892093829e1f88f",
            ),
            "historical-local-git",
        ),
    ]

    chains = [
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["ordinal"] in {10, 11}
    ]
    assert chains == [
        {
            "domain": "gitlink-chain",
            "ordinal": 10,
            "kind": "historical-gitlink-chain",
            "root_commit": "b3db11ea9da8fd48892fcf05534ca6d1c00a4437",
            "evidence_class": "historical-local-git",
            "links": [
                {
                    "repository": "Vibemind_V1",
                    "commit": "b3db11ea9da8fd48892fcf05534ca6d1c00a4437",
                    "path": "vibemind-os",
                    "target_commit": "58969c4515e77dc73f06d839e1f9dfe770ed2305",
                    "evidence_class": "static-local-git-tree",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "58969c4515e77dc73f06d839e1f9dfe770ed2305",
                    "path": "openfang",
                    "target_commit": "10a998a1cb9aaa42024bf780583074ca3d97e032",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "58969c4515e77dc73f06d839e1f9dfe770ed2305",
                    "path": "voice",
                    "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
            ],
        },
        {
            "domain": "gitlink-chain",
            "ordinal": 11,
            "kind": "historical-gitlink-chain",
            "root_commit": "2bdacf6dcb1501a75b17d6cbb33ccc72c92abaa0",
            "evidence_class": "historical-local-git",
            "links": [
                {
                    "repository": "Vibemind_V1",
                    "commit": "2bdacf6dcb1501a75b17d6cbb33ccc72c92abaa0",
                    "path": "vibemind-os",
                    "target_commit": "87596f0347aaa244353fbbf2dde79f05b29c5070",
                    "evidence_class": "static-local-git-tree",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "87596f0347aaa244353fbbf2dde79f05b29c5070",
                    "path": "openfang",
                    "target_commit": "36dc5260e3408b64ad2eb26958549d1faedf78e1",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "87596f0347aaa244353fbbf2dde79f05b29c5070",
                    "path": "voice",
                    "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
            ],
        },
    ]


def test_brain_coder_chain_records_remain_an_append_only_prefix() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)
    assert len(entries) >= 66
    assert entries[60:66] == [
        {
            "domain": "openfang-repository",
            "ordinal": 8,
            "kind": "historical-openfang-merge",
            "pull_request": 14,
            "merge_sha": "4bb89b22c287f84f6bb4f5ac6d40612531a33651",
            "parents": [
                "36dc5260e3408b64ad2eb26958549d1faedf78e1",
                "8430d870895bb8e230ae0f1d6c6e746f73ec89c8",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 16,
            "kind": "historical-child-merge",
            "pull_request": 134,
            "merge_sha": "89ba6176a40d190840dd36360a81dfdb3de3b97c",
            "parents": [
                "87596f0347aaa244353fbbf2dde79f05b29c5070",
                "bc012400bc04c710b2271d8bbb5a9718cd789df9",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 27,
            "kind": "historical-merge",
            "pull_request": 136,
            "merge_sha": "c73a5a8e2f8ef58b781f00bdc6d5710037d2d5a8",
            "parents": [
                "2bdacf6dcb1501a75b17d6cbb33ccc72c92abaa0",
                "55f965f66aa68cccecc69d33e69af8bb7784fc9f",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 28,
            "kind": "historical-merge",
            "pull_request": 137,
            "merge_sha": "299fd90053532d0574247d0e7998b82ca57c6cbd",
            "parents": [
                "c73a5a8e2f8ef58b781f00bdc6d5710037d2d5a8",
                "07ba2fa582694269f8f62b0ba696f18cdceeadd9",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 29,
            "kind": "historical-merge",
            "pull_request": 138,
            "merge_sha": "312a5bc68604d84c5f43c42cb4b2c2ad7b7c70e0",
            "parents": [
                "299fd90053532d0574247d0e7998b82ca57c6cbd",
                "29b30a5816b79dfad0a6111dfc991cea970e77f7",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "gitlink-chain",
            "ordinal": 12,
            "kind": "historical-gitlink-chain",
            "root_commit": "312a5bc68604d84c5f43c42cb4b2c2ad7b7c70e0",
            "evidence_class": "historical-local-git",
            "links": [
                {
                    "repository": "Vibemind_V1",
                    "commit": "312a5bc68604d84c5f43c42cb4b2c2ad7b7c70e0",
                    "path": "vibemind-os",
                    "target_commit": "89ba6176a40d190840dd36360a81dfdb3de3b97c",
                    "evidence_class": "static-local-git-tree",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "89ba6176a40d190840dd36360a81dfdb3de3b97c",
                    "path": "openfang",
                    "target_commit": "4bb89b22c287f84f6bb4f5ac6d40612531a33651",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "89ba6176a40d190840dd36360a81dfdb3de3b97c",
                    "path": "voice",
                    "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
            ],
        },
    ]


def test_runtime_admission_chain_records_are_exact_append_only_tail() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)
    assert entries[66:73] == [
        {
            "domain": "openfang-repository",
            "ordinal": 9,
            "kind": "historical-openfang-merge",
            "pull_request": 15,
            "merge_sha": "33be359cb30574b5b62c14686f9459ec11fcc184",
            "parents": [
                "4bb89b22c287f84f6bb4f5ac6d40612531a33651",
                "27afdc6b103f78406c94b4becd609c1903d13973",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 17,
            "kind": "historical-child-merge",
            "pull_request": 135,
            "merge_sha": "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
            "parents": [
                "89ba6176a40d190840dd36360a81dfdb3de3b97c",
                "5580051d952e70bdf240cee1a2beec4911decdb5",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 30,
            "kind": "historical-merge",
            "pull_request": 139,
            "merge_sha": "17427c7a9e433acb768326cd612880c5141ff24d",
            "parents": [
                "312a5bc68604d84c5f43c42cb4b2c2ad7b7c70e0",
                "906364e800eb89362008927c44bf35e39ef116b8",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 31,
            "kind": "historical-merge",
            "pull_request": 140,
            "merge_sha": "bdcde8746d53f2ecb1a22867e95df88f029c9f6a",
            "parents": [
                "17427c7a9e433acb768326cd612880c5141ff24d",
                "bc2ca911c10dd7c867220bf926ed16c86cd94d6d",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 32,
            "kind": "historical-merge",
            "pull_request": 142,
            "merge_sha": "375fcaf89f262f811133aece714af74739469d85",
            "parents": [
                "20cc8bfacb9af79fe47f9895f978a5b31b82590b",
                "ba52808b4d67a3dd0dbac24bf374bfcc6a3238a3",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 33,
            "kind": "historical-merge",
            "pull_request": 141,
            "merge_sha": "be906aa099c5e09656dd0e342dedc12397f646b7",
            "parents": [
                "375fcaf89f262f811133aece714af74739469d85",
                "b75736bc0ff05c2b1668be7bda9001ebb808dbe1",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "gitlink-chain",
            "ordinal": 13,
            "kind": "historical-gitlink-chain",
            "root_commit": "be906aa099c5e09656dd0e342dedc12397f646b7",
            "evidence_class": "historical-local-git",
            "links": [
                {
                    "repository": "Vibemind_V1",
                    "commit": "be906aa099c5e09656dd0e342dedc12397f646b7",
                    "path": "vibemind-os",
                    "target_commit": "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
                    "evidence_class": "static-local-git-tree",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
                    "path": "openfang",
                    "target_commit": "33be359cb30574b5b62c14686f9459ec11fcc184",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
                    "path": "voice",
                    "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
            ],
        },
    ]


def test_deterministic_rowboat_gateway_records_are_exact_append_only_tail() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)
    assert len(entries) >= 79
    assert [
        entry["pull_request"]
        for entry in entries[:79]
        if entry["kind"] == "historical-openfang-merge"
    ] == [7, 8, 9, 10, 11, 12, 13, 14, 15]
    assert entries[73:79] == [
        {
            "domain": "outer-repository",
            "ordinal": 34,
            "kind": "historical-merge",
            "pull_request": 145,
            "merge_sha": "78f2f92943b9630e84359c23adfc51cab5e82235",
            "parents": [
                "d5cd65243d180310fcdd0b135dfb24760d8fa3ff",
                "41e4aa253103beaf5826c852d7bf4f23f12035d8",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 35,
            "kind": "historical-merge",
            "pull_request": 146,
            "merge_sha": "b15e555c61f5e81e06606958916f897d9f3b5f33",
            "parents": [
                "78f2f92943b9630e84359c23adfc51cab5e82235",
                "245732abe7bf61936c08b91ea8ce7733d3851963",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "vibemind-os-repository",
            "ordinal": 18,
            "kind": "historical-child-merge",
            "pull_request": 136,
            "merge_sha": "9ee1cc42401185824a4f4c624c33a8bde1dc92b8",
            "parents": [
                "407d515280b97ddfb7cedfe820cc1d938a50f3c6",
                "6dbd7160d59cfe8d460bcf2ac4b80880b0008c75",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 36,
            "kind": "historical-merge",
            "pull_request": 147,
            "merge_sha": "f0650df67aa09c74c9e6bcf2be2be0c330610b7e",
            "parents": [
                "b15e555c61f5e81e06606958916f897d9f3b5f33",
                "b7eb1f482e48155c48830633a56036fece9772df",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 37,
            "kind": "historical-merge",
            "pull_request": 148,
            "merge_sha": "70faaf4755579a481fcb6f6ff1c31c613c9b6260",
            "parents": [
                "f0650df67aa09c74c9e6bcf2be2be0c330610b7e",
                "9fc51f5a4eaa97869a67261c97ed9a0e2baa7c12",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "gitlink-chain",
            "ordinal": 14,
            "kind": "historical-gitlink-chain",
            "root_commit": "70faaf4755579a481fcb6f6ff1c31c613c9b6260",
            "evidence_class": "historical-local-git",
            "links": [
                {
                    "repository": "Vibemind_V1",
                    "commit": "70faaf4755579a481fcb6f6ff1c31c613c9b6260",
                    "path": "vibemind-os",
                    "target_commit": "9ee1cc42401185824a4f4c624c33a8bde1dc92b8",
                    "evidence_class": "static-local-git-tree",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "9ee1cc42401185824a4f4c624c33a8bde1dc92b8",
                    "path": "openfang",
                    "target_commit": "33be359cb30574b5b62c14686f9459ec11fcc184",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "locally-materialized",
                },
                {
                    "repository": "vibemind-os",
                    "commit": "9ee1cc42401185824a4f4c624c33a8bde1dc92b8",
                    "path": "voice",
                    "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                    "evidence_class": "static-local-git-tree",
                    "target_object_evidence": "not-locally-materialized",
                },
            ],
        },
    ]


@pytest.mark.parametrize("tampered_path", ("vibemind-os", "openfang", "voice"))
def test_deterministic_rowboat_gateway_chain_rejects_tampered_pins(
    tmp_path: Path, tampered_path: str
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)
    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "70faaf4755579a481fcb6f6ff1c31c613c9b6260"
    )
    next(link for link in chain["links"] if link["path"] == tampered_path)[
        "target_commit"
    ] = "0" * 40
    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match="historical gitlink facts do not match"):
        _validate(REPOSITORY_ROOT, mutated_path)


@pytest.mark.parametrize("tampered_path", ("openfang", "vibemind-os"))
def test_runtime_admission_chain_rejects_tampered_child_and_openfang_pins(
    tmp_path: Path, tampered_path: str
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)
    runtime_chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "be906aa099c5e09656dd0e342dedc12397f646b7"
    )
    next(link for link in runtime_chain["links"] if link["path"] == tampered_path)[
        "target_commit"
    ] = "0" * 40
    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match="historical gitlink facts do not match"):
        _validate(REPOSITORY_ROOT, mutated_path)


def test_runtime_admission_ledger_rejects_reordered_preexisting_prefix(
    tmp_path: Path,
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)
    entries[60], entries[61] = entries[61], entries[60]
    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match="ledger entry order does not match"):
        _validate(REPOSITORY_ROOT, mutated_path)


@pytest.mark.parametrize("tampered_path", ("vibemind-os", "openfang"))
def test_latest_brain_coder_chain_rejects_tampered_pins(
    tmp_path: Path, tampered_path: str
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)
    latest_chain = next(
        (
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "312a5bc68604d84c5f43c42cb4b2c2ad7b7c70e0"
        ),
        None,
    )
    assert latest_chain is not None
    next(
        link for link in latest_chain["links"] if link["path"] == tampered_path
    )["target_commit"] = "0" * 40
    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match="historical gitlink facts do not match"):
        _validate(REPOSITORY_ROOT, mutated_path)


def test_brain_consumer_post_pin_records_extend_outer_continuity_and_static_chain() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    outer_merges = [
        entry
        for entry in entries
        if entry["kind"] == "historical-merge" and entry["pull_request"] <= 124
    ]
    recent_outer = [entry for entry in outer_merges if entry["ordinal"] >= 19]
    assert recent_outer == [
        {
            "domain": "outer-repository",
            "ordinal": 19,
            "kind": "historical-merge",
            "pull_request": 121,
            "merge_sha": "490fafd207caf4c9b9d7599b65364a5244e1d7db",
            "parents": [
                "d317fb0927a524eae2cef56a8a237abe8a58030d",
                "1ff92cc7310e04dc0b8312bec3bc00a4ded3d381",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 20,
            "kind": "historical-merge",
            "pull_request": 122,
            "merge_sha": "b0104d54e4f7ad4d9a31433d3413089e15b11158",
            "parents": [
                "490fafd207caf4c9b9d7599b65364a5244e1d7db",
                "46fb82d029ba0c8440a8f2e2d69e74aff1dd1af2",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 21,
            "kind": "historical-merge",
            "pull_request": 123,
            "merge_sha": "751ba6ea1d1113c2944b2358980226988c96a7f2",
            "parents": [
                "b0104d54e4f7ad4d9a31433d3413089e15b11158",
                "2415f0106bc93b7da3d83794c90ab5d0bd5fda61",
            ],
            "evidence_class": "historical-local-git",
        },
        {
            "domain": "outer-repository",
            "ordinal": 22,
            "kind": "historical-merge",
            "pull_request": 124,
            "merge_sha": "f0f1c478115ecd5373aa43637985ae4512687d9c",
            "parents": [
                "751ba6ea1d1113c2944b2358980226988c96a7f2",
                "019be6628515b06fe8a9168f874cbb42a41c88f8",
            ],
            "evidence_class": "historical-local-git",
        },
    ]
    assert [entry["merge_sha"] for entry in recent_outer[1:]] == _git(
        REPOSITORY_ROOT,
        "rev-list",
        "--first-parent",
        "--reverse",
        "490fafd207caf4c9b9d7599b65364a5244e1d7db..f0f1c478115ecd5373aa43637985ae4512687d9c",
    ).splitlines()

    child_merge = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge" and entry["ordinal"] == 8
    )
    assert child_merge == {
        "domain": "vibemind-os-repository",
        "ordinal": 8,
        "kind": "historical-child-merge",
        "pull_request": 126,
        "merge_sha": "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
        "parents": [
            "ef803b7d53871c52c00dfb17936bf42211c72525",
            "fcb6b09b16e952317fd9f92bdc6223c3f1d48d40",
        ],
        "evidence_class": "historical-local-git",
    }

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain" and entry["ordinal"] == 7
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 7,
        "kind": "historical-gitlink-chain",
        "root_commit": "f0f1c478115ecd5373aa43637985ae4512687d9c",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "f0f1c478115ecd5373aa43637985ae4512687d9c",
                "path": "vibemind-os",
                "target_commit": "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
                "path": "openfang",
                "target_commit": "f2b0fc2d8be90c6877ee96196456fe516815e68c",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_legacy_mcp_scope_post_pin_chain_is_exact_and_static_only() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-openfang-merge" and entry["ordinal"] == 4
    ) == {
        "domain": "openfang-repository",
        "ordinal": 4,
        "kind": "historical-openfang-merge",
        "pull_request": 10,
        "merge_sha": "f991dcf8d3b88a545b6a75a958433ed30fd9f9c8",
        "parents": [
            "f2b0fc2d8be90c6877ee96196456fe516815e68c",
            "7a918f07847a70dc9cbf203c790997efcbf07513",
        ],
        "evidence_class": "historical-local-git",
    }
    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge" and entry["ordinal"] == 9
    ) == {
        "domain": "vibemind-os-repository",
        "ordinal": 9,
        "kind": "historical-child-merge",
        "pull_request": 127,
        "merge_sha": "0ba96011719c61bcb84aab8d38baec9faf583de9",
        "parents": [
            "0e46f7c2301ce73fe1e658f91a43c8f0c5f6627b",
            "ca9cc3e1330ed6c35753934404c05600e46182c8",
        ],
        "evidence_class": "historical-local-git",
    }
    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-merge" and entry["ordinal"] == 23
    ) == {
        "domain": "outer-repository",
        "ordinal": 23,
        "kind": "historical-merge",
        "pull_request": 128,
        "merge_sha": "790ff4262be19be85254e6dd8479947822612123",
        "parents": [
            "4add481e59678f4d12f94ac3caad904aeffb7b85",
            "0a4a19d135646c740062f1e8ea82d391595df693",
        ],
        "evidence_class": "historical-local-git",
    }

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain" and entry["ordinal"] == 8
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 8,
        "kind": "historical-gitlink-chain",
        "root_commit": "790ff4262be19be85254e6dd8479947822612123",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "790ff4262be19be85254e6dd8479947822612123",
                "path": "vibemind-os",
                "target_commit": "0ba96011719c61bcb84aab8d38baec9faf583de9",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "0ba96011719c61bcb84aab8d38baec9faf583de9",
                "path": "openfang",
                "target_commit": "f991dcf8d3b88a545b6a75a958433ed30fd9f9c8",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "0ba96011719c61bcb84aab8d38baec9faf583de9",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_fallback_no_mcp_post_pin_chain_is_exact_and_static_only() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-openfang-merge" and entry["ordinal"] == 5
    ) == {
        "domain": "openfang-repository",
        "ordinal": 5,
        "kind": "historical-openfang-merge",
        "pull_request": 11,
        "merge_sha": "e004f8a1534250ac26bdeb413440f4ab9740ae5d",
        "parents": [
            "f991dcf8d3b88a545b6a75a958433ed30fd9f9c8",
            "82bcdbdebe1b1f41737d67d5fc12b72ce4729ad1",
        ],
        "evidence_class": "historical-local-git",
    }
    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-child-merge" and entry["ordinal"] == 10
    ) == {
        "domain": "vibemind-os-repository",
        "ordinal": 10,
        "kind": "historical-child-merge",
        "pull_request": 128,
        "merge_sha": "a9d0de3f467b45604504642aa0fe577031b61d1e",
        "parents": [
            "0ba96011719c61bcb84aab8d38baec9faf583de9",
            "18048071801275f8869e48d41dd02af98c4af88a",
        ],
        "evidence_class": "historical-local-git",
    }
    assert next(
        entry
        for entry in entries
        if entry["kind"] == "historical-merge" and entry["ordinal"] == 24
    ) == {
        "domain": "outer-repository",
        "ordinal": 24,
        "kind": "historical-merge",
        "pull_request": 131,
        "merge_sha": "5ccca83950069eaacff76868deadf5099ec357d3",
        "parents": [
            "fb1f05e270b27055c720ce0fc21b8b49a95a1f01",
            "f4d5fad24030462dea6e381c32a512feeabb74b3",
        ],
        "evidence_class": "historical-local-git",
    }

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain" and entry["ordinal"] == 9
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 9,
        "kind": "historical-gitlink-chain",
        "root_commit": "5ccca83950069eaacff76868deadf5099ec357d3",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "5ccca83950069eaacff76868deadf5099ec357d3",
                "path": "vibemind-os",
                "target_commit": "a9d0de3f467b45604504642aa0fe577031b61d1e",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "a9d0de3f467b45604504642aa0fe577031b61d1e",
                "path": "openfang",
                "target_commit": "e004f8a1534250ac26bdeb413440f4ab9740ae5d",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "a9d0de3f467b45604504642aa0fe577031b61d1e",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_post_authority_pin_gitlink_chain_is_exact_and_static_only() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "81200725aa2ac1f07b1fd15048654b3bef2f53cc"
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 4,
        "kind": "historical-gitlink-chain",
        "root_commit": "81200725aa2ac1f07b1fd15048654b3bef2f53cc",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "81200725aa2ac1f07b1fd15048654b3bef2f53cc",
                "path": "vibemind-os",
                "target_commit": "805363f068ea854acf8c2b55d572792b388e9c2a",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "805363f068ea854acf8c2b55d572792b388e9c2a",
                "path": "openfang",
                "target_commit": "cd3cef07f6c126b67a22f26975546141d891f6cf",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "805363f068ea854acf8c2b55d572792b388e9c2a",
                "path": "shared",
                "target_commit": "fe9c31d257c551568794c44098bf75e92f327e7f",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "805363f068ea854acf8c2b55d572792b388e9c2a",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_agentfarm_post_pin_gitlink_chain_is_exact_and_static_only() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "beff1541ecd7183ec980deba82b0cbbf25965f2b"
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 5,
        "kind": "historical-gitlink-chain",
        "root_commit": "beff1541ecd7183ec980deba82b0cbbf25965f2b",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "beff1541ecd7183ec980deba82b0cbbf25965f2b",
                "path": "vibemind-os",
                "target_commit": "d8093cf590b31d540adf393628108dcc9a3d45d3",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "d8093cf590b31d540adf393628108dcc9a3d45d3",
                "path": "openfang",
                "target_commit": "cd3cef07f6c126b67a22f26975546141d891f6cf",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "d8093cf590b31d540adf393628108dcc9a3d45d3",
                "path": "shared",
                "target_commit": "fe9c31d257c551568794c44098bf75e92f327e7f",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
            {
                "repository": "vibemind-os",
                "commit": "d8093cf590b31d540adf393628108dcc9a3d45d3",
                "path": "voice",
                "target_commit": "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_openfang_effective_scope_post_pin_chain_is_exact_and_static_only() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "490fafd207caf4c9b9d7599b65364a5244e1d7db"
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 6,
        "kind": "historical-gitlink-chain",
        "root_commit": "490fafd207caf4c9b9d7599b65364a5244e1d7db",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "490fafd207caf4c9b9d7599b65364a5244e1d7db",
                "path": "vibemind-os",
                "target_commit": "ef803b7d53871c52c00dfb17936bf42211c72525",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "ef803b7d53871c52c00dfb17936bf42211c72525",
                "path": "openfang",
                "target_commit": "f2b0fc2d8be90c6877ee96196456fe516815e68c",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


def test_post_pr112_gitlink_chain_preserves_static_evidence_boundary() -> None:
    entries = _ledger()["entries"]
    assert isinstance(entries, list)

    chain = next(
        entry
        for entry in entries
        if entry["kind"] == "historical-gitlink-chain"
        and entry["root_commit"] == "b790600ad7804c9048c557a69d84ef0a99a0b4d2"
    )
    assert chain == {
        "domain": "gitlink-chain",
        "ordinal": 3,
        "kind": "historical-gitlink-chain",
        "root_commit": "b790600ad7804c9048c557a69d84ef0a99a0b4d2",
        "evidence_class": "historical-local-git",
        "links": [
            {
                "repository": "Vibemind_V1",
                "commit": "b790600ad7804c9048c557a69d84ef0a99a0b4d2",
                "path": "vibemind-os",
                "target_commit": "7747d3b71576f2159a1384aea7eda131f92f7ca7",
                "evidence_class": "static-local-git-tree",
            },
            {
                "repository": "vibemind-os",
                "commit": "7747d3b71576f2159a1384aea7eda131f92f7ca7",
                "path": "shared",
                "target_commit": "fe9c31d257c551568794c44098bf75e92f327e7f",
                "evidence_class": "static-local-git-tree",
                "target_object_evidence": "not-locally-materialized",
            },
        ],
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("wrong-merge-sha", "historical merge facts do not match"),
        ("wrong-shared-pin", "historical gitlink facts do not match"),
        ("duplicate-domain-ordinal", "domain ordinal must be unique"),
        ("unreferenced-reference", "external references must be referenced"),
        ("stronger-child-git-claim", "historical gitlink facts do not match"),
        ("missing-child-merge", "historical child merge facts do not match"),
        ("wrong-parent-chain", "historical merge facts do not match"),
        ("pull-request-head-as-merge", "historical merge facts do not match"),
        ("skipped-pr", "historical merge facts do not match"),
        ("wrong-openfang-merge", "historical OpenFang merge facts do not match"),
        ("missing-openfang-merge", "historical OpenFang merge facts do not match"),
        ("wrong-openfang-parent", "historical OpenFang merge facts do not match"),
        ("openfang-pr-head", "historical OpenFang merge facts do not match"),
        ("wrong-latest-child-pin", "historical gitlink facts do not match"),
        ("missing-latest-child-pin", "historical gitlink facts do not match"),
        ("wrong-legacy-mcp-scope-pin", "historical gitlink facts do not match"),
        ("missing-legacy-mcp-scope-voice", "historical gitlink facts do not match"),
        ("wrong-fallback-no-mcp-pin", "historical gitlink facts do not match"),
        ("missing-fallback-no-mcp-voice", "historical gitlink facts do not match"),
        ("runtime-field", "forbidden claim field"),
        ("live-field", "forbidden claim field"),
        ("approval-field", "forbidden claim field"),
    ),
)
def test_ledger_rejects_closed_world_mutations(
    tmp_path: Path, mutation: str, message: str
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)

    if mutation == "wrong-merge-sha":
        entries[0]["merge_sha"] = "0" * 40
    elif mutation == "wrong-shared-pin":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "b790600ad7804c9048c557a69d84ef0a99a0b4d2"
        )
        chain["links"][1]["target_commit"] = "0" * 40
    elif mutation == "duplicate-domain-ordinal":
        entries[1]["ordinal"] = 1
    elif mutation == "unreferenced-reference":
        references = ledger["external_references"]
        assert isinstance(references, list)
        references.append(
            {
                "id": "opaque-reference-0099",
                "evidence_class": "historical-external-not-git-verified",
            }
        )
    elif mutation == "stronger-child-git-claim":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "99d41a795ac7538fb32927664a301d318d62e725"
        )
        next(link for link in chain["links"] if link["path"] == "openfang")[
            "evidence_class"
        ] = "local-git-verified"
    elif mutation == "missing-child-merge":
        entries.remove(
            next(
                entry
                for entry in entries
                if entry["kind"] == "historical-child-merge"
                and entry["pull_request"] == 115
            )
        )
    elif mutation == "wrong-parent-chain":
        entries[4]["parents"][0] = "0" * 40
    elif mutation == "pull-request-head-as-merge":
        entries[9]["merge_sha"] = "3c1960112b62c362ca8aee0310f5a90653178a09"
    elif mutation == "skipped-pr":
        entries.pop(7)
    elif mutation == "wrong-openfang-merge":
        next(
            entry
            for entry in entries
            if entry["kind"] == "historical-openfang-merge"
            and entry["pull_request"] == 8
        )["merge_sha"] = "0" * 40
    elif mutation == "missing-openfang-merge":
        entries.remove(
            next(
                entry
                for entry in entries
                if entry["kind"] == "historical-openfang-merge"
                and entry["pull_request"] == 8
            )
        )
    elif mutation == "wrong-openfang-parent":
        next(
            entry
            for entry in entries
            if entry["kind"] == "historical-openfang-merge"
            and entry["pull_request"] == 7
        )["parents"][0] = "0" * 40
    elif mutation == "openfang-pr-head":
        next(
            entry
            for entry in entries
            if entry["kind"] == "historical-openfang-merge"
            and entry["pull_request"] == 8
        )["merge_sha"] = "30f459ce694327b4e3adaa53b564bdcb5af11b2b"
    elif mutation == "wrong-latest-child-pin":
        latest_chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "beff1541ecd7183ec980deba82b0cbbf25965f2b"
        )
        next(link for link in latest_chain["links"] if link["path"] == "openfang")[
            "target_commit"
        ] = "0" * 40
    elif mutation == "missing-latest-child-pin":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "beff1541ecd7183ec980deba82b0cbbf25965f2b"
        )
        chain["links"].remove(
            next(link for link in chain["links"] if link["path"] == "shared")
        )
    elif mutation == "wrong-legacy-mcp-scope-pin":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "790ff4262be19be85254e6dd8479947822612123"
        )
        next(link for link in chain["links"] if link["path"] == "openfang")[
            "target_commit"
        ] = "0" * 40
    elif mutation == "missing-legacy-mcp-scope-voice":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "790ff4262be19be85254e6dd8479947822612123"
        )
        chain["links"].remove(
            next(link for link in chain["links"] if link["path"] == "voice")
        )
    elif mutation == "wrong-fallback-no-mcp-pin":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "5ccca83950069eaacff76868deadf5099ec357d3"
        )
        next(link for link in chain["links"] if link["path"] == "openfang")[
            "target_commit"
        ] = "0" * 40
    elif mutation == "missing-fallback-no-mcp-voice":
        chain = next(
            entry
            for entry in entries
            if entry["kind"] == "historical-gitlink-chain"
            and entry["root_commit"] == "5ccca83950069eaacff76868deadf5099ec357d3"
        )
        chain["links"].remove(
            next(link for link in chain["links"] if link["path"] == "voice")
        )
    else:
        entries[0][f"{mutation.removesuffix('-field')}_evidence"] = "forbidden"

    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match=message):
        _validate(REPOSITORY_ROOT, mutated_path)


def test_external_references_are_opaque_and_historical_only() -> None:
    ledger = _ledger()
    references = ledger["external_references"]
    assert references == [
        {
            "id": "task-openfang-0001-brain-bridge-fail-closed-v1",
            "evidence_class": "historical-external-not-git-verified",
        },
        {
            "id": "task-openfang-0002-voice-bridge-fail-closed-v1",
            "evidence_class": "historical-external-not-git-verified",
        },
        {
            "id": "gate-integration-0016-vibemind-os-pr115-postpin-regate-v1",
            "reported_outcome": "PASS",
            "evidence_class": "historical-external-not-git-verified",
        },
    ]


def test_external_reference_ids_are_canonical_and_do_not_accept_prefixes() -> None:
    ledger = _ledger()
    references = ledger["external_references"]
    assert isinstance(references, list)

    assert [reference["id"] for reference in references] == [
        "task-openfang-0001-brain-bridge-fail-closed-v1",
        "task-openfang-0002-voice-bridge-fail-closed-v1",
        "gate-integration-0016-vibemind-os-pr115-postpin-regate-v1",
    ]
    assert "task-openfang-0001" not in {
        reference["id"] for reference in references
    }
    assert "task-openfang-0002" not in {
        reference["id"] for reference in references
    }


CURRENT_CHAIN_PREFIX_ENTRY_COUNT = 79
CURRENT_CHAIN_TOTAL_ENTRY_COUNT = 155
CURRENT_CHAIN_PREFIX_SHA256 = "7a53c160ca6f0972badd271e5636efe170cdfd48405a1914325a291e2aafa946"
CURRENT_CHAIN_EXTERNAL_REFERENCES_SHA256 = "777d971ad9f8c59c358ce900eaefe749fb99b4da99fd3ed3f044dc9f883618da"
CURRENT_CHAIN_ROOT = "e804e94610c804a459aa1fb00711290acc5722f7"
CURRENT_CHAIN_CHILD = "731288b4e36ac172dfb902e22627c6f937760a3e"
CURRENT_CHAIN_OPENFANG = "75067d8c6b375fb70fe677daf78918164caaff41"
CURRENT_CHAIN_VOICE = "2a457625b4fc86ee4a673ce5d8f3bd7ca22f3899"
EXPECTED_CURRENT_MERGE_SUFFIX = (
    ("historical-merge", 149, "f78062b8022ee89327b8df8bb96a5f0210468f16"),
    ("historical-merge", 150, "f7e3b63aa8a1c5644482f2d551336d8bc156e42b"),
    ("historical-merge", 151, "5705894b1ecab3f013b3559e692247c94647bd4d"),
    ("historical-merge", 152, "88a977b469e3b8a40039e4dae5e6241c503d9c04"),
    ("historical-openfang-merge", 16, "eb9b72a4f6058c3c8aa261b846cd70da74d3a10e"),
    ("historical-merge", 153, "8f3476682bb29a3696540a3a0fda66a97d2baea8"),
    ("historical-merge", 154, "a1e9a6e785b429785386b696548f363cc9b7a6f1"),
    ("historical-merge", 155, "c149cff3d9aef1de1c03e7f9c2952196cd7f6cb1"),
    ("historical-merge", 156, "9c6f591d4daa5ecdff34f22fff55bffb0ba8c2c8"),
    ("historical-merge", 157, "c5aa093c8eab7e065a38f9acdafc0f9f5a8d7853"),
    ("historical-merge", 158, "ab98d76c64bd9d1a98e365faaa1bceb41186470d"),
    ("historical-merge", 159, "b0647ae13f59cab3c52a0444377a8ebeea9aeb34"),
    ("historical-merge", 160, "7f1f08592ece5d5d3cf035315ed5a1b9f9d4bf4e"),
    ("historical-merge", 161, "08443cced58bd7e7bd755b3ca07bb4c4e951bcc2"),
    ("historical-merge", 162, "71cc6afaf385f36ad5d265a189e1fdc62c1cea1a"),
    ("historical-merge", 163, "5e46a4aa93645d87db8faacbf4205eea97c88815"),
    ("historical-merge", 164, "292f92c24dc0407b7987f6e1f6e294cdf40b9858"),
    ("historical-child-merge", 137, "a92ccd3114a25f5bfd7b1a878ba68cff3e225895"),
    ("historical-merge", 165, "53a50c514791a445893e98bd9eff92adc4b8360b"),
    ("historical-merge", 166, "785b271a0b501c898c6ba08e55179f2aa087dce8"),
    ("historical-openfang-merge", 17, "5d38662f9fa596c8f145e4f6a45a09edf4504837"),
    ("historical-merge", 167, "792c6a27f16768509b9dbc2630b6ff6b0e2c7e6b"),
    ("historical-merge", 168, "4b2979791f36d1273c475daefb09b49d65cfcee5"),
    ("historical-merge", 169, "061feeacee25d9678d71350dcfbbc4b5592e47bf"),
    ("historical-merge", 170, "f862e3096c8215e7fcbb1bab8b355209b2aaee17"),
    ("historical-merge", 171, "48e80ad6c0447c5f649f6b7e57132ed3e4b6b0ab"),
    ("historical-merge", 172, "8f9279790443a329bf03fd30f89092f440a82950"),
    ("historical-merge", 173, "e131bd6790c3550dad063b7abd95f1fe688e215c"),
    ("historical-merge", 174, "576edc177e5ca25531169251d21175fc8c2e4c44"),
    ("historical-child-merge", 138, "fbc8761af66fb89830f7126564c419fffffae9ae"),
    ("historical-merge", 175, "302b92edd4df7340d688fc7826a9155111304f8a"),
    ("historical-merge", 176, "052768d80e600355d83feac95f5f7716dde38f12"),
    ("historical-merge", 177, "146e271ad7a0154074d64f19cc6d8193d2903817"),
    ("historical-merge", 178, "a1b136e221267e4c343cd0f2f27daba8d8d652ed"),
    ("historical-merge", 179, "b8f7cadd8b9e908cc5c0d0540b8c393e3cda4260"),
    ("historical-merge", 180, "75042ca3b83b1e62acb9eb11145161c0ab74594a"),
    ("historical-merge", 181, "93ca0edfa2115faa21a48122e05109eec8762000"),
    ("historical-merge", 182, "f9b3d484908383acf731414eb5a0f5c75b3716dd"),
    ("historical-merge", 183, "a34e500db8e1a6e6b15fa841277d4916654d9b56"),
    ("historical-merge", 184, "2680c1d040507fdbfa74a43a33f6fbd83686846c"),
    ("historical-child-merge", 139, "c5cba961126523bed39d0d94e8fd0c982cb9cbe2"),
    ("historical-merge", 185, "f4cb56660b5c44a0d996fb898090af6d2f16db52"),
    ("historical-merge", 186, "def56faeee73df1fbf13da7dd7e7987c4241c781"),
    ("historical-merge", 187, "14894480306aa458035f2f8654112c8c7be7c02f"),
    ("historical-merge", 188, "03221807cf0b69e620c39b060b7636728479d3df"),
    ("historical-merge", 189, "c2e55d4642a6f44fc7995e147b317981994defd3"),
    ("historical-merge", 190, "fe33597039b48940ca9c00d8d2ed5a5603068d89"),
    ("historical-merge", 191, "f00a9dec0ff1894383d555726b33b8b3dcbf3a0e"),
    ("historical-merge", 192, "76c8e309c1eb6a705da260b7dcb52c48b4dff1eb"),
    ("historical-merge", 193, "b6acc4a4e46da46b6fef70b68025dd9777c4c516"),
    ("historical-child-merge", 140, "f036d1572136b9cb86a92d69181e17e5a0c05fd7"),
    ("historical-merge", 194, "061c786acb0a7880ca1b74ad76019681640b746d"),
    ("historical-merge", 195, "75bb4e01cd226d00967f17839495f1f304f8255e"),
    ("historical-merge", 196, "233fec201e42bf0fdd50cdb8e272af246c9baa8c"),
    ("historical-openfang-merge", 18, "3b7bdb6b1871445d93d0e4dcad449a6b05699160"),
    ("historical-merge", 197, "a90b5bee1c8c58813244c160c0648fe0cc684343"),
    ("historical-merge", 198, "78e5ce80399242eb8d21555d3f9424b72ae84331"),
    ("historical-child-merge", 141, "a9a48af05cf509009775a7d5d144e2200f827f02"),
    ("historical-merge", 199, "3d879a7a9b97ce3d5433cc5dc7c742dbe070d575"),
    ("historical-merge", 200, "1c73437df93d33aed4608270ae6ba4d060c3f9d8"),
    ("historical-merge", 201, "4ec49de6fb1aeb6d2b68cb1c31e225645740eb4f"),
    ("historical-child-merge", 142, "ab86cc116cf802a561d6b9e76fb460f96de217f1"),
    ("historical-openfang-merge", 19, "75067d8c6b375fb70fe677daf78918164caaff41"),
    ("historical-merge", 202, "06d48febc8a0f79ced9354c12918c9b81156adce"),
    ("historical-merge", 203, "e0eb97c9cab9c664d94cbb3cb81058c27f1f3c87"),
    ("historical-merge", 204, "fda35620c54d357d852590053b5f55898bb1df28"),
    ("historical-child-merge", 143, "731288b4e36ac172dfb902e22627c6f937760a3e"),
    ("historical-merge", 205, "2e480c05343dfae28bcfa8e30ab0604ec12dd2ff"),
    ("historical-merge", 206, "1b7229b2cc8485272645e37dab78dbcee13e1bf2"),
    ("historical-merge", 207, "66812d26167f1c520d4f440c2848c0cb8a065abf"),
    ("historical-merge", 208, "745584af02edf3b9b82fec1ac61f31f30f5ac0d3"),
    ("historical-merge", 209, "17f6fbefb74ab4e4ed16b6ee137833d460fa31a5"),
    ("historical-merge", 210, "9ea036b1907cd5e01a22b02f29939cee1eac5d62"),
    ("historical-merge", 211, "f7f57a1dc2a4d5fd44e58a21345c6c2538148c71"),
    ("historical-merge", 212, "e804e94610c804a459aa1fb00711290acc5722f7"),
)


def _canonical_sha256(value: object) -> str:
    import hashlib

    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_current_integration_chain_is_strictly_appended() -> None:
    ledger = _ledger()
    entries = ledger["entries"]
    assert isinstance(entries, list)
    assert len(entries) == CURRENT_CHAIN_TOTAL_ENTRY_COUNT
    assert _canonical_sha256(entries[:CURRENT_CHAIN_PREFIX_ENTRY_COUNT]) == CURRENT_CHAIN_PREFIX_SHA256
    assert _canonical_sha256(ledger["external_references"]) == CURRENT_CHAIN_EXTERNAL_REFERENCES_SHA256

    actual_merges = tuple(
        (entry["kind"], entry["pull_request"], entry["merge_sha"])
        for entry in entries[CURRENT_CHAIN_PREFIX_ENTRY_COUNT:-1]
    )
    assert actual_merges == EXPECTED_CURRENT_MERGE_SUFFIX

    final_chain = entries[-1]
    assert final_chain["kind"] == "historical-gitlink-chain"
    assert final_chain["ordinal"] == 15
    assert final_chain["root_commit"] == CURRENT_CHAIN_ROOT
    assert tuple(
        (link["repository"], link["commit"], link["path"], link["target_commit"])
        for link in final_chain["links"]
    ) == (
        ("Vibemind_V1", CURRENT_CHAIN_ROOT, "vibemind-os", CURRENT_CHAIN_CHILD),
        ("vibemind-os", CURRENT_CHAIN_CHILD, "openfang", CURRENT_CHAIN_OPENFANG),
        ("vibemind-os", CURRENT_CHAIN_CHILD, "voice", CURRENT_CHAIN_VOICE),
    )


@pytest.mark.parametrize("tampered_path", ("vibemind-os", "openfang", "voice"))
def test_current_integration_chain_rejects_tampered_edges(
    tmp_path: Path, tampered_path: str
) -> None:
    ledger = copy.deepcopy(_ledger())
    entries = ledger["entries"]
    assert isinstance(entries, list)
    final_chain = next(
        (
            entry
            for entry in entries
            if entry.get("kind") == "historical-gitlink-chain"
            and entry.get("root_commit") == CURRENT_CHAIN_ROOT
        ),
        None,
    )
    assert final_chain is not None
    next(link for link in final_chain["links"] if link["path"] == tampered_path)[
        "target_commit"
    ] = "0" * 40
    mutated_path = tmp_path / "cockpit-reconciliation-ledger-v1.json"
    _write_ledger(mutated_path, ledger)

    from tools.v1_governance.reconciliation import ReconciliationError

    with pytest.raises(ReconciliationError, match="historical gitlink facts do not match"):
        _validate(REPOSITORY_ROOT, mutated_path)
