"""Bound PostgreSQL project receipt: concurrent creation, MFA and actual restore."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import unittest
import uuid

from business_foundation import BusinessFoundation, project_creation_scope, runtime_features
from core import canonical
from online import test_business_company_handover_pg as bound
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(bound.fixture.fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class ProjectCreationJournalPostgres(unittest.TestCase):
    setUp = bound.CompanyHandoverPostgres.setUp
    reopen = bound.CompanyHandoverPostgres.reopen
    login = bound.CompanyHandoverPostgres.login
    call = bound.CompanyHandoverPostgres.call

    def test_bound_original_receipt_concurrent_creation_and_real_restore(self):
        scope = self.call('GET', '/business/capabilities').json['project_creation_scope']
        self.assertEqual(scope, dict(schema_version=1, instance_id=self.instance, account_id=self.owner['id']))
        before = {table: self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                  for table in ('projects', 'customers', 'business_foundation_requests')}
        body = dict(request_id=uuid.uuid4().hex, name='Synthetic durable project',
                    customer='Synthetic durable customer')
        barrier = threading.Barrier(2)

        def create(_):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return office.add_project(self.owner, **body)
            finally:
                office.db.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(create, range(2)))
        self.assertEqual(results[0], results[1])
        for table, count in before.items():
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], count+1)
        result = self.call('POST', '/projects', body, status=201).json
        self.assertEqual(result, {'id': results[0]})
        receipt = self.call('GET', '/business/project-creations/'+body['request_id']).json
        fingerprint = hashlib.sha256(canonical(dict(operation='core.project.create:v1',
            data=dict(body, customer_id=None))).encode()).hexdigest()
        self.assertEqual(receipt, dict(scope, request_id=body['request_id'],
            request_hash=fingerprint, project_id=results[0]))
        self.office.db.close()

        with disposable_restore(self.runtime) as (target, runtime, report):
            operator = PostgresOffice(target)
            try:
                approve(operator, evidence_for(operator, report))
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(project_creation_scope(restored, self.owner), scope)
                self.assertIn('project_creation_journal', runtime_features(restored))
                self.assertEqual(BusinessFoundation(restored).project_creation_receipt(
                    self.owner, body['request_id']), receipt)
                self.assertEqual(restored.add_project(self.owner, **body), results[0])
                for table, count in before.items():
                    self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0], count+1)
            finally:
                restored.db.close()
