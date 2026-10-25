"""Bounded local interchange profiles and a separate website lead delivery API.

Partner protocols without an agreed authenticated contract stay unavailable.
Accounting mappings and GAEB inspection explicitly require external validation;
they are never advertised as native DATEV/Lexware or certified GAEB imports.
Only ENV reference names, hashes and source IDs are stored as credentials.
"""
import base64
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import hmac
import io
import ipaddress
import json
import math
import os
import re
import sqlite3
import string
import time
import uuid
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit

from core import Problem, canonical
from business_foundation import require_permission
from inquiries import Inquiries, _transaction


MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000
SUPPLIERS = {
    'granzow': {'name': 'Granzow', 'protocol_state': 'unverified', 'live_access': False,
                'feature': 'external.granzow', 'verified_protocols': [], 'candidate_support_url': 'https://www.granzow.de/', 'url_verified': False},
    'alexander_buerkle': {'name': 'Alexander Bürkle', 'protocol_state': 'unverified', 'live_access': False,
                         'feature': 'external.alexander_buerkle', 'verified_protocols': [], 'candidate_support_url': 'https://alexander-buerkle.com/', 'url_verified': False},
}
PROFILES = {
    'website_lead_v1': {'label': 'Website-Anfrage', 'supported': True, 'import': True, 'export': False,
                        'feature': 'external.website_leads', 'scope': 'server_to_server_only'},
    'catalog_csv_v1': {'label': 'Smartplan Artikel-CSV v1', 'supported': True, 'import': True, 'export': True,
                       'scope': 'code;name;unit;cost_price_net;unit_price_net;tax_rate, UTF-8'},
    'datanorm_a14_cp850_v1': {'label': 'DATANORM A14-Prüfprofil', 'supported': True, 'import': True, 'export': False,
        'scope': 'Nur A-Neuanlagen, CP850, 14 Felder; Rohpreis/Basis erhalten. Keine Rabatte, B/P/T/R/Löschsätze oder vollständige DATANORM-Version zugesichert.'},
    'gaeb_x83_inspect_v1': {'label': 'GAEB XML 3.2/3.3 X83-Prüfansicht', 'supported': True, 'import': True, 'export': True,
        'scope': 'Positions-/Mengenprüfung, keine offizielle XSD-Konformitätszusage oder X84/Rechnungs-/Nachtragsunterstützung.'},
    'datev_review_csv_v1': {'label': 'DATEV-Übergabemapping zur Prüfung', 'supported': True, 'import': False, 'export': True,
        'scope': 'Abgestimmtes Prüf-CSV mit Konten/Steuerschlüssel und Herkunft. Kein natives DATEV-EXTF und keine Importabnahme.'},
    'lexware_review_json_v1': {'label': 'Lexware-Übergabemapping zur Prüfung', 'supported': True, 'import': False, 'export': True,
        'scope': 'Versioniertes Rechnungs-/Zahlungsmapping mit Herkunft. Keine Lexware-API-Zustellung oder Zahlungsüberwachung.'},
    **{name: {'label': label, 'supported': False, 'import': False, 'export': False,
              'scope': 'Anbieter-/Versionsvertrag, Authentifizierung und echte Sandboxabnahme fehlen; keine Verbindung aktiviert.'}
       for name, label in (('ugl_partner', 'UGL'), ('ids_connect_partner', 'IDS Connect'),
                          ('oci_partner', 'OCI'), ('shk_connect_partner', 'SHK Connect'),
                          ('aroundhome_partner', 'Aroundhome'), ('taptaphome_partner', 'TapTapHome'))},
}
_ID = re.compile(r'[a-f0-9]{32}')
_ENV = re.compile(r'SMARTPLAN_[A-Z0-9_]{1,100}')
_LEAD_CREDENTIAL = re.compile(r'SPLD_[A-Za-z0-9_-]{43}')
_CSV_FIELDS = ('code', 'name', 'unit', 'cost_price_net', 'unit_price_net', 'tax_rate')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_adapters(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, profile TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
          secret_ref TEXT UNIQUE, revision INTEGER NOT NULL CHECK(revision>0),
          owner_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_adapter_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
          result_json TEXT NOT NULL, PRIMARY KEY(user_id,request_id))''',
        '''CREATE TABLE IF NOT EXISTS business_adapter_suppliers(
          adapter_id TEXT PRIMARY KEY REFERENCES business_adapters(id),
          supplier TEXT NOT NULL CHECK(supplier IN ('granzow','alexander_buerkle')))''',
        '''CREATE TABLE IF NOT EXISTS business_adapter_runs(
          id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL REFERENCES business_adapters(id), profile TEXT NOT NULL,
          status TEXT NOT NULL, source_sha256 TEXT NOT NULL, rows_json TEXT NOT NULL, rows_sha256 TEXT NOT NULL, result_json TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_adapter_articles(
          adapter_id TEXT NOT NULL REFERENCES business_adapters(id), source_code TEXT NOT NULL,
          article_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, PRIMARY KEY(adapter_id,source_code))''',
        '''CREATE TABLE IF NOT EXISTS business_leads(
          id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL REFERENCES business_adapters(id), external_id TEXT NOT NULL,
          inquiry_id TEXT NOT NULL REFERENCES inquiries(id), content_sha256 TEXT NOT NULL, received_at TEXT NOT NULL,
          UNIQUE(adapter_id,external_id))''',
        '''CREATE TABLE IF NOT EXISTS business_lead_limits(
          adapter_id TEXT PRIMARY KEY REFERENCES business_adapters(id), window_started DOUBLE PRECISION NOT NULL,
          window_count INTEGER NOT NULL CHECK(window_count>=0 AND window_count<=30))''',
        '''CREATE TABLE IF NOT EXISTS business_contact_form_limits(
          scope TEXT PRIMARY KEY, window_started DOUBLE PRECISION NOT NULL,
          window_count INTEGER NOT NULL CHECK(window_count>=0 AND window_count<=50))''',
        '''CREATE TABLE IF NOT EXISTS business_lead_reply_templates(
          id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL REFERENCES business_adapters(id),
          revision INTEGER NOT NULL CHECK(revision>0), subject TEXT NOT NULL, text TEXT NOT NULL,
          enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), approved_by TEXT NOT NULL REFERENCES users(id),
          approved_at TEXT NOT NULL, UNIQUE(adapter_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_lead_reply_outbox(
          id TEXT PRIMARY KEY, adapter_id TEXT NOT NULL REFERENCES business_adapters(id),
          inquiry_id TEXT NOT NULL UNIQUE REFERENCES inquiries(id), template_id TEXT NOT NULL REFERENCES business_lead_reply_templates(id),
          operation_id TEXT NOT NULL UNIQUE, job_json TEXT NOT NULL, content_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_lead_reply_receipts(
          id TEXT PRIMARY KEY, outbox_id TEXT NOT NULL REFERENCES business_lead_reply_outbox(id), operation_id TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('sending','accepted','unknown','failed')), ordinal INTEGER NOT NULL CHECK(ordinal>0),
          receipt_id TEXT, error_code TEXT, at TEXT NOT NULL, UNIQUE(outbox_id,ordinal))''',
        'CREATE INDEX IF NOT EXISTS business_adapter_runs_source ON business_adapter_runs(adapter_id,created_at,id)',
    ]


def protected_tables():
    return ('business_adapter_requests', 'business_leads', 'business_adapter_suppliers',
            'business_lead_reply_templates', 'business_lead_reply_outbox', 'business_lead_reply_receipts')


def runtime_privileges():
    return {**{table: ('SELECT', 'INSERT', 'UPDATE') for table in
            ('business_adapters', 'business_adapter_runs', 'business_adapter_articles', 'business_lead_limits')},
            'business_contact_form_limits': ('SELECT', 'INSERT', 'UPDATE', 'DELETE')}


def ensure_sqlite_schema(office):
    if isinstance(office.db, sqlite3.Connection):
        with _transaction(office):
            for statement in schema_statements('BLOB'):
                office.db.execute(statement)


def _id(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise Problem(400, 'Gültige Objekt-ID erwartet')
    return value


def _text(value, field, maximum=300, required=True):
    if (not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or required and not value.strip()):
        raise Problem(400, 'Ungültiges Feld: ' + field)
    return value.strip()


def _hash(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode('utf-8')).hexdigest()


def _decimal(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,4})?', value):
        raise Problem(400, 'Nichtnegative begrenzte Dezimalzeichenfolge erwartet')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise Problem(400, 'Ungültige Dezimalzahl') from None
    if not amount.is_finite():
        raise Problem(400, 'Ungültige Dezimalzahl')
    return amount


def _bytes(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise Problem(413, 'Datei muss zwischen 1 Byte und 2 MiB groß sein')
    if b'\x00' in raw:
        raise Problem(400, 'Binärinhalt im Textformat ist nicht zulässig')
    return raw


def _decode64(value):
    if not isinstance(value, str) or len(value) > 4 * ((MAX_BYTES + 2) // 3):
        raise Problem(413, 'Importdatei ist zu groß')
    try:
        return _bytes(base64.b64decode(value, validate=True))
    except (ValueError, TypeError):
        raise Problem(400, 'Gültige Base64-Datei erwartet') from None


def _origin(value):
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError('Invalid origin')
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError('Explicit HTTPS origin required')
    port = parsed.port
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Invalid origin port')
    host = '[' + parsed.hostname.lower() + ']' if ':' in parsed.hostname else parsed.hostname.lower()
    return 'https://' + host + (':' + str(port) if port not in (None, 443) else '')


def parse_catalog(profile, raw):
    _bytes(raw)
    try:
        text = raw.decode('cp850' if profile == 'datanorm_a14_cp850_v1' else 'utf-8-sig')
    except UnicodeError:
        raise Problem(400, 'Zeichensatz passt nicht zum vereinbarten Profil') from None
    rows, codes = [], set()
    if profile == 'catalog_csv_v1':
        reader = csv.DictReader(io.StringIO(text), delimiter=';', strict=True)
        if reader.fieldnames != list(_CSV_FIELDS):
            raise Problem(400, 'Exakte Artikel-CSV-Spalten und Reihenfolge erforderlich')
        try:
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise Problem(400, 'CSV-Zeile besitzt falsche Spaltenanzahl')
                item = {field: _text(_unspreadsheet(row[field]), field, 100 if field == 'code' else 500) for field in ('code', 'name', 'unit')}
                for field in ('cost_price_net', 'unit_price_net', 'tax_rate'):
                    _decimal(row[field])
                    item[field] = row[field]
                if Decimal(item['tax_rate']) > 100:
                    raise Problem(400, 'Steuersatz muss zwischen 0 und 100 liegen')
                rows.append(item)
        except csv.Error:
            raise Problem(400, 'Ungültige CSV-Struktur') from None
    elif profile == 'datanorm_a14_cp850_v1':
        for line in text.splitlines():
            if not line.strip():
                continue
            fields = line.split(';')
            if fields[0] != 'A':
                raise Problem(415, 'Dieses Prüfprofil unterstützt nur A-Neuanlagen, keine B/P/T/R- oder Löschsätze')
            if len(fields) != 14 or fields[1] != 'N' or fields[6] not in ('1', '2') or fields[7] not in ('0', '1', '2', '3'):
                raise Problem(400, 'Nicht unterstützter DATANORM-A14-Satz')
            if not re.fullmatch(r'[0-9]{1,14}', fields[9]):
                raise Problem(400, 'Ganzzahliger DATANORM-Rohpreis erwartet')
            rows.append({'code': _text(fields[2], 'Artikelnummer', 100),
                         'name': _text(' '.join(part.strip() for part in fields[4:6] if part.strip()), 'Artikeltext', 500),
                         'unit': _text(fields[8], 'Einheit', 30), 'source_price_integer': fields[9],
                         'price_basis': str(10 ** int(fields[7])), 'price_flag': fields[6],
                         'discount_group': fields[10], 'article_group': fields[11], 'long_text_key': fields[12]})
    else:
        raise Problem(415, 'Kein unterstütztes Artikelimportprofil')
    if not rows or len(rows) > MAX_ROWS:
        raise Problem(413, 'Zwischen 1 und 2000 Positionen erforderlich')
    for row in rows:
        if row['code'] in codes:
            raise Problem(400, 'Doppelte Artikelnummer innerhalb derselben Datei')
        codes.add(row['code'])
    return rows


def inspect_gaeb(raw):
    _bytes(raw)
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise Problem(400, 'DTD und Entities sind nicht zulässig')
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        raise Problem(400, 'Ungültige XML-Struktur') from None
    match = re.fullmatch(r'\{http://www\.gaeb\.de/GAEB_DA_XML/DA83/(3\.[23])\}GAEB', root.tag)
    if not match:
        raise Problem(415, 'Prüfansicht unterstützt nur GAEB XML DA83 Version 3.2/3.3')
    version = match[1]
    namespace = 'http://www.gaeb.de/GAEB_DA_XML/DA83/' + version
    def find(node, name):
        return node.find('.//{' + namespace + '}' + name)
    def text(node, name, default=''):
        item = find(node, name)
        return ''.join(item.itertext()).strip() if item is not None else default
    phase = text(root, 'DP')
    if phase != '83' or len(root.findall('.//{' + namespace + '}DP')) != 1:
        raise Problem(415, 'Nur Austauschphase 83 wird inspiziert')
    stack, count = [(root, 0)], 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 15000 or depth > 40:
            raise Problem(413, 'XML-Struktur überschreitet die Prüfgrenzen')
        stack.extend((child, depth + 1) for child in node)
    # An inspection may display unknown commercial constructs, but converting
    # them into a flat offer would silently sum alternatives or discard price
    # references. Only this explicitly recognized simple-position tree can be
    # used for a priced draft/review export. This is not an XSD validator.
    unsupported = set()
    children = {'GAEB': {'GAEBInfo', 'PrjInfo', 'Award'}, 'Award': {'DP', 'BoQ'},
                'BoQ': {'BoQBody'}, 'BoQBody': {'BoQCtgy', 'Itemlist'},
                'BoQCtgy': {'LblTx', 'BoQBody'}, 'Itemlist': {'Item'},
                'Item': {'Qty', 'QU', 'Description'}, 'DP': set(), 'Qty': set(), 'QU': set()}
    attributes = {'BoQ': {'ID'}, 'BoQCtgy': {'ID', 'RNoPart'}, 'Item': {'ID', 'RNoPart'}}
    def inspect_structure(node):
        name = node.tag.rsplit('}', 1)[-1]
        if name in ('GAEBInfo', 'PrjInfo', 'Description', 'LblTx'):
            return  # Metadata/plain displayed text do not determine totals.
        for attribute in node.attrib:
            if attribute not in attributes.get(name, set()):
                unsupported.add((name + '@' + attribute)[:150])
        for child in node:
            child_name = child.tag.rsplit('}', 1)[-1]
            if child.tag != '{' + namespace + '}' + child_name or child_name not in children.get(name, set()):
                unsupported.add((name + '/' + child_name)[:150])
            inspect_structure(child)
        if name == 'Item' and any(len(node.findall('{' + namespace + '}' + field)) != 1 for field in ('Qty', 'QU', 'Description')):
            unsupported.add('Item/ambiguous-required-field')
    inspect_structure(root)
    items = []
    for node in root.iter('{' + namespace + '}Item'):
        quantity = text(node, 'Qty')
        _decimal(quantity)
        items.append({'source_id': _text(node.attrib.get('ID', ''), 'GAEB-Positions-ID', 100),
                      'code': _text(node.attrib.get('RNoPart', ''), 'Ordnungszahl', 100),
                      'name': _text(' '.join(text(node, 'Description').split()), 'Positionstext', 10000),
                      'quantity': quantity, 'unit': _text(text(node, 'QU'), 'Einheit', 30)})
    if not items or len(items) > MAX_ROWS or len({item['source_id'] for item in items}) != len(items):
        raise Problem(400, 'Eindeutige, begrenzte Positionen erforderlich')
    return {'phase': phase, 'version': version, 'official_schema_validated': False, 'items': items,
            'review_required': True, 'simple_positions_supported': not unsupported,
            'unsupported_semantics': sorted(unsupported)[:100],
            'limitation': 'Strukturinspektion; keine offizielle GAEB-XSD-Konformitätsprüfung oder vollständige Langtextabbildung.'}


def _require_simple_gaeb(run):
    if run['result'].get('simple_positions_supported') is not True or run['result'].get('unsupported_semantics') != []:
        raise Problem(409, 'Unbekannte GAEB-Alternativ-/Referenz-/Positionssemantik; nur prüfen, nicht summieren oder verkürzt exportieren')


class Adapters:
    def __init__(self, office, *, environ=None, feature=None, clock=time.time):
        self.office, self.db, self.environ, self.clock = office, office.db, os.environ if environ is None else environ, clock
        if feature is None:
            from business_schema import feature_enabled
            feature = lambda name: feature_enabled(office, name)
        self.feature = feature

    def _now(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat(timespec='seconds')

    def _row(self, identifier):
        row = self.db.execute('SELECT * FROM business_adapters WHERE id=?', (_id(identifier),)).fetchone()
        if not row:
            raise Problem(404, 'Adapter nicht verfügbar')
        return row

    def _record(self, row):
        supplier = self.db.execute('SELECT supplier FROM business_adapter_suppliers WHERE adapter_id=?', (row['id'],)).fetchone()
        return dict(row, enabled=bool(row['enabled']), profile_info=dict(PROFILES[row['profile']]),
                    supplier=supplier['supplier'] if supplier else None,
                    supplier_info=dict(SUPPLIERS[supplier['supplier']]) if supplier else None,
                    connection_state='not_connected', live_verified=False)

    def _request(self, actor, operation, data):
        identifier = _id(data.get('request_id'))
        try:
            fingerprint = _hash({'operation': operation, 'data': data})
        except (ValueError, TypeError, UnicodeError):
            raise Problem(400, 'Gültige JSON-Daten erwartet') from None
        row = self.db.execute('SELECT * FROM business_adapter_requests WHERE user_id=? AND request_id=?', (actor['id'], identifier)).fetchone()
        if row and row['request_hash'] != fingerprint:
            raise Problem(409, 'Vorgangs-ID gehört zu anderem Inhalt')
        return identifier, fingerprint, json.loads(row['result_json']) if row else None

    def _remember(self, actor, request, fingerprint, result):
        self.db.execute('INSERT INTO business_adapter_requests(user_id,request_id,request_hash,result_json) VALUES(?,?,?,?)',
                        (actor['id'], request, fingerprint, canonical(result)))

    def list(self, actor):
        with self.office.lock:
            require_permission(self.office, actor, 'settings.manage')
            return {'items': [self._record(row) for row in self.db.execute('SELECT * FROM business_adapters ORDER BY name,id')],
                    'profiles': [{'id': key, **value} for key, value in PROFILES.items()],
                    'suppliers': [{'id': key, **value} for key, value in SUPPLIERS.items()]}

    def save(self, actor, data, identifier=None):
        if not isinstance(data, dict) or set(data) - {'request_id', 'revision', 'name', 'profile', 'enabled', 'secret_ref', 'supplier'}:
            raise Problem(400, 'Nur Adapterkonfiguration mit ENV-Referenz erwartet; keine Zugangswerte')
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'settings.manage')
            request, fingerprint, previous = self._request(actor, 'configure:' + str(identifier), data)
            if previous:
                return self._record(self._row(previous['id']))
            current = self._row(identifier) if identifier else None
            if current and (type(data.get('revision')) is not int or data['revision'] != current['revision']):
                raise Problem(409, 'Adapter wurde inzwischen geändert')
            profile = data.get('profile', current['profile'] if current else None)
            if not isinstance(profile, str) or profile not in PROFILES:
                raise Problem(400, 'Bekanntes versioniertes Adapterprofil erforderlich')
            if current and current['profile'] != profile:
                raise Problem(409, 'Adapterprofil ist unveränderlich; neue Quelle separat anlegen')
            enabled = data.get('enabled', bool(current['enabled']) if current else False)
            if type(enabled) is not bool:
                raise Problem(400, 'Aktivstatus erwartet')
            if enabled and not PROFILES[profile]['supported']:
                raise Problem(409, 'Anbietervertrag und unterstütztes Austauschprofil fehlen')
            name = _text(data.get('name', current['name'] if current else ''), 'Adaptername', 100)
            ref = data.get('secret_ref', current['secret_ref'] if current else None)
            if ref is not None and (not isinstance(ref, str) or not _ENV.fullmatch(ref)):
                raise Problem(400, 'Ausschließlich eine SMARTPLAN_ENV_REFERENZ ist zulässig')
            if profile == 'website_lead_v1' and not ref:
                raise Problem(400, 'Geschützte serverseitige ENV-Referenz erforderlich')
            if profile == 'website_lead_v1' and current is None and actor['role'] != 'owner':
                raise Problem(403, 'Website-Eingänge verbindet die Geschäftsführung mit ihrem Anfragebereich')
            supplier_old = self.db.execute('SELECT supplier FROM business_adapter_suppliers WHERE adapter_id=?', (identifier,)).fetchone() if identifier else None
            supplier = data.get('supplier', supplier_old['supplier'] if supplier_old else None)
            if supplier is not None:
                if not isinstance(supplier, str) or supplier not in SUPPLIERS:
                    raise Problem(400, 'Großhändler Granzow oder Alexander Bürkle auswählen')
                if profile not in ('catalog_csv_v1', 'datanorm_a14_cp850_v1', 'ugl_partner', 'ids_connect_partner', 'oci_partner', 'shk_connect_partner'):
                    raise Problem(400, 'Großhändlerbindung nur für Material-/Handelsprofile')
            if current and (supplier_old['supplier'] if supplier_old else None) != supplier:
                if supplier_old or self.db.execute('SELECT 1 FROM business_adapter_runs WHERE adapter_id=?', (identifier,)).fetchone():
                    raise Problem(409, 'Lieferantenherkunft nach Übernahmen unveränderlich; neue Importquelle anlegen')
            identifier, stamp = identifier or uuid.uuid4().hex, self._now()
            try:
                if current:
                    self.db.execute('UPDATE business_adapters SET name=?,enabled=?,secret_ref=?,revision=revision+1,updated_at=? WHERE id=?',
                                    (name, int(enabled), ref, stamp, identifier))
                else:
                    self.db.execute('INSERT INTO business_adapters(id,name,profile,enabled,secret_ref,revision,owner_id,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?,?)',
                                    (identifier, name, profile, int(enabled), ref, actor['id'], stamp, stamp))
            except self.office.integrity_error:
                raise Problem(409, 'Diese Zugangsbinding wird bereits von einer anderen Quelle verwendet') from None
            if supplier is not None and not supplier_old:
                self.db.execute('INSERT INTO business_adapter_suppliers(adapter_id,supplier) VALUES(?,?)', (identifier, supplier))
            self.office.audit(actor, 'business.adapter.configured', identifier)
            self._remember(actor, request, fingerprint, {'id': identifier})
            return self._record(self._row(identifier))

    def receive_lead(self, identifier, token, envelope):
        failure = None
        with _transaction(self.office):
            row = self._row(identifier)
            if row['profile'] != 'website_lead_v1' or not row['enabled'] or not self.feature('external.website_leads'):
                raise Problem(409, 'Website-Eingang ist nicht freigegeben')
            secret = self.environ.get(row['secret_ref'], '')
            if not isinstance(secret, str) or not _LEAD_CREDENTIAL.fullmatch(secret):
                raise Problem(409, 'Geschützte serverseitige Zugangsbinding fehlt')
            if (not isinstance(token, str) or not _LEAD_CREDENTIAL.fullmatch(token) or not hmac.compare_digest(token, secret)):
                raise Problem(401, 'Ungültiger Website-Einlieferungszugang')
            actor_row = self.db.execute("SELECT id,email,role,active FROM users WHERE id=?", (row['owner_id'],)).fetchone()
            if not actor_row or actor_row['active'] != 1 or actor_row['role'] != 'owner':
                raise Problem(401, 'Quelle ist nicht mehr freigegeben')
            actor = {key: actor_row[key] for key in ('id', 'email', 'role')}
            now = self.clock()
            rate = self.db.execute('SELECT * FROM business_lead_limits WHERE adapter_id=?', (identifier,)).fetchone()
            live = rate is not None and now < rate['window_started'] + 60
            count = rate['window_count'] if live else 0
            if count >= 30:
                raise Problem(429, 'Website-Anfragen später erneut übermitteln')
            self.db.execute('INSERT INTO business_lead_limits(adapter_id,window_started,window_count) VALUES(?,?,?) '
                            'ON CONFLICT(adapter_id) DO UPDATE SET window_started=excluded.window_started,window_count=excluded.window_count',
                            (identifier, rate['window_started'] if live else now, count + 1))
            try:
                with _transaction(self.office):
                    result = self._lead(actor, row, envelope)
            except Problem as error:
                failure = error
        if failure:
            raise failure
        return result

    def _lead(self, actor, adapter, envelope):
        allowed = {'external_id', 'subject', 'message', 'sender_name', 'sender_email', 'sender_phone', 'received_at', 'privacy_notice_version'}
        if not isinstance(envelope, dict) or set(envelope) - allowed:
            raise Problem(400, 'Begrenzte Website-Anfrage erwartet')
        external_id = _text(envelope.get('external_id'), 'Stabile externe Anfrage-ID', 200)
        try:
            raw = json.dumps(envelope, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        except (ValueError, TypeError, UnicodeError):
            raise Problem(400, 'Gültige JSON-Anfrage erwartet') from None
        if len(raw) > 200000:
            raise Problem(413, 'Anfrage ist zu groß')
        fingerprint = _hash(raw)
        old = self.db.execute('SELECT * FROM business_leads WHERE adapter_id=? AND external_id=?', (adapter['id'], external_id)).fetchone()
        if old:
            if old['content_sha256'] != fingerprint:
                raise Problem(409, 'Externe Anfrage-ID gehört zu geändertem Inhalt')
            return {'id': old['inquiry_id'], 'status': 'received'}
        notice = _text(envelope.get('privacy_notice_version', ''), 'Datenschutzhinweisversion', 100, False)
        normalized = {key: value for key, value in envelope.items() if key not in ('external_id', 'privacy_notice_version')}
        normalized.update(source='import', source_account='lead:' + adapter['id'], source_id=external_id,
                          request_id=_hash(('lead:' + adapter['id'] + ':' + external_id).encode())[:32])
        inquiry = Inquiries(self.office)._create(actor, normalized, provenance={
            'format': 'website_lead_v1', 'attachments': [], 'warnings': [], 'adapter_id': adapter['id'],
            'external_id': external_id, 'privacy_notice_version': notice})
        self.db.execute('INSERT INTO business_leads(id,adapter_id,external_id,inquiry_id,content_sha256,received_at) VALUES(?,?,?,?,?,?)',
                        (uuid.uuid4().hex, adapter['id'], external_id, inquiry['id'], fingerprint, self._now()))
        return {'id': inquiry['id'], 'status': 'received'}

    def _owner(self, actor):
        actor = require_permission(self.office, actor, 'settings.manage')
        if actor['role'] != 'owner':
            raise Problem(403, 'Anfragevorlagen und Kundennachrichten verwaltet die Geschäftsführung')
        return actor

    def reply_template(self, actor, adapter_id):
        with self.office.lock:
            self._owner(actor)
            adapter = self._row(adapter_id)
            if adapter['profile'] != 'website_lead_v1':
                raise Problem(400, 'Website-Anfragequelle erforderlich')
            row = self.db.execute('SELECT * FROM business_lead_reply_templates WHERE adapter_id=? ORDER BY revision DESC LIMIT 1', (adapter_id,)).fetchone()
            return dict(row, enabled=bool(row['enabled']), approved=True) if row else {
                'id': None, 'adapter_id': adapter_id, 'revision': 0, 'subject': '', 'text': '', 'enabled': False, 'approved': False}

    def approve_reply_template(self, actor, adapter_id, data):
        if (not isinstance(data, dict) or set(data) != {'request_id', 'revision', 'subject', 'text', 'approved', 'enabled'}
                or data['approved'] is not True or type(data['enabled']) is not bool):
            raise Problem(400, 'Vorlage, Ausgangsversion und ausdrückliche Freigabe erforderlich')
        with _transaction(self.office):
            actor = self._owner(actor)
            request, fingerprint, previous = self._request(actor, 'reply-template:' + adapter_id, data)
            if previous:
                row = self.db.execute('SELECT * FROM business_lead_reply_templates WHERE id=?', (previous['id'],)).fetchone()
                return dict(row, enabled=bool(row['enabled']), approved=True)
            current = self.reply_template(actor, adapter_id)
            if type(data['revision']) is not int or data['revision'] != current['revision']:
                raise Problem(409, 'Vorlage wurde inzwischen geändert')
            subject = _text(data['subject'], 'Antwortbetreff', 200)
            text = data['text']
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 10000 or '\x00' in text:
                raise Problem(400, 'Begrenzter Antworttext erforderlich')
            for value in (subject, text):
                try:
                    for _, field, spec, conversion in string.Formatter().parse(value):
                        if field is not None and (field not in ('sender_name', 'subject') or spec or conversion):
                            raise ValueError('unsupported variable')
                    maximum = value.format(sender_name='x' * 200, subject='x' * 300)
                except (ValueError, KeyError, AttributeError):
                    raise Problem(400, 'Nur Platzhalter {sender_name} und {subject} ohne Formatoptionen verwenden') from None
                if value is text and len(maximum) > 20000:
                    raise Problem(400, 'Antworttext kann mit Platzhaltern zu lang werden')
            identifier = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_lead_reply_templates(id,adapter_id,revision,subject,text,enabled,approved_by,approved_at) VALUES(?,?,?,?,?,?,?,?)',
                (identifier, adapter_id, current['revision'] + 1, subject, text.strip(), int(data['enabled']), actor['id'], self._now()))
            self.office.audit(actor, 'business.lead_reply.template_approved', identifier)
            self._remember(actor, request, fingerprint, {'id': identifier})
            return self.reply_template(actor, adapter_id)

    def _form_source(self, origin):
        if not self.feature('external.website_form'):
            raise Problem(409, 'Kontaktformular ist noch nicht ausdrücklich freigegeben')
        configured = self.environ.get('SMARTPLAN_CONTACT_ALLOWED_ORIGINS', '')
        if not isinstance(configured, str) or not configured.strip():
            raise Problem(409, 'Formularherkunft ist noch nicht eingerichtet')
        try:
            allowed = {_origin(value.strip()) for value in configured.split(',') if value.strip()}
            if not allowed or len(allowed) > 10:
                raise ValueError('bounded origin list')
        except (ValueError, Problem):
            raise Problem(409, 'Ausschließlich ausdrücklich bestätigte HTTPS-Formularherkünfte einrichten') from None
        try:
            incoming = _origin(origin)
        except (ValueError, Problem):
            raise Problem(403, 'Formularherkunft ist nicht freigegeben') from None
        if incoming not in allowed:
            raise Problem(403, 'Formularherkunft ist nicht freigegeben')
        identifier = self.environ.get('SMARTPLAN_CONTACT_ADAPTER_ID', '')
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise Problem(409, 'Formularquelle ist noch nicht eingerichtet')
        adapter = self._row(identifier)
        credential = self.environ.get(adapter['secret_ref'], '') if adapter['secret_ref'] else ''
        if adapter['profile'] != 'website_lead_v1' or not isinstance(credential, str) or not _LEAD_CREDENTIAL.fullmatch(credential):
            raise Problem(409, 'Geschützte Formularquelle ist nicht vollständig eingerichtet')
        return adapter, credential

    def _form_rate(self, adapter_id, credential, remote_address):
        try:
            address = ipaddress.ip_address(remote_address).compressed
        except (ValueError, TypeError):
            raise Problem(400, 'Formularquelle konnte nicht sicher bestimmt werden') from None
        now = self.clock()
        self.db.execute('DELETE FROM business_contact_form_limits WHERE window_started<?', (now - 86400,))
        digest = hmac.new(credential.encode(), address.encode(), hashlib.sha256).hexdigest()
        for scope, seconds, maximum in (('ip:' + adapter_id + ':' + digest, 600, 5), ('global:' + adapter_id, 3600, 50)):
            row = self.db.execute('SELECT * FROM business_contact_form_limits WHERE scope=?', (scope,)).fetchone()
            live = row is not None and now < row['window_started'] + seconds
            count = row['window_count'] if live else 0
            if count >= maximum:
                raise Problem(429, 'Kontaktformular bitte später erneut verwenden')
            self.db.execute('INSERT INTO business_contact_form_limits(scope,window_started,window_count) VALUES(?,?,?) '
                'ON CONFLICT(scope) DO UPDATE SET window_started=excluded.window_started,window_count=excluded.window_count',
                (scope, row['window_started'] if live else now, count + 1))

    def receive_form(self, origin, remote_address, data):
        failure = None
        with _transaction(self.office):
            adapter, credential = self._form_source(origin)
            self._form_rate(adapter['id'], credential, remote_address)
            try:
                with _transaction(self.office):
                    allowed = {'request_id', 'subject', 'message', 'sender_name', 'sender_email', 'sender_phone', 'website', 'privacy_notice_version'}
                    if not isinstance(data, dict) or set(data) - allowed or data.get('website', '') != '':
                        raise Problem(400, 'Anfrage konnte nicht übernommen werden')
                    request_id = _id(data.get('request_id'))
                    from business_delivery import _address
                    _address(data.get('sender_email'))
                    envelope = {key: value for key, value in data.items() if key not in ('website', 'request_id')}
                    envelope.update(external_id=request_id)
                    receipt = self.receive_lead(adapter['id'], credential, envelope)
                    state = self._queue_reply(adapter, receipt['id'])
                    result = {**receipt, 'reply_status': state['status'], 'accepted_by_server': state.get('accepted_by_server', False),
                              'recipient_delivery_confirmed': False}
            except Problem as error:
                failure = error
        if failure:
            raise failure
        return result

    def public_form_receipt(self, inquiry_id):
        """Opaque continuation ID only: no contact, mail, template or source data."""
        with self.office.lock:
            lead = self.db.execute('SELECT inquiry_id FROM business_leads WHERE inquiry_id=?', (_id(inquiry_id),)).fetchone()
            if not lead:
                raise Problem(404, 'Eingangsquittung nicht verfügbar')
            outbox = self.db.execute('SELECT id FROM business_lead_reply_outbox WHERE inquiry_id=?', (inquiry_id,)).fetchone()
            return {'id': inquiry_id, 'status': self._reply_state(outbox['id'])['status'] if outbox else 'received'}

    def _reply_state(self, outbox_id):
        outbox = self.db.execute('SELECT inquiry_id,operation_id FROM business_lead_reply_outbox WHERE id=?', (_id(outbox_id),)).fetchone()
        if not outbox:
            raise Problem(404, 'Antwortversand nicht verfügbar')
        last = self.db.execute('SELECT * FROM business_lead_reply_receipts WHERE outbox_id=? ORDER BY ordinal DESC LIMIT 1', (outbox_id,)).fetchone()
        status = last['status'] if last else 'pending'
        if status == 'sending':
            status = 'unknown'
        return {'id': outbox_id, 'outbox_id': outbox_id, 'inquiry_id': outbox['inquiry_id'], 'status': status,
                'accepted_by_server': status == 'accepted', 'recipient_delivery_confirmed': False,
                'error_code': last['error_code'] if last else None}

    def _queue_reply(self, adapter, inquiry_id):
        old = self.db.execute('SELECT id FROM business_lead_reply_outbox WHERE inquiry_id=?', (inquiry_id,)).fetchone()
        if old:
            return self._reply_state(old['id'])
        if not self.feature('external.lead_autoreply'):
            return {'status': 'disabled'}
        template = self.db.execute('SELECT * FROM business_lead_reply_templates WHERE adapter_id=? ORDER BY revision DESC LIMIT 1', (adapter['id'],)).fetchone()
        if not template or not template['enabled']:
            return {'status': 'not_configured'}
        from business_delivery import _address
        try:
            sender = _address(self.environ.get('SMARTPLAN_SMTP_FROM', ''))
        except Problem:
            return {'status': 'not_configured'}
        inquiry = self.db.execute('SELECT sender_name,sender_email,subject FROM inquiries WHERE id=?', (inquiry_id,)).fetchone()
        variables = {'sender_name': inquiry['sender_name'], 'subject': inquiry['subject']}
        subject = template['subject'].format(**variables)
        if len(subject) > 300:
            subject = subject[:297] + '...'
        identifier, operation = uuid.uuid4().hex, uuid.uuid4().hex
        job = {'operation_id': operation, 'recipient': _address(inquiry['sender_email']), 'subject': subject,
               'text': template['text'].format(**variables), 'expected_sender': sender, 'attachments': []}
        self.db.execute('INSERT INTO business_lead_reply_outbox(id,adapter_id,inquiry_id,template_id,operation_id,job_json,content_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            (identifier, adapter['id'], inquiry_id, template['id'], operation, canonical(job), _hash(job), template['approved_by'], self._now()))
        actor = {'id': template['approved_by']}
        self.office.audit(actor, 'business.lead_reply.queued', identifier)
        return self._reply_state(identifier)

    def replies(self, actor):
        with self.office.lock:
            self._owner(actor)
            return {'items': [self._reply_state(row['id']) for row in self.db.execute('SELECT id FROM business_lead_reply_outbox ORDER BY created_at,id')]}

    def deliver_reply(self, actor, outbox_id, data, *, transport=None):
        if not isinstance(data, dict) or set(data) != {'request_id'}:
            raise Problem(400, 'Stabile Versandvorgangs-ID erwartet')
        with _transaction(self.office):
            actor = self._owner(actor)
            outbox = self.db.execute('SELECT * FROM business_lead_reply_outbox WHERE id=?', (_id(outbox_id),)).fetchone()
            if not outbox:
                raise Problem(404, 'Antwortversand nicht verfügbar')
            if not self.feature('external.lead_autoreply'):
                raise Problem(409, 'Automatische Eingangsantworten sind nicht freigegeben')
            adapter = self._row(outbox['adapter_id'])
            source = self.db.execute('SELECT active,role FROM users WHERE id=?', (adapter['owner_id'],)).fetchone()
            if not adapter['enabled'] or not source or source['active'] != 1 or source['role'] != 'owner':
                raise Problem(409, 'Anfragequelle ist nicht mehr freigegeben')
            current_template = self.db.execute('SELECT enabled FROM business_lead_reply_templates WHERE adapter_id=? ORDER BY revision DESC LIMIT 1', (adapter['id'],)).fetchone()
            if not current_template or not current_template['enabled']:
                raise Problem(409, 'Antwortvorlage ist deaktiviert')
            request_id, fingerprint, previous = self._request(actor, 'reply-send:' + outbox_id, data)
            state = self._reply_state(outbox_id)
            if previous or state['status'] != 'pending':
                return state
            from business_schema import require_financial_release
            require_financial_release(self.office)
            job = json.loads(outbox['job_json'])
            if _hash(job) != outbox['content_sha256']:
                raise Problem(409, 'Freigegebene Antwort ist beschädigt')
            if transport is None:
                if self.environ is not os.environ:
                    raise Problem(409, 'Geschützte SMTP-Prozesskonfiguration fehlt')
                from business_delivery import configured_transport, configuration
                if configuration(self.environ).sender != job['expected_sender']:
                    raise Problem(409, 'Freigegebener Absender wurde geändert')
                transport = configured_transport()
            self.db.execute('INSERT INTO business_lead_reply_receipts(id,outbox_id,operation_id,status,ordinal,at) VALUES(?,?,?,?,?,?)',
                (uuid.uuid4().hex, outbox_id, outbox['operation_id'], 'sending', 1, self._now()))
        from business_delivery import DeliveryReceipt
        try:
            receipt = transport.send(job)
        except Exception:
            receipt = DeliveryReceipt('unknown', job['operation_id'], error_code='delivery_unconfirmed')
        if (not isinstance(receipt, DeliveryReceipt) or receipt.operation_id != job['operation_id']
                or receipt.status not in ('accepted', 'failed', 'unknown')
                or receipt.status == 'accepted' and (not receipt.accepted_by_server or not receipt.receipt_id)):
            receipt = DeliveryReceipt('unknown', job['operation_id'], error_code='invalid_delivery_receipt')
        with _transaction(self.office):
            code = receipt.error_code if receipt.error_code in ('smtp_rejected', 'smtp_unavailable', 'delivery_unconfirmed', 'invalid_delivery_receipt') else None
            self.db.execute('INSERT INTO business_lead_reply_receipts(id,outbox_id,operation_id,status,ordinal,receipt_id,error_code,at) VALUES(?,?,?,?,?,?,?,?)',
                (uuid.uuid4().hex, outbox_id, job['operation_id'], receipt.status, 2,
                 _hash(str(receipt.receipt_id).encode()) if receipt.receipt_id else None, code, self._now()))
            self.office.audit(actor, 'business.lead_reply.' + receipt.status, outbox_id)
            self._remember(actor, request_id, fingerprint, {'id': outbox_id})
            state = self._reply_state(outbox_id)
        # The durable external outcome survives a concurrent role/session
        # revocation; fresh authorization is checked before publishing it.
        self._owner(actor)
        return state

    def _run(self, identifier):
        row = self.db.execute('SELECT * FROM business_adapter_runs WHERE id=?', (_id(identifier),)).fetchone()
        if not row:
            raise Problem(404, 'Adaptervorgang nicht verfügbar')
        if _hash(json.loads(row['rows_json'])) != row['rows_sha256']:
            raise Problem(409, 'Importpositionen haben ihre Integritätsprüfung nicht bestanden')
        return dict(id=row['id'], adapter_id=row['adapter_id'], profile=row['profile'], status=row['status'],
                    source_sha256=row['source_sha256'], rows=json.loads(row['rows_json']), result=json.loads(row['result_json']), created_at=row['created_at'])

    def import_data(self, actor, identifier, data):
        if not isinstance(data, dict) or set(data) != {'request_id', 'content_base64'}:
            raise Problem(400, 'Vorgangs-ID und Importdatei erwartet')
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'finance.write')
            adapter = self._row(identifier)
            if not adapter['enabled'] or not PROFILES[adapter['profile']]['import'] or adapter['profile'] == 'website_lead_v1':
                raise Problem(409, 'Kein aktiviertes lokales Dateiimportprofil')
            request, fingerprint, previous = self._request(actor, 'import:' + identifier, data)
            if previous:
                return self._run(previous['id'])
            raw = _decode64(data['content_base64'])
            if adapter['profile'] == 'gaeb_x83_inspect_v1':
                result = inspect_gaeb(raw)
                rows = result['items']
            else:
                rows, result = parse_catalog(adapter['profile'], raw), {'review_required': True}
                targets = {}
                for item in rows:
                    target = self.db.execute('SELECT article_id FROM business_adapter_articles WHERE adapter_id=? AND source_code=?',
                                             (identifier, item['code'])).fetchone()
                    if target:
                        revision = self.db.execute('SELECT revision FROM business_articles WHERE id=?', (target['article_id'],)).fetchone()
                        if not revision:
                            raise Problem(409, 'Artikelzuordnung ist unvollständig; zuerst prüfen')
                        targets[item['code']] = {'article_id': target['article_id'], 'revision': revision['revision']}
                result['target_revisions'] = targets
            run = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_adapter_runs(id,adapter_id,profile,status,source_sha256,rows_json,rows_sha256,result_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (run, identifier, adapter['profile'], 'staged', _hash(raw), canonical(rows), _hash(rows), canonical(result), actor['id'], self._now()))
            self.office.audit(actor, 'business.adapter.import_staged', run)
            self._remember(actor, request, fingerprint, {'id': run})
            return self._run(run)

    def apply_catalog(self, actor, run_id, data):
        if not isinstance(data, dict) or set(data) - {'request_id', 'confirmed', 'price_scale', 'target_price', 'tax_rate'} or data.get('confirmed') is not True:
            raise Problem(400, 'Artikelübernahme muss ausdrücklich bestätigt werden')
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'finance.write')
            run = self._run(run_id)
            adapter = self._row(run['adapter_id'])
            if not adapter['enabled'] or run['profile'] not in ('catalog_csv_v1', 'datanorm_a14_cp850_v1') or run['status'] not in ('staged', 'applied'):
                raise Problem(409, 'Kein freigegebener Artikelimport')
            request, fingerprint, previous = self._request(actor, 'apply:' + run_id, data)
            if previous or run['status'] == 'applied':
                return self._run(run_id)
            from business_documents import Documents
            articles = Documents(self.office)
            applied = []
            for item in run['rows']:
                values = {key: item[key] for key in ('code', 'name', 'unit')}
                if run['profile'] == 'catalog_csv_v1':
                    values.update({key: item[key] for key in ('cost_price_net', 'unit_price_net', 'tax_rate')})
                else:
                    if item['discount_group'] or item['long_text_key']:
                        raise Problem(409, 'Rabatt-/Langtextverweise benötigen vollständiges Lieferantenprofil')
                    if data.get('target_price') not in ('purchase_net', 'sales_net') or 'price_scale' not in data or 'tax_rate' not in data:
                        raise Problem(400, 'Rohpreisskalierung, Nettopreisziel und Steuersatz ausdrücklich zuordnen')
                    if _decimal(data['price_scale']) <= 0 or _decimal(data['tax_rate']) > 100:
                        raise Problem(400, 'Positive Skalierung und Steuersatz bis 100 erforderlich')
                    amount = Decimal(item['source_price_integer']) * _decimal(data['price_scale']) / Decimal(item['price_basis'])
                    price = format(amount.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP), 'f')
                    values.update(cost_price_net=price if data['target_price'] == 'purchase_net' else '0',
                                  unit_price_net=price if data['target_price'] == 'sales_net' else '0', tax_rate=str(_decimal(data['tax_rate'])))
                values.update(kind='material', currency='EUR', active=True)
                old = self.db.execute('SELECT * FROM business_adapter_articles WHERE adapter_id=? AND source_code=?',
                                      (adapter['id'], item['code'])).fetchone()
                expected = run['result'].get('target_revisions', {}).get(item['code'])
                if bool(old) != bool(expected) or old and old['article_id'] != expected['article_id']:
                    raise Problem(409, 'Artikelzuordnung hat sich seit der Importvorschau geändert; neu prüfen')
                prior_row = self.db.execute('SELECT revision,payload_json FROM business_articles WHERE id=?', (old['article_id'],)).fetchone() if old else None
                if old and (not prior_row or prior_row['revision'] != expected['revision']):
                    raise Problem(409, 'Artikel hat sich seit der Importvorschau geändert; neu prüfen')
                if old and run['profile'] == 'datanorm_a14_cp850_v1':
                    preserved = 'unit_price_net' if data['target_price'] == 'purchase_net' else 'cost_price_net'
                    values[preserved] = json.loads(prior_row['payload_json'])[preserved]
                source_hash = _hash(values)
                if old and old['source_sha256'] == source_hash:
                    if any(json.loads(prior_row['payload_json']).get(field) != value for field, value in values.items()):
                        raise Problem(409, 'Artikel wurde nach dem früheren Import manuell geändert; bewusste Preisprüfung erforderlich')
                    applied.append(old['article_id'])
                    continue
                if old:
                    article = self.db.execute('SELECT revision FROM business_articles WHERE id=?', (old['article_id'],)).fetchone()
                    if not article:
                        raise Problem(409, 'Artikelzuordnung erfordert Wiederherstellungsprüfung')
                    values['revision'] = article['revision']
                values['request_id'] = _hash((request + ':' + item['code']).encode())[:32]
                saved = articles.save_article(actor, values, old['article_id'] if old else None)
                self.db.execute('INSERT INTO business_adapter_articles(adapter_id,source_code,article_id,source_sha256) VALUES(?,?,?,?) '
                    'ON CONFLICT(adapter_id,source_code) DO UPDATE SET article_id=excluded.article_id,source_sha256=excluded.source_sha256',
                    (adapter['id'], item['code'], saved['id'], source_hash))
                applied.append(saved['id'])
            self.db.execute('UPDATE business_adapter_runs SET status=?,result_json=? WHERE id=?', ('applied', canonical({'article_ids': applied}), run_id))
            self.office.audit(actor, 'business.adapter.catalog_applied', run_id)
            self._remember(actor, request, fingerprint, {'id': run_id})
            return self._run(run_id)

    def create_offer_from_inspection(self, actor, run_id, data):
        allowed = {'request_id', 'confirmed', 'project_id', 'buyer', 'issue_date', 'due_date', 'position_prices', 'tax_rate'}
        if not isinstance(data, dict) or set(data) != allowed or data['confirmed'] is not True:
            raise Problem(400, 'Projekt, Kundensnapshot, Daten, Preise und Steuer ausdrücklich bestätigen')
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'finance.write', _id(data['project_id']))
            run = self._run(run_id)
            if run['profile'] != 'gaeb_x83_inspect_v1' or run['status'] != 'staged' or not self._row(run['adapter_id'])['enabled']:
                raise Problem(409, 'Aktiviertes GAEB-Positionsprüfprofil erforderlich')
            _require_simple_gaeb(run)
            request, fingerprint, previous = self._request(actor, 'gaeb-offer:' + run_id, data)
            from business_documents import Documents
            documents = Documents(self.office)
            if previous:
                return documents.get(actor, previous['id'])
            prices = data['position_prices']
            ids = {item['source_id'] for item in run['rows']}
            if not isinstance(prices, dict) or set(prices) != ids or _decimal(data['tax_rate']) > 100:
                raise Problem(400, 'Nettopreis für jede Quellposition und gültigen Steuersatz bestätigen')
            positions = []
            for item in run['rows']:
                _decimal(prices[item['source_id']])
                positions.append({'description': item['code'] + ' ' + item['name'], 'quantity': item['quantity'],
                    'unit': item['unit'], 'unit_price_net': prices[item['source_id']], 'tax_rate': data['tax_rate'], 'kind': 'material'})
            document = documents.create(actor, {'request_id': _hash(('offer:' + request).encode())[:32],
                'project_id': data['project_id'], 'kind': 'offer', 'title': 'Angebot aus geprüften GAEB-Positionen',
                'buyer': data['buyer'], 'issue_date': data['issue_date'], 'due_date': data['due_date'], 'positions': positions,
                'notes': 'Quelle: GAEB-Positionsprüfung ' + run_id + '. Keine offizielle GAEB-XSD-Importabnahme; Positionsumfang wurde ausdrücklich bestätigt.'})
            self.office.audit(actor, 'business.adapter.offer_created', document['id'])
            self._remember(actor, request, fingerprint, {'id': document['id']})
            return document

    def export_data(self, actor, identifier, data):
        if not isinstance(data, dict) or set(data) - {'request_id', 'document_ids', 'mapping', 'include_payments', 'import_id'}:
            raise Problem(400, 'Explizite Belegauswahl oder geprüfter Import für den Export erwartet')
        if 'include_payments' in data and type(data['include_payments']) is not bool:
            raise Problem(400, 'Zahlungsauswahl muss Wahrheitswert sein')
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'finance.read')
            adapter = self._row(identifier)
            profile = adapter['profile']
            if not adapter['enabled'] or not PROFILES[profile]['export']:
                raise Problem(409, 'Kein aktiviertes Exportprofil')
            if profile == 'gaeb_x83_inspect_v1':
                import_run = self._run(_id(data.get('import_id')))
                if import_run['adapter_id'] != identifier or import_run['profile'] != profile or import_run['status'] != 'staged':
                    raise Problem(409, 'Prüfexport gehört zu einem anderen Importprofil')
                _require_simple_gaeb(import_run)
            request, fingerprint, previous = self._request(actor, 'export:' + identifier, data)
            from business_documents import Documents
            documents = Documents(self.office)
            if previous:
                saved = self._run(previous['id'])
                for item in saved['result'].get('sources', []):
                    if item.get('document_id'):
                        documents.get(actor, item['document_id'])
                return saved
            sources = []
            if profile == 'catalog_csv_v1':
                output = io.StringIO(newline='')
                writer = csv.writer(output, delimiter=';', lineterminator='\r\n')
                writer.writerow(_CSV_FIELDS)
                rows = documents.articles(actor)['items']
                for item in rows:
                    _text(item['code'], 'Eindeutige Artikelnummer vor CSV-Export', 100)
                    writer.writerow([_spreadsheet(item[field]) for field in _CSV_FIELDS])
                raw, media, filename = output.getvalue().encode('utf-8-sig'), 'text/csv', 'smartplan-artikel-v1.csv'
                note = 'Smartplan Artikel-CSV v1; Formelzeichen in Textzellen werden für sichere Tabellenansicht maskiert.'
            elif profile == 'gaeb_x83_inspect_v1':
                run = self._run(_id(data.get('import_id')))
                if run['adapter_id'] != identifier or run['profile'] != profile or run['status'] != 'staged':
                    raise Problem(409, 'Prüfexport gehört zu einem anderen Importprofil')
                rows = run['rows']
                version = run['result'].get('version', '3.2')
                namespace = 'http://www.gaeb.de/GAEB_DA_XML/DA83/' + version
                def add(parent, tag, value=None, **attrs):
                    node = ET.SubElement(parent, '{' + namespace + '}' + tag, attrs)
                    if value is not None:
                        node.text = value
                    return node
                root = ET.Element('{' + namespace + '}GAEB')
                info = add(root, 'GAEBInfo')
                add(info, 'Version', version)
                add(info, 'ProgName', 'Smartplan Prüfexport – nicht XSD-validiert')
                award = add(root, 'Award')
                add(award, 'DP', '83')
                listing = add(add(add(award, 'BoQ', ID='smartplan-review-' + run['id'][:8]), 'BoQBody'), 'Itemlist')
                for item in rows:
                    node = add(listing, 'Item', ID=item['source_id'], RNoPart=item['code'])
                    add(node, 'Qty', item['quantity'])
                    add(node, 'QU', item['unit'])
                    add(add(add(add(node, 'Description'), 'CompleteText'), 'DetailTxt'), 'Text', item['name'])
                raw, media, filename = ET.tostring(root, encoding='utf-8', xml_declaration=True), 'application/xml', 'smartplan-gaeb-pruefexport.xml'
                # Verify the represented subset, without implying an official
                # exchange document or preserving unsupported rich text/levels.
                if inspect_gaeb(raw)['items'] != rows:
                    raise Problem(409, 'Positions-Roundtrip des Prüfexports ist fehlgeschlagen')
                sources = [{'import_id': run['id'], 'sha256': run['source_sha256']}]
                note = 'Positions-Prüfexport; keine offizielle GAEB-XSD-Prüfung, kein vollständiger Hierarchie-/Langtext-Roundtrip.'
            else:
                ids = data.get('document_ids')
                mapping = data.get('mapping')
                if (not isinstance(ids, list) or not ids or len(ids) > 200 or any(not isinstance(i, str) or not _ID.fullmatch(i) for i in ids)
                        or len(set(ids)) != len(ids) or not isinstance(mapping, dict)):
                    raise Problem(400, 'Eindeutige finale Belegauswahl und ausdrückliches Zielmapping erwartet')
                rows = []
                for document_id in ids:
                    item = documents.get(actor, document_id)
                    if item['status'] != 'final' or item['kind'] not in ('invoice', 'advance_invoice', 'cumulative_invoice', 'final_invoice', 'credit_note'):
                        raise Problem(409, 'Ausschließlich finale Rechnungen/Gutschriften können übergeben werden')
                    choice = mapping.get(document_id)
                    if not isinstance(choice, dict):
                        raise Problem(400, 'Explizites Mapping für jeden ausgewählten Beleg erforderlich')
                    sources.append({'document_id': document_id, 'sha256': item['payload_sha256'], 'number': item['number']})
                    if profile == 'datev_review_csv_v1':
                        if set(choice) != {'account', 'contra_account', 'tax_keys'} or not isinstance(choice['tax_keys'], dict):
                            raise Problem(400, 'Konto, Gegenkonto und Steuerschlüssel je Steuersatz erforderlich')
                        for field in ('account', 'contra_account'):
                            if not isinstance(choice[field], str) or not re.fullmatch(r'[0-9]{4,9}', choice[field]):
                                raise Problem(400, 'Ausdrücklich bestätigte 4–9-stellige Kontonummer erwartet')
                        mapped_gross = Decimal(0)
                        for bucket in item['totals']['tax_breakdown']:
                            normalized_rate = format(Decimal(bucket['rate']).normalize(), 'f')
                            tax_key = choice['tax_keys'].get(bucket['rate'], choice['tax_keys'].get(normalized_rate))
                            if not isinstance(tax_key, str) or not re.fullmatch(r'[0-9]{1,4}', tax_key):
                                raise Problem(400, 'Steuerschlüssel für jeden vorkommenden Satz erforderlich')
                            gross = Decimal(bucket['net']) + Decimal(bucket['tax'])
                            mapped_gross += gross
                            rows.append({'document_id': document_id, 'number': item['number'], 'kind': item['kind'],
                                'date': item['issue_date'], 'due_date': item['due_date'], 'currency': 'EUR',
                                'amount_gross': format(gross, '.2f'), 'net': bucket['net'], 'tax': bucket['tax'], 'tax_rate': bucket['rate'],
                                'tax_category': bucket.get('category', ''), 'tax_exemption_reason': bucket.get('reason', ''),
                                'debit_credit': 'H' if item['kind'] == 'credit_note' else 'S', 'account': choice['account'],
                                'contra_account': choice['contra_account'], 'tax_key': tax_key, 'source_sha256': item['payload_sha256']})
                        if mapped_gross != Decimal(item['totals']['gross']):
                            raise Problem(409, 'Steuergruppen stimmen nicht mit dem finalen Gesamtbetrag überein')
                    elif profile == 'lexware_review_json_v1':
                        contact_id = choice.get('remote_contact_id')
                        if set(choice) != {'remote_contact_id'} or not isinstance(contact_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', contact_id):
                            raise Problem(400, 'Bestätigte externe Lexware-Kontaktzuordnung erforderlich')
                        rows.append({'source_document_id': document_id, 'source_sha256': item['payload_sha256'],
                            'remote_contact_id': contact_id, 'number': item['number'], 'kind': item['kind'],
                            'issue_date': item['issue_date'], 'due_date': item['due_date'], 'currency': 'EUR',
                            'buyer_snapshot': item['buyer'], 'positions': item['positions'], 'totals': item['totals']})
                    else:
                        raise Problem(415, 'Kein unterstütztes Exportprofil')
                if profile == 'datev_review_csv_v1':
                    output = io.StringIO(newline='')
                    writer = csv.DictWriter(output, fieldnames=list(rows[0]), delimiter=';', lineterminator='\r\n')
                    writer.writeheader()
                    writer.writerows({key: _spreadsheet(value) for key, value in row.items()} for row in rows)
                    raw, media, filename = output.getvalue().encode('utf-8-sig'), 'text/csv', 'datev-abstimmungsdaten-v1.csv'
                    note = 'Eigenes Mapping-CSV zur Beraterprüfung; kein DATEV-EXTF, keine native Import-/Kontierungsabnahme.'
                else:
                    payments = []
                    if data.get('include_payments', False):
                        if type(data['include_payments']) is not bool:
                            raise Problem(400, 'Zahlungsauswahl muss Wahrheitswert sein')
                        from business_finance import Finance
                        for payment in Finance(self.office).payments(actor)['items']:
                            allocated = [a for a in payment['allocations'] if a['document_id'] in ids]
                            if allocated:
                                payments.append({key: payment[key] for key in ('id', 'kind', 'booking_date', 'reference')})
                                payments[-1]['source_payment_amount'] = payment['amount']
                                payments[-1]['selected_allocation_total'] = format(sum((Decimal(a['amount']) for a in allocated), Decimal(0)), '.2f')
                                payments[-1]['allocations'] = allocated
                    raw = canonical({'profile': profile, 'documents': rows, 'payments_snapshot': payments,
                                     'native_api_payload': False, 'live_synchronized': False}).encode()
                    media, filename = 'application/json', 'lexware-abstimmungsdaten-v1.json'
                    note = 'Eigenes Quellen-/Kontakt-/Zahlungsmapping zur Prüfung; keine Lexware-API-Zustellung oder Live-Zahlungsüberwachung.'
            if len(raw) > MAX_BYTES:
                raise Problem(413, 'Export übersteigt 2 MiB; Auswahl eingrenzen')
            result = {'artifact_base64': base64.b64encode(raw).decode(), 'sha256': _hash(raw), 'media_type': media,
                      'filename': filename, 'sources': sources, 'review_required': True,
                      'official_schema_validated': False, 'native_import_approved': False, 'limitation': note}
            run_id = uuid.uuid4().hex
            self.db.execute('INSERT INTO business_adapter_runs(id,adapter_id,profile,status,source_sha256,rows_json,rows_sha256,result_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (run_id, identifier, profile, 'exported', _hash(raw), canonical(rows), _hash(rows), canonical(result), actor['id'], self._now()))
            self.office.audit(actor, 'business.adapter.exported', run_id)
            self._remember(actor, request, fingerprint, {'id': run_id})
            return self._run(run_id)

    def test(self, actor, identifier):
        with self.office.lock:
            require_permission(self.office, actor, 'settings.manage')
            adapter = self._row(identifier)
            info = PROFILES[adapter['profile']]
            credential = self.environ.get(adapter['secret_ref'], '') if adapter['secret_ref'] else ''
            return {'id': identifier, 'status': 'local_profile_available' if info['supported'] else 'unsupported',
                    'live_verified': False, 'connection_state': 'not_connected', 'profile': info,
                    'credential_configured': isinstance(credential, str) and bool(_LEAD_CREDENTIAL.fullmatch(credential)),
                    'feature_enabled': self.feature(info['feature']) if info.get('feature') else None}


def deliver_pending_replies(office, *, transport=None, limit=10):
    """One bounded authorized worker pass; never retries attempted deliveries."""
    if type(limit) is not int or not 1 <= limit <= 10:
        raise Problem(400, 'Höchstens zehn Antworten pro Worker-Lauf')
    service = Adapters(office)
    result = {'processed': 0, 'accepted': 0, 'unknown': 0, 'blocked': 0}
    with office.lock:
        if not service.feature('external.lead_autoreply'):
            return {**result, 'enabled': False}
        pending = [dict(row) for row in office.db.execute(
            'SELECT o.id,a.owner_id,u.email,u.role,u.active FROM business_lead_reply_outbox o '
            'JOIN business_adapters a ON a.id=o.adapter_id JOIN users u ON u.id=a.owner_id '
            'WHERE NOT EXISTS(SELECT 1 FROM business_lead_reply_receipts r WHERE r.outbox_id=o.id) '
            'ORDER BY o.created_at,o.id LIMIT ?', (limit,)).fetchall()]
    for row in pending:
        if row['active'] != 1 or row['role'] != 'owner':
            result['blocked'] += 1
            continue
        actor = {'id': row['owner_id'], 'email': row['email'], 'role': row['role']}
        try:
            state = service.deliver_reply(actor, row['id'], {'request_id': _hash(('reply-worker:' + row['id']).encode())[:32]}, transport=transport)
        except Problem:
            result['blocked'] += 1
            continue
        result['processed'] += 1
        if state['status'] == 'accepted':
            result['accepted'] += 1
        elif state['status'] == 'unknown':
            result['unknown'] += 1
    return {**result, 'enabled': True}


def sanitize_after_restore(office):
    """An older snapshot cannot prove that a pending reply was never sent.

    Append uncertainty only on disaster restore, never on release clones/down.
    Existing jobs, approvals, operation IDs and transport receipts stay intact.
    Caller owns restore transaction; this function never commits or sends.
    """
    service = Adapters(office)
    for row in office.db.execute('SELECT id,operation_id FROM business_lead_reply_outbox').fetchall():
        receipts = office.db.execute('SELECT * FROM business_lead_reply_receipts WHERE outbox_id=? ORDER BY ordinal', (row['id'],)).fetchall()
        if receipts and receipts[-1]['status'] in ('accepted', 'unknown'):
            continue
        if not receipts:
            office.db.execute('INSERT INTO business_lead_reply_receipts(id,outbox_id,operation_id,status,ordinal,at) VALUES(?,?,?,?,?,?)',
                (uuid.uuid4().hex, row['id'], row['operation_id'], 'sending', 1, service._now()))
            ordinal = 2
        else:
            ordinal = receipts[-1]['ordinal'] + 1
        office.db.execute('INSERT INTO business_lead_reply_receipts(id,outbox_id,operation_id,status,ordinal,error_code,at) VALUES(?,?,?,?,?,?,?)',
            (uuid.uuid4().hex, row['id'], row['operation_id'], 'unknown', ordinal, 'restored_delivery_unconfirmed', service._now()))


def validate_integrity(office):
    with office.lock:
        try:
            for row in office.db.execute('SELECT * FROM business_adapters'):
                _id(row['id'])
                if row['profile'] not in PROFILES or row['revision'] < 1 or row['enabled'] not in (0, 1):
                    raise ValueError('Invalid adapter configuration')
                if row['enabled'] and not PROFILES[row['profile']]['supported']:
                    raise ValueError('Unsupported partner adapter was enabled')
                if row['secret_ref'] is not None and not _ENV.fullmatch(row['secret_ref']):
                    raise ValueError('Adapter credential is not an ENV reference')
                if row['profile'] == 'website_lead_v1' and not row['secret_ref']:
                    raise ValueError('Website source has no credential reference')
            for row in office.db.execute('SELECT * FROM business_leads'):
                inquiry = office.db.execute('SELECT source,source_account,source_id FROM inquiries WHERE id=?', (row['inquiry_id'],)).fetchone()
                if not inquiry or (inquiry['source'], inquiry['source_account'], inquiry['source_id']) != ('import', 'lead:' + row['adapter_id'], row['external_id']):
                    raise ValueError('Lead provenance is not canonical')
                if not re.fullmatch(r'[a-f0-9]{64}', row['content_sha256']):
                    raise ValueError('Invalid lead hash')
            for row in office.db.execute('SELECT * FROM business_adapter_suppliers'):
                if row['supplier'] not in SUPPLIERS:
                    raise ValueError('Unverified supplier identifier')
            for row in office.db.execute('SELECT * FROM business_adapter_runs'):
                if row['profile'] not in PROFILES or row['status'] not in ('staged', 'applied', 'exported') or not re.fullmatch(r'[a-f0-9]{64}', row['source_sha256']):
                    raise ValueError('Invalid adapter run')
                adapter = office.db.execute('SELECT profile FROM business_adapters WHERE id=?', (row['adapter_id'],)).fetchone()
                if not adapter or adapter['profile'] != row['profile']:
                    raise ValueError('Adapter run has a different source profile')
                if not isinstance(json.loads(row['rows_json']), list) or not isinstance(json.loads(row['result_json']), dict):
                    raise ValueError('Invalid adapter run payload')
                if _hash(json.loads(row['rows_json'])) != row['rows_sha256']:
                    raise ValueError('Adapter source positions were modified')
                if row['status'] == 'exported':
                    result = json.loads(row['result_json'])
                    raw = base64.b64decode(result['artifact_base64'], validate=True)
                    if len(raw) > MAX_BYTES or _hash(raw) != row['source_sha256'] or result['sha256'] != row['source_sha256']:
                        raise ValueError('Export artifact integrity failed')
            for row in office.db.execute('SELECT * FROM business_adapter_requests'):
                _id(row['request_id'])
                if not re.fullmatch(r'[a-f0-9]{64}', row['request_hash']) or not isinstance(json.loads(row['result_json']), dict):
                    raise ValueError('Invalid adapter receipt')
            for row in office.db.execute('SELECT * FROM business_lead_limits'):
                if (type(row['window_count']) is not int or not 0 <= row['window_count'] <= 30
                        or type(row['window_started']) not in (int, float) or not math.isfinite(row['window_started'])):
                    raise ValueError('Invalid lead rate window')
            for row in office.db.execute('SELECT * FROM business_contact_form_limits'):
                if (not isinstance(row['scope'], str) or not row['scope'].startswith(('ip:', 'global:'))
                        or type(row['window_count']) is not int or not 0 <= row['window_count'] <= 50
                        or type(row['window_started']) not in (int, float) or not math.isfinite(row['window_started'])):
                    raise ValueError('Invalid private contact form rate')
            for row in office.db.execute('SELECT * FROM business_lead_reply_templates'):
                if row['revision'] < 1 or row['enabled'] not in (0, 1) or not row['subject'] or not row['text']:
                    raise ValueError('Invalid approved reply template')
            for row in office.db.execute('SELECT * FROM business_lead_reply_outbox'):
                job = json.loads(row['job_json'])
                if _hash(job) != row['content_sha256'] or job.get('operation_id') != row['operation_id'] or job.get('attachments') != []:
                    raise ValueError('Approved reply payload was changed')
                receipts = office.db.execute('SELECT * FROM business_lead_reply_receipts WHERE outbox_id=? ORDER BY ordinal', (row['id'],)).fetchall()
                if len(receipts) > 3:
                    raise ValueError('A lead reply was retried without reconciliation')
                for index, receipt in enumerate(receipts):
                    if receipt['ordinal'] != index + 1 or receipt['operation_id'] != row['operation_id']:
                        raise ValueError('Reply receipt is not bound to its operation')
                    if index == 0 and receipt['status'] != 'sending' or index == 1 and receipt['status'] not in ('accepted', 'unknown', 'failed'):
                        raise ValueError('Invalid lead reply delivery history')
                    if index == 2 and (receipt['status'] != 'unknown' or receipt['error_code'] != 'restored_delivery_unconfirmed' or receipts[1]['status'] != 'failed'):
                        raise ValueError('Only an independent restore uncertainty may follow a failed send')
                    if receipt['status'] == 'accepted' and not receipt['receipt_id']:
                        raise ValueError('Reply acceptance lacks a transport acknowledgment')
        except (Problem, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError('Invalid adapter state') from error
    return True


def methods(path):
    for pattern, allowed in ((r'/adapters', 'GET, POST'), (r'/adapters/replies', 'GET'),
        (r'/adapters/replies/[a-f0-9]{32}/send', 'POST'),
        (r'/adapters/[a-f0-9]{32}/reply-template', 'GET, POST'), (r'/adapters/[a-f0-9]{32}', 'GET, POST'),
        (r'/adapters/[a-f0-9]{32}/(?:import|export|test)', 'POST'),
        (r'/adapters/imports/[a-f0-9]{32}/(?:apply|offer)', 'POST')):
        if re.fullmatch(pattern, path):
            return allowed
    return None


def _spreadsheet(value):
    text = str(value)
    return "'" + text if text.startswith(("'", '=', '+', '-', '@', '\t', '\r')) else text


def _unspreadsheet(value):
    # This escaping is part of Smartplan catalog CSV v1, not a vendor format.
    return value[1:] if len(value) >= 2 and value[0] == "'" and value[1] in "'=+-@\t\r" else value


def dispatch(office, actor, path, method, data):
    allowed = methods(path)
    if allowed is None:
        return None
    if method not in allowed.split(', '):
        raise Problem(405, 'HTTP-Methode nicht erlaubt')
    service = Adapters(office)
    if path == '/adapters':
        return (service.list(actor), 200, 'application/json') if method == 'GET' else (service.save(actor, data), 201, 'application/json')
    if path == '/adapters/replies':
        return service.replies(actor), 200, 'application/json'
    match = re.fullmatch(r'/adapters/replies/([a-f0-9]{32})/send', path)
    if match:
        return service.deliver_reply(actor, match[1], data), 200, 'application/json'
    match = re.fullmatch(r'/adapters/([a-f0-9]{32})/reply-template', path)
    if match:
        return (service.reply_template(actor, match[1]), 200, 'application/json') if method == 'GET' else (
            service.approve_reply_template(actor, match[1], data), 200, 'application/json')
    match = re.fullmatch(r'/adapters/imports/([a-f0-9]{32})/(apply|offer)', path)
    if match:
        result = service.create_offer_from_inspection(actor, match[1], data) if match[2] == 'offer' else service.apply_catalog(actor, match[1], data)
        return result, 200, 'application/json'
    match = re.fullmatch(r'/adapters/([a-f0-9]{32})(?:/(import|export|test))?', path)
    identifier, action = match.groups()
    if action == 'import':
        return service.import_data(actor, identifier, data), 201, 'application/json'
    if action == 'test':
        if data:
            raise Problem(400, 'Leerer Testauftrag erwartet')
        return service.test(actor, identifier), 200, 'application/json'
    if action == 'export':
        return service.export_data(actor, identifier, data), 201, 'application/json'
    if method == 'GET':
        require_permission(office, actor, 'settings.manage')
        return service._record(service._row(identifier)), 200, 'application/json'
    return service.save(actor, data, identifier), 200, 'application/json'


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--deliver-replies']:
        raise SystemExit('Aufruf: python -m business_adapters --deliver-replies (ENV-Konfiguration, keine Schlüsselargumente)')
    from online.store import PostgresOffice
    from business_schema import require_capability
    dsn = os.environ.get('SMARTPLAN_DATABASE_DSN')
    if not dsn:
        raise SystemExit('Geschützte Datenbankkonfiguration fehlt')
    office = None
    try:
        office = PostgresOffice(dsn)
        require_capability(office, 'business_adapters')
        print(json.dumps(deliver_pending_replies(office), sort_keys=True))
    except Exception:
        print('{"status":"blocked","reason":"configuration_or_authorization_required"}')
        raise SystemExit(1)
    finally:
        if office is not None:
            office.db.close()
