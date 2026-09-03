"""github_create_repo — push a coding-project to a fresh GitHub repo.

What it does (atomically):
  1. Load the manifest at .rowboat/knowledge/Coding-Projects/<slug>.md
  2. Use `gh repo create` to make a new GitHub repo (private by default)
  3. Push the local repo's `main` branch
  4. Update the manifest's `git.remote` field with the new URL

Idempotent: if the manifest already has a remote, abort (use --force to
overwrite).

Authentication is handled by `gh` CLI — must already be logged in
(`gh auth status` should show "Logged in").

Usage::

    python github_create_repo.py --slug test-bootstrap
    python github_create_repo.py --slug my-thing --visibility public --description "Foo"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROWBOAT_ROOT = Path("C:/Users/User/.rowboat")
PROJECTS_DIR = ROWBOAT_ROOT / "projects"
MANIFESTS_DIR = ROWBOAT_ROOT / "knowledge" / "Coding-Projects"


def load_manifest(slug: str) -> tuple[Path, str, dict[str, Any]]:
    """Return (manifest_path, full_text, parsed_frontmatter_dict)."""
    path = MANIFESTS_DIR / f"{slug}.md"
    if not path.is_file():
        print(f"[gh-create] manifest not found: {path}", file=sys.stderr)
        print(f"  Known projects:", file=sys.stderr)
        for m in sorted(MANIFESTS_DIR.glob("*.md")):
            print(f"    {m.stem}", file=sys.stderr)
        sys.exit(2)
    text = path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    if text.startswith("---"):
        end = text.find("\n---", 4)
        if end >= 0:
            for line in text[4:end].splitlines():
                m = re.match(r"^(\w+):\s*(.*)$", line)
                if m:
                    fm[m.group(1)] = m.group(2).strip()
    return path, text, fm


def get_existing_remote(code_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=code_path, check=True, capture_output=True,
        )
        return result.stdout.decode().strip() or None
    except subprocess.CalledProcessError:
        return None


def get_active_gh_user() -> str | None:
    """Return the currently active gh CLI user (or None on failure)."""
    try:
        result = subprocess.run(
            ["gh", "api", "user", "-q", ".login"],
            check=True, capture_output=True, text=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def list_gh_authenticated_users() -> list[str]:
    """Parse `gh auth status` to list all known logged-in accounts."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        return []
    # `gh auth status` prints lines like "Logged in to github.com account NAME (keyring)"
    users = re.findall(r"account\s+(\S+)\s+\(", result.stdout + result.stderr)
    return list(dict.fromkeys(users))  # dedupe preserving order


