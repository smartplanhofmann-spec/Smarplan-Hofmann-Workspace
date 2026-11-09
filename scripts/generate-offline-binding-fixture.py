#!/usr/bin/env python3
"""Generate public synthetic client fixtures through the actual bound backend.

No running service, real credentials or existing database is read. Fixed UUIDs,
clock, salt and public synthetic token suffixes make the output reproducible.
Responses, plan fingerprints and lookup hashes are never assembled by hand.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
PROJECT = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
CUSTOMER = 'cccccccccccccccccccccccccccccccc'
PLAN = 'dddddddddddddddddddddddddddddddd'
INSTANCE = '11111111111111111111111111111111'
FOREIGN_INSTANCE = '22222222222222222222222222222222'
STAMP = '2026-11-09T12:00:00+00:00'
EPOCH = int(datetime.fromisoformat(STAMP).timestamp())


def generate(backend):
    sys.path.insert(0, str(backend))
    from core import Office
    import business_api
    import business_offline_binding
    from online.instance import bind
    from online.storage import Storage
    from online.web import dispatch

    with tempfile.TemporaryDirectory(prefix='synthetic-offline-binding-fixture-') as folder:
        path = Path(folder)
        offices = []

        def company(label, instance):
            office = Office(path / (label + '.sqlite3'))
            offices.append(office)
            with patch('core.uuid.uuid4', return_value=uuid.UUID(hex=ACCOUNT)), \
                 patch('core.secrets.token_hex', return_value='3' * 32):
                account = office.add_user('synthetic-owner@example.test',
                    'Synthetic-fixture-password-123', 'owner')
            actor = dict(id=account, email='synthetic-owner@example.test', role='owner')
            if instance is not None:
                # Public deterministic bytes, used only in this deleted fixture DB.
                key = base64.urlsafe_b64encode(bytes([17 if label == 'bound' else 34]) * 32)
                host = 'offline-fixture.example.test'
                storage = Storage(office, key, host, config={'server': {'path': str(path / (label + '-files'))}})
                bind(office, instance, host, key, storage)
            return office, actor

        try:
            office, actor = company('bound', INSTANCE)
            # add_project also creates an internal transaction savepoint UUID.
            with patch('core.uuid.uuid4', side_effect=[uuid.UUID(hex=PROJECT),
                    uuid.UUID(hex='99999999999999999999999999999999'), uuid.UUID(hex=CUSTOMER)]), \
                 patch('core.now_iso', return_value=STAMP):
                project = office.add_project(actor, 'Synthetisches Offlineprojekt', 'Synthetischer Kunde')

            with patch('plan_access.time.time', return_value=EPOCH), \
                 patch('plan_access.secrets.token_urlsafe', side_effect=[
                     'SYNTHETIC_WORKSPACE_BINDING_FIXTURE_TOKEN',
                     'SYNTHETIC_BUSINESS_BINDING_FIXTURE_TOKEN']), \
                 patch('core.now_iso', return_value=STAMP):
                workspace_grant, status = dispatch(office, actor, '/offline/access/v2', 'POST', {}, None)
                assert status == 201
                business_grant, status, media_type = business_api.dispatch(
                    office, actor, '/business/offline/access/v2', 'POST', {})
                assert status == 201 and media_type == 'application/json'

            command = dict(request_id='44444444444444444444444444444444',
                           title='  Synthetischer Altplan Süd 🚧  ',
                           walls=[dict(id='synthetic_wall', points=[[1.0, -0.0], [1e-6, 2.0]])])
            with patch('core.uuid.uuid4', return_value=uuid.UUID(hex=PLAN)), \
                 patch('core.now_iso', return_value=STAMP):
                office.save_plan(actor, project, command)
            lookup_command = dict(schema_version=1, nonce='55555555555555555555555555555555',
                kind='plan_write', project_id=project, plan_id=None,
                command_json=json.dumps(command, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
            lookup_result = business_offline_binding.legacy_lookup(office, actor, lookup_command)
            context = business_offline_binding.context(office, actor)
            other_office, other_actor = company('foreign', FOREIGN_INSTANCE)
            foreign_binding = business_offline_binding.context(other_office, other_actor)['binding']
            unbound_office, unbound_actor = company('unbound', None)
            unbound_context = business_offline_binding.context(unbound_office, unbound_actor)
            return dict(schema_version=1,
                fixture_scope='PUBLIC SYNTHETIC FIXTURE; no real credentials, live server or customer data',
                server_url='https://offline-fixture.example.test', api_version='v1',
                account_id=actor['id'], instance_id=INSTANCE, project_id=project,
                context=context, unbound_context=unbound_context,
                workspace_grant=workspace_grant, business_grant=business_grant,
                lookup_command=lookup_command, lookup_result=lookup_result,
                foreign_binding=foreign_binding)
        finally:
            for office in offices:
                office.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', type=Path, default=ROOT / 'backend')
    parser.add_argument('--output', type=Path, default=ROOT / 'app/test/fixtures/offline_binding_v2.json')
    args = parser.parse_args()
    result = generate(args.backend.resolve())
    encoded = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    print(json.dumps(dict(path=str(args.output), bytes=len(encoded), sha256=hashlib.sha256(encoded).hexdigest())))


if __name__ == '__main__':
    main()
