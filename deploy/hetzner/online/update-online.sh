#!/usr/bin/env bash
# Prepare a separate database; never migrate or restore the active database.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
(( $# == 0 )) || fail 'Dieser Ablauf verwendet ausschließlich die vorhandene Serverkonfiguration.'
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
[[ "$smartplan_repo" == /opt/smartplan-test && -d /run/systemd/system ]] || fail 'Erwartet: vorhandener systemd-Testserver /opt/smartplan-test.'
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
[[ -z "$(git -C "$smartplan_repo" status --porcelain -- backend deploy/hetzner)" ]] || fail 'Lokale Quelländerungen zuerst prüfen.'
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Verwaltung läuft bereits.'
smartplan_pending=/etc/smartplan-online/UPDATE_IN_PROGRESS
[[ ! -e "$smartplan_pending" && ! -L "$smartplan_pending" ]] || fail 'Ein vorheriges Update ist nicht abgeschlossen. UPDATE_IN_PROGRESS und Updatejournal prüfen; niemals blind zurückschalten.'
for smartplan_required in /etc/smartplan-online/service.env /var/lib/smartplan-online/vault.key /opt/smartplan-online/SOURCE_COMMIT; do
  [[ -f "$smartplan_required" && ! -L "$smartplan_required" ]] || fail "Vorhandene Installation zuerst prüfen: $smartplan_required"
done
[[ -d /opt/smartplan-online/app/backend && -x /opt/smartplan-online/venv/bin/python ]] || fail 'Vorhandene Online-Installation fehlt.'
systemctl is-active --quiet smartplan-online.service || fail 'Online-Dienst muss vor dem Update laufen.'
systemctl is-active --quiet smartplan-https.service || fail 'HTTPS-Dienst muss vor dem Update laufen.'
cmp -s "$smartplan_source/Caddyfile" /etc/smartplan-https/Caddyfile || fail 'Unbekannte HTTPS-Konfiguration. Nicht automatisch ändern.'
# Require the known service wiring; a hidden DSN override would defeat the switch.
for smartplan_unit in smartplan-online.service smartplan-online-backup.service; do
  [[ -f "/etc/systemd/system/$smartplan_unit" && ! -L "/etc/systemd/system/$smartplan_unit" ]] || fail 'Bekannte reguläre Dienstdateien erforderlich.'
  cmp -s "$smartplan_source/$smartplan_unit" "/etc/systemd/system/$smartplan_unit" || fail 'Dienstdatei weicht ab; Serverkonfiguration zuerst prüfen.'
done
systemctl daemon-reload
for smartplan_unit in smartplan-online.service smartplan-online-backup.service; do
  [[ "$(systemctl show "$smartplan_unit" --property=FragmentPath --value)" == "/etc/systemd/system/$smartplan_unit" ]] || fail 'Unerwarteter Dienstpfad.'
  [[ -z "$(systemctl show "$smartplan_unit" --property=DropInPaths --value)" ]] || fail 'Dienst-Drop-ins zuerst prüfen.'
  # Presence only: never print override values, which might contain credentials.
  [[ -z "$(systemctl show "$smartplan_unit" --property=Environment --value)" ]] || fail 'Direkte Dienst-Umgebungsüberschreibungen zuerst prüfen.'
done

smartplan_commit="$(git -C "$smartplan_repo" rev-parse HEAD)"
[[ "$smartplan_commit" =~ ^[a-f0-9]{40}$ ]] || fail 'Ungültiger Quellstand.'
smartplan_id="${smartplan_commit:0:12}-$(date -u +%Y%m%dT%H%M%S)-$$"
smartplan_candidate="smartplan_online_u_$(date -u +%Y%m%d%H%M%S)_${smartplan_commit:0:10}_$$"
(( ${#smartplan_candidate} <= 63 )) || fail 'Kandidatenname zu lang.'
smartplan_release="/opt/smartplan-online/releases/$smartplan_id"
smartplan_control="/etc/smartplan-online/updates/$smartplan_id"
smartplan_work="/var/lib/smartplan-online/updates/$smartplan_id"
smartplan_previous_app="$(readlink -f /opt/smartplan-online/app)"
smartplan_previous_venv="$(readlink -f /opt/smartplan-online/venv)"
smartplan_previous_commit="$(cat /opt/smartplan-online/SOURCE_COMMIT)"
[[ "$smartplan_previous_commit" =~ ^[a-f0-9]{40}$ ]] || fail 'Installierten Quellstand zuerst prüfen.'
for smartplan_path in "$smartplan_previous_app" "$smartplan_previous_venv"; do
  [[ "$smartplan_path" == /opt/smartplan-online/* && "$(stat -c %u "$smartplan_path")" == 0 ]] || fail 'Installierte Codepfade zuerst prüfen.'
done

# Prepare code before the maintenance window. Archive only the exact commit.
install -d -m 0755 /opt/smartplan-online/releases "$smartplan_release" "$smartplan_release/app"
(
  umask 0022
  git -C "$smartplan_repo" archive HEAD backend | tar -x -C "$smartplan_release/app"
  python3 -m venv "$smartplan_release/venv"
  "$smartplan_release/venv/bin/python" -m pip install --requirement "$smartplan_release/app/backend/online/requirements.lock"
  "$smartplan_release/venv/bin/python" -m pip check
  "$smartplan_release/venv/bin/python" -m compileall -q "$smartplan_release/app/backend"
)
smartplan_helper() { (cd "$smartplan_release/app/backend"; "$smartplan_release/venv/bin/python" -m online.release "$@"); }
smartplan_service_helper() { (cd "$smartplan_release/app/backend"; runuser -u smartplan-online -- "$smartplan_release/venv/bin/python" -m online.release "$@"); }
smartplan_atomic_copy() {
  (cd "$smartplan_release/app/backend"; "$smartplan_release/venv/bin/python" - "$@" <<'PY'
import grp
import sys
from pathlib import Path
from online.release import atomic_write
source, target, mode, group = sys.argv[1:]
atomic_write(target, Path(source).read_bytes(), mode=int(mode, 8), uid=0, gid=grp.getgrnam(group).gr_gid)
PY
  )
}
# Validate permissions before shell sourcing the operator-owned configuration.
(cd "$smartplan_release/app/backend"; "$smartplan_release/venv/bin/python" - <<'PY'
from online.release import read_environment
read_environment('/etc/smartplan-online/service.env')
PY
)
set -a
source /etc/smartplan-online/service.env
set +a
[[ "$SMARTPLAN_PUBLIC_HOST" == office.smartplan-hofmann.de ]] || fail 'Bekannten HTTPS-Hostnamen zuerst prüfen.'
# The service may still be connected here; validate only DSN/role/cluster now.
(cd "$smartplan_release/app/backend"; "$smartplan_release/venv/bin/python" - "$smartplan_candidate" <<'PY'
import os
import sys
from psycopg.conninfo import make_conninfo
from online.release import validate_dsns
active = os.environ['SMARTPLAN_DATABASE_DSN']
validate_dsns(active, make_conninfo(active, dbname=sys.argv[1]))
PY
)
install -d -m 0700 /etc/smartplan-online/updates "$smartplan_control"
install -d -m 0700 -o smartplan-online -g smartplan-online /var/lib/smartplan-online/updates "$smartplan_work"
# Reserve clone + dump + WAL headroom on the actual PostgreSQL/backup filesystems.
smartplan_database_bytes="$(smartplan_service_helper size)"
smartplan_pgdata="$(runuser -u postgres -- env -u PGHOSTADDR -u PGSERVICE -u PGSERVICEFILE -u PGOPTIONS psql \
  --no-psqlrc --host=/var/run/postgresql --port=5432 --username=postgres --dbname=postgres -Atqc 'SHOW data_directory')"
smartplan_helper capacity --path "$smartplan_pgdata" --backup-directory "$smartplan_work" --value "$smartplan_database_bytes"
install -m 0600 /etc/smartplan-online/service.env "$smartplan_control/service.env.before"
install -m 0600 /etc/smartplan-https/Caddyfile "$smartplan_control/Caddyfile.before"
install -m 0600 /opt/smartplan-online/SOURCE_COMMIT "$smartplan_control/SOURCE_COMMIT.before"
smartplan_helper maintenance --path "$smartplan_source/Caddyfile" --output "$smartplan_control/Caddyfile.maintenance"
install -m 0644 "$smartplan_control/Caddyfile.maintenance" "/etc/smartplan-https/Caddyfile.$smartplan_id"
runuser -u smartplan-https -- env XDG_DATA_HOME=/var/lib/smartplan-https XDG_CONFIG_HOME=/var/lib/smartplan-https/config \
  /opt/smartplan-https/bin/caddy validate --config "/etc/smartplan-https/Caddyfile.$smartplan_id" --adapter caddyfile
smartplan_phase() {
  smartplan_helper phase --path "$smartplan_control/phase" --value "$1"
  smartplan_helper phase --path "$smartplan_pending" --value "$1"
}
smartplan_gate=0
smartplan_stopped=0
smartplan_activating=0
smartplan_timer_was_active=0
smartplan_import_worker_was_active=0
# A failed activation-journal write must not itself resume a database writer.
smartplan_import_worker_may_resume=0
if systemctl is-active --quiet smartplan-plan-import.service; then smartplan_import_worker_was_active=1; fi
smartplan_app_legacy=""
smartplan_venv_legacy=""
smartplan_restore_link() {
  local smartplan_link="$1" smartplan_target="$2" smartplan_temp="$1.update-$$"
  [[ ! -e "$smartplan_temp" && ! -L "$smartplan_temp" ]] || return 1
  ln -s -- "$smartplan_target" "$smartplan_temp"
  if ! mv -Tf -- "$smartplan_temp" "$smartplan_link"; then
    rm -- "$smartplan_temp"
    return 1
  fi
}
smartplan_ready() {
  curl --fail --silent --max-time 3 -H 'Host: office.smartplan-hofmann.de' -H 'X-Forwarded-Proto: https' \
    http://127.0.0.1:8766/ready | "$smartplan_release/venv/bin/python" -c \
    'import json,sys; value=json.load(sys.stdin); assert value.get("status")=="ok" and value.get("database")=="ok"'
}
smartplan_abort() {
  local smartplan_result=$?
  trap - EXIT INT TERM
  set +e
  if (( smartplan_result == 0 )); then return; fi
  if (( smartplan_activating )); then
    if (( smartplan_import_worker_was_active && smartplan_import_worker_may_resume )); then
      systemctl start smartplan-plan-import.service || echo 'Importworker für die neue Datenbank nicht gestartet; Journal beibehalten und vorwärts beheben.' >&2
    fi
    if (( smartplan_timer_was_active )); then
      systemctl start smartplan-online-backup.timer || echo 'Sicherungstimer für die neue Datenbank nicht gestartet; umgehend prüfen.' >&2
    fi
    echo "Update nach Aktivierungsgrenze unterbrochen. Neue Datenbank und neuer Code bleiben erhalten. Vorwärts beheben; Journal: $smartplan_control" >&2
    echo 'Nicht automatisch auf die alte Datenbank zurückschalten: neue Schreibvorgänge könnten bereits angenommen sein.' >&2
    exit "$smartplan_result"
  fi
  local smartplan_restored=1
  if (( smartplan_stopped )); then
    if (( smartplan_import_worker_was_active )) && ! systemctl stop smartplan-plan-import.service; then
      echo "Importworker-Stopp nicht bestätigt. Konfiguration unverändert lassen; Wartung und Journal beibehalten: $smartplan_control" >&2
      exit "$smartplan_result"
    fi
    if ! systemctl stop smartplan-online.service; then
      echo "Dienststopp nicht bestätigt. Konfiguration unverändert lassen; Wartung und Journal beibehalten: $smartplan_control" >&2
      exit "$smartplan_result"
    fi
    smartplan_atomic_copy "$smartplan_control/service.env.before" /etc/smartplan-online/service.env 0640 smartplan-online || smartplan_restored=0
    if [[ -n "$smartplan_app_legacy" ]]; then
      if [[ -d "$smartplan_app_legacy" && ! -L "$smartplan_app_legacy" ]]; then
        if [[ -L /opt/smartplan-online/app ]]; then rm -- /opt/smartplan-online/app; fi
        if [[ ! -e /opt/smartplan-online/app ]]; then mv -- "$smartplan_app_legacy" /opt/smartplan-online/app || smartplan_restored=0; else smartplan_restored=0; fi
      elif [[ ! -d /opt/smartplan-online/app || -L /opt/smartplan-online/app ]]; then smartplan_restored=0; fi
    elif [[ -L /opt/smartplan-online/app ]]; then
      smartplan_restore_link /opt/smartplan-online/app "$smartplan_previous_app" || smartplan_restored=0
    fi
    if [[ -n "$smartplan_venv_legacy" ]]; then
      if [[ -d "$smartplan_venv_legacy" && ! -L "$smartplan_venv_legacy" ]]; then
        if [[ -L /opt/smartplan-online/venv ]]; then rm -- /opt/smartplan-online/venv; fi
        if [[ ! -e /opt/smartplan-online/venv ]]; then mv -- "$smartplan_venv_legacy" /opt/smartplan-online/venv || smartplan_restored=0; else smartplan_restored=0; fi
      elif [[ ! -d /opt/smartplan-online/venv || -L /opt/smartplan-online/venv ]]; then smartplan_restored=0; fi
    elif [[ -L /opt/smartplan-online/venv ]]; then
      smartplan_restore_link /opt/smartplan-online/venv "$smartplan_previous_venv" || smartplan_restored=0
    fi
    smartplan_atomic_copy "$smartplan_control/SOURCE_COMMIT.before" /opt/smartplan-online/SOURCE_COMMIT 0644 root || smartplan_restored=0
    if (( smartplan_restored )); then
      systemctl reset-failed smartplan-online.service || smartplan_restored=0
      systemctl start smartplan-online.service || smartplan_restored=0
      for smartplan_attempt in {1..15}; do smartplan_ready >/dev/null 2>&1 && break; sleep 1; done
      smartplan_ready >/dev/null 2>&1 || smartplan_restored=0
      if (( smartplan_restored && smartplan_import_worker_was_active )); then
        systemctl start smartplan-plan-import.service || smartplan_restored=0
      fi
    fi
  fi
  if (( smartplan_gate && smartplan_restored )); then
    smartplan_atomic_copy "$smartplan_control/Caddyfile.before" /etc/smartplan-https/Caddyfile 0644 root || smartplan_restored=0
    if (( smartplan_restored )); then systemctl reload smartplan-https.service || smartplan_restored=0; fi
  fi
  if (( smartplan_restored )); then
    if (( smartplan_timer_was_active )); then systemctl start smartplan-online-backup.timer || smartplan_restored=0; fi
    if (( smartplan_restored )); then
      if ! smartplan_phase rolled_back || ! rm -- "$smartplan_pending"; then
        echo "Vorheriger Dienst wieder aktiv; Abschlussjournal noch nicht bestätigt: $smartplan_control" >&2
        exit "$smartplan_result"
      fi
    else
      echo "Vorheriger Dienst aktiv; Sicherungstimer muss geprüft werden. Journal bleibt bestehen: $smartplan_control" >&2
      exit "$smartplan_result"
    fi
    echo 'Vorheriger Stand mit unveränderter Originaldatenbank wiederhergestellt. Kandidat und Sicherung bleiben erhalten.' >&2
  else
    echo "Rückkehr nicht vollständig bestätigt. Wartung beibehalten und Journal prüfen: $smartplan_control" >&2
  fi
  exit "$smartplan_result"
}
trap smartplan_abort EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Persist enough non-secret information for recovery after SIGKILL or reboot.
(cd "$smartplan_release/app/backend"; "$smartplan_release/venv/bin/python" - "$smartplan_control/metadata.json" "$smartplan_id" "$smartplan_candidate" "$smartplan_previous_app" "$smartplan_previous_venv" "$smartplan_release" "$smartplan_previous_commit" "$smartplan_commit" "$smartplan_import_worker_was_active" <<'PYMETA'
import json
import os
import sys
from psycopg.conninfo import conninfo_to_dict
from online.release import atomic_write
path, update_id, candidate, previous_app, previous_venv, release, old_commit, new_commit, import_worker_active = sys.argv[1:]
metadata = dict(update_id=update_id, candidate_database=candidate,
                source_database=conninfo_to_dict(os.environ['SMARTPLAN_DATABASE_DSN'])['dbname'],
                previous_app=previous_app, previous_venv=previous_venv,
                previous_app_was_link=os.path.islink('/opt/smartplan-online/app'),
                previous_venv_was_link=os.path.islink('/opt/smartplan-online/venv'),
                legacy_app='/opt/smartplan-online/app.before-' + update_id,
                legacy_venv='/opt/smartplan-online/venv.before-' + update_id,
                new_release=release, original_commit=old_commit, new_commit=new_commit,
                import_worker_was_active=import_worker_active == '1')
atomic_write(path, (json.dumps(metadata, sort_keys=True) + '\n').encode())
PYMETA
)
smartplan_phase prepared
smartplan_gate=1
smartplan_atomic_copy "$smartplan_control/Caddyfile.maintenance" /etc/smartplan-https/Caddyfile 0644 root
# Restart the dedicated proxy to terminate handlers accepted before maintenance;
# a reload alone could leave an old request waiting for the new backend port.
systemctl restart smartplan-https.service
smartplan_maintenance_ready=0
for smartplan_attempt in {1..10}; do
  if [[ "$(curl --silent --show-error --max-time 2 --noproxy '*' --resolve office.smartplan-hofmann.de:443:127.0.0.1 \
    --output /dev/null --write-out '%{http_code}' https://office.smartplan-hofmann.de/api/v1/projects)" == 503 ]]; then
    smartplan_maintenance_ready=1
    break
  fi
  sleep 1
done
(( smartplan_maintenance_ready )) || fail 'Öffentliche Wartungssperre nicht bestätigt.'
smartplan_phase maintenance
if systemctl is-active --quiet smartplan-online-backup.timer; then smartplan_timer_was_active=1; fi
systemctl stop smartplan-online-backup.timer
for smartplan_attempt in {1..70}; do
  smartplan_backup_state="$(systemctl show smartplan-online-backup.service --property=ActiveState --value)"
  [[ "$smartplan_backup_state" == inactive || "$smartplan_backup_state" == failed ]] && break
  sleep 5
done
[[ "$smartplan_backup_state" == inactive || "$smartplan_backup_state" == failed ]] || fail 'Laufende Sicherung zuerst auslaufen lassen.'
# Mark before stopping: even a partially failed stop must keep traffic gated.
smartplan_stopped=1
if (( smartplan_import_worker_was_active )); then systemctl stop smartplan-plan-import.service; fi
systemctl stop smartplan-online.service
smartplan_phase stopped
smartplan_service_helper validate --candidate "$smartplan_candidate"
runuser -u postgres -- env -u PGHOSTADDR -u PGSERVICE -u PGSERVICEFILE -u PGOPTIONS createdb --host=/var/run/postgresql --port=5432 --username=postgres --owner=smartplan-online -- "$smartplan_candidate"
smartplan_service_helper prepare --candidate "$smartplan_candidate" --backup-directory "$smartplan_work" --output "$smartplan_work/report.json"
install -m 0600 "$smartplan_work/report.json" "$smartplan_control/report.json"
smartplan_phase verified
# Keep the previous physical directories on first update; never delete releases.
if [[ ! -L /opt/smartplan-online/app ]]; then
  smartplan_app_legacy="/opt/smartplan-online/app.before-$smartplan_id"
  mv -- /opt/smartplan-online/app "$smartplan_app_legacy"
fi
if [[ ! -L /opt/smartplan-online/venv ]]; then
  smartplan_venv_legacy="/opt/smartplan-online/venv.before-$smartplan_id"
  mv -- /opt/smartplan-online/venv "$smartplan_venv_legacy"
fi
smartplan_restore_link /opt/smartplan-online/app "$smartplan_release/app"
smartplan_restore_link /opt/smartplan-online/venv "$smartplan_release/venv"
smartplan_helper configure --path /etc/smartplan-online/service.env --candidate "$smartplan_candidate"
printf '%s\n' "$smartplan_commit" > "$smartplan_control/SOURCE_COMMIT.new"
smartplan_atomic_copy "$smartplan_control/SOURCE_COMMIT.new" /opt/smartplan-online/SOURCE_COMMIT 0644 root
systemctl start smartplan-online.service
for smartplan_attempt in {1..15}; do smartplan_ready >/dev/null 2>&1 && break; sleep 1; done
smartplan_ready >/dev/null 2>&1 || fail 'Kandidat nicht bereit; Rückkehr vor öffentlicher Freigabe.'
curl --fail --silent --max-time 3 -H 'Host: office.smartplan-hofmann.de' -H 'X-Forwarded-Proto: https' \
  http://127.0.0.1:8766/ready | "$smartplan_release/venv/bin/python" -c \
  'import json,sys; v=json.load(sys.stdin); assert v.get("schema_version")==3 and {"project_plans","offline_plan_access","plan_imports"} <= set(v.get("capabilities",[]))'
systemctl is-active --quiet smartplan-online.service || fail 'Neuer Dienst nicht aktiv.'
# Durable boundary BEFORE any public request can reach the new database.
smartplan_activating=1
smartplan_phase activating
smartplan_import_worker_may_resume=1
smartplan_atomic_copy "$smartplan_control/Caddyfile.before" /etc/smartplan-https/Caddyfile 0644 root
systemctl reload smartplan-https.service
[[ "$(curl --silent --show-error --max-time 10 --noproxy '*' --resolve office.smartplan-hofmann.de:443:127.0.0.1 \
  --output /dev/null --write-out '%{http_code}' https://office.smartplan-hofmann.de/api/v1/projects)" == 401 ]] || fail 'Öffentliche Prüfung nicht bestätigt. Neue Datenbank beibehalten.'
if (( smartplan_import_worker_was_active )); then systemctl start smartplan-plan-import.service; fi
if (( smartplan_timer_was_active )); then systemctl start smartplan-online-backup.timer; fi
smartplan_phase active
rm -- "$smartplan_pending"
echo "Testupdate aktiviert: $smartplan_commit"
echo "Updatejournal: $smartplan_control"
echo 'Originaldatenbank, bisherige Releases und geprüfte Sicherung bleiben erhalten.'
echo 'Ab öffentlicher Freigabe keine automatische Datenbank-Rückkehr; neue Schreibvorgänge erhalten.'
