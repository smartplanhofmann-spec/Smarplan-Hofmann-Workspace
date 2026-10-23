#!/usr/bin/env bash
# Fresh GitHub-hosted VM only. Prepare fixed paths, then exercise the SAME
# synthetic acceptance helper used on the server; never a production database.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted && "${SMARTPLAN_SYSTEMD_IMPORT_CI:-}" == 1 ]] || fail 'Only the explicitly enabled GitHub-hosted systemd CI fixture may run this setup.'
(( EUID == 0 && $# == 0 )) || fail 'Run this CI fixture as root without arguments.'
[[ "$(cat /proc/1/comm)" == systemd && -d /run/systemd/system ]] || fail 'A real systemd PID 1 is required; this is not a container simulation.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'This disposable fixture requires the Ubuntu 24.04 hosted VM.'
[[ "${GITHUB_SHA:-}" =~ ^[a-f0-9]{40}$ && -d "${GITHUB_WORKSPACE:-}/.git" ]] || fail 'A checked-out GitHub source commit is required.'
smartplan_checkout="$(realpath -- "$GITHUB_WORKSPACE")"
smartplan_git() { git -c "safe.directory=$smartplan_checkout" -C "$smartplan_checkout" "$@"; }
[[ "$(smartplan_git rev-parse HEAD)" == "$GITHUB_SHA" ]] || fail 'The checked-out source must equal the workflow commit.'
for smartplan_path in /opt/smartplan-test /opt/smartplan-online /opt/smartplan-plan-import /etc/smartplan-online; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Refusing an existing server path: $smartplan_path"
done
if [[ -e /run/lock/smartplan-online-update.lock || -L /run/lock/smartplan-online-update.lock ]]; then
  # The preceding targeted AppArmor preparation uses the same persistent lock.
  [[ -f /run/lock/smartplan-online-update.lock && ! -L /run/lock/smartplan-online-update.lock &&
     "$(stat -c %u:%h:%s /run/lock/smartplan-online-update.lock)" == 0:1:0 ]] || fail 'An unexpected shared update lock must be reviewed.'
  smartplan_lock_mode="$(stat -c %a /run/lock/smartplan-online-update.lock)"
  (( (8#$smartplan_lock_mode & 8#022) == 0 )) || fail 'The shared update lock must not be group/other writable.'
fi
for smartplan_path in /etc/systemd/system/smartplan-plan-import* /run/systemd/system/smartplan-plan-import*; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Refusing an existing import unit or drop-in: $smartplan_path"
done
! getent passwd smartplan-online >/dev/null || fail 'Refusing an existing service user.'
! getent group smartplan-online >/dev/null || fail 'Refusing an existing service group.'
[[ "$(systemctl show smartplan-plan-import.service --property=LoadState --value)" == not-found ]] || fail 'An existing import unit must never be replaced by this fixture.'

smartplan_nonce="$(/usr/bin/python3 -c 'import secrets; print(secrets.token_hex(16))')"
[[ "$smartplan_nonce" =~ ^[a-f0-9]{32}$ ]] || fail 'Invalid fixture ownership marker.'
smartplan_owner="smartplan-systemd-ci:$smartplan_nonce"
smartplan_created_user=0
smartplan_created_role=0
smartplan_created_unit=0
smartplan_started_postgres=0
smartplan_created_roots=()
smartplan_service_uid=''
smartplan_service_gid=''
smartplan_psql() {
  runuser -u postgres -- /usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 \
    /usr/bin/psql -X --no-password --host=/var/run/postgresql --port=5432 --username=postgres --dbname=postgres --set=ON_ERROR_STOP=1 "$@"
}
smartplan_cleanup() {
  local smartplan_exit=$? smartplan_safe=1 smartplan_path smartplan_comment
  trap - EXIT
  set +e
  if (( smartplan_exit != 0 )); then
    journalctl --no-pager --unit='smartplan-plan-import-accept-*' --lines=100 >&2
  fi
  # The shared helper owns its nonce units/databases. If it retained any for
  # inspection, preserve the runtime too rather than deleting a live resource.
  for smartplan_path in /run/systemd/system/smartplan-plan-import-accept-*.service; do
    if [[ -e "$smartplan_path" || -L "$smartplan_path" ]]; then
      echo "Acceptance helper retained its test unit; preserving disposable fixture: $smartplan_path" >&2
      smartplan_safe=0
    fi
  done
  if (( smartplan_created_unit )); then
    if ! cmp -s /opt/smartplan-test/deploy/hetzner/online/smartplan-plan-import.service /etc/systemd/system/smartplan-plan-import.service ||
       [[ "$(systemctl show smartplan-plan-import.service --property=ActiveState --value)" != inactive ]]; then
      echo 'Unexpected main-unit change/state; preserving the disposable fixture for inspection.' >&2
      smartplan_safe=0
    fi
  fi
  if (( ! smartplan_safe )); then exit 1; fi
  if (( smartplan_created_unit )); then
    rm -- /etc/systemd/system/smartplan-plan-import.service || smartplan_exit=1
    systemctl daemon-reload || smartplan_exit=1
  fi
  if (( smartplan_created_role )); then
    smartplan_comment="$(smartplan_psql -Atc "SELECT shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname='smartplan-online'")"
    if [[ "$smartplan_comment" == "$smartplan_owner" ]]; then
      smartplan_psql -c 'DROP ROLE "smartplan-online"' || smartplan_exit=1
    else
      echo 'Role ownership marker changed; refusing to drop it.' >&2
      smartplan_exit=1
    fi
  fi
  for smartplan_path in "${smartplan_created_roots[@]}"; do
    if [[ -d "$smartplan_path" && ! -L "$smartplan_path" && "$(cat "$smartplan_path/.smartplan-systemd-ci-owner" 2>/dev/null)" == "$smartplan_owner" ]]; then
      rm -rf -- "$smartplan_path" || smartplan_exit=1
    else
      echo "Directory ownership marker changed; refusing cleanup: $smartplan_path" >&2
      smartplan_exit=1
    fi
  done
  if (( smartplan_created_user )); then
    if [[ "$(id -u smartplan-online 2>/dev/null)" == "$smartplan_service_uid" ]]; then
      userdel smartplan-online || smartplan_exit=1
      if getent group smartplan-online >/dev/null; then
        [[ "$(getent group smartplan-online | cut -d: -f3)" == "$smartplan_service_gid" ]] && groupdel smartplan-online || smartplan_exit=1
      fi
    else
      echo 'Service-user identity changed; refusing to remove it.' >&2
      smartplan_exit=1
    fi
  fi
  # The shared management lock is persistent and is never unlinked by a fixture.
  if (( smartplan_started_postgres )); then systemctl stop postgresql@16-main.service || smartplan_exit=1; fi
  exit "$smartplan_exit"
}
trap smartplan_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if ! systemctl is-active --quiet postgresql@16-main.service; then
  smartplan_started_postgres=1
  systemctl start postgresql@16-main.service
fi
smartplan_version="$(smartplan_psql -Atc 'SHOW server_version_num')"
[[ "$smartplan_version" =~ ^16[0-9]{4}$ ]] || fail 'The fixture requires the local PostgreSQL 16 peer socket.'
[[ "$(smartplan_psql -Atc "SELECT count(*) FROM pg_roles WHERE rolname='smartplan-online'")" == 0 ]] || fail 'Refusing an existing PostgreSQL service role.'
[[ "$(smartplan_psql -Atc "SELECT count(*) FROM pg_database WHERE left(datname,length('smartplan_import_accept_'))='smartplan_import_accept_'")" == 0 ]] || fail 'Refusing preexisting acceptance databases.'
useradd --system --user-group --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin smartplan-online
smartplan_created_user=1
smartplan_service_uid="$(id -u smartplan-online)"
smartplan_service_gid="$(id -g smartplan-online)"
smartplan_psql -c 'CREATE ROLE "smartplan-online" LOGIN'
smartplan_created_role=1
smartplan_psql -c "COMMENT ON ROLE \"smartplan-online\" IS '$smartplan_owner'"
for smartplan_path in /opt/smartplan-test /opt/smartplan-online /opt/smartplan-plan-import /etc/smartplan-online; do
  [[ ! -e "$smartplan_path" && ! -L "$smartplan_path" ]] || fail "Path appeared during fixture setup: $smartplan_path"
  mkdir -m 0755 -- "$smartplan_path"
  printf '%s\n' "$smartplan_owner" > "$smartplan_path/.smartplan-systemd-ci-owner"
  smartplan_created_roots+=("$smartplan_path")
done
chmod 0700 /etc/smartplan-online
smartplan_git archive HEAD | tar -x --no-same-owner -C /opt/smartplan-test
mkdir -m 0755 /opt/smartplan-online/app
cp -a /opt/smartplan-test/backend /opt/smartplan-online/app/backend
printf '%s\n' "$GITHUB_SHA" > /opt/smartplan-online/SOURCE_COMMIT
(
  umask 0022
  /usr/bin/python3 -m venv /opt/smartplan-online/venv
  /opt/smartplan-online/venv/bin/python -m pip install --only-binary=:all: \
    -r /opt/smartplan-online/app/backend/requirements.lock -r /opt/smartplan-online/app/backend/online/requirements.lock
  /opt/smartplan-online/venv/bin/python -m pip check
  /usr/bin/python3 -m venv /opt/smartplan-plan-import/venv
  /opt/smartplan-plan-import/venv/bin/python -m pip install --only-binary=:all: -r /opt/smartplan-online/app/backend/plan_import/requirements.lock
  /opt/smartplan-plan-import/venv/bin/python -m pip check
)
# The original unit stays inactive. Its marker DSN is never connected to; the
# shared helper substitutes only a private EnvironmentFile for its new nonce DB.
printf '%s\n' 'SMARTPLAN_DATABASE_DSN="postgresql:///smartplan_ci_unused?host=/var/run/postgresql&user=smartplan-online"' > /etc/smartplan-online/service.env
install -m 0644 /opt/smartplan-test/deploy/hetzner/online/smartplan-plan-import.service /etc/systemd/system/smartplan-plan-import.service
smartplan_created_unit=1
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/smartplan-plan-import.service
timeout 180 /usr/bin/bash /opt/smartplan-test/deploy/hetzner/online/accept-plan-import.sh
[[ "$(systemctl show smartplan-plan-import.service --property=ActiveState --value)" == inactive ]] || fail 'The production-named worker must remain inactive.'
echo 'Exact production-unit restrictions accepted on synthetic PostgreSQL data, including stop/refund/restart/cgroup cleanup.'
