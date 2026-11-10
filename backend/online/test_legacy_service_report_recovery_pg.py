"""Real restricted PostgreSQL readers, original archive/PDF and dump restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import hashlib
import unittest
import uuid

import psycopg

import business_schema
from business_operations import BusinessOperations
from business_offline_reports import ACTION
from core import Problem, canonical, digest
from offline_report_recovery import lookup,proof_hash
from online import release
from online import test_business_offline_binding_pg as base
from online import test_legacy_service_report_recovery as http
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve

DSN=base.bound.fixture.fixture.DSN


@unittest.skipUnless(DSN,'Own guarded disposable loopback PostgreSQL required')
class LegacyReportRecoveryPostgres(unittest.TestCase):
    setUp=base.OfflineBindingPostgres.setUp
    reopen=base.OfflineBindingPostgres.reopen
    login=base.OfflineBindingPostgres.login
    call=base.OfflineBindingPostgres.call

    def workflow(self):
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        project=self.office.add_project(self.owner,'Synthetic retained report','Synthetic customer')
        body=http.capture_body(self.office,self.owner,project)
        body['strokes']=[[[0.0,-0.0],[1e-7,0.1],[1,1.0]]]
        accepted=self.call('POST','/business/service-reports/offline',body,status=201).json
        old={k:v for k,v in body.items() if k!='project_id'}
        query=dict(schema_version=4,nonce=uuid.uuid4().hex,kind='service_report_capture',project_id=project,
            entry_id=body['entry_id'],request_id=body['request_id'],
            capture_hash=http.reference_hash([ACTION,project,body['entry_id'],old]))
        proof=self.call('POST','/business/offline/recovery/service-report',query).json
        self.assertEqual(proof['original']['request_hash'],accepted['offline_capture']['request_hash'])
        self.assertEqual(proof['original']['pdf_sha256'],accepted['pdf_sha256'])
        pdf=self.call('GET','/business/service-reports/'+accepted['id']+'/pdf?project_id='+project).data
        self.assertEqual(hashlib.sha256(pdf).hexdigest(),accepted['pdf_sha256'])
        self.assertTrue(business_schema.validate_integrity(self.office))
        return query,proof,pdf

    def test_two_real_runtime_readers_leave_all_business_and_original_archives_unchanged(self):
        query,proof,_=self.workflow();before=release.snapshot_fingerprint(DSN);barrier=threading.Barrier(2)
        def read(_):
            office=PostgresOffice(self.runtime)
            try:barrier.wait(timeout=10);return lookup(office,self.owner,query)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(read,range(2))),[proof,proof])
        after=release.snapshot_fingerprint(DSN)
        for table in before:
            if table.startswith('business_') or table in ('projects','audit','plan_versions','plan_requests'):
                self.assertEqual(after[table],before[table],table)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_original_report_proof_and_pdf_survive_actual_dump_restore_and_grant_revocation(self):
        query,proof,pdf=self.workflow();self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(lookup(restored,self.owner,query),proof)
                self.assertEqual(BusinessOperations(restored).entry_pdf(self.owner,query['project_id'],query['entry_id']),pdf)
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0],0)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()

    def test_missing_or_deliberately_damaged_original_never_proves_nonacceptance(self):
        query,proof,_=self.workflow()
        with self.assertRaises(psycopg.Error):
            with self.office.db:
                self.office.db.execute('UPDATE business_operations_requests SET result_json=? WHERE request_id=?',
                    ('{}',query['request_id']))
        self.assertEqual(lookup(self.office,self.owner,query),proof)
        # Deliberate operator-only corruption in this guarded disposable fixture;
        # application ACL/immutability guards remain unchanged in the product.
        with psycopg.connect(DSN) as operator:
            operator.execute('ALTER TABLE business_operation_entries DISABLE TRIGGER USER')
            operator.execute('UPDATE business_operation_entries SET pdf=%s WHERE id=%s',
                (b'%PDF-Synthetic-damaged-archive',query['entry_id']))
            operator.execute('ALTER TABLE business_operation_entries ENABLE TRIGGER USER')
        for value in (query,dict(query,request_id=uuid.uuid4().hex)):
            with self.assertRaises(Problem) as error:lookup(self.office,self.owner,value)
            self.assertIn(error.exception.status,(404,409))
            self.assertIsNone(getattr(error.exception,'request_resolution',None))


if __name__=='__main__':unittest.main()
