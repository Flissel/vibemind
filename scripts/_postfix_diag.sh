#!/usr/bin/env bash
set -e
PFX=$(docker ps -qf name=postfix-mailcow)
echo "container: $PFX"
echo ""
echo "=== running postconf shows: ==="
docker exec "$PFX" postconf smtpd_recipient_restrictions
echo ""
echo "=== main.cf has these recipient_restrictions: ==="
docker exec "$PFX" grep -n smtpd_recipient_restrictions /opt/postfix/conf/main.cf
echo ""
echo "=== extra.cf content: ==="
docker exec "$PFX" cat /opt/postfix/conf/extra.cf
echo ""
echo "=== does main.cf include extra.cf? ==="
docker exec "$PFX" grep -in extra /opt/postfix/conf/main.cf || echo "(no reference to extra)"
echo ""
echo "=== entrypoint script: ==="
docker exec "$PFX" sh -c 'ls -la /usr/local/bin/postfix.sh /opt/postfix/conf/postfix.sh 2>/dev/null'
docker exec "$PFX" sh -c 'find / -maxdepth 4 -name "*postfix*.sh" 2>/dev/null | head -10'
