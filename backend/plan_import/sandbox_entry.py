"""Recognize on bounded private tmpfs, export only two pre-opened host inodes."""
import os
import stat
import sys

from .process import main, _limit
from .sandbox_protocol import PARSER_STARTED
from .store import MAX_DERIVED_BYTES, MAX_RECOGNITION_BYTES


def _export(name, maximum):
    source = os.open('/output/' + name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        information = os.fstat(source)
        if not stat.S_ISREG(information.st_mode) or not 0 < information.st_size <= maximum:
            raise ValueError('Invalid bounded parser output')
        target = os.open('/export/' + name, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(target).st_mode):
                raise ValueError('Invalid export inode')
            remaining = information.st_size
            while remaining:
                chunk = os.read(source, min(remaining, 65536))
                if not chunk:
                    raise ValueError('Truncated parser output')
                view = memoryview(chunk)
                while view:
                    written = os.write(target, view)
                    if written <= 0:
                        raise OSError('Export did not progress')
                    view = view[written:]
                remaining -= len(chunk)
            os.fsync(target)
        finally:
            os.close(target)
    finally:
        os.close(source)


def run():
    _limit()
    # A native decoder crash must fail this document and let the queue advance;
    # a failed namespace/interpreter bootstrap must instead preserve its attempt.
    try:
        descriptor = os.open('/export/result.json', os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'wb') as receipt:
            receipt.write(PARSER_STARTED)
            receipt.flush()
            os.fsync(receipt.fileno())
    except OSError:
        return 2
    result = main()
    if result == 0:
        try:
            _export('preview.png', MAX_DERIVED_BYTES)
            _export('result.json', MAX_RECOGNITION_BYTES)
        except (OSError, ValueError):
            return 2
    return result


if __name__ == '__main__':
    sys.exit(run())
