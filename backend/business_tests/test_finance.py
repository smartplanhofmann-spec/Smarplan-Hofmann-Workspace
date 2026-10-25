"""Real SQLite finance ledgers with synthetic customers; no actual dispatch."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import base64
import json
import hashlib
import io
import random
import uuid
import unittest

from core import Problem
import business_finance as finance
from test_documents import DocumentsFixture


class FinanceTests(DocumentsFixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        with self.office.db:
            for sql in finance.schema_statements('BLOB')+finance.guard_statements('sqlite'):self.office.db.execute(sql)
        self.moment=datetime(2030,3,1,12,tzinfo=timezone.utc)
        self.finance=finance.Finance(self.office,clock=lambda:self.moment)
        self.settings()

    def fc(self,name,*args,**kwargs):return getattr(self.finance,name)(self.owner,*args,**kwargs)

    def invoice(self):return self.issue(self.draft(kind='invoice'))

    def enable_rules(self):
        rules=finance.default_rules();rules['enabled']=True
        return self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=0,**rules))

    def payment(self,document,amount='50.00',**extra):
        data=dict(request_id=uuid.uuid4().hex,source_id='bank:'+uuid.uuid4().hex,kind='receipt',amount=amount,
            currency='EUR',booking_date='2030-02-28',reference='Synthetic only',allocations=[dict(document_id=document['id'],amount=amount)])
        data.update(extra);return data

    def test_partial_payment_replay_open_balance_and_immutable_ledger(self):
        invoice=self.invoice();data=self.payment(invoice)
        first=self.fc('record_payment',data);self.assertEqual(first,self.fc('record_payment',data))
        item=self.fc('open_items')['items'][0]
        self.assertEqual('50.00',item['paid']);self.assertEqual(str(Decimal(invoice['totals']['gross'])-50),item['open'])
        with self.assertRaises(Exception),self.office.db:self.office.db.execute('DELETE FROM business_payments WHERE id=?',(first['id'],))
        finance.validate_integrity(self.office)

    def test_overpayment_is_unallocated_and_refund_requires_actual_received_funds(self):
        invoice=self.invoice();data=self.payment(invoice,'250.00',allocations=[dict(document_id=invoice['id'],amount='10.00')])
        row=self.fc('record_payment',data);self.assertEqual('240.00',row['unallocated'])
        with self.assertRaises(Problem):self.fc('record_payment',self.payment(invoice,'20.00',kind='refund'))
        self.fc('record_payment',self.payment(invoice,'5.00',kind='refund'))
        self.assertEqual('5.00',self.fc('open_items')['items'][0]['paid'])

    def test_preview_never_advances_stage_or_sends_and_full_payment_invalidates_approval(self):
        invoice=self.invoice();self.enable_rules()
        proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        self.assertEqual(0,self.fc('open_items')['items'][0]['level']);self.assertEqual([],self.fc('outbox')['items'])
        self.fc('record_payment',self.payment(invoice,invoice['totals']['gross']))
        with self.assertRaises(Problem):self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))

    def test_six_stages_manual_approval_unknown_receipt_blocks_and_exact_replay(self):
        self.invoice();self.enable_rules()
        for level in range(1,7):
            proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
            command=dict(request_id=uuid.uuid4().hex,confirmation=True)
            approved=self.fc('approve',proposal['id'],command);self.assertEqual(approved,self.fc('approve',proposal['id'],command))
            self.assertEqual(level,approved['level']);self.assertFalse(approved['sent'])
            base=dict(operation_id=approved['operation_id'])
            self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='sending',adapter='test_sink',**base))
            self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='unknown',**base))
            self.moment+=timedelta(days=8)
            self.assertEqual([],self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'])
            with self.assertRaises(Problem):self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='sending',adapter='test_sink',**base))
            self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='sent',confirmation=True,provider_receipt='synthetic-receipt-'+str(level),**base))
            self.moment+=timedelta(days=8)
        self.assertEqual([],self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'])
        self.assertEqual(6,self.fc('open_items')['items'][0]['level'])
        finance.validate_integrity(self.office)

    def test_public_api_never_starts_synthetic_or_real_delivery(self):
        self.invoice();self.enable_rules();p=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        row=self.fc('approve',p['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
        with self.assertRaises(Problem):finance.dispatch(self.office,self.owner,'/finance/outbox/'+row['outbox_id']+'/reconcile','POST',
            dict(request_id=uuid.uuid4().hex,outcome='sending',adapter='test_sink',operation_id=row['operation_id']))

    def test_exact_three_reminders_three_demands_and_fresh_authorization(self):
        rules=finance.default_rules();rules['levels'][3]['kind']='reminder'
        with self.assertRaises(Problem):self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=0,**rules))
        with self.office.db:self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner['id'],))
        with self.assertRaises(Problem):self.fc('open_items')

    def test_short_two_stage_configuration_and_empty_disabled_are_supported(self):
        rules=finance.default_rules();rules['enabled']=True
        rules['levels']=[rules['levels'][0],{**rules['levels'][3],'level':2}]
        saved=self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=0,**rules));self.assertEqual(2,len(saved['levels']))
        disabled=self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=1,enabled=False,levels=[]));self.assertFalse(disabled['enabled'])
        with self.assertRaises(Problem):self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=2,enabled=True,levels=[]))
        rules=finance.default_rules();rules['levels'].append({**rules['levels'][-1],'level':7})
        with self.assertRaises(Problem):self.fc('save_settings',dict(request_id=uuid.uuid4().hex,revision=2,**rules))

    def test_receipt_original_hash_preserved_no_fake_text_extraction(self):
        original=b'%PDF-1.4\nsynthetic-unparsed-original'
        row=self.fc('capture_receipt',dict(request_id=uuid.uuid4().hex,filename='synthetic.pdf',media_type='application/pdf',original_base64=base64.b64encode(original).decode()))
        self.assertEqual('needs_review',row['status']);self.assertEqual({},row['suggestion'])
        actual=self.office.db.execute('SELECT original FROM business_incoming_receipts WHERE id=?',(row['id'],)).fetchone()
        self.assertEqual(original,bytes(actual['original']));finance.validate_integrity(self.office)

    def test_large_private_chunked_receipt_media_becomes_preserved_financial_original(self):
        from PIL import Image
        from business_operations import BusinessOperations,schema_statements,CHUNK_SIZE
        with self.office.db:
            for sql in schema_statements('BLOB'):self.office.db.execute(sql)
        operations=BusinessOperations(self.office)
        image=Image.frombytes('RGB',(900,900),random.Random(13).randbytes(900*900*3));buffer=io.BytesIO();image.save(buffer,format='PNG');original=buffer.getvalue()
        self.assertGreater(len(original),1024*1024)
        media=operations.new_media(self.owner,self.project,dict(request_id=uuid.uuid4().hex,filename='synthetic-private-receipt.png',media_type='image/png',size=len(original),
            sha256=hashlib.sha256(original).hexdigest(),purpose='receipt',classification='financial'))
        for index in range((len(original)+CHUNK_SIZE-1)//CHUNK_SIZE):operations.put_media_chunk(self.owner,self.project,media['id'],index,original[index*CHUNK_SIZE:(index+1)*CHUNK_SIZE])
        operations.complete_media(self.owner,self.project,media['id'],dict(request_id=uuid.uuid4().hex))
        receipt=self.fc('capture_receipt',dict(request_id=uuid.uuid4().hex,media_id=media['id'],project_id=self.project))
        self.assertEqual(hashlib.sha256(original).hexdigest(),receipt['sha256']);self.assertEqual(original,self.fc('receipt_original',receipt['id'])[0])

    def test_receipt_review_appends_without_changing_original_and_replay_is_exact(self):
        original=b'%PDF-1.4\nsynthetic-original'
        row=self.fc('capture_receipt',dict(request_id=uuid.uuid4().hex,filename='synthetic.pdf',media_type='application/pdf',original_base64=base64.b64encode(original).decode()))
        data=dict(request_id=uuid.uuid4().hex,revision=0,vendor='Synthetic supplier',invoice_number='SYN-001',issue_date='2030-01-10',net='100.00',tax='19.00',gross='119.00',currency='EUR',status='reviewed')
        reviewed=self.fc('review_receipt',row['id'],data);self.assertEqual('reviewed',reviewed['status']);self.assertEqual(reviewed,self.fc('review_receipt',row['id'],data))
        self.assertEqual(original,self.fc('receipt_original',row['id'])[0]);finance.validate_integrity(self.office)

    def test_actual_dunning_delivery_uses_same_approved_job_and_never_replays_network(self):
        from business_delivery import DeliveryReceipt
        self.invoice();self.enable_rules();proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        approval=self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));outbox=self.fc('outbox')['items'][0]
        class Sink:
            calls=0
            def send(self,job):self.calls+=1;return DeliveryReceipt('accepted',job['operation_id'],'f'*64,accepted_by_server=True)
        sink=Sink();data=dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=outbox['payload_sha256'])
        first=self.fc('deliver',approval['outbox_id'],data,transport=sink);self.assertTrue(first['accepted_by_server']);self.assertFalse(first['recipient_delivery_confirmed'])
        self.assertEqual(first,self.fc('deliver',approval['outbox_id'],data,transport=sink));self.assertEqual(1,sink.calls)

    def test_payment_after_approval_prevents_actual_dunning_delivery(self):
        self.invoice();self.enable_rules();proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        approval=self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));outbox=self.fc('outbox')['items'][0]
        invoice=self.call('get',proposal['document_id']);self.fc('record_payment',self.payment(invoice,'1.00'))
        class Sink:
            def send(self,job):raise AssertionError('No network action after payment changes')
        with self.assertRaises(Problem):self.fc('deliver',approval['outbox_id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=outbox['payload_sha256']),transport=Sink())

    def test_op_notes_are_revisioned_replayable_and_sorting_is_decimal(self):
        first=self.invoice();second=self.issue(self.draft(kind='invoice',positions=[dict(description='Synthetic small',quantity='1',unit='C62',unit_price_net='2',tax_rate='19',kind='material')]))
        body=dict(request_id=uuid.uuid4().hex,revision=0,note='Synthetic agreed follow-up')
        value=self.fc('note',first['id'],body);self.assertEqual(value,self.fc('note',first['id'],body))
        items=self.fc('open_items',sort='open')['items'];self.assertEqual([second['id'],first['id']],[i['id'] for i in items]);self.assertEqual(body['note'],items[-1]['note'])

    def test_partial_payment_after_approval_gets_new_version_same_stage_without_mutating_old_pdf(self):
        invoice=self.invoice();self.enable_rules()
        first=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        approval=self.fc('approve',first['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
        old_pdf=self.fc('dunning_pdf',first['id'])
        self.fc('record_payment',self.payment(invoice,'10.00'))
        proposals=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items']
        self.assertEqual(1,len(proposals),'A partial payment must allow a newly reviewed unsent notice')
        replacement=proposals[0];self.assertEqual(1,replacement['level'])
        renewed=self.fc('approve',replacement['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
        self.assertEqual(approval['outbox_id'],renewed['outbox_id']);self.assertEqual(1,renewed['level']);self.assertEqual(2,renewed['edition'])
        self.assertNotEqual(approval['operation_id'],renewed['operation_id'])
        self.assertEqual(old_pdf,self.fc('dunning_pdf',first['id']));self.assertNotEqual(old_pdf,self.fc('dunning_pdf',replacement['id']))
        self.assertEqual(1,self.office.db.execute('SELECT count(*) FROM business_dunning_approvals').fetchone()[0])
        self.assertEqual(1,self.office.db.execute('SELECT count(*) FROM business_finance_outbox').fetchone()[0])
        from business_delivery import DeliveryReceipt
        class Sink:
            calls=0
            def send(self,job):self.calls+=1;return DeliveryReceipt('accepted',job['operation_id'],'a'*64,accepted_by_server=True)
        sink=Sink();active=self.fc('outbox')['items'][0];command=dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=active['payload_sha256'])
        delivered=self.fc('deliver',active['id'],command,transport=sink)
        self.assertEqual(delivered,self.fc('deliver',active['id'],command,transport=sink));self.assertEqual(1,sink.calls)
        self.assertEqual(renewed['operation_id'],delivered['operation_id']);self.assertEqual('sent',delivered['status'])
        finance.validate_integrity(self.office)

    def test_uncertain_previous_delivery_blocks_version_replacement_until_proven_not_sent(self):
        invoice=self.invoice();self.enable_rules();p=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        approved=self.fc('approve',p['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));bound=dict(operation_id=approved['operation_id'])
        self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='sending',adapter='test_sink',**bound))
        self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='unknown',**bound));self.fc('record_payment',self.payment(invoice,'10.00'))
        self.assertEqual([],self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'])
        self.fc('record_delivery',approved['outbox_id'],dict(request_id=uuid.uuid4().hex,outcome='not_sent',confirmation=True,provider_receipt='Synthetic definitive no-delivery proof',**bound))
        self.assertEqual(1,len(self.fc('propose',dict(request_id=uuid.uuid4().hex))['items']))

    def test_late_old_acceptance_is_preserved_and_blocks_new_edition_sending(self):
        from business_delivery import DeliveryReceipt
        invoice=self.invoice();self.enable_rules();p=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        first=self.fc('approve',p['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));original=self.fc('outbox')['items'][0];peer=self
        class LateAcceptance:
            def send(self,job):
                peer.moment+=timedelta(minutes=5)
                peer.fc('record_delivery',first['outbox_id'],dict(request_id=uuid.uuid4().hex,operation_id=job['operation_id'],outcome='not_sent',confirmation=True,provider_receipt='Synthetic stale worker investigation'))
                peer.fc('record_payment',peer.payment(invoice,'10.00'))
                replacement=peer.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
                peer.fc('approve',replacement['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
                return DeliveryReceipt('accepted',job['operation_id'],'b'*64,accepted_by_server=True)
        receipt=self.fc('deliver',first['outbox_id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=original['payload_sha256']),transport=LateAcceptance())
        self.assertTrue(receipt['accepted_by_server']);active=self.fc('outbox')['items'][0]
        self.assertTrue(active['supersession_conflict']);self.assertEqual('unknown',active['stage_state']);self.assertEqual('pending',active['status'])
        class NoSend:
            def send(self,job):raise AssertionError('Late acknowledgement must block the replacement network action')
        with self.assertRaises(Problem):self.fc('deliver',active['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=active['payload_sha256']),transport=NoSend())
        self.fc('record_delivery',active['id'],dict(request_id=uuid.uuid4().hex,operation_id=active['operation_id'],outcome='not_sent',confirmation=True,provider_receipt='Synthetic replacement withdrawn after actual old acceptance'))
        resolved=self.fc('outbox')['items'][0];self.assertFalse(resolved['supersession_conflict']);self.assertEqual('sent',resolved['stage_state']);self.assertEqual('not_sent',resolved['status'])
        self.assertEqual(1,self.office.db.execute("SELECT count(*) FROM business_outbox_receipts WHERE outcome='sent'").fetchone()[0]);finance.validate_integrity(self.office)

    def test_disaster_restore_marks_every_unconfirmed_edition_unknown_idempotently(self):
        invoice=self.invoice();self.enable_rules();p=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        self.fc('approve',p['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));self.fc('record_payment',self.payment(invoice,'10.00'))
        replacement=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0];self.fc('approve',replacement['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
        self.assertEqual({'dunning_mail_unknown':2},finance.sanitize_after_restore(self.office));self.assertEqual({'dunning_mail_unknown':0},finance.sanitize_after_restore(self.office))
        active=self.fc('outbox')['items'][0];self.assertTrue(active['supersession_conflict']);self.assertEqual(['unknown','unknown'],[v['status'] for v in active['editions']]);finance.validate_integrity(self.office)

    def test_accepted_notice_is_not_replaced_by_partial_payment_and_next_interval_starts_at_receipt(self):
        from business_delivery import DeliveryReceipt
        invoice=self.invoice();self.enable_rules();proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        first=self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));outbox=self.fc('outbox')['items'][0]
        self.assertIsNone(self.fc('open_items')['items'][0]['last_reminder'])
        self.moment+=timedelta(days=3)
        class Sink:
            def send(self,job):return DeliveryReceipt('accepted',job['operation_id'],'c'*64,accepted_by_server=True)
        self.fc('deliver',outbox['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=outbox['payload_sha256']),transport=Sink())
        item=self.fc('open_items')['items'][0];self.assertEqual((self.moment.date()+timedelta(days=7)).isoformat(),item['next_due_date'])
        self.fc('record_payment',self.payment(invoice,'10.00'));self.assertEqual([],self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'])
        self.moment+=timedelta(days=8);next_notice=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        self.assertEqual(2,next_notice['level']);self.assertNotIn('supersedes',next_notice)

    def test_late_previous_stage_conflict_blocks_later_stage_until_explicit_receipt_review(self):
        from business_delivery import DeliveryReceipt
        invoice=self.invoice();self.enable_rules();proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        first=self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));original=self.fc('outbox')['items'][0];peer=self
        class Accepted:
            def send(self,job):return DeliveryReceipt('accepted',job['operation_id'],'d'*64,accepted_by_server=True)
        class Late:
            def send(self,job):
                peer.moment+=timedelta(minutes=5)
                peer.fc('record_delivery',first['outbox_id'],dict(request_id=uuid.uuid4().hex,operation_id=job['operation_id'],outcome='not_sent',confirmation=True,provider_receipt='Synthetic stale investigation'))
                peer.fc('record_payment',peer.payment(invoice,'10.00'));proposal=peer.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
                peer.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));current=peer.fc('outbox')['items'][0]
                peer.fc('deliver',current['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=current['payload_sha256']),transport=Accepted())
                peer.moment+=timedelta(days=8);second=peer.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
                peer.fc('approve',second['id'],dict(request_id=uuid.uuid4().hex,confirmation=True))
                return DeliveryReceipt('accepted',job['operation_id'],'e'*64,accepted_by_server=True)
        self.fc('deliver',original['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=original['payload_sha256']),transport=Late())
        rows=self.fc('outbox')['items'];later=next(r for r in rows if r['level']==2);old=next(r for r in rows if r['level']==1)
        self.assertTrue(later['blocked_by_previous_conflict'])
        with self.assertRaises(Problem):self.fc('deliver',later['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=later['payload_sha256']),transport=Accepted())
        self.fc('record_delivery',old['id'],dict(request_id=uuid.uuid4().hex,operation_id=old['operation_id'],outcome='sent',confirmation=True,provider_receipt='Synthetic duplicated notices reviewed against external logs',acknowledge_conflict=True))
        self.assertFalse(self.fc('open_items')['items'][0]['supersession_conflict']);finance.validate_integrity(self.office)

    def test_known_accepted_proof_is_not_undone_by_later_transport_uncertainty(self):
        from business_delivery import DeliveryReceipt
        self.invoice();self.enable_rules();proposal=self.fc('propose',dict(request_id=uuid.uuid4().hex))['items'][0]
        approved=self.fc('approve',proposal['id'],dict(request_id=uuid.uuid4().hex,confirmation=True));outbox=self.fc('outbox')['items'][0];peer=self
        class UncertainTransport:
            def send(self,job):
                peer.moment+=timedelta(minutes=5)
                peer.fc('record_delivery',outbox['id'],dict(request_id=uuid.uuid4().hex,operation_id=job['operation_id'],outcome='sent',confirmation=True,provider_receipt='Synthetic real acceptance independently confirmed in SMTP logs'))
                return DeliveryReceipt('unknown',job['operation_id'],error_code='delivery_unconfirmed')
        self.fc('deliver',outbox['id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=outbox['payload_sha256']),transport=UncertainTransport())
        self.assertEqual('sent',self.fc('outbox')['items'][0]['status'])
        self.assertEqual(1,self.office.db.execute("SELECT count(*) FROM business_outbox_receipts WHERE outcome='sent'").fetchone()[0])


if __name__=='__main__':unittest.main()
