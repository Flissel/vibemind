from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs/operations/2026-08-01-repository-fork-reconciliation-plan.md"


def _plan() -> str:
    return PLAN.read_text(encoding="utf-8")


def test_plan_records_both_repository_forks_and_current_pins() -> None:
    plan = _plan()

    for fact in (
        "bece5e6e9ffdf28e384768e32d49ad4c1c0a7caf",
        "6cb27c35296a813b99b81a9fa3306dcff5ea2685",
        "4c5d43f56494e52973ea722d199de11844a9c938",
        "394104d556aa8503b83dc280ae11aae0200afe31",
        "630452e2d1fa90e98aad40a44a52190a65485c1b",
        "9be4dea49c9309d6a8918efbd03935c6341176bb",
        "120 / 30",
        "6 / 18",
    ):
        assert fact in plan


def test_plan_accounts_for_every_unmerged_space_branch() -> None:
    plan = _plan()

    for branch_tip in (
        "3a0fe5f",
        "7708063",
        "8017f5e",
        "ab669de",
        "4ba4da3",
        "ffd7bcd",
        "450b2e2",
        "8c785ae",
        "876f83f",
        "7b43a82",
        "8c65869",
        "6a572a8",
        "fa53d82",
        "9384e4b",
    ):
        assert branch_tip in plan


def test_plan_is_fail_closed_and_produces_one_candidate_child_commit() -> None:
    plan = _plan().lower()

    for requirement in (
        "no wholesale merge",
        "one explicit candidate child commit",
        "separate outer gitlink pr",
        "no gitlink change before",
        "standing-autonomy:v1",
        "no deployment",
        "no live-runtime claim",
    ):
        assert requirement in plan


def test_plan_replaces_workboard_and_preserves_reviewable_provenance() -> None:
    plan = _plan().lower()

    assert "origin/master remains the governance base" in plan
    assert "workboard.md remains historical" in plan
    assert "port selected operational commits" in plan
    assert "do not merge local master wholesale" in plan
    assert "tdd red" in plan
    assert "post-merge" in plan


def test_plan_records_reviewed_remote_drift_and_merged_child_candidate() -> None:
    plan = _plan().lower()

    for evidence in (
        "05a9df5cad57ba92f415ad6286b79e29924e408e",
        "c6f4d08a349f9267cac74fe716d248511ce71bdb",
        "56c8b45dbdb87eb9c75bf909476099c9663c0fae",
        "pull/62",
        "voice gitlink",
        "219 focused",
    ):
        assert evidence in plan
