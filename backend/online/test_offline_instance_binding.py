"""Bound offline grants and read-only legacy recovery over real MFA/HTTP.

Two independent companies intentionally share user/project IDs and credentials,
as a customer seed or copied session can do. Their instance identities, server
keys and storage roots remain distinct; no identity guard is bypassed.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
import zipfile

from cryptography.fernet import Fernet
from core import Office, canonical, digest
from company_export_archive import build, structure
from online.auth import totp
from online.instance import bind
from online.storage import Storage
from online.web import create_app
from online.test_instance_isolation import MFA_SCHEMA


HEADER = 'X-Smartplan-Offline-Binding'
PASSWORD = 'Synthetic-offline-binding-password-123'
ONLINE = object()


@unittest.skipUnless(os.name == 'posix', 'Private POSIX server storage required')
class OfflineInstanceBindingHttpTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-offline-binding-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        seed = Office(self.root / 'seed.sqlite3')
        seed.db.executescript(MFA_SCHEMA)
        self.account = seed.add_user('owner@example.test', PASSWORD, 'owner')
        self.actor = dict(id=self.account, role='owner')
        self.project = seed.add_project(self.actor, 'Same project name', 'Same customer name')
        for label in ('a', 'b'):
            target = sqlite3.connect(self.root / (label + '.sqlite3'))
            seed.db.backup(target)
            target.close()
        seed.db.close()
        self.a, self.b = (self.company(label) for label in ('a', 'b'))

    def company(self, label):
        office = Office(self.root / (label + '.sqlite3'))
        self.addCleanup(office.db.close)
        value = dict(office=office, instance_id=uuid.uuid4().hex, key=Fernet.generate_key(),
                     host='same.example.test', root=self.root / (label + '-storage'))
        value['storage'] = Storage(office, value['key'], value['host'],
            config={'server': {'path': str(value['root'])}})
        bind(office, value['instance_id'], value['host'], value['key'], value['storage'])
        self.reopen(value)
        value['token'] = self.login(value)
        return value

    def reopen(self, company):
        company['client'] = create_app(office=company['office'], key=company['key'],
            host=company['host'], instance_id=company['instance_id'], storage=company['storage']).test_client()

    def call(self, company, path, body=None, *, token=ONLINE, status=200, method=None, headers=None, raw=None):
        bearer = company.get('token') if token is ONLINE else token
        request_headers = dict(headers or {})
        if bearer:
            request_headers['Authorization'] = 'Bearer ' + bearer
        kwargs = dict(base_url='https://' + company['host'], headers=request_headers)
        if raw is not None:
            kwargs.update(data=raw, content_type='application/octet-stream')
        elif body is not None:
            kwargs['json'] = body
        response = company['client'].open('/api/v1' + path,
            method=method or ('POST' if body is not None or raw is not None else 'GET'), **kwargs)
        if status is not None:
            self.assertEqual(response.status_code, status, (path, response.status_code, response.data[:300]))
        return response

    def login(self, company, email='owner@example.test', password=PASSWORD):
        pending = self.call(company, '/login', dict(email=email, password=password), token=None).json
        self.assertTrue(pending['mfa_required'])
        return self.call(company, '/login/verify', dict(challenge=pending['challenge'],
            code=totp(pending['enrollment']['secret'], int(time.time() // 30))), token=None).json['token']

    def binding(self, company, account=None):
        return dict(schema_version=1, instance_id=company['instance_id'], account_id=account or self.account)

    def header(self, company, account=None):
        return {HEADER: company['instance_id'] + ':' + (account or self.account)}

    def grant(self, company, *, business=False):
        value = self.call(company, '/business/offline/access/v2' if business else '/offline/access/v2', {}, status=201).json
        self.assertEqual(value['schema_version'], 2)
        self.assertEqual(value['binding'], self.binding(company))
        self.assertTrue(value['token'].startswith('offline_business_v2_' if business else 'offline_workspace_v2_'))
        return value

    def legacy(self, company):
        """Exact pre-upgrade row; no new server issuance is assumed."""
        token = 'offline_workspace_' + uuid.uuid4().hex
        row = company['office'].db.execute('SELECT * FROM users WHERE id=?', (self.account,)).fetchone()
        fingerprint = digest(canonical([row['id'], row['salt'], row['password'], row['role'], row['active']]))
        with company['office'].db:
            company['office'].db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)',
                (digest(token), self.account, time.time() + 3600, fingerprint))
        return token

    def plan(self, company, *, token=ONLINE, headers=None, title='Unchanged original plan'):
        command = dict(request_id=uuid.uuid4().hex, title=title,
            walls=[dict(id='synthetic_wall', points=[[1.0, -0.0], [1e-6, 2.0]])])
        result = self.call(company, '/projects/' + self.project + '/plans', command,
            token=token, headers=headers, status=201).json
        return command, result

    def lookup(self, command, plan_id=None, **changes):
        body = dict(schema_version=1, nonce=uuid.uuid4().hex, kind='plan_write',
                    project_id=self.project, plan_id=plan_id, command_json=canonical(command))
        body.update(changes)
        return body

    def test_bound_context_and_workspace_and_business_grants_are_actor_bound(self):
        for company in (self.a, self.b):
            context = self.call(company, '/offline/context').json
            self.assertEqual(context, dict(schema_version=2, mode='bound_v2', binding=self.binding(company)))
            for business in (False, True):
                grant = self.grant(company, business=business)
                self.assertIn('project_plans', grant['capabilities'])
                self.assertEqual(self.call(company, '/projects', token=grant['token'], headers=self.header(company)).json[0]['id'], self.project)
                self.call(company, '/offline/context', token=grant['token'], headers=self.header(company), status=403)
        self.assertNotEqual(self.a['instance_id'], self.b['instance_id'])
        self.assertNotEqual(self.a['key'], self.b['key'])

    def test_every_v2_read_write_and_chunk_requires_matching_binding(self):
        grant = self.grant(self.a)
        path = '/projects/' + self.project + '/plans'
        command = dict(request_id=uuid.uuid4().hex, title='Bound only', walls=[])
        wrong = (None, self.header(self.b), self.header(self.a, account='f' * 32), {HEADER:'invalid'})
        for headers in wrong:
            self.call(self.a, path, token=grant['token'], headers=headers, status=403)
            self.call(self.a, path, command, token=grant['token'], headers=headers, status=403)
        self.assertEqual(self.call(self.a, path).json, [])
        self.call(self.a, path, command, token=grant['token'], headers=self.header(self.a), status=201)
        raw = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6n8AAAAASUVORK5CYII=')
        manifest = dict(request_id=uuid.uuid4().hex, filename='synthetic.png', media_type='image/png',
                        size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), page=0, title='Bound source')
        imported = self.call(self.a, '/projects/' + self.project + '/plan-imports', manifest,
            token=grant['token'], headers=self.header(self.a), status=201).json
        chunk = '/projects/' + self.project + '/plan-imports/' + imported['id'] + '/chunks/0'
        self.call(self.a, chunk, token=grant['token'], method='PUT', raw=raw, status=403)
        self.call(self.a, chunk, token=grant['token'], headers=self.header(self.a), method='PUT', raw=raw)

    def test_legacy_get_post_and_copied_session_are_blocked_without_mutating_business_data(self):
        token = self.legacy(self.a)
        source = self.a['office'].db.execute('SELECT * FROM plan_sessions WHERE token=?', (digest(token),)).fetchone()
        with self.b['office'].db:
            self.b['office'].db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)', tuple(source))
        self.reopen(self.b)
        for company in (self.a, self.b):
            self.call(company, '/projects', token=token, status=409)
            self.call(company, '/projects/' + self.project + '/plans',
                dict(request_id=uuid.uuid4().hex, title='Must not cross company', walls=[]), token=token, status=409)
            self.assertEqual(self.call(company, '/projects/' + self.project + '/plans').json, [])
        self.call(self.a, '/offline/logout', {}, token=token)

    def test_copied_v2_session_and_grant_cannot_be_relabelled_with_new_company_header(self):
        grant = self.grant(self.a)
        office = self.a['office']
        session = office.db.execute('SELECT * FROM plan_sessions WHERE token=?', (digest(grant['token']),)).fetchone()
        binding = office.db.execute('SELECT * FROM business_offline_instance_grants WHERE token_hash=?', (digest(grant['token']),)).fetchone()
        with self.b['office'].db:
            self.b['office'].db.execute('INSERT INTO plan_sessions(token,user_id,expiry,credential) VALUES(?,?,?,?)', tuple(session))
            self.b['office'].db.execute('INSERT INTO business_offline_instance_grants(token_hash,instance_id,account_id,issued_at,expiry) VALUES(?,?,?,?,?)', tuple(binding))
        for headers in (self.header(self.a), self.header(self.b)):
            response = self.call(self.b, '/projects', token=grant['token'], headers=headers, status=None)
            self.assertIn(response.status_code, (401,403,409))
        self.call(self.a, '/projects', token=grant['token'], headers=self.header(self.a))

    def test_expired_or_changed_credential_never_becomes_a_live_grant(self):
        grant = self.grant(self.a)
        with patch('plan_access.time.time', return_value=time.time() + 8*86400):
            self.call(self.a, '/projects', token=grant['token'], headers=self.header(self.a), status=401)
        with self.a['office'].db:
            self.a['office'].db.execute("UPDATE users SET role='technician' WHERE id=?", (self.account,))
        self.call(self.a, '/projects', token=grant['token'], headers=self.header(self.a), status=401)

    def test_unbound_context_is_explicit_and_v2_is_not_silently_downgraded(self):
        office = Office(self.root / 'unbound.sqlite3')
        self.addCleanup(office.db.close)
        office.db.executescript(MFA_SCHEMA)
        office.add_user('owner@example.test', PASSWORD, 'owner')
        company = dict(office=office, host='unbound.example.test', key=Fernet.generate_key())
        company['client'] = create_app(office=office, key=company['key'], host=company['host']).test_client()
        company['token'] = self.login(company)
        self.assertEqual(self.call(company, '/offline/context').json,
            dict(schema_version=2, mode='unbound_legacy', binding=None))
        self.call(company, '/offline/access/v2', {}, status=409)
        old = self.call(company, '/offline/access', {}, status=201).json
        self.call(company, '/projects', token=old['token'])

    def test_valid_logout_revokes_v2_and_cascades_private_binding(self):
        grant = self.grant(self.a)
        self.call(self.a, '/offline/logout', {}, token=grant['token'])
        self.assertIsNone(self.a['office'].db.execute(
            'SELECT token_hash FROM business_offline_instance_grants WHERE token_hash=?',
            (digest(grant['token']),)).fetchone())
        self.call(self.a, '/projects', token=grant['token'], headers=self.header(self.a), status=401)

    def test_private_grant_rows_are_classified_and_never_exported_as_company_records(self):
        grant = self.grant(self.a)
        inventory = structure(self.a['office'])
        entry = next(row for row in inventory if row['table']=='business_offline_instance_grants')
        self.assertFalse(entry['included'])
        self.assertIsNotNone(entry['exclusion_reason'])
        raw, _ = build(self.a['office'], instance_id=self.a['instance_id'], export_id=uuid.uuid4().hex,
            created_at='2026-11-09T12:00:00+00:00', created_by=self.account,
            reason='Synthetic safe company export', inventory=inventory)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertNotIn('data/business_offline_instance_grants.jsonl', archive.namelist())
            contents = b''.join(archive.read(name) for name in archive.namelist())
            self.assertNotIn(grant['token'].encode(), contents)
            self.assertNotIn(digest(grant['token']).encode(), contents)

    def test_lookup_returns_bound_original_not_latest_and_changes_no_business_rows(self):
        command, original = self.plan(self.a, title='  Alter Plan Süd 🚧  ')
        self.call(self.a, '/projects/' + self.project + '/plans/' + original['id'],
            dict(request_id=uuid.uuid4().hex, title='Later title', walls=[], revision=original['revision']))
        tables = ('projects','plan_versions','plan_requests')
        before = {table:[tuple(row) for row in self.a['office'].db.execute('SELECT * FROM '+table)] for table in tables}
        lookup = self.lookup(command)
        result = self.call(self.a, '/business/offline/recovery/lookup', lookup).json
        self.assertEqual(result, dict(schema_version=1, nonce=lookup['nonce'], lookup_hash=digest(canonical(lookup)),
            binding=self.binding(self.a), kind='plan_write', project_id=self.project, plan_id=None,
            request_id=command['request_id'], request_hash=digest(canonical(dict(project_id=self.project,plan_id=None,data=command))),
            original=original))
        self.assertEqual(before, {table:[tuple(row) for row in self.a['office'].db.execute('SELECT * FROM '+table)] for table in tables})
        unknown = self.call(self.b, '/business/offline/recovery/lookup', lookup, status=404)
        self.assertNotIn('request_resolution', unknown.json)
        self.assertEqual(self.call(self.b, '/projects/' + self.project + '/plans').json, [])

    def test_lookup_is_bounded_and_never_accepts_ambiguous_json(self):
        command, _ = self.plan(self.a)
        lookup = self.lookup(command)
        for raw, status in ((json.dumps(lookup)[:-1] + ',"nonce":"' + ('f' * 32) + '"}', 400),
                            (json.dumps(lookup | {'padding':'x' * 1_000_001}), 413)):
            response = self.a['client'].post('/api/v1/business/offline/recovery/lookup',
                data=raw, content_type='application/json', base_url='https://' + self.a['host'],
                headers={'Authorization':'Bearer ' + self.a['token']})
            self.assertEqual(response.status_code, status)
        second = self.lookup(command)
        result = self.call(self.a, '/business/offline/recovery/lookup', second).json
        self.assertEqual(result['nonce'], second['nonce'])
        self.assertEqual(result['lookup_hash'], digest(canonical(second)))
        # The original command is JSON text inside the outer JSON request.
        # Duplicate/nonfinite inner values must not bypass strict decoding.
        for inner in (canonical(command)[:-1] + ',"title":"Duplicate"}',
                      '[1,2]', '"not an object"',
                      json.dumps(command | {'walls':[{'id':'w','points':[[float('nan'),0],[1,1]]}]})):
            self.call(self.a, '/business/offline/recovery/lookup', lookup | {'command_json':inner}, status=400)
        different_spelling = lookup | {'nonce':uuid.uuid4().hex,
            'command_json':json.dumps(command, ensure_ascii=False)}
        value = self.call(self.a, '/business/offline/recovery/lookup', different_spelling).json
        self.assertEqual(value['request_hash'], result['request_hash'])
        self.assertEqual(value['lookup_hash'], digest(canonical(different_spelling)))
        self.assertNotEqual(value['lookup_hash'], result['lookup_hash'])

    def test_lookup_uses_own_receipt_and_fresh_project_access(self):
        office = self.a['office']
        technician = office.add_user('tech@example.test', PASSWORD, 'technician')
        office.assign(self.actor, self.project, technician)
        token = self.login(self.a, 'tech@example.test')
        command, _ = self.plan(self.a, token=token)
        lookup = self.lookup(command)
        self.call(self.a, '/business/offline/recovery/lookup', lookup, token=token)
        self.call(self.a, '/business/offline/recovery/lookup', lookup, status=404)
        office.assign(self.actor, self.project, technician, True)
        response = self.call(self.a, '/business/offline/recovery/lookup', lookup, token=token, status=None)
        self.assertIn(response.status_code, (403,404))
        self.assertNotIn('request_resolution', response.json)

    def test_lookup_rejects_changed_command_unknown_shape_and_corrupt_original_without_new_send_permission(self):
        command, original = self.plan(self.a)
        lookup = self.lookup(command)
        for body in (lookup | {'kind':'arbitrary_table'}, lookup | {'nonce':'invalid'}, lookup | {'unexpected':True},
                     self.lookup(command | {'unexpected':True})):
            self.call(self.a, '/business/offline/recovery/lookup', body, status=400)
        conflict = self.call(self.a, '/business/offline/recovery/lookup', self.lookup(command | {'title':'Changed'}), status=409)
        self.assertNotIn('request_resolution', conflict.json)
        self.call(self.a, '/business/offline/recovery/lookup?instance_id='+self.b['instance_id'], lookup, status=400)
        self.call(self.a, '/business/offline/recovery/lookup', lookup, token=None, status=401)
        grant = self.grant(self.a)
        self.call(self.a, '/business/offline/recovery/lookup', lookup, token=grant['token'], headers=self.header(self.a), status=403)
        with self.a['office'].db:
            self.a['office'].db.execute('UPDATE plan_requests SET result=? WHERE request_id=?',
                (canonical(original | {'title':'Tampered'}), command['request_id']))
        corrupt = self.call(self.a, '/business/offline/recovery/lookup', lookup, status=409)
        self.assertNotIn('request_resolution', corrupt.json)


@unittest.skipUnless(os.name == 'posix', 'Private POSIX server storage required')
class OfflineInstanceBindingLocalHttpTests(unittest.TestCase):
    """Actual TCP requests also exercise the packaged local server's branch."""

    def setUp(self):
        from http.server import ThreadingHTTPServer
        import threading
        from onedrive import OneDrive
        from server import make_handler
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-offline-binding-wire-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.office = Office(root / 'local.sqlite3')
        self.addCleanup(self.office.db.close)
        self.account = self.office.add_user('owner@example.test', PASSWORD, 'owner')
        self.full = self.office.login('owner@example.test', PASSWORD)
        actor = self.office.user(self.full)
        self.project = self.office.add_project(actor, 'Bound local site', 'Synthetic customer')
        self.instance = uuid.uuid4().hex
        key = Fernet.generate_key()
        storage = Storage(self.office, key, 'local.example.test',
                          config={'server': {'path': str(root / 'private-store')}})
        bind(self.office, self.instance, 'local.example.test', key, storage)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, body=None, *, token=None, headers=None, status=200):
        from http.client import HTTPConnection
        request_headers = {'Authorization': 'Bearer ' + (token or self.full), 'Content-Type': 'application/json'}
        request_headers.update(headers or {})
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=6)
        try:
            connection.request('POST' if body is not None else 'GET', '/api' + path,
                               body=None if body is None else canonical(body).encode('utf-8'),
                               headers=request_headers)
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, status, (path, result))
            return result
        finally:
            connection.close()

    def test_bound_local_wire_requires_origin_and_recovers_exact_original(self):
        origin = dict(schema_version=1, instance_id=self.instance, account_id=self.account)
        self.assertEqual(self.call('/offline/context'), dict(schema_version=2, mode='bound_v2', binding=origin))
        self.call('/offline/context?extra=1', status=400)
        grant = self.call('/offline/access/v2', {}, status=201)
        self.assertEqual(grant['binding'], origin)
        headers = {HEADER: self.instance + ':' + self.account}
        path = '/projects/' + self.project + '/plans'
        body = dict(request_id=uuid.uuid4().hex, title='Original local plan', walls=[])
        self.call(path, token=grant['token'], status=403)
        self.call(path, body, token=grant['token'], status=403)
        self.assertEqual(self.call(path), [])
        original = self.call(path, body, token=grant['token'], headers=headers, status=201)
        self.assertEqual(self.call(path, body, token=grant['token'], headers=headers, status=201), original)
        lookup = dict(schema_version=1, nonce=uuid.uuid4().hex, kind='plan_write', project_id=self.project,
                      plan_id=None, command_json=canonical(body))
        recovered = self.call('/business/offline/recovery/lookup', lookup)
        self.assertEqual(recovered['original'], original)
        self.assertEqual(recovered['lookup_hash'], digest(canonical(lookup)))
        self.assertEqual(recovered['binding'], origin)
        self.call('/offline/logout', {}, token=grant['token'])
        self.call(path, token=grant['token'], headers=headers, status=401)


if __name__ == '__main__':
    unittest.main()
