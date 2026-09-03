"""openfang_watchdog — keep the OpenFang daemon alive.

Polls `http://127.0.0.1:<port>/api/health` on a fixed interval. If the daemon
stops responding (timeout, 5xx, or connection refused) for `consecutive_fails`
checks in a row, kills the stale process via `taskkill` and respawns the daemon
with `.env` loaded into the process env (matches the manual restart flow).

Why this exists: on Windows, OpenFang's TCP listener can be lost after long
idle (~2h) — the process stays alive but doesn't answer requests. See memory
note "Gotcha — OpenFang zombie daemon after long idle on Windows".

Usage:
    python scripts/openfang_watchdog.py                 # default config
    python scripts/openfang_watchdog.py --interval 60   # poll every 60s
    python scripts/openfang_watchdog.py --once          # one-shot check + exit
    python scripts/openfang_watchdog.py --foreground    # don't daemonize logs

Run-in-background via the .cmd shim or via Start-Process in PowerShell.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DAEMON_JSON = Path.home() / ".openfang" / "daemon.json"
ENV_FILE = PROJECT_ROOT / ".env"
_EXE_NAME = "openfang.exe" if sys.platform == "win32" else "openfang"
_TARGET_BASE = PROJECT_ROOT / "vibemind-os" / "openfang" / "target"
_RELEASE = _TARGET_BASE / "release" / _EXE_NAME
_DEBUG = _TARGET_BASE / "debug" / _EXE_NAME
# Prefer the freshest build (whichever has the newer mtime) — release builds
# sometimes fail with LLVM ICEs on this large crate, so debug is the fallback.
def _pick_exe() -> Path:
    if _RELEASE.is_file() and _DEBUG.is_file():
        return _RELEASE if _RELEASE.stat().st_mtime > _DEBUG.stat().st_mtime else _DEBUG
    return _RELEASE if _RELEASE.is_file() else _DEBUG
OPENFANG_EXE = _pick_exe()
LOG_FILE = Path(os.environ.get("TEMP", "/tmp")) / "openfang_watchdog.log"

DEFAULT_INTERVAL_S = 60
DEFAULT_TIMEOUT_S = 8
DEFAULT_MAX_FAILS = 2  # 2 consecutive misses = restart


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(line)
    sys.stdout.flush()
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def read_daemon_state() -> tuple[int | None, str | None]:
    """Return (pid, listen_addr) from daemon.json, or (None, None) when missing."""
    if not DAEMON_JSON.is_file():
        return None, None
    try:
        d = json.loads(DAEMON_JSON.read_text(encoding="utf-8"))
        return d.get("pid"), d.get("listen_addr")
    except Exception:
        return None, None


def health_ok(listen_addr: str, timeout: float) -> bool:
    url = f"http://{listen_addr}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return False
            body = resp.read().decode("utf-8", errors="replace")
            return '"ok"' in body or '"status":"ok"' in body
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def kill_process(pid: int) -> bool:
    """Kill a process by PID. Cross-platform: taskkill on Windows, SIGKILL elsewhere."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, text=True, check=False,
            )
            if result.returncode == 0:
                log(f"killed pid={pid}")
                return True
            log(f"taskkill failed for pid={pid}: {result.stderr.strip() or result.stdout.strip()}")
            return False
        except FileNotFoundError:
            log("taskkill not available on this system")
            return False
    # POSIX (linux/macOS): SIGTERM first, then SIGKILL as fallback
    try:
        os.kill(pid, signal.SIGTERM)
        # Give it 2s to exit cleanly, then SIGKILL if still alive
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)  # 0 = no-op, raises OSError if process is gone
            except (OSError, ProcessLookupError):
                log(f"killed pid={pid} (SIGTERM)")
                return True
        os.kill(pid, signal.SIGKILL)
        log(f"killed pid={pid} (SIGKILL after timeout)")
        return True
    except (OSError, ProcessLookupError) as e:
        # Already dead or never existed — treat as success for our purposes
        log(f"kill pid={pid}: {e}")
        return True


