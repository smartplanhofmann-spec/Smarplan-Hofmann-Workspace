"""Real customer exchange with separated runtime ACLs and PostgreSQL restore.

Only the guarded disposable loopback fixture is used. No outside connection or
notification is sent. The restore target must not already exist.
"""
import base64
import hashlib
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_customer_workspace import CustomerWorkspace, protected_tables, validate_integrity
from core import Problem
from online import release, test_business_journey_pg as fixture
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from test_business_customer_workspace import png


ORIGIN = 'https://office.example.test'
request = fixture.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class CustomerWorkspacePostgres(unittest.TestCase):
    setUp = fixture.BusinessJourneyPostgres.setUp
    login = fixture.BusinessJourneyPostgres.login

    def call(self, method, path, body=None, *, token='owner', status=200):
        bearer = self.token if token == 'owner' else token
        headers = {'Authorization': 'Bearer '+bearer} if bearer else {}
        if path.startswith('/customer-workspace/') and method == 'POST':
            headers['Origin'] = ORIGIN
        response = self.client.open('/api/v1'+path, method=method, json=body,
            base_url=ORIGIN, headers=headers)
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        return response

    def exchange(self):
        project = self.call('POST', '/projects', dict(name='Synthetic customer project', customer='Synthetic customer'), status=201).json['id']
        customer = self.call('GET', '/business/customer-workspace?project_id='+project).json['project']['customer_id']
        command = request(project_id=project, customer_id=customer, recipient_name='Synthetic recipient',
            recipient_email='recipient@example.test', expires_in_days=7, allow_upload=True, confirmation=True)
        grant = self.call('POST', '/business/customer-workspace/grants', command, status=201).json
        invitation = dict(grant_id=grant['grant']['id'], key=parse_qs(urlsplit(grant['portal_url']).fragment)['key'][0])
        token = self.call('POST', '/customer-workspace/sessions', invitation, token=None, status=201).json['token']
        self.call('POST', '/business/customer-workspace/publications', request(project_id=project, customer_id=customer,
            expected_revision=0, title='Approved project details', description='Synthetic approved customer information',
            status_label='Planned', start_date=None, end_date=None, confirmation=True), status=201)
        original = png()
        upload = request(filename='synthetic-original.png', media_type='image/png', size=len(original),
            sha256=hashlib.sha256(original).hexdigest(), content_base64=base64.b64encode(original).decode(), note='Please inspect')
        received = self.call('POST', '/customer-workspace/uploads', upload, token=token, status=201).json
        self.assertEqual(self.call('POST', '/customer-workspace/uploads', upload, token=token, status=201).json, received)
        accepted = self.call('POST', '/business/customer-workspace/uploads/'+received['id']+'/accept',
            request(classification='operational', confirmation=True), status=201).json
        published = self.call('POST', '/business/customer-workspace/files', request(project_id=project, customer_id=customer,
            source_kind='media', source_id=accepted['media_id'], source_sha256=upload['sha256'],
            title='Approved customer original', confirmation=True), status=201).json
        self.assertEqual(self.call('GET', '/customer-workspace/files/'+published['id']+'/content', token=token).data, original)
        return dict(project=project, command=command, grant=grant, invitation=invitation, token=token,
            original=original, received=received, accepted=accepted, published=published)

    def test_real_runtime_exchange_replay_originals_and_immutable_history(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        data = self.exchange()
        replay = self.call('POST', '/business/customer-workspace/grants', data['command'], status=201).json
        self.assertFalse(replay['link_available'])
        self.assertNotIn('portal_url', replay)
        self.call('POST', '/business/customer-workspace/files/'+data['published']['id']+'/revoke', request(reason='Synthetic file revocation'), status=201)
        self.call('POST', '/business/customer-workspace/grants/'+data['grant']['grant']['id']+'/revoke', request(reason='Synthetic access revocation'), status=201)
        self.call('GET', '/customer-workspace/workspace', token=data['token'], status=401)
        for table in protected_tables():
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], 0)
            column = self.office.db.execute('SELECT * FROM '+table+' LIMIT 1').description[0].name
            for command in ('UPDATE '+table+' SET '+column+'='+column, 'DELETE FROM '+table, 'TRUNCATE '+table):
                with self.subTest(table=table, command=command), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(command)
            with psycopg.connect(fixture.DSN, autocommit=True) as owner:
                for command in ('UPDATE '+table+' SET '+column+'='+column, 'DELETE FROM '+table):
                    with self.subTest(table=table, guard=command), self.assertRaisesRegex(psycopg.Error, 'immutable customer workspace history'):
                        with owner.transaction():
                            owner.execute('SET LOCAL ROLE "smartplan-migrator"')
                            owner.execute(command)
        self.assertTrue(validate_integrity(self.office))
        business_schema.validate_integrity(self.office)

    def test_migration_keeps_access_restore_revokes_all_links_and_preserves_originals_receipts(self):
        data = self.exchange()
        actor, runtime = self.office.user(self.token), self.office.db.dsn
        before = release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        migrate(fixture.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN), before)
        reopened = PostgresOffice(runtime)
        reopened.portal_origin = ORIGIN
        try:
            self.assertEqual(CustomerWorkspace(reopened).content(data['token'], 'files', data['published']['id'])[0], data['original'])
        finally:
            reopened.db.close()
        target = make_conninfo(fixture.DSN, dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN, target, test_mode=True)
        with psycopg.connect(fixture.DSN, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='customer-workspace-pg-restore-') as directory:
                saved = backup(fixture.DSN, directory)
                self.assertTrue(restore(saved, fixture.DSN, target, privileged_operator=True, test_mode=True)['restore_pending'])
            target_runtime = make_conninfo(runtime, dbname='smartplan_release_check')
            with self.assertRaises(RuntimeError):
                PostgresOffice(target_runtime)
            verifier = PostgresOffice(target_runtime, allow_restore_pending=True)
            try:
                self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:
                verifier.db.close()
            restored = PostgresOffice(target_runtime)
            restored.portal_origin = ORIGIN
            try:
                api = CustomerWorkspace(restored)
                for action in (lambda: api.view(data['token']), lambda: api.open_session(**data['invitation'])):
                    with self.assertRaises(Problem) as denied:
                        action()
                    self.assertEqual(denied.exception.status, 401)
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_customer_sessions').fetchone()[0], 0)
                view = api.view_staff(actor, data['project'])
                self.assertEqual(view['grants'][0]['status'], 'revoked')
                self.assertFalse(view['writes_allowed'])
                self.assertEqual(api.staff_content(actor, 'uploads', data['received']['id'])[0], data['original'])
                self.assertEqual(api.staff_content(actor, 'files', data['published']['id'])[0], data['original'])
                business_schema.validate_integrity(restored)
                after = release.snapshot_fingerprint(target)
                for table in protected_tables():
                    if table != 'business_customer_revocations':
                        self.assertEqual(after[table], before[table], table)
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN), before)
            finally:
                restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


if __name__ == '__main__':
    unittest.main()
