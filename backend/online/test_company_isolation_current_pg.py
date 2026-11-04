"""Current cross-company acceptance with actual PostgreSQL roles and processes.

Only the guarded reserved disposable cluster; every company is newly provisioned
with random names by the existing fixture. No production accounts or providers.
"""
import multiprocessing
import os
import unittest

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from online import test_provisioning_pg as original
from online.test_company_isolation_current import CurrentCompanyScenario, PARSER_PYTHON


@unittest.skipUnless(original.DSN, 'Reserved disposable PostgreSQL55433 required')
class CompanyIsolationCurrentPostgres(CurrentCompanyScenario, unittest.TestCase):
    cleanup = original.ProvisioningPostgres.cleanup
    office = original.ProvisioningPostgres.office

    def setUp(self):
        original.ProvisioningPostgres.setUp(self)
        context = multiprocessing.get_context('spawn')
        for index, company in enumerate(self.companies):
            item = company['company']
            company.update(host=item.public_host, instance_id=item.instance_id,
                marker='PGONLY' + ('ALPHA' if index == 0 else 'BETA'),
                password='Synthetic-owner-password-123')
            ports = context.Queue()
            process = context.Process(target=original.serve_fixture, args=(item.document(), company['dsn'],
                company['key'], str(company['directory'] / 'documents'), company['privacy'], ports))
            process.start()
            self.processes.append(process)
            company.update(port=ports.get(timeout=25), pid=process.pid)

    def verify_actual_roles(self):
        for own, foreign in (self.companies, self.companies[::-1]):
            office = self.office(own)
            try:
                self.assertEqual(office.db.execute('SELECT current_user').fetchone()[0], own['company'].roles.runtime)
                self.assertEqual(office.db.execute('SELECT current_database()').fetchone()[0], own['company'].roles.database)
                self.assertTrue(business_schema.require_runtime_security(office))
                self.assertEqual(office.db.execute('SELECT instance_id FROM business_instance_identity').fetchone()[0], own['instance_id'])
            finally:
                office.db.close()
            with self.assertRaises(psycopg.Error):
                psycopg.connect(make_conninfo(own['dsn'], dbname=foreign['company'].roles.database), connect_timeout=5)

    def test_actual_two_runtime_roles_originals_search_and_full_archives(self):
        self.verify_actual_roles()
        self.current_originals_search_and_export()
        self.verify_actual_roles()

    def test_actual_two_runtime_roles_contexts_equal_rule_ids_events_and_actions(self):
        self.verify_actual_roles()
        self.current_context_events_and_same_rule_ids()
        self.verify_actual_roles()

    def test_actual_two_runtime_roles_private_originals_and_fresh_permissions(self):
        self.verify_actual_roles()
        self.current_private_originals_and_fresh_permissions()
        self.verify_actual_roles()

    @unittest.skipUnless(PARSER_PYTHON, 'Set SMARTPLAN_TEST_PARSER_PYTHON for actual local parser acceptance')
    def test_actual_two_runtime_roles_queue_and_separate_parser_processes(self):
        self.verify_actual_roles()
        self.current_queue_and_actual_parser_processes()
        self.verify_actual_roles()


if __name__ == '__main__':
    unittest.main()
