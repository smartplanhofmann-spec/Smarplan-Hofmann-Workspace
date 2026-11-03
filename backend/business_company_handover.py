"""Owner-only portable company evidence and a non-destructive exit review.

No deletion, deprovisioning, external transfer or credential revocation occurs.
The existing operator-bound company identity is required for new exports.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import io
import json
import re
import sqlite3
import uuid
import zipfile

from core import Problem,canonical
from business_foundation import _fresh
from business_operations import identifier,text,transaction
from company_export_archive import build,verify,structure,sha,catalog_sha256,MAX_ARCHIVE_BYTES,MAX_SOURCE_BYTES,MAX_ROWS
from workspace_api import BinaryAttachment

FEATURES=('company_handover',)
TABLES=('business_company_exports','business_company_exit_reviews','business_company_handover_requests')
CHECKS=('export_opened','retention_reviewed','recipient_handover_confirmed','provider_revocations_reviewed',
        'local_access_reviewed','backup_plan_reviewed','service_shutdown_reviewed')
_ID=r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB','BYTEA'):raise ValueError('Unsupported binary type')
    return [f'''CREATE TABLE IF NOT EXISTS business_company_exports(
      id TEXT PRIMARY KEY,instance_id TEXT NOT NULL,catalog_sha256 TEXT NOT NULL,
      manifest_json TEXT NOT NULL,manifest_sha256 TEXT NOT NULL,archive {binary_type} NOT NULL,
      archive_sha256 TEXT NOT NULL,archive_size INTEGER NOT NULL CHECK(archive_size>0),
      reason TEXT NOT NULL,created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
      '''CREATE TABLE IF NOT EXISTS business_company_exit_reviews(
      id TEXT PRIMARY KEY,instance_id TEXT NOT NULL,revision INTEGER NOT NULL UNIQUE CHECK(revision>0),
      export_id TEXT NOT NULL REFERENCES business_company_exports(id),export_sha256 TEXT NOT NULL,
      checks_json TEXT NOT NULL,evidence TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,
      created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
      '''CREATE TABLE IF NOT EXISTS business_company_handover_requests(
      user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,operation TEXT NOT NULL,
      request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''']


def protected_tables():return TABLES


def runtime_privileges():return {table:('SELECT','INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect=='sqlite':
        result=[f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable company handover'); END"
                for table in TABLES for action in ('UPDATE','DELETE')]
        for table,condition in zip(TABLES,('id=NEW.id','id=NEW.id OR revision=NEW.revision','user_id=NEW.user_id AND request_id=NEW.request_id')):
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) BEGIN SELECT RAISE(ABORT,'immutable company handover'); END")
        return result
    if dialect=='postgresql':
        result=["CREATE OR REPLACE FUNCTION business_company_handover_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable company handover'; END; $$"]
        for table in TABLES:
            for action in ('UPDATE','DELETE'):
                name=table+'_'+action.lower()+'_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_company_handover_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


@contextmanager
def snapshot_transaction(office):
    """Acquire the application's cross-process lock, then a real MVCC snapshot.

    A manual outer transaction is used because Database.__enter__ already reads
    its advisory lock before PostgreSQL permits SET TRANSACTION ISOLATION LEVEL.
    No provider or external filesystem call occurs within this transaction.
    """
    with office.lock:
        if isinstance(office.db,sqlite3.Connection):
            with transaction(office):yield
            return
        if office.db.contexts or office.db.connection.info.transaction_status.value!=0:
            raise Problem(409,'Unternehmensexport benötigt einen eigenständigen Snapshot.')
        from online.store import LOCK_ID
        # Wait before establishing the MVCC snapshot, so a completed access
        # revocation cannot be hidden by an older snapshot taken while waiting.
        office.db.execute('SELECT pg_advisory_lock(?)',(LOCK_ID,))
        try:
            with office.db.connection.transaction():
                office.db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                yield
        finally:
            if not office.db.connection.closed:
                office.db.execute('SELECT pg_advisory_unlock(?)',(LOCK_ID,))


def _shape(data,expected):
    if not isinstance(data,dict) or set(data)!=set(expected):raise Problem(400,'Vollständige unveränderte Export-/Prüffelder erwartet.')


def _owner(office,actor):
    fresh=_fresh(office,actor)
    if fresh['role']!='owner':raise Problem(403,'Der vollständige Unternehmensexport ist ausschließlich der aktiven Geschäftsführung zugänglich.')
    return fresh


def _binding(office):
    from business_instance import validate_integrity as validate_identity
    validate_identity(office)
    saved=office.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
    if saved is None:raise Problem(409,'Der Operator muss diese Unternehmensinstanz zuerst fest an Datenbank und Ablage binden.')
    return saved['instance_id']


def _metadata(row):
    manifest=json.loads(row['manifest_json'])
    return {**{key:row[key] for key in ('id','instance_id','created_by','created_at','reason','catalog_sha256')},
            'sha256':row['archive_sha256'],'size':row['archive_size'],
            **{key:manifest[key] for key in ('table_count','row_count','file_count')}}


def _review(row):
    return None if row is None else {**{key:row[key] for key in ('id','instance_id','revision','export_id','export_sha256','evidence','reason','status','created_by','created_at')},
        'checks':json.loads(row['checks_json']),'attested_only':True,'revocations_executed':False,'deletion_executed':False}


def _checked_archive(row):
    raw=bytes(row['archive'])
    if sha(raw)!=row['archive_sha256'] or len(raw)!=row['archive_size'] or sha(row['manifest_json'])!=row['manifest_sha256']:
        raise ValueError('Changed company archive')
    checked=verify(raw,instance_id=row['instance_id']);manifest=json.loads(row['manifest_json'])
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        if package.read('manifest.json')!=row['manifest_json'].encode():raise ValueError('Manifest diverges from stored archive')
    for key,column in (('export_id','id'),('catalog_sha256','catalog_sha256'),('created_at','created_at'),('created_by','created_by'),('reason','reason')):
        if manifest[key]!=row[column]:raise ValueError('Invalid company export binding')
    return raw,checked


class CompanyHandover:
    def __init__(self,office,*,clock=None):
        self.office,self.db=office,office.db;self.clock=clock or (lambda:datetime.now(timezone.utc))

    def now(self):return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _access_review(self):
        from business_schema import _tables
        tables=_tables(self.office)
        users=[dict(row) for row in self.db.execute('SELECT id,email,role,active FROM users ORDER BY id')]
        grants=[]
        for family in ('portal','customer'):
            table='business_'+family+'_grants';revocations='business_'+family+'_revocations'
            if table in tables:
                for row in self.db.execute('SELECT g.id,g.principal_id,g.project_id,g.expires_at,r.created_at AS revoked_at FROM '+table+' g LEFT JOIN '+revocations+' r ON r.grant_id=g.id ORDER BY g.id'):
                    grants.append(dict(row,family=family))
        integrations=[dict(row) for row in self.db.execute('SELECT provider,state,owner_id,updated_at FROM external_connections ORDER BY provider')] if 'external_connections' in tables else []
        offline=[dict(row) for row in self.db.execute('SELECT user_id,COUNT(*) AS count FROM plan_sessions GROUP BY user_id ORDER BY user_id')] if 'plan_sessions' in tables else []
        inbound=[dict(row) for row in self.db.execute('SELECT id,owner_id,name,source_account,expires_at,revoked_at FROM inbound_import_tokens ORDER BY id')] if 'inbound_import_tokens' in tables else []
        return dict(users=users,portal_grants=grants,integrations=integrations,offline_access=offline,inbound_access=inbound,
            provider_revocations_executed=False,local_revocations_executed=False,
            external_recipients_review='Review saved correspondence, portal publications and provider account recipients separately.')

    def state(self,actor):
        with transaction(self.office):
            _owner(self.office,actor);blockers=[];instance=None;inventory=[]
            try:instance=_binding(self.office)
            except Problem as error:blockers.append(dict(code='instance_binding_required',message=error.message))
            try:inventory=structure(self.office)
            except Problem as error:blockers.append(dict(code='catalog_review_required',message=error.message))
            rows=self.db.execute('SELECT id,instance_id,catalog_sha256,manifest_json,archive_sha256,archive_size,reason,created_by,created_at FROM business_company_exports ORDER BY created_at DESC,id DESC').fetchall()
            exports=[_metadata(row) for row in rows if row['instance_id']==instance]
            latest=self.db.execute('SELECT * FROM business_company_exit_reviews ORDER BY revision DESC LIMIT 1').fetchone()
            if latest and latest['instance_id']!=instance:raise Problem(409,'Ausstiegsprüfung gehört zu einer anderen Unternehmensinstanz.')
            return dict(instance_id=instance,ready=not blockers,blockers=blockers,catalog_sha256=catalog_sha256(),inventory=inventory,exports=exports,
                exit_review=_review(latest),access_review=self._access_review(),
                limits=dict(max_archive_bytes=MAX_ARCHIVE_BYTES,max_source_bytes=MAX_SOURCE_BYTES,max_rows=MAX_ROWS),
                owner_only=True,database_restore_supported=False,external_only_files_downloaded=False,
                checklist_keys=list(CHECKS),deletion_executed=False,revocations_executed=False)

    def _replay(self,actor,operation,data):
        identifier(data['request_id']);fingerprint=sha(canonical(dict(operation=operation,data=data)))
        row=self.db.execute('SELECT * FROM business_company_handover_requests WHERE user_id=? AND request_id=?',(actor['id'],data['request_id'])).fetchone()
        if row:
            if row['operation']!=operation or row['request_hash']!=fingerprint:raise Problem(409,'Vorgangskennung wurde mit anderem Inhalt verwendet.')
            return fingerprint,json.loads(row['result_json'])
        return fingerprint,None

    def _remember(self,actor,operation,data,fingerprint,result):
        self.db.execute('INSERT INTO business_company_handover_requests VALUES(?,?,?,?,?)',(actor['id'],data['request_id'],operation,fingerprint,canonical(result)))

    def create(self,actor,data):
        _shape(data,('request_id','instance_id','catalog_sha256','reason','confirmation','sensitive_data_confirmed'))
        identifier(data['instance_id']);reason=text(data['reason'],'Exportgrund',1000,required=True)
        if data['confirmation'] is not True or data['sensitive_data_confirmed'] is not True:raise Problem(400,'Vollständigen Export einschließlich sensibler Unternehmens-/Personaldaten ausdrücklich bestätigen.')
        with snapshot_transaction(self.office):
            fresh=_owner(self.office,actor);instance=_binding(self.office)
            if data['instance_id']!=instance:raise Problem(409,'Exportentscheidung gehört zu einer anderen Unternehmensinstanz.')
            fingerprint,replay=self._replay(fresh,'export',data)
            if replay:
                self._get(replay['id'],instance);return replay
            try:
                if data['catalog_sha256']!=catalog_sha256():raise Problem(409,'Exportkatalog wurde geändert; Bestandsaufnahme erneut prüfen.')
                inventory=structure(self.office);identifier_value=uuid.uuid4().hex;stamp=self.now()
                archive,manifest=build(self.office,instance_id=instance,export_id=identifier_value,created_at=stamp,created_by=fresh['id'],reason=reason,inventory=inventory)
            except Problem as error:
                # Negative receipt lookup and all validation share the lock.
                # Only these pre-write conflicts prove this nonce was not used.
                if error.status==409:raise Problem(409,error.message,request_resolution='not_accepted') from None
                raise
            encoded=canonical(manifest)
            self.db.execute('INSERT INTO business_company_exports VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (identifier_value,instance,catalog_sha256(),encoded,sha(encoded),archive,sha(archive),len(archive),reason,fresh['id'],stamp))
            result=_metadata(self._get(identifier_value,instance));self._remember(fresh,'export',data,fingerprint,result)
            self.office.audit(fresh,'business.company.export.created',identifier_value)
            return result

    def _get(self,export_id,instance):
        identifier(export_id);row=self.db.execute('SELECT * FROM business_company_exports WHERE id=?',(export_id,)).fetchone()
        if not row or row['instance_id']!=instance:raise Problem(404,'Unternehmensarchiv nicht verfügbar.')
        if sha(row['manifest_json'])!=row['manifest_sha256']:raise Problem(409,'Exportmanifest besteht die Integritätsprüfung nicht.')
        return row

    def exported(self,actor,export_id,*,action='metadata'):
        with transaction(self.office):
            _owner(self.office,actor);row=self._get(export_id,_binding(self.office))
            if action=='metadata':return dict(_metadata(row),manifest=json.loads(row['manifest_json']))
            try:raw,checked=_checked_archive(row)
            except (ValueError,KeyError,TypeError,UnicodeError):raise Problem(409,'Unternehmensarchiv ist nicht vollständig prüfbar.') from None
            if action=='verify':return checked
            if action!='archive':raise Problem(400,'Unbekannte Exportaktion.')
            return BinaryAttachment(raw,'smartplan-company-'+export_id+'.zip')

    def review(self,actor,data):
        _shape(data,('request_id','instance_id','expected_revision','export_id','export_sha256','checks','evidence','reason','confirmation'))
        identifier(data['instance_id']);identifier(data['export_id'])
        _shape(data['checks'],CHECKS)
        if any(type(value) is not bool for value in data['checks'].values()) or data['confirmation'] is not True:raise Problem(400,'Checkliste einzeln und ausdrücklich bestätigen.')
        if type(data['expected_revision']) is not int or data['expected_revision']<0:raise Problem(400,'Nichtnegative Prüfversion erwartet.')
        reason=text(data['reason'],'Prüfgrund',1000,required=True);evidence=text(data['evidence'],'Nachweise und Verantwortliche',5000,required=True)
        with transaction(self.office):
            fresh=_owner(self.office,actor);instance=_binding(self.office)
            if data['instance_id']!=instance:raise Problem(409,'Prüfung gehört zu einer anderen Unternehmensinstanz.')
            fingerprint,replay=self._replay(fresh,'review',data)
            if replay:return replay
            row=self._get(data['export_id'],instance)
            if data['export_sha256']!=row['archive_sha256']:raise Problem(409,'Exportnachweis stimmt nicht überein.',request_resolution='not_accepted')
            self.exported(fresh,row['id'],action='verify')
            latest=self.db.execute('SELECT MAX(revision) FROM business_company_exit_reviews').fetchone()[0] or 0
            if latest!=data['expected_revision']:raise Problem(409,'Ausstiegsprüfung wurde inzwischen ergänzt.',request_resolution='not_accepted')
            status='ready_for_operator_review' if all(data['checks'].values()) else 'in_progress'
            review_id=uuid.uuid4().hex
            self.db.execute('INSERT INTO business_company_exit_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (review_id,instance,latest+1,row['id'],row['archive_sha256'],canonical(data['checks']),evidence,reason,status,fresh['id'],self.now()))
            result=_review(self.db.execute('SELECT * FROM business_company_exit_reviews WHERE id=?',(review_id,)).fetchone())
            self._remember(fresh,'review',data,fingerprint,result);self.office.audit(fresh,'business.company.exit.reviewed',review_id)
            return result


def validate_integrity(office):
    for row in office.db.execute('SELECT * FROM business_company_exports'):
        _checked_archive(row)
    previous=0
    for row in office.db.execute('SELECT * FROM business_company_exit_reviews ORDER BY revision'):
        checks=json.loads(row['checks_json']);export=office.db.execute('SELECT instance_id,archive_sha256 FROM business_company_exports WHERE id=?',(row['export_id'],)).fetchone()
        if (row['revision']!=previous+1 or set(checks)!=set(CHECKS) or any(type(v) is not bool for v in checks.values()) or not export
                or export['instance_id']!=row['instance_id'] or export['archive_sha256']!=row['export_sha256']
                or row['status']!=('ready_for_operator_review' if all(checks.values()) else 'in_progress')):raise ValueError('Invalid company exit review')
        previous=row['revision']
    for row in office.db.execute('SELECT * FROM business_company_handover_requests'):
        result=json.loads(row['result_json'])
        if row['operation']=='export':
            source=office.db.execute('SELECT * FROM business_company_exports WHERE id=?',(result['id'],)).fetchone()
            expected=_metadata(source) if source else None
        elif row['operation']=='review':
            source=office.db.execute('SELECT * FROM business_company_exit_reviews WHERE id=?',(result['id'],)).fetchone()
            expected=_review(source)
        else:raise ValueError('Unknown company handover receipt')
        if (not source or source['created_by']!=row['user_id'] or result!=expected or not re.fullmatch(r'[a-f0-9]{64}',row['request_hash'])):
            raise ValueError('Invalid company handover receipt')
    return True


def methods(path):
    if path in ('/company-handover','/company-handover/inventory'):return 'GET'
    if path in ('/company-handover/exports','/company-handover/exit-reviews'):return 'POST'
    if re.fullmatch('/company-handover/exports/'+_ID+'(?:/(?:archive|verify))?',path):return 'GET'
    return None


def dispatch(office,actor,path,method,data):
    allowed=methods(path)
    if allowed is None:return None
    if method!=allowed:raise Problem(405,'HTTP-Methode nicht erlaubt.')
    if method=='GET' and data not in ({},{'_query':{}}):raise Problem(400,'Keine zusätzlichen Exportfilter erlaubt.')
    api=CompanyHandover(office)
    if path in ('/company-handover','/company-handover/inventory'):
        result=api.state(actor)
        if path.endswith('/inventory'):result=dict(catalog_sha256=result['catalog_sha256'],items=result['inventory'],blockers=result['blockers'])
        return result,200,'application/json'
    if path.endswith('/exit-reviews'):return api.review(actor,data),201,'application/json'
    if path=='/company-handover/exports':return api.create(actor,data),201,'application/json'
    parts=path.split('/');action=parts[4] if len(parts)>4 else 'metadata'
    return api.exported(actor,parts[3],action=action),200,'application/zip' if action=='archive' else 'application/json'
