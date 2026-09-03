"""Fail-closed determinism check for versioned Proxmox compose manifests.

Deployment readiness treats an image reference as deterministic only when it
carries an explicit ``@sha256:<64 hex>`` digest. A readable tag may stay in
front of the digest (``postgres:16-alpine@sha256:...``) — the digest is what
nails the bits, the tag is documentation.

Images that are built on the deployment host never reach a registry, so no
digest exists for them. Those are the only admissible exception and they must
be enumerated one by one, with a reason, in the versioned policy at
``infra/proxmox/image-determinism-policy.json``. The waiver list is a closed
set: a waiver for an image that a registry *could* resolve is rejected, and a
waiver that no longer matches any reference is rejected too, so the list
cannot silently grow stale.

Everything is decided from tracked, committed, unmodified repository content.
This module never contacts Proxmox, a Docker daemon, a registry, or any host.

Usage:
    python infra/proxmox/image_determinism.py --repo .

Exit codes: 0 = ready, 2 = blocked, 1 = usage error.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys

SCHEMA_VERSION = "vibemind.image-determinism.v1"
POLICY_SCHEMA_VERSION = "vibemind.image-determinism-policy.v1"
POLICY_PATH = "infra/proxmox/image-determinism-policy.json"

#: ``image:`` on a non-comment line; the value runs to the first whitespace or
#: inline comment.
IMAGE_LINE = re.compile(r"^[ \t]*image:[ \t]*(?P<image>[^\s#]+)", re.MULTILINE)

#: The only form accepted as deterministic.
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _git(repository_root: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def is_deterministic(image: str) -> bool:
    """True when the reference pins an exact manifest digest."""
    return bool(DIGEST.search(image))


def _looks_locally_built(image: str) -> bool:
    """True when no public registry can own this reference.

    A registry-resolvable name either carries a registry host or a Docker Hub
    namespace (both contain ``/``), or is a single-segment official image
    (``postgres``, ``redis``). What is left — a single-segment, hyphenated
    project name such as ``vibemind-brain-core`` or ``davefelix-coding-engine-api``
    — only ever exists in the local image store of the deployment host and is
    therefore the one case a waiver may cover.
    """
    reference = DIGEST.sub("", image)
    name = reference.rsplit(":", 1)[0] if ":" in reference.rsplit("/", 1)[-1] else reference
    if "/" in name:
        return False
    return "-" in name


def _is_readable_versioned_artifact(
    repository_root: Path, relative_path: str
) -> tuple[bool, str]:
    """Mirror the readiness preflight's versioned-artifact semantics."""
    if not (repository_root / relative_path).is_file():
        return False, "absent from the working tree"
    if _git(repository_root, "ls-files", "--error-unmatch", "--", relative_path).returncode != 0:
        return False, "not tracked by Git"
    if _git(repository_root, "cat-file", "-e", f"HEAD:{relative_path}").returncode != 0:
        return False, "has no committed HEAD version"
    if _git(repository_root, "diff", "--quiet", "--", relative_path).returncode != 0:
        return False, "has uncommitted working-tree modifications"
    if _git(repository_root, "diff", "--cached", "--quiet", "--", relative_path).returncode != 0:
        return False, "has staged modifications"
    return True, "readable versioned artifact"


def _tracked_paths(repository_root: Path) -> list[str] | None:
    head = _git(repository_root, "ls-tree", "-r", "--name-only", "HEAD")
    if head.returncode != 0:
        return None
    index = _git(repository_root, "ls-files", "--full-name")
    if index.returncode != 0:
        return None
    paths = set(head.stdout.splitlines()) | set(index.stdout.splitlines())
    return sorted(path for path in paths if path)


def _discover_manifests(
    repository_root: Path, policy: dict, findings: list[dict]
) -> list[str]:
    required = [str(entry) for entry in policy.get("manifests", {}).get("required", [])]
    patterns = [str(entry) for entry in policy.get("manifests", {}).get("discovery_patterns", [])]

    discovered: set[str] = set(required)
    tracked = _tracked_paths(repository_root)
    if tracked is None:
        findings.append(
            {"code": "repository-unavailable", "path": ".", "detail": "Git metadata is unreadable"}
        )
        return sorted(discovered)
    for pattern in patterns:
        discovered.update(path for path in tracked if fnmatch.fnmatch(path, pattern))

    # An untracked file matching a discovery pattern is a manifest that would
    # ship without review. Fail closed rather than ignore it.
    for pattern in patterns:
        for path in repository_root.glob(pattern):
            relative = path.relative_to(repository_root).as_posix()
            if relative not in tracked:
                findings.append(
                    {
                        "code": "manifest-untracked",
                        "path": relative,
                        "detail": "matches a discovery pattern but is not tracked by Git",
                    }
                )
    return sorted(discovered)


