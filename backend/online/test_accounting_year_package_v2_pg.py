"""Bound real PostgreSQL snapshots and actual restored v2 original journals."""
import tempfile
import unittest
import uuid
from accounting_year_verify_v2 import verify
from business_accounting_euer import EuerAccounting
from online import test_accounting_year_openings_pg as year
from online import test_accounting_year_package_pg as package
from online.store import PostgresOffice
from online.storage import Storage
from online.instance import bind
from online.test_postgres_accounting_components_integration import disposable_restore

@unittest.skipUnless(year.fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class YearPackageCarryoverPostgres(unittest.TestCase):
    login=year.YearValuesPostgres.login
    call=year.YearValuesPostgres.call
    post=year.YearValuesPostgres.post
    original=year.YearValuesPostgres.original
    command=year.YearValuesPostgres.command
    payment_command=year.YearValuesPostgres.payment_command
    classify_payment=year.YearValuesPostgres.classify_payment
    year_command=year.YearValuesPostgres.year_command
    classify=year.YearValuesPostgres.classify
    reopen=package.YearPackagePostgres.reopen

    def setUp(self):
        year.YearValuesPostgres.setUp(self)
        self.instance=uuid.uuid4().hex
        directory=tempfile.TemporaryDirectory(prefix='synthetic-year-package-v2-pg-');self.addCleanup(directory.cleanup)
        self.storage_config={'server':{'path':directory.name+'/company'}}
        operator=PostgresOffice(year.fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()

    def test_actual_historical_journal_zip_is_identical_after_populated_restore(self):
        old,_=self.post('export',{'year':2026});base='/business/accounting/euer/exports/'
        old_meta=self.call('GET',base+old['id']+'/evidence').json;old_raw=self.call('GET',base+old['id']+'/evidence/archive').data
        command=self.year_command();entry=self.call('POST',year.BASE+'/confirm',command,status=201).json;self.classify(entry)
        paid=self.call('POST',year.old.BASE+'/confirm',self.payment_command(self.item,'59.50'),status=201).json;self.classify_payment(paid)
        exported,_=self.post('export',{'year':2026});metadata=self.call('GET',base+exported['id']+'/evidence').json
        raw=self.call('GET',base+exported['id']+'/evidence/archive').data
        self.assertEqual((metadata['format'],metadata['original_year_complete']),('smartplan-year-evidence-v2',True))
        self.assertTrue(verify(raw,metadata['sha256'])['verified']);self.assertFalse(verify(raw,metadata['sha256'])['intrinsic_dependency_closure'])
        self.assertEqual(self.call('GET',base+old['id']+'/evidence/archive').data,old_raw)
        self.reopen();self.assertEqual(self.call('GET',base+exported['id']+'/evidence/archive').data,raw)
        counts={table:self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('business_euer_entries','business_euer_requests')+year.TABLES}
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            restored=PostgresOffice(runtime)
            try:
                api=EuerAccounting(restored)
                for entry,meta,data in ((old,old_meta,old_raw),(exported,metadata,raw)):
                    self.assertEqual(api.year_evidence(self.actor,entry['id']),meta)
                    self.assertEqual(bytes(api.year_evidence(self.actor,entry['id'],archive=True)),data)
                self.assertEqual(counts,{table:restored.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in counts})
                self.assertTrue(restore_report['restore_id'])
            finally:restored.db.close()

if __name__=='__main__':unittest.main()
