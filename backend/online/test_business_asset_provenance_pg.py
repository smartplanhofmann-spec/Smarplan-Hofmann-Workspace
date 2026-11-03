"""Delivery provenance through the restricted PostgreSQL role and actual restore.

Only the pre-existing guarded loopback fixture and its disposable restore target
are used. Every order and original is synthetic; no supplier is contacted.
"""
import time
import unittest

import business_schema
from online import test_customer_execution_journey_pg as pg
from online import test_purchasing_journey as purchasing
from online.auth import totp
from online.store import PostgresOffice
from online.web import create_app
from online import test_business_asset_provenance_api as http_fixture
from online.test_postgres_accounting_components_integration import disposable_restore


@unittest.skipUnless(pg.fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class AssetDeliveryPostgresTests(unittest.TestCase):
    reopen = pg.CustomerExecutionJourneyPostgres.reopen
    article_record = purchasing.PurchasingJourneyTests.article_record
    order = purchasing.PurchasingJourneyTests.order
    receipt_body = purchasing.PurchasingJourneyTests.receipt_body
    stock = purchasing.PurchasingJourneyTests.stock
    costs = purchasing.PurchasingJourneyTests.costs
    create_chain = http_fixture.AssetDeliveryHttpTests.create_chain

    def setUp(self):
        pg.CustomerExecutionJourneyPostgres.setUp(self)
        self.project = self.call('/projects', {'name': 'Synthetic delivered device',
            'customer': 'Synthetic operator'}, status=201).json['id']
        self.location = self.call('/business/inventory/locations',
            purchasing.request(name='Synthetic receiving store'), status=201).json
        self.article = self.article_record('SYN-PG-DELIVERED-DEVICE')

    def call(self, *args, **kwargs):
        if args[0] in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH'):
            return pg.CustomerExecutionJourneyPostgres.call(self, *args, **kwargs)
        path, body = args[0], args[1] if len(args) > 1 else None
        method = kwargs.pop('method', 'POST' if body is not None else 'GET')
        return pg.CustomerExecutionJourneyPostgres.call(self, method, path, body, **kwargs)

    def login(self, email, password):
        pending = self.call('/login', dict(email=email, password=password), token=None).json
        self.assertTrue(pending['mfa_required'])
        self.secret = pending.get('enrollment', {}).get('secret', getattr(self, 'secret', None))
        step = max(int(time.time() // 30), getattr(self, 'last_step', -1) + 1)
        self.last_step = step
        return self.call('/login/verify', dict(challenge=pending['challenge'],
            code=totp(self.secret, step)), token=None).json['token']

    def test_original_asset_maintenance_and_receipts_survive_real_dump_restore(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0], 'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        command, result, document, original, service, pdf, completed = self.create_chain()
        costs = self.costs()
        originpath = '/business/assets/' + result['id'] + '/origin'
        originalpath = '/business' + document['download_path']
        servicepath = '/business/service-reports/' + service['id'] + '/pdf'
        snapshots = {name: [dict(row) for row in self.office.db.execute('SELECT * FROM ' + name)]
            for name in ('business_delivery_documents', 'business_asset_origins',
                         'business_asset_provenance_requests')}
        for name in snapshots:
            with self.assertRaises(Exception):
                with self.office.db:
                    self.office.db.execute('DELETE FROM ' + name)
            with self.assertRaises(Exception):
                with self.office.db:
                    self.office.db.execute('UPDATE ' + name + ' SET created_at=created_at')
        self.reopen()
        self.assertEqual(self.call('/business/assets/from-delivery', command, status=201).json, result)
        self.assertEqual(self.call(originalpath).data, original)
        self.assertTrue(business_schema.validate_integrity(self.office))
        previous_token, runtime = self.token, self.runtime
        self.office.db.close()
        with disposable_restore(runtime) as (_, restored_runtime, _report):
            self.office = PostgresOffice(restored_runtime)
            try:
                self.app = create_app(office=self.office, key=self.key, host='office.example.test', storage_config={})
                self.client = self.app.test_client()
                self.assertTrue(business_schema.require_runtime_security(self.office))
                self.assertTrue(business_schema.validate_integrity(self.office))
                self.call(originpath, token=previous_token, status=401)
                self.token = self.login('order-owner@example.test', 'Synthetic-owner-password-123')
                self.assertEqual(self.call('/business/assets/from-delivery', command, status=201).json, result)
                self.assertEqual(self.call(originpath).json, result['origin'])
                self.assertEqual(self.call(originalpath).data, original)
                self.assertEqual(self.call(servicepath).data, pdf)
                self.assertEqual(self.costs(), costs)
                self.assertEqual(self.call('/business/maintenance/history?project_id=' + self.project +
                    '&asset_id=' + result['id']).json['items'], [completed])
                for name, rows in snapshots.items():
                    self.assertEqual([dict(row) for row in self.office.db.execute('SELECT * FROM ' + name)], rows)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assets').fetchone()[0], 1)
                self.assertTrue(business_schema.validate_integrity(self.office))
            finally:
                self.office.db.close()


if __name__ == '__main__':
    unittest.main()
