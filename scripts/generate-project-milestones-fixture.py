#!/usr/bin/env python3
"""Generate shared client contracts by running the real milestone domain."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from test_project_milestones import MilestoneFixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'app/test/fixtures/project_milestones.json')
    args = parser.parse_args()
    counter = 100

    def identifier():
        nonlocal counter
        counter += 1
        return uuid.UUID(int=counter)

    with tempfile.TemporaryDirectory(prefix='synthetic-milestone-fixture-') as temporary, patch('uuid.uuid4', identifier):
        fixture = MilestoneFixture(temporary)
        try:
            value = fixture.export()
            value.update(user_id=value['actor']['id'], team=value['workspace']['team'],
                         commands=[value[key] for key in ('create_command', 'update_command', 'cancel_command', 'reopen_command')],
                         records=[value[key] for key in ('created', 'updated', 'cancelled', 'reopened')])
        finally:
            fixture.office.db.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
