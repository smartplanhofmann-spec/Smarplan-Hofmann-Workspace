"""Private personnel evidence and immutable monthly payroll preparation.

This module never calculates net wages, tax, social contributions or allowances.
Wage agreements are explicit documents, never inferred from project cost rates.
Every revision, original, receipt and exported month is retained append-only.
"""
import base64
import binascii
import calendar
import csv
import hashlib
import io
import json
import re
import uuid
from datetime import date, datetime, timezone
from xml.sax.saxutils import escape

from core import Problem, canonical
from business_foundation import _fresh, permissions, require_permission
from business_operations import identifier, iso_date, instant, text, transaction, _image_check
from workspace_api import BinaryAttachment

FEATURES = ('personnel_preparation',)
TABLES = ('business_personnel_files', 'business_personnel_events', 'business_personnel_requests')
MAX_FILE_BYTES = 600_000
ID = r'[a-f0-9]{32}'
KINDS = {'agreements': 'agreement', 'expenses': 'expense', 'payroll-preparations': 'preparation'}
EVENT_COLUMNS = 'id,kind,employee_id,revision,payload_json,content_hash,previous_hash,created_by,created_at,pdf_sha256,identity_key'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage')
    return [
        f'''CREATE TABLE IF NOT EXISTS business_personnel_files(
          id TEXT PRIMARY KEY,employee_id TEXT NOT NULL REFERENCES business_employees(id),
          purpose TEXT NOT NULL CHECK(purpose IN ('personnel','expense_receipt')),
          owner_visible INTEGER NOT NULL CHECK(owner_visible IN (0,1)),
          filename TEXT NOT NULL,media_type TEXT NOT NULL,size INTEGER NOT NULL CHECK(size>0),
          sha256 TEXT NOT NULL,content_hash TEXT NOT NULL,original {binary_type} NOT NULL,
          supersedes TEXT REFERENCES business_personnel_files(id),
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL)''',
        f'''CREATE TABLE IF NOT EXISTS business_personnel_events(
          id TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN ('agreement','expense','preparation')),
          employee_id TEXT NOT NULL REFERENCES business_employees(id),revision INTEGER NOT NULL CHECK(revision>0),
          payload_json TEXT NOT NULL,content_hash TEXT NOT NULL,previous_hash TEXT,
          created_by TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,
          pdf {binary_type},pdf_sha256 TEXT,identity_key TEXT,PRIMARY KEY(id,revision),UNIQUE(employee_id,identity_key))''',
        '''CREATE TABLE IF NOT EXISTS business_personnel_requests(
          user_id TEXT NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
          request_hash TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_personnel_employee ON business_personnel_events(employee_id,kind,id,revision)',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable personnel evidence'); END"
                  for table in TABLES for action in ('UPDATE', 'DELETE')]
        for table, condition in zip(TABLES, ('id=NEW.id', '(id=NEW.id AND revision=NEW.revision) OR '
                                             '(NEW.identity_key IS NOT NULL AND employee_id=NEW.employee_id AND identity_key=NEW.identity_key)',
                                             'user_id=NEW.user_id AND request_id=NEW.request_id')):
            result.append(f"CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} "
                          f"WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) "
                          "BEGIN SELECT RAISE(ABORT,'immutable personnel evidence'); END")
        return result
    if dialect == 'postgresql':
        result = ["""CREATE OR REPLACE FUNCTION business_personnel_immutable_guard()
          RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable personnel evidence'; END; $$"""]
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' "
                              f"AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} "
                              "FOR EACH ROW EXECUTE FUNCTION business_personnel_immutable_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


def _sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def _shape(data, allowed, required=()):
    if not isinstance(data, dict) or set(data) - set(allowed) or not set(required) <= set(data):
        raise Problem(400, 'Unvollständige oder unbekannte Felder im Personalvorgang.')


def _integer(value, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise Problem(400, 'Ganze Zahl im zulässigen Bereich erwartet.')
    return value


def _month(value):
    if not isinstance(value, str) or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', value):
        raise Problem(400, 'Abrechnungsmonat als JJJJ-MM erwartet.')
    year, month = map(int, value.split('-'))
    return value + '-01', value + '-' + str(calendar.monthrange(year, month)[1])


class PersonnelWorkflow:
    def __init__(self, office, *, clock=None):
        self.office, self.db = office, office.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def now(self):
        return self.clock().astimezone(timezone.utc).isoformat(timespec='seconds')

    def _employee(self, actor, employee_id=None, *, permission='personnel.read', own=False):
        fresh = _fresh(self.office, actor)
        if employee_id is None:
            row = self.db.execute('SELECT id FROM business_employees WHERE user_id=?', (fresh['id'],)).fetchone()
            if row is None:
                raise Problem(409, 'Für diesen Zugang ist kein Mitarbeiterprofil vorhanden.')
            employee_id = row['id']
        identifier(employee_id, 'Mitarbeiter-ID')
        employee = self.db.execute('SELECT * FROM business_employees WHERE id=?', (employee_id,)).fetchone()
        if employee is None:
            raise Problem(404, 'Mitarbeiter nicht verfügbar.')
        if own and employee['user_id'] == fresh['id'] and permission not in permissions(self.office, fresh):
            require_permission(self.office, fresh, 'time.own')
        else:
            require_permission(self.office, fresh, permission)
        return fresh, dict(employee)

    def _gate(self, actor):
        from business_schema import require_capability
        from business_organization import require_active
        require_capability(self.office, 'business_personnel_workflow')
        require_active(self.office, actor, '/personnel', 'business_personnel_workflow')

    def _command(self, actor, employee_id, permission, own, operation, data, callback):
        identifier(data.get('request_id'), 'Vorgangs-ID')
        fingerprint = _sha([operation, data])
        with transaction(self.office):
            fresh, employee = self._employee(actor, employee_id, permission=permission, own=own)
            self._gate(fresh)
            previous = self.db.execute('SELECT * FROM business_personnel_requests WHERE user_id=? AND request_id=?',
                                       (fresh['id'], data['request_id'])).fetchone()
            if previous:
                if previous['request_hash'] != fingerprint:
                    raise Problem(409, 'Diese Vorgangs-ID wurde bereits mit anderem Inhalt verwendet.')
                return json.loads(previous['result_json'])
            try:
                result = callback(fresh, employee)
            except Problem as error:
                # No receipt exists for this identity/body, and the transaction
                # rolls back any attempted change before this proof is returned.
                if error.status == 409:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise
            self.db.execute('INSERT INTO business_personnel_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                            (fresh['id'], data['request_id'], fingerprint, canonical(result)))
            self.office.audit(fresh, 'personnel.' + operation.split(':')[0], result.get('id', employee_id))
            return result

    def _latest(self, object_id, kind=None):
        identifier(object_id)
        row = self.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? ORDER BY revision DESC LIMIT 1',
                              (object_id,)).fetchone()
        if row is None or kind is not None and row['kind'] != kind:
            raise Problem(404, 'Personalvorgang nicht verfügbar.')
        return self._event(row)

    def _event(self, row):
        value = json.loads(row['payload_json'])
        envelope = dict(id=row['id'], kind=row['kind'], employee_id=row['employee_id'], revision=row['revision'],
                        payload=value, previous_hash=row['previous_hash'], created_by=row['created_by'], created_at=row['created_at'], pdf_sha256=row['pdf_sha256'], identity_key=row['identity_key'])
        if _sha(envelope) != row['content_hash']:
            raise Problem(500, 'Integritätsprüfung der Personalhistorie fehlgeschlagen.')
        return dict(value, **{key: row[key] for key in ('id','kind','employee_id','revision','content_hash','previous_hash','created_by','created_at','pdf_sha256')})

    def _append(self, actor, kind, employee_id, payload, previous=None, pdf=None):
        object_id = previous['id'] if previous else uuid.uuid4().hex
        revision = previous['revision'] + 1 if previous else 1
        stamp = self.now()
        prior = previous['content_hash'] if previous else None
        pdf_hash = _sha(pdf) if pdf else None
        identity_key = None if previous or kind == 'expense' else kind + ':' + payload['effective_from' if kind == 'agreement' else 'month']
        envelope = dict(id=object_id, kind=kind, employee_id=employee_id, revision=revision, payload=payload,
                        previous_hash=prior, created_by=actor['id'], created_at=stamp, pdf_sha256=pdf_hash, identity_key=identity_key)
        self.db.execute('INSERT INTO business_personnel_events(id,kind,employee_id,revision,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256,identity_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (object_id, kind, employee_id, revision, canonical(payload), _sha(envelope), prior, actor['id'], stamp, pdf, pdf_hash, identity_key))
        return self._latest(object_id, kind)

    def _all(self, kind, employee_id):
        rows = self.db.execute('SELECT ' + ','.join('e.' + name for name in EVENT_COLUMNS.split(',')) +
            ' FROM business_personnel_events e WHERE e.kind=? AND e.employee_id=? AND NOT EXISTS '
            '(SELECT 1 FROM business_personnel_events n WHERE n.id=e.id AND n.revision>e.revision) ORDER BY e.created_at,e.id',
            (kind, employee_id)).fetchall()
        return [self._event(row) for row in rows]

    def list_records(self, actor, kind, query=None):
        query = query or {}
        _shape(query, ('employee_id',))
        with transaction(self.office):
            _, employee = self._employee(actor, query.get('employee_id'), own=True)
            return dict(employee_id=employee['id'], employee_name=employee['name'], items=self._all(kind, employee['id']))

    def get(self, actor, kind, object_id, history=False):
        with transaction(self.office):
            latest = self._latest(object_id, kind)
            self._employee(actor, latest['employee_id'], own=True)
            if history:
                rows = self.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? ORDER BY revision', (object_id,)).fetchall()
                return dict(items=[self._event(row) for row in rows])
            return latest

    def _file(self, file_id, employee_id=None):
        identifier(file_id, 'Datei-ID')
        row = self.db.execute('SELECT * FROM business_personnel_files WHERE id=?', (file_id,)).fetchone()
        if row is None or employee_id is not None and row['employee_id'] != employee_id:
            raise Problem(404, 'Personaldatei nicht verfügbar.')
        original = bytes(row['original'])
        metadata = {key: row[key] for key in row.keys() if key not in ('original','content_hash')}
        if len(original) != row['size'] or _sha(original) != row['sha256'] or _sha(metadata) != row['content_hash']:
            raise Problem(500, 'Integritätsprüfung des Personaloriginals fehlgeschlagen.')
        return dict(row)

    @staticmethod
    def _file_view(row):
        return {key: row[key] for key in ('id','employee_id','purpose','owner_visible','filename','media_type','size','sha256','content_hash','supersedes','created_by','created_at')}

    def files(self, actor, query=None):
        query = query or {}
        _shape(query, ('employee_id',))
        with transaction(self.office):
            fresh, employee = self._employee(actor, query.get('employee_id'), own=True)
            private = 'personnel.read' in permissions(self.office, fresh)
            columns = 'id,employee_id,purpose,owner_visible,filename,media_type,size,sha256,content_hash,supersedes,created_by,created_at'
            rows = self.db.execute('SELECT ' + columns + ' FROM business_personnel_files WHERE employee_id=? ORDER BY created_at,id', (employee['id'],)).fetchall()
            items = []
            for row in rows:
                if private or row['owner_visible']:
                    if _sha({key: row[key] for key in row.keys() if key != 'content_hash'}) != row['content_hash']:
                        raise Problem(500, 'Integritätsprüfung der Personalaktenliste fehlgeschlagen.')
                    items.append(dict(row))
            return dict(employee_id=employee['id'], items=items)

    def upload(self, actor, data):
        _shape(data, ('request_id','employee_id','purpose','owner_visible','filename','media_type','content_base64','supersedes'),
               ('request_id','employee_id','purpose','owner_visible','filename','media_type','content_base64'))
        purpose = data['purpose']
        if purpose not in ('personnel','expense_receipt') or type(data['owner_visible']) is not bool:
            raise Problem(400, 'Dateizweck und Sichtbarkeit angeben.')
        if purpose == 'expense_receipt' and not data['owner_visible']:
            raise Problem(400, 'Eigene Auslagenbelege müssen für den Mitarbeiter sichtbar bleiben.')
        filename = text(data['filename'], 'Dateiname', 180, required=True)
        if any(c in filename for c in '/\\\r\n\x00') or data['media_type'] not in ('application/pdf','image/png','image/jpeg'):
            raise Problem(400, 'PDF, PNG oder JPEG mit sicherem Dateinamen erwartet.')
        encoded = data['content_base64']
        if not isinstance(encoded, str) or len(encoded) > MAX_FILE_BYTES * 4 // 3 + 4:
            raise Problem(413, 'Ein Personaloriginal darf höchstens 600 kB groß sein.')
        try:
            original = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise Problem(400, 'Ungültige Dateikodierung.') from None
        if not 1 <= len(original) <= MAX_FILE_BYTES:
            raise Problem(413, 'Ein Personaloriginal darf höchstens 600 kB groß sein.')
        _image_check(original, data['media_type'])
        def save(fresh, employee):
            supersedes = data.get('supersedes')
            if supersedes is not None:
                previous = self._file(supersedes, employee['id'])
                if previous['purpose'] != purpose:
                    raise Problem(400, 'Die neue Datei muss denselben Aktenzweck haben.')
            object_id = uuid.uuid4().hex
            metadata = dict(id=object_id, employee_id=employee['id'], purpose=purpose, owner_visible=int(data['owner_visible']),
                            filename=filename, media_type=data['media_type'], size=len(original), sha256=_sha(original),
                            supersedes=supersedes, created_by=fresh['id'], created_at=self.now())
            columns = tuple(metadata)
            self.db.execute('INSERT INTO business_personnel_files(' + ','.join(columns) + ',content_hash,original) VALUES(' + ','.join('?' for _ in range(len(columns)+2)) + ')',
                            tuple(metadata.values()) + (_sha(metadata), original))
            return self._file_view(self._file(object_id))
        return self._command(actor, data['employee_id'], 'personnel.write', purpose == 'expense_receipt', 'file.upload', data, save)

    def file_content(self, actor, file_id):
        with transaction(self.office):
            row = self._file(file_id)
            self._employee(actor, row['employee_id'], own=bool(row['owner_visible']))
            self.office.audit(_fresh(self.office, actor), 'personnel.file.downloaded', file_id)
            return BinaryAttachment(row['original'], row['filename']), row['media_type']

    def save_agreement(self, actor, data):
        allowed = ('request_id','employee_id','id','revision','effective_from','employment_kind','pay_basis','amount_minor','currency','reference_file_id','notes','correction_reason')
        _shape(data, allowed, ('request_id','employee_id','revision','effective_from','employment_kind','pay_basis','amount_minor','currency','reference_file_id'))
        if 'id' in data:
            identifier(data['id'])
        if data['employment_kind'] not in ('regular','minijob') or data['pay_basis'] not in ('monthly','hourly') or data['currency'] != 'EUR':
            raise Problem(400, 'Reguläre Beschäftigung oder Minijob und eine ausdrückliche EUR-Entgeltvereinbarung erwartet.')
        payload = dict(effective_from=iso_date(data['effective_from']), employment_kind=data['employment_kind'],
                       pay_basis=data['pay_basis'], amount_minor=_integer(data['amount_minor'], 1), currency='EUR',
                       reference_file_id=identifier(data['reference_file_id']), notes=text(data.get('notes',''), 'Notiz', 2000),
                       correction_reason=text(data.get('correction_reason',''), 'Korrekturgrund', 1000))
        def save(fresh, employee):
            previous = self._latest(data['id'], 'agreement') if data.get('id') else None
            if previous and previous['employee_id'] != employee['id']:
                raise Problem(404, 'Entgeltvereinbarung nicht verfügbar.')
            if _integer(data['revision']) != (previous['revision'] if previous else 0):
                raise Problem(409, 'Entgeltvereinbarung wurde geändert. Bitte neu laden.')
            if previous and (not payload['correction_reason'] or payload['effective_from'] != previous['effective_from']):
                raise Problem(400, 'Korrekturgrund angeben; ein neuer Gültigkeitsbeginn benötigt eine neue Vereinbarung.')
            if any(item['effective_from'] == payload['effective_from'] and (not previous or item['id'] != previous['id']) for item in self._all('agreement', employee['id'])):
                raise Problem(409, 'Für dieses Gültigkeitsdatum besteht bereits eine Entgeltvereinbarung.')
            file = self._file(payload['reference_file_id'], employee['id'])
            if file['purpose'] != 'personnel':
                raise Problem(400, 'Eine Entgeltvereinbarung benötigt ein Personalaktenoriginal.')
            return self._append(fresh, 'agreement', employee['id'], dict(payload, reference_sha256=file['sha256']), previous)
        return self._command(actor, data['employee_id'], 'personnel.write', False, 'agreement.saved', data, save)

    def _expense_payload(self, data, employee_id):
        start, end = iso_date(data['start_date']), iso_date(data['end_date'])
        if end < start or (date.fromisoformat(end)-date.fromisoformat(start)).days > 366:
            raise Problem(400, 'Gültigen Reisezeitraum bis 366 Tage angeben.')
        if not isinstance(data['items'], list) or not 1 <= len(data['items']) <= 100:
            raise Problem(400, 'Eine bis 100 belegte Auslagen angeben.')
        items, files = [], set()
        for item in data['items']:
            _shape(item, ('date','description','amount_minor','currency','receipt_file_id','project_id'),
                   ('date','description','amount_minor','currency','receipt_file_id'))
            day = iso_date(item['date'])
            if item['currency'] != 'EUR':
                raise Problem(400, 'Tatsächlichen EUR-Auslagenbetrag angeben.')
            file = self._file(item['receipt_file_id'], employee_id)
            if file['purpose'] != 'expense_receipt' or file['sha256'] in files:
                raise Problem(400, 'Jedes Auslagenoriginal genau einmal zuordnen.')
            files.add(file['sha256'])
            project_id = item.get('project_id')
            if project_id is not None:
                identifier(project_id, 'Projekt-ID')
                if self.db.execute('SELECT id FROM projects WHERE id=?', (project_id,)).fetchone() is None:
                    raise Problem(404, 'Projekt nicht verfügbar.')
            items.append(dict(date=day, description=text(item['description'], 'Auslage', 500, required=True),
                              amount_minor=_integer(item['amount_minor'], 1), currency='EUR',
                              receipt_file_id=file['id'], receipt_sha256=file['sha256'], project_id=project_id))
        return dict(purpose=text(data['purpose'], 'Reisezweck', 1000, required=True), start_date=start, end_date=end,
                    items=items, total_minor=sum(item['amount_minor'] for item in items), currency='EUR',
                    allowance_calculation=False, tax_treatment='not_determined')

    def save_expense(self, actor, data):
        _shape(data, ('request_id','employee_id','id','revision','purpose','start_date','end_date','items','correction_reason'),
               ('request_id','employee_id','revision','purpose','start_date','end_date','items'))
        if 'id' in data:
            identifier(data['id'])
        def save(fresh, employee):
            previous = self._latest(data['id'], 'expense') if data.get('id') else None
            if previous and previous['employee_id'] != employee['id']:
                raise Problem(404, 'Reisekostenantrag nicht verfügbar.')
            if _integer(data['revision']) != (previous['revision'] if previous else 0):
                raise Problem(409, 'Reisekostenantrag wurde geändert. Bitte neu laden.')
            if previous and previous['status'] not in ('draft','rejected','approved','reversed'):
                raise Problem(409, 'Eingereichte Anträge zuerst zurückweisen; erstattete Anträge benötigen eine bestätigte Rückzahlung.')
            if previous:
                from payroll_travel_expenses_2026 import ensure_expense_unreserved
                ensure_expense_unreserved(self.office,previous)
            reason = text(data.get('correction_reason',''), 'Korrekturgrund', 1000, required=bool(previous))
            payload = self._expense_payload(data, employee['id'])
            for item in payload['items']:
                if item['project_id'] is not None and employee['user_id'] == fresh['id']:
                    self.office.project(fresh, item['project_id'])
            payload.update(status='draft', correction_reason=reason, payments=previous['payments'] if previous else [],
                           decision=None, submitted_by=None, submitted_at=None)
            return self._append(fresh, 'expense', employee['id'], payload, previous)
        return self._command(actor, data['employee_id'], 'personnel.write', True, 'expense.saved', data, save)

    def expense_action(self, actor, object_id, action, data):
        fields = {'submit': (), 'approve': ('reason',), 'reject': ('reason',),
                  'reimburse': ('payment_reference','paid_on','amount_minor','confirmed'),
                  'reverse-reimbursement': ('payment_reference','paid_on','amount_minor','confirmed')}
        if action not in fields:
            raise Problem(404, 'Unbekannter Reisekostenvorgang.')
        allowed = ('request_id','revision') + fields[action]
        _shape(data, allowed, allowed)
        with transaction(self.office):
            initial = self._latest(object_id, 'expense')
            self._employee(actor, initial['employee_id'], permission='personnel.approve' if action != 'submit' else 'personnel.write', own=action == 'submit')
        def change(fresh, employee):
            previous = self._latest(object_id, 'expense')
            if _integer(data['revision']) != previous['revision']:
                raise Problem(409, 'Reisekostenantrag wurde geändert. Bitte neu laden.')
            payload = {key: value for key, value in previous.items() if key not in EVENT_COLUMNS.split(',') and key != 'kind'}
            if action == 'submit':
                if previous['status'] != 'draft':
                    raise Problem(409, 'Nur ein Entwurf kann eingereicht werden.')
                # A receipt may not fund two currently submitted/approved claims.
                current_files = {item['receipt_sha256'] for item in previous['items']}
                for other in self._all('expense', employee['id']):
                    if other['id'] != object_id and other['status'] in ('submitted','approved','reimbursed') and current_files & {item['receipt_sha256'] for item in other['items']}:
                        raise Problem(409, 'Ein Beleg ist bereits einem eingereichten oder erstatteten Antrag zugeordnet.')
                payload.update(status='submitted', submitted_by=fresh['id'], submitted_at=self.now())
            elif action in ('approve','reject'):
                if previous['status'] != 'submitted':
                    raise Problem(409, 'Nur eingereichte Anträge können geprüft werden.')
                if employee['user_id'] == fresh['id'] or previous['submitted_by'] == fresh['id']:
                    raise Problem(403, 'Ein eigener oder selbst eingereichter Antrag benötigt eine andere prüfende Person.')
                reason = text(data.get('reason',''), 'Prüfvermerk', 1000, required=True)
                payload.update(status='approved' if action == 'approve' else 'rejected', decision=dict(by=fresh['id'], at=self.now(), reason=reason))
            elif action in ('reimburse','reverse-reimbursement'):
                if action=='reimburse':
                    from payroll_travel_expenses_2026 import ensure_expense_unreserved
                    ensure_expense_unreserved(self.office,previous)
                expected = 'approved' if action == 'reimburse' else 'reimbursed'
                if previous['status'] != expected:
                    raise Problem(409, 'Für diese Zahlungsbestätigung ist der Antragsstatus ungeeignet.')
                if data.get('confirmed') is not True or _integer(data.get('amount_minor'), 1) != previous['total_minor']:
                    raise Problem(400, 'Den tatsächlich vollständig gezahlten Betrag ausdrücklich bestätigen.')
                paid_on = iso_date(data.get('paid_on'))
                if paid_on > self.now()[:10]:
                    raise Problem(400, 'Eine ausgeführte Zahlung darf nicht in der Zukunft liegen.')
                reference = text(data.get('payment_reference'), 'Zahlungsreferenz', 250, required=True)
                if any(payment['reference'] == reference for expense in self._all('expense', employee['id']) for payment in expense['payments']):
                    raise Problem(409, 'Diese Zahlungsreferenz wurde bereits bestätigt.')
                payment = dict(kind='reimbursement' if action == 'reimburse' else 'repayment', reference=reference,
                               paid_on=paid_on, amount_minor=previous['total_minor'], confirmed_by=fresh['id'], confirmed_at=self.now())
                payload.update(status='reimbursed' if action == 'reimburse' else 'reversed', payments=previous['payments'] + [payment])
            else:
                raise Problem(404, 'Unbekannter Reisekostenvorgang.')
            return self._append(fresh, 'expense', employee['id'], payload, previous)
        return self._command(actor, initial['employee_id'], 'personnel.approve' if action != 'submit' else 'personnel.write', action == 'submit', 'expense.' + action + ':' + object_id, data, change)

    def _snapshot(self, employee, month):
        from business_time import TimeTracking
        first, last = _month(month)
        agreements = sorted((item for item in self._all('agreement', employee['id']) if item['effective_from'] <= last), key=lambda item: item['effective_from'])
        applicable = [item for item in agreements if item['effective_from'] <= first]
        if not applicable:
            # A new employee may legitimately begin during the month.
            start = max(first, employee['employment_from'] or first)
            applicable = [item for item in agreements if item['effective_from'] <= start]
        if not applicable:
            raise Problem(409, 'Eine belegte Entgeltvereinbarung zum Beschäftigungsbeginn im Monat fehlt.')
        agreements = [applicable[-1]] + [item for item in agreements if item['effective_from'] > applicable[-1]['effective_from']]
        active = self.db.execute("SELECT 1 FROM business_time_entries WHERE employee_id=? AND status<>'stopped' AND substr(started_at,1,10)<=?", (employee['id'], last)).fetchone()
        if active:
            raise Problem(409, 'Laufende Zeiterfassungen vor dem Monatsabschluss beenden.')
        rows = self.db.execute('SELECT * FROM business_time_days WHERE employee_id=? AND work_date>=? AND work_date<=? ORDER BY work_date', (employee['id'],first,last)).fetchall()
        if any(row['status'] != 'approved' for row in rows):
            raise Problem(409, 'Alle erfassten Arbeitstage im Monat müssen freigegeben sein.')
        time = TimeTracking(self.office, clock=self.clock)
        days = [time._day(employee, row['work_date']) for row in rows]
        corrections = [dict(row) for row in self.db.execute('SELECT c.* FROM business_time_corrections c JOIN business_time_entries e ON e.id=c.entry_id WHERE e.employee_id=? AND c.work_date>=? AND c.work_date<=? ORDER BY c.work_date,c.id', (employee['id'],first,last)).fetchall()]
        absences = [dict(row) for row in self.db.execute('SELECT * FROM business_absences WHERE employee_id=? AND start_date<=? AND end_date>=? ORDER BY start_date,id', (employee['id'],last,first)).fetchall()]
        if any(item['status'] == 'pending' for item in absences):
            raise Problem(409, 'Offene Abwesenheitsanträge vor dem Monatsabschluss prüfen.')
        # Medical free text is unnecessary for payroll preparation.
        absences = [{key: value for key, value in item.items() if key != 'details'} for item in absences if item['status'] == 'approved']
        expenses = [item for item in self._all('expense', employee['id']) if item['end_date'][:7] == month]
        if any(item['status'] in ('draft','submitted') for item in expenses):
            raise Problem(409, 'Offene Reisekosten des Monats vor dem Abschluss prüfen.')
        expenses = [item for item in expenses if item['status'] in ('approved','reimbursed','reversed')]
        return dict(schema_version=1, month=month, employee={key: employee[key] for key in ('id','user_id','name','employment_from','employment_to','revision')},
                    agreements=agreements, approved_days=days, corrections=corrections, approved_absences=absences, expenses=expenses,
                    net_work_seconds=sum(item['net_seconds'] for item in days),
                    recorded_expenses_minor=sum(item['total_minor'] for item in expenses if item['status'] != 'reversed'),
                    currency='EUR', payroll_calculated=False, tax_treatment='not_determined',
                    scope='recorded_and_approved_sources', allowance_calculation=False)

    def preview(self, actor, query):
        _shape(query, ('employee_id','month'), ('employee_id','month'))
        with transaction(self.office):
            _, employee = self._employee(actor, query['employee_id'])
            snapshot = self._snapshot(employee, query['month'])
            return dict(snapshot=snapshot, source_hash=_sha(snapshot))

    def close_preparation(self, actor, data):
        _shape(data, ('request_id','employee_id','month','source_hash','revision','id','completeness_confirmed','correction_reason'),
               ('request_id','employee_id','month','source_hash','revision','completeness_confirmed'))
        if 'id' in data:
            identifier(data['id'])
        if data['completeness_confirmed'] is not True or not isinstance(data['source_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', data['source_hash']):
            raise Problem(400, 'Geprüfte Vorschau und ausdrückliche Vollständigkeitsbestätigung erforderlich.')
        identifier(data['request_id'], 'Vorgangs-ID')
        # Authenticate before replay; the committed response survives later source changes.
        with transaction(self.office):
            fresh, _ = self._employee(actor, data['employee_id'], permission='personnel.approve')
            self._employee(fresh, data['employee_id'])
            self._gate(fresh)
            prior = self.db.execute('SELECT * FROM business_personnel_requests WHERE user_id=? AND request_id=?', (fresh['id'], data['request_id'])).fetchone()
            if prior:
                if prior['request_hash'] != _sha(['preparation.closed', data]):
                    raise Problem(409, 'Diese Vorgangs-ID wurde bereits mit anderem Inhalt verwendet.')
                return json.loads(prior['result_json'])
        # Render bounded, non-provider output outside the Office transaction.
        try:
            prepared = self.preview(actor, {'employee_id': data['employee_id'], 'month': data['month']})
        except Problem as error:
            if error.status != 409:
                raise
            def rejected(fresh, employee):
                raise Problem(409, error.message)
            return self._command(actor, data['employee_id'], 'personnel.approve', False, 'preparation.closed', data, rejected)
        if prepared['source_hash'] != data['source_hash']:
            def stale(fresh, employee):
                raise Problem(409, 'Die Monatsquellen wurden geändert. Vorschau neu laden.')
            return self._command(actor, data['employee_id'], 'personnel.approve', False, 'preparation.closed', data, stale)
        pdf = _render_preparation(prepared['snapshot'], prepared['source_hash'])
        def close(fresh, employee):
            snapshot = self._snapshot(employee, data['month'])
            if _sha(snapshot) != data['source_hash']:
                raise Problem(409, 'Die Monatsquellen wurden während des Abschlusses geändert.')
            previous = self._latest(data['id'], 'preparation') if data.get('id') else None
            if previous and (previous['employee_id'] != employee['id'] or previous['month'] != data['month']):
                raise Problem(404, 'Monatsabschluss nicht verfügbar.')
            if _integer(data['revision']) != (previous['revision'] if previous else 0):
                raise Problem(409, 'Der Monatsabschluss wurde geändert.')
            if not previous and any(item['month'] == data['month'] for item in self._all('preparation', employee['id'])):
                raise Problem(409, 'Der Monat ist bereits abgeschlossen. Eine begründete Korrekturversion anlegen.')
            reason = text(data.get('correction_reason',''), 'Korrekturgrund', 1000, required=bool(previous))
            payload = dict(month=data['month'], snapshot=snapshot, source_hash=data['source_hash'],
                           completeness_confirmed=True, correction_reason=reason, status='preparation_closed',
                           payroll_calculated=False, transmission_status='not_transmitted')
            return self._append(fresh, 'preparation', employee['id'], payload, previous, pdf)
        return self._command(actor, data['employee_id'], 'personnel.approve', False, 'preparation.closed', data, close)

    def export(self, actor, object_id, kind, revision=None):
        with transaction(self.office):
            latest = self._latest(object_id, 'preparation')
            self._employee(actor, latest['employee_id'], permission='personnel.export')
            self._employee(actor, latest['employee_id'])
            if revision is not None:
                try:
                    number = int(revision)
                except (ValueError, TypeError):
                    raise Problem(400, 'Gültige Exportversion erwartet.') from None
                row = self.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? AND revision=?', (object_id,number)).fetchone()
                if row is None:
                    raise Problem(404, 'Abschlussversion nicht verfügbar.')
                latest = self._event(row)
            self.office.audit(_fresh(self.office, actor), 'personnel.preparation.exported', object_id + ':' + str(latest['revision']))
            filename = 'lohnvorbereitung-' + latest['month'] + '-v' + str(latest['revision'])
            if kind == 'pdf':
                row = self.db.execute('SELECT pdf,pdf_sha256 FROM business_personnel_events WHERE id=? AND revision=?', (object_id, latest['revision'])).fetchone()
                content = bytes(row['pdf'])
                if _sha(content) != row['pdf_sha256']:
                    raise Problem(500, 'Integritätsprüfung des Monats-PDF fehlgeschlagen.')
                return BinaryAttachment(content, filename + '.pdf'), 'application/pdf'
            if kind == 'json':
                return BinaryAttachment(canonical(latest).encode(), filename + '.json'), 'application/json; charset=utf-8'
            return BinaryAttachment(_csv(latest), filename + '.csv'), 'text/csv; charset=utf-8'


def _csv(value):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\r\n')
    writer.writerow(['Lohnvorbereitung; keine Lohnabrechnung', 'Monat', 'Mitarbeiter-ID', 'Quellen-SHA256'])
    writer.writerow(['Abschluss', value['month'], value['employee_id'], value['source_hash']])
    writer.writerow(['Quelle', 'Datum', 'Sekunden', 'Cent', 'Referenz'])
    snapshot = value['snapshot']
    for day in snapshot['approved_days']:
        writer.writerow(['Freigegebene Zeit', day['date'], day['net_seconds'], '', 'Revision ' + str(day['revision'])])
    for agreement in snapshot['agreements']:
        writer.writerow(['Entgeltvereinbarung ' + agreement['pay_basis'], agreement['effective_from'], '', agreement['amount_minor'], agreement['id']])
    for absence in snapshot['approved_absences']:
        writer.writerow(['Abwesenheit ' + absence['kind'], absence['start_date'] + '/' + absence['end_date'], '', '', absence['id']])
    for expense in snapshot['expenses']:
        writer.writerow(['Auslagen ' + expense['status'], expense['end_date'], '', expense['total_minor'], expense['id']])
        for payment in expense['payments']:
            # Prefix spreadsheet-sensitive free text, including whitespace/control variants.
            reference = payment['reference']
            if reference.lstrip().startswith(('=','+','-','@')):
                reference = "'" + reference
            writer.writerow([payment['kind'], payment['paid_on'], '', payment['amount_minor'], reference])
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def _render_preparation(snapshot, source_hash):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    stream = io.BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph('Lohnvorbereitung ' + snapshot['month'], styles['Title'])]
    def line(value):
        story.append(Paragraph(escape(str(value)), styles['Normal']))
        story.append(Spacer(1, 5))
    line(snapshot['employee']['name'])
    line('Vorbereitungsunterlagen. Keine Brutto-Netto-Abrechnung, Steuerberechnung oder amtliche Meldung.')
    line('Quellen-SHA256: ' + source_hash)
    line('Freigegebene Arbeitszeit: ' + str(snapshot['net_work_seconds']) + ' Sekunden')
    for item in snapshot['agreements']:
        line('Entgeltvereinbarung ab ' + item['effective_from'] + ': ' + str(item['amount_minor']) + ' Cent EUR / ' + item['pay_basis'] + '; Original ' + item['reference_file_id'])
    for item in snapshot['approved_days']:
        line('Zeit ' + item['date'] + ': ' + str(item['net_seconds']) + ' Sekunden; Revision ' + str(item['revision']))
    for item in snapshot['approved_absences']:
        line('Freigegebene Abwesenheit ' + item['start_date'] + ' bis ' + item['end_date'] + ': ' + item['kind'])
    for item in snapshot['expenses']:
        line('Belegte Auslagen ' + item['purpose'] + ': ' + str(item['total_minor']) + ' Cent EUR; ' + item['status'])
        for payment in item['payments']:
            line(payment['kind'] + ' am ' + payment['paid_on'] + ': ' + str(payment['amount_minor']) + ' Cent; Referenz ' + payment['reference'])
    SimpleDocTemplate(stream, pageCompression=0).build(story)
    return stream.getvalue()


def validate_integrity(office):
    api = PersonnelWorkflow(office)
    try:
        for row in office.db.execute('SELECT id FROM business_personnel_files').fetchall():
            file = api._file(row['id'])
            if file['supersedes']:
                prior = api._file(file['supersedes'], file['employee_id'])
                if prior['purpose'] != file['purpose']:
                    raise ValueError('Invalid file successor')
            if file['size'] > MAX_FILE_BYTES or file['purpose'] not in ('personnel','expense_receipt') or file['media_type'] not in ('application/pdf','image/png','image/jpeg'):
                raise ValueError('Invalid personnel file metadata')
        prior = {}
        for row in office.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events ORDER BY id,revision').fetchall():
            value = api._event(row)
            instant(row['created_at'])
            previous = prior.get(row['id'])
            if row['revision'] != (previous['revision']+1 if previous else 1) or row['previous_hash'] != (previous['content_hash'] if previous else None):
                raise ValueError('Incomplete personnel event chain')
            if previous and any(row[key] != previous[key] for key in ('kind','employee_id')):
                raise ValueError('Changed personnel identity')
            expected_key = None if previous or row['kind'] == 'expense' else row['kind'] + ':' + value['effective_from' if row['kind'] == 'agreement' else 'month']
            if row['identity_key'] != expected_key:
                raise ValueError('Changed personnel period identity')
            if row['kind'] == 'agreement':
                file = api._file(value['reference_file_id'], row['employee_id'])
                if file['sha256'] != value['reference_sha256'] or file['purpose'] != 'personnel':
                    raise ValueError('Changed agreement original')
                _integer(value['amount_minor'], 1)
                iso_date(value['effective_from'])
                if value['pay_basis'] not in ('monthly','hourly') or value['employment_kind'] not in ('regular','minijob') or value['currency'] != 'EUR':
                    raise ValueError('Invalid wage agreement')
                if previous:
                    old = api._event(previous)
                    if old['effective_from'] != value['effective_from'] or not value['correction_reason']:
                        raise ValueError('Invalid agreement correction')
            elif row['kind'] == 'expense':
                total = 0
                for item in value['items']:
                    file = api._file(item['receipt_file_id'], row['employee_id'])
                    if file['sha256'] != item['receipt_sha256'] or file['purpose'] != 'expense_receipt':
                        raise ValueError('Changed expense original')
                    total += _integer(item['amount_minor'], 1)
                if total != value['total_minor'] or value['currency'] != 'EUR':
                    raise ValueError('Invalid expense total')
                if value['allowance_calculation'] is not False or value['tax_treatment'] != 'not_determined':
                    raise ValueError('Unexpected expense tax computation')
                start, end = iso_date(value['start_date']), iso_date(value['end_date'])
                if end < start or (date.fromisoformat(end)-date.fromisoformat(start)).days > 366:
                    raise ValueError('Invalid expense period')
                hashes = set()
                for item in value['items']:
                    iso_date(item['date'])
                    if item['currency'] != 'EUR' or item['receipt_sha256'] in hashes:
                        raise ValueError('Invalid expense item')
                    hashes.add(item['receipt_sha256'])
                _validate_expense_transition(value, api._event(previous) if previous else None,
                    office.db.execute('SELECT user_id FROM business_employees WHERE id=?', (row['employee_id'],)).fetchone()['user_id'])
            else:
                if _sha(value['snapshot']) != value['source_hash'] or value['snapshot']['employee']['id'] != row['employee_id'] or value['snapshot']['month'] != value['month']:
                    raise ValueError('Changed monthly snapshot')
                snapshot = value['snapshot']
                first, last = _month(value['month'])
                if (value['payroll_calculated'] is not False or value['transmission_status'] != 'not_transmitted'
                        or snapshot['payroll_calculated'] is not False or snapshot['allowance_calculation'] is not False
                        or snapshot['tax_treatment'] != 'not_determined' or value['status'] != 'preparation_closed'
                        or value['completeness_confirmed'] is not True or snapshot['currency'] != 'EUR'):
                    raise ValueError('Unexpected payroll calculation or transmission')
                if previous and (api._event(previous)['month'] != value['month'] or not value['correction_reason']):
                    raise ValueError('Invalid monthly correction')
                actual_employee = office.db.execute('SELECT user_id FROM business_employees WHERE id=?', (row['employee_id'],)).fetchone()
                if snapshot['employee']['user_id'] != actual_employee['user_id']:
                    raise ValueError('Changed monthly employee identity')
                for day in snapshot['approved_days']:
                    if day['employee_id'] != row['employee_id'] or not first <= iso_date(day['date']) <= last or day['status'] != 'approved':
                        raise ValueError('Foreign or unapproved monthly work day')
                for correction in snapshot['corrections']:
                    entry = office.db.execute('SELECT employee_id FROM business_time_entries WHERE id=?', (correction['entry_id'],)).fetchone()
                    if entry is None or entry['employee_id'] != row['employee_id'] or not first <= iso_date(correction['work_date']) <= last:
                        raise ValueError('Foreign monthly time correction')
                for absence in snapshot['approved_absences']:
                    if absence['employee_id'] != row['employee_id'] or absence['status'] != 'approved' or iso_date(absence['start_date']) > last or iso_date(absence['end_date']) < first or 'details' in absence:
                        raise ValueError('Foreign or unapproved monthly absence')
                if snapshot['net_work_seconds'] != sum(day['net_seconds'] for day in snapshot['approved_days']):
                    raise ValueError('Changed monthly time total')
                if snapshot['recorded_expenses_minor'] != sum(expense['total_minor'] for expense in snapshot['expenses'] if expense['status'] != 'reversed'):
                    raise ValueError('Changed monthly expense total')
                pdf = office.db.execute('SELECT pdf FROM business_personnel_events WHERE id=? AND revision=?', (row['id'],row['revision'])).fetchone()['pdf']
                if not pdf or _sha(bytes(pdf)) != row['pdf_sha256']:
                    raise ValueError('Changed preparation PDF')
                for category in ('agreements','expenses'):
                    for source in value['snapshot'][category]:
                        archived = office.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? AND revision=?', (source['id'],source['revision'])).fetchone()
                        if (archived is None or api._event(archived) != source or archived['employee_id'] != row['employee_id']
                                or archived['kind'] != ('agreement' if category == 'agreements' else 'expense')):
                            raise ValueError('Missing monthly source')
                        if category == 'agreements' and source['effective_from'] > last or category == 'expenses' and (source['end_date'][:7] != value['month'] or source['status'] not in ('approved','reimbursed','reversed')):
                            raise ValueError('Invalid monthly source period')
                agreements = snapshot['agreements']
                start = max(first, snapshot['employee']['employment_from'] or first)
                if not agreements or agreements[0]['effective_from'] > start or len({item['effective_from'] for item in agreements}) != len(agreements):
                    raise ValueError('Missing or ambiguous monthly wage agreement')
            prior[row['id']] = dict(row)
        for row in office.db.execute('SELECT * FROM business_personnel_requests').fetchall():
            identifier(row['request_id'])
            value = json.loads(row['result_json'])
            if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']):
                raise ValueError('Invalid personnel request hash')
            if value.get('kind') in ('agreement','expense','preparation'):
                archived = office.db.execute('SELECT ' + EVENT_COLUMNS + ' FROM business_personnel_events WHERE id=? AND revision=?', (value['id'],value['revision'])).fetchone()
                if archived is None or api._event(archived) != value:
                    raise ValueError('Changed personnel receipt')
            elif api._file_view(api._file(value['id'])) != value:
                raise ValueError('Changed file receipt')
    except (Problem, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid personnel workflow archive') from error
    return True


def _validate_expense_transition(value, previous, employee_user_id):
    status = value['status']
    allowed = {'draft': ('draft','rejected','approved','reversed'), 'submitted': ('draft',),
               'approved': ('submitted',), 'rejected': ('submitted',),
               'reimbursed': ('approved',), 'reversed': ('reimbursed',)}
    if status not in allowed or previous and previous['status'] not in allowed[status]:
        raise ValueError('Invalid expense transition')
    if previous is None:
        if status != 'draft' or value['payments']:
            raise ValueError('Expense must begin as unpaid draft')
    elif status == 'draft':
        if not value['correction_reason'] or value['payments'] != previous['payments']:
            raise ValueError('Invalid expense correction')
    else:
        changed = {'status'}
        changed |= {'submitted_by','submitted_at'} if status == 'submitted' else {'decision'} if status in ('approved','rejected') else {'payments'}
        metadata = {'id','kind','employee_id','revision','content_hash','previous_hash','created_by','created_at','pdf_sha256'}
        if any(value.get(key) != previous.get(key) for key in set(value) | set(previous) if key not in changed | metadata):
            raise ValueError('Changed expense evidence during approval/payment')
    if status == 'draft' and any(value[key] is not None for key in ('decision','submitted_by','submitted_at')):
        raise ValueError('Draft retains stale expense approval')
    if status == 'submitted' and (value['submitted_by'] != value['created_by'] or instant(value['submitted_at']) > value['created_at']):
        raise ValueError('Invalid expense submission attribution')
    if status in ('approved','rejected'):
        decision = value['decision']
        if (decision['by'] != value['created_by'] or instant(decision['at']) > value['created_at']
                or decision['by'] in (employee_user_id,value['submitted_by']) or not decision['reason'].strip()):
            raise ValueError('Invalid or self-approved expense decision')
    if status in ('reimbursed','reversed'):
        if len(value['payments']) != len(previous['payments'])+1 or value['payments'][:-1] != previous['payments']:
            raise ValueError('Changed expense payment history')
        payment = value['payments'][-1]
        if (payment['kind'] != ('reimbursement' if status == 'reimbursed' else 'repayment')
                or payment['amount_minor'] != value['total_minor'] or payment['confirmed_by'] != value['created_by']
                or instant(payment['confirmed_at']) > value['created_at'] or not payment['reference'].strip()
                or iso_date(payment['paid_on']) > value['created_at'][:10]):
            raise ValueError('Invalid confirmed expense payment')


def methods(path):
    if path in ('/personnel/files','/personnel/agreements','/personnel/expenses','/personnel/payroll-preparations'):
        return 'GET, POST'
    if path == '/personnel/payroll-preparations/preview':
        return 'GET'
    if re.fullmatch(r'/personnel/files/' + ID + r'/content', path):
        return 'GET'
    if re.fullmatch(r'/personnel/(?:agreements|expenses|payroll-preparations)/' + ID + r'(?:/history)?', path):
        return 'GET'
    if re.fullmatch(r'/personnel/payroll-preparations/' + ID + r'/(?:csv|pdf|json)', path):
        return 'GET'
    if re.fullmatch(r'/personnel/expenses/' + ID + r'/(?:submit|approve|reject|reimburse|reverse-reimbursement)', path):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'HTTP-Methode nicht erlaubt.')
    api = PersonnelWorkflow(office)
    if method == 'GET':
        _shape(data, ('_query',))
        query = data.get('_query', {})
        if path == '/personnel/files':
            result = api.files(actor, query)
        elif path == '/personnel/payroll-preparations/preview':
            result = api.preview(actor, query)
        else:
            parts = path.split('/')[2:]
            if len(parts) == 1:
                result = api.list_records(actor, KINDS[parts[0]], query)
            elif parts[0] == 'files':
                _shape(query, ())
                value, mime = api.file_content(actor, parts[1])
                return value, 200, mime
            elif len(parts) == 3 and parts[2] in ('csv','pdf','json'):
                _shape(query, ('revision',))
                value, mime = api.export(actor, parts[1], parts[2], query.get('revision'))
                return value, 200, mime
            else:
                _shape(query, ())
                result = api.get(actor, KINDS[parts[0]], parts[1], len(parts) == 3)
    elif path == '/personnel/files':
        result = api.upload(actor, data)
    elif path == '/personnel/agreements':
        result = api.save_agreement(actor, data)
    elif path == '/personnel/expenses':
        result = api.save_expense(actor, data)
    elif path == '/personnel/payroll-preparations':
        result = api.close_preparation(actor, data)
    else:
        parts = path.split('/')
        result = api.expense_action(actor, parts[3], parts[4], data)
    return result, 200, 'application/json'
