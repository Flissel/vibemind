"""Local OAuth-callback listener for LinkedIn (one-shot).

Flow:
    1. Listens on http://localhost:15999/callback for the OAuth redirect.
    2. Captures the `code` query-param.
    3. Exchanges code for access_token (POST /oauth/v2/accessToken).
    4. Calls GET /v2/userinfo (OIDC) to get the person URN (`sub` field).
    5. Writes the result as JSON to stdout AND to a file
       (logs/marketing/linkedin_oauth_result.json).
    6. Exits.

Run: python scripts/linkedin_oauth_listener.py
"""
from __future__ import annotations

import hmac
import html
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs" / "marketing"
LOG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
RESULT_FILE = LOG_DIR / "linkedin_oauth_result.json"


def _load_env():
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and all(c.isalnum() or c == "_" for c in k):
            os.environ.setdefault(k, v)


_load_env()
CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:15999/callback"
SCOPE = "openid profile email w_member_social"

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: LINKEDIN_CLIENT_ID / SECRET missing in env", file=sys.stderr)
    sys.exit(2)


_received: dict = {}
_done = threading.Event()
# CSRF state for the OAuth redirect — generated once at import time, compared
# constant-time in do_GET. 128 bits entropy (OAuth BCP recommends >= 128).
_EXPECTED_STATE = os.urandom(16).hex()


def _exchange_code(code: str) -> dict:
    """Exchange auth code for access_token + id_token."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": "token_exchange_failed", "detail": str(e)}


def _get_userinfo(access_token: str) -> dict:
    """OpenID Connect userinfo endpoint — returns `sub` = person URN."""
    req = urllib.request.Request(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": "userinfo_failed", "detail": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence default logging

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not the callback")
            return

        qs = urllib.parse.parse_qs(parsed.query)

        # CSRF: constant-time state check BEFORE touching code / calling LinkedIn.
        # If state is missing or mismatched, refuse — do NOT set _done so that a
        # stray probe cannot DoS the legitimate redirect.
        got_state = (qs.get("state") or [""])[0]
        if not got_state or not hmac.compare_digest(got_state, _EXPECTED_STATE):
            print("[oauth] state mismatch / missing — refusing callback", file=sys.stderr)
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b"invalid state")
            return

        if "error" in qs:
            # parse_qs returns lists — pick the first value, then HTML-escape.
            err_detail = (qs.get("error_description") or qs.get("error") or [""])[0]
            err_msg = f"LinkedIn rejected the auth: {err_detail}"
            print(f"[oauth] {err_msg}", file=sys.stderr)
            _received["error"] = err_msg
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(
                f"<h1>OAuth failed</h1><pre>{html.escape(err_msg)}</pre>".encode("utf-8")
            )
            _done.set()
            return

        code = (qs.get("code") or [""])[0]
        if not code:
            self.send_response(400)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"missing code param")
            return

        print(f"[oauth] received code (len={len(code)}), exchanging for token...")
        token_resp = _exchange_code(code)
        if "access_token" not in token_resp:
            err = f"token exchange failed: {token_resp}"
            print(f"[oauth] {err}", file=sys.stderr)
            _received["error"] = err
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(
                (
                    "<h1>Token exchange failed</h1><pre>"
                    + html.escape(json.dumps(token_resp, indent=2))
                    + "</pre>"
                ).encode("utf-8")
            )
            _done.set()
            return

        access_token = token_resp["access_token"]
        print(f"[oauth] got access_token (len={len(access_token)}), fetching userinfo...")

        userinfo = _get_userinfo(access_token)
        if "sub" not in userinfo:
            err = f"userinfo failed: {userinfo}"
            print(f"[oauth] {err}", file=sys.stderr)
            _received["error"] = err
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(
                (
                    "<h1>Userinfo failed</h1><pre>"
                    + html.escape(json.dumps(userinfo, indent=2))
                    + "</pre>"
                ).encode("utf-8")
            )
            _done.set()
            return

        result = {
            "access_token": access_token,
            "expires_in": token_resp.get("expires_in"),
            "id_token": token_resp.get("id_token"),
            "scope": token_resp.get("scope"),
            "userinfo": userinfo,
            "person_urn": f"urn:li:person:{userinfo['sub']}",
            "received_at": int(time.time()),
        }
        _received["result"] = result
        # File contains access_token + id_token in plaintext — write with 0o600
        # so other local users can't read it (umask-independent).
        # NB: os.open's mode arg only applies on CREATE; if the file existed
        # from a previous unhardened run it keeps its old perms. So we follow
        # with os.chmod to harden overwrite case too. On Windows both are
        # effective no-ops for read perms — harmless.
        _fd = os.open(
            str(RESULT_FILE),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        with os.fdopen(_fd, "w", encoding="utf-8") as _fh:
            _fh.write(json.dumps(result, indent=2))
        try:
            os.chmod(RESULT_FILE, 0o600)
        except OSError:
            # Windows / non-POSIX filesystem — perms are best-effort there.
            pass

        print(f"[oauth] success — person_urn={result['person_urn']}")
        print(f"[oauth] saved to {RESULT_FILE}")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        # Hide token in response page
        safe = {
            "person_urn": result["person_urn"],
            "userinfo": userinfo,
            "scope": result["scope"],
            "expires_in": result["expires_in"],
        }
        _e_urn = html.escape(str(result["person_urn"]))
        _e_name = html.escape(str(userinfo.get("name", "?")))
        _e_email = html.escape(str(userinfo.get("email", "?")))
        _e_safe = html.escape(json.dumps(safe, indent=2))
        self.wfile.write(f"""
            <html><body style='font-family:sans-serif;max-width:600px;margin:40px auto'>
            <h1>✅ LinkedIn OAuth komplett</h1>
            <p><strong>Person URN:</strong> <code>{_e_urn}</code></p>
            <p><strong>Name:</strong> {_e_name}</p>
            <p><strong>Email:</strong> {_e_email}</p>
            <p>Du kannst dieses Tab schliessen. Der Workflow wird jetzt automatisch konfiguriert.</p>
            <pre style='background:#f0f0f0;padding:12px;font-size:11px'>{_e_safe}</pre>
            </body></html>
        """.encode("utf-8"))
        _done.set()


def main():
    # _EXPECTED_STATE is module-level so the Handler thread can verify it.
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization"
        "?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&state={_EXPECTED_STATE}"
        f"&scope={urllib.parse.quote(SCOPE)}"
    )

    print("=" * 70)
    print("LinkedIn OAuth listener started on http://localhost:15999")
    print("=" * 70)
    print()
    print("ÖFFNE DIESE URL IM BROWSER:")
    print()
    print(f"  {auth_url}")
    print()
    print("Auf der LinkedIn-page: 'Allow' klicken.")
    print("Browser landet dann automatisch hier, listener fängt den code.")
    print()
    print("Wartet 15 minuten auf den callback. Strg+C abbrechen.")
    print()

    httpd = HTTPServer(("127.0.0.1", 15999), Handler)
    # Run in thread so we can wait on the event with timeout
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        if _done.wait(timeout=900):
            print("[oauth] flow complete")
        else:
            print("[oauth] timeout waiting for callback", file=sys.stderr)
            sys.exit(3)
    finally:
        httpd.shutdown()

    if "error" in _received:
        sys.exit(4)


if __name__ == "__main__":
    main()
