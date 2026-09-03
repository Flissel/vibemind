"""Apply a named MCP profile to the project-root `.mcp.json`.

The profiles in `.claude/mcp-profiles/` (`bare`/`code`/`desktop`, and `full`
if present) are normally selected per-prompt by `mcp_profile_selector.py` for
the *openclaude wrapper*. A plain interactive Claude Code session does NOT go
through that wrapper, so it never picks up a profile — it only reads the
project-root `.mcp.json` at startup.

This script bridges that gap: it copies a chosen profile to
`<repo>/.mcp.json` so the next Claude Code launch registers those servers.
Claude Code reads `.mcp.json` only at startup and prompts for trust on first
load, so a session restart + approval is required after applying.

Usage::

    python scripts/mcp_profile_apply.py code        # activate fungus-search
    python scripts/mcp_profile_apply.py desktop     # desktop-automation stack
    python scripts/mcp_profile_apply.py bare        # zero project servers
    python scripts/mcp_profile_apply.py --list      # list available profiles
    python scripts/mcp_profile_apply.py --show      # show currently-active .mcp.json
    python scripts/mcp_profile_apply.py --restore   # roll back to the last backup

The previous `.mcp.json` (if any) is saved to `.mcp.json.bak` before writing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILES_DIR = ROOT / ".claude" / "mcp-profiles"
TARGET = ROOT / ".mcp.json"
BACKUP = ROOT / ".mcp.json.bak"


def available_profiles() -> dict[str, Path]:
    if not PROFILES_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(PROFILES_DIR.glob("*.json"))}


def _server_names(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return sorted((data.get("mcpServers") or {}).keys())
    except Exception as e:  # noqa: BLE001 - report, don't crash listing
        return [f"<unreadable: {e}>"]


def _profile_meta(path: Path) -> dict:
    """Return profile meta (use_when, requires_stack, optional_stack)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "comment": data.get("_comment", ""),
            "use_when": data.get("_use_when", []),
            "requires_stack": data.get("_requires_stack", []),
            "optional_stack": data.get("_optional_stack", []),
            "notes": data.get("_notes", ""),
        }
    except Exception:
        return {}


