"""Explicit short dictation, without durable audio or transcript storage.

Speech is text input only. It neither executes assistant actions nor authorizes
them. A committed metadata claim precedes the single provider attempt; lost
responses are inspected through metadata and are never automatically retried.
"""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import sqlite3
import ssl
import struct
import time
from urllib.parse import urlsplit, unquote
import uuid

from core import Problem, canonical, now_iso
from business_assistant import Assistant
from business_assistant_provider import _PinnedHTTPS, decode
from business_foundation import _fresh
from business_operations import identifier, transaction

FEATURES = ('assistant_speech',)
MAX_AUDIO_BYTES = 1920044
LIMITS = dict(max_seconds=60,max_audio_bytes=MAX_AUDIO_BYTES,sample_rate=16000,channels=1,bits_per_sample=16)
TABLES = ('business_assistant_speech_requests','business_assistant_speech_outcomes')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'): raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_assistant_speech_requests(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        project_id TEXT NOT NULL REFERENCES projects(id), context_id TEXT NOT NULL REFERENCES business_assistant_contexts(id),
        instance_id TEXT NOT NULL, context_sha256 TEXT NOT NULL, audio_sha256 TEXT NOT NULL,
        audio_bytes INTEGER NOT NULL CHECK(audio_bytes>44 AND audio_bytes<=1920044),
        sample_count INTEGER NOT NULL CHECK(sample_count>0 AND sample_count<=960000),
        provider_json TEXT NOT NULL, provider_sha256 TEXT NOT NULL, request_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_assistant_speech_outcomes(
        request_id TEXT PRIMARY KEY REFERENCES business_assistant_speech_requests(id),
        status TEXT NOT NULL CHECK(status IN ('completed','failed','interrupted')),
        error_code TEXT NOT NULL CHECK(error_code IN ('','provider_unconfirmed','access_or_context_changed','interrupted_by_restore')),
        provider_attempted INTEGER NOT NULL CHECK(provider_attempted IN (0,1)),
        created_at TEXT NOT NULL)''',
    ]


def protected_tables(): return TABLES
def runtime_privileges(): return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        result=[f'CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} '
            "BEGIN SELECT RAISE(ABORT,'immutable speech metadata'); END" for table in TABLES for action in ('UPDATE','DELETE')]
        for table, key in zip(TABLES,('id','request_id')):
            result.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}=NEW.{key}) '
                "BEGIN SELECT RAISE(ABORT,'immutable speech metadata'); END")
        return result
    if dialect!='postgresql': raise ValueError('Unsupported dialect')
    result=["""CREATE OR REPLACE FUNCTION business_speech_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable speech metadata'; END; $$"""]
    for table in TABLES:
        name=table+'_immutable_guard'
        result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
            f'THEN CREATE TRIGGER {name} BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION '
            'business_speech_immutable(); END IF; END $$')
    return result


def _sha(value):
    return hashlib.sha256(value if isinstance(value,bytes) else canonical(value).encode()).hexdigest()


def _endpoint(value):
    try:
        endpoint=urlsplit(value)
        if (endpoint.scheme!='https' or endpoint.port not in (None,443) or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment
                or endpoint.path!='/v1/audio/transcriptions' or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?',endpoint.hostname or '')):
            raise ValueError('Invalid endpoint')
        return endpoint
    except (TypeError,ValueError):
        raise Problem(409,'Geschützter Sprach-Endpunkt ist nicht vollständig eingerichtet.') from None


@dataclass(frozen=True,repr=False)
class SpeechConfiguration:
    instance_id:str
    endpoint:str
    model:str
    api_key:str
    def __repr__(self): return 'SpeechConfiguration(<protected>)'
    def public(self):
        return dict(adapter='openai_compatible_transcription',instance_id=self.instance_id,endpoint=self.endpoint,model=self.model)


def configuration(office,environ=None):
    env=os.environ if environ is None else environ
    prefix='SMARTPLAN_ASSISTANT_SPEECH_'
    if env.get(prefix+'ENABLED')!='1' or env.get(prefix+'DATA_TRANSFER_APPROVED')!='1':
        raise Problem(409,'Sprachanbieter und Datenweitergabe sind für diese Unternehmensinstanz nicht freigegeben.')
    instance=office.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
    if instance is None or env.get(prefix+'INSTANCE_ID')!=instance['instance_id']:
        raise Problem(409,'Sprachkonfiguration ist nicht an diese Unternehmensinstanz gebunden.')
    endpoint,model,key=(env.get(prefix+field,'') for field in ('ENDPOINT','MODEL','API_KEY'))
    _endpoint(endpoint)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,149}',model) or not isinstance(key,str) or not 16<=len(key)<=1000 or any(ord(c)<33 for c in key):
        raise Problem(409,'Sprachmodell und geschützter API-Schlüssel sind nicht vollständig eingerichtet.')
    return SpeechConfiguration(instance['instance_id'],endpoint,model,key)


def wav_bytes(encoded):
    if not isinstance(encoded,str) or len(encoded)>4*((MAX_AUDIO_BYTES+2)//3):
        raise Problem(413,'Sprachaufnahme überschreitet 60 Sekunden.')
    try:
        raw=base64.b64decode(encoded,validate=True)
        if not 44<len(raw)<=MAX_AUDIO_BYTES: raise ValueError('Invalid audio size')
        riff,size,wave,fmt,fmt_size,codec,channels,rate,byte_rate,align,bits,data,data_size=struct.unpack('<4sI4s4sIHHIIHH4sI',raw[:44])
        if ((riff,wave,fmt,fmt_size,codec,channels,rate,byte_rate,align,bits,data)!=(b'RIFF',b'WAVE',b'fmt ',16,1,1,16000,32000,2,16,b'data')
                or size!=len(raw)-8 or data_size!=len(raw)-44 or data_size%2):
            raise ValueError('Only canonical PCM WAV allowed')
        return raw,data_size//2
    except (ValueError,TypeError,struct.error):
        raise Problem(400,'Eine vollständige WAV-Aufnahme mit Mono-PCM16 bei 16 kHz und höchstens 60 Sekunden erwartet.') from None


def _transcript(value):
    if not isinstance(value,str) or not value.strip() or len(value)>4000 or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise Problem(502,'Keine begrenzte verständliche Sprachantwort bestätigt. Aufnahme nicht automatisch wiederholen.')
    return value.strip()


class OpenAICompatibleSpeech:
    """Single documented multipart transcription call, verified TLS and egress."""
    def transcribe(self,config,audio,operation_id):
        endpoint=_endpoint(config.endpoint)
        boundary='smartplan-'+uuid.uuid4().hex
        pieces=[]
        for field,value in (('model',config.model),('language','de'),('response_format','json')):
            pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode())
        pieces.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="recording.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),audio,f'\r\n--{boundary}--\r\n'.encode()])
        encoded=b''.join(pieces)
        connection=None
        try:
            addresses={item[4][0] for item in socket.getaddrinfo(endpoint.hostname,443,type=socket.SOCK_STREAM)}
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                raise ValueError('Nonpublic speech provider')
            proxy_value=next((os.environ[name] for name in ('HTTPS_PROXY','https_proxy','ALL_PROXY','all_proxy','HTTP_PROXY','http_proxy') if os.environ.get(name)),None)
            if proxy_value:
                proxy=urlsplit(proxy_value)
                if proxy.scheme!='http' or not proxy.hostname or proxy.path not in ('','/') or proxy.query or proxy.fragment:
                    raise ValueError('Unsupported mandatory proxy')
                connection=http.client.HTTPSConnection(proxy.hostname,proxy.port or 80,timeout=20,context=ssl.create_default_context())
                headers={}
                if proxy.username is not None:
                    credentials=unquote(proxy.username)+':'+unquote(proxy.password or '')
                    if any(c in credentials for c in '\r\n\x00'): raise ValueError('Invalid proxy authentication')
                    headers['Proxy-Authorization']='Basic '+base64.b64encode(credentials.encode()).decode('ascii')
                connection.set_tunnel(endpoint.hostname,443,headers=headers)
            else: connection=_PinnedHTTPS(endpoint.hostname,sorted(addresses)[0])
            connection.request('POST',endpoint.path,body=encoded,headers={'Content-Type':'multipart/form-data; boundary='+boundary,
                'Accept':'application/json','Authorization':'Bearer '+config.api_key,'X-Client-Request-Id':operation_id})
            response=connection.getresponse()
            if response.status!=200 or response.getheader('Content-Type','').split(';')[0].strip().lower()!='application/json' or response.getheader('Content-Encoding','identity')!='identity':
                raise ValueError('Unconfirmed speech provider response')
            deadline,body=time.monotonic()+20,bytearray()
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise TimeoutError('Speech response deadline')
                if connection.sock: connection.sock.settimeout(remaining)
                chunk=response.read1(min(8192,32769-len(body)))
                if not chunk: break
                body.extend(chunk)
                if len(body)>32768: raise ValueError('Speech response too large')
            value=decode(bytes(body).decode('utf-8'))
            if not isinstance(value,dict): raise ValueError('Invalid transcript envelope')
            return _transcript(value['text'])
        except (OSError,ValueError,KeyError,TypeError,RecursionError,http.client.HTTPException):
            raise Problem(502,'Sprachantwort konnte nicht sicher bestätigt werden. Keine automatische Wiederholung.') from None
        finally:
            if connection: connection.close()


class AssistantSpeech:
    def __init__(self,office,*,clock=None,transport=None,environ=None):
        self.office,self.db=office,office.db
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.assistant=Assistant(office,clock=self.clock)
        self.transport=transport or OpenAICompatibleSpeech()
        self.environ=environ

    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')
    def _gate(self):
        from business_schema import require_capability
        require_capability(self.office,'business_assistant_speech')
        self.assistant._gate()

    def status(self,actor,project):
        with transaction(self.office):
            self.assistant._access(actor,project)
            try:provider=dict(configured=True,**configuration(self.office,self.environ).public())
            except Problem:provider=dict(configured=False,message='Sprachanbieter, Unternehmensbindung und Datenweitergabe noch nicht eingerichtet.')
            return dict(provider=provider,limits=LIMITS)

    def _outcome(self,request,status,error,attempted):
        if self.db.execute('SELECT 1 FROM business_assistant_speech_outcomes WHERE request_id=?',(request,)).fetchone():
            return
        self.db.execute('INSERT INTO business_assistant_speech_outcomes(request_id,status,error_code,provider_attempted,created_at) VALUES(?,?,?,?,?)',
            (request,status,error,int(attempted),self.now()))

    def request(self,actor,request_id):
        identifier(request_id)
        with transaction(self.office):
            fresh=_fresh(self.office,actor)
            row=self.db.execute('SELECT * FROM business_assistant_speech_requests WHERE id=? AND user_id=?',(request_id,fresh['id'])).fetchone()
            if row is None:raise Problem(404,'Persönliche Sprachaufnahme nicht verfügbar.')
            self.assistant._context(fresh,row['context_id'])
            outcome=self.db.execute('SELECT * FROM business_assistant_speech_outcomes WHERE request_id=?',(request_id,)).fetchone()
            return dict(id=request_id,project_id=row['project_id'],context_id=row['context_id'],
                status=outcome['status'] if outcome else 'started',audio_sha256=row['audio_sha256'],context_sha256=row['context_sha256'],
                retry_automatically=False,audio_persisted=False,transcript_persisted=False,
                provider_call_may_have_been_charged=bool(outcome['provider_attempted']) if outcome else True,
                error_code=outcome['error_code'] if outcome else '',created_at=row['created_at'])

    def transcribe(self,actor,data):
        if not isinstance(data,dict) or set(data)!={'request_id','context_id','data_transfer_confirmed','audio_base64'} or data.get('data_transfer_confirmed') is not True:
            raise Problem(400,'Kontext, Aufnahme und ausdrückliche Bestätigung der einmaligen Audioübertragung erwartet.')
        request_id=identifier(data['request_id']);identifier(data['context_id'])
        audio,samples=wav_bytes(data['audio_base64'])
        audio_hash=_sha(audio)
        with transaction(self.office):
            context_row,context,_=self.assistant._context(actor,data['context_id'],current=True)
            fresh=self.assistant._access(actor,context['project_id']);self._gate()
            if self.db.execute('SELECT 1 FROM business_assistant_speech_requests WHERE id=?',(request_id,)).fetchone():
                raise Problem(409,'Diese Aufnahme wurde bereits begonnen. Nur den Status prüfen; keine erneute Providerübertragung.')
            config=configuration(self.office,self.environ)
            metadata=dict(id=request_id,user_id=fresh['id'],project_id=context['project_id'],context_id=context_row['id'],
                instance_id=config.instance_id,context_sha256=context_row['sha256'],audio_sha256=audio_hash,
                audio_bytes=len(audio),sample_count=samples,provider=config.public(),created_at=self.now())
            self.db.execute('INSERT INTO business_assistant_speech_requests '
                '(id,user_id,project_id,context_id,instance_id,context_sha256,audio_sha256,audio_bytes,sample_count,provider_json,provider_sha256,request_sha256,created_at) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                tuple(metadata[key] for key in ('id','user_id','project_id','context_id','instance_id','context_sha256','audio_sha256','audio_bytes','sample_count'))+
                (canonical(config.public()),_sha(config.public()),_sha(metadata),metadata['created_at']))
            self.office.audit(fresh,'assistant.speech.started',request_id)
        attempted=False
        try:
            with transaction(self.office):
                self.assistant._context(fresh,data['context_id'],current=True);self._gate()
                if self.db.execute('SELECT 1 FROM business_assistant_speech_outcomes WHERE request_id=?',(request_id,)).fetchone():
                    raise Problem(409,'Diese Sprachaufnahme wurde bereits abgeschlossen oder unterbrochen.')
                if configuration(self.office,self.environ)!=config:
                    raise Problem(409,'Sprachkonfiguration wurde vor Übertragung geändert.')
            attempted=True
            text=_transcript(self.transport.transcribe(config,audio,request_id))
            with transaction(self.office):
                self.assistant._context(fresh,data['context_id'],current=True);self._gate()
                if self.db.execute('SELECT 1 FROM business_assistant_speech_outcomes WHERE request_id=?',(request_id,)).fetchone():
                    raise Problem(409,'Diese Sprachaufnahme wurde bereits abgeschlossen oder unterbrochen.')
                if configuration(self.office,self.environ)!=config:
                    raise Problem(409,'Sprachkonfiguration wurde während der Antwort geändert.')
                self._outcome(request_id,'completed','',attempted)
                self.office.audit(fresh,'assistant.speech.completed',request_id)
                return dict(id=request_id,project_id=context['project_id'],context_id=context_row['id'],status='completed',text=text,
                    audio_sha256=audio_hash,context_sha256=context_row['sha256'],audio_persisted=False,transcript_persisted=False,retry_automatically=False)
        except Problem as error:
            with transaction(self.office):
                self._outcome(request_id,'failed','access_or_context_changed' if error.status in (401,403,404,409,423) else 'provider_unconfirmed',attempted)
            raise
        except Exception:
            with transaction(self.office):self._outcome(request_id,'failed','provider_unconfirmed',attempted)
            raise Problem(502,'Sprachantwort nicht bestätigt. Nur den Status prüfen; nicht automatisch wiederholen.') from None


def sanitize_after_restore(db):
    tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} if isinstance(db,sqlite3.Connection) else {row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")}
    if TABLES[0] not in tables:return
    for row in db.execute('SELECT id FROM business_assistant_speech_requests r WHERE NOT EXISTS(SELECT 1 FROM business_assistant_speech_outcomes o WHERE o.request_id=r.id)').fetchall():
        db.execute('INSERT INTO business_assistant_speech_outcomes(request_id,status,error_code,provider_attempted,created_at) VALUES(?,?,?,?,?)',
            (row['id'],'interrupted','interrupted_by_restore',1,now_iso()))


def validate_integrity(office):
    try:
        for row in office.db.execute('SELECT * FROM business_assistant_speech_requests'):
            for field in ('id','user_id','project_id','context_id','instance_id'):identifier(row[field])
            for field in ('context_sha256','audio_sha256','provider_sha256','request_sha256'):
                if not re.fullmatch(r'[a-f0-9]{64}',row[field]):raise ValueError('Invalid speech metadata hash')
            provider=decode(row['provider_json'])
            if set(provider)!={'adapter','instance_id','endpoint','model'} or provider['adapter']!='openai_compatible_transcription' or provider['instance_id']!=row['instance_id']:
                raise ValueError('Invalid speech provider metadata')
            _endpoint(provider['endpoint'])
            if not isinstance(provider['model'],str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./:-]{0,149}',provider['model']):
                raise ValueError('Invalid speech model')
            if datetime.fromisoformat(row['created_at']).tzinfo is None:
                raise ValueError('Unqualified speech timestamp')
            if row['audio_bytes']!=row['sample_count']*2+44 or not 0<row['sample_count']<=960000:
                raise ValueError('Invalid audio metadata')
            context=office.db.execute('SELECT * FROM business_assistant_contexts WHERE id=?',(row['context_id'],)).fetchone()
            if context is None or context['project_id']!=row['project_id'] or context['sha256']!=row['context_sha256'] or json.loads(context['payload_json'])['instance_id']!=row['instance_id']:
                raise ValueError('Invalid speech context')
            metadata={key:row[key] for key in ('id','user_id','project_id','context_id','instance_id','context_sha256','audio_sha256','audio_bytes','sample_count','created_at')}
            metadata['provider']=provider
            if _sha(metadata)!=row['request_sha256'] or _sha(provider)!=row['provider_sha256']:
                raise ValueError('Modified speech metadata')
        for row in office.db.execute('SELECT * FROM business_assistant_speech_outcomes'):
            if row['status'] not in ('completed','failed','interrupted') or row['provider_attempted'] not in (0,1) or (row['status']=='completed')!=(row['error_code']==''):
                raise ValueError('Invalid speech outcome')
            if (row['status']=='completed' and row['provider_attempted']!=1 or
                    row['status']=='interrupted' and (row['error_code']!='interrupted_by_restore' or row['provider_attempted']!=1) or
                    row['status']=='failed' and row['error_code'] not in ('provider_unconfirmed','access_or_context_changed') or
                    datetime.fromisoformat(row['created_at']).tzinfo is None):
                raise ValueError('Invalid speech completion metadata')
            if not office.db.execute('SELECT 1 FROM business_assistant_speech_requests WHERE id=?',(row['request_id'],)).fetchone():
                raise ValueError('Unbound speech outcome')
    except (Problem,TypeError,ValueError,KeyError,json.JSONDecodeError) as error:
        raise ValueError('Invalid assistant speech metadata') from error
    return True


def methods(path):
    if path=='/assistant/speech/status' or re.fullmatch(r'/assistant/speech/requests/[a-f0-9]{32}',path):return 'GET'
    if path=='/assistant/speech/transcribe':return 'POST'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'Methode nicht erlaubt.')
    if not isinstance(data,dict):raise Problem(400,'JSON-Objekt erwartet.')
    api=AssistantSpeech(office)
    query=data.get('_query',{})
    if method=='GET':
        if set(data)-{'_query'}:raise Problem(400,'Keine zusätzlichen Abrufinhalte erlaubt.')
        if path.endswith('/status'):
            if set(query)!={'project_id'}:raise Problem(400,'Ein Projekt angeben.')
            result=api.status(actor,query['project_id'])
        else:
            if query:raise Problem(400,'Keine Abruffilter erlaubt.')
            result=api.request(actor,path.rsplit('/',1)[1])
    else:
        if query:raise Problem(400,'Keine Schreibfilter erlaubt.')
        result=api.transcribe(actor,{key:value for key,value in data.items() if key!='_query'})
    return result,200,'application/json'
