"""Actual Windows proof: existing private venv without tzdata -> offline update.

Runs only against a temporary LOCALAPPDATA, synthetic sentinel data and the
wheelhouse supplied by CI. It never starts Smartplan or accesses user data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def run_probe(wheels_dir):
    if os.name != 'nt' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Die echte Offline-Updaterprobe benoetigt Windows x64 / Python 3.12.')
    with tempfile.TemporaryDirectory(prefix='Smartplan offline update ') as temporary:
        directory = Path(temporary)
        package = directory / 'entpacktes Paket'
        (package / 'backend').mkdir(parents=True)
        shutil.copyfile(ROOT / 'backend/requirements.lock', package / 'backend/requirements.lock')
        for name in ('Python_Umgebung_aktualisieren.cmd', 'Python_Umgebung_aktualisieren.py'):
            shutil.copyfile(ROOT / 'windows' / name, package / name)
        shutil.copytree(wheels_dir, package / 'python-wheels')
        local = directory / 'private Local App Data'
        home = local / 'SmartplanOffice'
        venv = home / '.venv'
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True, timeout=90)
        python = venv / 'Scripts/python.exe'
        interpreter_hash = hashlib.sha256(python.read_bytes()).hexdigest()
        sentinel = home / 'data/office.sqlite3'
        sentinel.parent.mkdir()
        sentinel.write_bytes(b'SYNTHETIC EXISTING DATABASE; MUST NEVER BE OPENED OR MIGRATED')
        config = home / 'start-config.json'
        config.write_text('{"synthetic_existing_configuration":true}', encoding='utf-8')
        protected_before = {path.relative_to(home).as_posix(): path.read_bytes() for path in (sentinel, config)}
        environment = os.environ.copy()
        environment['LOCALAPPDATA'] = str(local)
        environment['PIP_INDEX_URL'] = 'http://127.0.0.1:9/no-network-during-updater'
        environment['PIP_EXTRA_INDEX_URL'] = environment['PIP_INDEX_URL']
        baseline = ("import importlib.util; assert importlib.util.find_spec('tzdata') is None; "
                    "import zoneinfo; zoneinfo.reset_tzpath(()); "
                    "exec(\"try:\\n zoneinfo.ZoneInfo('Europe/Berlin')\\nexcept zoneinfo.ZoneInfoNotFoundError:\\n pass\\nelse:\\n raise AssertionError('Missing-tzdata baseline failed')\")")
        subprocess.run([str(python), '-I', '-c', baseline], env=environment, check=True, timeout=20)
        # cmd /s strips one outer quote pair. Supply it explicitly so the
        # batch path containing spaces reaches cmd intact (shell=False).
        command = (subprocess.list2cmdline([environment.get('COMSPEC', 'cmd.exe')])
                   + ' /d /s /c ""' + str(package / 'Python_Umgebung_aktualisieren.cmd') + '" --no-pause"')
        import msvcrt
        with (home / 'office.lock').open('w+b') as lock:
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                running = subprocess.run(command, cwd=package, env=environment, timeout=60, check=False)
                if running.returncode == 0:
                    raise AssertionError('Running Smartplan must block dependency updates')
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        subprocess.run([str(python), '-I', '-c', baseline], env=environment, check=True, timeout=20)
        tzdata = next((package / 'python-wheels').glob('tzdata-*.whl'))
        contents = tzdata.read_bytes()
        tzdata.unlink()
        missing = subprocess.run(command, cwd=package, env=environment, timeout=60, check=False)
        if missing.returncode == 0:
            raise AssertionError('Incomplete wheelhouse must fail before pip installation')
        subprocess.run([str(python), '-I', '-c', baseline], env=environment, check=True, timeout=20)
        tzdata.write_bytes(contents)
        for _ in range(2):
            subprocess.run(command, cwd=package, env=environment, timeout=330, check=True)
        pins = dict(line.split('==') for line in (package / 'backend/requirements.lock').read_text().splitlines() if line)
        verify = ("import importlib.metadata as m,json,sys; import tzdata,zoneinfo; zoneinfo.reset_tzpath(()); "
                  "zoneinfo.ZoneInfo('Europe/Berlin'); "
                  "assert all(m.version(name)==version for name,version in json.loads(sys.argv[1]).items())")
        subprocess.run([str(python), '-I', '-c', verify, json.dumps(pins)], env=environment, check=True, timeout=20)
        subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', 'check'], env=environment, check=True, timeout=20)
        protected_after = {path.relative_to(home).as_posix(): path.read_bytes() for path in (sentinel, config)}
        if protected_after != protected_before or hashlib.sha256(python.read_bytes()).hexdigest() != interpreter_hash:
            raise AssertionError('Updater changed existing database/configuration/Python interpreter')
        if {path.relative_to(home / 'data').as_posix() for path in (home / 'data').rglob('*')} != {'office.sqlite3'}:
            raise AssertionError('Updater created unexpected business data')
    print('Windows offline update passed: absent tzdata -> complete pinned wheels, pip check, Berlin timezone; no business mutation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels-dir', required=True, type=Path)
    run_probe(parser.parse_args().wheels_dir)