def _check_port(host: str, port: int, timeout: float = 0.4) -> bool:
    """TCP connect probe — True if something is listening, False otherwise."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _parse_stack_entry(entry: str) -> tuple[str, int, str]:
    """Parse a `_requires_stack` / `_optional_stack` entry.

    Accepts formats:
      "brain-core:5000"
      "openfang:4200 (some comment)"

    Returns (label, port, comment). label is the bit before the colon.
    """
    import re
    m = re.match(r"^([\w.-]+):(\d+)(?:\s*\((.*)\))?\s*$", entry)
    if not m:
        return (entry, 0, "")
    return (m.group(1), int(m.group(2)), m.group(3) or "")


def _preflight(meta: dict) -> bool:
    """Probe required + optional stack ports. Returns False iff a REQUIRED port is down."""
    required = meta.get("requires_stack", [])
    optional = meta.get("optional_stack", [])
    if not required and not optional:
        return True  # nothing to check
    print("\nPre-flight stack check:")
    all_required_ok = True
    for entry in required:
        label, port, _ = _parse_stack_entry(entry)
        ok = _check_port("127.0.0.1", port) if port else True
        mark = "OK  " if ok else "DOWN"
        print(f"  [REQ] {label:<20} :{port:<5} {mark}")
        if not ok:
            all_required_ok = False
    for entry in optional:
        label, port, note = _parse_stack_entry(entry)
        ok = _check_port("127.0.0.1", port) if port else True
        mark = "OK  " if ok else "down"
        suffix = f"  ({note})" if note else ""
        print(f"  [opt] {label:<20} :{port:<5} {mark}{suffix}")
    return all_required_ok


def cmd_list() -> int:
    profiles = available_profiles()
    if not profiles:
        print(f"No profiles found in {PROFILES_DIR}", file=sys.stderr)
        return 1
    active_servers = set(_server_names(TARGET)) if TARGET.exists() else None
    print(f"Profiles in {PROFILES_DIR}:")
    print()
    for name, path in profiles.items():
        servers = _server_names(path)
        meta = _profile_meta(path)
        # Mark the currently-active profile (best-effort: same server set as .mcp.json)
        active_marker = ""
        if active_servers is not None and set(servers) == active_servers:
            active_marker = "  [ACTIVE]"
        label = ", ".join(servers) if servers else "(no servers)"
        print(f"  {name:<10} {active_marker}")
        if meta.get("comment"):
            # Trim long comments to first sentence for the list view
            first_sentence = meta["comment"].split(".")[0] + "."
            print(f"    {first_sentence}")
        print(f"    servers: {label}")
        if meta.get("requires_stack"):
            print(f"    requires: {', '.join(meta['requires_stack'])}")
        print()
    print("Apply: python scripts/mcp_profile_apply.py <name>")
    print("Show:  python scripts/mcp_profile_apply.py --show")
    return 0


def cmd_show() -> int:
    if not TARGET.exists():
        print(f"No active .mcp.json at {TARGET}")
        print("=> no project-scoped MCP servers load (effectively 'bare').")
        return 0
    print(f"Active {TARGET}:")
    print(f"  servers: {', '.join(_server_names(TARGET)) or '(none)'}")
    print("\n--- content ---")
    print(TARGET.read_text(encoding="utf-8"))
    return 0


def cmd_coverage() -> int:
    """Show which mcp_server*.py implementations in the repo are NOT in any profile.

    Coverage = the set of `script-path -> profile-name` mappings we believe are
    registered. Many mcp_server.py files in the repo are not direct Claude-Code
    targets: they're aggregated via the Brain MCP-proxy (`mcp__brain-core__*`)
    or are submodule duplicates under spaces/desktop/, spaces/coding/. This
    report lists what's actually wired into a profile vs what's loose.
    """
    import os

    # Collect every server entry across all profiles, keyed by the script path
    # they point to (so we can match against implementations on disk).
    profile_scripts: dict[str, list[tuple[str, str]]] = {}  # script_path -> [(profile, server_name)]
    profile_names: dict[str, list[str]] = {}                # script_path -> [server_names]
    profiles = available_profiles()
    for prof_name, prof_path in profiles.items():
        try:
            data = json.loads(prof_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for sname, sinfo in (data.get("mcpServers") or {}).items():
            args = sinfo.get("args", [])
            # Track the most recent `cd /d <dir>` so relative .py paths resolve
            cwd_hint = None
            script: str | None = None
            for i, a in enumerate(args):
                if not isinstance(a, str):
                    continue
                # `cmd /c cd /d <abs-dir>` pattern (fungus-search) — sniff cwd
                if a.lower() in ("cd", "/d") and i + 1 < len(args):
                    nxt = args[i + 1]
                    if isinstance(nxt, str) and (nxt.endswith("/") or nxt.endswith("\\") or len(nxt) > 3):
                        cwd_hint = nxt
                if a.endswith(".py"):
                    script = a
                    break
            if not script:
                continue
            if "\\" not in script and "/" not in script and cwd_hint:
                # Relative script + sniffed cwd → reconstruct absolute path
                norm = (cwd_hint.rstrip("\\/") + "/" + script).replace("\\", "/").lower()
            else:
                norm = script.replace("\\", "/").lower()
            profile_scripts.setdefault(norm, []).append((prof_name, sname))
            profile_names.setdefault(norm, []).append(sname)

    # Walk the repo for all mcp_server*.py
    SKIP_DIRS = {".git", "node_modules", "target", "__pycache__", ".venv", ".venv312", "dist", "build"}
    all_impls: list[str] = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.startswith("mcp_server") and f.endswith(".py"):
                rel = str((Path(root) / f).resolve()).replace("\\", "/").lower()
                all_impls.append(rel)

    # De-dupe + drop submodule duplicates
    def is_dup(p: str) -> bool:
        return (
            "worktrees" in p
            or "spaces/desktop/automation_ui" in p
            or "spaces/coding/coding_engine" in p
            or "voice/python/spaces/" in p  # duplicate of spaces/<x>/ at repo top
        )

    impls = sorted({p for p in all_impls if not is_dup(p)})

    # Normalise profile script paths: strip leading "c:/users/..." absolute prefix
    # so we can match by relative repo-path. The profiles use absolute paths;
    # the walk produces lowercase absolute paths too — same shape, simple match.
    covered: list[tuple[str, list[str]]] = []
    uncovered: list[str] = []
    for impl in impls:
        names: list[str] = []
        for prof_path, entries in profile_names.items():
            if impl == prof_path:  # exact path match — no false-positives
                names.extend(entries)
        if names:
            covered.append((impl, sorted(set(names))))
        else:
            uncovered.append(impl)

    repo_str = str(ROOT).replace("\\", "/").lower()

    def short(p: str) -> str:
        return p.replace(repo_str + "/", "")

    print(f"MCP coverage report")
    print(f"  profiles dir : {PROFILES_DIR}")
    print(f"  repo root    : {ROOT}")
    print()
    print(f"COVERED ({len(covered)}):")
    for impl, names in covered:
        print(f"  [{', '.join(names):<24}] {short(impl)}")

    print()
    print(f"NOT IN ANY PROFILE ({len(uncovered)}):")
    print("  (most of these are Brain-internal — reachable via mcp__brain-core__*)")
    print()
    from collections import defaultdict
    groups: dict[str, list[str]] = defaultdict(list)
    for p in uncovered:
        rel = short(p)
        # Group by top-level dir under repo root
        parts = rel.split("/")
        top = parts[1] if rel.startswith("vibemind-os/") and len(parts) > 1 else parts[0]
        groups[top].append(rel)
    for top in sorted(groups):
        print(f"  {top}/")
        for r in groups[top]:
            print(f"    {r}")
    print()
    print(f"Summary: {len(covered)} covered / {len(uncovered)} loose / {len(impls)} total")
    return 0


def cmd_restore() -> int:
    if not BACKUP.exists():
        print(f"No backup at {BACKUP} to restore.", file=sys.stderr)
        return 1
    shutil.copy2(BACKUP, TARGET)
    print(f"Restored {TARGET} from {BACKUP}")
    print(f"  servers now: {', '.join(_server_names(TARGET)) or '(none)'}")
    print("\nRestart Claude Code for the change to take effect.")
    return 0


def cmd_apply(name: str) -> int:
    profiles = available_profiles()
    if name not in profiles:
        print(
            f"Unknown profile '{name}'. Available: {', '.join(profiles) or '(none)'}",
            file=sys.stderr,
        )
        return 2

    src = profiles[name]
    # Validate the profile is well-formed JSON before touching the target.
    try:
        json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Profile '{name}' is not valid JSON: {e}", file=sys.stderr)
        return 1

    meta = _profile_meta(src)
    if meta.get("comment"):
        print(f"\n{meta['comment']}\n")

    # Pre-flight: probe required + optional stack ports. Required failure does
    # not abort (the user may want to apply the profile and start the stack
    # afterwards), but it surfaces the issue before the restart prompt below.
    required_ok = _preflight(meta)
    if not required_ok:
        print()
        print("  ⚠  Some REQUIRED stack services are not listening.")
        print("     Profile will still be applied, but the affected MCP servers will")
        print("     fail their tool calls until those services come up.")
        print("     Bring the stack up with: scripts/vibemind-start.ps1")

    if TARGET.exists():
        shutil.copy2(TARGET, BACKUP)
        print(f"\nBacked up existing .mcp.json -> {BACKUP}")
    else:
        print()

    shutil.copy2(src, TARGET)
    servers = _server_names(TARGET)
    print(f"Applied profile '{name}' -> {TARGET}")
    print(f"  servers: {', '.join(servers) or '(none)'}")

    if meta.get("notes"):
        print(f"\nNotes: {meta['notes']}")

    print("\nNext steps:")
    print("  1. Restart the Claude Code session (it reads .mcp.json only at startup).")
    print("  2. Approve the trust prompt for the new servers when it appears.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="?", help="profile name to apply")
    parser.add_argument("--list", action="store_true", help="list available profiles")
    parser.add_argument("--show", action="store_true", help="show active .mcp.json")
    parser.add_argument(
        "--restore", action="store_true", help="restore the last .mcp.json.bak"
    )
    parser.add_argument(
        "--coverage", action="store_true",
        help="show which mcp_server*.py files in the repo are NOT in any profile"
    )
    args = parser.parse_args()

    if args.list:
        return cmd_list()
    if args.show:
        return cmd_show()
    if args.restore:
        return cmd_restore()
    if args.coverage:
        return cmd_coverage()
    if not args.profile:
        parser.print_help()
        return 2
    return cmd_apply(args.profile)


if __name__ == "__main__":
    sys.exit(main())