def _load_policy(repository_root: Path, findings: list[dict]) -> dict | None:
    readable, detail = _is_readable_versioned_artifact(repository_root, POLICY_PATH)
    if not readable:
        findings.append({"code": "policy-unreadable", "path": POLICY_PATH, "detail": detail})
        return None
    try:
        policy = json.loads((repository_root / POLICY_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        findings.append(
            {"code": "policy-unreadable", "path": POLICY_PATH, "detail": f"unparsable: {error}"}
        )
        return None
    if not isinstance(policy, dict) or policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        findings.append(
            {
                "code": "policy-unreadable",
                "path": POLICY_PATH,
                "detail": f"schema_version is not {POLICY_SCHEMA_VERSION}",
            }
        )
        return None
    return policy


def _collect_waivers(policy: dict, findings: list[dict]) -> dict[str, str]:
    waivers: dict[str, str] = {}
    entries = policy.get("waivers", [])
    if not isinstance(entries, list):
        findings.append(
            {"code": "policy-unreadable", "path": POLICY_PATH, "detail": "waivers is not a list"}
        )
        return waivers
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("image"), str):
            findings.append(
                {
                    "code": "policy-unreadable",
                    "path": POLICY_PATH,
                    "detail": f"malformed waiver entry: {entry!r}",
                }
            )
            continue
        image = entry["image"]
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            findings.append(
                {
                    "code": "waiver-reason-missing",
                    "path": POLICY_PATH,
                    "detail": f"waiver for {image} carries no reason",
                }
            )
            continue
        if not _looks_locally_built(image):
            findings.append(
                {
                    "code": "waiver-not-admissible",
                    "path": POLICY_PATH,
                    "detail": (
                        f"{image} is resolvable from a registry and must carry a digest "
                        "instead of a waiver"
                    ),
                }
            )
            continue
        waivers[image] = reason.strip()
    return waivers


def assess_image_determinism(repository_root: Path | str) -> dict:
    """Assess every image reference in the versioned deployment manifests."""
    repository_root = Path(repository_root)
    findings: list[dict] = []
    references: list[dict] = []

    if not repository_root.is_dir() or _git(repository_root, "rev-parse", "--git-dir").returncode != 0:
        findings.append(
            {
                "code": "repository-unavailable",
                "path": str(repository_root),
                "detail": "not a readable Git repository",
            }
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "manifests": [],
            "references": references,
            "findings": findings,
        }

    policy = _load_policy(repository_root, findings)
    if policy is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "ready": False,
            "manifests": [],
            "references": references,
            "findings": findings,
        }

    waivers = _collect_waivers(policy, findings)
    manifests = _discover_manifests(repository_root, policy, findings)
    used_waivers: set[str] = set()

    for relative_path in manifests:
        readable, detail = _is_readable_versioned_artifact(repository_root, relative_path)
        if not readable:
            findings.append(
                {"code": "manifest-unreadable", "path": relative_path, "detail": detail}
            )
            continue
        try:
            content = (repository_root / relative_path).read_text(encoding="utf-8")
        except OSError as error:
            findings.append(
                {"code": "manifest-unreadable", "path": relative_path, "detail": str(error)}
            )
            continue

        for match in IMAGE_LINE.finditer(content):
            image = match.group("image")
            line = content.count("\n", 0, match.start()) + 1
            if is_deterministic(image):
                status = "deterministic"
            elif image in waivers:
                status = "waived"
                used_waivers.add(image)
            else:
                status = "floating"
                findings.append(
                    {
                        "code": "image-reference-not-deterministic",
                        "path": f"{relative_path}:{line}",
                        "detail": (
                            f"{image} carries no @sha256 digest and holds no admissible waiver"
                        ),
                    }
                )
            references.append(
                {
                    "image": image,
                    "manifest": relative_path,
                    "line": line,
                    "status": status,
                    "reason": waivers.get(image) if status == "waived" else None,
                }
            )

    for image in sorted(set(waivers) - used_waivers):
        findings.append(
            {
                "code": "waiver-stale",
                "path": POLICY_PATH,
                "detail": f"waiver for {image} matches no reference in the versioned manifests",
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "ready": not findings,
        "manifests": manifests,
        "references": references,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="repository root to assess")
    arguments = parser.parse_args(argv)
    report = assess_image_determinism(arguments.repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
