"""Executable inventory of existing continuation and the actual opening gap."""
import unittest
import uuid

from core import Problem
import test_business_accounting_euer as fixture


class ExistingOpeningItemInventory(unittest.TestCase):
    def setUp(self):
        self.f=fixture.EuerWorkflowTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.owner=self.f.owner

    def test_existing_archived_invoice_remains_payable_after_cutover_without_reissue(self):
        f=self.f;f.configure(bookkeeping_start='2026-11-02')
        invoice=f.fixture.invoice();before=self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0]
        payment=f.fixture.finance.record_payment(self.owner,dict(request_id=uuid.uuid4().hex,
            source_id='actual-post-start-payment',kind='receipt',amount='59.50',currency='EUR',
            booking_date='2026-11-02',reference='Actual incoming remainder',
            allocations=[dict(document_id=invoice['id'],amount='59.50')]))
        event=f.documented(f.fixture.api.import_payment(self.owner,f.fixture.import_body(payment)))
        f.post('cash',f.cash_payload(event))
        item=next(i for i in f.fixture.finance.open_items(self.owner)['items'] if i['id']==invoice['id'])
        self.assertEqual((item['paid'],item['open']),('59.50','59.50'))
        report=f.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_income'],'59.50')
        self.assertEqual(report['totals']['confirmed_output_vat'],'9.50')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],before)

    def test_prestart_supplier_invoice_can_be_captured_paid_but_old_input_vat_cannot_be_shifted(self):
        f=self.f;f.configure(vat_effective_from='2025-01-01')
        receipt=f.incoming(day='2025-12-15');event=f.payout(receipt,day='2026-02-15')
        with self.assertRaises(Problem) as error:f.api.preview(self.owner,f.body('input_vat',f.vat_payload(receipt,day='2025-12-15')))
        self.assertEqual(error.exception.status,409)
        self.assertIn('Buchführungs',error.exception.message)
        with self.assertRaises(Problem) as error:f.api.preview(self.owner,f.body('cash',f.cash_payload(event,'materials')))
        self.assertEqual(error.exception.status,409)
        self.assertIn('Vorsteuerrecht',error.exception.message)
        shifted=f.vat_payload(receipt,day='2025-12-15');shifted['entitlement_date']='2026-01-01'
        with self.assertRaises(Problem) as error:f.api.preview(self.owner,f.body('input_vat',shifted))
        self.assertEqual(error.exception.status,400)
        self.assertEqual(f.api.report(self.owner,2026)['totals']['confirmed_input_vat'],'0.00')

    def test_unallocated_receipt_is_real_cash_but_not_an_external_invoice_tax_source(self):
        f=self.f;payment=f.fixture.payment(amount='119.00')
        event=f.fixture.api.import_payment(self.owner,f.fixture.import_body(payment))
        source=f.api._cash_source(self.owner,event['id'])
        self.assertEqual(source['undocumented_amount'],'119.00')
        self.assertEqual(source['units'],[])
        self.assertEqual(f.fixture.finance.open_items(self.owner)['items'],[])
        with self.assertRaises(Problem) as error:f.api.preview(self.owner,f.body('cash',f.cash_payload(event)))
        self.assertEqual(error.exception.status,409)


if __name__=='__main__':unittest.main()
