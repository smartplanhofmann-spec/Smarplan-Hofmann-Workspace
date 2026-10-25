"""Verified TLS loopback SMTP and real document-outbox lifecycle tests."""
from email import policy
from email.parser import BytesParser
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import uuid

from core import Problem
from business_delivery import SMTPConfiguration,SMTPTransport,DeliveryReceipt,configuration
from test_documents import DocumentsFixture


class TLSSink:
    def __init__(self,directory,*,drop_after_data=False,slow_reply=False):
        self.directory=Path(directory);self.drop=drop_after_data;self.slow=slow_reply;self.message=None;self.error=None
        cert=self.directory/'test.crt';key=self.directory/'test.key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=localhost',
            '-addext','subjectAltName=DNS:localhost,IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)
        self.context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);self.context.load_cert_chain(cert,key)
        self.client_context=ssl.create_default_context(cafile=str(cert))
        self.listener=socket.socket();self.listener.bind(('127.0.0.1',0));self.listener.listen(1);self.listener.settimeout(5)
        self.port=self.listener.getsockname()[1];self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def run(self):
        try:
            plain,_=self.listener.accept();plain.settimeout(3)
            with self.context.wrap_socket(plain,server_side=True) as connection:
                if self.slow:
                    for b in b'220 slow\r\n':
                        connection.send(bytes([b]));time.sleep(.12)
                    return
                stream=connection.makefile('rb');connection.sendall(b'220 synthetic.local ready\r\n')
                while True:
                    line=stream.readline(8193)
                    if not line:return
                    command=line.split(b' ',1)[0].upper().strip()
                    if command==b'EHLO':connection.sendall(b'250-synthetic.local\r\n250 AUTH PLAIN\r\n')
                    elif command==b'AUTH':connection.sendall(b'235 2.7.0 synthetic authenticated\r\n')
                    elif command in (b'MAIL',b'RCPT'):connection.sendall(b'250 2.1.0 accepted\r\n')
                    elif command==b'DATA':
                        connection.sendall(b'354 continue\r\n');parts=[]
                        while True:
                            part=stream.readline(8193)
                            if not part or part==b'.\r\n':break
                            parts.append(part[1:] if part.startswith(b'..') else part)
                        self.message=b''.join(parts)
                        if self.drop:return
                        connection.sendall(b'250 2.0.0 queued synthetic-receipt-1\r\n')
                    elif command==b'QUIT':connection.sendall(b'221 bye\r\n');return
                    else:connection.sendall(b'500 rejected\r\n')
        except (OSError,ssl.SSLError) as error:self.error=type(error).__name__
        finally:self.listener.close()

    def close(self):
        self.listener.close();self.thread.join(5)
        if self.thread.is_alive():raise AssertionError('Synthetic SMTP sink did not terminate')


class SMTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='smartplan-smtp-');self.addCleanup(self.temp.cleanup)

    def job(self):
        value=b'%PDF-1.4\nsynthetic only'
        return {'operation_id':uuid.uuid4().hex,'recipient':'buyer@example.test','subject':'Synthetischer Beleg','text':'Nur Test, keine Kundenpost',
            'attachments':[{'bytes':value,'filename':'synthetic.pdf','media_type':'application/pdf','sha256':hashlib.sha256(value).hexdigest()}]}

    def transport(self,sink,timeout=3):
        return SMTPTransport(SMTPConfiguration('127.0.0.1',sink.port,'ssl','synthetic-user','synthetic-secret','seller@example.test',timeout),context=sink.client_context)

    def test_real_verified_tls_smtp_preserves_operation_and_attachment_bytes(self):
        sink=TLSSink(self.temp.name);self.addCleanup(sink.close);job=self.job()
        result=self.transport(sink).send(job);self.assertEqual('accepted',result.status);self.assertTrue(result.accepted_by_server);self.assertFalse(result.recipient_delivery_confirmed)
        message=BytesParser(policy=policy.default).parsebytes(sink.message)
        self.assertEqual(job['operation_id'],message['X-Smartplan-Operation']);self.assertEqual(job['attachments'][0]['bytes'],list(message.iter_attachments())[0].get_payload(decode=True))

    def test_lost_post_data_reply_is_unknown_not_safe_retry(self):
        sink=TLSSink(self.temp.name,drop_after_data=True);self.addCleanup(sink.close)
        result=self.transport(sink).send(self.job());self.assertEqual('unknown',result.status);self.assertIsNotNone(sink.message)

    def test_absolute_deadline_bounds_slow_tls_smtp_reply(self):
        sink=TLSSink(self.temp.name,slow_reply=True);self.addCleanup(sink.close);start=time.monotonic()
        result=self.transport(sink,timeout=1).send(self.job());self.assertEqual('failed',result.status);self.assertLess(time.monotonic()-start,2)

    def test_unverified_context_and_disabled_configuration_fail_closed(self):
        with self.assertRaises(Problem):configuration({})
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
        with self.assertRaises(ValueError):SMTPTransport(SMTPConfiguration('localhost',465,'ssl','user','secret','seller@example.test'),context=context)
        self.assertNotIn('secret',repr(SMTPConfiguration('localhost',465,'ssl','user','secret','seller@example.test')))


