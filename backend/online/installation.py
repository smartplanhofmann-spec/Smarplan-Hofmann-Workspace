"""Bounded, immutable packaging metadata; never infer installation from a checkout."""
import argparse
import json
import os
from pathlib import Path
import re
import stat


MARKER = Path(__file__).with_name('BUILD_SOURCE.json')
COMMIT = re.compile(r'[0-9a-f]{40}')


def _unique_pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate installation metadata key')
        value[key] = item
    return value


def read_context(path=None):
    unknown = dict(schema_version=1, status='unrecorded', source_commit=None)
    target = MARKER if path is None else Path(path)
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022
                    or not 0 < info.st_size <= 1024):
                return unknown
            raw = stream.read(1025)
        if len(raw) > 1024:
            return unknown
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs)
        if (not isinstance(value, dict) or set(value) != {'schema_version', 'source_commit'}
                or type(value['schema_version']) is not int or value['schema_version'] != 1
                or not isinstance(value['source_commit'], str)
                or not COMMIT.fullmatch(value['source_commit'])):
            return unknown
        return dict(schema_version=1, status='recorded', source_commit=value['source_commit'])
    except (OSError, ValueError, UnicodeError):
        return unknown


def write_context(path, commit):
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError('Explicit full source commit required')
    value = dict(schema_version=1, source_commit=commit)
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    # Packaging creates a new release. A previous marker must not be replaced.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return value


def main():
    parser = argparse.ArgumentParser(description='Record exact archived source before starting a new release')
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    write_context(MARKER, args.commit)


if __name__ == '__main__':
    main()
