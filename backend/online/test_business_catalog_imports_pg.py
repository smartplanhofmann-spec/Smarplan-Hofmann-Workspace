"""Catalog originals and acceptance under real separated PostgreSQL runtime.

Uses the existing guarded, disposable loopback database fixture. No providers
or supplier connections; no existing restore target is touched.
"""
import base64
import hashlib
import unittest

import psycopg
from online import test_customer_execution_journey_pg as fixture
from business_catalog_imports import validate_integrity


@unittest.skipUnless(fixture.fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class CatalogImportsPostgres(unittest.TestCase):
    def setUp(self):
        self.f = fixture.CustomerExecutionJourneyPostgres('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.source = self.f.call('POST', '/business/adapters', fixture.request(
            name='Synthetic PostgreSQL catalog', profile='catalog_csv_v1', enabled=True), status=201).json
        self.path = '/business/adapters/' + self.source['id']

    def stage(self, raw):
        command = fixture.request(filename='synthetic-original.csv', content_base64=base64.b64encode(raw).decode())
        return command, self.f.call('POST', self.path + '/import', command, status=201).json

    def test_actual_two_mib_original_immutable_acceptance_reopen_and_readonly_preview(self):
        row = ('code;name;unit;cost_price_net;unit_price_net;tax_rate\nSYN-PG;Synthetischer Zähler;ST;12.50;20;19\n').encode()
        raw = row + b'\n' * (2097152 - len(row))
        body, staged = self.stage(raw)
        path = '/business/adapters/imports/' + staged['id']
        self.assertEqual(staged['original']['size'], 2097152)
        self.assertEqual(staged['source_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.f.call('GET', path + '/original').data, raw)
        count = self.f.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
        checked = self.f.call('POST', path + '/catalog-preview', {}).json
        self.assertEqual(checked['rows'][0]['action'], 'create')
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0], count)
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0], 0)
        command = fixture.request(confirmed=True)
        accepted = self.f.call('POST', path + '/apply', command).json
        self.assertEqual(self.f.call('POST', path + '/apply', command).json, accepted)
        self.assertEqual(self.f.call('POST', self.path + '/import', body, status=201).json, accepted)
        self.assertTrue(validate_integrity(self.f.office))
        for table in ('business_catalog_originals', 'business_catalog_acceptances'):
            with self.assertRaises(psycopg.Error), psycopg.connect(self.f.runtime) as connection:
                connection.execute('DELETE FROM ' + table + ' WHERE run_id=%s', (staged['id'],))
            with self.assertRaises(psycopg.Error), psycopg.connect(fixture.fixture.DSN) as connection:
                connection.execute('DELETE FROM ' + table + ' WHERE run_id=%s', (staged['id'],))
        self.f.reopen()
        self.assertEqual(self.f.call('GET', path).json, accepted)
        self.assertEqual(self.f.call('GET', path + '/original').data, raw)
        self.assertEqual(self.f.call('GET', self.path + '/imports').json['total'], 1)

    def test_fresh_mfa_finance_and_settings_permissions_guard_history_original_and_preview(self):
        _, staged = self.stage(b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nSYN;Synthetic;ST;1;2;19\n')
        path = '/business/adapters/imports/' + staged['id']
        user_id = self.f.office.add_user('catalog-reader@example.test', 'Synthetic-catalog-reader-123', 'accountant')
        token = self.f.login('catalog-reader@example.test', 'Synthetic-catalog-reader-123')
        self.f.call('GET', path + '/original', token=token, status=403)
        self.f.call('POST', path + '/catalog-preview', {}, token=token, status=403)
        self.f.call('POST', '/business/settings/permissions', fixture.request(
            user_id=user_id, permission='settings.manage', scope='*', effect='allow', revision=0))
        self.assertEqual(self.f.call('GET', path, token=token).json['id'], staged['id'])
        self.f.call('POST', '/business/settings/permissions', fixture.request(
            user_id=user_id, permission='finance.read', scope='*', effect='deny', revision=0))
        for suffix in (path, path + '/original', self.path + '/imports'):
            self.f.call('GET', suffix, token=token, status=403)
        self.f.call('POST', path + '/catalog-preview', {}, token=token, status=403)


if __name__ == '__main__':
    unittest.main()
