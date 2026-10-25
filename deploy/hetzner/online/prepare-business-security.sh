#!/usr/bin/env bash
# Ownership preparation only, after maintenance and complete writer stop.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
smartplan_inherited_lock=0
if [[ "${1-}" == --under-update-lock ]]; then smartplan_inherited_lock=1; shift; fi
(( $# == 2 )) || fail 'Aufruf: prepare-business-security.sh [--under-update-lock] RELEASE_PYTHON RELEASE_BACKEND'
smartplan_python=$1
smartplan_backend=$2
smartplan_release="$(dirname -- "$(dirname -- "$(dirname -- "$smartplan_python")")")"
[[ "$smartplan_release" == /opt/smartplan-online/releases/* &&
   "$smartplan_python" == "$smartplan_release/venv/bin/python" &&
   "$smartplan_backend" == "$smartplan_release/app/backend" &&
   "$(readlink -f -- "$smartplan_release")" == "$smartplan_release" ]] || fail 'Bekannter vorbereiteter Releasepfad erforderlich.'
for smartplan_path in "$smartplan_release" "$smartplan_release/venv" "$smartplan_release/venv/bin" \
    "$smartplan_python" "$smartplan_release/app" "$smartplan_backend" \
    "$smartplan_backend/online" "$smartplan_backend/online/release.py" "$smartplan_backend/business_schema.py"; do
  [[ -e "$smartplan_path" && "$(stat -Lc %u -- "$smartplan_path")" == 0 ]] || fail 'Release muss vollständig root gehören.'
  smartplan_mode="$(stat -Lc %a -- "$smartplan_path")"
  (( (8#$smartplan_mode & 0022) == 0 )) || fail 'Release darf nicht durch Gruppe oder andere Benutzer verändert werden.'
done
[[ -x "$smartplan_python" && -f "$smartplan_backend/online/release.py" ]] || fail 'Vorbereiteter Operatorruntime fehlt.'
if (( smartplan_inherited_lock )); then
  [[ -e /proc/self/fd/9 && "$(stat -Lc '%d:%i' /proc/self/fd/9)" == "$(stat -Lc '%d:%i' /run/lock/smartplan-online-update.lock)" ]] || fail 'Geerbte Updatesperre fehlt.'
  flock -n 9 || fail 'Updatesperre nicht exklusiv übernommen.'
else
  exec 9>/run/lock/smartplan-online-update.lock
  flock -n 9 || fail 'Ein Update oder eine Verwaltung läuft bereits.'
  [[ ! -e /etc/smartplan-online/UPDATE_IN_PROGRESS && ! -L /etc/smartplan-online/UPDATE_IN_PROGRESS ]] || fail 'Vorheriges Update zuerst abschließen.'
fi
for smartplan_unit in smartplan-online.service smartplan-online-backup.timer smartplan-online-backup.service smartplan-plan-import.service smartplan-lead-replies.timer smartplan-lead-replies.service; do
  smartplan_active="$(systemctl show "$smartplan_unit" --property=ActiveState --value)"
  [[ "$smartplan_active" == inactive || "$smartplan_active" == failed ]] || fail 'Alle API-/Import-/Sicherungswriter zuerst geordnet anhalten.'
done
IFS= read -r smartplan_dsn < <(PYTHONPATH="$smartplan_backend" PYTHONNOUSERSITE=1 "$smartplan_python" - <<'PY'
from psycopg.conninfo import make_conninfo
from online.release import read_environment, validate_dsns
_, _, _, dsn = read_environment('/etc/smartplan-online/service.env')
validate_dsns(dsn, make_conninfo(dsn, dbname='smartplan_security_guard'))
print(dsn)
PY
) || fail 'Dienstkonfiguration ist nicht eindeutig und lokal.'
[[ -n "$smartplan_dsn" ]] || fail 'Lokale Dienstkonfiguration fehlt.'
runuser -u postgres -- env -u PGHOSTADDR -u PGSERVICE -u PGSERVICEFILE -u PGOPTIONS -u PGPORT \
  -u PYTHONHOME -u PYTHONSTARTUP -u PYTHONUSERBASE \
  SMARTPLAN_DATABASE_DSN="$smartplan_dsn" PYTHONPATH="$smartplan_backend" PYTHONNOUSERSITE=1 \
  "$smartplan_python" -m online.release security
echo 'Ownership getrennt. Dienste bleiben gestoppt; der koordinierte Updatepfad prüft und aktiviert den Kandidaten.'
