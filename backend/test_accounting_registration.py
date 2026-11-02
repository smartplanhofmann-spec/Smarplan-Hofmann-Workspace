"""Global accounting rights and honest local/offline capability discovery."""
from pathlib import Path
import tempfile
import unittest
import uuid

import business_api
import business_schema
from business_foundation import BusinessFoundation, permissions
from core import Office, Problem


class AccountingRegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-accounting-registration-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.foundation = BusinessFoundation(self.office)
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')

    def actor(self, role):
        email = role + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def grant(self, permission, scope='*', effect='allow'):
        return self.foundation.save_grant(self.owner, dict(request_id=uuid.uuid4().hex,
            user_id=self.tech['id'], permission=permission, scope=scope, effect=effect, revision=0))

    def call(self, actor, path, *, offline=False):
        return business_api.dispatch(self.office, actor, '/business' + path, 'GET', {},
                                    offline=offline, offline_capabilities=['time_events'])[0]

    def test_new_rights_have_no_employee_defaults_and_project_grants_are_rejected(self):
        for actor in (self.tech, self.actor('manager'), self.actor('accountant')):
            self.assertFalse(set(permissions(self.office, actor)) &
                             {'accounting.read', 'accounting.prepare', 'accounting.admin'})
        project = self.office.add_project(self.owner, 'Synthetic scoped project', 'Synthetic customer')
        before = self.office.db.execute('SELECT COUNT(*) FROM business_permission_grants').fetchone()[0]
        for name in ('accounting.read', 'accounting.prepare', 'accounting.admin'):
            for effect in ('allow', 'deny'):
                with self.subTest(permission=name, effect=effect), self.assertRaises(Problem) as caught:
                    self.grant(name, project, effect)
                self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_permission_grants').fetchone()[0], before)
        self.grant('accounting.read')
        self.assertIn('accounting.read', permissions(self.office, self.tech))

    def test_accounting_right_does_not_replace_finance_read(self):
        self.grant('accounting.read')
        with self.assertRaises(Problem) as caught:
            self.call(self.tech, '/accounting/status')
        self.assertEqual(caught.exception.status, 403)
        self.grant('finance.read')
        value = self.call(self.tech, '/accounting/status')
        self.assertEqual(value['scope'], 'authorized_sources')
        self.assertEqual(value['tax_status'], 'unconfigured')
        self.assertFalse(value['tax_result_available'])

    def test_historical_project_only_row_cannot_become_global_accounting_access(self):
        project = self.office.add_project(self.owner, 'Synthetic scope', 'Synthetic customer')
        self.office.assign(self.owner, project, self.tech['id'])
        self.grant('finance.read')
        # Simulate a pre-existing/imported scoped row, bypassing only the new
        # settings-input rule; the actual API must still enforce global access.
        with self.office.db:
            self.office.db.execute('INSERT INTO business_permission_grants '
                '(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)',
                (uuid.uuid4().hex, self.tech['id'], 'accounting.read', project,
                 'allow', self.owner['id'], '2026-11-02T00:00:00+00:00'))
        with self.assertRaises(Problem) as caught:
            self.call(self.tech, '/accounting/status')
        self.assertEqual(caught.exception.status, 403)

    def test_local_capability_remains_honest_in_legacy_and_absent_for_offline(self):
        self.assertIn('accounting_prejournal', self.call(self.owner, '/capabilities')['features'])
        before = self.office.db.total_changes
        status = self.call(self.owner, '/accounting/status')
        self.assertEqual(status['profile_status'], 'unconfigured')
        self.assertFalse(status['tax_result_available'])
        self.assertEqual(self.office.db.total_changes, before)
        business_schema.set_mode(self.office, 'legacy')
        self.assertIn('accounting_prejournal', self.call(self.owner, '/capabilities')['features'])
        self.assertFalse(self.call(self.owner, '/accounting/status')['writes_allowed'])
        offline = self.call(self.owner, '/capabilities', offline=True)
        self.assertNotIn('accounting_prejournal', offline['features'])
        self.assertNotIn('business_accounting', offline['capabilities'])
        with self.assertRaises(Problem) as caught:
            self.call(self.owner, '/accounting/status', offline=True)
        self.assertEqual(caught.exception.status, 403)


if __name__ == '__main__':
    unittest.main()
