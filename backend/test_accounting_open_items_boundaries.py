"""Actual competing consumers, old tax timing, and append-only failure boundaries."""
import sqlite3
import unittest
from unittest.mock import patch
import uuid
from core import Problem
from business_accounting_open_items import TABLES
import test_business_accounting_open_items as fixture

class OpeningItemBoundaries(unittest.TestCase):
    def setUp(self):
        self.f=fixture.OpeningItemWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_old_declared_month_does_not_fake_prior_exercise_of_input_vat(self):
        f=self.f;payload=f.item('late-vat','payable');payload['prior_input_vat']['deducted_on']='2026-01-01'
        f.reject(409,f.api.preview,f.owner,f.body('item','late-vat',payload))
        payload['prior_input_vat']['deducted_on']='2025-11-10'
        f.reject(409,f.api.preview,f.owner,f.body('item','late-vat',payload))

    def test_same_actual_cash_reference_reserved_in_both_existing_and_opening_directions(self):
        f=self.f;ordinary=f.euer.fixture.payment();body=f.euer.fixture.import_body(ordinary);body['evidence_reference']='SYN shared original transfer'
        f.euer.fixture.api.import_payment(f.owner,body)
        item,_=f.save('item','legacy-a',f.item());f.reject(409,f.payment,item,reference='ＳＹＮ shared original transfer')
        actual,_=f.payment(item,reference='SYN second actual transfer')
        ordinary=f.euer.fixture.payment();body=f.euer.fixture.import_body(ordinary);body['evidence_reference']='syn SECOND actual TRANSFER'
        f.reject(409,f.euer.fixture.api.import_payment,f.owner,body)
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0],1)

    def test_two_real_stale_previews_never_overconsume_same_original_remainder(self):
        f=self.f;item,_=f.save('item','legacy-a',f.item(prior=True));commands=[]
        for _ in range(2):
            key=uuid.uuid4().hex;payload=dict(status='active',item_key=item['entity_key'],item_id=item['id'],item_hash=item['content_hash'],date='2026-02-15',amount='79.33',account_id=f.f.account['id'],account_revision=1,evidence_reference='Actual concurrent source '+key,proof=f.original('legacy-a','actual concurrent payment '+key))
            body=f.body('payment',key,payload);preview=f.api.preview(f.owner,body);commands.append(dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        f.api.confirm(f.owner,commands[0]);error=f.reject(409,f.api.confirm,f.owner,commands[1])
        self.assertEqual(error.request_resolution,'not_accepted')
        f.reject(409,f.api.preview,f.owner,f.body('payment',commands[1]['entity_key'],commands[1]['payload']))
        self.assertEqual(f.api.state(f.owner)['items'][0]['remaining'],'0.00')

    def test_late_payment_failure_keeps_no_cash_or_acceptance_and_all_tables_are_immutable(self):
        f=self.f;item,_=f.save('item','legacy-a',f.item());before=f.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0]
        proof=f.original('legacy-a','actual payment failure')
        with patch.object(f.office,'audit',side_effect=RuntimeError('Synthetic failure after payment insert')):
            with self.assertRaises(RuntimeError):f.payment(item,proof=proof)
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],before)
        self.assertEqual(f.euer.api.report(f.owner,2026)['cash_movements'],[])
        for table in TABLES:
            with self.subTest(table=table),self.assertRaises(sqlite3.IntegrityError):f.office.db.execute('DELETE FROM '+table)

    def test_one_item_cannot_use_another_trade_original_as_actual_cash_proof(self):
        f=self.f;first,_=f.save('item','legacy-a',f.item());second,_=f.save('item','legacy-b',f.item('legacy-b'))
        raw=f.api._original(second['payload']['invoice_proof']['original_id'])[1]
        import base64
        original=f.api.upload_original(f.owner,dict(request_id=uuid.uuid4().hex,entity_key='legacy-a',filename='wrong-payment.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
        f.reject(409,f.payment,first,proof=dict(original_id=original['id'],sha256=original['sha256']))

if __name__=='__main__':unittest.main()
