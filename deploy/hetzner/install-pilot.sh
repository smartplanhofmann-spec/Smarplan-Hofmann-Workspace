#!/usr/bin/env bash
# Install only the private test service on the already-provisioned Ubuntu VM.
# Does not open ports, initialize an owner, import data or install dependencies.
set -euo pipefail
umask 0077
smartplan_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
smartplan_user=smartplan-pilot
smartplan_state=/var/lib/smartplan-pilot
smartplan_units=(smartplan-pilot.service smartplan-pilot-backup.service smartplan-pilot-backup.timer)
fail() { echo "$*" >&2; exit 1; }

(( EUID == 0 )) || fail 'Die Dienstinstallation benötigt root auf dem Hetzner-Testserver.'
[[ "$smartplan_repo" == /opt/smartplan-test ]] || fail 'Erwarteter Checkout: /opt/smartplan-test.'
[[ -d /run/systemd/system ]] || fail 'Diese Installation benötigt ein laufendes systemd.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Geprüftes Ziel: Ubuntu 24.04 LTS.'
case "$(uname -m)" in aarch64|x86_64) ;; *) fail 'Nicht unterstützte Architektur.' ;; esac
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
[[ -x "$smartplan_repo/backend/.venv/bin/python" ]] || fail 'Die geprüfte Python-Umgebung fehlt.'
git -C "$smartplan_repo" diff --quiet -- backend deploy/hetzner || fail 'Lokale Quelländerungen zuerst prüfen.'
git -C "$smartplan_repo" diff --cached --quiet -- backend deploy/hetzner || fail 'Vorgemerkte Quelländerungen zuerst prüfen.'
"$smartplan_repo/backend/.venv/bin/python" -m pip check

for smartplan_unit in "${smartplan_units[@]}"; do
  smartplan_target="/etc/systemd/system/$smartplan_unit"
  [[ ! -L "$smartplan_target" ]] || fail "Vorhandenen Unit-Symlink zuerst prüfen: $smartplan_target"
  if [[ -e "$smartplan_target" ]] && ! cmp -s "$smartplan_repo/deploy/hetzner/$smartplan_unit" "$smartplan_target"; then
    fail "Vorhandene abweichende Unit wird nicht überschrieben: $smartplan_target"
  fi
done
[[ ! -L "$smartplan_state" ]] || fail 'Der Pilot-Datenordner darf kein Symlink sein.'
if getent passwd "$smartplan_user" > /dev/null; then
  smartplan_identity="$(getent passwd "$smartplan_user")"
  [[ "$(cut -d: -f6 <<< "$smartplan_identity")" == "$smartplan_state" ]] || fail 'Abweichendes Dienstkonto-Home.'
  [[ "$(cut -d: -f7 <<< "$smartplan_identity")" == /usr/sbin/nologin ]] || fail 'Abweichende Dienstkonto-Shell.'
  (( $(id -u "$smartplan_user") > 0 && $(id -u "$smartplan_user") < 1000 )) || fail 'Abweichendes Dienstkonto.'
else
  [[ ! -e "$smartplan_state" ]] || fail 'Vorhandene Pilotdaten zuerst prüfen; Dienstkonto fehlt.'
fi

if systemctl is-active --quiet smartplan-pilot.service; then
  [[ -f /etc/systemd/system/smartplan-pilot.service ]] || fail 'Vorhandenen aktiven Dienst zuerst prüfen.'
  echo 'Pilot läuft bereits; der laufende Prozess wird nicht neu gestartet.'
else
  # Fail before installing or stopping anything if a different process owns the port.
  "$smartplan_repo/backend/.venv/bin/python" - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 8765))
PY
fi

if ! getent passwd "$smartplan_user" > /dev/null; then
  useradd --system --user-group --no-create-home --home-dir "$smartplan_state" \
    --shell /usr/sbin/nologin "$smartplan_user"
fi
if [[ -e "$smartplan_state" ]]; then
  [[ -d "$smartplan_state" ]] || fail 'Pilot-Datenpfad ist kein Verzeichnis.'
  [[ "$(stat -c %u "$smartplan_state")" == "$(id -u "$smartplan_user")" ]] || fail 'Vorhandene Daten gehören einem anderen Konto.'
else
  install -d -m 0700 -o "$smartplan_user" -g "$smartplan_user" "$smartplan_state"
fi
runuser -u "$smartplan_user" -- test -x "$smartplan_repo/backend/.venv/bin/python"
runuser -u "$smartplan_user" -- test -r "$smartplan_repo/backend/server.py"
for smartplan_unit in "${smartplan_units[@]}"; do
  install -m 0644 "$smartplan_repo/deploy/hetzner/$smartplan_unit" "/etc/systemd/system/$smartplan_unit"
done
systemd-analyze verify "${smartplan_units[@]/#//etc/systemd/system/}"
systemctl daemon-reload
systemctl enable --now smartplan-pilot.service
systemctl enable --now smartplan-pilot-backup.timer

# Check the actual process, not only systemctl's early 'active' transition.
"$smartplan_repo/backend/.venv/bin/python" - <<'PY'
import json
import time
import urllib.error
import urllib.request
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(30):
    try:
        with opener.open('http://127.0.0.1:8765/health', timeout=2) as response:
            health = json.load(response)
        if health.get('status') != 'ok' or health.get('launch_id') != 'smartplan-private-pilot':
            raise SystemExit('Unerwartete Instanz auf Port 8765. Dienststatus und Journal prüfen.')
        try:
            opener.open('http://127.0.0.1:8765/api/projects', timeout=2)
        except urllib.error.HTTPError as denied:
            if denied.code == 401:
                print('Privater Pilot gestartet; Fachzugriff ohne Anmeldung gesperrt (401).')
                break
            raise
        raise SystemExit('Unangemeldeter Fachzugriff wurde nicht gesperrt.')
    except urllib.error.URLError:
        if attempt == 29:
            raise SystemExit('Startprüfung fehlgeschlagen. journalctl -u smartplan-pilot -n 40 --no-pager prüfen.')
        time.sleep(0.5)
PY
systemctl --no-pager --full status smartplan-pilot.service
systemctl --no-pager list-timers smartplan-pilot-backup.timer
echo 'Nur privater Pilot auf 127.0.0.1:8765; kein öffentliches HTTPS und noch kein Benutzerkonto.'
