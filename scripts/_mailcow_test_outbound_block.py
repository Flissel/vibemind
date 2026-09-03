"""Verify the loopback-only outbound block.

Two checks:
  1. NEGATIVE: marketing@ -> external-recipient@example.com MUST fail with 554
  2. POSITIVE: marketing@ -> tester1@vibemind.space MUST succeed

This proves the block targets only external addresses; internal mail still
flows.
"""
from __future__ import annotations
import os
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / ".env"
for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k, v)

HOST = os.environ["SMTP_HOST"]
PORT = int(os.environ["SMTP_PORT"])
USER = os.environ["SMTP_USER"]
PASS = os.environ["SMTP_PASS"]


def smtp() -> smtplib.SMTP_SSL:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    s = smtplib.SMTP_SSL(HOST, PORT, context=ctx, timeout=20)
    s.login(USER, PASS)
    return s


def send(to: str) -> tuple[bool, str]:
    msg = MIMEText("Test from outbound-block verifier", "plain", "utf-8")
    msg["Subject"] = "Outbound-block verifier"
    msg["From"] = USER
    msg["To"] = to
    try:
        with smtp() as s:
            s.sendmail(USER, [to], msg.as_string())
        return True, "delivered"
    except smtplib.SMTPRecipientsRefused as e:
        # e.recipients is dict: {to: (code, msg)}
        info = e.recipients.get(to, (0, b""))
        return False, f"refused {info[0]}: {info[1].decode(errors='replace')}"
    except smtplib.SMTPResponseException as e:
        return False, f"smtp {e.smtp_code}: {e.smtp_error.decode(errors='replace')}"
    except Exception as e:
        return False, f"exc: {e}"


def main() -> int:
    print(f"SMTP: {HOST}:{PORT} as {USER}")
    print()

    # 1) Negative test: external must FAIL
    print("=== NEGATIVE: external recipient (gmail) ===")
    ok, msg = send("external-recipient@example.com")
    if ok:
        print(f"  [FAIL] delivery succeeded — block NOT working: {msg}")
        neg_ok = False
    else:
        if "554" in msg or "LOOPBACK" in msg.upper():
            print(f"  [PASS] correctly refused: {msg}")
            neg_ok = True
        else:
            print(f"  [WARN] refused but unexpected reason: {msg}")
            neg_ok = False  # treat as fail — we want our specific 554 LOOPBACK

    print()
    # 2) Positive test: internal must STILL WORK
    print("=== POSITIVE: internal recipient (tester) ===")
    ok, msg = send("maya.klein01@vibemind.space")
    if ok:
        print(f"  [PASS] delivered: {msg}")
        pos_ok = True
    else:
        print(f"  [FAIL] internal send rejected — over-blocked: {msg}")
        pos_ok = False

    print()
    if neg_ok and pos_ok:
        print("ALL GOOD — loopback block works correctly.")
        return 0
    elif not neg_ok and pos_ok:
        print("BLOCK NOT EFFECTIVE — external addresses still go through.")
        return 1
    elif neg_ok and not pos_ok:
        print("OVER-BLOCKED — internal mail also rejected.")
        return 2
    else:
        print("DOUBLE FAIL — postfix is in a weird state.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
