"""OpenFang -> openclaw bridge wrapper.

OpenFang's `claude_code` driver spawns this script (via the `.cmd` shim) as if
it were a Claude-Code CLI. We translate that into an openclaw embedded-agent
call inside the running `vibemind-openclaw` container:

    docker exec -e OPENAI_API_KEY=<from .env> -e OPENCLAW_DEFAULT_MODEL=<model> \
      vibemind-openclaw node openclaw.mjs agent --local --agent main \
      --message <prompt-from-stdin> --json --timeout <s>

Why this shape (decided in plan k-nnnen-wir-adative-skills-splendid-mochi.md):
  - `--local` runs openclaw's embedded agent — NO gateway pairing / channels
    / device setup needed. This is the only reliably-working entry point.
  - The container's mounted secret (/run/secrets/openai_api_key) is a DEAD key
    (OpenAI returns 401) and OPENCLAW_DEFAULT_MODEL defaults to the
    non-existent `openai/gpt-5.4`. So we inject the known-good key from the
    repo .env (OPENCLAUDE_OPENAI_KEY) and a real model (gpt-4o-mini) via
    `docker exec -e`. Wrapper-local — no container rebuild / secret rotation.
  - OpenFang's claude_code driver was already patched to feed the prompt via
    stdin (see memory project_openclaude_openfang.md). We read stdin, pass it
    to openclaw `--message` as argv. `docker exec` on the Linux container has
    ~2MB ARG_MAX so the Windows 8191-char cmd limit does NOT apply here
    (verified with a 12KB prompt in plan Phase 0b).
  - openclaw `--json` prints diagnostics then a JSON object
    `{"payloads":[{"text":...}], "meta":{...}}`. We extract payloads[0].text
    and write ONLY that to stdout (that's what the claude_code driver expects
    as the assistant response).

Config via env (with sane defaults):
  OPENCLAW_CONTAINER   default "vibemind-openclaw"
  OPENCLAW_AGENT       default "main"
  OPENCLAW_MODEL       default "openai/gpt-4o-mini"
  OPENCLAW_TIMEOUT_S   default 280  (openclaw-side; leave room under OpenFang's)
  OPENCLAW_KEY_ENVVAR  default "OPENCLAUDE_OPENAI_KEY" (.env key name to inject)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

CONTAINER = os.environ.get("OPENCLAW_CONTAINER", "vibemind-openclaw")
OC_AGENT = os.environ.get("OPENCLAW_AGENT", "main")
OC_MODEL = os.environ.get("OPENCLAW_MODEL", "openai/gpt-4o-mini")
OC_TIMEOUT_S = int(os.environ.get("OPENCLAW_TIMEOUT_S", "280"))
KEY_ENVVAR = os.environ.get("OPENCLAW_KEY_ENVVAR", "OPENCLAUDE_OPENAI_KEY")


def _read_env_value(name: str) -> str | None:
    """Read a single KEY=VALUE from the repo .env. No shell expansion."""
    if not ENV_FILE.is_file():
        return None
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == name:
            return v.strip().strip('"').strip("'")
    return None


def _extract_text(raw: str) -> str:
    """openclaw prints diagnostics then a JSON blob. Find the last top-level
    JSON object and pull payloads[0].text. Fall back to raw on any failure."""
    # The JSON object is the final {...} block; scan from the last newline-{ .
    start = raw.rfind("\n{")
    candidates = []
    if start >= 0:
        candidates.append(raw[start + 1:])
    candidates.append(raw[raw.find("{"):] if "{" in raw else raw)
    for cand in candidates:
        try:
            d = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        payloads = d.get("payloads")
        if isinstance(payloads, list) and payloads:
            txt = payloads[0].get("text")
            if isinstance(txt, str) and txt.strip():
                return txt
        # Some openclaw paths may put it elsewhere; deep-search 'text'.
        found: list[str] = []

        def _walk(o: object) -> None:
            if isinstance(o, dict):
                for kk, vv in o.items():
                    if kk == "text" and isinstance(vv, str) and vv.strip():
                        found.append(vv)
                    _walk(vv)
            elif isinstance(o, list):
                for vv in o:
                    _walk(vv)

        _walk(d)
        if found:
            return found[-1]
    # Nothing parseable — return raw so the caller at least sees something.
    return raw.strip()


def main() -> int:
    # OpenFang's patched claude_code driver pipes the prompt via stdin.
    try:
        prompt = sys.stdin.read()
    except Exception:
        prompt = ""
    prompt = (prompt or "").strip()
    if not prompt:
        print("[openclaw-wrapper] empty prompt on stdin", file=sys.stderr)
        return 2

    # OpenFang's claude_code driver also passes flags (-p, --output-format,
    # --system-prompt-file, --model, ...). We ignore all of them — openclaw
    # has its own CLI surface. The only thing we need is the prompt text.
    # (A --system-prompt-file, if present, is folded into the message so the
    # agent still gets that context.)
    sys_prompt = ""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--system-prompt-file" and i + 1 < len(argv):
            try:
                sys_prompt = Path(argv[i + 1]).read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                sys_prompt = ""
            break
    message = f"{sys_prompt}\n\n{prompt}" if sys_prompt else prompt

    good_key = _read_env_value(KEY_ENVVAR) or os.environ.get("OPENAI_API_KEY", "")
    if not good_key:
        print(f"[openclaw-wrapper] no key found ({KEY_ENVVAR} in .env / OPENAI_API_KEY env)",
              file=sys.stderr)
        return 2

    cmd = [
        "docker", "exec",
        "-e", f"OPENAI_API_KEY={good_key}",
        "-e", f"OPENCLAW_DEFAULT_MODEL={OC_MODEL}",
        CONTAINER,
        "node", "openclaw.mjs", "agent",
        "--local", "--agent", OC_AGENT,
        "--message", message,
        "--json", "--timeout", str(OC_TIMEOUT_S),
    ]

    if os.environ.get("OPENFANG_OPENCLAW_DEBUG"):
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaw_wrapper.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(f"--- pid={os.getpid()} model={OC_MODEL} msg_len={len(message)}\n")
                fh.write(f"msg_head={message[:200]!r}\n")
        except Exception:
            pass

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=OC_TIMEOUT_S + 30,
        )
    except subprocess.TimeoutExpired:
        print(f"[openclaw-wrapper] timed out after {OC_TIMEOUT_S + 30}s", file=sys.stderr)
        return 124
    except FileNotFoundError:
        print("[openclaw-wrapper] 'docker' not found on PATH", file=sys.stderr)
        return 127

    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    text = _extract_text(combined)

    if os.environ.get("OPENFANG_OPENCLAW_DEBUG"):
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaw_wrapper.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(f"rc={result.returncode} extracted_len={len(text)}\n")
                fh.write(f"extracted_head={text[:200]!r}\n")
        except Exception:
            pass

    # OpenFang's claude_code driver reads stdout as the assistant response.
    sys.stdout.write(text)
    sys.stdout.flush()
    # openclaw returns non-zero on agent error; surface that so OpenFang can
    # classify it, but we still emitted whatever text we could extract.
    return 0 if text and result.returncode == 0 else (result.returncode or 1)


if __name__ == "__main__":
    sys.exit(main())
