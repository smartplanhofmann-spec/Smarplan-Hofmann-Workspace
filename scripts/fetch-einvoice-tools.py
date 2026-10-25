"""Explicit operator/CI setup; never called by an invoice HTTP request.

Fixed upstream releases, mandatory SHA-256, bounded downloads, safe extraction.
No customer data or application secrets are sent to these public sources.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import urllib.request
import zipfile


ASSETS = (
    ('validator-1.6.3-standalone.jar',
     'https://github.com/itplr-kosit/validator/releases/download/v1.6.3/validator-1.6.3-standalone.jar',
     '799e64befca97d4080e03608c80b85dd5a5ecc5f4ae4f35d1116ec2855b9a7c9'),
    ('xrechnung-3.0.2-validator-configuration-2026-08-31.zip',
     'https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/v2026-08-31/xrechnung-3.0.2-validator-configuration-2026-08-31.zip',
     '2530cd107c414511c5d0462ec10f886910395abfca820db82e83d70bf01221a8'),
    ('Mustang-CLI-2.26.0.jar',
     'https://github.com/ZUGFeRD/mustangproject/releases/download/core-2.26.0/Mustang-CLI-2.26.0.jar',
     '42d7868cb68264874a7b8cab4c3587b03b23ccc7cd72373da917f66758bb9736'),
    ('verapdf-cli-1.30.3.jar',
     'https://repo.maven.apache.org/maven2/org/verapdf/apps/cli/1.30.3/cli-1.30.3.jar',
     '4c8acbaeb16405456c8d6d76deac8cf40d94618cb4e33aedf44e51ee1b68be91'),
)
CONFIG_NAME = 'xrechnung-3.0.2-2026-08-31'
CONFIG_SHA = 'a85e078104dd621e1cf39d4674878c046a6cec1d8b3d34cf187aa279d19712db'
MAX_DOWNLOAD = 80 * 1024 * 1024


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(directory, name, url, expected):
    destination = directory / name
    if destination.is_symlink():
        raise ValueError('Keine Werkzeugverknüpfung erlaubt.')
    if destination.exists():
        if not destination.is_file() or digest(destination) != expected:
            raise ValueError('Vorhandene Werkzeugdatei weicht von der freigegebenen Version ab: ' + name)
        return destination
    with tempfile.NamedTemporaryFile(dir=directory, prefix='.download-', delete=False) as target:
        temporary = Path(target.name)
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Smartplan-Explicit-Tool-Setup/1'})
            deadline = time.monotonic() + 120
            with urllib.request.urlopen(request, timeout=45) as response:
                size = 0
                read = getattr(response, 'read1', response.read)
                while block := read(128 * 1024):
                    if time.monotonic() > deadline:
                        raise ValueError('Zeitlimit des Werkzeugdownloads überschritten.')
                    size += len(block)
                    if size > MAX_DOWNLOAD:
                        raise ValueError('Werkzeugdownload überschreitet das Limit.')
                    target.write(block)
            target.flush()
            os.fsync(target.fileno())
            if digest(temporary) != expected:
                raise ValueError('Werkzeugprüfsumme abgelehnt: ' + name)
            temporary.chmod(0o644)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination


def configuration_digest(directory):
    entries = []
    total = 0
    for source in sorted(directory.rglob('*')):
        if source.is_symlink():
            raise ValueError('Keine Konfigurationsverknüpfung erlaubt.')
        if source.is_file():
            total += source.stat().st_size
            if total > 64 * 1024 * 1024 or len(entries) >= 97:
                raise ValueError('Konfigurationslimit überschritten.')
            entries.append((source.relative_to(directory).as_posix(), digest(source)))
    return hashlib.sha256(json.dumps(entries, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def extract_configuration(source, destination):
    if destination.is_symlink():
        raise ValueError('Keine Konfigurationsverknüpfung erlaubt.')
    if destination.exists():
        if configuration_digest(destination) != CONFIG_SHA:
            raise ValueError('Vorhandene XRechnung-Konfiguration wurde verändert.')
        return
    with tempfile.TemporaryDirectory(prefix='.config-', dir=destination.parent) as temporary:
        stage = Path(temporary) / CONFIG_NAME
        stage.mkdir()
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            if len(members) > 150 or sum(item.file_size for item in members) > 64 * 1024 * 1024:
                raise ValueError('Archivlimit überschritten.')
            seen = set()
            for item in members:
                path = PurePosixPath(item.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in item.filename or
                        not path.parts or item.filename in seen or
                        stat.S_ISLNK(item.external_attr >> 16)):
                    raise ValueError('Unsicherer Archivpfad.')
                seen.add(item.filename)
                target = stage.joinpath(*path.parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as incoming, target.open('xb') as outgoing:
                        shutil.copyfileobj(incoming, outgoing)
                    target.chmod(0o644)
        if configuration_digest(stage) != CONFIG_SHA:
            raise ValueError('Vollständige offizielle Konfiguration stimmt nicht überein.')
        stage.replace(destination)


def setup(directory):
    directory = Path(directory).absolute()
    if any(part.is_symlink() for part in (directory, *directory.parents)):
        raise ValueError('Kein Werkzeugpfad über Verknüpfungen.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o755)
    for asset in ASSETS:
        download(directory, *asset)
    extract_configuration(directory / ASSETS[1][0], directory / CONFIG_NAME)
    return {
        'SMARTPLAN_KOSIT_JAR': str(directory / ASSETS[0][0]),
        'SMARTPLAN_KOSIT_SCENARIOS': str(directory / CONFIG_NAME / 'scenarios.xml'),
        'SMARTPLAN_MUSTANG_JAR': str(directory / ASSETS[2][0]),
        'SMARTPLAN_VERAPDF_JAR': str(directory / ASSETS[3][0]),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--github-env', type=Path)
    arguments = parser.parse_args()
    values = setup(arguments.directory)
    if arguments.github_env:
        if any('\n' in value or '\r' in value for value in values.values()):
            raise ValueError('Ungültiger Umgebungsdateipfad.')
        with arguments.github_env.open('a', encoding='utf-8') as stream:
            for name, value in values.items():
                stream.write(name + '=' + value + '\n')
    print(json.dumps(values, ensure_ascii=False, indent=2))
