"""
VibeMind status probe server.

Serves a tiny HTTP API + the live dashboard. Unlike Vibemind.debug.ps1
(stale ports, short timeouts, frozen snapshot) this probes the *correct*
endpoints, in parallel, and the dashboard re-polls every few seconds.

Run:  python scripts/status_probe_server.py   (default :8799)
Then open http://127.0.0.1:8799/ in a browser.

Corrections vs. the PS script (verified 2026-05-19):
  OpenFang   :4200   (HTTP API; :50051 is gRPC only)
  MongoDB    :27017  (not :37017)
  Brain      :5000   primary (/api/health); :5001 is a secondary API
  Rowboat    :3100   (the running docker container)
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROBE_PORT = int(os.environ.get("VIBEMIND_STATUS_PORT", "8799"))
HTTP_TIMEOUT = 4.0
DASHBOARD_HTML = Path(__file__).parent / "status_dashboard.html"

# name, kind ("http"|"tcp"), target, ok-codes (http only)
SERVICES: list[dict] = [
    {"name": "Brain (Dashboard)", "kind": "http", "url": "http://127.0.0.1:5000/api/health", "ok": (200,)},
    {"name": "Brain API (2nd)",   "kind": "http", "url": "http://127.0.0.1:5001/health",     "ok": (200,)},
    {"name": "Bridge",            "kind": "http", "url": "http://127.0.0.1:5150/health",     "ok": (200, 404)},
    {"name": "La-Fungus Search",  "kind": "http", "url": "http://127.0.0.1:8011/docs",       "ok": (200,)},
    {"name": "Minibook",          "kind": "http", "url": "http://127.0.0.1:3480/api/v1/agents", "ok": (200,)},
    {"name": "MiroFish",          "kind": "http", "url": "http://127.0.0.1:5101/health",     "ok": (200,)},
    {"name": "Voice Electron",    "kind": "http", "url": "http://127.0.0.1:9223/json/version", "ok": (200,)},
    {"name": "Automation BE",     "kind": "http", "url": "http://127.0.0.1:8007/api/health/health", "ok": (200,)},
    {"name": "OpenFang",          "kind": "http", "url": "http://127.0.0.1:4200/api/health", "ok": (200,)},
    {"name": "OpenClaw",          "kind": "http", "url": "http://127.0.0.1:18789/healthz",   "ok": (200,)},
    {"name": "n8n Workflows",     "kind": "http", "url": "http://127.0.0.1:15678/healthz",   "ok": (200,)},
    {"name": "Coding Engine",     "kind": "http", "url": "http://127.0.0.1:8000/docs",       "ok": (200,)},
    {"name": "Coding Frontend",   "kind": "http", "url": "http://127.0.0.1:5173/",           "ok": (200,)},
    {"name": "Supabase API",      "kind": "http", "url": "http://127.0.0.1:54321/",          "ok": (200, 404)},
    {"name": "Supabase Studio",   "kind": "http", "url": "http://127.0.0.1:54323/",          "ok": (200,)},
    {"name": "Media Server",      "kind": "http", "url": "http://127.0.0.1:8977/",           "ok": (200,)},
    {"name": "Rowboat",           "kind": "tcp",  "host": "127.0.0.1", "port": 3100},
    {"name": "MongoDB",           "kind": "tcp",  "host": "127.0.0.1", "port": 27017},
    {"name": "MoireServer (ws)",  "kind": "tcp",  "host": "127.0.0.1", "port": 8766},
    {"name": "Qdrant",            "kind": "tcp",  "host": "127.0.0.1", "port": 6730},
]


def _probe_http(url: str, ok: tuple[int, ...]) -> dict:
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception as e:  # noqa: BLE001
        return {"up": False, "detail": f"{type(e).__name__}", "ms": int((time.monotonic() - t0) * 1000)}
    return {"up": code in ok, "detail": f"HTTP {code}", "ms": int((time.monotonic() - t0) * 1000)}


def _probe_tcp(host: str, port: int) -> dict:
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=HTTP_TIMEOUT):
            return {"up": True, "detail": "TCP open", "ms": int((time.monotonic() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"up": False, "detail": f"{type(e).__name__}", "ms": int((time.monotonic() - t0) * 1000)}


def _probe_one(svc: dict) -> dict:
    if svc["kind"] == "http":
        r = _probe_http(svc["url"], tuple(svc["ok"]))
        target = svc["url"]
    else:
        r = _probe_tcp(svc["host"], svc["port"])
        target = f"{svc['host']}:{svc['port']}"
    return {"name": svc["name"], "kind": svc["kind"], "target": target, **r}


def collect_status() -> dict:
    with ThreadPoolExecutor(max_workers=len(SERVICES)) as ex:
        results = list(ex.map(_probe_one, SERVICES))
    up = sum(1 for r in results if r["up"])
    return {"ts": time.time(), "up": up, "total": len(results), "services": results}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            body = json.dumps(collect_status()).encode("utf-8")
            self._send(200, body, "application/json")
        elif self.path in ("/", "/index.html"):
            if DASHBOARD_HTML.exists():
                self._send(200, DASHBOARD_HTML.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"dashboard html missing", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PROBE_PORT), Handler)
    print(f"[status-probe] http://127.0.0.1:{PROBE_PORT}/  ({len(SERVICES)} services)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
