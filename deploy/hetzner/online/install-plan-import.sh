#!/usr/bin/env bash
# Prepare the optional local recognizer after the verified schema-3 API update.
# Never starts a database writer, modifies a DB or changes existing API wiring.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
(( $# == 0 )) || fail 'Dieser Ablauf verwendet ausschließlich die vorhandene Serverkonfiguration.'
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
smartplan_runtime=/opt/smartplan-plan-import
smartplan_unit=/etc/systemd/system/smartplan-plan-import.service
[[ "$smartplan_repo" == /opt/smartplan-test && -d /run/systemd/system ]] || fail 'Erwartet: vorhandener systemd-Testserver /opt/smartplan-test.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Geprüftes Ziel: Ubuntu 24.04 LTS.'
case "$(uname -m)" in aarch64|x86_64) ;; *) fail 'Nur ARM64 und x86-64 unterstützt.' ;; esac
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
[[ -z "$(git -C "$smartplan_repo" status --porcelain -- backend deploy/hetzner)" ]] || fail 'Lokale Quelländerungen zuerst prüfen.'
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Verwaltung läuft bereits.'
[[ ! -e /etc/smartplan-online/UPDATE_IN_PROGRESS && ! -L /etc/smartplan-online/UPDATE_IN_PROGRESS ]] || fail 'Ein vorheriges Update ist nicht abgeschlossen; zuerst dessen Journal prüfen.'
systemctl is-active --quiet smartplan-online.service || fail 'Die aktualisierte Online-API muss laufen.'
[[ -f /opt/smartplan-online/SOURCE_COMMIT && ! -L /opt/smartplan-online/SOURCE_COMMIT ]] || fail 'Installierten Quellstand zuerst prüfen.'
smartplan_commit="$(git -C "$smartplan_repo" rev-parse HEAD)"
[[ "$smartplan_commit" =~ ^[a-f0-9]{40}$ && "$(cat /opt/smartplan-online/SOURCE_COMMIT)" == "$smartplan_commit" ]] || fail 'Zuerst den geprüften API-Updateablauf mit genau diesem Quellstand abschließen.'
[[ -x /opt/smartplan-online/venv/bin/python ]] || fail 'Installierte Online-Python-Umgebung fehlt.'
for smartplan_file in online/import_worker.py online/import_sandbox.py online/plan_imports.py plan_import/process.py plan_import/sandbox_entry.py plan_import/sandbox_probe.py plan_import/requirements.lock; do
  cmp -s "$smartplan_repo/backend/$smartplan_file" "/opt/smartplan-online/app/backend/$smartplan_file" || fail 'Installierter Importcode weicht vom geprüften Quellstand ab.'
done
# Read only the canonical DSN through the existing strict parser. This never
# connects, migrates, claims an import, or changes the operator's configuration.
(cd /opt/smartplan-online/app/backend; /opt/smartplan-online/venv/bin/python - <<'PY'
from psycopg.conninfo import make_conninfo
from online.release import read_environment, validate_dsns
_, _, _, dsn = read_environment('/etc/smartplan-online/service.env')
validate_dsns(dsn, make_conninfo(dsn, dbname='smartplan_import_install_check'))
PY
)
for smartplan_path in "$smartplan_runtime" "$smartplan_unit" "$smartplan_unit.d"; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Bereits vorhanden; nicht überschreiben: $smartplan_path"
done
systemctl daemon-reload
[[ "$(systemctl show smartplan-plan-import.service --property=LoadState --value)" == not-found ]] || fail 'Vorhandene Importunit zuerst prüfen.'
[[ "$(systemctl show smartplan-plan-import.service --property=ActiveState --value)" == inactive ]] || fail 'Ein noch aktiver Importdienst muss zuerst geordnet geklärt werden.'
for smartplan_link in /etc/systemd/system/*.wants/smartplan-plan-import.service /run/systemd/system/*.wants/smartplan-plan-import.service; do
  [[ ! -e "$smartplan_link" && ! -L "$smartplan_link" ]] || fail 'Vorhandene Import-Aktivierung zuerst prüfen.'
done
smartplan_created_runtime=0
smartplan_created_unit=0
smartplan_done=0
smartplan_cleanup() {
  local smartplan_exit=$?
  trap - EXIT
  if (( ! smartplan_done )); then
    # Only objects created by this first-install invocation are removed. System
    # packages are shared and stay installed; existing app/data/config stay put.
    if (( smartplan_created_unit )); then
      rm -f -- "$smartplan_unit"
      systemctl daemon-reload || echo 'Dienstkonfiguration nach Bereinigung prüfen.' >&2
    fi
    if (( smartplan_created_runtime )); then rm -rf -- "$smartplan_runtime"; fi
  fi
  exit "$smartplan_exit"
}
trap smartplan_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
  python3.12-venv bubblewrap tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu fonts-dejavu-core
# The shared lock and repeated absence check assign cleanup ownership before
# either command can create a partial object or receive SIGTERM.
[[ ! -e "$smartplan_runtime" && ! -L "$smartplan_runtime" ]] || fail 'Runtime wurde zwischenzeitlich angelegt; zuerst prüfen.'
smartplan_created_runtime=1
mkdir -m 0755 -- "$smartplan_runtime"
(
  umask 0022
  python3.12 -m venv "$smartplan_runtime/venv"
  "$smartplan_runtime/venv/bin/python" -m pip install --only-binary=:all: --requirement /opt/smartplan-online/app/backend/plan_import/requirements.lock
  "$smartplan_runtime/venv/bin/python" -m pip check
)
# Match NoNewPrivileges and the real service UID during the namespace/runtime
# probe. The unit repeats this acceptance before any database connection.
(cd /opt/smartplan-online/app/backend; runuser -u smartplan-online -- \
  /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/setpriv --no-new-privs /opt/smartplan-online/venv/bin/python -m online.import_worker \
  --worker-python "$smartplan_runtime/venv/bin/python" --ocr-languages deu+eng --doctor)
[[ ! -e "$smartplan_unit" && ! -L "$smartplan_unit" ]] || fail 'Importunit wurde zwischenzeitlich angelegt; zuerst prüfen.'
smartplan_created_unit=1
install -m 0644 "$smartplan_source/smartplan-plan-import.service" "$smartplan_unit"
systemctl daemon-reload
[[ "$(systemctl show smartplan-plan-import.service --property=FragmentPath --value)" == "$smartplan_unit" ]] || fail 'Unerwarteter Dienstpfad.'
[[ -z "$(systemctl show smartplan-plan-import.service --property=DropInPaths --value)" ]] || fail 'Unerwartete Dienst-Drop-ins.'
[[ -z "$(systemctl show smartplan-plan-import.service --property=Environment --value)" ]] || fail 'Unerwartete direkte Dienstumgebung.'
systemd-analyze verify "$smartplan_unit"
smartplan_done=1
echo 'Lokaler Importdienst vorbereitet; noch nicht gestartet oder aktiviert.'
echo 'Vor echten Plänen die dokumentierte systemd-/ARM64-Serverabnahme durchführen.'
