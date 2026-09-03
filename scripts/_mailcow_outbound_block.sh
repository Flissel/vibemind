#!/usr/bin/env bash
# Configures Mailcow's Postfix to reject all recipients outside vibemind.space.
# Loopback-only safeguard against accidental external mail delivery during
# marketing-ops development. Reversible: just remove the
# `check_recipient_access pcre:...` line from extra.cf and restart postfix.
#
# Run inside WSL: bash scripts/_mailcow_outbound_block.sh
set -euo pipefail

PFX=$(docker ps -qf name=postfix-mailcow)
if [[ -z "$PFX" ]]; then
  echo "ERROR: postfix-mailcow container not running"
  exit 1
fi
echo "postfix container: $PFX"

# --- 1) Write the PCRE recipient-block map to a temp file in WSL ---
TMP_PCRE=$(mktemp)
TMP_EXTRA=$(mktemp)
trap 'rm -f "$TMP_PCRE" "$TMP_EXTRA"' EXIT

cat > "$TMP_PCRE" <<'EOF'
# 2026-05-26 loopback-only safeguard for VibeMind marketing-ops dev.
# Reject any recipient whose domain is NOT vibemind.space (case-insensitive).
# Sends FROM marketing@vibemind.space TO @gmail.com etc. get 554 instead
# of bouncing — protects against accidental external delivery while
# audience-filter logic is still being built. Remove or comment the
# map line in extra.cf to re-enable external delivery (e.g. after
# Production cutover).
/^[^@]+@(?!vibemind\.space$)/  REJECT 554 5.7.1 LOOPBACK-MODE - external recipients are blocked.
EOF

cat > "$TMP_EXTRA" <<'EOF'
myhostname = mail.vibemind.space

# 2026-05-26: Loopback-only override. Adds a PCRE block as FIRST check in
# smtpd_recipient_restrictions, before SASL-auth permission - so even
# authenticated marketing@ cannot send to external addresses. Keeps the
# rest of the original Mailcow chain after.
smtpd_recipient_restrictions =
  check_recipient_access pcre:/opt/postfix/conf/loopback_recipient_block.pcre,
  check_recipient_mx_access proxy:mysql:/opt/postfix/conf/sql/mysql_mbr_access_maps.cf,
  permit_sasl_authenticated,
  permit_mynetworks,
  check_recipient_access proxy:mysql:/opt/postfix/conf/sql/mysql_tls_enforce_in_policy.cf,
  reject_invalid_helo_hostname,
  reject_unauth_destination
EOF

# --- 2) Backup existing extra.cf inside the container (once) ---
docker exec "$PFX" sh -c 'test -f /opt/postfix/conf/extra.cf.pre-loopback-block || cp /opt/postfix/conf/extra.cf /opt/postfix/conf/extra.cf.pre-loopback-block'
echo "backup ensured"

# --- 3) Copy the files into the container ---
docker cp "$TMP_PCRE" "$PFX":/opt/postfix/conf/loopback_recipient_block.pcre
docker cp "$TMP_EXTRA" "$PFX":/opt/postfix/conf/extra.cf
echo "files copied into container"

# --- 4) Verify ---
echo ""
echo "=== /opt/postfix/conf/extra.cf ==="
docker exec "$PFX" cat /opt/postfix/conf/extra.cf
echo ""
echo "=== /opt/postfix/conf/loopback_recipient_block.pcre ==="
docker exec "$PFX" cat /opt/postfix/conf/loopback_recipient_block.pcre

# --- 5) Reload postfix to pick up the new config ---
echo ""
echo "=== postfix reload ==="
docker exec "$PFX" postfix reload 2>&1 || echo "(reload may need restart instead)"

echo ""
echo "Done. To verify: try sending from marketing@ to a non-vibemind.space address — should fail with 554."
echo "To rollback:"
echo "  docker exec $PFX cp /opt/postfix/conf/extra.cf.pre-loopback-block /opt/postfix/conf/extra.cf"
echo "  docker exec $PFX postfix reload"
