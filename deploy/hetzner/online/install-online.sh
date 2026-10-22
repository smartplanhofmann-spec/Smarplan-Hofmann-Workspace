#!/usr/bin/env bash
# First install on the existing VM, leaves HTTPS routes and the SQLite pilot unchanged.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
[[ "$smartplan_repo" == /opt/smartplan-test && -d /run/systemd/system ]] || fail 'Erwartet: vorhandener systemd-Testserver.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Geprüftes Ziel: Ubuntu 24.04 LTS.'
case "$(uname -m)" in aarch64|x86_64) ;; *) fail 'Nur ARM64 und x86-64 unterstützt.' ;; esac
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
[[ -z "$(git -C "$smartplan_repo" status --porcelain -- backend deploy/hetzner)" ]] || fail 'Lokale Quelländerungen zuerst prüfen.'
for smartplan_path in /opt/smartplan-online /etc/smartplan-online /var/lib/smartplan-online /etc/systemd/system/smartplan-online.service /etc/systemd/system/smartplan-online-backup.service /etc/systemd/system/smartplan-online-backup.timer; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Bereits vorhanden, zuerst prüfen: $smartplan_path"
done
! getent passwd smartplan-online >/dev/null || fail 'Dienstkonto existiert bereits; zuerst prüfen.'
! getent group smartplan-online >/dev/null || fail 'Dienstgruppe existiert bereits; zuerst prüfen.'
for smartplan_unit in smartplan-online.service smartplan-online-backup.service smartplan-online-backup.timer; do
  [[ "$(systemctl show "$smartplan_unit" --property=LoadState --value)" == not-found ]] || fail "Vorhandene Unit zuerst prüfen: $smartplan_unit"
done
[[ -z "$(ss -H -ltn 'sport = :8766')" ]] || fail 'Port 8766 ist belegt.'
systemctl is-active --quiet smartplan-https.service || fail 'Bestehender HTTPS-Dienst muss laufen.'
cmp -s "$smartplan_repo/deploy/hetzner/https/Caddyfile" /etc/smartplan-https/Caddyfile || fail 'HTTPS-Konfiguration weicht ab; zuerst prüfen.'
systemd-analyze verify "$smartplan_source/smartplan-online.service" "$smartplan_source/smartplan-online-backup.service" "$smartplan_source/smartplan-online-backup.timer"

# Ubuntu's PostgreSQL 16 uses local peer authentication; no database password is created.
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install --yes postgresql-16 postgresql-client-16
[[ "$(runuser -u postgres -- psql --no-psqlrc -Atqc 'SHOW server_version_num')" == 16* ]] || fail 'PostgreSQL 16 auf dem Standard-Socket erforderlich.'
smartplan_listen="$(runuser -u postgres -- psql --no-psqlrc -Atqc 'SHOW listen_addresses')"
[[ "$smartplan_listen" == localhost || "$smartplan_listen" == 127.0.0.1 || -z "$smartplan_listen" ]] || fail 'PostgreSQL lauscht über Loopback hinaus; zuerst prüfen.'
[[ -z "$(runuser -u postgres -- psql --no-psqlrc -Atqc "SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'")" ]] || fail 'Datenbankrolle existiert bereits.'
[[ -z "$(runuser -u postgres -- psql --no-psqlrc -Atqc "SELECT 1 FROM pg_database WHERE datname='smartplan_online'")" ]] || fail 'Datenbank existiert bereits.'

install -d -m 0755 /opt/smartplan-online /opt/smartplan-online/app
(
  umask 0022
  git -C "$smartplan_repo" archive HEAD backend | tar -x -C /opt/smartplan-online/app
  python3 -m venv /opt/smartplan-online/venv
  /opt/smartplan-online/venv/bin/python -m pip install --requirement /opt/smartplan-online/app/backend/online/requirements.lock
  /opt/smartplan-online/venv/bin/python -m pip check
)
git -C "$smartplan_repo" rev-parse HEAD > /opt/smartplan-online/SOURCE_COMMIT
chmod 0644 /opt/smartplan-online/SOURCE_COMMIT
useradd --system --user-group --no-create-home --home-dir /var/lib/smartplan-online --shell /usr/sbin/nologin smartplan-online
install -d -m 0700 -o smartplan-online -g smartplan-online /var/lib/smartplan-online
install -d -m 0750 -o root -g smartplan-online /etc/smartplan-online
cat > /etc/smartplan-online/service.env <<'ENV'
SMARTPLAN_DATABASE_DSN='dbname=smartplan_online user=smartplan-online host=/var/run/postgresql'
SMARTPLAN_PUBLIC_HOST=office.smartplan-hofmann.de
SMARTPLAN_VAULT_KEY_FILE=/var/lib/smartplan-online/vault.key
ENV
chown root:smartplan-online /etc/smartplan-online/service.env
chmod 0640 /etc/smartplan-online/service.env
runuser -u smartplan-online -- /opt/smartplan-online/venv/bin/python - <<'PY'
import os
from cryptography.fernet import Fernet
fd = os.open('/var/lib/smartplan-online/vault.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
with os.fdopen(fd, 'wb') as stream:
    stream.write(Fernet.generate_key())
PY
runuser -u postgres -- psql --no-psqlrc -v ON_ERROR_STOP=1 -c 'CREATE ROLE "smartplan-online" LOGIN'
runuser -u postgres -- createdb --owner=smartplan-online smartplan_online
bash "$smartplan_source/manage-online.sh" migrate
install -m 0644 "$smartplan_source/smartplan-online.service" /etc/systemd/system/smartplan-online.service
install -m 0644 "$smartplan_source/smartplan-online-backup.service" "$smartplan_source/smartplan-online-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now smartplan-online.service
systemctl enable --now smartplan-online-backup.timer
systemctl status smartplan-online.service --no-pager --full
echo 'Online-Pilot auf Loopback installiert. Zuerst eigenes Online-Testkonto anlegen, dann HTTPS aktivieren.'
echo 'Port 8766 und PostgreSQL-Port 5432 bleiben ohne öffentliche Firewall-Freigabe.'
