"""Create 50 realistic test mailboxes in local Mailcow for marketing-space audience testing.

Uses Faker for realistic names + simulated metadata (last_login, signup_date, tags).
Saves credentials to a single JSON file so we can iterate without rebuilding.

Tags simulate the kind of segmentation a real CRM would have:
  role:        founder | engineer | designer | marketer | exec
  region:      DACH | UK | US | APAC | other
  tier:        free | trial | enterprise
  engagement:  hot | warm | cold

Run:
    python scripts/_mailcow_create_test_audience.py
"""

from __future__ import annotations
import json
import os
import random
import secrets
import ssl
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAILCOW_URL = os.environ.get("MAILCOW_URL", "https://127.0.0.1:8443")
MAILCOW_API_KEY = os.environ.get("MAILCOW_API_KEY")
if not MAILCOW_API_KEY:
    print(
        "ERROR: MAILCOW_API_KEY not in env. Source from .env or export before run.",
        file=sys.stderr,
    )
    sys.exit(1)

DOMAIN = "vibemind.space"
COUNT = 50
# Repo-root path — NOT vibemind-os/ (that's a submodule, gets reset on pulls).
OUT_PATH = Path(__file__).parent.parent / "spaces" / "marketing" / "docs" / "test-audience.json"

# Skip TLS verification for self-signed mailcow cert
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _http(method: str, path: str, payload: dict | None = None) -> dict | list:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"X-API-Key": MAILCOW_API_KEY}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(MAILCOW_URL + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
        body = resp.read()
        return json.loads(body) if body else {}


def _gen_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "._+-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# Self-contained name + tag generation (no external deps needed)
FIRST_NAMES = [
    "Alex","Jordan","Sam","Casey","Morgan","Taylor","Riley","Jamie","Quinn","Avery",
    "Maria","Lena","Sophie","Anna","Emma","Lukas","Noah","Felix","Ben","Paul",
    "Liam","Olivia","Mia","Lara","Charlie","Cameron","Pat","Drew","Reese","Sky",
    "Aiden","Zoe","Iris","Yara","Elena","Mira","Nora","Hugo","Theo","Leo",
    "Maya","Nina","Tara","Tom","Eric","Jonas","Kai","Robin","Sasha","Vera",
]
LAST_NAMES = [
    "Schmidt","Müller","Fischer","Weber","Wagner","Becker","Schulz","Klein","Wolf","Schwarz",
    "Schneider","Hofmann","Werner","Lehmann","Schmitt","Krause","Meyer","Walker","Carter","Davis",
    "Bennett","Mitchell","Anderson","Thompson","White","Roberts","Lewis","Walker","Hall","Allen",
    "Young","King","Wright","Lopez","Hill","Scott","Green","Adams","Baker","Gonzalez",
    "Nelson","Carter","Mitchell","Perez","Roberts","Turner","Phillips","Campbell","Parker","Evans",
]

ROLES = ["founder", "engineer", "designer", "marketer", "exec"]
REGIONS = ["DACH", "UK", "US", "APAC", "other"]
TIERS = ["free", "free", "free", "trial", "trial", "enterprise"]  # weighted free-heavy
ENGAGEMENT = ["hot", "warm", "warm", "cold", "cold", "cold"]  # weighted cold


def gen_profile(idx: int) -> dict:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    # use idx in localpart to guarantee uniqueness even with name collisions
    local = f"{first.lower()}.{last.lower()}{idx:02d}"
    days_ago = random.randint(1, 365)
    last_login_days_ago = random.randint(0, days_ago)  # cannot be before signup
    return {
        "idx": idx,
        "local_part": local,
        "email": f"{local}@{DOMAIN}",
        "name": f"{first} {last}",
        "tags": {
            "role": random.choice(ROLES),
            "region": random.choice(REGIONS),
            "tier": random.choice(TIERS),
            "engagement": random.choice(ENGAGEMENT),
        },
        "signup_date": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(),
        "last_login_date": (datetime.now(timezone.utc) - timedelta(days=last_login_days_ago)).isoformat(),
        "password": _gen_password(),
    }


def create_mailbox(profile: dict) -> tuple[bool, str]:
    payload = {
        "local_part": profile["local_part"],
        "domain": DOMAIN,
        "name": profile["name"],
        "quota": 50,  # 50 MB per mailbox — plenty for marketing tests, fits 100 boxes in 5 GB
        "password": profile["password"],
        "password2": profile["password"],
        "active": 1,
        "force_pw_update": 0,
        "tls_enforce_in": 1,
        "tls_enforce_out": 1,
    }
    try:
        resp = _http("POST", "/api/v1/add/mailbox", payload)
        # Mailcow can respond as either a dict or a list of dicts.
        # Each dict has {type: "success"/"danger", msg: [...]} — msg items can be
        # mixed str and int (e.g. ["mailbox_quota_left_exceeded", 0]), so we
        # stringify before joining.
        items = resp if isinstance(resp, list) else [resp] if isinstance(resp, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("type") == "danger":
                msg_parts = [str(p) for p in item.get("msg", [])]
                return False, ", ".join(msg_parts)
        return True, "ok"
    except urllib.error.HTTPError as e:
        try:
            return False, f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
        except Exception:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def list_existing_mailboxes() -> set[str]:
    try:
        resp = _http("GET", "/api/v1/get/mailbox/all")
        if isinstance(resp, list):
            return {entry.get("username", "") for entry in resp if isinstance(entry, dict)}
    except Exception as e:
        print(f"warn: could not list existing mailboxes: {e}", file=sys.stderr)
    return set()


def main() -> int:
    random.seed(42)  # reproducible test audience
    print(f"Creating {COUNT} test mailboxes in {DOMAIN} via {MAILCOW_URL}")
    print()

    existing = list_existing_mailboxes()
    print(f"  {len(existing)} mailboxes already exist (will skip duplicates)\n")

    profiles = [gen_profile(i) for i in range(1, COUNT + 1)]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Load previous run if exists — preserves passwords of already-created boxes
    prev_created: list[dict] = []
    if OUT_PATH.exists():
        try:
            prev = json.loads(OUT_PATH.read_text())
            prev_created = prev.get("created", [])
        except Exception:
            pass
    prev_by_email = {p["email"]: p for p in prev_created}

    created = []
    skipped = []
    errors = []
    for p in profiles:
        if p["email"] in existing:
            # Already there — keep existing password from prev json if we have it
            old = prev_by_email.get(p["email"])
            if old:
                p["password"] = old.get("password", p["password"])
            skipped.append(p)
            created.append(p)
            print(f"  [SKP] {p['email']:50s}  already exists")
            continue
        ok, msg = create_mailbox(p)
        if ok:
            print(f"  [OK ] {p['email']:50s}  {p['name']:25s}  {p['tags']}")
            created.append(p)
        else:
            print(f"  [ERR] {p['email']:50s}  {msg[:120]}")
            errors.append({"email": p["email"], "error": msg})

    OUT_PATH.write_text(
        json.dumps({"created": created, "errors": errors, "domain": DOMAIN, "count": COUNT}, indent=2, default=str),
        encoding="utf-8",
    )

    print()
    print(f"Summary: {len(created)} total ({len(skipped)} skipped/existing, {len(errors)} errors)")
    print(f"Saved to: {OUT_PATH}")
    print()
    print("Tag distribution:")
    for tag_kind in ("role", "region", "tier", "engagement"):
        counts: dict[str, int] = {}
        for p in created:
            v = p["tags"][tag_kind]
            counts[v] = counts.get(v, 0) + 1
        print(f"  {tag_kind:12s}  " + "  ".join(f"{k}:{v}" for k, v in sorted(counts.items())))

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
