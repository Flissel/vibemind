"""Bidirectional skill format converter: vibemind <-> anthropic.

Formats:

VIBEMIND (this repo's vibemind-os/skills/<app>/<slug>/SKILL.md):
    ---
    name: hr-<slug>
    description: ...
    app: hr
    requires_approval: true | false
    agents: ["*"]
    inputs: [...]
    expected_state: {description, verification_tool}
    confidence: 0.0-1.0
    attempts: int
    successes: int
    eval_score: 0-100
    last_adjusted: ISO timestamp
    ---
    <markdown body>

ANTHROPIC (anthropics/skills/skills/<slug>/SKILL.md):
    ---
    name: <slug>
    description: "..."
    license: <optional>
    ---
    <markdown body>

OpenClaw extension (vibemind-os/openclaw/extensions/<ext>/skills/<slug>/SKILL.md):
    ---
    name: <slug>
    description: ...
    user-invocable: true | false
    ---
    <markdown body>

Usage:

    # convert one direction
    python scripts/skill_format_bridge.py to-anthropic \\
        --input vibemind-os/skills/hr/mitarbeiter-stammdatenliste/SKILL.md \\
        --output dist/hr-pack/skills/mitarbeiter-stammdatenliste/SKILL.md

    # batch convert a directory
    python scripts/skill_format_bridge.py to-anthropic \\
        --input-dir vibemind-os/skills/hr \\
        --output-dir dist/hr-pack/skills

    # reverse
    python scripts/skill_format_bridge.py to-vibemind \\
        --input <anthropic SKILL.md> --output <vibemind SKILL.md> --app <app>

    # quick listing
    python scripts/skill_format_bridge.py info --input vibemind-os/skills/hr
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ── frontmatter parsing/serialization ────────────────────────────────

def parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Returns (frontmatter_dict, body_str). Accepts both `---`-delimited
    frontmatter and bare-YAML-at-start-of-file (Anthropic-style trims off
    the leading `---` sometimes when raw-fetched from GitHub API).
    """
    text = path.read_text(encoding="utf-8")
    # Strip BOM if present
    text = text.lstrip("﻿")

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"malformed frontmatter in {path}")
        fm = yaml.safe_load(parts[1]) or {}
        body = parts[2].lstrip("\n")
        return fm, body

    # Tolerant mode: yaml-at-start, body starts at first H1 or first blank
    # line followed by non-yaml content.
    lines = text.splitlines(keepends=True)
    yaml_lines: list[str] = []
    body_start_idx = 0
    in_yaml = True
    for i, line in enumerate(lines):
        if not in_yaml:
            break
        stripped = line.rstrip("\n")
        if not stripped:
            # Blank line — peek next: if next line starts with '#' (heading)
            # or doesn't look like yaml (no ': ' at start), body begins
            if i + 1 < len(lines):
                nxt = lines[i + 1].lstrip()
                if nxt.startswith("#") or not (":" in nxt[:50]):
                    body_start_idx = i + 1
                    in_yaml = False
                    continue
            yaml_lines.append(line)
        elif stripped.startswith("#"):
            body_start_idx = i
            in_yaml = False
        else:
            yaml_lines.append(line)
    if not yaml_lines:
        raise ValueError(f"no frontmatter detectable in {path}")
    try:
        fm = yaml.safe_load("".join(yaml_lines)) or {}
    except Exception as e:
        raise ValueError(f"yaml parse error in {path}: {e}")
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter is not a dict in {path}")
    body = "".join(lines[body_start_idx:])
    return fm, body


def write_skill(path: Path, frontmatter: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_yaml = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False,
                              default_flow_style=False).strip()
    path.write_text(f"---\n{fm_yaml}\n---\n\n{body.lstrip()}", encoding="utf-8")


# ── conversion functions ─────────────────────────────────────────────

VIBEMIND_EXTRA_KEYS = {
    "app", "requires_approval", "agents", "inputs",
    "expected_state", "secrets", "confidence", "attempts",
    "successes", "eval_score", "last_adjusted", "trigger",
}


