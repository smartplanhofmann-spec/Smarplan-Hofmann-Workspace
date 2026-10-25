"""Explicit offline dependency update of the existing private Windows venv.

Stdlib only: no backend imports, no database/config creation, no downloads and
no Python installation. Packaging also reuses the read-only wheel validators.
"""
from email.parser import BytesParser
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import sysconfig
import zipfile

MANIFEST = 'WHEELS_SHA256.json'
TARGET = 'cpython-3.12-win_amd64'


def _name(value):
    return re.sub(r'[-_.]+', '-', value).lower()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def locked_versions(lock):
    result = {}
    for line in Path(lock).read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)', line)
        _require(match, 'Abhaengigkeitsdatei muss ausschliesslich feste Name==Version-Eintraege enthalten.')
        key = _name(match[1])
        _require(key not in result, 'Doppelter Abhaengigkeitseintrag: ' + key)
        result[key] = match[2]
    _require(bool(result) and 'tzdata' in result, 'Abhaengigkeitsdatei ist unvollstaendig; tzdata fehlt.')
    return result


def _compatible_tag(tag):
    parts = tag.split('-')
    if len(parts) != 3:
        return False
    interpreters, abi, platform = (value.split('.') for value in parts)
    for interpreter in interpreters:
        if interpreter in ('py3', 'py312') and 'none' in abi and ('any' in platform or 'win_amd64' in platform):
            return True
        match = re.fullmatch(r'cp3([0-9]+)', interpreter)
        if match and 'win_amd64' in platform:
            minor = int(match[1])
            if minor == 12 and 'cp312' in abi or 2 <= minor <= 12 and 'abi3' in abi:
                return True
    return False


def wheel_manifest(wheels_dir, lock):
    """Validate a complete lock-bound binary wheelhouse without installing it."""
    directory, lock = Path(wheels_dir), Path(lock)
    _require(directory.is_dir() and not directory.is_symlink(), 'Offlineordner python-wheels fehlt; vollstaendiges Windows-Paket laden.')
    pins = locked_versions(lock)
    found, hashes = {}, {}
    for wheel in sorted(directory.iterdir()):
        if wheel.name == MANIFEST:
            _require(wheel.is_file() and not wheel.is_symlink(), 'Ungueltiges Wheelmanifest.')
            continue
        _require(wheel.is_file() and not wheel.is_symlink() and wheel.suffix == '.whl', 'Nur binaere .whl-Dateien im Offlineordner erlaubt.')
        _require(0 < wheel.stat().st_size <= 60 * 1024 * 1024, 'Wheeldatei ist leer oder zu gross.')
        parts = wheel.name[:-4].split('-')
        _require(len(parts) in (5, 6) and _compatible_tag('-'.join(parts[-3:])), 'Wheel passt nicht zu Windows x64 / Python 3.12: ' + wheel.name)
        try:
            with zipfile.ZipFile(wheel) as archive:
                entries = archive.infolist()
                _require(len(entries) <= 10000 and sum(item.file_size for item in entries) <= 200 * 1024 * 1024, 'Wheelinhalt ist zu gross.')
                _require(len({item.filename for item in entries}) == len(entries), 'Doppelte Wheeldateipfade.')
                for item in entries:
                    path = PurePosixPath(item.filename)
                    _require(not path.is_absolute() and '..' not in path.parts and '\\' not in item.filename
                             and not re.match(r'^[A-Za-z]:', item.filename)
                             and (item.external_attr >> 16) & 0o170000 != 0o120000, 'Unsicherer Wheeldateipfad.')
                metadata_paths = [item.filename for item in entries if item.filename.endswith('.dist-info/METADATA')]
                _require(len(metadata_paths) == 1, 'Eindeutige Wheel-Metadaten fehlen.')
                metadata_path = metadata_paths[0]
                _require(archive.getinfo(metadata_path).file_size <= 2 * 1024 * 1024, 'Wheel-Metadaten sind zu gross.')
                metadata = BytesParser().parsebytes(archive.read(metadata_path))
                name, version = metadata.get('Name'), metadata.get('Version')
                _require(isinstance(name, str) and isinstance(version, str), 'Wheelname oder Version fehlt.')
                key = _name(name)
                _require(key in pins and pins[key] == version, 'Wheelversion passt nicht zur Abhaengigkeitsdatei: ' + key)
                _require(_name(parts[0]) == key and parts[1] == version, 'Wheeldateiname passt nicht zu seinen Metadaten.')
                _require(key not in found, 'Mehrere Wheels fuer dieselbe Abhaengigkeit: ' + key)
                wheel_path = metadata_path.rsplit('/', 1)[0] + '/WHEEL'
                _require(archive.getinfo(wheel_path).file_size <= 10000, 'WHEEL-Metadaten sind zu gross.')
                metadata_tags = BytesParser().parsebytes(archive.read(wheel_path)).get_all('Tag', [])
                _require(any(_compatible_tag(tag) for tag in metadata_tags), 'WHEEL-Metadaten passen nicht zu Windows x64 / Python 3.12.')
        except (zipfile.BadZipFile, KeyError, OSError) as error:
            raise ValueError('Ungueltige Wheeldatei: ' + wheel.name) from error
        found[key] = version
        hashes[wheel.name] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    _require(found == pins, 'Offline-Wheels fehlen fuer: ' + ', '.join(sorted(set(pins) - set(found))))
    return {'schema_version': 1, 'target': TARGET, 'requirements_sha256': hashlib.sha256(lock.read_bytes()).hexdigest(),
            'versions': pins, 'files_sha256': hashes}


