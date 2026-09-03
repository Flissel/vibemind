"""project_bootstrap — atomar ein neues Coding-Projekt anlegen.

Erstellt deterministisch:
  1. `C:/Users/User/.rowboat/projects/<slug>/` als git-Repo (mit .gitignore)
  2. `C:/Users/User/.rowboat/knowledge/Coding-Projects/<slug>.md` als Manifest
  3. Stack-spezifisches Skelett wenn `--stack` angegeben (siehe STACK_BOOTSTRAPPERS)

Idempotent: wenn das Projekt schon existiert, abort statt überschreiben.
Atomar: schlägt einer der Schritte fehl, wird das, was bereits erstellt wurde,
nicht zurückgerollt — der User soll sehen wie weit er kam und manuell fixen.

Usage:
    python project_bootstrap.py --name "Mein API Service" --stack python-fastapi
    python project_bootstrap.py --name "todo-frontend" --stack node-react \\
        --git-remote https://github.com/me/todo.git --description "Todo-App"

Stacks: python, python-fastapi, node, node-react, node-next, plain (only git).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROWBOAT_ROOT = Path("C:/Users/User/.rowboat")
PROJECTS_DIR = ROWBOAT_ROOT / "projects"
MANIFESTS_DIR = ROWBOAT_ROOT / "knowledge" / "Coding-Projects"
TEMPLATE_PATH = Path(__file__).parent / "templates" / "coding-project-manifest.md"


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unnamed"


def render_manifest(fields: dict) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    # very-light template: {key} -> value. We don't use str.format() because
    # of `{` collisions in markdown.
    out = template
    for k, v in fields.items():
        out = out.replace("{" + k + "}", str(v))
    return out


# ---------------------------------------------------------------------------
# Stack bootstrappers — minimal skeletons, NOT opinionated frameworks.
# Each returns the list of files it created (relative to project root).
# ---------------------------------------------------------------------------

def bootstrap_plain(root: Path) -> list[str]:
    (root / "README.md").write_text(f"# {root.name}\n\n", encoding="utf-8")
    return ["README.md"]


def bootstrap_python(root: Path) -> list[str]:
    (root / "README.md").write_text(f"# {root.name}\n\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{root.name}"\nversion = "0.1.0"\n'
        f'description = ""\nrequires-python = ">=3.10"\n'
        f'dependencies = []\n',
        encoding="utf-8",
    )
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "main.py").write_text(
        'def main():\n    print("hello")\n\n\nif __name__ == "__main__":\n    main()\n',
        encoding="utf-8",
    )
    return ["README.md", "pyproject.toml", "src/__init__.py", "src/main.py"]


def bootstrap_python_fastapi(root: Path) -> list[str]:
    files = bootstrap_python(root)
    (root / "src" / "main.py").write_text(
        'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/")\n'
        'def root():\n    return {"hello": "world"}\n',
        encoding="utf-8",
    )
    # add fastapi to deps
    pp = root / "pyproject.toml"
    pp.write_text(
        pp.read_text(encoding="utf-8").replace(
            "dependencies = []", 'dependencies = ["fastapi>=0.110", "uvicorn>=0.27"]'
        ),
        encoding="utf-8",
    )
    return files


def bootstrap_node(root: Path) -> list[str]:
    (root / "README.md").write_text(f"# {root.name}\n\n", encoding="utf-8")
    (root / "package.json").write_text(
        json.dumps(
            {
                "name": root.name,
                "version": "0.1.0",
                "type": "module",
                "scripts": {"start": "node src/index.js"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "index.js").write_text('console.log("hello")\n', encoding="utf-8")
    return ["README.md", "package.json", "src/index.js"]


STACK_BOOTSTRAPPERS = {
    "plain": bootstrap_plain,
    "python": bootstrap_python,
    "python-fastapi": bootstrap_python_fastapi,
    "node": bootstrap_node,
    "node-react": bootstrap_node,  # delegate; LLM-Skill kann später CRA/Vite installieren
    "node-next": bootstrap_node,
}


GITIGNORE_BASE = """\
# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Secrets
.env
.env.local
*.pem

