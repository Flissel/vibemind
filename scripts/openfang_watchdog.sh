#!/usr/bin/env bash
# openfang_watchdog — POSIX shim for openfang_watchdog.py.
# Mirrors openfang_watchdog.cmd but for Linux/macOS.
#
# Usage:
#   ./openfang_watchdog.sh                 # default: poll every 60s in foreground
#   ./openfang_watchdog.sh --once          # single check + exit
#
# Run in background (nohup):
#   nohup ./openfang_watchdog.sh >/tmp/openfang_watchdog.out 2>&1 &
#   # save the PID with: echo $! > /tmp/openfang_watchdog.pid

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/../.venv/bin/python"
WATCHDOG="$SCRIPT_DIR/openfang_watchdog.py"

if [ -x "$VENV_PY" ]; then
    exec "$VENV_PY" "$WATCHDOG" "$@"
else
    exec python3 "$WATCHDOG" "$@"
fi