def verify_wheel_manifest(wheels_dir, lock):
    manifest = Path(wheels_dir) / MANIFEST
    _require(manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size <= 100000, 'Offline-Pruefsummenmanifest fehlt.')
    try:
        expected = json.loads(manifest.read_text(encoding='utf-8'))
    except (ValueError, OSError) as error:
        raise ValueError('Offline-Pruefsummenmanifest ist unlesbar.') from error
    actual = wheel_manifest(wheels_dir, lock)
    _require(actual == expected, 'Offline-Pruefsumme oder Abhaengigkeitsversion stimmt nicht; vollstaendiges Paket erneut entpacken.')
    return actual


def _verify_private_interpreter():
    _require(os.name == 'nt' and sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8
             and sysconfig.get_platform().replace('-', '_') == 'win_amd64',
             'Dieses Offlinepaket benoetigt die bestehende Windows-x64-Python-3.12-Umgebung.')
    local = os.environ.get('LOCALAPPDATA')
    _require(bool(local) and Path(local).is_absolute(), 'Privater LOCALAPPDATA-Ordner fehlt.')
    expected = (Path(local) / 'SmartplanOffice' / '.venv').resolve()
    _require(Path(sys.prefix).resolve() == expected and sys.prefix != sys.base_prefix
             and Path(sys.executable).resolve() == (expected / 'Scripts/python.exe').resolve(),
             'Nur die bestehende private Smartplan-Python-Umgebung darf aktualisiert werden.')
    return expected


@contextmanager
def _installation_lock(home):
    """Share the starter's OS lock; a stale filename alone is not an active app."""
    with (Path(home) / 'office.lock').open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # Portable synthetic lock regression; main rejects non-Windows.
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Smartplan oder die Sicherung laeuft noch; App und Startfenster zuerst schliessen.') from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)


def update_existing_environment(package, *, run=subprocess.run):
    """No pip action occurs until platform, private venv and all wheels pass."""
    package = Path(package).resolve()
    expected = _verify_private_interpreter()
    lock = package / 'backend/requirements.lock'
    if not lock.is_file():
        lock = package.parent / 'backend/requirements.lock'
    wheels = package / 'python-wheels'
    if not wheels.is_dir() and package.name == 'windows':
        wheels = package.parent / 'python-wheels'
    manifest = verify_wheel_manifest(wheels, lock)
    safe_names = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP', 'LOCALAPPDATA', 'USERPROFILE', 'PATHEXT'}
    environment = {key: value for key, value in os.environ.items() if key.upper() in safe_names}
    environment['PIP_CONFIG_FILE'] = os.devnull
    pip = [sys.executable, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check', '--no-input', '--require-virtualenv']
    # A separate isolated process tests the interpreter exactly as the starter
    # will use it. No backend import can open/migrate a business database.
    code = ("import importlib.metadata as m,json,sys; import tzdata; from zoneinfo import ZoneInfo; "
            "ZoneInfo('Europe/Berlin'); pins=json.loads(sys.argv[1]); "
            "assert all(m.version(name)==version for name,version in pins.items()), 'Abhaengigkeitsversion weicht ab'; "
            "print('Python-Abhaengigkeiten und Europe/Berlin erfolgreich geprueft.')")
    with _installation_lock(expected.parent):
        run([*pip, 'install', '--no-index', '--no-deps', '--no-cache-dir', '--only-binary=:all:',
             '--find-links', str(wheels), '--requirement', str(lock)], env=environment, check=True, timeout=240)
        run([*pip, 'check'], env=environment, check=True, timeout=45)
        run([sys.executable, '-I', '-X', 'utf8', '-c', code, json.dumps(manifest['versions'], sort_keys=True)],
            env=environment, check=True, timeout=45)


def main():
    try:
        update_existing_environment(Path(__file__).parent)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('Offline-Update nicht abgeschlossen: ' + str(error), file=sys.stderr)
        return 1
    print('Vorhandene Python-Umgebung aktualisiert. Geschaeftsdaten und Startkonfiguration wurden nicht geoeffnet.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
