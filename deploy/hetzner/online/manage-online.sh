#!/usr/bin/env bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Im SSH-Serverfenster als root ausführen.' >&2; exit 1; }
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || { echo 'Ein Update oder eine Verwaltung läuft bereits.' >&2; exit 1; }
[[ ! -e /etc/smartplan-online/UPDATE_IN_PROGRESS && ! -L /etc/smartplan-online/UPDATE_IN_PROGRESS ]] || { echo 'Unvollständiges Update zuerst über das Journal klären.' >&2; exit 1; }
cd /opt/smartplan-online/app/backend
set -a
source /etc/smartplan-online/service.env
set +a
exec runuser --pty -u smartplan-online -- /opt/smartplan-online/venv/bin/python -m online.manage "$@"
