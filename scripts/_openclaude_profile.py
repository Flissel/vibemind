"""Shared profile loader for openclaude wrappers.

Resolution order (first match wins, key by key):
    1. Existing process env (highest priority — explicit override)
    2. .env: OPENCLAUDE_* names (dedicated to this wrapper, so it doesn't
       collide with other tools' OPENAI_* config in the same .env)
    3. .env: regular OPENAI_* names (with OPENAI_API_BASE -> OPENAI_BASE_URL fallback)
    4. .openclaude-profile.json — legacy fallback so older setups keep
       working. We log a deprecation hint when used.

The OPENCLAUDE_* indirection exists because a single .env often serves
multiple tools: one wants OPENAI_API_KEY pointed at OpenAI direct, another
wants it pointed at OpenRouter. Setting OPENCLAUDE_OPENAI_KEY etc. lets
openclaude have its own provider pair without rewriting the shared keys.

Recognised .env keys (any of these works):
    OPENCLAUDE_OPENAI_KEY   | OPENCLAUDE_API_KEY    -> OPENAI_API_KEY
    OPENCLAUDE_BASE_URL     | OPENCLAUDE_API_BASE   -> OPENAI_BASE_URL
    OPENCLAUDE_MODEL                                -> OPENAI_MODEL
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Keys the wrappers actually inject into the child env.
_PROFILE_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
)


def _load_dotenv_file(env_path: Path) -> dict[str, str]:
    """Parse a `KEY=VALUE` file. Skips comments + blank lines. No shell expansion."""
    if not env_path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                out[k] = v
    except OSError:
        return {}
    return out


def _legacy_json_candidates(global_bin_dir: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if env_path := os.environ.get("OPENCLAUDE_PROFILE"):
        candidates.append(Path(env_path))
    candidates.append(PROJECT_ROOT / ".openclaude-profile.json")
    candidates.append(Path.home() / ".openclaude-profile.json")
    if global_bin_dir is not None:
        candidates.append(global_bin_dir.parent / ".openclaude-profile.json")
    return candidates


def _load_legacy_json(global_bin_dir: Path | None) -> dict | None:
    """Read the first existing .openclaude-profile.json. Returns None if none found."""
    for p in _legacy_json_candidates(global_bin_dir):
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    print(
                        f"[openclaude] note: loaded legacy profile from {p}. "
                        f"Move OPENAI_* into {PROJECT_ROOT / '.env'} and delete the JSON "
                        f"to keep the key out of an on-disk JSON.",
                        file=sys.stderr,
                    )
                    return data
            except Exception as e:  # noqa: BLE001
                print(f"[openclaude] warning: failed to parse {p}: {e}", file=sys.stderr)
    return None


def load_profile(global_bin_dir: Path | None = None) -> dict:
    """Return a profile dict shaped like the legacy JSON:

        {"profile": "<name>", "env": {"OPENAI_API_KEY": "...", ...}}

    Always non-None; missing fields just yield an empty env dict.
    """
    env_block: dict[str, str] = {}
    dotenv_vars = _load_dotenv_file(PROJECT_ROOT / ".env")

    # 1. .env — OPENCLAUDE_* dedicated keys win first. These exist so a shared
    #    .env can route openclaude at one provider while leaving OPENAI_* for
    #    other tools' use.
    openclaude_key_aliases = {
        "OPENAI_API_KEY":  ("OPENCLAUDE_OPENAI_KEY", "OPENCLAUDE_API_KEY"),
        "OPENAI_BASE_URL": ("OPENCLAUDE_BASE_URL", "OPENCLAUDE_API_BASE"),
        "OPENAI_MODEL":    ("OPENCLAUDE_MODEL",),
    }
    # Keys filled from a dedicated OPENCLAUDE_* alias are LOCKED: they are an
    # explicit "this is openclaude's provider, regardless of what OPENAI_* the
    # shared .env / inherited process env has for other tools" declaration.
    # Step 3 (process-env override) must not clobber these — otherwise a parent
    # like OpenFang that inherits the repo .env (OPENAI_MODEL=<openrouter model>)
    # leaks the wrong model into openclaude.
    locked_keys: set[str] = set()
    for target, aliases in openclaude_key_aliases.items():
        for alias in aliases:
            if dotenv_vars.get(alias):
                env_block[target] = dotenv_vars[alias]
                locked_keys.add(target)
                break

    # 2. .env — regular OPENAI_* keys (only fill what OPENCLAUDE_* didn't).
    for k in _PROFILE_KEYS:
        if k not in env_block and dotenv_vars.get(k):
            env_block[k] = dotenv_vars[k]
    # Legacy convention: OPENAI_API_BASE -> OPENAI_BASE_URL.
    if "OPENAI_BASE_URL" not in env_block and dotenv_vars.get("OPENAI_API_BASE"):
        env_block["OPENAI_BASE_URL"] = dotenv_vars["OPENAI_API_BASE"]

    # 2. .openclaude-profile.json (legacy) — only fills keys still missing.
    profile_name = ""
    legacy = _load_legacy_json(global_bin_dir)
    if legacy:
        profile_name = (legacy.get("profile") or "").strip()
        for k, v in (legacy.get("env") or {}).items():
            if k in _PROFILE_KEYS and v and not env_block.get(k):
                env_block[k] = str(v)

    # 3. Existing process env beats everything — let an explicit shell override
    #    win — EXCEPT keys locked by a dedicated OPENCLAUDE_* alias above.
    #    Those are a deliberate "openclaude uses THIS provider" statement and
    #    must survive an inherited shared .env / parent process env.
    for k in _PROFILE_KEYS:
        if k in locked_keys:
            continue
        if os.environ.get(k):
            env_block[k] = os.environ[k]

    # Infer profile name from base URL when not explicitly set.
    if not profile_name:
        base = (env_block.get("OPENAI_BASE_URL") or "").lower()
        if "openrouter" in base:
            profile_name = "openrouter"
        elif "localhost" in base or "127.0.0.1" in base or "11434" in base:
            profile_name = "ollama"
        elif env_block.get("OPENAI_API_KEY"):
            profile_name = "openai"

    return {"profile": profile_name, "env": env_block}