def switch_gh_account(target_user: str) -> bool:
    """Switch the active gh CLI account. Returns True on success."""
    try:
        subprocess.run(
            ["gh", "auth", "switch", "--user", target_user],
            check=True, capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ensure_gh_account_for_owner(owner: str) -> tuple[bool, str]:
    """If --owner is a user/org that doesn't match the current gh user, try to
    switch. Returns (switched_ok, message). Switched_ok=True even if no switch
    was needed.

    Heuristic: owner can be either a username or an org slug. We don't know
    which without an API call, so we compare against `gh api user`.
    - If owner matches active user: no switch needed.
    - If owner is in `gh auth status` user list: switch.
    - If not in user list: assume owner is an org of the active user, no switch.
    """
    if not owner:
        return True, "no owner specified, using active gh user"
    active = get_active_gh_user() or ""
    # GitHub usernames are case-insensitive — match accordingly so
    # `--owner vibemind-lab` and the gh-reported `Vibemind-LAB` are the same.
    if active.lower() == owner.lower():
        return True, f"already on {active}"
    known_users = list_gh_authenticated_users()
    known_lc = {u.lower(): u for u in known_users}
    if owner.lower() in known_lc:
        canonical = known_lc[owner.lower()]
        ok = switch_gh_account(canonical)
        return ok, f"switched to {canonical}" if ok else f"failed to switch to {canonical}"
    # Owner isn't a logged-in user — assume it's an org slug for the active user
    return True, f"owner '{owner}' treated as org of active user '{active}'"


def update_manifest_remote(manifest_path: Path, new_remote: str) -> None:
    """Surgically update only the `remote:` field under `git:` in frontmatter
    and the `**Remote:**` line in the body. Leave everything else untouched."""
    text = manifest_path.read_text(encoding="utf-8")
    # Frontmatter: `  remote: <whatever>` after `git:`
    text = re.sub(
        r"(git:\s*\n(?:[^\n]*\n){0,5}?\s*remote:)\s*[^\n]*",
        rf"\1 {new_remote}",
        text,
        count=1,
    )
    # Body: `- **Remote:** ...`
    text = re.sub(
        r"-\s*\*\*Remote:\*\*\s*[^\n]*",
        f"- **Remote:** {new_remote}",
        text,
        count=1,
    )
    manifest_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="Project slug (matches manifest file name)")
    parser.add_argument("--visibility", default="private", choices=["private", "public", "internal"])
    parser.add_argument("--description", default="", help="GitHub repo description")
    parser.add_argument("--force", action="store_true",
                        help="Allow overwriting an existing remote (DANGEROUS — usually wrong)")
    parser.add_argument("--repo-name", default="",
                        help="Override the repo name (default: slug)")
    parser.add_argument("--owner", default="",
                        help="Owner/org prefix (default: authenticated user)")
    args = parser.parse_args()

    manifest_path, _manifest_text, fm = load_manifest(args.slug)
    code_path_str = fm.get("code_path")
    if not code_path_str:
        print(f"[gh-create] manifest is missing code_path", file=sys.stderr)
        return 2
    code_path = Path(code_path_str)
    if not code_path.is_dir():
        print(f"[gh-create] code_path does not exist on disk: {code_path}", file=sys.stderr)
        return 2

    existing_remote = get_existing_remote(code_path)
    if existing_remote and not args.force:
        print(f"[gh-create] ABORT: '{args.slug}' already has a remote: {existing_remote}", file=sys.stderr)
        print(f"  Pass --force to overwrite (this won't delete the old GitHub repo).", file=sys.stderr)
        return 2

    repo_name = args.repo_name or args.slug
    full_name = f"{args.owner}/{repo_name}" if args.owner else repo_name

    # Multi-account: if --owner is a different logged-in user, switch first.
    # Orgs of the active user don't trigger a switch (they're scoped to the
    # current token).
    if args.owner:
        switched_ok, msg = ensure_gh_account_for_owner(args.owner)
        if not switched_ok:
            print(f"[gh-create] {msg}", file=sys.stderr)
            print(f"  Available accounts: {list_gh_authenticated_users()}", file=sys.stderr)
            print(f"  To add: gh auth login --hostname github.com (use a PAT)", file=sys.stderr)
            return 2
        print(f"[gh-create] gh account: {msg}", file=sys.stderr)

    # Build `gh repo create` command. Using --source pushes the local repo.
    gh_cmd = [
        "gh", "repo", "create", full_name,
        f"--{args.visibility}",
        "--source", str(code_path),
        "--remote", "origin",
        "--push",
    ]
    if args.description:
        gh_cmd += ["--description", args.description]
    if args.force and existing_remote:
        # `gh repo create` won't reuse an existing 'origin' — remove first
        subprocess.run(["git", "remote", "remove", "origin"], cwd=code_path, capture_output=True)

    try:
        result = subprocess.run(gh_cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[gh-create] gh repo create failed (exit {e.returncode})", file=sys.stderr)
        print(f"  stderr: {e.stderr}", file=sys.stderr)
        # Hint for common multi-account confusion
        if args.owner and (
            "Could not resolve to a User" in (e.stderr or "")
            or "Resource not accessible" in (e.stderr or "")
            or "HTTP 404" in (e.stderr or "")
        ):
            print(f"\n  HINT: '{args.owner}' is not accessible to the active gh user", file=sys.stderr)
            print(f"        ({get_active_gh_user() or '?'}). Either:", file=sys.stderr)
            print(f"        - Add the account: gh auth login --hostname github.com", file=sys.stderr)
            print(f"          (then re-run this command)", file=sys.stderr)
            print(f"        - Or pass --owner of an org you have access to", file=sys.stderr)
        return e.returncode

    # gh prints the repo URL on stdout; extract it
    new_remote = (result.stdout or "").strip().splitlines()[-1] if result.stdout else ""
    if not new_remote.startswith("http"):
        # Fall back to asking git
        new_remote = get_existing_remote(code_path) or ""

    if new_remote:
        update_manifest_remote(manifest_path, new_remote)

    print(json.dumps({
        "status": "ok",
        "slug": args.slug,
        "repo_url": new_remote,
        "manifest_updated": bool(new_remote),
        "visibility": args.visibility,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
