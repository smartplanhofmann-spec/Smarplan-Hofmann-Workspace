"""Actual MFA/HTTP role boundary, create retry and current access revocation."""
import unittest

from business_foundation import BusinessFoundation
from online import test_business_planning_time_api as base
from test_business_planning import rid


class EmployeeAccountSelectionHttp(unittest.TestCase):
    setUp = base.BusinessPlanningTimeApiTests.setUp
    # The shared MFA fixture owns its temporary database and cleanup callbacks.
    from online.test_workspace_api import WorkspaceHttpFlow as _Flow
    call = _Flow.call
    mfa_login = _Flow.mfa_login
    add_actor = _Flow.add_actor

    def hr(self):
        identifier, token = self.add_actor('technician')
        actor = self.office.user(token)
        foundation = BusinessFoundation(self.office)
        for permission in ('personnel.read', 'personnel.manage'):
            foundation.save_grant(self.owner, dict(request_id=rid(), user_id=identifier,
                permission=permission, scope='*', effect='allow', revision=0))
        return identifier, actor, token, foundation

    def test_actual_nonowner_mfa_selects_accounts_and_creates_one_profile_with_same_nonce(self):
        identifier, actor, token, _ = self.hr()
        result = self.call('GET', '/business/employees/account-selection', token=token).json
        self.assertTrue(all(set(row) == {'id', 'email'} for row in result['items']))
        self.assertIn('employee_account_selection_v1', self.call('GET', '/business/capabilities', token=token).json['features'])
        self.call('GET', '/users', token=token, status=403)
        body = dict(request_id=rid(), user_id=identifier, name='Synthetic HR employee', weekly_minutes=1200, hourly_cost_minor=2500)
        first = self.call('POST', '/business/employees', body, token=token, status=201).json
        self.assertEqual(self.call('POST', '/business/employees', body, token=token, status=201).json, first)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_employees WHERE user_id=?', (identifier,)).fetchone()[0], 1)

    def test_current_revoke_offline_role_and_query_are_denied(self):
        identifier, actor, token, foundation = self.hr()
        self.call('GET', '/business/employees/account-selection', token=token)
        foundation.save_grant(self.owner, dict(request_id=rid(), user_id=identifier,
            permission='personnel.manage', scope='*', effect='deny', revision=1))
        self.call('GET', '/business/employees/account-selection', token=token, status=403)
        self.call('GET', '/business/employees/account-selection?project_id='+self.project, status=400)
        self.call('POST', '/business/employees/account-selection', {}, status=405)
        offline=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET', '/business/employees/account-selection', token=offline, status=403)

    def test_actual_hr_can_close_existing_profile_after_its_user_login_is_disabled(self):
        _, _, token, _ = self.hr()
        self.call('POST', '/users/'+self.technician_id, {'active': False})
        body=dict(request_id=rid(), revision=self.employee['revision'], active=False, employment_to='2026-10-31')
        path='/business/employees/'+self.employee['id']
        first=self.call('POST', path, body, token=token).json
        self.assertIs(first['active'], False)
        self.assertEqual(first['user_id'], self.technician_id)
        self.assertEqual(self.call('POST', path, body, token=token).json, first)


if __name__ == '__main__': unittest.main()
