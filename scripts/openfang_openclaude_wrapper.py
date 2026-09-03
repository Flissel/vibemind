"""OpenFang -> OpenClaude bridge wrapper.

OpenFang's `claude_code` driver spawns this script (via the `.cmd` shim) instead
of openclaude directly. We do two things openclaude's stock entry point
doesn't:

1. Load the OpenAI provider profile (priority: project .env → legacy
   .openclaude-profile.json → already-set process env wins above both) and
   inject `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` into the env.
   OpenFang strips these by default (treats them as cross-provider secrets),
   so we have to re-inject them here, after the strip.
2. Exec the global openclaude entry point with stdin still attached so the
   patched OpenFang driver can pump the prompt via `--input-format text`.

Profile resolution lives in scripts/_openclaude_profile.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Local helper — single source of truth for profile resolution.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _openclaude_profile import load_profile as _load_profile  # noqa: E402


GLOBAL_BIN_DIR = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "@gitlawb" / "openclaude" / "bin"
GLOBAL_OPENCLAUDE_BIN = GLOBAL_BIN_DIR / "openclaude"

# Default project root — openclaude needs to start here so that .claude/skills/,
# .mcp.json, and CLAUDE.md are discovered. OpenFang spawns the wrapper from its
# own cwd (target/release/), where none of that exists. Override via env if you
# want to point at a different project.
DEFAULT_PROJECT_CWD = Path("C:/Users/User/Desktop/Vibemind_V1")


def load_profile() -> dict:
    return _load_profile(global_bin_dir=GLOBAL_BIN_DIR)


PROFILE_GATES = {
    "openai": "CLAUDE_CODE_USE_OPENAI",
    "ollama": "CLAUDE_CODE_USE_OPENAI",  # ollama routes through OpenAI-compat
    "gemini": "CLAUDE_CODE_USE_GEMINI",
    "codex": "CLAUDE_CODE_USE_OPENAI",
}


def main() -> int:
    profile = load_profile()
    env_block = profile.get("env") or {}
    profile_name = (profile.get("profile") or "").strip().lower()

    # Inject profile env. Profile values always win — we override inherited
    # env because parents often have OPENAI_* set for other tools (e.g.
    # OpenRouter via OPENAI_API_KEY/MODEL pointing at OpenRouter), and
    # mixing those into openclaude breaks routing.
    for key, value in env_block.items():
        if value:
            os.environ[key] = str(value)

    # Flip the provider gate so openclaude actually routes to the chosen
    # provider instead of falling back to Anthropic.
    gate = PROFILE_GATES.get(profile_name)
    if gate and not os.environ.get(gate):
        os.environ[gate] = "1"

    # Strip Anthropic credentials so the gate is the only thing in play —
    # otherwise the SDK may try Anthropic auth first.
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"):
        os.environ.pop(k, None)

    # fungus-search (code/full profile) loads a 56k-doc FAISS index + the Qwen
    # embedder before it answers `initialize` — on CPU that is well past the
    # default MCP startup timeout, so the CLI drops the server and the coder
    # never sees `fungus_search`. Give MCP servers room to boot.
    os.environ.setdefault("MCP_TIMEOUT", "180000")  # ms

    # Isolate openclaude's config from the *user's* Claude Code config
    # (~/.claude). Without this openclaude inherits `enabledPlugins`, and the
    # superpowers plugin's SessionStart hook ("invoke skills before ANY
    # response") makes the weak backend model greet / chase skills instead of
    # executing the task — it never reaches its tools (verified 2026-06-27:
    # baseline greeted, CLAUDE_CONFIG_DIR-isolated it actually ran tools).
    # Project-level .claude/ (skills, CLAUDE.md) still loads from the cwd.
    if not os.environ.get("CLAUDE_CONFIG_DIR"):
        iso = Path.home() / ".openclaude-config"
        try:
            iso.mkdir(parents=True, exist_ok=True)
            os.environ["CLAUDE_CONFIG_DIR"] = str(iso)
        except OSError as e:
            print(f"[wrapper] warning: could not isolate CLAUDE_CONFIG_DIR: {e}", file=sys.stderr)

    # Find node + openclaude entry point.
    if not GLOBAL_OPENCLAUDE_BIN.is_file():
        print(
            f"[wrapper] openclaude global install not found at {GLOBAL_OPENCLAUDE_BIN}. "
            f"Install: npm install -g @gitlawb/openclaude",
            file=sys.stderr,
        )
        return 127

    # Override the model arg with the profile's OPENAI_MODEL when we're in
    # OpenAI mode — OpenFang passes through Anthropic model IDs (e.g.
    # `claude-sonnet-4-20250514`) which the OpenAI API rejects with a 404.
    forwarded_argv = list(sys.argv[1:])

    # Inject the post-edit syntax-verification settings (PostToolUse hook) so a
    # weak backend model cannot silently corrupt source files. Project-agnostic:
    # works no matter which cwd the resolver picked. Skip if caller already
    # passed --settings (don't clobber an explicit override).
    _verify_settings = (
        Path(__file__).resolve().parent.parent
        / ".claude" / "openclaude-verify-settings.json"
    )
    if "--settings" not in forwarded_argv and _verify_settings.is_file():
        forwarded_argv = ["--settings", str(_verify_settings)] + forwarded_argv

    target_model = os.environ.get("OPENAI_MODEL")

    if os.environ.get("OPENFANG_OPENCLAUDE_DEBUG"):
        debug_path = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaude_wrapper.log"
        try:
            with debug_path.open("a", encoding="utf-8") as fh:
                fh.write(f"--- {os.getpid()} profile={profile_name} target_model={target_model}\n")
                fh.write(f"argv_in: {forwarded_argv}\n")
        except Exception:
            pass
    if target_model and profile_name in {"openai", "ollama", "codex"}:
        i = 0
        replaced = False
        while i < len(forwarded_argv):
            if forwarded_argv[i] == "--model" and i + 1 < len(forwarded_argv):
                forwarded_argv[i + 1] = target_model
                replaced = True
                break
            i += 1
        if not replaced:
            forwarded_argv.extend(["--model", target_model])

    # ---- Project-Resolver (per-call cwd override) -------------------------
    # If the user's latest turn says "in <projekt-alias>: ...", look up the
    # project's code_path in .rowboat/knowledge/Coding-Projects/ manifests and
    # cwd into that repo. Falls back to env override / default Vibemind_V1.
    #
    # We need to PEEK at stdin to do this, but openclaude consumes stdin via
    # --input-format text below. So we slurp the whole stdin buffer here and
    # later re-feed it to openclaude as bytes.
    stdin_buf: bytes | None = None
    resolved_project: dict | None = None
    if not sys.stdin.isatty():
        try:
            stdin_buf = sys.stdin.buffer.read()
        except Exception:
            stdin_buf = None
        if stdin_buf:
            try:
                resolver_dir = Path(os.environ.get("OPENFANG_OPENCLAUDE_CWD") or str(DEFAULT_PROJECT_CWD)) / "scripts"
                sys.path.insert(0, str(resolver_dir))
                from project_resolver import resolve as resolve_project  # type: ignore
                full_prompt = stdin_buf.decode("utf-8", errors="replace")
                last_user_idx = full_prompt.rfind("[User]")
                routing_prompt = full_prompt[last_user_idx + len("[User]"):] if last_user_idx >= 0 else full_prompt
                resolved_project = resolve_project(routing_prompt.strip())
            except Exception as e:
                print(f"[wrapper] project_resolver failed ({e}); using default cwd", file=sys.stderr)

    # Switch cwd: explicit project (from resolver) > env override > default
    if resolved_project and Path(resolved_project["code_path"]).is_dir():
        target_cwd_str = resolved_project["code_path"]
    else:
        target_cwd_str = os.environ.get("OPENFANG_OPENCLAUDE_CWD") or str(DEFAULT_PROJECT_CWD)
    target_cwd = Path(target_cwd_str)
    if target_cwd.is_dir():
        try:
            os.chdir(target_cwd)
        except OSError as e:
            print(f"[wrapper] warning: failed to chdir to {target_cwd}: {e}", file=sys.stderr)
    else:
        print(f"[wrapper] warning: project cwd {target_cwd} does not exist, staying in {os.getcwd()}", file=sys.stderr)

    # ---- Adaptive MCP-profile selection -----------------------------------
    # stdin was already slurped above (project-resolver step). Reuse it.
    adaptive_profile: str | None = None
    adaptive_skills: list[str] = []
    if stdin_buf and "--mcp-config" not in forwarded_argv:
            try:
                # MCP-profile dir always lives in Vibemind_V1, NOT in resolved
                # project repo. Resolver target_cwd may be a fresh empty repo.
                vibemind_root = DEFAULT_PROJECT_CWD
                sys.path.insert(0, str(vibemind_root / "scripts"))
                from mcp_profile_selector import select as select_profile  # type: ignore
                # Use only the LATEST user turn for routing, not the full
                # conversation history. OpenFang sends `[User]...\n\n[Assistant]...`
                # turn-blocks; old turns about Excel/skills/etc. pollute the
                # heuristic and force-route to `desktop` for unrelated tasks.
                full_prompt = stdin_buf.decode("utf-8", errors="replace")
                last_user_idx = full_prompt.rfind("[User]")
                routing_prompt = full_prompt[last_user_idx:] if last_user_idx >= 0 else full_prompt
                result = select_profile(routing_prompt)
                adaptive_profile = result.get("profile")
                adaptive_skills = result.get("skills") or []
                # Floor at `code`: this wrapper only ever serves the coding
                # agent, and `bare` gives it ZERO MCP servers — no codebase
                # search at all. The keyword heuristic drops to `bare` far too
                # easily (e.g. "report the top result's file path" matches the
                # bare rule on "file", while `\bsearch\b` does NOT match inside
                # "fungus_search" — the underscore is a word char). The agent
                # then truthfully answers "no such tool available", or worse,
                # hallucinates a path. A coding agent without code tools is
                # never the right answer.
                if adaptive_profile == "bare":
                    print("[wrapper] selector said 'bare'; upgrading to 'code' "
                          "(coding agent must keep codebase search)", file=sys.stderr)
                    adaptive_profile = "code"
                mcp_profile_dir = vibemind_root / ".claude" / "mcp-profiles"
                if adaptive_profile == "full":
                    mcp_config = vibemind_root / ".mcp.json"
                else:
                    mcp_config = mcp_profile_dir / f"{adaptive_profile}.json"
                if mcp_config.is_file():
                    forwarded_argv = ["--mcp-config", str(mcp_config), "--strict-mcp-config"] + forwarded_argv
                    if adaptive_skills:
                        hint = "## Suggested skills for this task\n" + "\n".join(
                            f"  - /{name}" for name in adaptive_skills
                        )
                        forwarded_argv += ["--append-system-prompt", hint]
                    if os.environ.get("OPENFANG_OPENCLAUDE_DEBUG"):
                        debug_path = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaude_wrapper.log"
                        try:
                            with debug_path.open("a", encoding="utf-8") as fh:
                                fh.write(f"resolved_project: {resolved_project.get('slug') if resolved_project else None} cwd={target_cwd}\n")
                                fh.write(f"adaptive: profile={adaptive_profile} skills={adaptive_skills} reason={result.get('reason')}\n")
                                preview = stdin_buf.decode("utf-8", errors="replace")[:400]
                                fh.write(f"stdin_preview (first 400 chars): {preview!r}\n")
                                fh.write(f"stdin_total_bytes: {len(stdin_buf)}\n")
                        except Exception:
                            pass
            except Exception as e:
                print(f"[wrapper] adaptive selection failed ({e}); using full MCP set", file=sys.stderr)

    # ---- Shared memory injection (hard-fail by design) --------------------
    # Every agent (OpenClaude, brain-coder via OpenFang, Telegram desktop) gets
    # the same persistent memory layer. Profile selectable via env, defaults to
    # "coding" because most OpenFang/OpenClaude invocations are code work.
    mem_profile = os.environ.get("OPENFANG_MEMORY_PROFILE", "coding")
    shared_src = DEFAULT_PROJECT_CWD / "vibemind-os" / "shared" / "src"
    if str(shared_src) not in sys.path:
        sys.path.insert(0, str(shared_src))
    try:
        from vibemind_shared import load_memory  # type: ignore
        mem_block = load_memory(mem_profile)
    except Exception as e:
        print(
            f"[wrapper] FATAL: memory load failed for profile '{mem_profile}': {e}",
            file=sys.stderr,
        )
        sys.exit(2)

    hint_parts = [mem_block]
    if adaptive_skills:
        hint_parts.append(
            "## Suggested skills for this task\n"
            + "\n".join(f"  - /{name}" for name in adaptive_skills)
        )
    # Strip any prior --append-system-prompt (the adaptive block above only adds
    # one when adaptive_skills is non-empty; we now own that arg).
    pruned: list[str] = []
    skip_next = False
    for a in forwarded_argv:
        if skip_next:
            skip_next = False
            continue
        if a == "--append-system-prompt":
            skip_next = True
            continue
        pruned.append(a)
    forwarded_argv = pruned + ["--append-system-prompt", "\n\n".join(hint_parts)]

    if os.environ.get("OPENFANG_OPENCLAUDE_DEBUG"):
        debug_path = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaude_wrapper.log"
        try:
            with debug_path.open("a", encoding="utf-8") as fh:
                fh.write(f"memory_profile={mem_profile} memory_len={len(mem_block)}\n")
        except Exception:
            pass

    # Re-exec via node so stdin stays attached for `--input-format text`.
    node_exe = "node"
    node_in_npm = GLOBAL_BIN_DIR.parent.parent.parent.parent / "node.exe"
    if node_in_npm.is_file():
        node_exe = str(node_in_npm)

    argv = [node_exe, str(GLOBAL_OPENCLAUDE_BIN), *forwarded_argv]

    if os.environ.get("OPENFANG_OPENCLAUDE_DEBUG"):
        try:
            with debug_path.open("a", encoding="utf-8") as fh:
                fh.write(f"argv_out: {forwarded_argv}\n")
                fh.write(f"env OPENAI_API_KEY_SET: {bool(os.environ.get('OPENAI_API_KEY'))}\n")
                fh.write(f"env OPENAI_BASE_URL: {os.environ.get('OPENAI_BASE_URL')}\n")
                fh.write(f"env OPENAI_MODEL: {os.environ.get('OPENAI_MODEL')}\n")
                fh.write(f"env CLAUDE_CODE_USE_OPENAI: {os.environ.get('CLAUDE_CODE_USE_OPENAI')}\n")
        except Exception:
            pass

    # If we slurped stdin during adaptive routing, we have to feed it back to
    # openclaude via subprocess — execvp would hand off the already-consumed
    # stdin (EOF immediately).
    if stdin_buf is not None:
        import subprocess
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE)
        try:
            proc.communicate(input=stdin_buf)
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait(timeout=5)
        return proc.returncode

    # On Windows use os.execvp; child inherits stdin/stdout/stderr.
    os.execvp(node_exe, argv)
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main())
