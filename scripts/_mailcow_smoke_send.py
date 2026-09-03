"""Smoke-test: send a personalized newsletter from marketing@vibemind.space
to all 50 test audience mailboxes via Mailcow's internal SMTP submission port.

Verifies:
  1. SMTP auth with the marketing@ service account works
  2. Postfix accepts the mail for local delivery (all recipients are @vibemind.space)
  3. Dovecot delivers to each recipient's INBOX
  4. Personalization via Jinja-style {{name}} substitution works
  5. HTML + plain-text multipart works

Verification after run:
  - Check the count in any tester's INBOX via doveadm
  - Open SOGo as a tester (https://127.0.0.1:8443/SOGo, login with test creds)
"""
from __future__ import annotations
import json
import os
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid, formatdate
from pathlib import Path

# Load .env (cheap version — no python-dotenv dep required)
ENV_PATH = Path(__file__).parent.parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k, v)

SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "VibeMind Marketing")

AUDIENCE_PATH = Path(__file__).parent.parent / "vibemind-os" / "spaces" / "marketing" / "docs" / "test-audience.json"

TEMPLATE_SUBJECT = "Hi {first_name} — Welcome to the VibeMind audience"
TEMPLATE_TEXT = """\
Hi {first_name},

This is a smoke-test from the VibeMind marketing-ops space (loopback mode).

Your profile in our test audience:
  - role:        {role}
  - region:      {region}
  - tier:        {tier}
  - engagement:  {engagement}

If you're reading this, the marketing@ -> {email} SMTP path works end-to-end.

— The VibeMind Marketing team
"""

TEMPLATE_HTML = """\
<!DOCTYPE html>
<html><body style="font-family: -apple-system, system-ui, sans-serif; max-width:600px; margin: 24px auto; color: #1d1d1f;">
  <h2 style="color: #007aff;">Hi {first_name} —</h2>
  <p>Welcome to the <strong>VibeMind audience</strong>. This is a smoke-test from
     the marketing-ops space (loopback mode).</p>
  <h3>Your test profile</h3>
  <table style="border-collapse: collapse; width: 100%;">
    <tr><td style="padding: 6px 0;"><strong>Role</strong></td><td>{role}</td></tr>
    <tr><td style="padding: 6px 0;"><strong>Region</strong></td><td>{region}</td></tr>
    <tr><td style="padding: 6px 0;"><strong>Tier</strong></td><td>{tier}</td></tr>
    <tr><td style="padding: 6px 0;"><strong>Engagement</strong></td><td>{engagement}</td></tr>
  </table>
  <p style="margin-top: 24px; color: #86868b; font-size: 13px;">
    Sent via marketing@vibemind.space — VibeMind Marketing Ops smoke test.<br>
    Loopback delivery: all 50 of your fellow testers got the same mail.
  </p>
</body></html>
"""


def send_one(server: smtplib.SMTP_SSL, profile: dict) -> bool:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = TEMPLATE_SUBJECT.format(first_name=profile["name"].split()[0])
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    msg["To"] = formataddr((profile["name"], profile["email"]))
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="vibemind.space")
    # Add custom headers for tracking (mimics what listmonk/brevo would do)
    msg["X-VibeMind-Campaign"] = "smoke-test-2026-05-26"
    msg["X-VibeMind-Audience-Tag-Role"] = profile["tags"]["role"]
    msg["X-VibeMind-Audience-Tag-Region"] = profile["tags"]["region"]
    msg["X-VibeMind-Audience-Tag-Tier"] = profile["tags"]["tier"]

    first_name = profile["name"].split()[0]
    text = TEMPLATE_TEXT.format(
        first_name=first_name,
        email=profile["email"],
        role=profile["tags"]["role"],
        region=profile["tags"]["region"],
        tier=profile["tags"]["tier"],
        engagement=profile["tags"]["engagement"],
    )
    html = TEMPLATE_HTML.format(
        first_name=first_name,
        role=profile["tags"]["role"],
        region=profile["tags"]["region"],
        tier=profile["tags"]["tier"],
        engagement=profile["tags"]["engagement"],
    )

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        server.sendmail(SMTP_FROM, [profile["email"]], msg.as_string())
        return True
    except smtplib.SMTPException as e:
        print(f"  [ERR] {profile['email']}: {e}", file=sys.stderr)
        return False


def main() -> int:
    audience = json.loads(AUDIENCE_PATH.read_text())
    recipients = audience["created"]
    print(f"Loaded {len(recipients)} recipients from {AUDIENCE_PATH}")
    print(f"SMTP: {SMTP_HOST}:{SMTP_PORT} as {SMTP_USER}")
    print()

    # Self-signed cert in local Mailcow — accept it
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=30) as server:
        # server.set_debuglevel(1)  # uncomment to see SMTP wire protocol
        server.login(SMTP_USER, SMTP_PASS)
        print("SMTP auth OK")
        print()

        sent = 0
        failed = 0
        for r in recipients:
            ok = send_one(server, r)
            if ok:
                sent += 1
                print(f"  [OK ] {r['email']}")
            else:
                failed += 1

    print()
    print(f"Summary: {sent} sent, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
