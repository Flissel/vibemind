"""vercel_deploy — deploy a coding-project to Vercel and update its manifest.

What it does:
  1. Load the manifest at .rowboat/knowledge/Coding-Projects/<slug>.md
  2. Run `vercel --yes` from the project's code_path
     - First run: links to a new Vercel project (auto-named after slug)
     - Subsequent runs: deploy to the existing linked project
  3. Optionally `--prod` for a production deployment
  4. Parse the deployment URL from CLI output, write to manifest

Authentication: vercel CLI must already be logged in (`vercel whoami`).

Usage::

    python vercel_deploy.py --slug test-bootstrap                 # preview deploy
    python vercel_deploy.py --slug test-bootstrap --prod           # production
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
MANIFESTS_DIR = ROWBOAT_ROOT / "knowledge" / "Coding-Projects"
ENV_FILE = Path("C:/Users/User/Desktop/Vibemind_V1/.env")

# Owner -> .env var name that holds that owner's Vercel access token.
# Default lookup uses uppercase-with-underscores; add custom mappings here as
# you onboard more Vercel identities.
OWNER_TOKEN_ENV_MAP = {
    "Vibemind-LAB": "VERCEL_TOKEN_VIBEMIND_LAB",
    "vibemind-lab": "VERCEL_TOKEN_VIBEMIND_LAB",
}

# Owner -> Vercel team slug for deploys. Vercel calls them "scope".
OWNER_SCOPE_MAP = {
    "Vibemind-LAB": "vibe-mind-lab",
    "vibemind-lab": "vibe-mind-lab",
}


def load_token_for_owner(owner: str) -> str | None:
    """Look up a Vercel access token for the given owner from .env.

    Returns the token string or None when not configured. If no owner, returns
    None so the caller falls back to the default vercel CLI auth (the
    interactive `vercel login` user).
    """
    if not owner:
        return None
    var_name = OWNER_TOKEN_ENV_MAP.get(owner) or f"VERCEL_TOKEN_{owner.upper().replace('-', '_')}"
    # Prefer process env, fall back to parsing .env directly
    val = __import__("os").environ.get(var_name)
    if val:
        return val.strip()
    if ENV_FILE.is_file():
        for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == var_name:
                return value.strip()
    return None


def load_manifest(slug: str) -> tuple[Path, dict[str, Any]]:
    path = MANIFESTS_DIR / f"{slug}.md"
    if not path.is_file():
        print(f"[vercel] manifest not found: {path}", file=sys.stderr)
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
    return path, fm


def update_manifest_deploy(manifest_path: Path, provider: str, url: str) -> None:
    """Update deployment.provider and deployment.url in frontmatter + body."""
    text = manifest_path.read_text(encoding="utf-8")
    # Frontmatter `deployment:` block — update provider + url
    text = re.sub(
        r"(deployment:\s*\n\s*provider:)\s*[^\n]*",
        rf"\1 {provider}",
        text, count=1,
    )
    text = re.sub(
        r"(deployment:\s*\n(?:[^\n]*\n){0,3}?\s*url:)\s*[^\n]*",
        rf"\1 {url}",
        text, count=1,
    )
    # Body lines
    text = re.sub(
        r"-\s*\*\*Provider:\*\*\s*[^\n]*",
        f"- **Provider:** {provider}",
        text, count=1,
    )
    text = re.sub(
        r"-\s*\*\*URL:\*\*\s*[^\n]*",
        f"- **URL:** {url}",
        text, count=1,
    )
    manifest_path.write_text(text, encoding="utf-8")


def extract_deployment_url(stdout: str, stderr: str) -> str | None:
    """Vercel CLI prints the URL like `https://my-app-abc123.vercel.app` —
    grep it out of either stream."""
    combined = (stdout or "") + "\n" + (stderr or "")
    # Match the FIRST https://...vercel.app URL we see
    m = re.search(r"https://[a-z0-9\-]+\.vercel\.app(?:/\S*)?", combined, re.IGNORECASE)
    return m.group(0) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--prod", action="store_true", help="Production deploy (default: preview)")
    parser.add_argument("--project-name", default="",
                        help="Override the Vercel project name (default: slug)")
    parser.add_argument("--owner", default="",
                        help="Use a non-default Vercel identity. Token is looked up via "
                             "OWNER_TOKEN_ENV_MAP / VERCEL_TOKEN_<OWNER> in .env.")
    parser.add_argument("--scope", default="",
                        help="Vercel team slug to deploy under (e.g. 'vibe-mind-lab'). "
                             "Auto-inferred from --owner if omitted.")
    args = parser.parse_args()

    manifest_path, fm = load_manifest(args.slug)
    code_path_str = fm.get("code_path")
    if not code_path_str:
        print(f"[vercel] manifest is missing code_path", file=sys.stderr)
        return 2
    code_path = Path(code_path_str)
    if not code_path.is_dir():
        print(f"[vercel] code_path does not exist: {code_path}", file=sys.stderr)
        return 2

    project_name = args.project_name or args.slug

    # Windows: npm-installed CLIs are .cmd shims. subprocess.run with a bare
    # name doesn't find them unless shell=True. We resolve via shutil.which
    # and fall back to a known npm-global path.
    import shutil
    vercel_bin = shutil.which("vercel") or shutil.which("vercel.cmd")
    if not vercel_bin:
        npm_global = Path(__import__("os").environ.get("APPDATA", "")) / "npm" / "vercel.cmd"
        if npm_global.is_file():
            vercel_bin = str(npm_global)

    if not vercel_bin:
        print(f"[vercel] 'vercel' CLI not found. Install: npm i -g vercel", file=sys.stderr)
        return 127

    # NB: `--name` is deprecated in newer vercel CLI versions. Project naming
    # happens on first link instead. project_name kept here for future ref but
    # not passed to argv.
    _ = project_name
    vercel_cmd = [vercel_bin, "--yes"]
    if args.prod:
        vercel_cmd.append("--prod")

    # Multi-identity: if --owner is set, use that owner's token + team scope.
    if args.owner:
        token = load_token_for_owner(args.owner)
        if not token:
            var = OWNER_TOKEN_ENV_MAP.get(args.owner) or f"VERCEL_TOKEN_{args.owner.upper().replace('-', '_')}"
            print(f"[vercel] no token found for --owner {args.owner}", file=sys.stderr)
            print(f"  Expected env var or .env key: {var}", file=sys.stderr)
            return 2
        vercel_cmd += ["--token", token]
        scope = args.scope or OWNER_SCOPE_MAP.get(args.owner)
        if scope:
            vercel_cmd += ["--scope", scope]

    try:
        result = subprocess.run(
            vercel_cmd,
            cwd=code_path,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min cap — Vercel deploys are usually < 1 min
        )
    except subprocess.TimeoutExpired:
        print(f"[vercel] deploy timed out after 5 minutes", file=sys.stderr)
        return 124

    if result.returncode != 0:
        print(f"[vercel] deploy failed (exit {result.returncode})", file=sys.stderr)
        print(f"  stdout: {result.stdout[:500]}", file=sys.stderr)
        print(f"  stderr: {result.stderr[:500]}", file=sys.stderr)
        return result.returncode

    url = extract_deployment_url(result.stdout, result.stderr)

    if url:
        update_manifest_deploy(manifest_path, "vercel", url)

    print(json.dumps({
        "status": "ok",
        "slug": args.slug,
        "url": url,
        "prod": args.prod,
        "manifest_updated": bool(url),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
