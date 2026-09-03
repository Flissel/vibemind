#!/usr/bin/env bash
# postconf -e sets a Postfix parameter directly in main.cf at runtime.
# This is how Mailcow normally applies its compiled config — extra.cf is
# just a convention for the entrypoint, not read by postfix natively.
set -e

PFX=$(docker ps -qf name=postfix-mailcow)
echo "container: $PFX"

# The new restriction chain — PCRE block first, then original Mailcow chain.
NEW='check_recipient_access pcre:/opt/postfix/conf/loopback_recipient_block.pcre, check_recipient_mx_access proxy:mysql:/opt/postfix/conf/sql/mysql_mbr_access_maps.cf, permit_sasl_authenticated, permit_mynetworks, check_recipient_access proxy:mysql:/opt/postfix/conf/sql/mysql_tls_enforce_in_policy.cf, reject_invalid_helo_hostname, reject_unauth_destination'

docker exec "$PFX" postconf -e "smtpd_recipient_restrictions=$NEW"
echo "postconf -e applied"

echo ""
echo "=== readback ==="
docker exec "$PFX" postconf smtpd_recipient_restrictions

echo ""
echo "=== reload ==="
docker exec "$PFX" postfix reload 2>&1 || echo "reload returned non-zero (often OK if file is in valid state)"
