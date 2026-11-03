"""Independent supplier-return regressions with disposable SQLite evidence.

No PostgreSQL reset, provider request or real stock/financial change is made.
"""
from decimal import Decimal
import base64
import json
import unittest

import business_schema
from core import canonical,Problem
from business_purchase_changes import mixed_stock_events,sha
import test_business_purchase_changes as fixtures


class PurchaseChangesIndependentReview(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PurchaseChangesTests('runTest')
        self.f.setUp();self.addCleanup(self.f.doCleanups)

    def duplicate_order(self):
        f=self.f
        f.order=f.make_order(items=[dict(article_id=f.article['id'],quantity='10'),
                                   dict(article_id=f.article['id'],quantity='10')])
        f.confirm_body=f.confirmation()
        f.confirmed=f.api.confirm(f.owner,f.order['id'],f.confirm_body)
        f.evidence=f.upload()

    def financial_rows(self):
        db=self.f.office.db
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'business_accounting_%' OR name LIKE 'business_finance_%' OR name LIKE 'business_bank_%')")]
        return {table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in tables}

    def test_same_article_lines_share_reservations_and_original_receipts_survive_revaluation(self):
        f=self.f;self.duplicate_order()
        receipt_body=f.receipt(lines=[dict(line_index=0,quantity='5',unit_cost_net='2'),
                                     dict(line_index=1,quantity='5',unit_cost_net='4')])
        received=f.api.receive(f.owner,f.order['id'],receipt_body)
        f.inventory.reserve(f.owner,f.project,f.req(article_id=f.article['id'],location_id=f.location['id'],quantity='4'))
        def lines(amount):
            return [dict(receipt_id=received['id'],line_index=index,quantity=amount) for index in (1,0)]
        # Each line fits alone, but their aggregate exceeds the six free units.
        f.error(409,f.changes.preview,f.owner,f.order['id'],'supplier-returns',f.returning(received,'4',lines=lines('4')))
        self.assertEqual(f.balance()['on_hand'],'10.0000')
        financial=self.financial_rows()
        result,body=f.apply('supplier-returns',f.returning(received,'3',lines=lines('3')))
        self.assertEqual(result['record']['total_book_value_net'],'18.0000')
        self.assertEqual([r['line_index'] for r in result['record']['lines']],[0,1])
        self.assertEqual((f.balance()['on_hand'],f.balance()['available']),('4.0000','0.0000'))
        # A later genuine delivery changes the moving average, not old returns.
        f.receive(expected_receipt_revision=1,receipt_reference='REVIEW-LATER',
            lines=[dict(line_index=0,quantity='1',unit_cost_net='9'),dict(line_index=1,quantity='1',unit_cost_net='9')])
        self.assertEqual(f.inventory._stock(f.location['id'],f.article['id'])[:2],(Decimal(6),Decimal(30)))
        self.assertEqual(f.changes.confirm(f.owner,f.order['id'],'supplier-returns',body),result)
        self.assertEqual(f.api.receive(f.owner,f.order['id'],receipt_body),received)
        self.assertEqual(f.api.confirm(f.owner,f.order['id'],f.confirm_body),f.confirmed)
        self.assertEqual(self.financial_rows(),financial)
        self.assertEqual(f.inventory.cost_report(f.owner,f.project)['material_actual_net'],'0.00')
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_equal_article_does_not_merge_original_position_capacity(self):
        f=self.f;self.duplicate_order()
        received=f.receive(lines=[dict(line_index=0,quantity='3',unit_cost_net='2'),
                                  dict(line_index=1,quantity='7',unit_cost_net='4')])
        f.error(409,f.changes.preview,f.owner,f.order['id'],'supplier-returns',f.returning(received,'4'))
        f.apply('supplier-returns',f.returning(received,'3'))
        # Anonymous stock of the same article cannot replenish a returned lot.
        f.inventory.move(f.owner,f.req(kind='receive',article_id=f.article['id'],to_location_id=f.location['id'],quantity='5',unit_cost_net='8'))
        f.error(409,f.changes.preview,f.owner,f.order['id'],'supplier-returns',f.returning(received,'1'))
        accepted,_=f.apply('supplier-returns',f.returning(received,'7',lines=[dict(receipt_id=received['id'],line_index=1,quantity='7')]))
        self.assertEqual(accepted['order']['items'][0]['returned_quantity'],'3.0000')
        self.assertEqual(accepted['order']['items'][1]['returned_quantity'],'7.0000')
        self.assertEqual(f.balance()['on_hand'],'5.0000')
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_restore_rejects_rehashed_historical_order_receipt_disagreeing_with_sources(self):
        f=self.f
        received=f.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        _,body=f.apply('supplier-returns',f.returning(received,'2'))
        self.assertTrue(business_schema.validate_integrity(f.office))
        with f.office.db:
            # Model a damaged backup after immutable guards are bypassed by an
            # operator. A fresh checksum alone is not an independent source.
            f.office.db.execute('DROP TRIGGER business_purchase_change_requests_update_guard')
            row=f.office.db.execute('SELECT result_json FROM business_purchase_change_requests WHERE user_id=? AND request_id=?',(f.owner['id'],body['request_id'])).fetchone()
            altered=json.loads(row['result_json'])
            altered['order']['items'][0]['received_quantity']='999.0000'
            f.office.db.execute('UPDATE business_purchase_change_requests SET result_json=?,result_sha256=? WHERE user_id=? AND request_id=?',
                (canonical(altered),sha(altered),f.owner['id'],body['request_id']))
        with self.subTest(path='restore'):
            with self.assertRaises(ValueError):
                business_schema.validate_integrity(f.office)
        with self.subTest(path='accepted_replay'):
            f.error(500,f.changes.confirm,f.owner,f.order['id'],'supplier-returns',body)

    def test_count_return_and_transfer_preserve_location_capacity_and_project_costs(self):
        f=self.f
        receipt=f.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        financial=self.financial_rows()
        other=f.inventory.save_location(f.owner,f.req(name='Independent return review second stock'))
        f.count('8')
        f.apply('supplier-returns',f.returning(receipt,'1'))
        f.inventory.move(f.owner,f.req(kind='transfer',article_id=f.article['id'],
            from_location_id=f.location['id'],to_location_id=other['id'],quantity='4'))
        # Company stock is seven, but only three units remain at the receipt's store.
        f.error(409,f.changes.preview,f.owner,f.order['id'],'supplier-returns',f.returning(receipt,'4'))
        f.count('4')
        f.apply('supplier-returns',f.returning(receipt,'2'))
        f.inventory.move(f.owner,f.req(kind='transfer',article_id=f.article['id'],
            from_location_id=other['id'],to_location_id=f.location['id'],quantity='1'))
        issued=f.inventory.move(f.owner,f.req(kind='issue',article_id=f.article['id'],
            from_location_id=f.location['id'],project_id=f.project,quantity='2'))
        self.assertEqual(issued['cost_net'],'4.0000')
        f.apply('supplier-returns',f.returning(receipt,'1'))
        self.assertEqual([kind for kind,_ in mixed_stock_events(f.office)],
            ['movement','count','supplier_return','movement','count','supplier_return',
             'movement','movement','supplier_return'])
        self.assertEqual(f.inventory._stock(f.location['id'],f.article['id'])[:2],(Decimal(0),Decimal(0)))
        self.assertEqual(f.inventory._stock(other['id'],f.article['id'])[:2],(Decimal(3),Decimal(6)))
        self.assertEqual(f.inventory.cost_report(f.owner,f.project)['material_actual_net'],'4.00')
        self.assertEqual(self.financial_rows(),financial)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_restore_rejects_impossible_unconfirmed_original_command_even_with_new_hash(self):
        f=self.f
        received=f.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        _,body=f.apply('supplier-returns',f.returning(received,'2'))
        with f.office.db:
            f.office.db.execute('DROP TRIGGER business_purchase_change_requests_update_guard')
            row=f.office.db.execute('SELECT operation,request_json FROM business_purchase_change_requests WHERE user_id=? AND request_id=?',
                (f.owner['id'],body['request_id'])).fetchone()
            altered=json.loads(row['request_json']);altered['confirmation']=False
            f.office.db.execute('UPDATE business_purchase_change_requests SET request_json=?,request_hash=? WHERE user_id=? AND request_id=?',
                (canonical(altered),sha([row['operation'],altered]),f.owner['id'],body['request_id']))
        with self.subTest(path='restore'):
            with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)
        with self.subTest(path='accepted_replay'):
            f.error(500,f.changes.confirm,f.owner,f.order['id'],'supplier-returns',altered)

    def test_original_normalized_input_keeps_exact_command_and_historical_replay(self):
        f=self.f
        receipt=f.receive(lines=[dict(line_index=0,quantity='6',unit_cost_net='2')])
        result,body=f.apply('supplier-returns',f.returning(receipt,'02.0000',
            reference='  return review  ',reason='  Actual physical return  '))
        self.assertEqual(result['record']['reference'],'return review')
        self.assertEqual(result['record']['reason'],'Actual physical return')
        self.assertEqual(result['record']['lines'][0]['quantity'],'2.0000')
        row=f.office.db.execute('SELECT request_json FROM business_purchase_change_requests WHERE user_id=? AND request_id=?',
            (f.owner['id'],body['request_id'])).fetchone()
        self.assertEqual(json.loads(row['request_json']),body)
        f.count('5')
        self.assertEqual(f.changes.confirm(f.owner,f.order['id'],'supplier-returns',body),result)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_noncanonical_base64_is_rejected_or_produces_a_valid_replayable_original(self):
        f=self.f;raw=b'%PDF-1.7\nx'
        encoded=base64.b64encode(raw).decode()
        alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        # Non-zero unused padding bits decode to the identical original bytes.
        altered=encoded[:-3]+alphabet[alphabet.index(encoded[-3])^1]+encoded[-2:]
        self.assertNotEqual(encoded,altered)
        self.assertEqual(base64.b64decode(altered,validate=True),raw)
        body=f.req(filename='review-padding.pdf',media_type='application/pdf',content_base64=altered)
        before=f.office.db.execute('SELECT COUNT(*) FROM business_purchase_change_evidence').fetchone()[0]
        try:result=f.changes.upload(f.owner,f.order['id'],body)
        except Problem as error:
            self.assertEqual(error.status,400)
            self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_purchase_change_evidence').fetchone()[0],before)
        else:
            self.assertEqual(bytes(f.changes.file(f.order['id'],result['id'])['content']),raw)
            self.assertEqual(f.changes.upload(f.owner,f.order['id'],body),result)
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
