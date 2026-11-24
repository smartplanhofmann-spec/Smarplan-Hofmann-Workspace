#!/usr/bin/env bash
# Select the installed test server's authentication policy.
set -euo pipefail
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
[[ $# == 1 && ( $1 == password || $1 == mfa ) ]] || fail 'Aufruf: set-test-login.sh password|mfa'
mode=$1
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Verwaltung läuft bereits.'
[[ ! -e /etc/smartplan-online/UPDATE_IN_PROGRESS && ! -L /etc/smartplan-online/UPDATE_IN_PROGRESS ]] ||
  fail 'Ein laufendes Serverupdate zuerst abschließen.'

cd /opt/smartplan-online/app/backend
python=/opt/smartplan-online/venv/bin/python
configure() {
  "$python" -m online.release test-login --path /etc/smartplan-online/service.env --value "$1"
}
restart_and_check() {
  systemctl restart smartplan-online.service || return 1
  curl --fail --silent --show-error --noproxy '*' --resolve office.smartplan-hofmann.de:443:127.0.0.1 \
    --retry 8 --retry-connrefused --retry-delay 1 --retry-max-time 25 --max-time 5 \
    https://office.smartplan-hofmann.de/ready | "$python" -c \
    'import json,sys; v=json.load(sys.stdin); sys.exit(0 if v.get("status")=="ok" and v.get("database")=="ok" else 1)'
}
configure "$mode"
if ! restart_and_check; then
  if [[ $mode == password ]]; then
    configure mfa
    restart_and_check || fail 'Zwei-Faktor-Pflicht gesetzt. Dienst und HTTPS-Bereitschaft prüfen.'
    fail 'Passwortanmeldung konnte nicht aktiviert werden. Zwei-Faktor-Pflicht wieder aktiv.'
  fi
  fail 'Zwei-Faktor-Pflicht gesetzt. Dienst und HTTPS-Bereitschaft prüfen.'
fi
if [[ $mode == password ]]; then
  echo 'Testserver bereit. Anmeldeverfahren: Passwort.'
else
  echo 'Testserver bereit. Anmeldeverfahren: Passwort und zweiter Faktor.'
fi
