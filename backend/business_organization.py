"""Company needs and module choices; visibility never grants a permission.

One configuration belongs to one Office database. It is not a tenant selector.
All modules remain readable under their existing rights after deactivation;
new commands are gated at the shared business HTTP boundary. An operation
already admitted may finish. No preference change deletes business records.
"""
import hashlib
import json
import re

from core import Problem, canonical, now_iso
from inquiries import _transaction
from business_foundation import _fresh, require_permission

FEATURES = ('organization_modules',)
NEEDS = dict(has_employees=False, uses_inventory=False, project_work=True,
             uses_finance=True, works_with_tax_advisor=False)
MODULES = dict(personnel='Personal', material='Material und Lager',
               planning='Einsatzplanung', documents='Kaufmännische Belege', finance='Finanzen')


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_organization_settings(
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER NOT NULL CHECK(revision>0),
          needs_json TEXT NOT NULL, modules_json TEXT NOT NULL,
          updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_organization_events(
          revision INTEGER PRIMARY KEY CHECK(revision>0), needs_json TEXT NOT NULL, modules_json TEXT NOT NULL,
          updated_by TEXT NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_organization_requests(
          user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
          request_hash TEXT NOT NULL, revision INTEGER NOT NULL REFERENCES business_organization_events(revision),
          PRIMARY KEY(user_id,request_id))''',
    ]


def protected_tables():
    return ('business_organization_events', 'business_organization_requests')


def runtime_privileges():
    return {'business_organization_settings': ('SELECT', 'INSERT', 'UPDATE')}


def _choices(needs, modules):
    if (not isinstance(needs, dict) or set(needs) != set(NEEDS)
            or any(type(value) is not bool for value in needs.values())):
        raise Problem(400, 'Bitte alle Fragen zum Unternehmensbedarf mit Ja oder Nein beantworten.')
    if not isinstance(modules, dict) or set(modules) != set(MODULES):
        raise Problem(400, 'Bitte alle unterstützten Module angeben.')
    for value in modules.values():
        if (not isinstance(value, dict) or set(value) != {'visible', 'enabled'}
                or value['visible'] is not None and type(value['visible']) is not bool
                or type(value['enabled']) is not bool):
            raise Problem(400, 'Modulsichtbarkeit benötigt Automatisch, Anzeigen oder Ausblenden; Aktivierung Ja oder Nein.')
    return needs, modules


def _stored(office):
    row = office.db.execute('SELECT * FROM business_organization_settings WHERE singleton=1').fetchone()
    if row is None:
        return dict(revision=0, configured=False, needs=dict(NEEDS),
                    modules={key: dict(visible=None, enabled=True) for key in MODULES})
    needs, modules = _choices(json.loads(row['needs_json']), json.loads(row['modules_json']))
    return dict(revision=row['revision'], configured=True, needs=needs, modules=modules)


def _view(office, value):
    count = office.db.execute('SELECT COUNT(*) FROM business_employees e JOIN users u ON u.id=e.user_id '
                             'WHERE e.active=1 AND u.active=1').fetchone()[0]
    needs = value['needs']
    suggested = dict(personnel=needs['has_employees'] or count > 0,
                     material=needs['uses_inventory'], planning=needs['project_work'],
                     documents=needs['uses_finance'], finance=needs['uses_finance'])
    return dict(revision=value['revision'], configured=value['configured'], needs=needs,
                active_employee_count=count,
                suggestion_reasons=dict(personnel='active_employees' if count else 'company_needs',
                    material='company_needs', planning='company_needs', documents='company_needs', finance='company_needs'),
                modules={key: dict(label=label, suggested=suggested[key],
                    visibility_override=value['modules'][key]['visible'],
                    visible=suggested[key] if value['modules'][key]['visible'] is None else value['modules'][key]['visible'],
                    enabled=value['modules'][key]['enabled']) for key, label in MODULES.items()})


def module_enabled(office, key):
    """Read only a module state; this grants no identity or object permission.

    Separate authentication domains such as the customer portal use this after
    their own authorization instead of impersonating an internal Office user.
    """
    if key not in MODULES:
        raise ValueError('Unknown organization module')
    with office.lock:
        return _stored(office)['modules'][key]['enabled']


def navigation(office, actor):
    """Minimum nonsensitive hints; caller still checks module and object rights."""
    with office.lock:
        _fresh(office, actor)
        view = _view(office, _stored(office))
        return dict(revision=view['revision'], configured=view['configured'],
                    modules={key: {field: item[field] for field in ('visible', 'enabled')}
                             for key, item in view['modules'].items()})


class Organization:
    def __init__(self, office):
        self.office, self.db = office, office.db

    def get(self, actor):
        with self.office.lock:
            require_permission(self.office, actor, 'settings.manage')
            return _view(self.office, _stored(self.office))

    def save(self, actor, data):
        if not isinstance(data, dict) or set(data) != {'request_id', 'revision', 'needs', 'modules'}:
            raise Problem(400, 'Vorgangs-ID, Version, Bedarf und Module erwartet.')
        if not isinstance(data['request_id'], str) or not re.fullmatch(r'[a-f0-9]{32}', data['request_id']):
            raise Problem(400, 'Ungültige Vorgangs-ID.')
        if type(data['revision']) is not int or data['revision'] < 0:
            raise Problem(400, 'Ungültige Konfigurationsversion.')
        needs, modules = _choices(data['needs'], data['modules'])
        fingerprint = hashlib.sha256(canonical(data).encode()).hexdigest()
        with _transaction(self.office):
            actor = require_permission(self.office, actor, 'settings.manage')
            prior = self.db.execute('SELECT * FROM business_organization_requests WHERE user_id=? AND request_id=?',
                                    (actor['id'], data['request_id'])).fetchone()
            if prior:
                if prior['request_hash'] != fingerprint:
                    raise Problem(409, 'Diese Vorgangs-ID wurde bereits mit anderem Inhalt verwendet.')
                # Return the committed version, never overwrite a newer choice.
                event = self.db.execute('SELECT * FROM business_organization_events WHERE revision=?',
                                        (prior['revision'],)).fetchone()
                return _view(self.office, dict(revision=event['revision'], configured=True,
                    needs=json.loads(event['needs_json']), modules=json.loads(event['modules_json'])))
            current = _stored(self.office)
            if current['revision'] != data['revision']:
                raise Problem(409, 'Die Unternehmenskonfiguration wurde geändert. Bitte neu laden.')
            revision, stamp = current['revision'] + 1, now_iso()
            values = (revision, canonical(needs), canonical(modules), actor['id'], stamp)
            self.db.execute('INSERT INTO business_organization_events '
                            '(revision,needs_json,modules_json,updated_by,updated_at) VALUES(?,?,?,?,?)', values)
            self.db.execute('INSERT INTO business_organization_settings '
                            '(singleton,revision,needs_json,modules_json,updated_by,updated_at) VALUES(1,?,?,?,?,?) '
                            'ON CONFLICT(singleton) DO UPDATE SET revision=excluded.revision,needs_json=excluded.needs_json,'
                            'modules_json=excluded.modules_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at', values)
            self.db.execute('INSERT INTO business_organization_requests(user_id,request_id,request_hash,revision) VALUES(?,?,?,?)',
                            (actor['id'], data['request_id'], fingerprint, revision))
            self.office.audit(actor, 'organization.settings.changed', str(revision))
            return _view(self.office, dict(revision=revision, configured=True, needs=needs, modules=modules))


def command_module(path, module_name):
    """Explicit business areas. Settings remain reachable to re-enable a module."""
    if path.startswith('/organization') or path.startswith('/settings/') or path == '/commercial/settings':
        return None
    if module_name == 'business_portal' and re.fullmatch(r'/portal/grants/[a-f0-9]{32}/revoke', path):
        return None
    if module_name in ('business_time', 'business_personnel_workflow', 'business_payroll', 'business_payroll_accounts', 'business_payroll_cash') or re.match(r'^/(employees|absences|shifts)(?:/|$)', path):
        return 'personnel'
    if module_name == 'business_planning':
        return 'planning'
    if module_name == 'business_operations' and path == '/service-reports/offline':
        return 'documents'
    if module_name == 'business_operations' and re.match(r'^/receipt-media(?:/|$)', path):
        return 'finance'
    if module_name in ('business_project_economics', 'business_accounting_euer', 'business_bank_reconciliation'):
        return 'finance'
    if module_name in ('business_asset_provenance', 'business_inventory_counts'):
        return 'material'
    if module_name == 'business_customer_workspace':
        if re.fullmatch(r'/customer-workspace/(?:grants|files)/[a-f0-9]{32}/revoke', path):
            return None
        return 'documents'
    if module_name == 'business_adapters' and re.fullmatch(r'/adapters/imports/[a-f0-9]{32}/(apply|offer)', path):
        return 'documents'
    return {'business_catalog_prices': 'documents', 'business_inventory': 'material', 'business_documents': 'documents', 'business_portal': 'documents',
            'business_finance': 'finance', 'business_accounting': 'finance',
            'business_accounting_allocations': 'finance', 'business_accounting_components': 'finance',
            'business_accounting_refunds': 'finance', 'business_accounting_capacity': 'finance',
            'business_accounting_refunds_v2': 'finance', 'business_accounting_profile': 'finance',
            'business_accounting_openings': 'finance', 'business_accounting_asset_openings': 'finance'}.get(module_name)


def require_active(office, actor, path, module_name, data=None):
    key = command_module(path, module_name)
    if key is None:
        return
    with office.lock:
        _fresh(office, actor)
        if not _stored(office)['modules'][key]['enabled']:
            # A previously committed offline time event only needs its receipt.
            # The domain rechecks actor, project, employee, complete fingerprint
            # and location before acknowledging it; a changed replay still fails.
            if path == '/time/events' and isinstance(data, dict) and isinstance(data.get('request_id'), str):
                prior = office.db.execute('SELECT user_id FROM business_time_events WHERE request_id=?',
                                          (data['request_id'],)).fetchone()
                if prior and prior['user_id'] == actor['id']:
                    return
            raise Problem(423, MODULES[key] + ' ist fachlich deaktiviert. Vorhandene Daten bleiben lesbar; '
                          'neue Vorgänge benötigen die Aktivierung in den Unternehmenseinstellungen.')


def validate_integrity(office):
    try:
        rows = office.db.execute('SELECT * FROM business_organization_settings').fetchall()
        events = office.db.execute('SELECT * FROM business_organization_events ORDER BY revision').fetchall()
        if len(rows) > 1 or bool(rows) != bool(events):
            raise ValueError('Incomplete organization history')
        for expected, event in enumerate(events, 1):
            if event['revision'] != expected:
                raise ValueError('Gap in organization history')
            _choices(json.loads(event['needs_json']), json.loads(event['modules_json']))
        if rows:
            if rows[0]['singleton'] != 1 or any(rows[0][key] != events[-1][key] for key in
                    ('revision', 'needs_json', 'modules_json', 'updated_by', 'updated_at')):
                raise ValueError('Organization settings differ from recorded history')
        for row in office.db.execute('SELECT * FROM business_organization_requests').fetchall():
            if (not re.fullmatch(r'[a-f0-9]{32}', row['request_id'])
                    or not re.fullmatch(r'[a-f0-9]{64}', row['request_hash'])
                    or not 1 <= row['revision'] <= len(events)):
                raise ValueError('Invalid organization receipt')
    except (Problem, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid organization configuration') from error
    return True


def methods(path):
    return 'GET, POST' if path == '/organization' else None


def dispatch(office, actor, path, method, data):
    if path != '/organization':
        return None
    service = Organization(office)
    if method == 'GET':
        if data:
            raise Problem(400, 'Diese Konfiguration hat keine Suchfilter.')
        return service.get(actor), 200, 'application/json'
    if method == 'POST':
        return service.save(actor, data), 200, 'application/json'
    raise Problem(405, 'HTTP-Methode nicht erlaubt.')
