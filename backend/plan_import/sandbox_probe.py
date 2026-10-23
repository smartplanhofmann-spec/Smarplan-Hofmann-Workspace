"""Synthetic startup acceptance inside the exact production parser namespace."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
from importlib.metadata import version

from .process import _limit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ocr-languages', required=True)
    parser.add_argument('--host-namespaces', required=True)
    args = parser.parse_args()
    _limit()
    host = json.loads(args.host_namespaces)
    for name in ('net', 'pid', 'mnt'):
        if os.readlink('/proc/self/ns/' + name) == host[name]:
            raise RuntimeError('Namespace isolation missing')
    for path in ('/etc/smartplan-online', '/var/lib/smartplan-online', '/run/postgresql',
                 '/var/run/postgresql', '/home', '/root'):
        if Path(path).exists():
            raise RuntimeError('Host-private path is visible')
    if any(name in os.environ for name in ('SMARTPLAN_DATABASE_DSN', 'SMARTPLAN_VAULT_KEY_FILE',
                                           'HTTP_PROXY', 'HTTPS_PROXY', 'LD_PRELOAD', 'PYTHONHOME')):
        raise RuntimeError('Inherited host environment')
    if Path('/input/source.bin').read_bytes() != b'Synthetic sandbox startup probe':
        raise RuntimeError('Source mount missing')
    for path in ('/input/source.bin', '/runtime/pyvenv.cfg', '/app/plan_import/__init__.py'):
        try:
            descriptor = os.open(path, os.O_WRONLY)
        except OSError:
            continue
        else:
            os.close(descriptor)
            raise RuntimeError('Read-only mount is writable')
    for path, maximum in (('/tmp', 128 * 1024 * 1024), ('/output', 96 * 1024 * 1024)):
        filesystem = os.statvfs(path)
        if filesystem.f_blocks * filesystem.f_frsize > maximum:
            raise RuntimeError('Unbounded temporary filesystem')
    if ctypes.CDLL(None, use_errno=True).unshare(0x10000000) == 0:
        raise RuntimeError('Nested user namespaces remain enabled')
    import cv2
    import numpy
    import PIL.Image
    import pypdfium2
    for line in (Path(__file__).parent / 'requirements.lock').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        package, required = line.split('==')
        if version(package) != required:
            raise RuntimeError('Installed parser dependencies do not match the source lock')
    from .recognize import _language_selection
    _, selected, warnings = _language_selection('tesseract', args.ocr_languages, 5)
    if warnings:
        raise RuntimeError('Configured local OCR languages are not installed')
    print(json.dumps({'ready': True, 'sandboxed': True, 'languages': selected,
                      'namespaces': ['net', 'pid', 'mnt'], 'temporary_storage_bounded': True}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