# Logs
*.log
"""

GITIGNORE_BY_STACK = {
    "python": "\n# Python\n__pycache__/\n*.pyc\n.venv/\nvenv/\ndist/\nbuild/\n*.egg-info/\n",
    "python-fastapi": "\n# Python\n__pycache__/\n*.pyc\n.venv/\nvenv/\ndist/\nbuild/\n*.egg-info/\n",
    "node": "\n# Node\nnode_modules/\nnpm-debug.log\ndist/\n.next/\n",
    "node-react": "\n# Node\nnode_modules/\nnpm-debug.log\ndist/\nbuild/\n",
    "node-next": "\n# Node\nnode_modules/\nnpm-debug.log\n.next/\nout/\n",
    "plain": "",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Human name (z.B. 'Mein API Service')")
    parser.add_argument("--stack", default="plain", choices=list(STACK_BOOTSTRAPPERS.keys()))
    parser.add_argument("--description", default="", help="Kurzbeschreibung für das Manifest")
    parser.add_argument("--git-remote", default="", help="Optional: github/gitlab remote-URL")
    parser.add_argument("--git-branch", default="main")
    parser.add_argument("--tags", default="", help="Komma-separiert, z.B. 'api,backend'")
    parser.add_argument("--deploy-provider", default="", choices=["", "vercel", "cloudflare", "docker", "fly"])
    parser.add_argument("--deploy-url", default="")
    parser.add_argument("--slug", default="", help="Optional: override auto-slug")
    args = parser.parse_args()

    slug = args.slug or slugify(args.name)
    project_root = PROJECTS_DIR / slug
    manifest_path = MANIFESTS_DIR / f"{slug}.md"

    if project_root.exists() or manifest_path.exists():
        print(f"[bootstrap] ABORT: project '{slug}' already exists.", file=sys.stderr)
        print(f"  project_root: {project_root} (exists={project_root.exists()})", file=sys.stderr)
        print(f"  manifest:     {manifest_path} (exists={manifest_path.exists()})", file=sys.stderr)
        return 2

    # 1. Create directory + stack skeleton
    project_root.mkdir(parents=True)
    bootstrap_fn = STACK_BOOTSTRAPPERS[args.stack]
    created_files = bootstrap_fn(project_root)

    # 2. .gitignore
    gitignore = GITIGNORE_BASE + GITIGNORE_BY_STACK.get(args.stack, "")
    (project_root / ".gitignore").write_text(gitignore, encoding="utf-8")
    created_files.append(".gitignore")

    # 3. git init
    git_ok = False
    try:
        subprocess.run(["git", "init", "-b", args.git_branch], cwd=project_root, check=True, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=project_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit (project_bootstrap)"],
            cwd=project_root, check=True, capture_output=True,
        )
        if args.git_remote:
            subprocess.run(
                ["git", "remote", "add", "origin", args.git_remote],
                cwd=project_root, check=True, capture_output=True,
            )
        git_ok = True
    except subprocess.CalledProcessError as e:
        print(f"[bootstrap] WARNING: git init failed: {e.stderr.decode(errors='replace')}", file=sys.stderr)

    # 4. Resolve last_commit hash
    last_commit = ""
    if git_ok:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=project_root, check=True, capture_output=True,
            )
            last_commit = result.stdout.decode().strip()
        except subprocess.CalledProcessError:
            pass

    # 5. Manifest
    parts = args.stack.split("-", 1)
    stack_language = parts[0]
    stack_framework = parts[1] if len(parts) > 1 else ""
    stack_pkg = {"python": "pip", "python-fastapi": "pip", "node": "npm", "node-react": "npm", "node-next": "npm"}.get(args.stack, "")

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]
    aliases = sorted({slug, args.name.lower(), slug.replace("-", " ")})

    fields = {
        "name": args.name,
        "slug": slug,
        "code_path": str(project_root).replace("\\", "/"),
        "stack_language": stack_language or "—",
        "stack_framework": stack_framework or "—",
        "stack_pkg": stack_pkg or "—",
        "git_remote": args.git_remote or "—",
        "git_branch": args.git_branch,
        "git_last_commit": last_commit or "—",
        "deploy_provider": args.deploy_provider or "—",
        "deploy_url": args.deploy_url or "—",
        "deploy_secrets": "—",
        "tags": json.dumps(tags_list, ensure_ascii=False),
        "tags_human": ", ".join(tags_list) if tags_list else "—",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "aliases": json.dumps(aliases, ensure_ascii=False),
        "aliases_examples": "\n".join(f"- **{a}**" for a in aliases),
        "description": args.description or "*(Kurzbeschreibung hier)*",
    }
    manifest_text = render_manifest(fields)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest_text, encoding="utf-8")

    # 6. Report
    print(json.dumps(
        {
            "status": "ok",
            "slug": slug,
            "name": args.name,
            "code_path": str(project_root).replace("\\", "/"),
            "manifest_path": str(manifest_path).replace("\\", "/"),
            "stack": args.stack,
            "git_initialized": git_ok,
            "git_last_commit": last_commit,
            "files_created": created_files,
            "aliases": aliases,
        },
        indent=2, ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
