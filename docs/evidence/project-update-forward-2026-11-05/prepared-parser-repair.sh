#!/usr/bin/env bash
# Prepared manual repair; never executed by the cloud assistant.
(
  set -e
  umask 0077
  exec 9>/run/lock/smartplan-online-update.lock
  flock -n 9
  test "$(cat /opt/smartplan-online/SOURCE_COMMIT)" = a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5
  test "$(cat /etc/smartplan-online/UPDATE_IN_PROGRESS)" = activating
  smartplan_repair_journal=/etc/smartplan-online/updates/a93cb4d02eab-20261105T183445-10529
  test "$(cat "$smartplan_repair_journal/phase")" = activating
  test -f /opt/smartplan-plan-import/venv/pyvenv.cfg
  systemctl stop smartplan-plan-import.service
  smartplan_parser_backup=$(mktemp -d /opt/smartplan-plan-import/venv-before-pillow13.XXXXXX)
  cp -a -- /opt/smartplan-plan-import/venv/. "$smartplan_parser_backup/"
  chmod 0700 "$smartplan_parser_backup"
  printf '%s\n' "$smartplan_parser_backup" >> "$smartplan_repair_journal/parser-venv-backups.log"
  printf 'Parser-Sicherung: %s\n' "$smartplan_parser_backup"
  umask 0022
  /opt/smartplan-plan-import/venv/bin/python -m pip --disable-pip-version-check install --only-binary=:all: --no-deps pillow==13.0.0
  /opt/smartplan-plan-import/venv/bin/python -m pip check
  systemctl reset-failed smartplan-plan-import.service
  systemctl start smartplan-plan-import.service || {
    journalctl -u smartplan-plan-import.service -n 30 --no-pager -o short-iso
    exit 1
  }
  sleep 5
  journalctl -u smartplan-plan-import.service -n 20 --no-pager -o short-iso
  systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service
  curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
)
