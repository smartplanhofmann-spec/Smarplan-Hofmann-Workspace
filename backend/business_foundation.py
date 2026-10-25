"""Additive project/CRM foundation with fresh, scoped authorization.

No schema is created by a service constructor or request. Legacy customers and
project IDs remain canonical. Mutation receipts contain references, not copies
of contact details. Unknown originals require an explicit document release.
"""
import hashlib
import hmac
import json
import re
import sqlite3
import uuid

from core import Problem, canonical, customer_key, customer_values, now_iso
from inquiries import _transaction


PERMISSIONS = frozenset(('contacts.read', 'contacts.write', 'projects.manage',
    'documents.read', 'documents.write', 'documents.classify', 'finance.read',
    'finance.write', 'finance.issue', 'finance.approve', 'personnel.read',
    'personnel.manage', 'personnel.write', 'personnel.approve', 'personnel.export',
    'planning.read', 'planning.write', 'planning.override', 'time.own', 'time.approve',
    'inventory.read', 'inventory.write', 'privacy.manage', 'settings.manage'))
_DEFAULTS = {
    'manager': {'contacts.read', 'contacts.write', 'projects.manage', 'documents.read',
                'documents.write', 'planning.read', 'planning.write', 'inventory.read', 'time.own'},
    'technician': {'documents.read', 'documents.write', 'planning.read', 'inventory.read', 'time.own'},
    'accountant': {'contacts.read', 'documents.read', 'finance.read', 'finance.write', 'time.own'},
}
CLASSES = frozenset(('operational', 'financial', 'personnel', 'restricted'))
CONTACT_KINDS = frozenset(('customer', 'supplier', 'partner'))
_ID = re.compile(r'[a-f0-9]{32}')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_permission_grants(
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          permission TEXT NOT NULL, scope TEXT NOT NULL, effect TEXT NOT NULL CHECK(effect IN ('allow','deny')),
          revision INTEGER NOT NULL CHECK(revision>0), updated_by TEXT NOT NULL REFERENCES users(id),
          updated_at TEXT NOT NULL, UNIQUE(user_id,permission,scope))''',
        '''CREATE TABLE IF NOT EXISTS business_project_statuses(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, color TEXT NOT NULL, position INTEGER NOT NULL,
          terminal INTEGER NOT NULL CHECK(terminal IN (0,1)), active INTEGER NOT NULL CHECK(active IN (0,1)),
          revision INTEGER NOT NULL CHECK(revision>0), updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_project_profiles(
          project_id TEXT PRIMARY KEY REFERENCES projects(id), project_number TEXT NOT NULL,
          status_id TEXT REFERENCES business_project_statuses(id), manager_id TEXT REFERENCES users(id),
          site_address TEXT NOT NULL, description TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK(revision>0), updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_contact_extras(
          customer_id TEXT PRIMARY KEY REFERENCES customers(id), entity_type TEXT NOT NULL CHECK(entity_type IN ('person','company')),
          kinds_json TEXT NOT NULL, tags_json TEXT NOT NULL, erased_at TEXT,
          revision INTEGER NOT NULL CHECK(revision>0), updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_contact_people(
          id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
          name TEXT NOT NULL, role_label TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
          position INTEGER NOT NULL, UNIQUE(customer_id,position))''',
        '''CREATE TABLE IF NOT EXISTS business_contact_addresses(
          id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
          purpose TEXT NOT NULL, label TEXT NOT NULL, street TEXT NOT NULL,
          postal_code TEXT NOT NULL, city TEXT NOT NULL, country TEXT NOT NULL,
          position INTEGER NOT NULL, UNIQUE(customer_id,position))''',
        '''CREATE TABLE IF NOT EXISTS business_document_classes(
          kind TEXT NOT NULL CHECK(kind IN ('link','mail')), object_id TEXT NOT NULL,
          project_id TEXT NOT NULL REFERENCES projects(id), classification TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL,
          revision INTEGER NOT NULL CHECK(revision>0), updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL,
          PRIMARY KEY(kind,object_id))''',
        '''CREATE TABLE IF NOT EXISTS business_feed(
          id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), event_type TEXT NOT NULL,
          summary TEXT NOT NULL, visibility TEXT NOT NULL, refs_json TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_foundation_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
          request_hash TEXT NOT NULL, result_json TEXT NOT NULL, PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_privacy_requests(
          id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id), operation TEXT NOT NULL,
          status TEXT NOT NULL, blockers_json TEXT NOT NULL, checkpoint_digest TEXT,
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        'CREATE INDEX IF NOT EXISTS business_feed_project ON business_feed(project_id,created_at,id)',
        'CREATE INDEX IF NOT EXISTS business_contact_people_customer ON business_contact_people(customer_id,position)',
        'CREATE INDEX IF NOT EXISTS business_contact_addresses_customer ON business_contact_addresses(customer_id,position)',
    ]


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with _transaction(office):
            for statement in schema_statements('BLOB'):
                office.db.execute(statement)


def protected_tables():
    """Runtime receives SELECT/INSERT only; current contact rows stay mutable."""
    return ('business_feed', 'business_foundation_requests', 'business_privacy_requests')


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise Problem(400, 'Gültige Objekt-ID erwartet')
    return value


def _text(value, field, limit=200, required=False):
    if (not isinstance(value, str) or len(value) > limit or
            any((ord(c) < 32 and c not in '\r\n\t') or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise Problem(400, 'Ungültiges Feld: ' + field)
    value = value.strip()
    if required and not value:
        raise Problem(400, 'Bitte ausfüllen: ' + field)
    return value


def _bool(value, field):
    if type(value) is not bool:
        raise Problem(400, 'Wahrheitswert erwartet: ' + field)
    return value


def _integer(value, field, low=0, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise Problem(400, 'Ungültige Zahl: ' + field)
    return value


def _fresh(office, actor):
    if not isinstance(actor, dict) or not isinstance(actor.get('id'), str):
        raise Problem(401, 'Bitte anmelden')
    row = office.db.execute('SELECT id,email,role,active FROM users WHERE id=?', (actor['id'],)).fetchone()
    if not row or row['active'] != 1:
        raise Problem(401, 'Bitte anmelden')
    return {key: row[key] for key in ('id', 'email', 'role')}


def permissions(office, actor):
    """Global capability names; project authorization still requires its scope."""
    with office.lock:
        current = _fresh(office, actor)
        if current['role'] == 'owner':
            return set(PERMISSIONS)
        result = set(_DEFAULTS.get(current['role'], ()))
        for row in office.db.execute('SELECT permission,effect FROM business_permission_grants WHERE user_id=? AND scope=?',
                                     (current['id'], '*')):
            if row['effect'] == 'allow':
                result.add(row['permission'])
            else:
                result.discard(row['permission'])
        return result


def require_permission(office, actor, name, project_id=None):
    if not isinstance(name, str) or name not in PERMISSIONS:
        raise Problem(403, 'Unbekannte Fachberechtigung')
    with office.lock:
        current = _fresh(office, actor)
        if project_id is not None:
            office.project(current, _id(project_id))
        if current['role'] == 'owner':
            return current
        allowed = name in permissions(office, current)
        global_grant = office.db.execute('SELECT effect FROM business_permission_grants WHERE user_id=? AND permission=? AND scope=?',
                                        (current['id'], name, '*')).fetchone()
        if project_id is not None:
            grant = office.db.execute('SELECT effect FROM business_permission_grants WHERE user_id=? AND permission=? AND scope=?',
                                      (current['id'], name, project_id)).fetchone()
            if grant:
                allowed = grant['effect'] == 'allow'
        if global_grant and global_grant['effect'] == 'deny':
            allowed = False
        if not allowed:
            raise Problem(403, 'Diese Fachberechtigung fehlt')
        return current


def project_permissions(office, actor, project_id):
    """Effective names for a project UI, including scoped grants and denials."""
    result = set()
    for name in PERMISSIONS:
        try:
            require_permission(office, actor, name, project_id)
            result.add(name)
        except Problem as error:
            if error.status != 403:
                raise
    return result


class BusinessFoundation:
    def __init__(self, office, *, clock=now_iso):
        self.office, self.db, self.clock = office, office.db, clock

    def authorize(self, actor, name, project_id=None):
        return require_permission(self.office, actor, name, project_id)

    def _request(self, actor, operation, data):
        if not isinstance(data, dict):
            raise Problem(400, 'JSON-Objekt erwartet')
        request = _id(data.get('request_id'))
        try:
            encoded = json.dumps({'operation': operation, 'data': data}, ensure_ascii=False,
                                 sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
        except (TypeError, ValueError, UnicodeError):
            raise Problem(400, 'Gültige begrenzte JSON-Daten erwartet') from None
        if len(encoded) > 200000:
            raise Problem(413, 'Vorgang ist zu groß')
        fingerprint = hashlib.sha256(encoded).hexdigest()
        row = self.db.execute('SELECT request_hash,result_json FROM business_foundation_requests WHERE user_id=? AND request_id=?',
                              (actor['id'], request)).fetchone()
        if row and row['request_hash'] != fingerprint:
            raise Problem(409, 'Vorgangs-ID wurde mit anderem Inhalt verwendet')
        return request, fingerprint, json.loads(row['result_json']) if row else None

    def _remember(self, actor, request, fingerprint, result):
        self.db.execute('INSERT INTO business_foundation_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                        (actor['id'], request, fingerprint, canonical(result)))

    def grants(self, actor):
        with self.office.lock:
            self.authorize(actor, 'settings.manage')
            return {'items': [dict(row) for row in self.db.execute('SELECT * FROM business_permission_grants ORDER BY user_id,scope,permission')]}

    def save_grant(self, actor, data):
        if not isinstance(data, dict) or set(data) != {'request_id', 'user_id', 'permission', 'scope', 'effect', 'revision'}:
            raise Problem(400, 'Benutzer, Fachrecht, Umfang, Entscheidung und Version erwartet')
        user = _id(data['user_id'])
        permission, scope, effect = data['permission'], data['scope'], data['effect']
        if not isinstance(permission, str) or permission not in PERMISSIONS or effect not in ('allow', 'deny'):
            raise Problem(400, 'Ungültige Fachberechtigung')
        if scope != '*':
            _id(scope)
        revision = _integer(data['revision'], 'Version')
        with _transaction(self.office):
            actor = self.authorize(actor, 'settings.manage')
            target = self.db.execute('SELECT role FROM users WHERE id=?', (user,)).fetchone()
            if not target:
                raise Problem(404, 'Benutzer nicht verfügbar')
            if target['role'] == 'owner':
                raise Problem(400, 'Geschäftsführung behält vollständige Fachrechte')
            if scope != '*':
                self.office.project(actor, scope)
            request, fingerprint, previous = self._request(actor, 'grant', data)
            if previous:
                return dict(self.db.execute('SELECT * FROM business_permission_grants WHERE id=?', (previous['id'],)).fetchone())
            row = self.db.execute('SELECT * FROM business_permission_grants WHERE user_id=? AND permission=? AND scope=?',
                                  (user, permission, scope)).fetchone()
            if revision != (row['revision'] if row else 0):
                raise Problem(409, 'Berechtigung wurde inzwischen geändert')
            identifier, stamp = row['id'] if row else uuid.uuid4().hex, self.clock()
            if row:
                self.db.execute('UPDATE business_permission_grants SET effect=?,revision=revision+1,updated_by=?,updated_at=? WHERE id=?',
                                (effect, actor['id'], stamp, identifier))
            else:
                self.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                                (identifier, user, permission, scope, effect, 1, actor['id'], stamp))
            self.office.audit(actor, 'business.permission.changed', identifier)
            self._remember(actor, request, fingerprint, {'id': identifier})
            return dict(self.db.execute('SELECT * FROM business_permission_grants WHERE id=?', (identifier,)).fetchone())

    def statuses(self, actor):
        with self.office.lock:
            _fresh(self.office, actor)
            return {'items': [dict(row, active=bool(row['active']), terminal=bool(row['terminal'])) for row in
                              self.db.execute('SELECT * FROM business_project_statuses ORDER BY position,name,id')]}

    def save_status(self, actor, data, identifier=None):
        allowed = {'request_id', 'revision', 'name', 'color', 'position', 'terminal', 'active'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise Problem(400, 'Gültige Statuskonfiguration erwartet')
        with _transaction(self.office):
            actor = self.authorize(actor, 'settings.manage')
            request, fingerprint, previous = self._request(actor, 'status:' + str(identifier), data)
            if previous:
                return self._status(previous['id'])
            current = self._status(_id(identifier)) if identifier else None
            if current and _integer(data.get('revision'), 'Version') != current['revision']:
                raise Problem(409, 'Status wurde inzwischen geändert')
            name = _text(data.get('name', (current or {}).get('name', '')), 'Statusname', required=True)
            color = data.get('color', (current or {}).get('color', '#64748B'))
            if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                raise Problem(400, 'Sechsstellige Hex-Farbe erwartet')
            position = _integer(data.get('position', (current or {}).get('position', 0)), 'Reihenfolge')
            terminal = _bool(data.get('terminal', (current or {}).get('terminal', False)), 'Abschlussstatus')
            active = _bool(data.get('active', (current or {}).get('active', True)), 'Aktiv')
            identifier, revision, stamp = identifier or uuid.uuid4().hex, current['revision'] + 1 if current else 1, self.clock()
            if current:
                self.db.execute('UPDATE business_project_statuses SET name=?,color=?,position=?,terminal=?,active=?,revision=?,updated_by=?,updated_at=? WHERE id=?',
                                (name, color.upper(), position, int(terminal), int(active), revision, actor['id'], stamp, identifier))
            else:
                self.db.execute('INSERT INTO business_project_statuses(id,name,color,position,terminal,active,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (identifier, name, color.upper(), position, int(terminal), int(active), revision, actor['id'], stamp))
            self.office.audit(actor, 'business.project_status.changed', identifier)
            self._remember(actor, request, fingerprint, {'id': identifier})
            return self._status(identifier)

    def _status(self, identifier):
        row = self.db.execute('SELECT * FROM business_project_statuses WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise Problem(404, 'Projektstatus nicht verfügbar')
        return dict(row, terminal=bool(row['terminal']), active=bool(row['active']))

    def project(self, actor, project_id):
        with self.office.lock:
            actor = self.authorize(actor, 'documents.read', project_id)
            project = self.office.project(actor, project_id)
            row = self.db.execute('SELECT * FROM business_project_profiles WHERE project_id=?', (project_id,)).fetchone()
            extra = dict(row) if row else {'project_id': project_id, 'project_number': '', 'status_id': None,
                'manager_id': None, 'site_address': '', 'description': '', 'revision': 0, 'updated_at': None}
            from project_workspace import ProjectWorkspace
            shared = ProjectWorkspace(self.office).profile(actor, project_id)
            extra.update(description=shared['description'], site_address=shared['site_address'], workspace_revision=shared['revision'])
            extra.update(id=project_id, name=project['name'], customer_id=project['customer_id'], customer=project['customer'],
                         status=self._status(extra['status_id']) if extra['status_id'] else None,
                         permissions=sorted(project_permissions(self.office, actor, project_id)))
            return extra

    def save_project(self, actor, project_id, data):
        allowed = {'request_id', 'revision', 'workspace_revision', 'project_number', 'status_id', 'manager_id', 'site_address', 'description'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise Problem(400, 'Gültige Projekterweiterung erwartet')
        with _transaction(self.office):
            actor = self.authorize(actor, 'projects.manage', project_id)
            request, fingerprint, previous = self._request(actor, 'project:' + project_id, data)
            if previous:
                return self.project(actor, project_id)
            current = self.project(actor, project_id)
            if _integer(data.get('revision'), 'Version') != current['revision']:
                raise Problem(409, 'Projekt wurde inzwischen geändert')
            values = {field: data.get(field, current[field]) for field in allowed - {'request_id', 'revision', 'workspace_revision'}}
            for field, maximum in (('project_number', 80), ('site_address', 2000), ('description', 10000)):
                values[field] = _text(values[field], field, maximum)
            if values['status_id'] is not None:
                status = self._status(_id(values['status_id']))
                if not status['active'] and current['status_id'] != status['id']:
                    raise Problem(409, 'Archivierter Status kann nicht neu zugeordnet werden')
            if values['manager_id'] is not None:
                member = self.db.execute('SELECT id,active FROM users WHERE id=?', (_id(values['manager_id']),)).fetchone()
                if not member or member['active'] != 1 or not (self.db.execute('SELECT 1 FROM assignments WHERE user_id=? AND project_id=?',
                                            (member['id'], project_id)).fetchone() or member['id'] == actor['id'] and actor['role'] == 'owner'):
                    raise Problem(400, 'Verantwortlicher muss ein aktives Projektmitglied sein')
            shared_changes = {field: values[field] for field in ('description', 'site_address') if field in data}
            if shared_changes:
                if _integer(data.get('workspace_revision'), 'Version der Projektübersicht') != current['workspace_revision']:
                    raise Problem(409, 'Projektbeschreibung wurde inzwischen im Projekt geändert; neu laden')
                from project_workspace import ProjectWorkspace
                ProjectWorkspace(self.office).save_profile(actor, project_id, dict(shared_changes,
                    request_id=hashlib.sha256(('business-profile:' + request).encode()).hexdigest()[:32],
                    revision=current['workspace_revision']))
            stamp, revision = self.clock(), current['revision'] + 1
            fields = ('project_number', 'status_id', 'manager_id', 'site_address', 'description')
            if current['revision']:
                self.db.execute('UPDATE business_project_profiles SET project_number=?,status_id=?,manager_id=?,site_address=?,description=?,revision=?,updated_by=?,updated_at=? WHERE project_id=?',
                                (*(values[field] for field in fields), revision, actor['id'], stamp, project_id))
            else:
                self.db.execute('INSERT INTO business_project_profiles(project_id,project_number,status_id,manager_id,site_address,description,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                (project_id, *(values[field] for field in fields), revision, actor['id'], stamp))
            self.event(actor, project_id, 'project.updated', 'Projektprofil aktualisiert', refs={'project_id': project_id})
            self.office.audit(actor, 'business.project.updated', project_id)
            self._remember(actor, request, fingerprint, {'id': project_id})
            return self.project(actor, project_id)

    def pipeline(self, actor, query=''):
        with self.office.lock:
            actor = _fresh(self.office, actor)
            query = _text(query, 'Suche', 300).casefold()
            items = []
            for project in self.office.projects(actor):
                try:
                    record = self.project(actor, project['id'])
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                if not query or query in ' '.join(str(record.get(key) or '') for key in ('name', 'customer', 'project_number', 'site_address')).casefold():
                    items.append(record)
            return {'items': items}

    def _contact_scope(self, actor, customer_id, permission='contacts.read'):
        actor = _fresh(self.office, actor)
        if actor['role'] == 'owner':
            return actor
        for row in self.db.execute('SELECT id FROM projects WHERE customer_id=?', (customer_id,)):
            try:
                return self.authorize(actor, permission, row['id'])
            except Problem as error:
                if error.status not in (403, 404):
                    raise
        raise Problem(403, 'Kontakt ist nicht für diesen Projektumfang freigegeben')

    def contact(self, actor, customer_id):
        with self.office.lock:
            customer_id = _id(customer_id)
            actor = self._contact_scope(actor, customer_id)
            row = self.db.execute('SELECT id,name,contact,email,phone,address,notes,active,created_at,updated_at FROM customers WHERE id=?',
                                  (customer_id,)).fetchone()
            if not row:
                raise Problem(404, 'Kontakt nicht verfügbar')
            result = dict(row, active=bool(row['active']))
            if actor['role'] != 'owner':
                try:
                    self._contact_scope(actor, customer_id, 'contacts.write')
                except Problem:
                    result.pop('notes', None)
            extra = self.db.execute('SELECT * FROM business_contact_extras WHERE customer_id=?', (customer_id,)).fetchone()
            result.update(entity_type=extra['entity_type'] if extra else 'company',
                          kinds=json.loads(extra['kinds_json']) if extra else ['customer'],
                          tags=json.loads(extra['tags_json']) if extra else [], revision=extra['revision'] if extra else 0,
                          erased_at=extra['erased_at'] if extra else None,
                          persons=[dict(item) for item in self.db.execute('SELECT id,name,role_label,email,phone FROM business_contact_people WHERE customer_id=? ORDER BY position', (customer_id,))],
                          addresses=[dict(item) for item in self.db.execute('SELECT id,purpose,label,street,postal_code,city,country FROM business_contact_addresses WHERE customer_id=? ORDER BY position', (customer_id,))])
            return result

    def contacts(self, actor, query='', kind=None):
        with self.office.lock:
            actor = _fresh(self.office, actor)
            query = _text(query, 'Kontaktsuche', 300).casefold()
            if kind is not None and (not isinstance(kind, str) or kind not in CONTACT_KINDS):
                raise Problem(400, 'Unbekannte Kontaktart')
            result = []
            for row in self.db.execute('SELECT id FROM customers ORDER BY lower(name),id'):
                try:
                    contact = self.contact(actor, row['id'])
                except Problem as error:
                    if error.status == 403:
                        continue
                    raise
                if (not kind or kind in contact['kinds']) and (not query or query in ' '.join(str(contact.get(k) or '') for k in ('name', 'contact', 'email', 'phone', 'address')).casefold()):
                    result.append(contact)
            return {'items': result, 'can_create': actor['role'] == 'owner'}

    def _contact_values(self, data, current=None):
        base = customer_values({field: data.get(field, (current or {}).get(field, default)) for field, default in
            (('name', ''), ('contact', ''), ('email', ''), ('phone', ''), ('address', ''), ('notes', ''), ('active', True))})
        entity = data.get('entity_type', (current or {}).get('entity_type', 'company'))
        kinds, tags = data.get('kinds', (current or {}).get('kinds', ['customer'])), data.get('tags', (current or {}).get('tags', []))
        if entity not in ('person', 'company') or not isinstance(kinds, list) or not kinds or len(kinds) > 3 or any(not isinstance(k, str) or k not in CONTACT_KINDS for k in kinds) or len(set(kinds)) != len(kinds):
            raise Problem(400, 'Gültiger Kontakttyp und Kontaktarten erwartet')
        if not isinstance(tags, list) or len(tags) > 30:
            raise Problem(400, 'Höchstens 30 Schlagworte erwartet')
        tags = sorted(set(_text(tag, 'Schlagwort', 60, True) for tag in tags))
        persons, addresses = data.get('persons', (current or {}).get('persons', [])), data.get('addresses', (current or {}).get('addresses', []))
        if not isinstance(persons, list) or len(persons) > 20 or not isinstance(addresses, list) or len(addresses) > 20:
            raise Problem(400, 'Höchstens 20 Ansprechpartner und Adressen erwartet')
        clean_persons, clean_addresses = [], []
        for person in persons:
            if not isinstance(person, dict) or set(person) - {'id', 'name', 'role_label', 'email', 'phone'}:
                raise Problem(400, 'Ungültiger Ansprechpartner')
            item = {field: _text(person.get(field, ''), field, maximum, field == 'name') for field, maximum in
                    (('name', 200), ('role_label', 200), ('email', 254), ('phone', 100))}
            if item['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', item['email']):
                raise Problem(400, 'Gültige E-Mail des Ansprechpartners erwartet')
            item['id'] = _id(person['id']) if 'id' in person else uuid.uuid4().hex
            clean_persons.append(item)
        for address in addresses:
            if not isinstance(address, dict) or set(address) - {'id', 'purpose', 'label', 'street', 'postal_code', 'city', 'country'}:
                raise Problem(400, 'Ungültige Kontaktadresse')
            purpose = address.get('purpose', 'other')
            if purpose not in ('billing', 'site', 'delivery', 'other'):
                raise Problem(400, 'Ungültiger Adresszweck')
            item = {field: _text(address.get(field, ''), field, maximum) for field, maximum in
                    (('label', 200), ('street', 1000), ('postal_code', 30), ('city', 200))}
            country = address.get('country', 'DE')
            if not isinstance(country, str) or not re.fullmatch(r'[A-Z]{2}', country):
                raise Problem(400, 'Zweistelliger Ländercode erwartet')
            item.update(id=_id(address['id']) if 'id' in address else uuid.uuid4().hex, purpose=purpose, country=country)
            clean_addresses.append(item)
        for items in (clean_persons, clean_addresses):
            if len({item['id'] for item in items}) != len(items):
                raise Problem(400, 'Unterobjekt-IDs müssen eindeutig sein')
        return base, entity, sorted(kinds), tags, clean_persons, clean_addresses

    def save_contact(self, actor, data, customer_id=None):
        allowed = {'request_id', 'revision', 'name', 'contact', 'email', 'phone', 'address', 'notes', 'active',
                   'entity_type', 'kinds', 'tags', 'persons', 'addresses'}
        if not isinstance(data, dict) or set(data) - allowed:
            raise Problem(400, 'Gültige Kontaktdaten erwartet')
        with _transaction(self.office):
            actor = _fresh(self.office, actor)
            if customer_id:
                self._contact_scope(actor, _id(customer_id), 'contacts.write')
            elif actor['role'] != 'owner':
                raise Problem(403, 'Neue Kontakte legt die Geschäftsführung an')
            request, fingerprint, previous = self._request(actor, 'contact:' + str(customer_id), data)
            if previous:
                return self.contact(actor, previous['id'])
            current = self.contact(actor, customer_id) if customer_id else None
            if current and (_integer(data.get('revision'), 'Version') != current['revision'] or current['erased_at']):
                raise Problem(409, 'Kontakt wurde inzwischen geändert oder datenschutzgerecht gelöscht')
            base, entity, kinds, tags, persons, addresses = self._contact_values(data, current)
            for table, items in (('business_contact_people', persons), ('business_contact_addresses', addresses)):
                for item in items:
                    old = self.db.execute('SELECT customer_id FROM ' + table + ' WHERE id=?', (item['id'],)).fetchone()
                    if old and old['customer_id'] != customer_id:
                        raise Problem(409, 'Unterobjekt gehört zu einem anderen Kontakt')
            stamp, revision = self.clock(), current['revision'] + 1 if current else 1
            if current:
                try:
                    self.db.execute('UPDATE customers SET name=?,contact=?,email=?,phone=?,address=?,notes=?,active=?,dedupe_key=?,updated_at=? WHERE id=?',
                        (base['name'], base['contact'], base['email'], base['phone'], base['address'], base['notes'], int(base['active']), customer_key(base['name'], base['address']), stamp, customer_id))
                except self.office.integrity_error:
                    raise Problem(409, 'Kontakt mit diesem Namen und dieser Adresse existiert bereits') from None
                self.db.execute('UPDATE projects SET customer=? WHERE customer_id=?', (base['name'], customer_id))
            else:
                customer_id = self.office.insert_customer(base)
            self.db.execute('INSERT INTO business_contact_extras(customer_id,entity_type,kinds_json,tags_json,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?) '
                            'ON CONFLICT(customer_id) DO UPDATE SET entity_type=excluded.entity_type,kinds_json=excluded.kinds_json,tags_json=excluded.tags_json,revision=excluded.revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
                            (customer_id, entity, canonical(kinds), canonical(tags), revision, actor['id'], stamp))
            self.db.execute('DELETE FROM business_contact_people WHERE customer_id=?', (customer_id,))
            self.db.execute('DELETE FROM business_contact_addresses WHERE customer_id=?', (customer_id,))
            for position, person in enumerate(persons):
                self.db.execute('INSERT INTO business_contact_people(id,customer_id,name,role_label,email,phone,position) VALUES(?,?,?,?,?,?,?)',
                    (person['id'], customer_id, person['name'], person['role_label'], person['email'], person['phone'], position))
            for position, address in enumerate(addresses):
                self.db.execute('INSERT INTO business_contact_addresses(id,customer_id,purpose,label,street,postal_code,city,country,position) VALUES(?,?,?,?,?,?,?,?,?)',
                    (address['id'], customer_id, address['purpose'], address['label'], address['street'], address['postal_code'], address['city'], address['country'], position))
            self.office.audit(actor, 'business.contact.updated' if current else 'business.contact.created', customer_id)
            self._remember(actor, request, fingerprint, {'id': customer_id})
            return self.contact(actor, customer_id)

    def _document(self, project_id, kind, object_id):
        _id(object_id)
        if kind == 'link':
            row = self.db.execute("SELECT project_id,payload,revision FROM workspace_items WHERE id=? AND kind='links'", (object_id,)).fetchone()
            if not row or row['project_id'] != project_id:
                raise Problem(404, 'Dokument nicht verfügbar')
            return (json.loads(row['payload']).get('category'),
                    hashlib.sha256(canonical({'revision': row['revision'], 'payload': row['payload']}).encode()).hexdigest())
        if kind == 'mail':
            row = self.db.execute("SELECT i.project_id,a.status,a.source_attachment_id,a.filename,a.media_type,a.size,a.sha256 FROM inquiry_attachments a JOIN inquiries i ON i.id=a.inquiry_id WHERE a.id=? AND i.status='converted'", (object_id,)).fetchone()
            if not row or row['project_id'] != project_id or row['status'] == 'deleted':
                raise Problem(404, 'Dokument nicht verfügbar')
            return None, hashlib.sha256(canonical({key: row[key] for key in ('source_attachment_id', 'filename', 'media_type', 'size', 'sha256')}).encode()).hexdigest()
        raise Problem(400, 'Dokumentart link oder mail erwartet')

    def classification(self, actor, project_id, kind, object_id):
        with self.office.lock:
            self.authorize(actor, 'documents.read', project_id)
            category, fingerprint = self._document(project_id, kind, object_id)
            row = self.db.execute('SELECT * FROM business_document_classes WHERE kind=? AND object_id=?', (kind, object_id)).fetchone()
            value = dict(row) if row else {'kind': kind, 'object_id': object_id, 'project_id': project_id,
                                           'classification': 'unclassified', 'revision': 0, 'updated_at': None}
            value['release_current'] = bool(row and row['content_fingerprint'] == fingerprint)
            if row and not value['release_current']:
                value['classification'] = 'unclassified'
            if category in ('offer', 'invoice') and value['classification'] != 'restricted':
                value['effective_classification'] = 'financial'
            else:
                value['effective_classification'] = value['classification']
            value['id'] = object_id
            value['source_fingerprint'] = fingerprint
            return value

    def can_read_document(self, actor, project_id, kind, object_id, category=None):
        with self.office.lock:
            actor = _fresh(self.office, actor)
            try:
                record = self.classification(actor, project_id, kind, object_id)
                level = record['effective_classification']
                if actor['role'] == 'owner':
                    return True
                if record['classification'] == 'unclassified' or not record['release_current']:
                    return False
                if level == 'operational':
                    return True
                if level == 'financial':
                    self.authorize(actor, 'finance.read', project_id)
                    return True
                if level == 'personnel':
                    self.authorize(actor, 'personnel.read', project_id)
                    return True
                return False
            except Problem as error:
                if error.status in (403, 404):
                    return False
                raise

    def classify(self, actor, project_id, kind, object_id, data):
        if (not isinstance(data, dict) or set(data) != {'request_id', 'revision', 'classification', 'expected_source_fingerprint'}
                or not isinstance(data['classification'], str) or data['classification'] not in CLASSES):
            raise Problem(400, 'Dokumentklasse und Ausgangsversion erwartet')
        expected_source = data['expected_source_fingerprint']
        if not isinstance(expected_source, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_source):
            raise Problem(400, 'Prüfsumme der zuletzt geprüften Dokumentquelle erwartet')
        with _transaction(self.office):
            actor = self.authorize(actor, 'documents.classify', project_id)
            current = self.classification(actor, project_id, kind, object_id)
            if not hmac.compare_digest(expected_source, current['source_fingerprint']):
                raise Problem(409, 'Dokumentquelle wurde inzwischen geändert; vor der Freigabe erneut prüfen')
            request, fingerprint, previous = self._request(actor, 'class:' + kind + ':' + object_id, data)
            if previous:
                return self.classification(actor, project_id, kind, object_id)
            if data['revision'] != current['revision'] or type(data['revision']) is not int:
                raise Problem(409, 'Dokumentfreigabe wurde inzwischen geändert')
            category, content_fingerprint = self._document(project_id, kind, object_id)
            if category in ('offer', 'invoice') and data['classification'] not in ('financial', 'restricted'):
                raise Problem(400, 'Finanzdokumente können nicht allgemein freigegeben werden')
            stamp = self.clock()
            self.db.execute('INSERT INTO business_document_classes(kind,object_id,project_id,classification,content_fingerprint,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?) '
                'ON CONFLICT(kind,object_id) DO UPDATE SET classification=excluded.classification,content_fingerprint=excluded.content_fingerprint,revision=excluded.revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
                (kind, object_id, project_id, data['classification'], content_fingerprint, current['revision'] + 1, actor['id'], stamp))
            self.office.audit(actor, 'business.document.classified', object_id)
            self._remember(actor, request, fingerprint, {'id': object_id, 'kind': kind})
            return self.classification(actor, project_id, kind, object_id)

    def event(self, actor, project_id, event_type, summary, *, visibility='operational', refs=None):
        actor = self.authorize(actor, 'documents.read', project_id)
        if not isinstance(visibility, str) or visibility not in CLASSES:
            raise Problem(400, 'Ungültiger Sichtbarkeitsumfang')
        if visibility == 'financial':
            self.authorize(actor, 'finance.read', project_id)
        if visibility == 'personnel':
            self.authorize(actor, 'personnel.read', project_id)
        if visibility == 'restricted' and actor['role'] != 'owner':
            raise Problem(403, 'Geschützter Vorgang')
        identifier = uuid.uuid4().hex
        self.db.execute('INSERT INTO business_feed(id,project_id,event_type,summary,visibility,refs_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
            (identifier, project_id, _text(event_type, 'Ereignisart', 100, True), _text(summary, 'Eintrag', 10000, True),
             visibility, canonical(refs or {}), actor['id'], self.clock()))
        return identifier

    def feed(self, actor, project_id=None, limit=100):
        with self.office.lock:
            actor = _fresh(self.office, actor)
            limit = _integer(limit, 'Anzahl', 1, 200)
            if project_id:
                self.authorize(actor, 'documents.read', project_id)
            visible = {row['id'] for row in self.office.projects(actor)}
            result = []
            for row in self.db.execute('SELECT * FROM business_feed ORDER BY created_at DESC,id DESC'):
                if row['project_id'] not in visible or project_id and row['project_id'] != project_id:
                    continue
                try:
                    self.authorize(actor, 'documents.read', row['project_id'])
                    if row['visibility'] == 'financial':
                        self.authorize(actor, 'finance.read', row['project_id'])
                    if row['visibility'] == 'personnel':
                        self.authorize(actor, 'personnel.read', row['project_id'])
                    if row['visibility'] == 'restricted' and actor['role'] != 'owner':
                        continue
                except Problem as error:
                    if error.status in (403, 404):
                        continue
                    raise
                result.append(dict(row, refs=json.loads(row['refs_json'])))
                result[-1].pop('refs_json')
                if len(result) == limit:
                    break
            return {'items': result}

    def post_message(self, actor, data):
        if not isinstance(data, dict) or set(data) - {'request_id', 'project_id', 'text', 'visibility'}:
            raise Problem(400, 'Projekt und Nachricht erwartet')
        with _transaction(self.office):
            project = _id(data.get('project_id'))
            actor = self.authorize(actor, 'documents.write', project)
            request, fingerprint, previous = self._request(actor, 'message', data)
            if previous:
                row = self.db.execute('SELECT * FROM business_feed WHERE id=?', (previous['id'],)).fetchone()
            else:
                identifier = self.event(actor, project, 'message', data.get('text'), visibility=data.get('visibility', 'operational'))
                self._remember(actor, request, fingerprint, {'id': identifier})
                row = self.db.execute('SELECT * FROM business_feed WHERE id=?', (identifier,)).fetchone()
            # Recheck visibility before replay; a revoked finance grant may not
            # turn an old immutable receipt into a read bypass.
            if row['visibility'] == 'financial':
                self.authorize(actor, 'finance.read', project)
            if row['visibility'] == 'personnel':
                self.authorize(actor, 'personnel.read', project)
            if row['visibility'] == 'restricted' and actor['role'] != 'owner':
                raise Problem(403, 'Geschützter Vorgang')
            result = dict(row, refs=json.loads(row['refs_json']))
            result.pop('refs_json')
            return result

    def export_contact(self, actor, customer_id):
        with _transaction(self.office):
            actor = self.authorize(actor, 'privacy.manage')
            contact = self.contact(actor, customer_id)
            projects = [dict(row) for row in self.db.execute('SELECT id,name,customer FROM projects WHERE customer_id=?', (customer_id,))]
            inquiries = [dict(row) for row in self.db.execute('SELECT id,source,source_account,source_id,subject,message,sender_name,sender_email,sender_phone,received_at,provenance FROM inquiries WHERE customer_id=?', (customer_id,))]
            identifier = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_privacy_requests(id,customer_id,operation,status,blockers_json,created_by,created_at) VALUES(?,?,?,?,?,?,?)',
                            (identifier, customer_id, 'export', 'review_required', '[]', actor['id'], self.clock()))
            self.office.audit(actor, 'business.privacy.exported', identifier)
            return {'id': identifier, 'contact': contact, 'projects': projects, 'inquiries': inquiries,
                    'generated_at': self.clock(), 'status': 'review_required',
                    'coverage': ['contact_master', 'contact_people', 'contact_addresses', 'linked_projects', 'linked_inquiry_text'],
                    'limitations': ['Originaldateien, historische Belege, externe Systeme und lokale Kopien sind gesondert zu prüfen.',
                                    'Nachrichten auf Angaben weiterer Personen prüfen; kein vollständiger Betroffenenexport behauptet.']}

    def erase_contact(self, actor, customer_id, data):
        if (not isinstance(data, dict) or set(data) != {'request_id', 'revision', 'confirmed'}
                or data['confirmed'] is not True):
            raise Problem(400, 'Ausdrückliche Bestätigung und Kontaktversion erwartet')
        with _transaction(self.office):
            actor = self.authorize(actor, 'privacy.manage')
            request, fingerprint, previous = self._request(actor, 'erase:' + customer_id, data)
            if previous:
                return previous
            contact = self.contact(actor, customer_id)
            if _integer(data['revision'], 'Version') != contact['revision']:
                raise Problem(409, 'Kontakt wurde inzwischen geändert')
            blockers = _privacy_blockers(self.office, customer_id)
            checkpoint = None
            if not blockers:
                try:
                    from business_schema import checkpoint_before_erasure
                    checkpoint = checkpoint_before_erasure(self.office, customer_id, request)
                    if (not isinstance(checkpoint, dict) or not isinstance(checkpoint.get('digest'), str)
                            or not re.fullmatch(r'[a-f0-9]{64}', checkpoint['digest'])):
                        checkpoint = None
                        blockers.append('Unabhängiger Datenschutz-Checkpoint hat keine gültige Bestätigung geliefert.')
                except (ImportError, Problem):
                    blockers.append('Unabhängiger Datenschutz-Checkpoint ist nicht vollständig eingerichtet oder bestätigt.')
            status = 'blocked' if blockers else 'erased'
            if not blockers:
                _anonymize(self.office, customer_id, actor['id'], self.clock())
            identifier = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_privacy_requests(id,customer_id,operation,status,blockers_json,checkpoint_digest,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (identifier, customer_id, 'erase', status, canonical(blockers), checkpoint.get('digest') if checkpoint else None, actor['id'], self.clock()))
            result = {'id': identifier, 'customer_id': customer_id, 'status': status, 'blockers': blockers}
            self.office.audit(actor, 'business.privacy.' + status, identifier)
            self._remember(actor, request, fingerprint, result)
            return result


def _privacy_blockers(office, customer_id):
    customer = office.db.execute('SELECT * FROM customers WHERE id=?', (customer_id,)).fetchone()
    if not customer:
        raise Problem(404, 'Kontakt nicht verfügbar')
    extra = office.db.execute('SELECT erased_at FROM business_contact_extras WHERE customer_id=?', (customer_id,)).fetchone()
    if extra and extra['erased_at']:
        return []
    blockers = []
    if office.db.execute('SELECT 1 FROM projects WHERE customer_id=?', (customer_id,)).fetchone():
        blockers.append('Verknüpfte Projekte und aufbewahrungspflichtige Belege benötigen einen geprüften Bereinigungsplan.')
    for row in office.db.execute('SELECT customer_id,sender_email,sender_phone,message FROM inquiries'):
        if (row['customer_id'] == customer_id or customer['email'] and customer['email'].casefold() == row['sender_email'].casefold()
                or customer['phone'] and customer['phone'] == row['sender_phone']):
            blockers.append('Anfragen, Originalanhänge und historische Quittungen müssen gemeinsam geprüft werden.')
            break
    # Existing receipts may contain complete historical contact/candidate data.
    for row in office.db.execute('SELECT result FROM inquiry_requests'):
        if customer_id in row['result'] or customer['email'] and customer['email'].casefold() in row['result'].casefold():
            blockers.append('Historische Anfragequittungen enthalten möglicherweise personenbezogene Kopien.')
            break
    # Fail closed on further copies, including newly added commercial modules.
    # Inspect only ordinary text columns, never credentials or binary artifacts.
    skipped = {'customers', 'business_contact_extras', 'business_contact_people',
               'business_contact_addresses', 'business_foundation_requests',
               'business_privacy_requests', 'audit', 'users', 'secrets', 'sessions',
               'mfa', 'auth_challenges', 'login_limits', 'plan_sessions',
               'inbound_import_tokens', 'inquiry_attachment_limits', 'inquiries',
               'inquiry_requests', 'sqlite_sequence'}
    if isinstance(office.db, sqlite3.Connection):
        tables = [r[0] for r in office.db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        columns = lambda table: [r['name'] for r in office.db.execute('PRAGMA table_info(' + table + ')') if r['type'].upper() in ('TEXT', 'JSON', 'JSONB')]
    else:
        tables = [r[0] for r in office.db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")]
        columns = lambda table: [r[0] for r in office.db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=? AND data_type IN ('text','character varying','json','jsonb')", (table,))]
    needles = [customer_id] + [str(customer[field]).casefold() for field in ('name', 'email', 'phone') if len(str(customer[field])) >= 4]
    for table in tables:
        if table in skipped or any(token in table for token in ('credential', 'secret', 'token', 'oauth', 'session')):
            continue
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', table):
            blockers.append('Unbekannte Datentabelle erfordert eine gesonderte Datenschutzprüfung.')
            break
        fields = columns(table)
        if not fields:
            continue
        if any(not re.fullmatch(r'[a-z_][a-z0-9_]*', field) for field in fields):
            blockers.append('Unbekannte Datenstruktur erfordert eine gesonderte Datenschutzprüfung.')
            break
        rows = office.db.execute('SELECT ' + ','.join('"' + field + '"' for field in fields) + ' FROM "' + table + '" LIMIT 10001').fetchall()
        if len(rows) > 10000 or any(any(needle in str(row[field] or '').casefold() for needle in needles) for row in rows for field in fields):
            blockers.append('Weitere historische oder fachliche Datenkopien benötigen einen geprüften Bereinigungsplan.')
            break
    return blockers


def _anonymize(office, customer_id, actor_id, stamp):
    name = 'Gelöschter Kontakt ' + customer_id
    office.db.execute('UPDATE customers SET name=?,contact=?,email=?,phone=?,address=?,notes=?,active=0,dedupe_key=?,updated_at=? WHERE id=?',
                     (name, '', '', '', '', '', customer_key(name), stamp, customer_id))
    for table in ('business_contact_people', 'business_contact_addresses'):
        office.db.execute('DELETE FROM ' + table + ' WHERE customer_id=?', (customer_id,))
    office.db.execute('INSERT INTO business_contact_extras(customer_id,entity_type,kinds_json,tags_json,erased_at,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?) '
        'ON CONFLICT(customer_id) DO UPDATE SET entity_type=excluded.entity_type,kinds_json=excluded.kinds_json,tags_json=excluded.tags_json,erased_at=excluded.erased_at,revision=business_contact_extras.revision+1,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
        (customer_id, 'person', '["customer"]', '[]', stamp, 1, actor_id, stamp))


def reapply_privacy_checkpoint(office, event):
    from business_schema import privacy_subject_hash
    if (not isinstance(event, dict) or event.get('operation') != 'anonymize_customer'
            or event.get('subject_kind', 'customer') != 'customer'):
        raise ValueError('Unsupported privacy checkpoint')
    for row in office.db.execute('SELECT id FROM customers').fetchall():
        if privacy_subject_hash(row['id']) == event.get('subject_hash'):
            if _privacy_blockers(office, row['id']):
                raise ValueError('Privacy checkpoint cannot be safely reapplied to linked historical data')
            extra = office.db.execute('SELECT erased_at FROM business_contact_extras WHERE customer_id=?', (row['id'],)).fetchone()
            if extra and extra['erased_at']:
                return True
            actor = office.db.execute("SELECT id FROM users WHERE role='owner' ORDER BY id LIMIT 1").fetchone()
            if not actor:
                raise ValueError('No accountable owner exists for privacy restore')
            _anonymize(office, row['id'], actor['id'], now_iso())
            return True
    return True


def legacy_customer_changed(office, actor, customer_id):
    """Caller owns the existing customer mutation transaction, including down.

    Tracking remains active when business writes are disabled: returning to the
    business editor must never accept a stale revision after a legacy edit.
    """
    if isinstance(office.db, sqlite3.Connection):
        present = office.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='business_contact_extras'").fetchone()
    else:
        present = office.db.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='business_contact_extras'").fetchone()
    if not present:
        return None
    actor = _fresh(office, actor)
    if actor['role'] != 'owner':
        raise Problem(403, 'Kundenstammdaten im bisherigen API ändern nur die Geschäftsführung')
    row = office.db.execute('SELECT erased_at FROM business_contact_extras WHERE customer_id=?', (customer_id,)).fetchone()
    if row and row['erased_at']:
        raise Problem(409, 'Dieser Kontakt wurde datenschutzgerecht anonymisiert; eine neue Person separat anlegen')
    stamp = now_iso()
    office.db.execute('INSERT INTO business_contact_extras(customer_id,entity_type,kinds_json,tags_json,revision,updated_by,updated_at) VALUES(?,?,?,?,?,?,?) '
        'ON CONFLICT(customer_id) DO UPDATE SET revision=business_contact_extras.revision+1,updated_by=excluded.updated_by,updated_at=excluded.updated_at',
        (customer_id, 'company', '["customer"]', '[]', 1, actor['id'], stamp))
    office.audit(actor, 'business.contact.legacy_updated', customer_id)
    return office.db.execute('SELECT revision FROM business_contact_extras WHERE customer_id=?', (customer_id,)).fetchone()[0]


def validate_integrity(office):
    with office.lock:
        try:
            for row in office.db.execute('SELECT * FROM business_permission_grants'):
                _id(row['id'])
                if row['permission'] not in PERMISSIONS or row['effect'] not in ('allow', 'deny') or row['revision'] < 1:
                    raise ValueError('Invalid business permission')
                if row['scope'] != '*' and not office.db.execute('SELECT 1 FROM projects WHERE id=?', (row['scope'],)).fetchone():
                    raise ValueError('Permission references an unknown project')
            for row in office.db.execute('SELECT * FROM business_project_statuses'):
                _id(row['id'])
                _text(row['name'], 'Statusname', 200, True)
                _integer(row['position'], 'Reihenfolge')
                if (not re.fullmatch(r'#[0-9A-F]{6}', row['color']) or row['revision'] < 1
                        or row['active'] not in (0, 1) or row['terminal'] not in (0, 1)):
                    raise ValueError('Invalid project status')
            for row in office.db.execute('SELECT * FROM business_project_profiles'):
                _id(row['project_id'])
                for field, maximum in (('project_number', 80), ('site_address', 2000), ('description', 10000)):
                    _text(row[field], field, maximum)
                if row['revision'] < 1:
                    raise ValueError('Invalid project profile')
                if row['status_id'] and not office.db.execute('SELECT 1 FROM business_project_statuses WHERE id=?', (row['status_id'],)).fetchone():
                    raise ValueError('Project references an unknown status')
            for row in office.db.execute('SELECT * FROM business_contact_extras'):
                if row['entity_type'] not in ('company', 'person') or row['revision'] < 1:
                    raise ValueError('Invalid contact extension')
                kinds, tags = json.loads(row['kinds_json']), json.loads(row['tags_json'])
                if not isinstance(kinds, list) or not kinds or len(set(kinds)) != len(kinds) or any(k not in CONTACT_KINDS for k in kinds) or not isinstance(tags, list):
                    raise ValueError('Invalid contact kinds')
                if row['erased_at']:
                    customer = office.db.execute('SELECT * FROM customers WHERE id=?', (row['customer_id'],)).fetchone()
                    if customer['active'] or any(customer[field] for field in ('contact', 'email', 'phone', 'address', 'notes')):
                        raise ValueError('Erased contact retains active personal data')
                    for table in ('business_contact_people', 'business_contact_addresses'):
                        if office.db.execute('SELECT 1 FROM ' + table + ' WHERE customer_id=?', (row['customer_id'],)).fetchone():
                            raise ValueError('Erased contact retains personal children')
            for row in office.db.execute('SELECT * FROM business_contact_people'):
                _id(row['id'])
                _text(row['name'], 'Ansprechpartner', 200, True)
                _text(row['role_label'], 'Rolle', 200)
                _text(row['phone'], 'Telefon', 100)
                if row['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', row['email']):
                    raise ValueError('Invalid contact person email')
            for row in office.db.execute('SELECT * FROM business_contact_addresses'):
                _id(row['id'])
                if row['purpose'] not in ('billing', 'site', 'delivery', 'other') or not re.fullmatch(r'[A-Z]{2}', row['country']):
                    raise ValueError('Invalid contact address')
            for row in office.db.execute('SELECT * FROM business_document_classes'):
                if row['classification'] not in CLASSES or row['revision'] < 1 or not re.fullmatch(r'[a-f0-9]{64}', row['content_fingerprint']):
                    raise ValueError('Invalid document classification')
            for row in office.db.execute('SELECT * FROM business_feed'):
                if row['visibility'] not in CLASSES or not isinstance(json.loads(row['refs_json']), dict):
                    raise ValueError('Invalid project feed event')
            for row in office.db.execute('SELECT * FROM business_foundation_requests'):
                _id(row['request_id'])
                if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']) or not isinstance(json.loads(row['result_json']), dict):
                    raise ValueError('Invalid business request receipt')
            for row in office.db.execute('SELECT * FROM business_privacy_requests'):
                if row['operation'] not in ('export', 'erase') or row['status'] not in ('review_required', 'blocked', 'erased'):
                    raise ValueError('Invalid privacy request')
                if row['status'] == 'erased' and (not row['checkpoint_digest'] or not re.fullmatch(r'[a-f0-9]{64}', row['checkpoint_digest'])):
                    raise ValueError('Erasure lacks an independent checkpoint')
        except (Problem, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError('Invalid business foundation data') from error
    return True


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'HTTP-Methode nicht erlaubt')
    service = BusinessFoundation(office)
    query = data.get('_query', {}) if method == 'GET' else {}
    if path == '/overview' and method == 'GET':
        with office.lock:
            actor = _fresh(office, actor)
            projects = service.pipeline(actor, query.get('q', ''))['items']
            return {'projects': projects, 'statuses': service.statuses(actor)['items'], 'counters': {'projects': len(projects)},
                    'can_create_project': actor['role'] == 'owner', 'can_read_inquiries': actor['role'] == 'owner'}, 200, 'application/json'
    if path == '/contacts':
        return (service.contacts(actor, query.get('q', ''), query.get('kind')), 200, 'application/json') if method == 'GET' else (service.save_contact(actor, data), 201, 'application/json')
    match = re.fullmatch(r'/contacts/([a-f0-9]{32})(?:/(export|erase))?', path)
    if match:
        identifier, action = match.groups()
        if action == 'export' and method == 'GET':
            return service.export_contact(actor, identifier), 200, 'application/json'
        if action == 'erase' and method == 'POST':
            return service.erase_contact(actor, identifier, data), 200, 'application/json'
        if action is None:
            return (service.contact(actor, identifier), 200, 'application/json') if method == 'GET' else (service.save_contact(actor, data, identifier), 200, 'application/json')
    if path == '/project-statuses':
        return (service.statuses(actor), 200, 'application/json') if method == 'GET' else (service.save_status(actor, data), 201, 'application/json')
    match = re.fullmatch(r'/project-statuses/([a-f0-9]{32})', path)
    if match and method == 'POST':
        return service.save_status(actor, data, match[1]), 200, 'application/json'
    match = re.fullmatch(r'/projects/([a-f0-9]{32})/profile', path)
    if match:
        return (service.project(actor, match[1]), 200, 'application/json') if method == 'GET' else (service.save_project(actor, match[1], data), 200, 'application/json')
    if path == '/feed':
        return (service.feed(actor, query.get('project_id')), 200, 'application/json') if method == 'GET' else (service.post_message(actor, data), 201, 'application/json')
    match = re.fullmatch(r'/documents/(link|mail)/([a-f0-9]{32})/classification', path)
    if match and method in ('GET', 'POST'):
        kind, identifier = match.groups()
        if kind == 'link':
            row = office.db.execute("SELECT project_id FROM workspace_items WHERE id=? AND kind='links'", (identifier,)).fetchone()
        else:
            row = office.db.execute('SELECT i.project_id FROM inquiries i JOIN inquiry_attachments a ON a.inquiry_id=i.id WHERE a.id=?', (identifier,)).fetchone()
        if not row or not row['project_id']:
            raise Problem(404, 'Dokument nicht verfügbar')
        if method == 'GET':
            service.authorize(actor, 'documents.classify', row['project_id'])
            return service.classification(actor, row['project_id'], kind, identifier), 200, 'application/json'
        return service.classify(actor, row['project_id'], kind, identifier, data), 200, 'application/json'
    if path == '/settings/permissions':
        return (service.grants(actor), 200, 'application/json') if method == 'GET' else (service.save_grant(actor, data), 200, 'application/json')
    return None


def methods(path):
    routes = (
        (r'/overview', 'GET'), (r'/contacts', 'GET, POST'),
        (r'/contacts/[a-f0-9]{32}', 'GET, POST'),
        (r'/contacts/[a-f0-9]{32}/export', 'GET'),
        (r'/contacts/[a-f0-9]{32}/erase', 'POST'),
        (r'/project-statuses', 'GET, POST'),
        (r'/project-statuses/[a-f0-9]{32}', 'POST'),
        (r'/projects/[a-f0-9]{32}/profile', 'GET, POST'),
        (r'/feed', 'GET, POST'),
        (r'/documents/(?:link|mail)/[a-f0-9]{32}/classification', 'GET, POST'),
        (r'/settings/permissions', 'GET, POST'),
    )
    return next((allowed for pattern, allowed in routes if re.fullmatch(pattern, path)), None)
