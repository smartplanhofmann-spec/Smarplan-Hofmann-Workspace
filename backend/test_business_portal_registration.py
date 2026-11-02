"""Portal availability at the actual local/online/offline capability boundary."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import business_api
import business_schema
from core import Office, Problem


class PortalRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='synthetic-portal-registration-')
        self.addCleanup(self.temporary.cleanup)
        self.office = Office(Path(self.temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.owner = self.actor('owner')

    def actor(self, role):
        email = role + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def capabilities(self, **kwargs):
        return business_api.dispatch(self.office, self.owner, '/business/capabilities', 'GET', {}, **kwargs)[0]

    def test_local_installation_preserves_module_but_advertises_no_customer_link(self):
        metadata = self.capabilities()
        self.assertIn('business_portal', metadata['capabilities'])
        self.assertNotIn('offer_portal', metadata['features'])
        self.office.portal_origin = 'https://portal.example.test'
        self.assertIn('offer_portal', self.capabilities()['features'])
        business_schema.set_mode(self.office, 'legacy')
        metadata = self.capabilities()
        self.assertIn('offer_portal', metadata['features'])
        self.assertIn('business_portal', metadata['read_capabilities'])
        self.assertNotIn('business_portal', metadata['active_capabilities'])

    def test_invalid_origin_never_advertises_customer_access(self):
        for value in (None, '', 'http://portal.example.test', 'https://user:pass@portal.example.test',
                      'https://portal.example.test/path', 'https://portal.example.test?secret=x',
                      'https://portal.example.test#fragment', 'https://portal.example.test:invalid',
                      'https://portal.example.test\n'):
            with self.subTest(origin=value):
                self.office.portal_origin = value
                self.assertNotIn('offer_portal', self.capabilities()['features'])

    def test_new_employee_defaults_and_offline_credentials_do_not_gain_portal_access(self):
        self.office.portal_origin = 'https://portal.example.test'
        for role in ('manager', 'technician', 'accountant'):
            with self.subTest(role=role):
                metadata = business_api.capabilities(self.office, self.actor(role))
                self.assertNotIn('portal.manage', metadata['permissions'])
        metadata = self.capabilities(offline=True, offline_capabilities=['time_events', 'field_media'])
        self.assertNotIn('offer_portal', metadata['features'])
        self.assertNotIn('portal.manage', metadata['permissions'])
        self.assertNotIn('business_portal', metadata['capabilities'])
        for path, method in (('/portal/grants', 'GET'), ('/portal/grants', 'POST'),
                             ('/portal/grants/' + 'a' * 32 + '/revoke', 'POST')):
            with self.subTest(path=path, method=method), self.assertRaises(Problem) as caught:
                business_api.dispatch(self.office, self.owner, '/business' + path, method, {},
                                      offline=True, offline_capabilities=['time_events', 'field_media'])
            self.assertEqual(caught.exception.status, 403)

    def test_old_schema_without_portal_never_advertises_runtime_feature(self):
        previous = tuple(spec for spec in business_schema.registry() if spec.name != 'business_portal')
        with patch.object(business_schema, 'registry', return_value=previous):
            old = Office(Path(self.temporary.name) / 'previous.db')
            self.addCleanup(old.db.close)
            owner = dict(id=old.add_user('previous@example.test', 'Synthetic-password-123', 'owner'), role='owner')
            old.portal_origin = 'https://portal.example.test'
            metadata = business_api.capabilities(old, owner)
        self.assertNotIn('business_portal', metadata['capabilities'])
        self.assertNotIn('offer_portal', metadata['features'])


if __name__ == '__main__':
    unittest.main()
