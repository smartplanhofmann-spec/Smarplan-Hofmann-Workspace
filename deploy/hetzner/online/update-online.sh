#!/usr/bin/env bash
# Update the existing online pilot without replacing its database or vault key.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
[[ "$smartplan_repo" == /opt/smartplan-test && -d /run/systemd/system ]] || fail 'Erwartet: vorhandener systemd-Testserver /opt/smartplan-test.'
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
[[ -z "$(git -C "$smartplan_repo" status --porcelain -- backend deploy/hetzner)" ]] || fail 'Lokale Quelländerungen zuerst prüfen.'
for smartplan_required in /etc/smartplan-online/service.env /var/lib/smartplan-online/vault.key /opt/smartplan-online/SOURCE_COMMIT; do
  [[ -f "$smartplan_required" && ! -L "$smartplan_required" ]] || fail "Vorhandene Installation zuerst prüfen: $smartplan_required"
done
[[ -d /opt/smartplan-online/app/backend && -x /opt/smartplan-online/venv/bin/python ]] || fail 'Vorhandene Online-Installation fehlt.'
systemctl is-active --quiet smartplan-online.service || fail 'Online-Dienst muss vor dem Update laufen.'
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Speichereinrichtung läuft bereits.'

smartplan_commit="$(git -C "$smartplan_repo" rev-parse HEAD)"
[[ "$smartplan_commit" =~ ^[a-f0-9]{40}$ ]] || fail 'Ungültiger Quellstand.'
smartplan_release="/opt/smartplan-online/releases/${smartplan_commit}-$(date -u +%Y%m%dT%H%M%S)-$$"
smartplan_previous_app="$(readlink -f /opt/smartplan-online/app)"
smartplan_previous_venv="$(readlink -f /opt/smartplan-online/venv)"
smartplan_previous_commit="$(cat /opt/smartplan-online/SOURCE_COMMIT)"
[[ "$smartplan_previous_commit" =~ ^[a-f0-9]{40}$ ]] || fail 'Installierten Quellstand zuerst prüfen.'
for smartplan_path in "$smartplan_previous_app" "$smartplan_previous_venv"; do
  [[ "$smartplan_path" == /opt/smartplan-online/* && "$(stat -c %u "$smartplan_path")" == 0 ]] || fail 'Installierte Codepfade zuerst prüfen.'
done

# Install into its final path: virtual-environment executable shebangs stay valid.
install -d -m 0755 /opt/smartplan-online/releases "$smartplan_release" "$smartplan_release/app"
(
  umask 0022
  git -C "$smartplan_repo" archive HEAD backend | tar -x -C "$smartplan_release/app"
  python3 -m venv "$smartplan_release/venv"
  "$smartplan_release/venv/bin/python" -m pip install --requirement "$smartplan_release/app/backend/online/requirements.lock"
  "$smartplan_release/venv/bin/python" -m pip check
  "$smartplan_release/venv/bin/python" -m compileall -q "$smartplan_release/app/backend"
)
(
  cd "$smartplan_release/app/backend"
  "$smartplan_release/venv/bin/python" -c 'import online.web, online.store'
)
# Existing backup unit runs the installed, previously accepted backup implementation.
systemctl start smartplan-online-backup.service

smartplan_switched=0
smartplan_stopped=0
smartplan_app_legacy=""
smartplan_venv_legacy=""
smartplan_restore_link() {
  local smartplan_link="$1" smartplan_target="$2" smartplan_temp="$1.update-$$"
  rm -f -- "$smartplan_temp"
  ln -s -- "$smartplan_target" "$smartplan_temp"
  mv -Tf -- "$smartplan_temp" "$smartplan_link"
}
smartplan_restore() {
  local smartplan_result=$?
  trap - EXIT INT TERM
  set +e
  if (( smartplan_result != 0 && smartplan_stopped )); then
    echo 'Update fehlgeschlagen; vorherigen Code wiederherstellen.' >&2
    systemctl stop smartplan-online.service || true
    if [[ -n "$smartplan_app_legacy" ]]; then
      rm -f -- /opt/smartplan-online/app
      mv -- "$smartplan_app_legacy" /opt/smartplan-online/app
    elif (( smartplan_switched )); then
      smartplan_restore_link /opt/smartplan-online/app "$smartplan_previous_app"
    fi
    if [[ -n "$smartplan_venv_legacy" ]]; then
      rm -f -- /opt/smartplan-online/venv
      mv -- "$smartplan_venv_legacy" /opt/smartplan-online/venv
    elif (( smartplan_switched )); then
      smartplan_restore_link /opt/smartplan-online/venv "$smartplan_previous_venv"
    fi
    printf '%s\n' "$smartplan_previous_commit" > /opt/smartplan-online/SOURCE_COMMIT.update
    chmod 0644 /opt/smartplan-online/SOURCE_COMMIT.update
    mv -f -- /opt/smartplan-online/SOURCE_COMMIT.update /opt/smartplan-online/SOURCE_COMMIT
    if ! systemctl restart smartplan-online.service; then
      echo 'Vorherigen Dienst nicht neu gestartet; systemctl status smartplan-online.service prüfen.' >&2
    fi
  fi
  exit "$smartplan_result"
}
trap smartplan_restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

systemctl stop smartplan-online.service
smartplan_stopped=1
# The first update retains the initial installation directories for rollback.
if [[ ! -L /opt/smartplan-online/app ]]; then
  smartplan_app_legacy="/opt/smartplan-online/app.before-${smartplan_commit}-$$"
  mv -- /opt/smartplan-online/app "$smartplan_app_legacy"
fi
if [[ ! -L /opt/smartplan-online/venv ]]; then
  smartplan_venv_legacy="/opt/smartplan-online/venv.before-${smartplan_commit}-$$"
  mv -- /opt/smartplan-online/venv "$smartplan_venv_legacy"
fi
smartplan_switched=1
smartplan_restore_link /opt/smartplan-online/app "$smartplan_release/app"
smartplan_restore_link /opt/smartplan-online/venv "$smartplan_release/venv"
printf '%s\n' "$smartplan_commit" > /opt/smartplan-online/SOURCE_COMMIT.update
chmod 0644 /opt/smartplan-online/SOURCE_COMMIT.update
mv -f -- /opt/smartplan-online/SOURCE_COMMIT.update /opt/smartplan-online/SOURCE_COMMIT
systemctl start smartplan-online.service
smartplan_ready=0
for smartplan_attempt in {1..15}; do
  if curl --fail --silent --max-time 3 -H 'Host: office.smartplan-hofmann.de' \
    -H 'X-Forwarded-Proto: https' http://127.0.0.1:8766/ready | \
    python3 -c 'import json,sys; v=json.load(sys.stdin); assert v.get("status")=="ok" and v.get("database")=="ok"' 2>/dev/null; then
    smartplan_ready=1
    break
  fi
  sleep 1
done
(( smartplan_ready )) || fail 'Bereitschaftsprüfung fehlgeschlagen.'
systemctl is-active --quiet smartplan-online.service || fail 'Dienst nach Update nicht aktiv.'
smartplan_stopped=0
echo "Online-Code aktualisiert: $smartplan_commit"
echo 'Datenbank, MFA-Tresorschlüssel, bestehende Berichte und HTTPS-Konfiguration wurden erhalten.'
echo 'Vorherige Codeverzeichnisse bleiben für eine spätere Rückkehr erhalten.'
