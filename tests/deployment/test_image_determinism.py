"""Fail-closed coverage for Proxmox compose image determinism.

Every assertion runs against a throwaway fixture repository or against the
tracked manifests of this repository. Nothing here contacts Proxmox, a Docker
daemon, a registry, or any production host.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPOSITORY_ROOT / "infra" / "proxmox" / "image_determinism.py"


def _load_validator():
    specification = importlib.util.spec_from_file_location(
        "vibemind_image_determinism", VALIDATOR_PATH
    )
    if specification is None or specification.loader is None:
        raise ImportError(f"cannot load validator from {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


image_determinism = _load_validator()
assess_image_determinism = image_determinism.assess_image_determinism


PINNED_POSTGRES = (
    "postgres:16-alpine@sha256:"
    "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
)
PINNED_NGINX = (
    "nginx:alpine@sha256:"
    "4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752"
)


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def write(root: Path, relative_path: str, content: str) -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def default_policy(waivers: list[dict[str, str]] | None = None) -> str:
    return json.dumps(
        {
            "schema_version": "vibemind.image-determinism-policy.v1",
            "manifests": {
                "required": [
                    "infra/proxmox/phase1-docker-compose.yml",
                    "infra/swarm/vibemind-stack.yml",
                ],
                "discovery_patterns": ["infra/proxmox/*-docker-compose.yml"],
            },
            "waivers": waivers or [],
        },
        indent=2,
    )


def fixture_repository(
    path: Path,
    *,
    phase1_images: list[str],
    stack_images: list[str] | None = None,
    policy: str | None = None,
    commit: bool = True,
) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "tests@example.invalid")
    git(path, "config", "user.name", "Image Determinism Tests")

    def services(images: list[str]) -> str:
        lines = ["services:"]
        for index, image in enumerate(images):
            lines.append(f"  service-{index}:")
            lines.append(f"    image: {image}")
        return "\n".join(lines) + "\n"

    write(path, "infra/proxmox/phase1-docker-compose.yml", services(phase1_images))
    write(
        path,
        "infra/swarm/vibemind-stack.yml",
        services(stack_images if stack_images is not None else [PINNED_NGINX]),
    )
    write(
        path,
        "infra/proxmox/image-determinism-policy.json",
        policy if policy is not None else default_policy(),
    )
    if commit:
        git(path, "add", "-A")
        git(path, "commit", "-m", "test: initialize image determinism fixture")
    return path


def finding_codes(report: dict) -> set[str]:
    return {finding["code"] for finding in report["findings"]}


# --- floating references fail closed -----------------------------------------


@pytest.mark.parametrize(
    "floating_image",
    [
        "postgres:16-alpine",
        "redis:latest",
        "nginx",
        "gitea/gitea:1.23",
        "public.ecr.aws/supabase/kong:2.8.1",
    ],
)
def test_floating_reference_is_blocked(tmp_path: Path, floating_image: str) -> None:
    repository = fixture_repository(tmp_path / "floating", phase1_images=[floating_image])

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "image-reference-not-deterministic" in finding_codes(report)
    assert any(
        reference["image"] == floating_image and reference["status"] == "floating"
        for reference in report["references"]
    )


def test_malformed_digest_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "malformed", phase1_images=["postgres:16-alpine@sha256:abc123"]
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "image-reference-not-deterministic" in finding_codes(report)


def test_digest_pinned_reference_is_ready(tmp_path: Path) -> None:
    repository = fixture_repository(tmp_path / "pinned", phase1_images=[PINNED_POSTGRES])

    report = assess_image_determinism(repository)

    assert report["ready"] is True
    assert report["findings"] == []
    assert all(
        reference["status"] == "deterministic" for reference in report["references"]
    )


def test_digest_without_readable_tag_is_ready(tmp_path: Path) -> None:
    bare = PINNED_POSTGRES.replace("postgres:16-alpine@", "postgres@")
    repository = fixture_repository(tmp_path / "bare-digest", phase1_images=[bare])

    report = assess_image_determinism(repository)

    assert report["ready"] is True


def test_commented_image_line_is_ignored(tmp_path: Path) -> None:
    repository = tmp_path / "commented"
    fixture_repository(repository, phase1_images=[PINNED_POSTGRES], commit=False)
    write(
        repository,
        "infra/proxmox/phase1-docker-compose.yml",
        "services:\n"
        "  service-0:\n"
        "    # this is a node:18-alpine image: it ships busybox\n"
        f"    image: {PINNED_POSTGRES}\n",
    )
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "test: commented image line")

    report = assess_image_determinism(repository)

    assert report["ready"] is True
    assert len(report["references"]) == 2


# --- waivers are a closed, auditable set -------------------------------------


def test_waived_local_image_is_ready(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "waived",
        phase1_images=["vibemind-brain-core:latest"],
        policy=default_policy(
            [
                {
                    "image": "vibemind-brain-core:latest",
                    "reason": "built on the deployment host; no registry digest exists",
                }
            ]
        ),
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is True
    assert any(
        reference["image"] == "vibemind-brain-core:latest"
        and reference["status"] == "waived"
        for reference in report["references"]
    )


def test_waiver_without_reason_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "waiver-no-reason",
        phase1_images=["vibemind-brain-core:latest"],
        policy=default_policy([{"image": "vibemind-brain-core:latest", "reason": "  "}]),
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "waiver-reason-missing" in finding_codes(report)


def test_waiver_for_registry_resolvable_image_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "waiver-registry",
        phase1_images=["public.ecr.aws/supabase/kong:2.8.1"],
        policy=default_policy(
            [
                {
                    "image": "public.ecr.aws/supabase/kong:2.8.1",
                    "reason": "we would rather not pin this one",
                }
            ]
        ),
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "waiver-not-admissible" in finding_codes(report)


def test_stale_waiver_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "waiver-stale",
        phase1_images=[PINNED_POSTGRES],
        policy=default_policy(
            [
                {
                    "image": "vibemind-retired-service:latest",
                    "reason": "built on the deployment host; no registry digest exists",
                }
            ]
        ),
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "waiver-stale" in finding_codes(report)


# --- manifest and policy integrity fail closed --------------------------------


def test_missing_policy_is_blocked(tmp_path: Path) -> None:
    repository = tmp_path / "no-policy"
    fixture_repository(repository, phase1_images=[PINNED_POSTGRES], commit=False)
    (repository / "infra" / "proxmox" / "image-determinism-policy.json").unlink()
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "test: drop policy")

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "policy-unreadable" in finding_codes(report)


def test_unparsable_policy_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(
        tmp_path / "bad-policy", phase1_images=[PINNED_POSTGRES], policy="{not json"
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "policy-unreadable" in finding_codes(report)


def test_missing_required_manifest_is_blocked(tmp_path: Path) -> None:
    repository = tmp_path / "missing-manifest"
    fixture_repository(repository, phase1_images=[PINNED_POSTGRES], commit=False)
    (repository / "infra" / "swarm" / "vibemind-stack.yml").unlink()
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "test: drop required manifest")

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "manifest-unreadable" in finding_codes(report)


def test_untracked_manifest_is_blocked(tmp_path: Path) -> None:
    repository = tmp_path / "untracked"
    fixture_repository(repository, phase1_images=[PINNED_POSTGRES], commit=False)
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "test: initialize")
    write(
        repository,
        "infra/proxmox/extension-docker-compose.yml",
        f"services:\n  extra:\n    image: {PINNED_NGINX}\n",
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "manifest-untracked" in finding_codes(report)


def test_uncommitted_manifest_change_is_blocked(tmp_path: Path) -> None:
    repository = fixture_repository(tmp_path / "dirty", phase1_images=[PINNED_POSTGRES])
    write(
        repository,
        "infra/proxmox/phase1-docker-compose.yml",
        "services:\n  service-0:\n    image: postgres:16-alpine\n",
    )

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "manifest-unreadable" in finding_codes(report)


def test_discovered_additional_compose_artifact_is_covered(tmp_path: Path) -> None:
    repository = tmp_path / "discovered"
    fixture_repository(repository, phase1_images=[PINNED_POSTGRES], commit=False)
    write(
        repository,
        "infra/proxmox/extension-docker-compose.yml",
        "services:\n  extra:\n    image: redis:7-alpine\n",
    )
    git(repository, "add", "-A")
    git(repository, "commit", "-m", "test: add discovered compose artifact")

    report = assess_image_determinism(repository)

    assert report["ready"] is False
    assert "infra/proxmox/extension-docker-compose.yml" in report["manifests"]
    assert "image-reference-not-deterministic" in finding_codes(report)


def test_non_repository_root_is_blocked(tmp_path: Path) -> None:
    report = assess_image_determinism(tmp_path / "does-not-exist")

    assert report["ready"] is False
    assert "repository-unavailable" in finding_codes(report)


# --- this repository ----------------------------------------------------------


def test_tracked_manifests_of_this_repository_are_deterministic() -> None:
    report = assess_image_determinism(REPOSITORY_ROOT)

    assert report["findings"] == [], report["findings"]
    assert report["ready"] is True
    assert "infra/swarm/vibemind-stack.yml" in report["manifests"]
    assert not [
        reference
        for reference in report["references"]
        if reference["status"] == "floating"
    ]
