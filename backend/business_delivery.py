"""Explicit, TLS-verified SMTP delivery; credentials exclusively from ENV.

This module has no tables or registry hook. Callers own authorized preparation,
an immutable operation ID, an outbox and a later short result transaction.
SMTP acceptance is not evidence of reading or recipient delivery.
"""
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formatdate
import hashlib
import base64
import json
import os
import re
import smtplib
import socket
import ssl
import signal
import subprocess
import sys
import time

from core import Problem

MAX_MAIL=24*1024*1024


@dataclass(frozen=True,repr=False)
class SMTPConfiguration:
    host:str
    port:int
    mode:str
    username:str
    password:str
    sender:str
    timeout:float=30

    def __repr__(self):return 'SMTPConfiguration(<protected>)'


@dataclass(frozen=True)
class DeliveryReceipt:
    status:str
    operation_id:str
    receipt_id:str|None=None
    error_code:str|None=None
    accepted_by_server:bool=False
    recipient_delivery_confirmed:bool=False


def _address(value):
    if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+\-/=?^_`{|}~]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}',value):raise Problem(400,'Einzelne gültige E-Mail-Adresse erwartet')
    return value


def configuration(environ=None):
    env=os.environ if environ is None else environ
    if env.get('SMARTPLAN_SMTP_ENABLED')!='1':raise Problem(409,'E-Mail-Versand ist noch nicht ausdrücklich eingerichtet')
    host=env.get('SMARTPLAN_SMTP_HOST','');mode=env.get('SMARTPLAN_SMTP_MODE','ssl')
    if not isinstance(host,str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?',host) or mode not in ('ssl','starttls'):raise Problem(409,'Geschützte SMTP-Konfiguration ist unvollständig')
    username=env.get('SMARTPLAN_SMTP_USERNAME','');password=env.get('SMARTPLAN_SMTP_PASSWORD','')
    if not username or not password or len(username)>300 or len(password)>1000 or any(c in username+password for c in '\r\n\x00'):raise Problem(409,'Geschützte SMTP-Anmeldung fehlt')
    sender=env.get('SMARTPLAN_SMTP_FROM','')
    try:_address(sender)
    except Problem:raise Problem(409,'SMTP-Absender ist nicht eingerichtet') from None
    return SMTPConfiguration(host,465 if mode=='ssl' else 587,mode,username,password,sender)


class _Deadline:
    def _remaining(self):
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('SMTP deadline')
        return remaining

    def send(self,value):
        if self.sock:self.sock.settimeout(self._remaining())
        return super().send(value)

    def getreply(self):
        # smtplib's buffered readline can be kept alive by a slow peer. Read
        # each bounded reply with the same absolute operation deadline instead.
        lines=[];code=-1;total=0
        while True:
            line=bytearray()
            while len(line)<=8192:
                self.sock.settimeout(self._remaining());part=self.sock.recv(1)
                if not part:raise smtplib.SMTPServerDisconnected('SMTP reply missing')
                line+=part
                if part==b'\n':break
            total+=len(line)
            if len(line)>8192 or total>65536 or len(lines)>100:raise smtplib.SMTPResponseException(500,b'Bounded reply exceeded')
            if len(line)<4 or not bytes(line[:3]).isdigit():raise smtplib.SMTPResponseException(500,b'Malformed reply')
            current=int(line[:3])
            if code!=-1 and current!=code:raise smtplib.SMTPResponseException(500,b'Inconsistent reply')
            code=current;lines.append(bytes(line[4:]).strip())
            if line[3:4]!=b'-':break
        return code,b'\n'.join(lines)


class _SMTP(_Deadline,smtplib.SMTP):
    def __init__(self,*args,deadline,**kwargs):self.deadline=deadline;super().__init__(*args,**kwargs)


class _SMTPSSL(_Deadline,smtplib.SMTP_SSL):
    def __init__(self,*args,deadline,**kwargs):self.deadline=deadline;super().__init__(*args,**kwargs)


class SMTPTransport:
    def __init__(self,config=None,*,context=None):
        self.config=config or configuration();self.context=context or ssl.create_default_context()
        if self.context.verify_mode!=ssl.CERT_REQUIRED or not self.context.check_hostname:raise ValueError('Verified SMTP TLS is mandatory')
        if self.config.mode not in ('ssl','starttls') or not 1<=self.config.timeout<=60:raise ValueError('Bounded verified SMTP configuration required')

    def send(self,job):
        operation=job.get('operation_id')
        if not isinstance(operation,str) or not re.fullmatch(r'[a-f0-9]{32}',operation):raise Problem(400,'Stabile Versandkennung erwartet')
        sender=_address(self.config.sender);recipient=_address(job.get('recipient'));subject=job.get('subject');text=job.get('text')
        if job.get('expected_sender') and job['expected_sender']!=sender:raise Problem(409,'Freigegebener SMTP-Absender wurde geändert')
        if not isinstance(subject,str) or not 1<=len(subject)<=300 or any(c in subject for c in '\r\n\x00') or not isinstance(text,str) or len(text)>20000 or '\x00' in text:raise Problem(400,'Begrenzter E-Mail-Inhalt erwartet')
        files=job.get('attachments',[])
        if not isinstance(files,list) or len(files)>3:raise Problem(400,'Begrenzte Beleganhänge erwartet')
        message=EmailMessage(policy=SMTP);message['From']=sender;message['To']=recipient;message['Subject']=subject
        message['Date']=formatdate(localtime=False,usegmt=True);message['Message-ID']='<smartplan-'+operation+'@'+sender.rsplit('@',1)[1]+'>'
        message['X-Smartplan-Operation']=operation;message.set_content(text,cte='quoted-printable')
        total=0
        for attachment in files:
            if not isinstance(attachment,dict):raise Problem(400,'Beleganhang erwartet')
            value=attachment.get('bytes');filename=attachment.get('filename');mime=attachment.get('media_type')
            if not isinstance(value,bytes) or not 1<=len(value)<=20*1024*1024 or hashlib.sha256(value).hexdigest()!=attachment.get('sha256'):raise Problem(409,'Anhang-Prüfsumme stimmt nicht')
            if mime not in ('application/pdf','application/xml') or not isinstance(filename,str) or not 1<=len(filename)<=200 or any(c in filename for c in '\r\n\x00/\\'):raise Problem(400,'Sicherer Belegdateiname erwartet')
            total+=len(value)
            if total>20*1024*1024:raise Problem(413,'Beleganhänge sind zu groß')
            main,sub=mime.split('/');message.add_attachment(value,maintype=main,subtype=sub,filename=filename)
        encoded=message.as_bytes()
        if len(encoded)>MAX_MAIL:raise Problem(413,'E-Mail überschreitet das Größenlimit')
        deadline=time.monotonic()+self.config.timeout;client=None;entered_data=False
        try:
            cls=_SMTPSSL if self.config.mode=='ssl' else _SMTP
            kwargs={'timeout':self.config.timeout,'deadline':deadline,'local_hostname':'smartplan.local'}
            if self.config.mode=='ssl':kwargs['context']=self.context
            client=cls(**kwargs);client._host=self.config.host
            code,_=client.connect(self.config.host,self.config.port)
            if code!=220:raise smtplib.SMTPConnectError(code,b'Unavailable')
            client.ehlo()
            if self.config.mode=='starttls':client.starttls(context=self.context);client.ehlo()
            client.login(self.config.username,self.config.password)
            code,_=client.mail(sender)
            if code!=250:raise smtplib.SMTPSenderRefused(code,b'Rejected',sender)
            code,_=client.rcpt(recipient)
            if code not in (250,251):raise smtplib.SMTPRecipientsRefused({recipient:(code,b'Rejected')})
            # Once DATA is entered a lost reply is ambiguous. Never infer that
            # the mail was not accepted and never replay the network action.
            entered_data=True;code,reply=client.data(encoded)
            if code!=250:return DeliveryReceipt('failed',operation,error_code='smtp_rejected')
            receipt=hashlib.sha256(reply).hexdigest()
            return DeliveryReceipt('accepted',operation,receipt_id=receipt,accepted_by_server=True)
        except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError):
            return DeliveryReceipt('failed',operation,error_code='smtp_rejected')
        except (OSError,smtplib.SMTPException,ssl.SSLError):
            return DeliveryReceipt('unknown' if entered_data else 'failed',operation,error_code='delivery_unconfirmed' if entered_data else 'smtp_unavailable')
        finally:
            if client is not None:
                # No QUIT roundtrip after an accepted/ambiguous DATA result.
                client.close()


class _ProcessSMTPTransport:
    """A controller deadline also bounds resolver/TLS/runtime stalls."""
    def __init__(self):configuration()

    def send(self,job):
        operation=job.get('operation_id');payload={**job,'attachments':[
            {**{k:v for k,v in item.items() if k!='bytes'},'base64':base64.b64encode(item['bytes']).decode('ascii')}
            for item in job.get('attachments',[])]}
        encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(encoded)>32*1024*1024:raise Problem(413,'E-Mail-Artefakte sind zu groß')
        env={'PATH':os.defpath,'PYTHONPATH':os.path.dirname(os.path.abspath(__file__)),'LANG':'C.UTF-8'}
        if os.name=='nt':
            for name in ('SYSTEMROOT','SystemRoot','WINDIR','TEMP','TMP'):
                if name in os.environ:env[name]=os.environ[name]
        for name,value in os.environ.items():
            if name.startswith('SMARTPLAN_SMTP_'):env[name]=value
        worker=subprocess.Popen([sys.executable,'-m','business_delivery','--worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,env=env,close_fds=True,start_new_session=os.name!='nt')
        try:output,_=worker.communicate(encoded,timeout=40)
        except subprocess.TimeoutExpired:
            if os.name=='nt':worker.kill()
            else:os.killpg(worker.pid,signal.SIGKILL)
            worker.communicate();return DeliveryReceipt('unknown',operation,error_code='delivery_unconfirmed')
        if worker.returncode!=0 or len(output)>2000:return DeliveryReceipt('unknown',operation,error_code='delivery_unconfirmed')
        try:
            result=json.loads(output)
            if result.get('operation_id')!=operation or result.get('status') not in ('accepted','failed','unknown'):raise ValueError()
            receipt=result.get('receipt_id')
            if receipt is not None and not re.fullmatch('[a-f0-9]{64}',receipt):raise ValueError()
            return DeliveryReceipt(result['status'],operation,receipt,result.get('error_code'),result['status']=='accepted')
        except (ValueError,TypeError,AttributeError):return DeliveryReceipt('unknown',operation,error_code='delivery_unconfirmed')


def configured_transport():return _ProcessSMTPTransport()


def _worker():
    from dataclasses import asdict
    raw=sys.stdin.buffer.read(32*1024*1024+1)
    if len(raw)>32*1024*1024:return 1
    try:
        job=json.loads(raw)
        for attachment in job.get('attachments',[]):attachment['bytes']=base64.b64decode(attachment.pop('base64'),validate=True)
        result=SMTPTransport().send(job)
        print(json.dumps(asdict(result),separators=(',',':')))
        return 0
    except Exception:return 1


if __name__=='__main__':raise SystemExit(_worker() if sys.argv[1:]==['--worker'] else 2)
