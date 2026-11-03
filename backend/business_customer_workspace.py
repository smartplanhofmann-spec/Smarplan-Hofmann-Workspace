"""Explicit project publications and bounded customer file exchange.

Customer credentials are distinct from offer credentials and Office actors.
Public views contain only deliberately published snapshots. Customer originals
remain in an inbox until an authorized employee accepts them into the project.
"""
import base64
from datetime import timedelta
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import uuid

from core import Problem, canonical
from business_operations import Domain, BusinessOperations, identifier, text as _text, transaction, iso_date
from business_portal import _origin, _at, _token

FEATURES = ('customer_workspace_portal',)
MAX_UPLOAD = 4 * 1024 * 1024
MAX_PUBLISHED_FILE = 20 * 1024 * 1024
MAX_UPLOADS = 20
MAX_UPLOAD_TOTAL = 20 * 1024 * 1024
PREFIX = 'business_customer_'
_HISTORY = tuple(PREFIX + name for name in ('grants', 'revocations', 'publications', 'files',
    'file_revocations', 'uploads', 'acceptances', 'staff_requests', 'upload_requests'))
_ID = r'[a-f0-9]{32}'
_HASH = r'[a-f0-9]{64}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage')
    return [
        '''CREATE TABLE IF NOT EXISTS business_customer_grants(
        id TEXT PRIMARY KEY, principal_id TEXT NOT NULL REFERENCES business_portal_principals(id),
        project_id TEXT NOT NULL REFERENCES projects(id), customer_id TEXT NOT NULL REFERENCES customers(id),
        project_name TEXT NOT NULL, customer_name TEXT NOT NULL,
        allow_upload INTEGER NOT NULL CHECK(allow_upload IN (0,1)), secret_hash TEXT NOT NULL UNIQUE,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, expires_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_customer_revocations(
        grant_id TEXT PRIMARY KEY REFERENCES business_customer_grants(id), reason TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('staff','restore')), revoked_by TEXT REFERENCES users(id), created_at TEXT NOT NULL,
        CHECK((kind='staff' AND revoked_by IS NOT NULL) OR (kind='restore' AND revoked_by IS NULL)))''',
        '''CREATE TABLE IF NOT EXISTS business_customer_sessions(
        token_hash TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES business_customer_grants(id),
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_customer_publications(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), customer_id TEXT NOT NULL REFERENCES customers(id),
        revision INTEGER NOT NULL CHECK(revision>0), payload_json TEXT NOT NULL, sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(project_id,customer_id,revision))''',
        f'''CREATE TABLE IF NOT EXISTS business_customer_files(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), customer_id TEXT NOT NULL REFERENCES customers(id),
        source_kind TEXT NOT NULL CHECK(source_kind IN ('media','service_report','document')), source_id TEXT NOT NULL,
        title TEXT NOT NULL, filename TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>0),
        sha256 TEXT NOT NULL, original {binary_type} NOT NULL, created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_customer_file_revocations(
        file_id TEXT PRIMARY KEY REFERENCES business_customer_files(id), reason TEXT NOT NULL,
        revoked_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_customer_uploads(
        id TEXT PRIMARY KEY, grant_id TEXT NOT NULL REFERENCES business_customer_grants(id),
        project_id TEXT NOT NULL REFERENCES projects(id), customer_id TEXT NOT NULL REFERENCES customers(id),
        filename TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL CHECK(size>0), sha256 TEXT NOT NULL,
        original {binary_type} NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_customer_acceptances(
        upload_id TEXT PRIMARY KEY REFERENCES business_customer_uploads(id), media_id TEXT NOT NULL UNIQUE REFERENCES business_media(id),
        classification TEXT NOT NULL CHECK(classification IN ('restricted','operational','financial','personnel')),
        accepted_by TEXT NOT NULL REFERENCES users(id), accepted_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_customer_staff_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
        operation TEXT NOT NULL, target_id TEXT NOT NULL, request_json TEXT NOT NULL, result_json TEXT NOT NULL,
        PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_customer_upload_requests(
        grant_id TEXT NOT NULL REFERENCES business_customer_grants(id), request_id TEXT NOT NULL,
        request_hash TEXT NOT NULL, upload_id TEXT NOT NULL REFERENCES business_customer_uploads(id),
        PRIMARY KEY(grant_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_customer_files_project ON business_customer_files(project_id,customer_id,created_at)',
        'CREATE INDEX IF NOT EXISTS business_customer_uploads_project ON business_customer_uploads(project_id,created_at)',
    ]


def protected_tables():
    return _HISTORY


def runtime_privileges():
    return {**{table: ('SELECT', 'INSERT') for table in _HISTORY},
            PREFIX + 'sessions': ('SELECT', 'INSERT', 'DELETE')}


def guard_statements(dialect):
    conflicts = {table: 'id=NEW.id' for table in _HISTORY}
    conflicts.update({PREFIX+'grants': 'id=NEW.id OR secret_hash=NEW.secret_hash',
        PREFIX+'revocations': 'grant_id=NEW.grant_id',
        PREFIX+'publications': 'id=NEW.id OR (project_id=NEW.project_id AND customer_id=NEW.customer_id AND revision=NEW.revision)',
        PREFIX+'file_revocations': 'file_id=NEW.file_id',
        PREFIX+'acceptances': 'upload_id=NEW.upload_id OR media_id=NEW.media_id',
        PREFIX+'staff_requests': 'user_id=NEW.user_id AND request_id=NEW.request_id',
        PREFIX+'upload_requests': 'grant_id=NEW.grant_id AND request_id=NEW.request_id'})
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
            "BEGIN SELECT RAISE(ABORT,'immutable customer workspace history'); END"
            for table in _HISTORY for action in ('UPDATE', 'DELETE')]
        return guards + [f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
            f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
            "BEGIN SELECT RAISE(ABORT,'immutable customer workspace history'); END" for table, condition in conflicts.items()]
    if dialect == 'postgresql':
        result = ["""CREATE OR REPLACE FUNCTION business_customer_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'immutable customer workspace history'; END; $$"""]
        for table in _HISTORY:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                    f"THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_customer_immutable_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


def runtime_features(office):
    return FEATURES if _origin(office) else ()


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def text(value, name, maximum=1000, *, required=False):
    result = _text(value, name, maximum, required=required)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise Problem(400, 'Gültiger Unicode-Text erwartet: '+name)
    return result


def _body(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields) | {'request_id'}:
        raise Problem(400, 'Vollständige vorgesehene Felder erwartet')
    identifier(data['request_id'], 'Anfrage-ID')


def _confirmed(value):
    if value is not True:
        raise Problem(400, 'Ausdrückliche Bestätigung erforderlich')


def _filename(value):
    text(value, 'Dateiname', 200, required=True)
    if value in ('.', '..') or any(c in value for c in '/\\\r\n\x00'):
        raise Problem(400, 'Einfacher Dateiname ohne Pfad erwartet')
    return value


def _file_bytes(row):
    from business_operations import MEDIA_TYPES, _image_check
    try:
        content = bytes(row['original'])
        if (row['media_type'] not in MEDIA_TYPES or type(row['size']) is not int or len(content) != row['size'] or
                not 1 <= len(content) <= MAX_PUBLISHED_FILE or _sha(content) != row['sha256']):
            raise ValueError('Invalid original')
        _filename(row['filename'])
        _image_check(content, row['media_type'])
    except (Problem, KeyError, TypeError, ValueError) as error:
        raise Problem(500, 'Originaldatei besteht die Integritätsprüfung nicht') from error
    return content


class CustomerWorkspace(Domain):
    def _online(self):
        origin = _origin(self.office)
        if not origin:
            raise Problem(409, 'Kundenarbeitsbereich benötigt den eingerichteten Online-Dienst')
        return origin

    def _gate(self):
        from business_schema import require_capability, state, require_financial_release
        from business_organization import module_enabled
        self._online()
        require_capability(self.office, 'business_customer_workspace')
        if state(self.office)['compatibility_mode'] != 'business':
            raise Problem(409, 'Kundenarbeitsbereich ist im Lesemodus')
        if not module_enabled(self.office, 'documents'):
            raise Problem(423, 'Dokumente sind fachlich deaktiviert')
        require_financial_release(self.office)

    def _staff(self, actor, project_id, *, write=False):
        identifier(project_id, 'Projekt-ID')
        fresh = self.access(actor, 'portal.manage', project_id)
        self.access(fresh, 'documents.read', project_id)
        if write:
            self._gate()
        return fresh

    def _project(self, project_id, customer_id=None):
        row = self.office.db.execute('SELECT p.id,p.name,p.customer_id,c.name AS customer,c.active '
            'FROM projects p LEFT JOIN customers c ON c.id=p.customer_id WHERE p.id=?', (project_id,)).fetchone()
        if row is None:
            raise Problem(404, 'Projekt nicht verfügbar')
        erased = self.office.db.execute('SELECT erased_at FROM business_contact_extras WHERE customer_id=?',
            (row['customer_id'],)).fetchone() if row['customer_id'] else None
        if not row['customer_id'] or not row['active'] or (erased and erased['erased_at']):
            raise Problem(409, 'Aktive Kundenbindung erforderlich')
        if customer_id is not None and customer_id != row['customer_id']:
            raise Problem(409, 'Kundenbindung wurde geändert; erneut prüfen')
        return {key: row[key] for key in ('id', 'name', 'customer_id', 'customer')}

    def _row(self, table, identifier_):
        identifier(identifier_)
        row = self.office.db.execute('SELECT * FROM '+PREFIX+table+' WHERE id=?', (identifier_,)).fetchone()
        if row is None:
            raise Problem(404, 'Eintrag nicht verfügbar')
        return row

    def _receipt(self, actor, operation, target, data):
        digest = _sha(canonical([operation, target, data]))
        row = self.office.db.execute('SELECT * FROM business_customer_staff_requests WHERE user_id=? AND request_id=?',
            (actor['id'], data['request_id'])).fetchone()
        if row and (row['request_hash'] != digest or row['operation'] != operation or row['target_id'] != target):
            raise Problem(409, 'Anfrage-ID wurde bereits anders verwendet')
        return digest, json.loads(row['result_json']) if row else None

    def _remember(self, actor, data, digest, operation, target, result):
        self.office.db.execute('INSERT INTO business_customer_staff_requests(user_id,request_id,request_hash,operation,target_id,request_json,result_json) VALUES(?,?,?,?,?,?,?)',
            (actor['id'], data['request_id'], digest, operation, target, canonical(data), canonical(result)))
        self.office.audit(actor, 'business.customer_workspace.'+operation, target)

    def _bound(self, row):
        principal = self.office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (row['principal_id'],)).fetchone()
        if (not principal or not principal['active'] or principal['customer_id'] != row['customer_id'] or
                _at(row['expires_at']) <= _at(self.now()) or
                self.office.db.execute('SELECT 1 FROM business_customer_revocations WHERE grant_id=?', (row['id'],)).fetchone()):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        try:
            self._project(row['project_id'], row['customer_id'])
        except Problem:
            raise Problem(401, 'Kundenzugang nicht verfügbar') from None
        return principal

    def _grant(self, row):
        principal = self.office.db.execute('SELECT name,email FROM business_portal_principals WHERE id=?', (row['principal_id'],)).fetchone()
        revoked = self.office.db.execute('SELECT 1 FROM business_customer_revocations WHERE grant_id=?', (row['id'],)).fetchone()
        status = 'revoked' if revoked else 'expired' if _at(row['expires_at']) <= _at(self.now()) else 'active'
        if status == 'active':
            try:
                self._bound(row)
            except Problem:
                status = 'unavailable'
        return dict(id=row['id'], recipient_name=principal['name'], recipient_email=principal['email'],
            allow_upload=bool(row['allow_upload']), created_at=row['created_at'], expires_at=row['expires_at'], status=status)

    def _publication(self, row):
        if row is None:
            return None
        if _sha(row['payload_json']) != row['sha256']:
            raise Problem(500, 'Veröffentlichung besteht die Integritätsprüfung nicht')
        result = json.loads(row['payload_json'])
        fields = {'id', 'project_id', 'customer_id', 'revision', 'project_name', 'customer_name',
            'title', 'description', 'status_label', 'start_date', 'end_date', 'published_at'}
        if (not isinstance(result, dict) or set(result) != fields or
                any(result.get(key) != row[key] for key in ('id', 'project_id', 'customer_id', 'revision')) or
                type(result['revision']) is not int or result['revision'] < 1 or result['published_at'] != row['created_at']):
            raise Problem(500, 'Veröffentlichung ist nicht konsistent')
        for key, maximum in (('title', 300), ('description', 10000), ('status_label', 200), ('project_name', 500), ('customer_name', 500)):
            text(result[key], key, maximum, required=key != 'status_label')
        for key in ('start_date', 'end_date'):
            iso_date(result[key], optional=True)
        if result['start_date'] and result['end_date'] and result['end_date'] < result['start_date']:
            raise Problem(500, 'Veröffentlichungszeitraum ist nicht konsistent')
        return result

    def _latest(self, project_id, customer_id):
        row = self.office.db.execute('SELECT * FROM business_customer_publications WHERE project_id=? AND customer_id=? ORDER BY revision DESC LIMIT 1',
            (project_id, customer_id)).fetchone()
        return self._publication(row)

    def _file(self, row, *, staff=False):
        _file_bytes(row)
        result = {key: row[key] for key in ('id', 'project_id', 'title', 'filename', 'media_type', 'size', 'sha256', 'created_at')}
        if staff:
            result.update(source_kind=row['source_kind'], source_id=row['source_id'],
                status='revoked' if self.office.db.execute('SELECT 1 FROM business_customer_file_revocations WHERE file_id=?', (row['id'],)).fetchone() else 'published')
        return result

    def _upload(self, row, *, staff=False):
        _file_bytes(row)
        result = {key: row[key] for key in ('id', 'grant_id', 'project_id', 'filename', 'media_type', 'size', 'sha256', 'note', 'created_at')}
        accepted = self.office.db.execute('SELECT * FROM business_customer_acceptances WHERE upload_id=?', (row['id'],)).fetchone()
        result['status'] = 'accepted' if accepted else 'received'
        if accepted:
            result['accepted_at'] = accepted['accepted_at']
        if staff:
            result.update(customer_id=row['customer_id'], acceptance=dict(accepted) if accepted else None)
        return result

    def _source(self, actor, project_id, kind, source_id):
        identifier(source_id, 'Quelldatei-ID')
        ops = BusinessOperations(self.office)
        if kind == 'media':
            value = ops.get_media(actor, project_id, source_id)
            if value['status'] != 'ready' or value.get('purpose') == 'receipt' or value.get('classification') == 'personnel':
                raise Problem(409, 'Nur fertige Projektdokumente und Fotos freigeben')
            content = ops.media_source(actor, project_id, source_id)
            filename, media_type, title = value['filename'], value['media_type'], value.get('caption') or value['filename']
        elif kind == 'service_report':
            value = ops.get_entry(actor, project_id, source_id)
            if value['kind'] != 'service' or value['status'] != 'signed':
                raise Problem(409, 'Unterzeichneten Servicebericht auswählen')
            content = ops.entry_pdf(actor, project_id, source_id)
            filename, media_type, title = 'Servicebericht-'+source_id+'.pdf', 'application/pdf', value['title']
        elif kind == 'document':
            from business_documents import Documents
            self.access(actor, 'finance.read', project_id)
            value = Documents(self.office).get(actor, source_id)
            if value['project_id'] != project_id or value['status'] != 'final' or value['kind'] not in (
                    'offer', 'order_confirmation', 'delivery_note', 'invoice', 'advance_invoice', 'final_invoice', 'credit_note'):
                raise Problem(409, 'Finalen Kundenbeleg aus diesem Projekt auswählen')
            project = self._project(project_id)
            if value['customer_id'] != project['customer_id']:
                raise Problem(409, 'Beleg gehört nicht zur aktuellen Kundenbindung')
            content = Documents(self.office).archive(actor, source_id)
            filename, media_type, title = 'Beleg-'+source_id+'.pdf', 'application/pdf', value.get('title') or value['number']
        else:
            raise Problem(400, 'Unbekannte Dateiherkunft')
        _filename(filename)
        if not 1 <= len(content) <= MAX_PUBLISHED_FILE:
            raise Problem(413, 'Veröffentlichte Datei ist zu groß')
        return dict(source_kind=kind, source_id=source_id, title=title, filename=filename,
            media_type=media_type, size=len(content), sha256=_sha(content)), content

    def _sources(self, actor, project_id):
        options = []
        candidates = [('media', row['id']) for row in self.office.db.execute("SELECT id FROM business_media WHERE project_id=? AND status='ready' ORDER BY created_at DESC LIMIT 100", (project_id,)).fetchall()]
        candidates += [('service_report', row['id']) for row in self.office.db.execute("SELECT id FROM business_operation_entries WHERE project_id=? AND kind='service' ORDER BY created_at DESC LIMIT 100", (project_id,)).fetchall()]
        candidates += [('document', row['id']) for row in self.office.db.execute("SELECT id FROM business_documents WHERE project_id=? AND status='final' ORDER BY created_at DESC LIMIT 100", (project_id,)).fetchall()]
        for kind, source_id in candidates:
            try:
                option, _ = self._source(actor, project_id, kind, source_id)
                options.append(option)
            except Problem as error:
                if error.status not in (403, 404, 409, 413):
                    raise
        return options

    def _staff_original_access(self, actor, row, kind):
        """Published copies and accepted inbox originals retain staff file rights."""
        ops = BusinessOperations(self.office)
        if kind == 'uploads':
            accepted = self.office.db.execute('SELECT media_id FROM business_customer_acceptances WHERE upload_id=?', (row['id'],)).fetchone()
            if accepted:
                ops.get_media(actor, row['project_id'], accepted['media_id'])
        elif row['source_kind'] == 'media':
            ops.get_media(actor, row['project_id'], row['source_id'])
        elif row['source_kind'] == 'service_report':
            ops.get_entry(actor, row['project_id'], row['source_id'])
        else:
            self.access(actor, 'finance.read', row['project_id'])

    def view_staff(self, actor, project_id):
        with transaction(self.office):
            fresh = self._staff(actor, project_id)
            project = self._project(project_id)
            allowed = True
            try:
                self._gate()
            except Problem as error:
                if error.status not in (409, 423):
                    raise
                allowed = False
            files = []
            for row in self.office.db.execute('SELECT * FROM business_customer_files WHERE project_id=? AND customer_id=? ORDER BY created_at,id', (project_id, project['customer_id'])).fetchall():
                try:
                    self._staff_original_access(fresh, row, 'files')
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                files.append(self._file(row, staff=True))
            uploads = []
            for row in self.office.db.execute('SELECT * FROM business_customer_uploads WHERE project_id=? ORDER BY created_at,id', (project_id,)).fetchall():
                try:
                    self._staff_original_access(fresh, row, 'uploads')
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                uploads.append(self._upload(row, staff=True))
            can_accept = allowed
            try:
                self.access(fresh, 'documents.write', project_id)
                self.access(fresh, 'documents.classify', project_id)
            except Problem as error:
                if error.status != 403:
                    raise
                can_accept = False
            return dict(project=project, publication=self._latest(project_id, project['customer_id']), writes_allowed=allowed, can_accept=can_accept,
                grants=[self._grant(row) for row in self.office.db.execute('SELECT * FROM business_customer_grants WHERE project_id=? ORDER BY created_at,id', (project_id,)).fetchall()],
                files=files, uploads=uploads,
                source_files=self._sources(fresh, project_id))

    def create_grant(self, actor, data):
        _body(data, ('project_id', 'customer_id', 'recipient_name', 'recipient_email', 'expires_in_days', 'allow_upload', 'confirmation'))
        _confirmed(data['confirmation'])
        name = text(data['recipient_name'], 'Empfängername', 200, required=True)
        email = text(data['recipient_email'], 'E-Mail', 254, required=True)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise Problem(400, 'Gültige Empfängeradresse angeben')
        if type(data['expires_in_days']) is not int or not 1 <= data['expires_in_days'] <= 30 or type(data['allow_upload']) is not bool:
            raise Problem(400, 'Zugangsdauer 1 bis 30 Tage und ausdrückliche Uploadwahl erwartet')
        with transaction(self.office):
            fresh = self._staff(actor, data['project_id'], write=True)
            project = self._project(data['project_id'], data['customer_id'])
            fingerprint, replay = self._receipt(fresh, 'grant', project['id'], data)
            if replay:
                return dict(grant=self._grant(self._row('grants', replay['grant']['id'])), link_available=False)
            active = [row for row in self.office.db.execute('SELECT * FROM business_customer_grants WHERE project_id=?', (project['id'],)).fetchall() if self._grant(row)['status'] == 'active']
            if len(active) >= 10 or any(self._grant(row)['recipient_email'].casefold() == email.casefold() for row in active):
                raise Problem(409, 'Aktiven Empfängerzugang zuerst widerrufen; höchstens zehn Zugänge je Projekt', request_resolution='not_accepted')
            principal, grant, stamp = uuid.uuid4().hex, uuid.uuid4().hex, self.now()
            key = 'SPCI_'+secrets.token_urlsafe(32)
            expiry = (_at(stamp)+timedelta(days=data['expires_in_days'])).isoformat(timespec='seconds')
            self.office.db.execute('INSERT INTO business_portal_principals(id,customer_id,name,email,active,revision,created_by,created_at) VALUES(?,?,?,?,1,1,?,?)',
                (principal, project['customer_id'], name, email, fresh['id'], stamp))
            self.office.db.execute('INSERT INTO business_customer_grants(id,principal_id,project_id,customer_id,project_name,customer_name,allow_upload,secret_hash,created_by,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (grant, principal, project['id'], project['customer_id'], project['name'], project['customer'], int(data['allow_upload']), _sha(key), fresh['id'], stamp, expiry))
            result = dict(grant=self._grant(self._row('grants', grant)), link_available=False)
            self._remember(fresh, data, fingerprint, 'grant', project['id'], result)
            return dict(result, link_available=True, portal_url=self._online()+'/office/customer-workspace.html#grant='+grant+'&key='+key)

    def revoke_grant(self, actor, grant_id, data):
        _body(data, ('reason',))
        reason = text(data['reason'], 'Widerrufsgrund', 500, required=True)
        with transaction(self.office):
            row = self._row('grants', grant_id)
            fresh = self._staff(actor, row['project_id'])
            fingerprint, replay = self._receipt(fresh, 'revoke', grant_id, data)
            if not replay:
                if not self.office.db.execute('SELECT 1 FROM business_customer_revocations WHERE grant_id=?', (grant_id,)).fetchone():
                    self.office.db.execute("INSERT INTO business_customer_revocations(grant_id,reason,kind,revoked_by,created_at) VALUES(?,?,'staff',?,?)", (grant_id, reason, fresh['id'], self.now()))
                self._remember(fresh, data, fingerprint, 'revoke', grant_id, self._grant(row))
            self.office.db.execute('DELETE FROM business_customer_sessions WHERE grant_id=?', (grant_id,))
            return self._grant(row)

    def publish(self, actor, data):
        _body(data, ('project_id', 'customer_id', 'expected_revision', 'title', 'description', 'status_label', 'start_date', 'end_date', 'confirmation'))
        _confirmed(data['confirmation'])
        if type(data['expected_revision']) is not int or data['expected_revision'] < 0:
            raise Problem(400, 'Aktuellen Veröffentlichungsstand angeben')
        clean = dict(title=text(data['title'], 'Titel', 300, required=True), description=text(data['description'], 'Projektinformation', 10000, required=True),
            status_label=text(data['status_label'], 'Projektstatus', 200), start_date=iso_date(data['start_date'], optional=True), end_date=iso_date(data['end_date'], optional=True))
        if clean['start_date'] and clean['end_date'] and clean['end_date'] < clean['start_date']:
            raise Problem(400, 'Projektende liegt vor Projektbeginn')
        with transaction(self.office):
            fresh = self._staff(actor, data['project_id'], write=True)
            project = self._project(data['project_id'], data['customer_id'])
            fingerprint, replay = self._receipt(fresh, 'publish', project['id'], data)
            if replay:
                return replay
            current = self._latest(project['id'], project['customer_id'])
            if data['expected_revision'] != (current['revision'] if current else 0):
                raise Problem(409, 'Projektinformation wurde inzwischen veröffentlicht', request_resolution='not_accepted')
            value = dict(clean, id=uuid.uuid4().hex, project_id=project['id'], customer_id=project['customer_id'], project_name=project['name'],
                customer_name=project['customer'], revision=data['expected_revision']+1, published_at=self.now())
            self.office.db.execute('INSERT INTO business_customer_publications(id,project_id,customer_id,revision,payload_json,sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (value['id'], project['id'], project['customer_id'], value['revision'], canonical(value), _sha(canonical(value)), fresh['id'], value['published_at']))
            self._remember(fresh, data, fingerprint, 'publish', project['id'], value)
            return value

    def publish_file(self, actor, data):
        _body(data, ('project_id', 'customer_id', 'source_kind', 'source_id', 'source_sha256', 'title', 'confirmation'))
        _confirmed(data['confirmation'])
        title = text(data['title'], 'Dateititel', 300, required=True)
        with transaction(self.office):
            fresh = self._staff(actor, data['project_id'], write=True)
            project = self._project(data['project_id'], data['customer_id'])
            fingerprint, replay = self._receipt(fresh, 'file', project['id'], data)
            try:
                source, content = self._source(fresh, project['id'], data['source_kind'], data['source_id'])
                if source['sha256'] != data['source_sha256']:
                    raise Problem(409, 'Quelldatei hat sich geändert; Original erneut prüfen')
            except Problem as error:
                if error.status == 409 and replay is None:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise
            if replay:
                return self._file(self._row('files', replay['id']), staff=True)
            count = self.office.db.execute('SELECT COUNT(*) FROM business_customer_files f WHERE project_id=? AND customer_id=? AND NOT EXISTS(SELECT 1 FROM business_customer_file_revocations r WHERE r.file_id=f.id)', (project['id'], project['customer_id'])).fetchone()[0]
            if count >= 200:
                raise Problem(409, 'Höchstens 200 gleichzeitig veröffentlichte Projektdateien', request_resolution='not_accepted')
            file_id, stamp = uuid.uuid4().hex, self.now()
            self.office.db.execute('INSERT INTO business_customer_files(id,project_id,customer_id,source_kind,source_id,title,filename,media_type,size,sha256,original,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (file_id, project['id'], project['customer_id'], source['source_kind'], source['source_id'], title, source['filename'], source['media_type'], source['size'], source['sha256'], content, fresh['id'], stamp))
            result = self._file(self._row('files', file_id), staff=True)
            self._remember(fresh, data, fingerprint, 'file', project['id'], result)
            return result

    def revoke_file(self, actor, file_id, data):
        _body(data, ('reason',))
        reason = text(data['reason'], 'Widerrufsgrund', 500, required=True)
        with transaction(self.office):
            row = self._row('files', file_id)
            fresh = self._staff(actor, row['project_id'])
            if row['source_kind'] == 'document':
                self.access(fresh, 'finance.read', row['project_id'])
            fingerprint, replay = self._receipt(fresh, 'file_revoke', file_id, data)
            if not replay:
                if not self.office.db.execute('SELECT 1 FROM business_customer_file_revocations WHERE file_id=?', (file_id,)).fetchone():
                    self.office.db.execute('INSERT INTO business_customer_file_revocations(file_id,reason,revoked_by,created_at) VALUES(?,?,?,?)', (file_id, reason, fresh['id'], self.now()))
                self._remember(fresh, data, fingerprint, 'file_revoke', file_id, self._file(row, staff=True))
            return self._file(row, staff=True)

    def accept_upload(self, actor, upload_id, data):
        _body(data, ('classification', 'confirmation'))
        _confirmed(data['confirmation'])
        if data['classification'] not in ('restricted', 'operational', 'financial', 'personnel'):
            raise Problem(400, 'Zugriffsklasse für die interne Datei auswählen')
        with transaction(self.office):
            row = self._row('uploads', upload_id)
            fresh = self._staff(actor, row['project_id'], write=True)
            self.access(fresh, 'documents.write', row['project_id'])
            self.access(fresh, 'documents.classify', row['project_id'])
            permission = {'financial': 'finance.write', 'personnel': 'personnel.manage'}.get(data['classification'])
            if permission:
                self.access(fresh, permission, row['project_id'])
            self._project(row['project_id'], row['customer_id'])
            self._staff_original_access(fresh, row, 'uploads')
            content = _file_bytes(row)
            fingerprint, replay = self._receipt(fresh, 'accept', upload_id, data)
            if replay:
                return replay
            accepted = self.office.db.execute('SELECT * FROM business_customer_acceptances WHERE upload_id=?', (upload_id,)).fetchone()
            if accepted:
                if accepted['classification'] != data['classification']:
                    raise Problem(409, 'Datei wurde bereits mit anderer Zugriffsklasse übernommen', request_resolution='not_accepted')
                result = dict(accepted)
            else:
                api = BusinessOperations(self.office)
                media = api.new_media(fresh, row['project_id'], dict(request_id=uuid.uuid4().hex, filename=row['filename'], media_type=row['media_type'], size=row['size'], sha256=row['sha256'], purpose='document', classification=data['classification']))
                from business_operations import CHUNK_SIZE
                for index, begin in enumerate(range(0, len(content), CHUNK_SIZE)):
                    api.put_media_chunk(fresh, row['project_id'], media['id'], index, content[begin:begin+CHUNK_SIZE])
                api.complete_media(fresh, row['project_id'], media['id'], {'request_id': uuid.uuid4().hex})
                result = dict(upload_id=upload_id, media_id=media['id'], classification=data['classification'], accepted_by=fresh['id'], accepted_at=self.now())
                self.office.db.execute('INSERT INTO business_customer_acceptances(upload_id,media_id,classification,accepted_by,accepted_at) VALUES(?,?,?,?,?)',
                    (upload_id, result['media_id'], data['classification'], fresh['id'], result['accepted_at']))
            self._remember(fresh, data, fingerprint, 'accept', upload_id, result)
            return result

    def staff_content(self, actor, kind, object_id):
        with transaction(self.office):
            row = self._row(kind, object_id)
            fresh = self._staff(actor, row['project_id'])
            self._staff_original_access(fresh, row, kind)
            return _file_bytes(row), row['filename'], row['media_type']

    def source_content(self, actor, project_id, kind, source_id):
        with transaction(self.office):
            fresh = self._staff(actor, project_id)
            source, content = self._source(fresh, project_id, kind, source_id)
            return content, source['filename'], source['media_type']

    def open_session(self, grant_id, key):
        self._online()
        if not isinstance(grant_id, str) or not re.fullmatch(_ID, grant_id) or not _token(key, 'SPCI_'):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        with transaction(self.office):
            row = self.office.db.execute('SELECT * FROM business_customer_grants WHERE id=?', (grant_id,)).fetchone()
            if not row or not hmac.compare_digest(row['secret_hash'], _sha(key)):
                raise Problem(401, 'Kundenzugang nicht verfügbar')
            self._bound(row)
            stamp = self.now()
            self.office.db.execute('DELETE FROM business_customer_sessions WHERE expires_at<=?', (stamp,))
            if self.office.db.execute('SELECT COUNT(*) FROM business_customer_sessions WHERE grant_id=?', (grant_id,)).fetchone()[0] >= 5:
                raise Problem(429, 'Zu viele aktive Kundensitzungen')
            token = 'SPCT_'+secrets.token_urlsafe(32)
            expiry = min(_at(row['expires_at']), _at(stamp)+timedelta(minutes=30)).isoformat(timespec='seconds')
            self.office.db.execute('INSERT INTO business_customer_sessions(token_hash,grant_id,created_at,expires_at) VALUES(?,?,?,?)', (_sha(token), grant_id, stamp, expiry))
            return dict(token=token, expires_at=expiry)

    def _session(self, token):
        self._online()
        if not _token(token, 'SPCT_'):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        row = self.office.db.execute('SELECT * FROM business_customer_sessions WHERE token_hash=?', (_sha(token),)).fetchone()
        if not row or _at(row['expires_at']) <= _at(self.now()):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        grant = self._row('grants', row['grant_id'])
        if _at(row['expires_at']) > _at(grant['expires_at']):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        self._bound(grant)
        return row, grant

    def logout(self, token):
        if not _token(token, 'SPCT_'):
            raise Problem(401, 'Kundenzugang nicht verfügbar')
        with transaction(self.office):
            self.office.db.execute('DELETE FROM business_customer_sessions WHERE token_hash=?', (_sha(token),))
        return dict(logged_out=True)

    def view(self, token):
        with transaction(self.office):
            session, grant = self._session(token)
            publication = self._latest(grant['project_id'], grant['customer_id'])
            allowed = bool(grant['allow_upload'])
            try:
                self._gate()
            except Problem as error:
                if error.status not in (409, 423):
                    raise
                allowed = False
            files = self.office.db.execute('SELECT f.* FROM business_customer_files f WHERE project_id=? AND customer_id=? AND NOT EXISTS(SELECT 1 FROM business_customer_file_revocations r WHERE r.file_id=f.id) ORDER BY created_at,id', (grant['project_id'], grant['customer_id'])).fetchall()
            public = None if publication is None else {key: publication[key] for key in ('id', 'revision', 'title', 'description', 'status_label', 'start_date', 'end_date', 'published_at')}
            return dict(grant_id=grant['id'], project=dict(id=grant['project_id'], name=publication['project_name'] if publication else grant['project_name'], customer=publication['customer_name'] if publication else grant['customer_name']),
                publication=public, files=[self._file(row) for row in files], uploads=[self._upload(row) for row in self.office.db.execute('SELECT * FROM business_customer_uploads WHERE grant_id=? ORDER BY created_at,id', (grant['id'],)).fetchall()],
                expires_at=session['expires_at'], uploads_allowed=allowed)

    def upload(self, token, data):
        _body(data, ('filename', 'media_type', 'size', 'sha256', 'content_base64', 'note'))
        # Authenticate before decoding or verifying potentially expensive originals;
        # repeat this check in the committing transaction after verification.
        with transaction(self.office):
            _, grant = self._session(token)
            self._gate()
            if not grant['allow_upload']:
                raise Problem(403, 'Dieser Zugang erlaubt keine Dateiübermittlung')
        from business_operations import MEDIA_TYPES, _image_check
        filename = _filename(data['filename'])
        text(data['note'], 'Nachricht zur Datei', 3000)
        note = data['note']
        if not isinstance(data['media_type'], str) or data['media_type'] not in MEDIA_TYPES or type(data['size']) is not int or not 1 <= data['size'] <= MAX_UPLOAD:
            raise Problem(400, 'Unterstützte Datei bis 4 MiB erwartet')
        if not isinstance(data['sha256'], str) or not re.fullmatch(_HASH, data['sha256']) or not isinstance(data['content_base64'], str) or len(data['content_base64']) > ((MAX_UPLOAD+2)//3)*4:
            raise Problem(400, 'Begrenzte Originaldatei mit Prüfsumme erwartet')
        try:
            content = base64.b64decode(data['content_base64'], validate=True)
        except (ValueError, TypeError):
            raise Problem(400, 'Gültige Base64-Datei erwartet') from None
        if len(content) != data['size'] or _sha(content) != data['sha256']:
            raise Problem(409, 'Dateigröße oder Prüfsumme stimmt nicht')
        _image_check(content, data['media_type'])
        digest = _sha(canonical(data))
        with transaction(self.office):
            _, grant = self._session(token)
            self._gate()
            if not grant['allow_upload']:
                raise Problem(403, 'Dieser Zugang erlaubt keine Dateiübermittlung')
            replay = self.office.db.execute('SELECT * FROM business_customer_upload_requests WHERE grant_id=? AND request_id=?', (grant['id'], data['request_id'])).fetchone()
            if replay:
                if replay['request_hash'] != digest:
                    raise Problem(409, 'Anfrage-ID wurde bereits anders verwendet')
                return self._upload(self._row('uploads', replay['upload_id']))
            stats = self.office.db.execute('SELECT COUNT(*) AS n,COALESCE(SUM(size),0) AS total FROM business_customer_uploads WHERE grant_id=?', (grant['id'],)).fetchone()
            if stats['n'] >= MAX_UPLOADS or stats['total']+len(content) > MAX_UPLOAD_TOTAL:
                raise Problem(413, 'Dateikontingent dieses Kundenzugangs erreicht')
            upload_id = uuid.uuid4().hex
            self.office.db.execute('INSERT INTO business_customer_uploads(id,grant_id,project_id,customer_id,filename,media_type,size,sha256,original,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (upload_id, grant['id'], grant['project_id'], grant['customer_id'], filename, data['media_type'], len(content), data['sha256'], content, note, self.now()))
            self.office.db.execute('INSERT INTO business_customer_upload_requests(grant_id,request_id,request_hash,upload_id) VALUES(?,?,?,?)', (grant['id'], data['request_id'], digest, upload_id))
            return self._upload(self._row('uploads', upload_id))

    def content(self, token, kind, object_id):
        with transaction(self.office):
            _, grant = self._session(token)
            row = self._row(kind, object_id)
            if (row['project_id'] != grant['project_id'] or row['customer_id'] != grant['customer_id'] or
                    (kind == 'uploads' and row['grant_id'] != grant['id']) or
                    (kind == 'files' and self.office.db.execute('SELECT 1 FROM business_customer_file_revocations WHERE file_id=?', (object_id,)).fetchone())):
                raise Problem(404, 'Datei nicht verfügbar')
            return _file_bytes(row), row['filename'], row['media_type']


def sanitize_after_restore(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} if isinstance(db, sqlite3.Connection) else {row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()}
    if PREFIX+'grants' not in tables:
        return
    from core import now_iso
    for row in db.execute('SELECT id FROM business_customer_grants').fetchall():
        if not db.execute('SELECT 1 FROM business_customer_revocations WHERE grant_id=?', (row['id'],)).fetchone():
            db.execute("INSERT INTO business_customer_revocations(grant_id,reason,kind,revoked_by,created_at) VALUES(?,'Wiederherstellung','restore',NULL,?)", (row['id'], now_iso()))
    db.execute('DELETE FROM business_customer_sessions')


def validate_integrity(office):
    api = CustomerWorkspace(office)
    try:
        grants = {row['id']: row for row in office.db.execute('SELECT * FROM business_customer_grants').fetchall()}
        for row in grants.values():
            identifier(row['id']); identifier(row['project_id']); identifier(row['customer_id'])
            principal = office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (row['principal_id'],)).fetchone()
            if (not principal or principal['customer_id'] != row['customer_id'] or not re.fullmatch(_HASH, row['secret_hash']) or
                    not timedelta(0) < _at(row['expires_at'])-_at(row['created_at']) <= timedelta(days=30)):
                raise ValueError('Invalid customer workspace grant')
        for row in office.db.execute('SELECT * FROM business_customer_sessions').fetchall():
            grant = grants[row['grant_id']]
            if not re.fullmatch(_HASH, row['token_hash']) or not timedelta(0) < _at(row['expires_at'])-_at(row['created_at']) <= timedelta(minutes=30) or _at(row['expires_at']) > _at(grant['expires_at']):
                raise ValueError('Invalid customer workspace session')
        revisions = {}
        for row in office.db.execute('SELECT * FROM business_customer_publications ORDER BY project_id,customer_id,revision').fetchall():
            value = api._publication(row)
            key = (row['project_id'], row['customer_id'])
            revisions[key] = revisions.get(key, 0)+1
            if row['revision'] != revisions[key] or value['published_at'] != row['created_at']:
                raise ValueError('Invalid publication chain')
        for row in office.db.execute('SELECT * FROM business_customer_files').fetchall():
            _file_bytes(row)
            identifier(row['source_id'])
            table = {'media': 'business_media', 'service_report': 'business_operation_entries', 'document': 'business_documents'}[row['source_kind']]
            source = office.db.execute('SELECT * FROM '+table+' WHERE id=? AND project_id=?', (row['source_id'], row['project_id'])).fetchone()
            if source is None:
                raise ValueError('Missing published source')
            if row['source_kind'] == 'media':
                content = bytes(source['original'])
            elif row['source_kind'] == 'service_report':
                content = bytes(source['pdf'])
            else:
                archive = office.db.execute('SELECT pdf FROM business_document_archives WHERE document_id=?', (source['id'],)).fetchone()
                content = bytes(archive['pdf'])
            if _sha(content) != row['sha256'] or content != bytes(row['original']):
                raise ValueError('Published original differs from its source')
        for row in office.db.execute('SELECT * FROM business_customer_uploads').fetchall():
            _file_bytes(row)
            grant = grants[row['grant_id']]
            if any(row[key] != grant[key] for key in ('project_id', 'customer_id')) or row['size'] > MAX_UPLOAD:
                raise ValueError('Invalid customer upload scope')
        for row in office.db.execute('SELECT * FROM business_customer_acceptances').fetchall():
            source = api._row('uploads', row['upload_id'])
            target = office.db.execute('SELECT * FROM business_media WHERE id=?', (row['media_id'],)).fetchone()
            original = office.db.execute("SELECT payload_json FROM business_operation_versions WHERE kind='media' AND object_id=? AND revision=1", (row['media_id'],)).fetchone()
            if (not target or target['project_id'] != source['project_id'] or target['created_by'] != row['accepted_by'] or
                    target['sha256'] != source['sha256'] or bytes(target['original']) != bytes(source['original']) or
                    not original or json.loads(original['payload_json'])['classification'] != row['classification']):
                raise ValueError('Invalid accepted customer original')
        for row in office.db.execute('SELECT * FROM business_customer_upload_requests').fetchall():
            source = api._row('uploads', row['upload_id'])
            data = dict(request_id=row['request_id'], filename=source['filename'], media_type=source['media_type'], size=source['size'], sha256=source['sha256'], content_base64=base64.b64encode(bytes(source['original'])).decode('ascii'), note=source['note'])
            if row['grant_id'] != source['grant_id'] or row['request_hash'] != _sha(canonical(data)):
                raise ValueError('Invalid customer upload receipt')
        for row in office.db.execute('SELECT * FROM business_customer_staff_requests').fetchall():
            identifier(row['request_id'])
            if not re.fullmatch(_HASH, row['request_hash']) or row['operation'] not in ('grant', 'revoke', 'publish', 'file', 'file_revoke', 'accept'):
                raise ValueError('Invalid staff receipt')
            request = json.loads(row['request_json'])
            if request.get('request_id') != row['request_id'] or row['request_hash'] != _sha(canonical([row['operation'], row['target_id'], request])):
                raise ValueError('Staff command differs from its receipt')
            value = json.loads(row['result_json'])
            if not isinstance(value, dict) or 'portal_url' in value or value.get('link_available') is True:
                raise ValueError('Staff receipt contains invitation material')
            operation, target = row['operation'], row['target_id']
            identifier(target)
            if operation == 'grant':
                grant = grants[value['grant']['id']]
                principal = office.db.execute('SELECT * FROM business_portal_principals WHERE id=?', (grant['principal_id'],)).fetchone()
                expected = dict(id=grant['id'], recipient_name=principal['name'], recipient_email=principal['email'],
                    allow_upload=bool(grant['allow_upload']), created_at=grant['created_at'], expires_at=grant['expires_at'], status='active')
                if (value != dict(grant=expected, link_available=False) or
                        any(request[key] != grant[key] for key in ('project_id', 'customer_id')) or
                        request['allow_upload'] != bool(grant['allow_upload']) or
                        target != grant['project_id'] or row['user_id'] != grant['created_by'] or
                        text(request['recipient_name'], 'Name', 200, required=True) != principal['name'] or
                        text(request['recipient_email'], 'E-Mail', 254, required=True) != principal['email'] or
                        _at(grant['expires_at'])-_at(grant['created_at']) != timedelta(days=request['expires_in_days'])):
                    raise ValueError('Grant receipt differs from immutable grant')
            elif operation == 'publish':
                publication = api._row('publications', value['id'])
                if (value != api._publication(publication) or target != publication['project_id'] or
                        row['user_id'] != publication['created_by'] or request['project_id'] != target or
                        request['customer_id'] != publication['customer_id'] or
                        request['expected_revision']+1 != publication['revision'] or
                        any(text(request[key], key, 10000) != value[key] for key in ('title', 'description', 'status_label')) or
                        any(request[key] != value[key] for key in ('start_date', 'end_date'))):
                    raise ValueError('Publication receipt differs from immutable publication')
            elif operation in ('file', 'file_revoke'):
                file = api._row('files', value['id'])
                expected = api._file(file, staff=True)
                expected['status'] = 'published' if operation == 'file' else 'revoked'
                if value != expected:
                    raise ValueError('File receipt differs from immutable original')
                if operation == 'file':
                    if (target != file['project_id'] or row['user_id'] != file['created_by'] or
                            any(request[key] != file[key] for key in ('project_id', 'customer_id', 'source_kind', 'source_id')) or
                            request['source_sha256'] != file['sha256'] or text(request['title'], 'Titel', 300, required=True) != file['title']):
                        raise ValueError('Published file receipt differs from source')
                elif target != file['id'] or not office.db.execute('SELECT 1 FROM business_customer_file_revocations WHERE file_id=?', (target,)).fetchone():
                    raise ValueError('Missing file revocation receipt target')
            elif operation == 'accept':
                acceptance = office.db.execute('SELECT * FROM business_customer_acceptances WHERE upload_id=?', (target,)).fetchone()
                if acceptance is None or value != dict(acceptance) or request['classification'] != acceptance['classification']:
                    raise ValueError('Acceptance receipt differs from imported original')
            elif value.get('id') != target or value.get('status') != 'revoked' or not office.db.execute('SELECT 1 FROM business_customer_revocations WHERE grant_id=?', (target,)).fetchone():
                raise ValueError('Missing grant revocation receipt target')
            if operation not in ('revoke', 'file_revoke') and request.get('confirmation') is not True:
                raise ValueError('Missing original explicit confirmation')
        for row in office.db.execute('SELECT * FROM business_customer_revocations').fetchall():
            if row['grant_id'] not in grants or (row['revoked_by'] is None) != (row['kind'] == 'restore'):
                raise ValueError('Invalid customer revocation')
        for row in office.db.execute('SELECT * FROM business_customer_file_revocations').fetchall():
            api._row('files', row['file_id']); text(row['reason'], 'Grund', 500, required=True)
    except (Problem, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError('Invalid customer workspace history') from error
    return True


def methods(path):
    if path == '/customer-workspace':
        return 'GET'
    if path in ('/customer-workspace/grants', '/customer-workspace/publications', '/customer-workspace/files') or re.fullmatch(r'/customer-workspace/(?:grants|files)/'+_ID+r'/revoke', path) or re.fullmatch(r'/customer-workspace/uploads/'+_ID+r'/accept', path):
        return 'POST'
    if re.fullmatch(r'/customer-workspace/(?:files|uploads)/'+_ID+r'/content', path):
        return 'GET'
    if re.fullmatch(r'/customer-workspace/sources/(?:media|service_report|document)/'+_ID+r'/content', path):
        return 'GET'
    return None


def dispatch(office, actor, path, method, data):
    expected = methods(path)
    if expected is None:
        return None
    if method != expected:
        raise Problem(405, 'Methode nicht erlaubt')
    if not isinstance(data, dict):
        raise Problem(400, 'JSON-Objekt erwartet')
    query = data.get('_query', {})
    body = {key: value for key, value in data.items() if key != '_query'}
    api = CustomerWorkspace(office)
    if path == '/customer-workspace':
        if body or not isinstance(query, dict) or set(query) != {'project_id'} or not isinstance(query['project_id'], str):
            raise Problem(400, 'Genau ein Projektfilter erwartet')
        return api.view_staff(actor, query['project_id']), 200, 'application/json'
    if path.startswith('/customer-workspace/sources/'):
        if body or not isinstance(query, dict) or set(query) != {'project_id'} or not isinstance(query['project_id'], str):
            raise Problem(400, 'Genau ein Projektfilter erwartet')
        content, _, media_type = api.source_content(actor, query['project_id'], path.split('/')[3], path.split('/')[4])
        return content, 200, media_type
    if query or (method == 'GET' and body):
        raise Problem(400, 'Keine zusätzlichen Filter oder Abrufinhalte erlaubt')
    if path.endswith('/content'):
        content, _, media_type = api.staff_content(actor, path.split('/')[2], path.split('/')[3])
        return content, 200, media_type
    if path == '/customer-workspace/grants':
        result = api.create_grant(actor, body)
    elif path == '/customer-workspace/publications':
        result = api.publish(actor, body)
    elif path == '/customer-workspace/files':
        result = api.publish_file(actor, body)
    elif path.endswith('/accept'):
        result = api.accept_upload(actor, path.split('/')[3], body)
    elif path.split('/')[2] == 'grants':
        result = api.revoke_grant(actor, path.split('/')[3], body)
    else:
        result = api.revoke_file(actor, path.split('/')[3], body)
    return result, 201, 'application/json'
