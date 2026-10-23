#!/usr/bin/env bash
# Exercise the real service restrictions on synthetic data in a NEW database.
# Neither the active application's DSN nor its import queue is changed.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Die isolierte Serverabnahme benötigt root.'
(( $# == 0 )) || fail 'Die Abnahme wählt ihre Einwegdatenbank selbst.'
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
smartplan_python=/opt/smartplan-online/venv/bin/python
[[ "$smartplan_repo" == /opt/smartplan-test && -d /run/systemd/system ]] || fail 'Erwartet: vorbereiteter systemd-Server /opt/smartplan-test.'
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der geprüfte Checkout muss root gehören.'
[[ -x "$smartplan_python" && -x /opt/smartplan-plan-import/venv/bin/python ]] || fail 'Zuerst die getrennten Laufzeitumgebungen vorbereiten.'
[[ -f "$smartplan_source/accept-plan-import-fixture.py" && ! -L "$smartplan_source/accept-plan-import-fixture.py" ]] || fail 'Geprüfte Abnahme-Fixture fehlt.'
[[ -d /etc/smartplan-online && ! -L /etc/smartplan-online ]] || fail 'Vorbereitete Dienstkonfiguration fehlt.'
[[ "$(stat -c %u /etc/smartplan-online)" == 0 ]] || fail 'Dienstkonfiguration muss root gehören.'
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Verwaltung läuft bereits.'
[[ ! -e /etc/smartplan-online/UPDATE_IN_PROGRESS && ! -L /etc/smartplan-online/UPDATE_IN_PROGRESS ]] || fail 'Zuerst das offene Updatejournal klären.'
cmp -s "$smartplan_source/smartplan-plan-import.service" /etc/systemd/system/smartplan-plan-import.service || fail 'Die bekannte Importunit zuerst vorbereiten.'
systemctl daemon-reload
[[ "$(systemctl show smartplan-plan-import.service --property=FragmentPath --value)" == /etc/systemd/system/smartplan-plan-import.service ]] || fail 'Unerwarteter regulärer Unitpfad.'
[[ -z "$(systemctl show smartplan-plan-import.service --property=DropInPaths --value)" ]] || fail 'Reguläre Unit-Drop-ins zuerst prüfen.'
[[ -z "$(systemctl show smartplan-plan-import.service --property=Environment --value)" ]] || fail 'Reguläre direkte Unitumgebung zuerst prüfen.'
[[ "$(systemctl show smartplan-plan-import.service --property=ActiveState --value)" == inactive ]] || fail 'Der reguläre Importdienst muss für die Abnahme inaktiv sein.'
[[ "$(systemctl show smartplan-plan-import.service --property=UnitFileState --value)" == disabled ]] || fail 'Der reguläre Importdienst darf für die Abnahme nicht automatisch aktiviert sein.'
[[ "$(runuser -u postgres -- /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 psql --no-psqlrc --host=/var/run/postgresql --port=5432 --username=postgres --dbname=postgres -Atqc 'SHOW server_version_num')" == 16* ]] || fail 'Erwartet: lokaler PostgreSQL-16-Peer-Cluster.'
smartplan_nonce="$("$smartplan_python" -c 'import secrets; print(secrets.token_hex(12))')"
[[ "$smartplan_nonce" =~ ^[a-f0-9]{24}$ ]] || fail 'Abnahme-ID ungültig.'
smartplan_database="smartplan_import_accept_$smartplan_nonce"
smartplan_unit="smartplan-plan-import-accept-$smartplan_nonce.service"
smartplan_unit_path="/run/systemd/system/$smartplan_unit"
smartplan_dsn="postgresql:///$smartplan_database?host=/var/run/postgresql&user=smartplan-online"
[[ ! -e "$smartplan_unit_path" && ! -L "$smartplan_unit_path" ]] || fail 'Abnahmeunit bereits vorhanden.'
smartplan_state="$(mktemp -d /etc/smartplan-online/.import-accept-XXXXXXXX)"
smartplan_created_database=0
smartplan_verified=0
smartplan_cleanup() {
  local smartplan_exit=$? smartplan_stopped=1
  trap - EXIT
  # The link target proves ownership even if a signal interrupted its creation.
  if [[ -L "$smartplan_unit_path" && "$(readlink "$smartplan_unit_path")" == "$smartplan_state/accept.service" ]]; then
    systemctl stop "$smartplan_unit" || smartplan_stopped=0
    [[ "$(systemctl show "$smartplan_unit" --property=ActiveState --value)" == inactive ]] || smartplan_stopped=0
    if (( smartplan_stopped )); then
      rm -- "$smartplan_unit_path"
      systemctl daemon-reload || smartplan_exit=1
      systemctl reset-failed "$smartplan_unit" >/dev/null 2>&1 || true
    fi
  fi
  if (( ! smartplan_stopped )); then
    echo "Abnahmedienst nicht beendet; ausschließlich eigene Testobjekte zur Prüfung behalten: $smartplan_unit / $smartplan_database" >&2
    exit 1
  fi
  if (( smartplan_created_database )); then
    # No --force: never terminate an unexpected database client.
    if ! runuser -u postgres -- /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
      dropdb --host=/var/run/postgresql --port=5432 --username=postgres "$smartplan_database"; then
      echo "Eigene Abnahmedatenbank zur Prüfung behalten: $smartplan_database" >&2
      smartplan_exit=1
    fi
  fi
  rm -rf -- "$smartplan_state"
  if (( smartplan_exit == 0 && smartplan_verified )); then
    echo 'Synthetische systemd-Abnahme erfolgreich: Ergebnisse geprüft, Prozessfamilie beendet, Auftrag wiederaufgenommen und eigene Testobjekte entfernt.'
  fi
  exit "$smartplan_exit"
}
trap smartplan_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# PostgreSQL creates this unique database atomically. A failed creation never
# assigns cleanup ownership and can therefore never drop a pre-existing DB.
runuser -u postgres -- /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
  createdb --host=/var/run/postgresql --port=5432 --username=postgres --owner=smartplan-online "$smartplan_database"
smartplan_created_database=1
"$smartplan_python" - "$smartplan_source/smartplan-plan-import.service" "$smartplan_state" "$smartplan_database" <<'PY'
from pathlib import Path
import sys
source, state, database = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
old = 'EnvironmentFile=/etc/smartplan-online/service.env'
content = source.read_text()
if content.count(old) != 1:
    raise SystemExit('Genau eine bekannte EnvironmentFile-Zeile erforderlich.')
(state / 'service.env').write_text("SMARTPLAN_DATABASE_DSN='dbname=" + database + " user=smartplan-online host=/var/run/postgresql'\n")
(state / 'accept.service').write_text(content.replace(old, 'EnvironmentFile=' + str(state / 'service.env')))
PY
ln -s -- "$smartplan_state/accept.service" "$smartplan_unit_path"
systemctl daemon-reload
smartplan_fixture() {
  (cd /opt/smartplan-online/app/backend; runuser -u smartplan-online -- \
    /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 SMARTPLAN_IMPORT_ACCEPTANCE=1 \
    "$smartplan_python" "$smartplan_source/accept-plan-import-fixture.py" \
    --dsn "$smartplan_dsn" --unit "$smartplan_unit" "$@")
}
smartplan_job_id() {
  "$smartplan_python" -c 'import json,re,sys; value=json.load(sys.stdin)["job_id"]; assert re.fullmatch(r"[a-f0-9]{32}",value); print(value)'
}
smartplan_first="$(smartplan_fixture seed-first | smartplan_job_id)"
systemctl start "$smartplan_unit"
smartplan_fixture wait-review --job "$smartplan_first"
smartplan_second="$(smartplan_fixture seed-second | smartplan_job_id)"
smartplan_fixture wait-running --job "$smartplan_second" > "$smartplan_state/running.json"
systemctl stop "$smartplan_unit"
smartplan_fixture verify-stopped --job "$smartplan_second" < "$smartplan_state/running.json"
systemctl start "$smartplan_unit"
smartplan_fixture wait-review --job "$smartplan_second"
systemctl stop "$smartplan_unit"
smartplan_verified=1