def load_env_dict() -> dict[str, str]:
    """Parse .env into a dict. Skips comments + blank lines."""
    out: dict[str, str] = {}
    if not ENV_FILE.is_file():
        return out
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def spawn_openfang() -> int | None:
    """Start the OpenFang daemon detached. Returns the new PID or None on failure."""
    if not OPENFANG_EXE.is_file():
        log(f"openfang.exe not found at {OPENFANG_EXE}")
        return None
    env = os.environ.copy()
    env.update(load_env_dict())
    outer_scripts = PROJECT_ROOT / "scripts"
    env["PATH"] = os.pathsep.join((str(outer_scripts), env.get("PATH", "")))
    env["VIBEMIND_SUBSCRIPTION_WRAPPER_DIR"] = str(outer_scripts.resolve())
    stdout_log = Path(os.environ.get("TEMP", "/tmp")) / "openfang_watchdog_daemon.log"
    stderr_log = Path(os.environ.get("TEMP", "/tmp")) / "openfang_watchdog_daemon.err"
    try:
        # Detach the spawned daemon so it survives if the watchdog exits.
        # Windows: DETACHED_PROCESS + new process group.
        # POSIX:   start_new_session=True puts it in its own session/pgid.
        popen_kwargs: dict[str, object] = {
            "stdout": stdout_log.open("ab"),
            "stderr": stderr_log.open("ab"),
            "stdin": subprocess.DEVNULL,
            "env": env,
            "close_fds": True,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen([str(OPENFANG_EXE), "start"], **popen_kwargs)
        log(f"spawned new daemon pid={proc.pid} (detached)")
        return proc.pid
    except Exception as e:
        log(f"spawn failed: {e}")
        return None


def restart_daemon() -> bool:
    """Kill the recorded zombie + spawn a fresh daemon. Returns True when the
    new daemon responds to /api/health within 30s."""
    pid, listen_addr = read_daemon_state()
    if pid:
        kill_process(pid)
        # Brief pause so Windows releases the socket / cleans up handles
        time.sleep(2)
    new_pid = spawn_openfang()
    if not new_pid:
        return False

    # Wait for daemon to boot. It writes daemon.json once ready.
    for attempt in range(15):
        time.sleep(2)
        new_pid_check, addr = read_daemon_state()
        if new_pid_check and addr and health_ok(addr, timeout=3):
            log(f"new daemon healthy at {addr} after {(attempt + 1) * 2}s")
            return True
    log("new daemon failed to become healthy within 30s")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S,
                        help="Seconds between health checks (default 60)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S,
                        help="Per-check HTTP timeout in seconds (default 8)")
    parser.add_argument("--max-fails", type=int, default=DEFAULT_MAX_FAILS,
                        help="Consecutive failed checks before restart (default 2)")
    parser.add_argument("--once", action="store_true",
                        help="One check, then exit (no loop)")
    args = parser.parse_args()

    log(f"watchdog started — interval={args.interval}s timeout={args.timeout}s max_fails={args.max_fails}")
    log(f"daemon.json: {DAEMON_JSON}")
    log(f"env file: {ENV_FILE}")
    log(f"openfang.exe: {OPENFANG_EXE}")

    consecutive_fails = 0
    poll_count = 0
    HEARTBEAT_EVERY = 10  # log "alive" status every Nth ok-poll (~10 min at 60s interval)

    while True:
        pid, listen_addr = read_daemon_state()
        if not pid or not listen_addr:
            log("daemon.json missing or invalid — spawning fresh daemon")
            ok = restart_daemon()
            log(f"restart result: {'ok' if ok else 'FAILED'}")
            consecutive_fails = 0
            poll_count = 0
        else:
            ok = health_ok(listen_addr, timeout=args.timeout)
            if ok:
                poll_count += 1
                if consecutive_fails > 0:
                    log(f"health recovered (pid={pid}, addr={listen_addr})")
                    poll_count = 1
                elif args.once:
                    log(f"health ok (pid={pid}, addr={listen_addr})")
                elif poll_count == 1 or poll_count % HEARTBEAT_EVERY == 0:
                    log(f"alive ok (pid={pid}, addr={listen_addr}, poll={poll_count})")
                consecutive_fails = 0
            else:
                consecutive_fails += 1
                log(f"health FAIL ({consecutive_fails}/{args.max_fails}) — pid={pid} addr={listen_addr}")
                if consecutive_fails >= args.max_fails:
                    log(f"threshold reached — restarting daemon")
                    restart_ok = restart_daemon()
                    log(f"restart result: {'ok' if restart_ok else 'FAILED'}")
                    consecutive_fails = 0

        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("watchdog stopped by SIGINT")
        sys.exit(0)