class DocumentOutboxTests(DocumentsFixture,unittest.TestCase):
    def setUp(self):super().setUp();self.settings();self.document=self.issue(self.draft(kind='invoice'))

    def data(self):
        preview=self.api.email_preview(self.owner,self.document['id'])
        return dict(request_id=uuid.uuid4().hex,revision=self.document['revision'],confirmation=True,preview_sha256=preview['preview_sha256'])

    def test_exact_repeat_never_resends_and_smtp_acceptance_is_not_delivery(self):
        class Sink:
            calls=0
            def send(self,job):self.calls+=1;return DeliveryReceipt('accepted',job['operation_id'],'a'*64,accepted_by_server=True)
        sink=Sink();data=self.data();first=self.api.send_mail(self.owner,self.document['id'],data,transport=sink)
        self.assertEqual('accepted',first['status']);self.assertFalse(first['recipient_delivery_confirmed'])
        self.assertEqual(first,self.api.send_mail(self.owner,self.document['id'],data,transport=sink));self.assertEqual(1,sink.calls)

    def test_unknown_outcome_blocks_different_request_and_no_blind_retry(self):
        class Sink:
            calls=0
            def send(self,job):self.calls+=1;return DeliveryReceipt('unknown',job['operation_id'],error_code='delivery_unconfirmed')
        sink=Sink();data=self.data();first=self.api.send_mail(self.owner,self.document['id'],data,transport=sink)
        self.assertEqual('unknown',first['status']);self.assertEqual(first,self.api.send_mail(self.owner,self.document['id'],data,transport=sink))
        with self.assertRaises(Problem):self.api.send_mail(self.owner,self.document['id'],self.data(),transport=sink)
        self.assertEqual(1,sink.calls)

    def test_revoked_during_io_preserves_receipt_but_does_not_publish_result(self):
        office=self.office;actor=self.owner
        class Sink:
            def send(self,job):
                with office.db:office.db.execute('UPDATE users SET active=0 WHERE id=?',(actor['id'],))
                return DeliveryReceipt('accepted',job['operation_id'],'b'*64,accepted_by_server=True)
        with self.assertRaises(Problem):self.api.send_mail(self.owner,self.document['id'],self.data(),transport=Sink())
        row=office.db.execute("SELECT status FROM business_document_mail_receipts WHERE ordinal=2").fetchone();self.assertEqual('accepted',row['status'])

    def test_restore_gate_changed_during_io_preserves_actual_ack_without_publication(self):
        office=self.office
        class Sink:
            def send(self,job):
                with office.db:office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=1,restore_id=? WHERE singleton=1',(uuid.uuid4().hex,))
                return DeliveryReceipt('accepted',job['operation_id'],'c'*64,accepted_by_server=True)
        with self.assertRaises(Problem) as caught:self.api.send_mail(self.owner,self.document['id'],self.data(),transport=Sink())
        self.assertEqual(409,caught.exception.status)
        self.assertEqual('accepted',office.db.execute('SELECT status FROM business_document_mail_receipts WHERE ordinal=2').fetchone()['status'])

    def test_independent_accepted_proof_remains_authoritative_after_late_unknown(self):
        from datetime import timedelta
        peer=self;before=self.api.clock()
        class Uncertain:
            def send(self,job):
                peer.api.clock=lambda:before+timedelta(minutes=5)
                outbox=peer.office.db.execute('SELECT id FROM business_document_outbox WHERE operation_id=?',(job['operation_id'],)).fetchone()['id']
                peer.api.reconcile_mail(peer.owner,peer.document['id'],dict(request_id=uuid.uuid4().hex,outbox_id=outbox,operation_id=job['operation_id'],outcome='accepted',confirmation=True,proof='Synthetic independent definitive server acceptance'))
                return DeliveryReceipt('unknown',job['operation_id'],error_code='delivery_unconfirmed')
        result=self.api.send_mail(self.owner,self.document['id'],self.data(),transport=Uncertain())
        self.assertEqual('accepted',result['status']);self.assertTrue(result['accepted_by_server']);self.assertFalse(result['recipient_delivery_confirmed'])


if __name__=='__main__':unittest.main()
