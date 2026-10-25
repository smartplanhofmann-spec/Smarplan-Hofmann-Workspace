"""Device scopes stay additive: a legacy plan/workspace grant never gains time access."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Office, Problem
import plan_access
import business_api


class BusinessDeviceScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.office=Office(Path(self.temp.name)/'synthetic.sqlite3');self.addCleanup(self.office.db.close)
        uid=self.office.add_user('scope@example.test','Synthetic-password-123','owner')
        self.actor={'id':uid,'email':'scope@example.test','role':'owner'}

    def test_legacy_grants_keep_their_old_namespaces_and_never_get_business_scope(self):
        with self.office.db:
            plan=plan_access.issue(self.office,self.actor)
            workspace=plan_access.issue(self.office,self.actor,workspace=True)
        self.assertTrue(plan['token'].startswith('offline_'))
        self.assertFalse(plan_access.allows_business(plan['token']))
        self.assertTrue(workspace['token'].startswith('offline_workspace_'))
        self.assertFalse(plan_access.allows_business(workspace['token']))

    def test_new_explicit_grant_authenticates_same_user_and_includes_only_classified_scope(self):
        with self.office.db:
            grant=plan_access.issue(self.office,self.actor,workspace=True,business=True)
        self.assertTrue(grant['token'].startswith('offline_business_'))
        self.assertTrue(plan_access.allows_workspace(grant['token']))
        self.assertTrue(plan_access.allows_business(grant['token']))
        self.assertEqual(plan_access.user(self.office,grant['token'])['id'],self.actor['id'])
        forged=grant['token'].replace('offline_business_','offline_workspace_',1)
        with self.assertRaises(Problem):plan_access.user(self.office,forged)

    def test_business_namespace_alone_never_authenticates_a_token(self):
        forged='offline_business_'+'X'*43
        self.assertTrue(plan_access.allows_business(forged))
        with self.assertRaises(Problem):plan_access.user(self.office,forged)

    def test_business_scope_requires_workspace_and_explicit_boolean(self):
        for kwargs in [{'business':True},{'workspace':True,'business':1}]:
            with self.assertRaises(Problem):plan_access.issue(self.office,self.actor,**kwargs)

    def test_scope_does_not_grant_finance_or_other_employee_lists(self):
        self.assertFalse(business_api.offline_path('/business/payments','GET'))
        self.assertFalse(business_api.offline_path('/business/time/entries','GET'))
        self.assertTrue(business_api.offline_path('/business/time/entries/'+'a'*32,'GET'))

if __name__=='__main__':unittest.main()
