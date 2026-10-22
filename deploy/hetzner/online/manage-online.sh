#!/usr/bin/env bash
set -euo pipefail
(( EUID == 0 )) || { echo 'Im SSH-Serverfenster als root ausführen.' >&2; exit 1; }
cd /opt/smartplan-online/app/backend
set -a
source /etc/smartplan-online/service.env
set +a
exec runuser --pty -u smartplan-online -- /opt/smartplan-online/venv/bin/python -m online.manage "$@"
