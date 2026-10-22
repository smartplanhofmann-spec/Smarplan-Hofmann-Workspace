#!/usr/bin/env bash
# Switch only the explicitly owned setup proxy after the new backend and owner are ready.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
[[ "$smartplan_repo" == /opt/smartplan-test ]] || fail 'Erwarteter Checkout: /opt/smartplan-test.'
[[ -z "$(git -C "$smartplan_repo" status --porcelain -- backend deploy/hetzner)" ]] || fail 'Lokale Änderungen zuerst prüfen.'
[[ "$(cat /opt/smartplan-online/SOURCE_COMMIT)" == "$(git -C "$smartplan_repo" rev-parse HEAD)" ]] || fail 'Checkout und installierter Online-Stand unterscheiden sich.'
cmp -s "$smartplan_repo/deploy/hetzner/https/Caddyfile" /etc/smartplan-https/Caddyfile || fail 'Vorhandene HTTPS-Konfiguration zuerst prüfen; bereits aktiviert?'
[[ ! -e /etc/smartplan-online/Caddyfile.before ]] || fail 'Vorherige Aktivierung zuerst prüfen.'
systemctl is-active --quiet smartplan-online.service || fail 'Online-Dienst läuft nicht.'
set -a
source /etc/smartplan-online/service.env
set +a
cd /opt/smartplan-online/app/backend
runuser -u smartplan-online -- /opt/smartplan-online/venv/bin/python - <<'PY'
import os
from online.store import PostgresOffice
office = PostgresOffice(os.environ['SMARTPLAN_DATABASE_DSN'])
try:
    if not office.db.execute("SELECT 1 FROM users WHERE active=1 AND role='owner'").fetchone():
        raise SystemExit('Zuerst eigenes Online-Testkonto anlegen.')
finally:
    office.db.close()
PY
curl --fail --silent --show-error --max-time 10 -H 'Host: office.smartplan-hofmann.de' \
  -H 'X-Forwarded-Proto: https' http://127.0.0.1:8766/ready | python3 -c 'import json,sys; v=json.load(sys.stdin); assert v.get("version")=="0.5.0-online-pilot" and v.get("database")=="ok"'
systemctl start smartplan-online-backup.service
install -m 0644 "$smartplan_source/Caddyfile" /etc/smartplan-https/Caddyfile.online
runuser -u smartplan-https -- env XDG_DATA_HOME=/var/lib/smartplan-https XDG_CONFIG_HOME=/var/lib/smartplan-https/config \
  /opt/smartplan-https/bin/caddy validate --config /etc/smartplan-https/Caddyfile.online --adapter caddyfile
install -m 0600 /etc/smartplan-https/Caddyfile /etc/smartplan-online/Caddyfile.before
install -m 0644 /etc/smartplan-https/Caddyfile.online /etc/smartplan-https/Caddyfile
if ! systemctl reload smartplan-https.service; then
  install -m 0644 /etc/smartplan-online/Caddyfile.before /etc/smartplan-https/Caddyfile
  systemctl reload smartplan-https.service
  fail 'Neue Konfiguration abgewiesen; vorherige HTTPS-Konfiguration wiederhergestellt.'
fi
if ! smartplan_status="$(curl --silent --show-error --max-time 15 --output /dev/null --write-out '%{http_code}' https://office.smartplan-hofmann.de/api/v1/projects)" || [[ "$smartplan_status" != 401 ]]; then
  install -m 0644 /etc/smartplan-online/Caddyfile.before /etc/smartplan-https/Caddyfile
  systemctl reload smartplan-https.service
  fail 'Öffentliche Prüfung erwartet 401; vorherige HTTPS-Konfiguration wiederhergestellt. Journal prüfen.'
fi
echo 'Versionierte Online-API über HTTPS erreichbar; unangemeldeter Projektzugriff gesperrt (401).'
echo 'Nur fiktive Testdaten verwenden. Die Windows-App benötigt das separate Online-Pilotpaket.'
