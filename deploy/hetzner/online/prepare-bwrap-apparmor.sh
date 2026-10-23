#!/usr/bin/env bash
# Prepare Ubuntu's targeted, capability-dropping bubblewrap profile. Never
# disable AppArmor/userns restrictions or replace an operator's existing policy.
set -euo pipefail
umask 0077
fail() { echo "$*" >&2; exit 1; }
(( EUID == 0 && $# == 0 )) || fail 'Die gezielte AppArmor-Vorbereitung benötigt root und keine Argumente.'
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || fail 'Geprüftes Profilziel: Ubuntu 24.04 LTS.'
smartplan_aa_enabled="$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || true)"
smartplan_aa_restriction="$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || true)"
if [[ "$smartplan_aa_enabled" != Y || "$smartplan_aa_restriction" == 0 || -z "$smartplan_aa_restriction" ]]; then
  echo 'Keine aktive AppArmor-Userns-Restriktion erkannt; keine Profiländerung. Der Worker-Doctor bleibt erforderlich.'
  exit 0
fi
[[ "$smartplan_aa_restriction" == 1 ]] || fail 'Unbekannte AppArmor-Userns-Einstellung; keine Änderung.'
[[ -d /run/systemd/system ]] || fail 'Ein vorbereiteter systemd-Server ist erforderlich.'
if [[ -f /proc/sys/kernel/unprivileged_userns_clone ]]; then
  [[ "$(cat /proc/sys/kernel/unprivileged_userns_clone)" == 1 ]] || fail 'Userns ist zusätzlich global gesperrt; diese Vorbereitung ändert keine Sysctls.'
fi
[[ -x /usr/sbin/apparmor_parser ]] || fail 'Zuerst die Ubuntu-Pakete apparmor und apparmor-profiles installieren.'
[[ "$(dpkg-query -W -f='${Status}' apparmor-profiles 2>/dev/null)" == 'install ok installed' ]] || fail 'Das offizielle Ubuntu-Paket apparmor-profiles ist erforderlich.'

/usr/bin/python3 - <<'PY'
import hashlib
import fcntl
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

SOURCE = Path('/usr/share/apparmor/extra-profiles/bwrap-userns-restrict')
TARGET = Path('/etc/apparmor.d/smartplan-bwrap-userns')
PARSER = '/usr/sbin/apparmor_parser'
EXPECTED = '11d39094f044f0cda0febb3ad517b830301da6b2ce929664af09ee9e4dd264f9'
NAMES = {'bwrap', 'unpriv_bwrap'}


def fail(message):
    raise SystemExit(message)


def trusted_regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022 or info.st_nlink != 1:
        fail('Keine unveränderte root-eigene reguläre Profildatei: ' + str(path))
    return path.read_bytes()


def loaded():
    states = {}
    for line in Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines():
        match = re.fullmatch(r'(.+) \(([^)]+)\)', line)
        if match and match[1] in NAMES:
            states[match[1]] = match[2]
    return states


def declares_conflicting_profile(text):
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        named = re.match(r'^profile\s+("[^"]+"|\S+)(.*)$', line)
        if named:
            name = named[1].strip('"')
            if name in NAMES or any(name.startswith(value + '//') for value in NAMES):
                return True
            # Separate a conventional opening body brace from an attachment's
            # /usr/bin/{foo,bwrap} glob. Ignore execution rules inside the body.
            attachment = named[2].split(' {', 1)[0]
            if '/' in attachment and re.search(r'\bbwrap\b', attachment):
                return True
        elif line.startswith(('/', '"/')) and not line.endswith(','):
            # Implicit path attachments may continue on the following line.
            # Ordinary `/usr/bin/bwrap ix,` and `px -> bwrap,` rules end in a
            # comma and do not declare or replace another executable's profile.
            attachment = line.split(' {', 1)[0]
            if re.search(r'\bbwrap\b', attachment):
                return True
    return False


lock = os.open('/run/lock/smartplan-online-update.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
lock_info = os.fstat(lock)
if not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0 or lock_info.st_nlink != 1 or lock_info.st_mode & 0o022:
    fail('Unerwartete gemeinsame Updatesperre; keine Profiländerung.')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    fail('Ein Update oder eine Verwaltung läuft bereits.')
pending = Path('/etc/smartplan-online/UPDATE_IN_PROGRESS')
if pending.exists() or pending.is_symlink():
    fail('Zuerst das offene Updatejournal klären.')
state = subprocess.run(['/usr/bin/systemctl', 'show', 'smartplan-plan-import.service',
                        '--property=ActiveState', '--value'], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
if state.stdout.strip() != 'inactive':
    fail('Der Importdienst muss vor der Profilvorbereitung inaktiv sein.')
source = trusted_regular(SOURCE)
if hashlib.sha256(source).hexdigest() != EXPECTED:
    fail('Das paketierte Bubblewrap-Profil hat einen ungeprüften Inhalt; zuerst unabhängig prüfen.')
package = subprocess.run(['/usr/bin/dpkg-query', '-S', str(SOURCE)], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
if package.stdout.strip() != 'apparmor-profiles: ' + str(SOURCE):
    fail('Die Profildatei ist nicht dem erwarteten Ubuntu-Paket zugeordnet.')
directory = TARGET.parent
information = directory.lstat()
if not stat.S_ISDIR(information.st_mode) or information.st_uid != 0 or information.st_mode & 0o022:
    fail('Das AppArmor-Profilverzeichnis muss ein root-eigenes unverknüpftes Verzeichnis sein.')
existing = TARGET.exists() or TARGET.is_symlink()
if existing and trusted_regular(TARGET) != source:
    fail('Eine abweichende bestehende Smartplan-Profilkonfiguration wird nicht überschrieben.')

# The official profile has optional local includes. Accept no additions, disable
# links, complain links, competing attachments or differently named bwrap policy.
for override in ('local/bwrap-userns-restrict', 'local/unpriv_bwrap'):
    path = directory / override
    if path.exists() or path.is_symlink():
        fail('Bestehende lokale Profilergänzung zuerst prüfen: ' + str(path))
keyword = re.compile(r'\bbwrap\b|\bunpriv_bwrap\b')
for path in directory.rglob('*'):
    if path == TARGET or path.is_dir():
        continue
    if path.parent.name in ('disable', 'force-complain') and keyword.search(path.name):
        fail('Bestehende Bubblewrap-Deaktivierung oder Complain-Konfiguration zuerst prüfen: ' + str(path))
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        continue
    try:
        text = path.read_text()
    except UnicodeError:
        continue
    if declares_conflicting_profile(text):
        fail('Bestehende weitere Bubblewrap-Profildeklaration zuerst prüfen: ' + str(path))
states = loaded()
if states:
    if existing and states == {'bwrap': 'enforce', 'unpriv_bwrap': 'enforce'}:
        print('Das unveränderte offizielle Bubblewrap-Profil ist bereits persistent im Enforce-Modus vorbereitet.')
        raise SystemExit(0)
    fail('Bereits geladene abweichende oder unvollständige Bubblewrap-Profile werden nicht ersetzt.')

# Compile without kernel/cache changes first. --add is deliberately used below:
# an existing loaded profile is an error, never a reason to replace its policy.
subprocess.run([PARSER, '--skip-kernel-load', '--skip-read-cache', '--skip-cache', str(SOURCE)], check=True, timeout=15)
if not existing:
    descriptor, name = tempfile.mkstemp(prefix='.smartplan-bwrap-userns-', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            os.fchmod(output.fileno(), 0o644)
            output.write(source)
            output.flush()
            os.fsync(output.fileno())
        # link() commits atomically without overwriting even a late-created path.
        os.link(temporary, TARGET, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
try:
    subprocess.run([PARSER, '--add', '--skip-read-cache', '--skip-cache', str(TARGET)], check=True, timeout=15)
    if loaded() != {'bwrap': 'enforce', 'unpriv_bwrap': 'enforce'}:
        fail('Die neuen Profile sind nicht vollständig im Enforce-Modus geladen.')
except BaseException:
    # Do not remove/replace kernel policy after an ambiguous load result. Keep
    # the exact known file for review/reboot and report failure to the caller.
    print('Profilvorbereitung unvollständig; ausschließlich bekannte neue Datei zur Prüfung behalten: ' + str(TARGET), flush=True)
    raise
print('Offizielles Bubblewrap-Profil persistent vorbereitet; globale AppArmor-/Userns-Einstellungen unverändert. Worker-Doctor und Dienstabnahme noch ausführen.')
PY