def to_anthropic(fm: dict, body: str, license_text: str | None = None) -> tuple[dict, str]:
    """Convert vibemind/openclaw frontmatter to anthropic-minimal format.

    Strategy:
      - Keep name (strip 'hr-' / 'roarboot-' prefix if present)
      - Keep description
      - Stuff vibemind-specific keys into a `metadata` block (PinchBench-style)
        so info isn't lost
      - Add `license` if provided
    """
    name = fm.get("name", "")
    # Normalize name: strip common prefixes for cleaner public-facing slug
    for prefix in ("hr-", "roarboot-", "rowboat-", "vibemind-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    desc = fm.get("description", "")
    if isinstance(desc, str) and len(desc) > 1024:
        desc = desc[:1020] + "..."

    out_fm: dict[str, Any] = {
        "name": name,
        "description": desc,
    }

    # Collect vibemind-specific metadata under `metadata` (only non-trivial)
    metadata: dict[str, Any] = {}
    for k in VIBEMIND_EXTRA_KEYS:
        if k in fm and fm[k] not in (None, "", [], {}):
            metadata[k] = fm[k]
    if metadata:
        # Add source-pack hint
        metadata.setdefault("source_pack", "vibemind/hr")
        out_fm["metadata"] = metadata

    if license_text:
        out_fm["license"] = license_text

    return out_fm, body


def to_vibemind(fm: dict, body: str, app: str = "imported") -> tuple[dict, str]:
    """Convert anthropic/openclaw frontmatter to vibemind format.

    Strategy:
      - name gets prefixed with `<app>-` if not already
      - description preserved
      - Defaults filled for vibemind fields:
          requires_approval: True (safe default)
          agents: ["*"]
          confidence: 1.0 (assume the import is good)
          attempts: 0, successes: 0 (fresh)
          last_adjusted: now
      - If anthropic format had `metadata` (PinchBench-style), restore
        any known vibemind keys from it
    """
    name = fm.get("name", "")
    if not name.startswith(f"{app}-"):
        name = f"{app}-{name}"

    out_fm: dict[str, Any] = {
        "name": name,
        "description": fm.get("description", ""),
        "app": app,
        "requires_approval": True,
        "agents": ["*"],
        "inputs": [],
        "expected_state": {
            "description": "Imported skill — behavior matches source repo",
            "verification_tool": "none",
        },
        "confidence": 1.0,
        "attempts": 0,
        "successes": 0,
        "last_adjusted": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # If the source had a metadata block with vibemind-keys (round-trip case),
    # restore them so we get a lossless reverse conversion
    md = fm.get("metadata") or {}
    if isinstance(md, dict):
        for k in VIBEMIND_EXTRA_KEYS:
            if k in md:
                out_fm[k] = md[k]

    return out_fm, body


def to_openclaw(fm: dict, body: str, user_invocable: bool = False) -> tuple[dict, str]:
    """Convert to OpenClaw extension format (minimal + user-invocable flag)."""
    name = fm.get("name", "")
    for prefix in ("hr-", "roarboot-", "rowboat-", "vibemind-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    out_fm = {
        "name": name,
        "description": fm.get("description", ""),
        "user-invocable": user_invocable,
    }
    return out_fm, body


# ── batch operations ─────────────────────────────────────────────────

def batch_convert(input_dir: Path, output_dir: Path, direction: str, **kwargs) -> dict:
    """Walk input_dir, convert every SKILL.md, write into output_dir.

    Returns {converted: int, skipped: int, errors: [...]}.
    """
    stats = {"converted": 0, "skipped": 0, "errors": []}
    for skill_md in sorted(input_dir.rglob("SKILL.md")):
        try:
            fm, body = parse_frontmatter(skill_md)
        except Exception as e:
            stats["errors"].append({"path": str(skill_md), "error": str(e)})
            continue
        if direction == "to-anthropic":
            out_fm, out_body = to_anthropic(fm, body, license_text=kwargs.get("license"))
        elif direction == "to-vibemind":
            out_fm, out_body = to_vibemind(fm, body, app=kwargs.get("app", "imported"))
        elif direction == "to-openclaw":
            out_fm, out_body = to_openclaw(fm, body, user_invocable=kwargs.get("user_invocable", False))
        else:
            stats["errors"].append({"path": str(skill_md), "error": f"unknown direction {direction}"})
            continue

        # Use the new name to build output path
        out_slug = out_fm["name"]
        # Strip any `<app>-` prefix back for folder name when going to anthropic
        if direction == "to-anthropic":
            for prefix in ("hr-", "roarboot-", "rowboat-", "vibemind-"):
                if out_slug.startswith(prefix):
                    out_slug = out_slug[len(prefix):]
                    break
        out_path = output_dir / out_slug / "SKILL.md"
        write_skill(out_path, out_fm, out_body)
        stats["converted"] += 1
        print(f"  [OK] {skill_md.parent.name} -> {out_path}")
    return stats


# ── info command ─────────────────────────────────────────────────────

def detect_format(fm: dict) -> str:
    if any(k in fm for k in VIBEMIND_EXTRA_KEYS):
        return "vibemind"
    if "user-invocable" in fm:
        return "openclaw"
    if "metadata" in fm and isinstance(fm["metadata"], dict):
        return "anthropic-with-metadata"
    return "anthropic"


def cmd_info(path: Path) -> int:
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.rglob("SKILL.md"))
    print(f"Found {len(files)} SKILL.md file(s) in {path}")
    print()
    print(f"{'format':<26} {'name':<45} {'path'}")
    print("-" * 100)
    for f in files:
        try:
            fm, _ = parse_frontmatter(f)
        except Exception as e:
            print(f"{'<error>':<26} {f.name:<45} {f.parent.name} ({e})")
            continue
        fmt = detect_format(fm)
        name = fm.get("name", "?")
        print(f"{fmt:<26} {name:<45} {f.parent.name}")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    for cmd_name in ("to-anthropic", "to-vibemind", "to-openclaw"):
        p = sub.add_parser(cmd_name)
        p.add_argument("--input", type=Path)
        p.add_argument("--input-dir", type=Path)
        p.add_argument("--output", type=Path)
        p.add_argument("--output-dir", type=Path)
        if cmd_name == "to-vibemind":
            p.add_argument("--app", default="imported")
        if cmd_name == "to-anthropic":
            p.add_argument("--license", default=None)
        if cmd_name == "to-openclaw":
            p.add_argument("--user-invocable", action="store_true")

    info = sub.add_parser("info")
    info.add_argument("--input", type=Path, required=True)

    args = parser.parse_args()

    if args.cmd == "info":
        return cmd_info(args.input)

    direction = args.cmd

    # Single-file mode
    if args.input and args.output:
        fm, body = parse_frontmatter(args.input)
        kw = {}
        if direction == "to-vibemind":
            kw["app"] = args.app
        elif direction == "to-anthropic":
            kw["license_text"] = args.license
        elif direction == "to-openclaw":
            kw["user_invocable"] = args.user_invocable

        converter = {"to-anthropic": to_anthropic,
                     "to-vibemind": to_vibemind,
                     "to-openclaw": to_openclaw}[direction]
        out_fm, out_body = converter(fm, body, **kw)
        write_skill(args.output, out_fm, out_body)
        print(f"converted: {args.input} -> {args.output}")
        print(f"  detected: {detect_format(fm)} -> {direction.replace('to-','')}")
        print(f"  name: {fm.get('name')} -> {out_fm['name']}")
        return 0

    # Batch mode
    if args.input_dir and args.output_dir:
        kw = {}
        if direction == "to-vibemind":
            kw["app"] = args.app
        elif direction == "to-anthropic":
            kw["license"] = args.license
        elif direction == "to-openclaw":
            kw["user_invocable"] = args.user_invocable

        stats = batch_convert(args.input_dir, args.output_dir, direction, **kw)
        print()
        print(f"DONE: converted={stats['converted']}, errors={len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"  ERROR: {err}")
        return 0 if not stats["errors"] else 1

    parser.error("provide either --input+--output or --input-dir+--output-dir")
    return 2


if __name__ == "__main__":
    sys.exit(main())
