"""OpenFang -> openclaw VISIBLE-browser bridge wrapper.

Sibling of `openfang_openclaw_wrapper.py`. That one runs the openclaw embedded
agent HEADLESS inside the Docker container (`docker exec ... agent --local`).
THIS one drives a **visible Chrome window on the host PC** by routing the
agent turn through the *native* openclaw Gateway:

    OPENCLAW_GATEWAY_URL=ws://127.0.0.1:18793 \
    OPENCLAW_GATEWAY_TOKEN=<gateway.auth.token from native config> \
      openclaw agent --agent main --message <prompt-from-stdin> \
      --json --timeout <s>

Why this shape (decided + proven in plan
k-nnnen-wir-adative-skills-splendid-mochi.md, session 2026-05-19):

  - The native openclaw is already globally installed on Windows
    (`openclaw` npm-global, config C:\\Users\\User\\.openclaw\\openclaw.json).
    Unlike the container's `--local` path, the native Gateway runs a real
    **Browser Control Service** (loopback :18795) — that service is what the
    `--local` path lacks and is why headless-only / no live view there.
  - `openclaw agent` (Gateway mode, NO --local) gets the `browser` tool and
    drives the Gateway's browser. With `browser.defaultProfile: "openclaw"`
    that is a managed, **visible** Chrome window (no extension needed).
  - `openclaw agent` has no --url/--token flags; the target Gateway is chosen
    via env vars OPENCLAW_GATEWAY_URL + OPENCLAW_GATEWAY_TOKEN (verified).
  - CRITICAL native-config requirements (set once, see plan / memory):
      * gateway.port = 18793  (NOT 18789 — that's the Docker container; the
        agent's internal browser-tool call resolves its target from
        config.gateway.port, so a --port FLAG override is not enough — it
        must be the config value or the browser tool hits the container's
        gateway and fails `token mismatch`).
      * gateway.remote.{url,token} aligned with gateway.auth.token.
      * browser.defaultProfile = "openclaw" (else default "chrome" wants a
        Chrome extension attached → fails).
      * agents.defaults.model.primary = openai/gpt-4o-mini + env.OPENAI_API_KEY
        (the native Anthropic OAuth profile is out-of-usage).
    This wrapper does NOT mutate config — it only reads gateway.auth.token
    and assumes the Gateway is already running with the above config (the
    "OpenClaw Gateway" scheduled task / persistence handles that).
  - openclaw `--json` prints diagnostics then a JSON object
    `{"payloads":[{"text":...}], "meta":{...}}` followed by MORE diagnostic
    lines. We brace-scan for the object that has `payloads` and emit only
    payloads[0].text to stdout (what OpenFang's claude_code driver expects).

Config via env (with sane defaults):
  OPENCLAW_GW_URL       default "ws://127.0.0.1:18793"
  OPENCLAW_NATIVE_CFG   default "C:/Users/User/.openclaw/openclaw.json"
  OPENCLAW_AGENT        default "main"
  OPENCLAW_TIMEOUT_S    default 220  (leave room under OpenFang's 300s)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

GW_URL = os.environ.get("OPENCLAW_GW_URL", "ws://127.0.0.1:18793")
NATIVE_CFG = Path(
    os.environ.get("OPENCLAW_NATIVE_CFG", "C:/Users/User/.openclaw/openclaw.json")
)
OC_AGENT = os.environ.get("OPENCLAW_AGENT", "main")
OC_TIMEOUT_S = int(os.environ.get("OPENCLAW_TIMEOUT_S", "220"))


def _resolve_openclaw() -> list[str] | None:
    """Resolve the openclaw invocation as a direct argv prefix.

    CRITICAL (Windows argv limit): the npm-global `openclaw` is a `.cmd`
    shim. Spawning it goes through `cmd.exe /c openclaw.cmd ...`, and
    cmd.exe caps the command line at 8191 chars — the OpenFang sysprompt
    blows that. The proven container wrapper avoids this by invoking a
    native exe (`docker.exe`) directly (~32767-char CreateProcess limit).
    We mirror that: resolve `node.exe` + `openclaw.mjs` and invoke node
    DIRECTLY, never via the .cmd. Falls back to the .cmd only if the
    .mjs/node cannot be found (small prompts still work there).

    Returns the argv prefix list, e.g. ["C:/.../node.exe", "C:/.../openclaw.mjs"].
    """
    # Explicit override wins (can be a node path or a launcher path).
    explicit = os.environ.get("OPENCLAW_BIN")
    if explicit and Path(explicit).is_file():
        return [explicit]

    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        for p in (
            Path(r"C:/Program Files/nodejs/node.exe"),
            Path(r"C:/Program Files (x86)/nodejs/node.exe"),
        ):
            if p.is_file():
                node = str(p)
                break

    # Locate openclaw.mjs (the real entrypoint the .cmd shim wraps).
    mjs_candidates = []
    env_mjs = os.environ.get("OPENCLAW_MJS")
    if env_mjs:
        mjs_candidates.append(Path(env_mjs))
    appdata = os.environ.get("APPDATA")
    roots = []
    if appdata:
        roots.append(Path(appdata) / "npm")
    roots.append(Path.home() / "AppData" / "Roaming" / "npm")
    for r in roots:
        mjs_candidates.append(r / "node_modules" / "openclaw" / "openclaw.mjs")
    mjs = next((str(m) for m in mjs_candidates if m.is_file()), None)

    if node and mjs:
        return [node, mjs]

    # Fallback: the .cmd shim (works for small prompts; argv-limited).
    for name in ("openclaw.cmd", "openclaw.exe", "openclaw"):
        found = shutil.which(name)
        if found:
            return [found]
    for r in roots:
        c = r / "openclaw.cmd"
        if c.is_file():
            return [str(c)]
    return None


def _read_gateway_token() -> str | None:
    """Read gateway.auth.token from the native openclaw config.

    The file is UTF-8 *with BOM* (PowerShell wrote it); strip the BOM before
    json.loads. The token is never printed/logged.
    """
    try:
        raw = NATIVE_CFG.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
        cfg = json.loads(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    gw = cfg.get("gateway") or {}
    auth = gw.get("auth") or {}
    tok = auth.get("token")
    return tok if isinstance(tok, str) and tok else None


def _extract_text(raw: str) -> str:
    """openclaw prints diagnostics, then a JSON blob, then MORE diagnostics.
    Brace-scan every top-level {...}; return payloads[0].text from the object
    that has a `payloads` list. Fall back to a deep 'text' search, then raw."""
    objs: list[str] = []
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    objs.append(raw[start : i + 1])
                    start = -1
    for cand in reversed(objs):  # last complete object first
        try:
            d = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        payloads = d.get("payloads")
        if isinstance(payloads, list) and payloads:
            txt = payloads[0].get("text")
            if isinstance(txt, str) and txt.strip():
                return txt
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
    return raw.strip()


def main() -> int:
    # OpenFang's patched claude_code driver pipes the prompt via stdin.
    try:
        prompt = sys.stdin.read()
    except Exception:
        prompt = ""
    prompt = (prompt or "").strip()
    if not prompt:
        print("[openclaw-visible-wrapper] empty prompt on stdin", file=sys.stderr)
        return 2

    # NOTE: OpenFang's claude_code driver passes its (~18 KB) system prompt
    # via --system-prompt-file. We deliberately do NOT fold it into
    # --message: the openclaw gateway agent already carries its own persona
    # (agent.toml system_prompt) + session context, and folding 18 KB into
    # an argv-passed --message is exactly what blew the Windows command-line
    # limit. The OpenFang persona is generic ("you are a helpful agent")
    # and redundant here; openclaw-visible's own system_prompt is what
    # matters. Keep --message = just the user prompt (small, argv-safe).
    message = prompt

    token = _read_gateway_token()
    if not token:
        print(
            f"[openclaw-visible-wrapper] no gateway.auth.token in {NATIVE_CFG}",
            file=sys.stderr,
        )
        return 2

    openclaw_argv = _resolve_openclaw()
    if not openclaw_argv:
        print(
            "[openclaw-visible-wrapper] openclaw not found (need node+"
            "openclaw.mjs, or set OPENCLAW_BIN / OPENCLAW_MJS)",
            file=sys.stderr,
        )
        return 127

    env = os.environ.copy()
    env["OPENCLAW_GATEWAY_URL"] = GW_URL
    env["OPENCLAW_GATEWAY_TOKEN"] = token

    oc_args = [
        "agent",
        "--agent",
        OC_AGENT,
        "--message",
        message,
        "--json",
        "--timeout",
        str(OC_TIMEOUT_S),
    ]
    # openclaw_argv is [node, openclaw.mjs] (preferred, native exe — no
    # cmd.exe, ~32767-char limit like the proven container path) or a
    # single-element [launcher] fallback. Direct spawn, shell=False.
    cmd = [*openclaw_argv, *oc_args]
    last = openclaw_argv[-1].lower()
    if last.endswith(".cmd") or last.endswith(".bat"):
        # Fallback only: a .cmd needs the interpreter (argv-limited).
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        cmd = [comspec, "/c", *openclaw_argv, *oc_args]

    debug = os.environ.get("OPENFANG_OPENCLAW_DEBUG")
    if debug:
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaw_visible.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"--- pid={os.getpid()} gw={GW_URL} msg_len={len(message)}\n"
                )
                fh.write(f"msg_head={message[:200]!r}\n")
        except Exception:
            pass

    try:
        # encoding/errors are REQUIRED on Windows. Without them text=True
        # uses cp1252 (default locale) and crashes on the UTF-8 bytes the
        # openclaw CLI emits (smart quotes, German umlauts, etc.) with:
        #   UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d
        # That kills the whole tool call (`exit code 1`) and Brain sees
        # response: "" from the OpenFang stream. Verified 2026-05-29.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OC_TIMEOUT_S + 40,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(
            f"[openclaw-visible-wrapper] timed out after {OC_TIMEOUT_S + 40}s",
            file=sys.stderr,
        )
        return 124
    except FileNotFoundError:
        print(
            "[openclaw-visible-wrapper] 'openclaw' not found on PATH", file=sys.stderr
        )
        return 127

    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    text = _extract_text(combined)

    if debug:
        dbg = Path(os.environ.get("TEMP", "/tmp")) / "openfang_openclaw_visible.log"
        try:
            with dbg.open("a", encoding="utf-8") as fh:
                fh.write(f"rc={result.returncode} extracted_len={len(text)}\n")
                fh.write(f"extracted_head={text[:200]!r}\n")
        except Exception:
            pass

    # Trailing newline is REQUIRED: OpenFang's claude_code streaming driver
    # reads stdout via `tokio::io::Lines::next_line()` which waits for `\n`.
    # Without it the final chunk is buffered until EOF and may not surface
    # as a stream chunk in time — Brain.multihop_execute then sees
    # response: "" because openclaw-visible "produced no chunks".
    # Fix verified 2026-05-29: the only thing between wrapper-correct-output
    # and Telegram-bot-actually-works.
    if not text.endswith("\n"):
        text = text + "\n"
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0 if text.strip() and result.returncode == 0 else (result.returncode or 1)


if __name__ == "__main__":
    sys.exit(main())
