#!/usr/bin/env bash
# Private loopback pilot only; not an Internet-facing production server.
set -euo pipefail
umask 0077

if (( EUID == 0 )); then
  echo 'Der Pilot muss unter einem eigenen Dienstkonto laufen, nicht als root.' >&2
  exit 1
fi
: "${OFFICE_DATA_DIR:?OFFICE_DATA_DIR muss auf den privaten Pilot-Datenordner zeigen}"
smartplan_repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
smartplan_python="$smartplan_repo/backend/.venv/bin/python"
smartplan_action="${1:-run}"
export PYTHONDONTWRITEBYTECODE=1

case "$smartplan_action" in
  backup)
    if [[ ! -f "$OFFICE_DATA_DIR/office.sqlite3" ]]; then
      echo 'Noch keine Pilotdatenbank vorhanden; keine Sicherung erforderlich.'
      exit 0
    fi
    mkdir -p -- "$OFFICE_DATA_DIR/backups"
    smartplan_backup="$OFFICE_DATA_DIR/backups/pilot-$(date -u +%Y%m%dT%H%M%S%N).sqlite3"
    "$smartplan_python" "$smartplan_repo/backend/backup.py" \
      "$OFFICE_DATA_DIR/office.sqlite3" "$smartplan_backup"
    (
      cd -- "$OFFICE_DATA_DIR/backups"
      sha256sum -- "$(basename -- "$smartplan_backup")" > "$smartplan_backup.sha256"
    )
    ;;
  run)
    smartplan_port="${SMARTPLAN_PILOT_PORT:-8765}"
    if [[ ! "$smartplan_port" =~ ^[0-9]{4,5}$ ]] || \
       (( 10#$smartplan_port < 1024 || 10#$smartplan_port > 65535 )); then
      echo 'Ungültiger Pilot-Port (erlaubt: 1024 bis 65535).' >&2
      exit 1
    fi
    export SMARTPLAN_LAUNCH_ID=smartplan-private-pilot
    exec "$smartplan_python" -u "$smartplan_repo/backend/server.py" --port "$smartplan_port"
    ;;
  *)
    echo 'Erlaubte Aktionen: run oder backup.' >&2
    exit 1
    ;;
esac
