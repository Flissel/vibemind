"""openclaude-vibemind — `claude`-style CLI that targets gpt-4o-mini.

Wraps openclaude with: OpenAI profile env, Vibemind_V1 project cwd, and a
selectable MCP subset (so the 25-server `.mcp.json` doesn't always load).

MCP profiles live in `.claude/mcp-profiles/<name>.json`:
  - bare    — zero MCPs (fastest startup)
  - code    — fungus-search only (default)
  - desktop — desktop-automation + brain + ideas
  - full    — the full project `.mcp.json` (slowest, all 25 servers)

Pass `--mcp <name>` to pick one. Everything else forwards to openclaude.

Note: this wrapper passes args via os.execvp (no shell), so quoting works the
same as native `claude`. Use `-p "your prompt"` or pipe via stdin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Local helper — single source of truth for profile resolution.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _openclaude_profile import load_profile as _load_profile  # noqa: E402


PROJECT_ROOT = Path("C:/Users/User/Desktop/Vibemind_V1")
MCP_PROFILE_DIR = PROJECT_ROOT / ".claude" / "mcp-profiles"
FULL_MCP_FILE = PROJECT_ROOT / ".mcp.json"
GLOBAL_BIN_DIR = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@gitlawb" / "openclaude" / "bin"
GLOBAL_OPENCLAUDE_BIN = GLOBAL_BIN_DIR / "openclaude"

PROFILE_GATES = {
    "openai": "CLAUDE_CODE_USE_OPENAI",
    "ollama": "CLAUDE_CODE_USE_OPENAI",
    "gemini": "CLAUDE_CODE_USE_GEMINI",
    "codex": "CLAUDE_CODE_USE_OPENAI",
}


def extract_prompt_for_routing(argv: list[str]) -> str:
    """Find the prompt text in argv (after `-p`/`--print`) or read it from stdin.

    Returns empty string if no prompt is discoverable (interactive mode).
    """
    # Look for `-p <prompt>` / `--print <prompt>` positional
    for i, tok in enumerate(argv):
        if tok in ("-p", "--print") and i + 1 < len(argv):
            next_tok = argv[i + 1]
            if not next_tok.startswith("--"):
                return next_tok
    # Fall back to stdin (only if stdin is a pipe, not a tty)
    if not sys.stdin.isatty():
        try:
            data = sys.stdin.read()
            # Re-inject stdin so the child still gets it via --input-format text
            os.environ["_OPENCLAUDE_VIBEMIND_STDIN_BUF"] = data
            return data.strip()
        except Exception:
            return ""
    return ""


def list_profiles() -> list[str]:
    if not MCP_PROFILE_DIR.is_dir():
        return ["full"]
    return [p.stem for p in MCP_PROFILE_DIR.glob("*.json") if not p.stem.startswith("_")] + ["full"]


def resolve_mcp_config(name: str) -> Path | None:
    if name == "full":
        return FULL_MCP_FILE if FULL_MCP_FILE.is_file() else None
    candidate = MCP_PROFILE_DIR / f"{name}.json"
    return candidate if candidate.is_file() else None


def load_openclaude_profile() -> dict:
    return _load_profile(global_bin_dir=GLOBAL_BIN_DIR)


def main() -> int:
    argv = sys.argv[1:]

    # Extract --mcp <name> from argv. If absent, profile is picked adaptively
    # based on the prompt by `mcp_profile_selector.py`.
    mcp_profile: str | None = None
    cleaned: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--mcp" and i + 1 < len(argv):
            mcp_profile = argv[i + 1]
            i += 2
            continue
        if argv[i] == "--list-mcp-profiles":
            for p in list_profiles():
                print(p)
            return 0
        cleaned.append(argv[i])
        i += 1

    # Adaptive selection: if no --mcp passed, try to find the prompt text in argv
    # or stdin and route through the selector.
    adaptive_skills: list[str] = []
    adaptive_reason = ""
    if mcp_profile is None:
        prompt_text = extract_prompt_for_routing(cleaned)
        if prompt_text:
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from mcp_profile_selector import select as select_profile  # type: ignore
                result = select_profile(prompt_text)
                mcp_profile = result.get("profile") or "code"
                adaptive_skills = result.get("skills") or []
                adaptive_reason = result.get("reason") or ""
                if os.environ.get("OPENCLAUDE_VIBEMIND_DEBUG"):
                    print(f"[openclaude-vibemind] adaptive: profile={mcp_profile} "
                          f"skills={adaptive_skills} reason={adaptive_reason}", file=sys.stderr)
            except Exception as e:
                print(f"[openclaude-vibemind] selector failed ({e}); falling back to 'code'",
                      file=sys.stderr)
                mcp_profile = "code"
        else:
            mcp_profile = "code"

    mcp_config = resolve_mcp_config(mcp_profile)
    if mcp_config is None:
        print(f"[openclaude-vibemind] MCP profile not found: {mcp_profile}", file=sys.stderr)
        print(f"Available profiles: {', '.join(list_profiles())}", file=sys.stderr)
        return 2

    # Load OpenAI profile env (key + base_url + model + gate)
    profile = load_openclaude_profile()
    env_block = profile.get("env") or {}
    profile_name = (profile.get("profile") or "").strip().lower()
    for key, value in env_block.items():
        if value:
            os.environ[key] = str(value)
    gate = PROFILE_GATES.get(profile_name)
    if gate:
        os.environ[gate] = "1"
    # Strip Anthropic credentials so the OpenAI gate is the only route
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        os.environ.pop(k, None)

    # fungus-search loads a 56k-doc FAISS index + the Qwen embedder before it
    # answers `initialize`; on CPU that exceeds the default MCP startup timeout,
    # so the CLI drops the server and `fungus_search` never appears.
    os.environ.setdefault("MCP_TIMEOUT", "180000")  # ms

    # Isolate openclaude's config from the user's Claude Code config (~/.claude).
    # Otherwise openclaude inherits `enabledPlugins` and the superpowers plugin's
    # SessionStart hook makes the weak backend model greet / chase skills instead
    # of doing the task (verified 2026-06-27). Project .claude/ still loads from cwd.
    if not os.environ.get("CLAUDE_CONFIG_DIR"):
        iso = Path.home() / ".openclaude-config"
        try:
            iso.mkdir(parents=True, exist_ok=True)
            os.environ["CLAUDE_CONFIG_DIR"] = str(iso)
        except OSError as e:
            print(f"[openclaude-vibemind] warning: config isolation failed: {e}", file=sys.stderr)

    # Resolve --model: if the user didn't pass one, use the profile's OPENAI_MODEL
    has_model_arg = any(cleaned[j] == "--model" for j in range(len(cleaned) - 1))
    if not has_model_arg and os.environ.get("OPENAI_MODEL"):
        cleaned.extend(["--model", os.environ["OPENAI_MODEL"]])

    # Inject MCP config (strict — ignore other configs so we get ONLY this set)
    final_args = ["--mcp-config", str(mcp_config), "--strict-mcp-config"] + cleaned

    # If the selector found relevant skills, hint them to openclaude so it
    # actively considers invoking them.
    if adaptive_skills:
        hint_lines = [
            "## Suggested skills for this task",
            "Consider these skills (invoke via /skill-name) — they were "
            "semantically matched to your prompt:",
        ]
        hint_lines.extend(f"  - /{name}" for name in adaptive_skills)
        skill_hint = "\n".join(hint_lines)
        final_args.extend(["--append-system-prompt", skill_hint])

    # Switch to project root so .claude/skills/, CLAUDE.md, etc. auto-discover
    if PROJECT_ROOT.is_dir():
        os.chdir(PROJECT_ROOT)

    if not GLOBAL_OPENCLAUDE_BIN.is_file():
        print(f"[openclaude-vibemind] openclaude not installed at {GLOBAL_OPENCLAUDE_BIN}", file=sys.stderr)
        print("Install: npm install -g @gitlawb/openclaude", file=sys.stderr)
        return 127

    node_exe = "node"
    node_in_npm = GLOBAL_BIN_DIR.parent.parent.parent.parent / "node.exe"
    if node_in_npm.is_file():
        node_exe = str(node_in_npm)

    exec_argv = [node_exe, str(GLOBAL_OPENCLAUDE_BIN), *final_args]
    if os.environ.get("OPENCLAUDE_VIBEMIND_DEBUG"):
        print(f"[openclaude-vibemind] mcp_profile={mcp_profile} cwd={os.getcwd()}", file=sys.stderr)
        print(f"[openclaude-vibemind] adaptive_reason={adaptive_reason}", file=sys.stderr)
        print(f"[openclaude-vibemind] argv: {exec_argv}", file=sys.stderr)

    # If we slurped stdin into a buffer (for adaptive routing), we have to feed
    # it back to openclaude via a subprocess — execvp would hand off the
    # already-consumed stdin which would EOF immediately.
    stdin_buf = os.environ.pop("_OPENCLAUDE_VIBEMIND_STDIN_BUF", None)
    if stdin_buf is not None:
        import subprocess
        proc = subprocess.Popen(exec_argv, stdin=subprocess.PIPE)
        try:
            proc.communicate(input=stdin_buf.encode("utf-8"))
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait(timeout=5)
        return proc.returncode

    os.execvp(node_exe, exec_argv)
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main())
