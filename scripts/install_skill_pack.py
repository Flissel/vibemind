"""Install a remote skill-pack into the local vibemind-os/skills/ library.

Takes a GitHub repo URL (or local path) containing SKILL.md files in any
of the three supported formats (anthropic, openclaw, vibemind), converts
them to vibemind-format via skill_format_bridge, and installs them under
``vibemind-os/skills/<app>/<slug>/SKILL.md`` so the coordinator can find
them via skill_search.

Examples:

    # Install your own HR pack back into the local library
    python scripts/install_skill_pack.py \\
        --repo https://github.com/Flissel/vibemind-hr-skills \\
        --app hr-imported

    # Install Anthropic's official docx skill
    python scripts/install_skill_pack.py \\
        --repo https://github.com/anthropics/skills \\
        --subdir skills/docx \\
        --app office

    # Install from a local directory (already cloned/cwd)
    python scripts/install_skill_pack.py \\
        --local path/to/cloned/repo \\
        --app office

    # Dry-run to see what would be installed
    python scripts/install_skill_pack.py \\
        --repo https://github.com/Flissel/vibemind-hr-skills \\
        --app hr-imported --dry-run
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from skill_format_bridge import (  # type: ignore
    parse_frontmatter, to_vibemind, write_skill, detect_format,
)

VIBEMIND_SKILLS_ROOT = HERE.parent / "vibemind-os" / "skills"


def clone_to_temp(repo_url: str, branch: str | None = None) -> Path:
    """Shallow clone a repo to a tempdir, return the path."""
    tmp = Path(tempfile.mkdtemp(prefix="skillpack_"))
    cmd = ["git", "clone", "--depth=1"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [repo_url, str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"git clone failed: {r.stderr[:500]}")
    return tmp


def find_skills(root: Path, subdir: str | None = None) -> list[Path]:
    """Find all SKILL.md files. Subdir narrows the search if given."""
    base = root / subdir if subdir else root
    if not base.exists():
        return []
    # Common patterns:
    #   <pack>/skills/<slug>/SKILL.md          (anthropic, our export)
    #   <pack>/<slug>/SKILL.md                 (some community packs)
    #   <pack>/extensions/<ext>/skills/<slug>/SKILL.md   (openclaw)
    #   <pack>/SKILL.md                        (single-skill repo)
    found = list(base.rglob("SKILL.md"))
    # Filter out anything inside .git, node_modules, etc.
    return [
        f for f in found
        if not any(part.startswith(".") or part in {"node_modules", "__pycache__"}
                   for part in f.relative_to(root).parts)
    ]


def install_one(skill_md: Path, app: str, dry_run: bool = False) -> dict:
    """Convert + install a single SKILL.md. Returns a result dict."""
    try:
        fm, body = parse_frontmatter(skill_md)
    except Exception as e:
        return {
            "source_path": str(skill_md),
            "source_format": "unknown",
            "target_path": "",
            "skill_name": skill_md.parent.name,
            "status": "parse_error",
            "error": str(e),
        }

    fmt = detect_format(fm)
    # If already vibemind, keep frontmatter intact; otherwise convert.
    if fmt == "vibemind":
        out_fm = dict(fm)
        # ensure app matches target
        out_fm["app"] = app
        # ensure name has app-prefix
        if "name" in out_fm and not out_fm["name"].startswith(f"{app}-"):
            base_name = out_fm["name"]
            for prefix in ("hr-", "office-", "roarboot-", "rowboat-", "vibemind-"):
                if base_name.startswith(prefix):
                    base_name = base_name[len(prefix):]
                    break
            out_fm["name"] = f"{app}-{base_name}"
        out_body = body
    else:
        out_fm, out_body = to_vibemind(fm, body, app=app)

    slug = out_fm["name"]
    # strip "<app>-" for folder name (folder matches anthropic convention)
    folder_slug = slug
    if folder_slug.startswith(f"{app}-"):
        folder_slug = folder_slug[len(app) + 1:]

    target = VIBEMIND_SKILLS_ROOT / app / folder_slug / "SKILL.md"

    result = {
        "source_path": str(skill_md),
        "source_format": fmt,
        "target_path": str(target),
        "skill_name": out_fm["name"],
        "status": "would_install" if dry_run else "installed",
    }

    if not dry_run:
        if target.exists():
            result["status"] = "overwritten"
        write_skill(target, out_fm, out_body)
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--repo", help="GitHub repo URL to clone")
    src.add_argument("--local", help="Local path to an already-cloned skill pack")
    p.add_argument("--branch", default=None, help="Branch to clone (default: repo default)")
    p.add_argument("--subdir", default=None,
                   help="Subdir inside repo where skills live (e.g. 'skills' for anthropic)")
    p.add_argument("--app", required=True,
                   help="Target app folder under vibemind-os/skills/")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.repo:
        print(f"=== Cloning {args.repo} ===")
        try:
            root = clone_to_temp(args.repo, args.branch)
            print(f"  -> {root}")
        except Exception as e:
            print(f"  FAILED: {e}")
            return 1
        cleanup = root
    else:
        root = Path(args.local).resolve()
        if not root.is_dir():
            print(f"local path not found: {root}")
            return 1
        cleanup = None
        print(f"=== Using local pack: {root} ===")

    try:
        print(f"=== Finding skills (subdir={args.subdir}) ===")
        skills = find_skills(root, args.subdir)
        print(f"  found {len(skills)} SKILL.md files")
        for s in skills:
            print(f"    {s.relative_to(root)}")
        print()

        if not skills:
            print("nothing to install")
            return 0

        print(f"=== Installing under vibemind-os/skills/{args.app}/ ===")
        results = []
        for sk in skills:
            r = install_one(sk, args.app, dry_run=args.dry_run)
            results.append(r)
            status = r["status"]
            tag = "[OK]" if status in ("installed", "would_install") else (
                  "[OW]" if status == "overwritten" else "[!!]")
            print(f"  {tag} {r.get('source_format','?'):<8} "
                  f"{Path(r['source_path']).parent.name} -> "
                  f"{Path(r['target_path']).parent.name}  ({r['skill_name']})")
            if "error" in r:
                print(f"       error: {r['error']}")
        print()

        # Summary
        n_ok = sum(1 for r in results if r["status"] in ("installed", "would_install", "overwritten"))
        n_err = sum(1 for r in results if r["status"] == "parse_error")
        print(f"DONE: ok={n_ok}, errors={n_err}, target=vibemind-os/skills/{args.app}/")
        if args.dry_run:
            print("(dry-run: nothing was written)")
        return 0 if n_err == 0 else 1
    finally:
        if cleanup:
            shutil.rmtree(cleanup, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
