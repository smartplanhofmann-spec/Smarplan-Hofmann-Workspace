"""Real pg_dump/pg_restore preserves offline originals and revokes grants.

Only the guarded, disposable loopback smartplan_check fixture is reset. The
restore helper creates and removes its own smartplan_release_check target.
Runtime access uses the real restricted role; no provider is contacted.
"""
import hashlib
import time
import unittest

from unittest.mock import patch

import business_schema
from online.auth import totp
from online import test_business_journey_pg as fixture
from online.test_business_offline_reports_api import capture_body, PATH
from online.test_postgres_accounting_components_integration import disposable_restore
from online.store import PostgresOffice
from online.web import create_app


@unittest.skipUnless(fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class OfflineReportPostgresRestoreTests(unittest.TestCase):
    call = fixture.BusinessJourneyPostgres.call

    def setUp(self):
        # Retain the fixture's synthetic vault key exactly as an operator must
        # after restore. The original factory, auth and handlers run unchanged.
        def application(**kwargs):
            self.key = kwargs['key']
            return create_app(**kwargs)
        with patch.object(fixture, 'create_app', side_effect=application):
            fixture.BusinessJourneyPostgres.setUp(self)

    def login(self, email, password):
        pending = self.call('POST', '/login', dict(email=email, password=password), token=None).json
        self.assertTrue(pending['mfa_required'])
        self.secret = pending.get('enrollment', {}).get('secret', getattr(self, 'secret', None))
        step = max(int(time.time() // 30), getattr(self, 'last_step', -1) + 1)
        self.last_step = step
        return self.call('POST', '/login/verify', dict(challenge=pending['challenge'],
            code=totp(self.secret, step)), token=None).json['token']

    def test_actual_dump_restore_keeps_integrated_signed_capture_receipt_and_pdf(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        project = self.call('POST', '/projects', dict(name='Synthetic restore project',
            customer='Synthetic restore customer'), status=201).json['id']
        grant = self.call('POST', '/business/offline/access', {}, status=201).json
        body = capture_body(self.office, self.office.user(self.token), project)
        diagnosis_path = PATH + '/diagnosis'
        self.assertIs(self.call('GET', '/business/capabilities', token=grant['token']).json['offline_report_diagnosis_supported'], True)
        self.assertEqual(self.call('POST', diagnosis_path, body, token=grant['token']).json['state'], 'ready')
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE projects SET name=? WHERE id=?', ('Changed before import', project))
        changed = self.call('POST', diagnosis_path, body, token=grant['token']).json
        self.assertEqual(changed['state'], 'context_changed')
        self.assertIsNone(changed['server_record'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0], 0)
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE projects SET name=? WHERE id=?', (body['content']['project_name'], project))
        row = self.call('POST', PATH, body, token=grant['token'], status=201).json
        with self.office.lock, self.office.db:
            self.office.db.execute('UPDATE projects SET name=? WHERE id=?', ('Changed after original import', project))
        self.assertEqual(self.call('POST', diagnosis_path, body, token=grant['token']).json['server_record'], row)
        archive = '/business/service-reports/' + row['id']
        pdf = self.call('GET', archive + '/pdf', token=grant['token']).data
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), row['pdf_sha256'])
        versions = [dict(item) for item in self.office.db.execute(
            'SELECT * FROM business_operation_versions WHERE object_id=? ORDER BY revision', (row['id'],))]
        receipt = dict(self.office.db.execute('SELECT * FROM business_operations_requests WHERE request_id=?',
            (body['request_id'],)).fetchone())
        self.assertTrue(business_schema.validate_integrity(self.office))
        runtime = self.office.db.dsn
        self.office.db.close()
        with disposable_restore(runtime) as (target, restored_runtime, report):
            self.office = PostgresOffice(restored_runtime)
            try:
                self.assertTrue(business_schema.require_runtime_security(self.office))
                self.assertTrue(business_schema.validate_integrity(self.office))
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_device_grants').fetchone()[0], 0)
                self.app = create_app(office=self.office, key=self.key, host='office.example.test')
                self.client = self.app.test_client()
                self.call('POST', PATH, body, token=grant['token'], status=401)
                self.call('POST', diagnosis_path, body, token=grant['token'], status=401)
                self.call('GET', archive + '/pdf', token=grant['token'], status=401)
                self.token = self.login('journey-owner@example.test', 'Synthetic-owner-password-123')
                renewed = self.call('POST', '/business/offline/access', {}, status=201).json
                diagnosed = self.call('POST', diagnosis_path, body, token=renewed['token']).json
                self.assertEqual(diagnosed['state'], 'accepted')
                self.assertEqual(diagnosed['server_record'], row)
                self.assertEqual(diagnosed['current_context']['project_name'], 'Changed after original import')
                self.assertEqual(self.call('POST', PATH, body, token=renewed['token'], status=201).json, row)
                self.assertEqual(self.call('GET', archive, token=renewed['token']).json, row)
                self.assertEqual(self.call('GET', archive + '/pdf', token=renewed['token']).data, pdf)
                self.assertEqual([dict(item) for item in self.office.db.execute(
                    'SELECT * FROM business_operation_versions WHERE object_id=? ORDER BY revision', (row['id'],))], versions)
                self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_operations_requests WHERE request_id=?',
                    (body['request_id'],)).fetchone()), receipt)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0], 1)
                self.assertEqual(self.office.db.execute('SELECT financial_reconciliation_required FROM business_restore_state').fetchone()[0], 1)
                self.assertTrue(business_schema.validate_integrity(self.office))
            finally:
                self.office.db.close()


if __name__ == '__main__':
    unittest.main()
