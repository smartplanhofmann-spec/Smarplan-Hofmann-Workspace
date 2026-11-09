"""Actual MFA and fresh settings authorization for the descriptive scope."""
import json
import unittest
import uuid

from online import test_offline_instance_binding as fixture


PATH = '/business/commercial/rule-scope'


class CommercialCountryScopeHttpTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.OfflineInstanceBindingHttpTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_mfa_scope_tracks_own_company_settings_and_is_read_only(self):
        initial = self.f.call(self.f.a, PATH).json
        self.assertEqual(initial['issuer_country'], 'DE')
        self.assertTrue(initial['supported_issuer'])
        self.assertEqual(initial['settings_revision'], 0)
        self.f.call(self.f.a, '/business/commercial/settings', dict(
            request_id=uuid.uuid4().hex, revision=0, country='AT'))
        before = list(self.f.a['office'].db.execute('SELECT * FROM business_commercial_settings'))
        changed = self.f.call(self.f.a, PATH).json
        self.assertEqual(changed['issuer_country'], 'AT')
        self.assertFalse(changed['supported_issuer'])
        self.assertIsNone(changed['selected'])
        self.assertEqual(list(self.f.a['office'].db.execute('SELECT * FROM business_commercial_settings')), before)
        self.assertEqual(self.f.call(self.f.b, PATH).json, initial)

    def test_fresh_settings_right_and_actual_device_tokens_are_enforced(self):
        office = self.f.a['office']
        office.add_user('country-scope-worker@example.test', fixture.PASSWORD, 'technician')
        token = self.f.login(self.f.a, 'country-scope-worker@example.test')
        self.f.call(self.f.a, PATH, token=token, status=403)
        for route in ('/offline/access/v2', '/business/offline/access/v2'):
            grant = self.f.call(self.f.a, route, {}, status=201).json
            self.f.call(self.f.a, PATH, token=grant['token'],
                headers={'X-Smartplan-Offline-Binding':self.f.a['instance_id']+':'+self.f.account}, status=403)
        with office.db:
            office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.f.account,))
        self.f.call(self.f.a, PATH, status=401)

    def test_scope_has_no_method_query_or_ignored_get_body_channel(self):
        self.f.call(self.f.a, PATH, {}, status=405)
        self.f.call(self.f.a, PATH+'?country=DE', status=400)
        response = self.f.a['client'].get('/api/v1'+PATH, base_url='https://same.example.test',
            headers={'Authorization':'Bearer '+self.f.a['token']},
            content_type='application/json', data=json.dumps(dict(country='DE')))
        self.assertEqual(response.status_code, 400)
        features = self.f.call(self.f.a, '/business/capabilities').json['features']
        self.assertIn('commercial_country_scope', features)


if __name__ == '__main__':
    unittest.main()
