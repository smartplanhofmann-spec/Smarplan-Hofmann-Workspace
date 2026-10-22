#!/usr/bin/env bash
# First installation only; never exposes or restarts the private pilot service.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
smartplan_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
smartplan_repo="$(cd -- "$smartplan_source/../../.." && pwd)"
smartplan_unit=/etc/systemd/system/smartplan-https.service
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
[[ "$smartplan_repo" == /opt/smartplan-test ]] || fail 'Erwarteter Checkout: /opt/smartplan-test.'
[[ -d /run/systemd/system ]] || fail 'Ein laufendes systemd wird benötigt.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Geprüftes Ziel: Ubuntu 24.04 LTS.'
[[ "$(stat -c %u "$smartplan_repo")" == 0 ]] || fail 'Der Checkout muss root gehören.'
git -C "$smartplan_repo" diff --quiet -- deploy/hetzner/https || fail 'Lokale HTTPS-Änderungen zuerst prüfen.'
git -C "$smartplan_repo" diff --cached --quiet -- deploy/hetzner/https || fail 'Vorgemerkte HTTPS-Änderungen zuerst prüfen.'
for smartplan_command in python3 curl tar sha512sum systemd-analyze ss ip; do
  command -v "$smartplan_command" >/dev/null || fail "Werkzeug fehlt: $smartplan_command"
done
# Avoid replacing any existing installation, including a partially completed one.
for smartplan_path in "$smartplan_unit" /opt/smartplan-https /etc/smartplan-https /usr/share/smartplan-setup /var/lib/smartplan-https; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Bereits vorhanden; vor Wiederholung prüfen: $smartplan_path"
done
! getent passwd smartplan-https >/dev/null || fail 'Dienstkonto existiert bereits; zuerst Installation prüfen.'
! getent group smartplan-https >/dev/null || fail 'Dienstgruppe existiert bereits; zuerst Installation prüfen.'
[[ "$(systemctl show smartplan-https.service --property=LoadState --value)" == not-found ]] || fail 'Vorhandene HTTPS-Unit zuerst prüfen.'
[[ -z "$(ss -H -ltn '( sport = :80 or sport = :443 )')" ]] || fail 'Port 80 oder 443 ist belegt; kein Dienst wird gestoppt.'

# All DNS answers must belong to this VM; stray AAAA records can break ACME.
python3 "$smartplan_source/check-dns.py"
systemd-analyze verify "$smartplan_source/smartplan-https.service"
smartplan_tmp="$(mktemp -d)"
trap 'rm -rf -- "$smartplan_tmp"' EXIT
bash "$smartplan_source/fetch-caddy.sh" "$smartplan_tmp"
# Adapt before changing the system; this does not start a server or request certificates.
"$smartplan_tmp/caddy" adapt --config "$smartplan_source/Caddyfile" --adapter caddyfile > /dev/null

useradd --system --user-group --no-create-home --home-dir /var/lib/smartplan-https \
  --shell /usr/sbin/nologin smartplan-https
install -d -m 0755 /opt/smartplan-https /opt/smartplan-https/bin /etc/smartplan-https /usr/share/smartplan-setup
install -m 0755 "$smartplan_tmp/caddy" /opt/smartplan-https/bin/caddy
install -m 0644 "$smartplan_source/Caddyfile" /etc/smartplan-https/Caddyfile
install -m 0644 "$smartplan_source/index.html" "$smartplan_source/style.css" /usr/share/smartplan-setup/
install -d -m 0700 -o smartplan-https -g smartplan-https /var/lib/smartplan-https
runuser -u smartplan-https -- env XDG_DATA_HOME=/var/lib/smartplan-https \
  XDG_CONFIG_HOME=/var/lib/smartplan-https/config \
  /opt/smartplan-https/bin/caddy validate --config /etc/smartplan-https/Caddyfile --adapter caddyfile
install -m 0644 "$smartplan_source/smartplan-https.service" "$smartplan_unit"
systemctl daemon-reload
systemctl enable --now smartplan-https.service
systemctl status smartplan-https.service --no-pager --full
echo 'HTTPS-Dienst gestartet. Die Zertifikatsausstellung ist erst mit erfolgreichem HTTPS-Abruf bestätigt.'
echo 'TCP 80/443 müssen in der Hetzner-Firewall öffentlich erlaubt sein. Port 8765 bleibt geschlossen.'
echo 'Danach im Browser prüfen: https://office.smartplan-hofmann.de'
