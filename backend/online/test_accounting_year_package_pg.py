"""Actual PostgreSQL runtime/issuer plus populated restore of fixed year ZIPs."""
import tempfile
import unittest
import uuid

from accounting_year_verify_v1 import verify
from business_accounting_euer import EuerAccounting
from online import test_accounting_open_items_pg as item_fixture
from online import test_business_accounting_euer_pg as euer_fixture
from online.store import PostgresOffice
from online.storage import Storage
from online.instance import bind
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore


@unittest.skipUnless(item_fixture.fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class YearPackagePostgres(unittest.TestCase):
    login=item_fixture.OpeningItemPostgres.login
    call=item_fixture.OpeningItemPostgres.call
    post=item_fixture.OpeningItemPostgres.post
    original=item_fixture.OpeningItemPostgres.original
    command=item_fixture.OpeningItemPostgres.command
    item=item_fixture.OpeningItemPostgres.item
    payment_command=item_fixture.OpeningItemPostgres.payment_command
    classify=item_fixture.OpeningItemPostgres.classify
    project=euer_fixture.EuerPostgres.project
    issuer=euer_fixture.EuerPostgres.issuer
    invoice=euer_fixture.EuerPostgres.invoice
    payment=euer_fixture.EuerPostgres.payment
    document=euer_fixture.EuerPostgres.document
    source=euer_fixture.EuerPostgres.source
    cash=euer_fixture.EuerPostgres.cash

    def setUp(self):
        item_fixture.OpeningItemPostgres.setUp(self)
        self.instance=uuid.uuid4().hex
        directory=tempfile.TemporaryDirectory(prefix='synthetic-year-package-pg-');self.addCleanup(directory.cleanup)
        self.storage_config={'server':{'path':directory.name+'/company'}}
        operator=PostgresOffice(item_fixture.fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()

    def reopen(self):
        if not hasattr(self,'instance'):return item_fixture.OpeningItemPostgres.reopen(self)
        if hasattr(self,'office'):self.office.db.close()
        self.office=PostgresOffice(self.runtime);self.addCleanup(self.office.db.close)
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',instance_id=self.instance,storage_config=self.storage_config)
        self.client=self.app.test_client()

    def test_real_invoice_original_partial_cash_and_restart_preserve_package(self):
        self.issuer();project=self.project();invoice=self.invoice(project,'100.00')
        payment=self.payment(invoice,'59.50')
        source=next(row for row in self.call('GET','/business/accounting/sources/payments').json['items'] if row['payment_id']==payment['id'])
        req=item_fixture.req
        event=self.call('POST','/business/accounting/events/import-payment',req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],account_id=self.account['id'],account_revision=1,cash_date=self.today,evidence_reference='Synthetic actual annual PG incoming'),status=201).json
        self.document(event);self.post('cash',self.cash(event));export,_=self.post('export',dict(year=self.year))
        path='/business/accounting/euer/exports/'+export['id']+'/evidence'
        metadata=self.call('GET',path).json;raw=self.call('GET',path+'/archive').data
        self.assertTrue(verify(raw,metadata['sha256'])['verified']);self.assertEqual(metadata['original_count'],1)
        self.assertEqual(self.call('GET','/business/accounting/euer/report?year='+str(self.year)).json['totals']['confirmed_income'],'59.50')
        self.reopen();self.assertEqual(self.call('GET',path).json,metadata);self.assertEqual(self.call('GET',path+'/archive').data,raw)

    def test_actual_old_supplier_package_is_identical_after_populated_restore(self):
        item,_=self.item();command=self.payment_command(item)
        payment=self.call('POST',item_fixture.BASE+'/confirm',command,status=201).json;self.classify(payment)
        export,_=self.post('export',dict(year=self.year));path='/business/accounting/euer/exports/'+export['id']+'/evidence'
        metadata=self.call('GET',path).json;raw=self.call('GET',path+'/archive').data
        self.assertTrue(verify(raw,metadata['sha256'])['verified']);self.assertEqual(metadata['original_count'],4)
        before={table:self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('business_euer_entries','business_euer_requests')}
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            restored=PostgresOffice(runtime)
            try:
                self.assertTrue(restore_report['restore_id'])
                api=EuerAccounting(restored)
                # Reading the old original does not imply approval for new
                # financial writes after restore. No reconciliation is changed.
                self.assertEqual(api.year_evidence(self.actor,export['id']),metadata)
                self.assertEqual(bytes(api.year_evidence(self.actor,export['id'],archive=True)),raw)
                self.assertEqual(before,{table:restored.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in before})
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
