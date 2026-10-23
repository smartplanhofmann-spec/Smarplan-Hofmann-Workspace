#!/usr/bin/env bash
# Trusted operator configuration; secrets are read directly from the terminal.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 )) || fail 'Im SSH-Serverfenster als root ausführen.'
(( $# == 0 )) || fail 'Anschlussdaten ausschließlich interaktiv eingeben.'
[[ -t 0 && -t 1 ]] || fail 'Interaktives SSH-Serverfenster erforderlich.'
[[ -f /etc/smartplan-online/service.env && ! -L /etc/smartplan-online/service.env ]] || fail 'Vorhandene Online-Konfiguration fehlt.'
[[ -f /var/lib/smartplan-online/vault.key ]] || fail 'Vorhandener MFA-Tresorschlüssel fehlt; zuerst Installation prüfen.'
[[ -x /opt/smartplan-online/venv/bin/python ]] || fail 'Vorhandene Online-Installation fehlt.'
exec 9>/run/lock/smartplan-online-update.lock
flock -n 9 || fail 'Ein Update oder eine Speichereinrichtung läuft bereits.'
systemctl is-active --quiet smartplan-online.service || fail 'Online-Dienst muss vor der Einrichtung laufen.'
if [[ -e /etc/smartplan-online/storage.json || -L /etc/smartplan-online/storage.json ]]; then
  [[ -f /etc/smartplan-online/storage.json && ! -L /etc/smartplan-online/storage.json ]] || fail 'Vorhandene Speicherkonfiguration zuerst prüfen.'
fi
smartplan_previous="$(mktemp -d /etc/smartplan-online/.storage-before.XXXXXX)"
install -m 0600 /etc/smartplan-online/service.env "$smartplan_previous/service.env"
smartplan_had_config=0
if [[ -e /etc/smartplan-online/storage.json || -L /etc/smartplan-online/storage.json ]]; then
  install -m 0600 /etc/smartplan-online/storage.json "$smartplan_previous/storage.json"
  smartplan_had_config=1
fi
smartplan_restore_configuration() {
  local smartplan_result=$?
  trap - EXIT INT TERM
  set +e
  if (( smartplan_result != 0 )); then
    local smartplan_changed=0
    cmp -s "$smartplan_previous/service.env" /etc/smartplan-online/service.env || smartplan_changed=1
    if (( smartplan_had_config )); then
      cmp -s "$smartplan_previous/storage.json" /etc/smartplan-online/storage.json || smartplan_changed=1
    elif [[ -e /etc/smartplan-online/storage.json ]]; then
      smartplan_changed=1
    fi
    if (( smartplan_changed )); then
      echo 'Einrichtung abgebrochen; vorherige Speicherkonfiguration wiederherstellen.' >&2
      install -m 0640 -o root -g smartplan-online "$smartplan_previous/service.env" /etc/smartplan-online/service.env
      if (( smartplan_had_config )); then
        install -m 0640 -o root -g smartplan-online "$smartplan_previous/storage.json" /etc/smartplan-online/storage.json
      else
        rm -f -- /etc/smartplan-online/storage.json
      fi
      systemctl restart smartplan-online.service || echo 'Vorherigen Dienst nicht neu gestartet; Dienststatus prüfen.' >&2
    fi
  fi
  rm -rf -- "$smartplan_previous"
  exit "$smartplan_result"
}
trap smartplan_restore_configuration EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

/opt/smartplan-online/venv/bin/python - <<'PY'
import getpass
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

directory = Path('/etc/smartplan-online')
config_path = directory / 'storage.json'
env_path = directory / 'service.env'
service = pwd.getpwnam('smartplan-online')

def read_regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o037:
        raise SystemExit('Konfigurationsdatei zuerst auf Eigentümer und Rechte prüfen.')
    if info.st_size > 65536:
        raise SystemExit('Konfigurationsdatei ist unerwartet groß.')
    return path.read_text()

def atomic_write(path, value, mode=0o640):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        os.fchown(descriptor, 0, service.pw_gid)
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

with open('/dev/tty', 'r+') as terminal:
    def ask(label, default=''):
        terminal.write(label + (f' [{default}]' if default else '') + ': ')
        terminal.flush()
        result = terminal.readline()
        if not result:
            raise SystemExit('Eingabe abgebrochen; keine Konfiguration gespeichert.')
        return result.strip() or default

    try:
        values = json.loads(read_regular(config_path)) if config_path.exists() else {}
    except (ValueError, OSError):
        raise SystemExit('Bestehende Speicherkonfiguration zuerst prüfen.') from None
    if (not isinstance(values, dict) or set(values) - {'server', 'onedrive', 'webdav'} or
            any(not isinstance(value, dict) for value in values.values())):
        raise SystemExit('Bestehende Speicherkonfiguration zuerst prüfen.')
    print('Dokumentablage vorbereiten: 1 = Smartplan-Server, 2 = OneDrive, 3 = Cloud/NAS über WebDAV')
    choice = ask('Auswahl', '1')
    if choice == '1':
        previous = values.get('server', {})
        destination = Path(ask('Dediziertes Dokumentverzeichnis', previous.get('path', '/var/lib/smartplan-online/documents')))
        if not destination.is_absolute() or destination == Path('/') or '..' in destination.parts:
            raise SystemExit('Absolutes dediziertes Verzeichnis erforderlich.')
        if any(parent.is_symlink() for parent in (destination, *destination.parents)):
            raise SystemExit('Dokumentverzeichnis darf keine symbolischen Links enthalten.')
        if destination.parts[1] not in {'var', 'srv', 'mnt', 'media'}:
            raise SystemExit('Dokumentverzeichnis unter /var, /srv, /mnt oder /media verwenden.')
        if not destination.exists():
            destination.mkdir(mode=0o700)
            os.chown(destination, service.pw_uid, service.pw_gid)
        info = destination.stat()
        if not destination.is_dir() or info.st_uid != service.pw_uid or info.st_mode & 0o077:
            raise SystemExit('Dediziertes Verzeichnis muss smartplan-online gehören und Modus 0700 haben.')
        values['server'] = {'path': str(destination)}
    elif choice == '2':
        previous = values.get('onedrive', {})
        client = ask('Microsoft-Anwendungs-ID (Client-ID)', previous.get('client_id', ''))
        try:
            uuid.UUID(client)
        except ValueError:
            raise SystemExit('Client-ID muss eine Microsoft-Anwendungs-UUID sein.')
        secret = getpass.getpass('Microsoft-Client-Secret (ausgeblendet; leer = vorhandenes behalten): ', stream=terminal)
        secret = secret or previous.get('client_secret', '')
        if not 1 <= len(secret) <= 4096 or any(character in secret for character in '\r\n\x00'):
            raise SystemExit('Client-Secret fehlt oder ist ungültig.')
        values['onedrive'] = {'client_id': client, 'client_secret': secret}
    elif choice == '3':
        previous = values.get('webdav', {})
        url = ask('HTTPS-WebDAV-Adresse des Zielordners', previous.get('url', ''))
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
                parsed.query or parsed.fragment or any(character.isspace() for character in url)):
            raise SystemExit('Gültige HTTPS-WebDAV-Adresse ohne Benutzerinfo, Abfrage oder Fragment erforderlich.')
        user = ask('WebDAV-Benutzer', previous.get('username', ''))
        password = getpass.getpass('WebDAV-Passwort/App-Passwort (ausgeblendet; leer = vorhandenes behalten): ', stream=terminal)
        password = password or previous.get('password', '')
        if not user or not password or len(user) > 1024 or len(password) > 4096 or any(c in user + password for c in '\r\n\x00'):
            raise SystemExit('WebDAV-Benutzer und Passwort erforderlich.')
        values['webdav'] = {'url': url, 'username': user, 'password': password}
    else:
        raise SystemExit('Unbekannte Auswahl; keine Konfiguration gespeichert.')

    # Validate the candidate against the installed server's actual schema before
    # replacing either live configuration file. This does not contact a provider.
    sys.path.insert(0, '/opt/smartplan-online/app/backend')
    try:
        from online.storage import load_config
    except ImportError:
        raise SystemExit('Zuerst den Online-Code mit update-online.sh aktualisieren.') from None
    descriptor, candidate = tempfile.mkstemp(prefix='.storage-check.', dir=directory)
    previous_setting = os.environ.get('SMARTPLAN_STORAGE_CONFIG_FILE')
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(values, stream, ensure_ascii=False)
        os.environ['SMARTPLAN_STORAGE_CONFIG_FILE'] = candidate
        try:
            load_config()
        except (RuntimeError, ValueError):
            raise SystemExit('Anschlusskonfiguration wurde vom Server abgewiesen; keine Änderung gespeichert.') from None
    finally:
        if previous_setting is None:
            os.environ.pop('SMARTPLAN_STORAGE_CONFIG_FILE', None)
        else:
            os.environ['SMARTPLAN_STORAGE_CONFIG_FILE'] = previous_setting
        os.unlink(candidate)

    # An existing environment file contains no plaintext Microsoft/WebDAV secret.
    environment = read_regular(env_path)
    filtered = [line for line in environment.splitlines() if not re.match(r'^\s*(?:export\s+)?SMARTPLAN_STORAGE_CONFIG_FILE\s*=', line)]
    filtered.append('SMARTPLAN_STORAGE_CONFIG_FILE=/etc/smartplan-online/storage.json')
    atomic_write(config_path, json.dumps(values, ensure_ascii=False, indent=2) + '\n')
    atomic_write(env_path, '\n'.join(filtered) + '\n')
print('Speicheranschluss vorbereitet. In der App unter Ablage ausdrücklich auswählen.')
PY
systemctl restart smartplan-online.service
systemctl is-active --quiet smartplan-online.service || fail 'Dienst nach Einrichtung nicht aktiv; Status prüfen.'
smartplan_ready=0
for smartplan_attempt in {1..10}; do
  if curl --fail --silent --max-time 3 -H 'Host: office.smartplan-hofmann.de' \
    -H 'X-Forwarded-Proto: https' http://127.0.0.1:8766/ready | \
    python3 -c 'import json,sys; v=json.load(sys.stdin); assert v.get("status")=="ok" and v.get("database")=="ok"' 2>/dev/null; then
    smartplan_ready=1
    break
  fi
  sleep 1
done
(( smartplan_ready )) || fail 'Bereitschaftsprüfung nach Einrichtung fehlgeschlagen.'
echo 'Online-Dienst neu gestartet. Vorhandene Anmeldung und Berichte bleiben erhalten.'
