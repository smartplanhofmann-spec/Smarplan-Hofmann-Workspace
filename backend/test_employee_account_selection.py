"""HR can select active accounts without obtaining user-administration access."""
import unittest

from business_foundation import BusinessFoundation
from business_planning import dispatch, methods
from core import Problem
from test_business_planning import BusinessFixture, rid


class EmployeeAccountSelectionTests(BusinessFixture, unittest.TestCase):
    def setUp(self):
        self.prepare()
        self.hr_id = self.office.add_user('hr@example.test', 'Synthetic-hr-password-123', 'technician')
        self.hr = self.office.user(self.office.login('hr@example.test', 'Synthetic-hr-password-123'))
        self.foundation = BusinessFoundation(self.office)
        for permission in ('personnel.read', 'personnel.manage'):
            self.grant(permission, 'allow')

    def grant(self, permission, effect, revision=0, scope='*'):
        return self.foundation.save_grant(self.owner, dict(request_id=rid(), user_id=self.hr_id,
            permission=permission, scope=scope, effect=effect, revision=revision))

    def test_hr_sees_only_active_account_identity_without_admin_fields_or_mutation(self):
        inactive = self.office.add_user('inactive@example.test', 'Synthetic-inactive-password-123', 'technician')
        with self.office.db: self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (inactive,))
        before = [tuple(row) for row in self.office.db.execute('SELECT * FROM users ORDER BY id')]
        self.problem(403, lambda: self.office.users(self.hr))
        result = self.planning.employee_account_selection(self.hr)
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual({row['id'] for row in result['items']}, {self.owner_id, self.technician['id'], self.hr_id})
        self.assertTrue(all(set(row) == {'id', 'email'} for row in result['items']))
        self.assertEqual(result['items'], sorted(result['items'], key=lambda row: (row['email'], row['id'])))
        self.assertEqual(before, [tuple(row) for row in self.office.db.execute('SELECT * FROM users ORDER BY id')])

    def test_both_hr_permissions_and_fresh_actor_are_required(self):
        self.problem(403, lambda: self.planning.employee_account_selection(self.technician))
        for permission in ('personnel.manage', 'personnel.read'):
            self.grant(permission, 'deny', 1)
            self.problem(403, lambda: self.planning.employee_account_selection(self.hr))
            self.grant(permission, 'allow', 2)
        with self.office.db: self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.hr_id,))
        self.problem(401, lambda: self.planning.employee_account_selection(self.hr))

    def test_project_scoped_manage_is_not_global_account_directory_access(self):
        self.grant('personnel.manage', 'deny', 1)
        self.grant('personnel.manage', 'allow', scope=self.project)
        self.problem(403, lambda: self.planning.employee_account_selection(self.hr))

    def test_new_route_refuses_parameters_body_and_wrong_method(self):
        path = '/employees/account-selection'
        self.assertEqual(methods(path), 'GET')
        self.assertEqual(dispatch(self.office, self.hr, path, 'GET', {'_query': {}})[1:], (200, 'application/json'))
        for data in ({'_query': {'project_id': self.project}}, {'_query': {}, 'user_id': self.owner_id}, {'_query': []}):
            self.problem(400, lambda: dispatch(self.office, self.hr, path, 'GET', data))
        self.problem(405, lambda: dispatch(self.office, self.hr, path, 'POST', {}))

    def test_more_than_500_accounts_are_not_returned_as_a_complete_subset(self):
        # The limit is checked over actual SQL rows; password hashes are synthetic.
        with self.office.db:
            self.office.db.executemany('INSERT INTO users(id,email,salt,password,role,active) VALUES(?,?,?,?,?,1)',
                [(rid(), f'synthetic-{n}@example.test', 'synthetic', 'synthetic', 'technician') for n in range(498)])
        self.problem(413, lambda: self.planning.employee_account_selection(self.hr))

    def test_locked_login_does_not_prevent_authorized_closure_of_its_existing_employee(self):
        before = [tuple(row) for row in self.office.db.execute('SELECT * FROM business_employee_terms WHERE employee_id=? ORDER BY revision', (self.employee['id'],))]
        with self.office.db: self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.technician['id'],))
        body = dict(request_id=rid(), id=self.employee['id'], revision=1,
            active=False, employment_to='2026-10-25')
        result = self.planning.save_employee(self.hr, body)
        self.assertFalse(result['active'])
        self.assertEqual(result['employment_to'], '2026-10-25')
        self.assertEqual(result['user_id'], self.technician['id'])
        self.assertEqual(self.planning.save_employee(self.hr, body), result)
        after = [tuple(row) for row in self.office.db.execute('SELECT * FROM business_employee_terms WHERE employee_id=? ORDER BY revision', (self.employee['id'],))]
        self.assertEqual(after[:len(before)], before)
        self.problem(401, lambda: self.planning.employee_account_selection(self.technician))

    def test_new_employee_still_needs_an_active_existing_account(self):
        disabled = self.office.add_user('disabled-new@example.test', 'Synthetic-disabled-password-123', 'technician')
        with self.office.db: self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (disabled,))
        self.problem(400, lambda: self.planning.save_employee(self.hr, dict(request_id=rid(), user_id=disabled, name='Synthetic blocked new profile')))


if __name__ == '__main__': unittest.main()
