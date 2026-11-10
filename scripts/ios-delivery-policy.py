#!/usr/bin/env python3
"""Validate an explicit signed iOS delivery selection without Apple access."""
import argparse
import json
import re

ALLOWED_REFS = frozenset({
    'refs/heads/codex/smartplan-office-0.2',
    'refs/heads/codex/testupdate-0.7-projects-20261104',
})


def authorize(*, event, ref, commit, prepare_signed, upload):
    """Fail closed before signing; preparing a package never selects upload."""
    if event != 'workflow_dispatch' or ref not in ALLOWED_REFS:
        raise ValueError('Signierung erfordert einen manuellen Start auf einem freigegebenen Branch')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Vollstaendiger unveraenderlicher Quellcommit erforderlich')
    if prepare_signed not in ('true', 'false') or upload not in ('true', 'false'):
        raise ValueError('Beide Auslieferungsangaben muessen ausdruecklich true oder false sein')
    if prepare_signed == 'false' and upload == 'false':
        raise ValueError('Keine signierte Auslieferung ausgewaehlt')
    return {
        'schema_version': 1,
        'mode': 'upload' if upload == 'true' else 'signed_only',
        'ref': ref,
        'source_commit': commit,
        'upload_to_testflight': upload == 'true',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('event', 'ref', 'commit', 'prepare-signed', 'upload'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        decision = authorize(event=args.event, ref=args.ref, commit=args.commit,
                             prepare_signed=args.prepare_signed, upload=args.upload)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(decision, sort_keys=True))


if __name__ == '__main__':
    main()
