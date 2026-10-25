"""Disaster snapshots never turn uncertain SMTP delivery into a safe retry."""
from datetime import datetime,timezone
import unittest
import uuid

import business_documents as documents
import business_finance as finance
from business_delivery import DeliveryReceipt
from test_documents import DocumentsFixture


class OutboxRestoreTests(DocumentsFixture,unittest.TestCase):
    def setUp(self):super().setUp();self.settings()

    def intent(self):
        invoice=self.issue(self.draft(kind='invoice'));preview=self.api.email_preview(self.owner,invoice['id'])
        data=dict(request_id=uuid.uuid4().hex,revision=invoice['revision'],confirmation=True,preview_sha256=preview['preview_sha256'])
        return invoice,data,self.api.prepare_mail(self.owner,invoice['id'],data)

    def test_document_pending_becomes_unknown_once_while_accepted_and_archives_are_preserved(self):
        pending,body,pending_state=self.intent();sent,sent_body,_=self.intent()
        class Sink:
            def send(self,job):return DeliveryReceipt('accepted',job['operation_id'],'e'*64,accepted_by_server=True)
        accepted=self.api.send_mail(self.owner,sent['id'],sent_body,transport=Sink())
        original=self.api.archive(self.owner,pending['id']);numbers=self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0]
        self.assertEqual({'document_mail_unknown':1},documents.sanitize_after_restore(self.office))
        self.assertEqual('unknown',self.api._mail_state(pending_state['outbox_id'])['status'])
        self.assertEqual('accepted',self.api._mail_state(accepted['outbox_id'])['status'])
        self.assertEqual({'document_mail_unknown':0},documents.sanitize_after_restore(self.office))
        self.assertEqual(original,self.api.archive(self.owner,pending['id']));self.assertEqual(numbers,self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0])
        documents.validate_integrity(self.office)

    def test_dunning_pending_becomes_unknown_without_stage_repeat_or_loss_of_sent_receipt(self):
        api=finance.Finance(self.office,clock=lambda:datetime(2030,3,1,12,tzinfo=timezone.utc))
        self.issue(self.draft(kind='invoice'));self.issue(self.draft(kind='invoice'))
        rules=finance.default_rules();rules['enabled']=True;api.save_settings(self.owner,dict(request_id=uuid.uuid4().hex,revision=0,**rules))
        proposals=api.propose(self.owner,dict(request_id=uuid.uuid4().hex))['items']
        approvals=[api.approve(self.owner,p['id'],dict(request_id=uuid.uuid4().hex,confirmation=True)) for p in proposals]
        outboxes={r['id']:r for r in api.outbox(self.owner)['items']}
        class Sink:
            def send(self,job):return DeliveryReceipt('accepted',job['operation_id'],'f'*64,accepted_by_server=True)
        sent=approvals[1];api.deliver(self.owner,sent['outbox_id'],dict(request_id=uuid.uuid4().hex,confirmation=True,payload_sha256=outboxes[sent['outbox_id']]['payload_sha256']),transport=Sink())
        self.assertEqual({'dunning_mail_unknown':1},finance.sanitize_after_restore(self.office))
        self.assertEqual('unknown',api._outcome(approvals[0]['outbox_id']));self.assertEqual('sent',api._outcome(sent['outbox_id']))
        self.assertEqual({'dunning_mail_unknown':0},finance.sanitize_after_restore(self.office));self.assertEqual(2,self.office.db.execute('SELECT count(*) FROM business_dunning_approvals').fetchone()[0])
        finance.validate_integrity(self.office)


if __name__=='__main__':unittest.main()
