"""Real portal history, runtime privileges and disaster restore on PostgreSQL.

Uses only the guarded disposable loopback smartplan_check fixture. A restore
target is created exclusively and never replaces an existing database. All
people, credentials and documents are synthetic; no provider is contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import business_schema
from business_documents import Documents, render_prepared
from business_portal import Portal, STATEMENTS, protected_tables, validate_integrity
from core import Problem
from online import release, test_online as base, test_business_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import migrate, PostgresOffice


request = journey.request
ORIGIN = 'https://office.example.test'


def issuer_settings(day):
    return request(revision=0, company_name='Synthetic portal seller',
        address_line='Synthetic seller street 1', postal_code='10115', city='Berlin',
        country='DE', vat_id='DE123456789', email='seller@example.test', issuer_mode='own',
        issuing_enabled=True, cutover_ack=True, cutover_date=day, einvoice_format='none')


def offer_data(project, day):
    return request(project_id=project, kind='offer', title='Synthetic PostgreSQL portal offer',
        issue_date=day, due_date=(datetime.fromisoformat(day).date() + timedelta(days=14)).isoformat(),
        buyer={'name': 'Synthetic portal buyer', 'address_line': 'Synthetic buyer street 2',
               'postal_code': '10117', 'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
        positions=[{'description': 'Synthetic service', 'quantity': '2', 'unit': 'HUR',
                    'unit_price_net': '50.00', 'tax_rate': '19', 'kind': 'labor'}])


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PortalPostgres(unittest.TestCase):
    login = journey.BusinessJourneyPostgres.login

    def call(self, method, path, body=None, *, token='owner', status=200):
        bearer = self.token if token == 'owner' else token
        headers = {'Authorization': 'Bearer ' + bearer} if bearer else {}
        if path.startswith('/portal/') and method == 'POST':
            headers['Origin'] = ORIGIN
        response = self.client.open('/api/v1' + path, method=method,
            base_url=ORIGIN, headers=headers, json=body)
        # Never include invitation URLs or tokens in assertion diagnostics.
        self.assertEqual(response.status_code, status, (method, path, response.status_code))
        return response

    def setUp(self):
        journey.BusinessJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)
        self.runtime = self.office.db.dsn
        self.project = self.call('POST', '/projects', {'name': 'Synthetic portal project',
            'customer': 'Synthetic portal customer'}, status=201).json['id']
        self.call('POST', '/business/settings/branding', issuer_settings(self.today))
        draft = self.call('POST', '/business/documents', offer_data(self.project, self.today)).json
        self.offer = self.call('POST', '/business/documents/' + draft['id'] + '/finalize',
            request(revision=draft['revision'])).json
        self.assertEqual((self.offer['kind'], self.offer['status'], self.offer['archive_security']),
                         ('offer', 'final', 'postgresql_runtime_separated'))
        self.pdf = self.call('GET', '/business/documents/' + self.offer['id'] + '/pdf').data
        self.source = self.call('GET', '/business/portal/grants?offer_id=' + self.offer['id']).json['source']
        self.adopt_path = '/business/portal/offers/' + self.offer['id'] + '/adopt'

    def grant(self, *, token='owner'):
        body = request(**{key: self.source[key] for key in
            ('offer_id', 'source_revision', 'content_hash', 'pdf_hash')},
            recipient_name='Synthetic representative', recipient_email='recipient@example.test',
            expires_in_days=7, confirmation=True)
        result = self.call('POST', '/business/portal/grants', body, token=token, status=201).json
        parts = urlsplit(result['portal_url'])
        self.assertEqual(parts.scheme + '://' + parts.netloc, ORIGIN)
        self.assertEqual((parts.path, parts.query), ('/office/portal.html', ''))
        fragment = parse_qs(parts.fragment)
        self.assertEqual(fragment['grant'], [result['grant']['id']])
        return dict(result=result, body=body, id=result['grant']['id'], key=fragment['key'][0])

    def session(self, grant):
        return self.call('POST', '/portal/sessions', {'grant_id': grant['id'], 'key': grant['key']},
                         token=None, status=201).json['token']

    def decision_body(self, *, decision='accepted'):
        return request(content_hash=self.source['content_hash'], pdf_hash=self.source['pdf_hash'],
            decision=decision, declared_name='Synthetic customer representative',
            statement_version=STATEMENTS['version'], confirmation=True)

    def accepted(self):
        grant = self.grant()
        token = self.session(grant)
        body = self.decision_body()
        decision = self.call('POST', '/portal/offer/decision', body, token=token, status=201).json
        return grant, token, body, decision

    def adoption_body(self, decision):
        return request(decision_id=decision['id'], confirmation=True,
            **{key: self.source[key] for key in ('source_revision', 'content_hash', 'pdf_hash')})

    def reopen(self, *, dsn=None):
        office = PostgresOffice(dsn or self.runtime)
        office.portal_origin = ORIGIN
        self.addCleanup(office.db.close)
        return office

    def permission(self, user, name, *, scope=None, effect='allow', revision=0):
        return self.call('POST', '/business/settings/permissions', request(user_id=user,
            permission=name, scope=scope or self.project, effect=effect, revision=revision)).json

    def test_final_offer_http_separate_tokens_original_pdf_decision_explicit_draft_and_restart(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        grant = self.grant()
        replay = self.call('POST', '/business/portal/grants', grant['body'], status=201).json
        self.assertEqual(replay['grant'], grant['result']['grant'])
        self.assertFalse(replay['link_available'])
        self.assertNotIn('portal_url', replay)
        token = self.session(grant)
        self.assertTrue(token.startswith('SPPT_'))
        self.call('GET', '/projects', token=token, status=401)
        self.call('GET', '/portal/offer', status=401)
        self.call('POST', '/portal/sessions', {'grant_id': grant['id'], 'key': grant['key']}, status=401)
        public = self.call('GET', '/portal/offer', token=token).json
        self.assertEqual(public['offer']['id'], self.offer['id'])
        self.assertEqual(public['offer']['totals']['gross'], '119.00')
        self.assertTrue(public['actions_allowed'])
        self.assertIsNone(public['decision'])
        self.assertNotIn('project_id', public['offer'])
        self.assertNotIn('customer_id', public['offer'])
        download = self.call('GET', '/portal/offer/pdf', token=token)
        self.assertEqual(download.data, self.pdf)
        self.assertEqual(hashlib.sha256(download.data).hexdigest(), self.source['pdf_hash'])
        self.assertEqual(download.headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', download.headers)
        body = self.decision_body()
        decision = self.call('POST', '/portal/offer/decision', body, token=token, status=201).json
        self.assertEqual(self.call('POST', '/portal/offer/decision', body, token=token, status=201).json, decision)
        self.assertEqual(decision['statement_text'], STATEMENTS['accepted'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], 1)
        adoption_body = self.adoption_body(decision)
        adoption = self.call('POST', self.adopt_path, adoption_body, status=201).json
        self.assertEqual(self.call('POST', self.adopt_path, adoption_body, status=201).json, adoption)
        target = self.call('GET', '/business/documents/' + adoption['document_id']).json
        self.assertEqual((target['kind'], target['status'], target['project_id']),
                         ('order_confirmation', 'draft', self.project))
        self.assertEqual(adoption['created_by'], self.owner['id'])
        self.assertEqual(self.call('GET', '/business/documents/' + self.offer['id']).json, self.offer)
        self.assertEqual(self.call('GET', '/business/documents/' + self.offer['id'] + '/pdf').data, self.pdf)
        for table in (*protected_tables(), 'business_portal_principals', 'business_portal_sessions'):
            stored = json.dumps([dict(row) for row in self.office.db.execute('SELECT * FROM ' + table)], default=str)
            self.assertFalse(grant['key'] in stored, 'Invitation secret persisted')
            self.assertFalse(token in stored, 'Portal session token persisted')
        reopened = self.reopen()
        self.assertEqual(Portal(reopened).view(token)['decision'], decision)
        self.assertFalse(Portal(reopened).view(token)['actions_allowed'])
        self.assertEqual(Portal(reopened).pdf(token)[0], self.pdf)
        self.assertEqual(Portal(reopened).list_grants(self.owner, self.offer['id'])['adoption'], adoption)
        self.assertTrue(validate_integrity(reopened))
        business_schema.validate_integrity(reopened)

    def test_current_project_scoped_permissions_precede_grant_and_adoption_replays(self):
        user = self.call('POST', '/users', {'email': 'portal-manager@example.test',
            'password': 'Synthetic-portal-manager-password-123', 'role': 'technician'}, status=201).json['id']
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user})
        token = self.login('portal-manager@example.test', 'Synthetic-portal-manager-password-123')
        self.call('GET', '/business/portal/grants?offer_id=' + self.offer['id'], token=token, status=403)
        grants = {name: self.permission(user, name) for name in
                  ('portal.manage', 'finance.read', 'finance.write', 'projects.manage')}
        grant = self.grant(token=token)
        self.permission(user, 'portal.manage', effect='deny', revision=grants['portal.manage']['revision'])
        self.call('POST', '/business/portal/grants', grant['body'], token=token, status=403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_grants').fetchone()[0], 1)
        self.permission(user, 'portal.manage', revision=grants['portal.manage']['revision'] + 1)
        portal_token = self.session(grant)
        decision = self.call('POST', '/portal/offer/decision', self.decision_body(), token=portal_token, status=201).json
        body = self.adoption_body(decision)
        adoption = self.call('POST', self.adopt_path, body, token=token, status=201).json
        self.assertEqual(adoption['created_by'], user)
        self.permission(user, 'projects.manage', effect='deny', revision=grants['projects.manage']['revision'])
        self.call('POST', self.adopt_path, body, token=token, status=403)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 1)
        self.call('POST', '/assignments', {'project_id': self.project, 'user_id': user, 'remove': True})
        self.call('GET', '/business/portal/grants?offer_id=' + self.offer['id'], token=token, status=404)
        self.assertEqual(Portal(self.office).view(portal_token)['decision'], decision)

    def test_history_runtime_acl_migration_role_guards_and_principal_monotonicity(self):
        grant, token, _, decision = self.accepted()
        self.call('POST', self.adopt_path, self.adoption_body(decision), status=201)
        self.call('POST', '/business/portal/grants/' + grant['id'] + '/revoke',
            request(reason='Synthetic revocation', confirmation=True))
        before = release.snapshot_fingerprint(journey.DSN)
        for table in protected_tables():
            column = self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').description[0].name
            self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
            for command in ('UPDATE ' + table + ' SET ' + column + '=' + column,
                            'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.subTest(table=table, command=command), self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:
                        self.office.db.execute(command)
            # An ACL regression must not silently remove row immutability.
            with psycopg.connect(journey.DSN, autocommit=True) as owner:
                for command in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                    with self.subTest(table=table, guard=command), self.assertRaisesRegex(psycopg.Error, 'immutable portal history'):
                        with owner.transaction():
                            owner.execute('SET LOCAL ROLE "smartplan-migrator"')
                            owner.execute(command)
        with self.assertRaisesRegex(psycopg.Error, 'immutable portal identity'):
            with self.office.db:
                self.office.db.execute("UPDATE business_portal_principals SET name='Changed synthetic identity'")
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        with self.office.db:
            self.office.db.execute('UPDATE business_portal_principals SET active=0,revision=revision+1')
        with self.assertRaisesRegex(psycopg.Error, 'immutable portal identity'):
            with self.office.db:
                self.office.db.execute('UPDATE business_portal_principals SET active=1,revision=revision+1')
        self.assertTrue(validate_integrity(self.office))

    def compete(self, invoke, values):
        barrier = threading.Barrier(len(values))

        def run(value):
            office = PostgresOffice(self.runtime)
            office.portal_origin = ORIGIN
            try:
                barrier.wait(timeout=5)
                try:
                    return 201, invoke(Portal(office), value)
                except Problem as error:
                    return error.status, None
            finally:
                office.db.close()

        with ThreadPoolExecutor(max_workers=len(values)) as workers:
            return list(workers.map(run, values))

    def test_separate_connections_competing_decisions_commit_one_declaration(self):
        grant = self.grant()
        token = self.session(grant)
        results = self.compete(lambda api, body: api.decide(token, body),
            [self.decision_body(decision=value) for value in ('accepted', 'declined')])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_decisions').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_decision_requests').fetchone()[0], 1)
        winner = next(result for status, result in results if status == 201)
        self.assertEqual(Portal(self.office).view(token)['decision'], winner)
        self.assertEqual(Documents(self.office).archive(self.owner, self.offer['id'], 'pdf'), self.pdf)
        self.assertTrue(validate_integrity(self.office))

    def test_separate_connections_competing_adoptions_commit_one_related_draft(self):
        _, _, _, decision = self.accepted()
        results = self.compete(lambda api, body: api.adopt(self.owner, self.offer['id'], body),
                               [self.adoption_body(decision), self.adoption_body(decision)])
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_portal_adoptions').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0], 2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_relations').fetchone()[0], 1)
        winner = next(result for status, result in results if status == 201)
        draft = Documents(self.office).get(self.owner, winner['document_id'])
        self.assertEqual((draft['kind'], draft['status']), ('order_confirmation', 'draft'))
        self.assertTrue(validate_integrity(self.office))

    def test_adoption_failure_after_real_document_insert_rolls_back_and_can_retry(self):
        _, _, _, decision = self.accepted()
        body = self.adoption_body(decision)
        with psycopg.connect(journey.DSN) as admin:
            admin.execute("CREATE FUNCTION synthetic_portal_adoption_failure() RETURNS trigger LANGUAGE plpgsql AS $$ "
                          "BEGIN RAISE EXCEPTION 'synthetic adoption failure'; END; $$")
            admin.execute('CREATE TRIGGER synthetic_portal_adoption_failure BEFORE INSERT ON business_portal_adoptions '
                          'FOR EACH ROW EXECUTE FUNCTION synthetic_portal_adoption_failure()')
        before = release.snapshot_fingerprint(journey.DSN)
        try:
            with self.assertRaisesRegex(psycopg.Error, 'synthetic adoption failure'):
                Portal(self.office).adopt(self.owner, self.offer['id'], body)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        finally:
            with psycopg.connect(journey.DSN) as admin:
                admin.execute('DROP TRIGGER synthetic_portal_adoption_failure ON business_portal_adoptions')
                admin.execute('DROP FUNCTION synthetic_portal_adoption_failure()')
        result = Portal(self.office).adopt(self.owner, self.offer['id'], body)
        self.assertEqual(Documents(self.office).get(self.owner, result['document_id'])['status'], 'draft')
        self.assertTrue(validate_integrity(self.office))

    def test_normal_migration_preserves_access_disaster_restore_revokes_it_and_retains_history(self):
        grant, token, _, decision = self.accepted()
        adoption = self.call('POST', self.adopt_path, self.adoption_body(decision), status=201).json
        self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM business_portal_rate_counters').fetchone()[0], 0)
        before = release.snapshot_fingerprint(journey.DSN)
        self.office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
        reopened = self.reopen()
        self.assertEqual(Portal(reopened).view(token)['decision'], decision)
        self.assertEqual(Portal(reopened).pdf(token)[0], self.pdf)
        reopened.db.close()
        target = make_conninfo(journey.DSN, dbname='smartplan_release_check')
        release.validate_dsns(journey.DSN, target, test_mode=True)
        with psycopg.connect(journey.DSN, autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Disposable restore target already exists; preserve and inspect it.')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-portal-pg-restore-') as directory:
                saved = backup(journey.DSN, directory)
                report = restore(saved, journey.DSN, target, privileged_operator=True, test_mode=True)
            self.assertTrue(report['restore_pending'])
            target_runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
            with self.assertRaises(RuntimeError):
                PostgresOffice(target_runtime)
            verifier = PostgresOffice(target_runtime, allow_restore_pending=True)
            try:
                self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:
                verifier.db.close()
            after = release.snapshot_fingerprint(target)
            retained = (*protected_tables(), 'business_documents', 'business_document_archives',
                        'business_document_numbers', 'business_document_counters', 'business_document_relations', 'audit')
            for table in retained:
                if table != 'business_portal_revocations':
                    self.assertEqual(after[table], before[table], table)
            self.assertEqual(release.snapshot_fingerprint(journey.DSN), before)
            restored = self.reopen(dsn=target_runtime)
            try:
                self.assertTrue(business_schema.require_runtime_security(restored))
                api = Portal(restored)
                for action in (lambda: api.view(token), lambda: api.pdf(token),
                               lambda: api.open_session(grant['id'], grant['key']), lambda: restored.user(self.token)):
                    with self.assertRaises(Problem) as denied:
                        action()
                    self.assertEqual(denied.exception.status, 401)
                for table in ('business_portal_sessions', 'business_portal_rate_counters', 'sessions'):
                    self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0)
                history = api.list_grants(self.owner, self.offer['id'])
                self.assertEqual(history['decision'], decision)
                self.assertEqual(history['adoption'], adoption)
                self.assertEqual(history['items'][0]['status'], 'revoked')
                self.assertEqual(history['items'][0]['revocation']['kind'], 'restore')
                self.assertIsNone(history['items'][0]['revocation']['revoked_by'])
                self.assertFalse(history['items'][0]['principal']['active'])
                self.assertEqual(Documents(restored).archive(self.owner, self.offer['id'], 'pdf'), self.pdf)
                self.assertEqual(Documents(restored).get(self.owner, self.offer['id']), self.offer)
                self.assertEqual(Documents(restored).get(self.owner, adoption['document_id'])['status'], 'draft')
                self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])
                with self.assertRaises(Problem) as blocked:
                    api.create_grant(self.owner, {**grant['body'], 'request_id': uuid.uuid4().hex})
                self.assertEqual(blocked.exception.status, 409)
                self.assertTrue(validate_integrity(restored))
                business_schema.validate_integrity(restored)
            finally:
                restored.db.close()
        finally:
            with psycopg.connect(journey.DSN, autocommit=True) as admin:
                admin.execute('DROP DATABASE smartplan_release_check')


@unittest.skipUnless(journey.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class PortalMigrationPostgres(unittest.TestCase):
    def test_additive_migration_preserves_prior_schema_final_offer_pdf_numbers_and_audit(self):
        prior = tuple(spec for spec in business_schema.registry() if spec.name != 'business_portal')
        with patch.object(business_schema, 'registry', return_value=prior):
            base.reset()
            bootstrap = PostgresOffice(journey.DSN)
            try:
                owner_id = bootstrap.add_user('migration@example.test', 'Synthetic-migration-password-123', 'owner')
                owner = dict(bootstrap.db.execute('SELECT * FROM users WHERE id=?', (owner_id,)).fetchone())
                project = bootstrap.add_project(owner, 'Synthetic prior portal project', 'Synthetic prior customer')
            finally:
                bootstrap.db.close()
            with psycopg.connect(journey.DSN) as admin:
                if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
                    admin.execute('CREATE ROLE "smartplan-online" LOGIN')
                admin.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(
                    sql.Literal('synthetic-business-runtime-only')))
            release.secure_database(journey.DSN, test_mode=True)
            runtime = make_conninfo(journey.DSN, user='smartplan-online', password='synthetic-business-runtime-only')
            office = PostgresOffice(runtime)
            try:
                clock = lambda: datetime(2030, 1, 10, 12, tzinfo=timezone.utc)
                api = Documents(office, clock=clock)
                api.save_settings(owner, issuer_settings('2030-01-10'))
                draft = api.create(owner, offer_data(project, '2030-01-10'))
                prepared = api.prepare_finalization(owner, draft['id'], draft['revision'])
                final = api.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
                self.assertEqual(final['archive_security'], 'postgresql_runtime_separated')
                pdf = api.archive(owner, draft['id'], 'pdf')
                before = release.snapshot_fingerprint(journey.DSN)
                self.assertNotIn('business_portal_grants', before)
            finally:
                office.db.close()
        migrate(journey.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        release.secure_database(journey.DSN, test_mode=True)
        after = release.snapshot_fingerprint(journey.DSN)
        for table, fingerprint in before.items():
            if table != 'business_schema_migrations':
                self.assertEqual(after[table], fingerprint, table)
        office = PostgresOffice(runtime)
        try:
            self.assertTrue(business_schema.require_runtime_security(office))
            self.assertEqual(Documents(office).get(owner, draft['id']), final)
            self.assertEqual(Documents(office).archive(owner, draft['id'], 'pdf'), pdf)
            self.assertEqual(office.db.execute('SELECT COUNT(*) FROM business_portal_grants').fetchone()[0], 0)
            self.assertTrue(validate_integrity(office))
            business_schema.validate_integrity(office)
        finally:
            office.db.close()


if __name__ == '__main__':
    unittest.main()
