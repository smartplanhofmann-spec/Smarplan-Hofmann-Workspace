"""Explicit offline-workspace grants without widening old plan-only tokens."""
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import Office, Problem, digest
import plan_access


class WorkspaceAccessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-workspace-access-')
        self.path = Path(self.temporary.name) / 'office.sqlite'
        self.office = Office(self.path)
        self.owner = self.actor('owner')
        self.technician = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Assigned synthetic project', 'Synthetic Customer')
        self.private_project = self.office.add_project(self.owner, 'Other synthetic project', 'Other Customer')
        self.office.assign(self.owner, self.project, self.technician['id'])

    def tearDown(self):
        self.office.db.close()
        self.temporary.cleanup()

    def actor(self, role):
        email = role + '@example.test'
        identifier = self.office.add_user(email, 'Synthetic-password-123', role)
        return dict(id=identifier, email=email, role=role)

    def grant(self, actor=None, *, workspace=False):
        with self.office.lock, self.office.db:
            return plan_access.issue(self.office, actor or self.technician, workspace=workspace)

    def authenticate(self, token):
        return plan_access.user(self.office, token)

    def denied(self, token):
        with self.assertRaises(Problem) as caught:
            self.authenticate(token)
        self.assertEqual(caught.exception.status, 401)

    def test_default_issue_retains_plan_namespace_and_new_grant_is_explicit(self):
        old = self.grant()['token']
        new = self.grant(workspace=True)['token']
        self.assertTrue(old.startswith(plan_access.PREFIX))
        self.assertFalse(plan_access.allows_workspace(old))
        self.assertTrue(new.startswith(plan_access.WORKSPACE_PREFIX))
        self.assertTrue(new.startswith(plan_access.PREFIX))
        self.assertTrue(plan_access.allows_workspace(new))
        self.assertEqual(self.authenticate(old), self.technician)
        self.assertEqual(self.authenticate(new), self.technician)
        stored = {row['token'] for row in self.office.db.execute('SELECT token FROM plan_sessions')}
        self.assertEqual(stored, {digest(old), digest(new)})
        self.assertNotIn(old, stored)
        self.assertNotIn(new, stored)
        events = [row['action'] for row in self.office.db.execute(
            "SELECT action FROM audit WHERE action IN ('plan.offline_access','workspace.offline_access') ORDER BY id")]
        self.assertEqual(events, ['plan.offline_access', 'workspace.offline_access'])

    def test_adding_or_removing_workspace_prefix_cannot_change_a_stored_grant(self):
        old = self.grant()['token']
        forged_workspace = plan_access.WORKSPACE_PREFIX + old[len(plan_access.PREFIX):]
        self.assertTrue(plan_access.allows_workspace(forged_workspace))
        self.denied(forged_workspace)
        new = self.grant(workspace=True)['token']
        forged_plan = plan_access.PREFIX + new[len(plan_access.WORKSPACE_PREFIX):]
        self.assertFalse(plan_access.allows_workspace(forged_plan))
        self.denied(forged_plan)
        self.assertEqual(self.authenticate(old), self.technician)
        self.assertEqual(self.authenticate(new), self.technician)

    def test_workspace_prefix_is_not_authentication_or_cross_project_authorization(self):
        self.assertTrue(plan_access.allows_workspace(plan_access.WORKSPACE_PREFIX + 'not-a-session'))
        self.denied(plan_access.WORKSPACE_PREFIX + 'not-a-session')
        token = self.grant(workspace=True)['token']
        actor = self.authenticate(token)
        self.assertEqual(self.office.project(actor, self.project)['id'], self.project)
        with self.assertRaises(Problem) as caught:
            self.office.project(actor, self.private_project)
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(Problem) as caught:
            self.office.users(actor)
        self.assertEqual(caught.exception.status, 403)
        # Assignment revocation is effective without changing or refreshing the
        # device token, even though its namespace remains recognizable.
        self.office.assign(self.owner, self.project, self.technician['id'], remove=True)
        actor = self.authenticate(token)
        self.assertTrue(plan_access.allows_workspace(token))
        with self.assertRaises(Problem) as caught:
            self.office.project(actor, self.project)
        self.assertEqual(caught.exception.status, 404)

    def test_both_namespaces_keep_the_exact_seven_day_expiry_boundary(self):
        issued = 1_792_843_200.0
        for workspace in (False, True):
            with self.subTest(workspace=workspace), patch('plan_access.time.time', return_value=issued):
                grant = self.grant(workspace=workspace)
            token = grant['token']
            self.assertEqual(datetime.fromisoformat(grant['expires_at']) - datetime.fromisoformat(grant['issued_at']),
                             timedelta(days=7))
            with patch('plan_access.time.time', return_value=issued + 7 * 86400 - 1):
                self.assertEqual(self.authenticate(token), self.technician)
            with patch('plan_access.time.time', return_value=issued + 7 * 86400):
                self.denied(token)

    def test_role_and_password_changes_invalidate_the_old_credentials(self):
        for changes in ({'role': 'manager'}, {'password': 'New-synthetic-password-123'}):
            old = self.grant()['token']
            workspace = self.grant(workspace=True)['token']
            self.office.update_user(self.owner, self.technician['id'], changes)
            self.denied(old)
            self.denied(workspace)
            fresh = self.grant(workspace=True)['token']
            actor = self.authenticate(fresh)
            self.assertEqual(actor['role'], 'manager')

    def test_current_database_role_is_checked_even_when_a_session_row_remains(self):
        old = self.grant()['token']
        workspace = self.grant(workspace=True)['token']
        with self.office.db:
            self.office.db.execute('UPDATE users SET role=? WHERE id=?', ('manager', self.technician['id']))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 2)
        self.denied(old)
        self.denied(workspace)
        fresh = self.grant(workspace=True)['token']
        self.assertEqual(self.authenticate(fresh)['role'], 'manager')

    def test_only_an_explicit_boolean_can_request_the_wider_namespace(self):
        for value in (None, 1, 'false', 'workspace', []):
            with self.assertRaises(Problem) as caught:
                self.grant(workspace=value)
            self.assertEqual(caught.exception.status, 400)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0], 0)

    def test_deactivation_reactivation_and_explicit_revoke_never_revive_old_grants(self):
        old = self.grant()['token']
        workspace = self.grant(workspace=True)['token']
        self.office.update_user(self.owner, self.technician['id'], {'active': False})
        self.denied(old)
        self.denied(workspace)
        self.office.update_user(self.owner, self.technician['id'], {'active': True})
        self.denied(old)
        self.denied(workspace)
        fresh = self.grant(workspace=True)['token']
        with self.office.lock, self.office.db:
            self.assertEqual(plan_access.revoke(self.office, fresh), {'ok': True})
            self.assertEqual(plan_access.revoke(self.office, fresh), {'ok': True})
        self.denied(fresh)

    def test_namespace_helper_treats_nonstrings_and_similar_names_as_not_granted(self):
        for value in (None, 1, False, b'offline_workspace_x', {}, 'workspace_x', 'offline_workspace',
                      'prefix_offline_workspace_secret', 'offline_workspaces_secret'):
            self.assertFalse(plan_access.allows_workspace(value))
        self.denied(plan_access.WORKSPACE_PREFIX)

    def test_existing_grants_and_scope_survive_a_database_reopen(self):
        old = self.grant()['token']
        workspace = self.grant(workspace=True)['token']
        reopened = Office(self.path)
        try:
            self.assertEqual(plan_access.user(reopened, old), self.technician)
            self.assertEqual(plan_access.user(reopened, workspace), self.technician)
            self.assertFalse(plan_access.allows_workspace(old))
            self.assertTrue(plan_access.allows_workspace(workspace))
        finally:
            reopened.db.close()


if __name__ == '__main__':
    unittest.main()
