"""Additive, immutable catalog originals and explicit acceptance evidence.

The old adapter format, run rows and idempotency receipts are unchanged. Migration
marks pre-existing imports; their unavailable originals are never reconstructed
from normalized rows. New catalog imports always retain the actual upload bytes.
"""
import base64
from decimal import Decimal, ROUND_HALF_UP
import json
import re

from core import Problem, canonical
from business_foundation import require_permission
from workspace_api import BinaryAttachment

FEATURES = ('catalog_import_history',)
PROFILES = ('catalog_csv_v1', 'datanorm_a14_cp850_v1')
TABLES = ('business_catalog_legacy_imports', 'business_catalog_originals', 'business_catalog_acceptances')
ID = r'[a-f0-9]{32}'


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BYTEA', 'BLOB'):
        raise ValueError('Unsupported binary storage type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_catalog_legacy_imports(
          run_id TEXT PRIMARY KEY REFERENCES business_adapter_runs(id), source_sha256 TEXT NOT NULL,
          rows_sha256 TEXT NOT NULL, baseline_status TEXT NOT NULL CHECK(baseline_status IN ('staged','applied')))''',
        f'''CREATE TABLE IF NOT EXISTS business_catalog_originals(
          run_id TEXT PRIMARY KEY REFERENCES business_adapter_runs(id), filename TEXT NOT NULL,
          content {binary_type} NOT NULL, sha256 TEXT NOT NULL, rows_sha256 TEXT NOT NULL,
          request_json TEXT NOT NULL, request_hash TEXT NOT NULL, targets_json TEXT NOT NULL, targets_sha256 TEXT NOT NULL,
          created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS business_catalog_acceptances(
          run_id TEXT PRIMARY KEY REFERENCES business_adapter_runs(id), request_json TEXT NOT NULL,
          payload_json TEXT NOT NULL, sha256 TEXT NOT NULL)''',
        '''INSERT INTO business_catalog_legacy_imports(run_id,source_sha256,rows_sha256,baseline_status)
          SELECT id,source_sha256,rows_sha256,status FROM business_adapter_runs
          WHERE profile IN ('catalog_csv_v1','datanorm_a14_cp850_v1') AND status IN ('staged','applied')
          AND id NOT IN (SELECT run_id FROM business_catalog_originals)
          AND id NOT IN (SELECT run_id FROM business_catalog_legacy_imports)''',
    ]


def protected_tables():
    return TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        result = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'immutable catalog evidence'); END"
                  for table in TABLES for action in ('UPDATE', 'DELETE')]
        return result + [f"CREATE TRIGGER IF NOT EXISTS {table}_replace_guard BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE run_id=NEW.run_id) BEGIN SELECT RAISE(ABORT,'immutable catalog evidence'); END" for table in TABLES]
    if dialect == 'postgresql':
        result = ["CREATE OR REPLACE FUNCTION business_catalog_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable catalog evidence'; END; $$"]
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                name = table + '_' + action.lower() + '_guard'
                result.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION business_catalog_evidence_guard(); END IF; END $$")
        return result
    raise ValueError('Unsupported guard dialect')


def installed(office):
    from business_schema import _tables
    present = set(TABLES) & _tables(office)
    if present and present != set(TABLES):
        raise Problem(503, 'Katalogoriginale sind nur teilweise eingerichtet; Migration prüfen.')
    return bool(present)


def filename(value, profile):
    from business_adapters import _text
    value = _text(value, 'Dateiname', 200)
    if value in ('.', '..') or any(char in value for char in '/\\'):
        raise Problem(400, 'Ein einfacher Dateiname ohne Verzeichnisse ist erforderlich.')
    return value


def save_original(office, actor, run, raw, data, fingerprint):
    """Called inside the existing import transaction, before its receipt."""
    from business_adapters import _hash
    if not installed(office):
        return
    name = filename(data.get('filename', 'katalog-' + run['id'] + ('.csv' if run['profile'] == PROFILES[0] else '.dat')), run['profile'])
    # Keep the exact accepted command, including its base64 spelling: the v1
    # decoder accepts equivalent encodings whose request fingerprints differ.
    request = dict(data)
    targets = run['result']['target_revisions']
    office.db.execute('INSERT INTO business_catalog_originals VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        (run['id'], name, raw, run['source_sha256'], _hash(run['rows']), canonical(request), fingerprint,
         canonical(targets), _hash(targets), actor['id'], run['created_at']))


def _raw_run(office, run_id):
    from business_adapters import _id
    row = office.db.execute('SELECT * FROM business_adapter_runs WHERE id=?', (_id(run_id),)).fetchone()
    if row is None or row['profile'] not in PROFILES or row['status'] not in ('staged', 'applied'):
        raise Problem(404, 'Katalogimport nicht verfügbar.')
    return row


def _receipt(office, actor_id, request_id, request_hash, run_id):
    row = office.db.execute('SELECT * FROM business_adapter_requests WHERE user_id=? AND request_id=?', (actor_id, request_id)).fetchone()
    if row is None or row['request_hash'] != request_hash or json.loads(row['result_json']) != {'id': run_id}:
        raise ValueError('Catalog evidence is not bound to its original adapter receipt')


def _original(office, run, *, receipt=True):
    from business_adapters import _hash, parse_catalog, MAX_BYTES
    original = office.db.execute('SELECT * FROM business_catalog_originals WHERE run_id=?', (run['id'],)).fetchone()
    legacy = office.db.execute('SELECT * FROM business_catalog_legacy_imports WHERE run_id=?', (run['id'],)).fetchone()
    if bool(original) == bool(legacy):
        raise ValueError('Catalog import must have exactly one original or explicit legacy marker')
    if _hash(json.loads(run['rows_json'])) != run['rows_sha256']:
        raise ValueError('Catalog rows were changed')
    if legacy:
        if legacy['source_sha256'] != run['source_sha256'] or legacy['rows_sha256'] != run['rows_sha256']:
            raise ValueError('Legacy catalog hashes were changed')
        return None, legacy
    raw = bytes(original['content'])
    request = json.loads(original['request_json'])
    if not isinstance(request, dict) or set(request) - {'request_id', 'filename', 'content_base64'} or not {'request_id', 'content_base64'} <= set(request):
        raise ValueError('Invalid original catalog request fields')
    name = filename(request.get('filename', 'katalog-' + run['id'] + ('.csv' if run['profile'] == PROFILES[0] else '.dat')), run['profile'])
    targets = json.loads(original['targets_json'])
    if (not 0 < len(raw) <= MAX_BYTES or name != original['filename'] or _hash(raw) != original['sha256']
            or original['sha256'] != run['source_sha256'] or original['rows_sha256'] != run['rows_sha256']
            or _hash(parse_catalog(run['profile'], raw)) != run['rows_sha256']
            or base64.b64decode(request['content_base64'], validate=True) != raw
            or _hash({'operation': 'import:' + run['adapter_id'], 'data': request}) != original['request_hash']
            or not isinstance(targets, dict) or _hash(targets) != original['targets_sha256']
            or original['created_by'] != run['created_by'] or original['created_at'] != run['created_at']):
        raise ValueError('Catalog original differs from its source or command')
    if run['status'] == 'staged' and json.loads(run['result_json']).get('target_revisions') != targets:
        raise ValueError('Catalog preview targets were changed')
    codes = {item['code'] for item in json.loads(run['rows_json'])}
    for code, target in targets.items():
        if (code not in codes or not isinstance(target, dict) or set(target) != {'article_id', 'revision'}
                or not isinstance(target['article_id'], str) or not re.fullmatch(ID, target['article_id'])
                or type(target['revision']) is not int or target['revision'] < 1):
            raise ValueError('Invalid original catalog target version')
        prior = office.db.execute('SELECT payload_json,payload_sha256 FROM business_article_versions WHERE article_id=? AND revision=?',
                                  (target['article_id'], target['revision'])).fetchone()
        if prior is None or _hash(json.loads(prior['payload_json'])) != prior['payload_sha256']:
            raise ValueError('Original catalog target version is missing')
    if receipt:
        _receipt(office, original['created_by'], request['request_id'], original['request_hash'], run['id'])
    return original, None


def original_metadata(original):
    if original is None:
        return dict(available=False, reason='legacy_original_not_stored')
    return dict(available=True, filename=original['filename'], size=len(original['content']), sha256=original['sha256'])


def save_acceptance(office, actor, run_id, data, fingerprint, stamp):
    from business_adapters import _hash
    if not installed(office):
        return
    run = _raw_run(office, run_id)
    original, legacy = _original(office, run)
    articles = []
    for article_id in json.loads(run['result_json'])['article_ids']:
        item = office.db.execute('SELECT revision FROM business_articles WHERE id=?', (article_id,)).fetchone()
        articles.append(dict(article_id=article_id, revision=item['revision']))
    value = dict(run_id=run_id, source_sha256=run['source_sha256'], rows_sha256=run['rows_sha256'],
                 original_available=original is not None, request_id=data['request_id'], request_sha256=fingerprint,
                 confirmed=True, price_mapping={key: data[key] for key in ('price_scale', 'target_price', 'tax_rate') if key in data},
                 articles=articles, created_by=actor['id'], created_at=stamp)
    office.db.execute('INSERT INTO business_catalog_acceptances VALUES(?,?,?,?)',
                      (run_id, canonical(data), canonical(value), _hash(value)))


def _acceptance(office, run, original, legacy, *, receipt=True):
    from business_adapters import _hash
    row = office.db.execute('SELECT * FROM business_catalog_acceptances WHERE run_id=?', (run['id'],)).fetchone()
    if row is None:
        if run['status'] == 'applied' and (original or legacy['baseline_status'] != 'applied'):
            raise ValueError('Catalog acceptance evidence is missing')
        return None
    value, request = json.loads(row['payload_json']), json.loads(row['request_json'])
    if (not isinstance(value, dict) or _hash(value) != row['sha256'] or run['status'] != 'applied'
            or value['run_id'] != run['id'] or value['source_sha256'] != run['source_sha256']
            or value['rows_sha256'] != run['rows_sha256'] or value['original_available'] != (original is not None)
            or value['confirmed'] is not True or request.get('confirmed') is not True
            or set(request) - {'request_id', 'confirmed', 'price_scale', 'target_price', 'tax_rate'}
            or request['request_id'] != value['request_id']
            or value['price_mapping'] != {key: request[key] for key in ('price_scale', 'target_price', 'tax_rate') if key in request}
            or _hash({'operation': 'apply:' + run['id'], 'data': request}) != value['request_sha256']
            or [item['article_id'] for item in value['articles']] != json.loads(run['result_json'])['article_ids']):
        raise ValueError('Catalog acceptance binding was changed')
    sources = json.loads(run['rows_json'])
    if len(value['articles']) != len(sources):
        raise ValueError('Accepted article count differs from the original catalog')
    for source, item in zip(sources, value['articles']):
        article = office.db.execute('SELECT payload_json,payload_sha256 FROM business_article_versions WHERE article_id=? AND revision=?',
                                    (item['article_id'], item['revision'])).fetchone()
        if article is None or _hash(json.loads(article['payload_json'])) != article['payload_sha256']:
            raise ValueError('Accepted article version is unavailable or changed')
        actual = json.loads(article['payload_json'])
        expected = {key: source[key] for key in ('code', 'name', 'unit')}
        expected.update(kind='material', currency='EUR', active=True)
        if run['profile'] == PROFILES[0]:
            expected.update({key: source[key] for key in ('cost_price_net', 'unit_price_net', 'tax_rate')})
        else:
            if (source['discount_group'] or source['long_text_key'] or request.get('target_price') not in ('purchase_net', 'sales_net')
                    or Decimal(request['price_scale']) <= 0 or not 0 <= Decimal(request['tax_rate']) <= 100):
                raise ValueError('Unsupported DATANORM acceptance')
            price = Decimal(source['source_price_integer']) * Decimal(request['price_scale']) / Decimal(source['price_basis'])
            field = 'cost_price_net' if request['target_price'] == 'purchase_net' else 'unit_price_net'
            expected[field] = format(price.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP), 'f')
            expected['tax_rate'] = str(Decimal(request['tax_rate']))
            if original is not None:
                target = json.loads(original['targets_json']).get(source['code'])
                other = 'unit_price_net' if field == 'cost_price_net' else 'cost_price_net'
                previous = office.db.execute('SELECT payload_json FROM business_article_versions WHERE article_id=? AND revision=?',
                    (target['article_id'], target['revision'])).fetchone() if target else None
                expected[other] = json.loads(previous['payload_json'])[other] if previous else '0'
        if any(actual.get(key) != expected_value for key, expected_value in expected.items()):
            raise ValueError('Accepted article differs from its original catalog and price mapping')
    if receipt:
        _receipt(office, value['created_by'], value['request_id'], value['request_sha256'], run['id'])
    return dict(value, sha256=row['sha256'])


def enrich(office, value):
    if value['profile'] not in PROFILES or value['status'] == 'exported' or not installed(office):
        return value
    try:
        run = _raw_run(office, value['id'])
        original, legacy = _original(office, run)
        return dict(value, original=original_metadata(original), acceptance=_acceptance(office, run, original, legacy))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise Problem(409, 'Katalogoriginal oder Annahmenachweis ist unvollständig oder verändert; Wiederherstellung prüfen.') from error


def validate_integrity(office):
    with office.lock:
        if not installed(office):
            raise ValueError('Catalog evidence schema is missing')
        try:
            for run in office.db.execute("SELECT * FROM business_adapter_runs WHERE profile IN ('catalog_csv_v1','datanorm_a14_cp850_v1') AND status IN ('staged','applied')"):
                original, legacy = _original(office, run)
                _acceptance(office, run, original, legacy)
            for table in TABLES:
                for row in office.db.execute('SELECT run_id FROM ' + table):
                    _raw_run(office, row['run_id'])
        except (Problem, TypeError, KeyError, json.JSONDecodeError) as error:
            raise ValueError('Invalid catalog original or acceptance evidence') from error
    return True


class CatalogImports:
    def __init__(self, office):
        self.office = office

    def authority(self, actor):
        require_permission(self.office, actor, 'settings.manage')
        return require_permission(self.office, actor, 'finance.read')

    def history(self, actor, adapter_id, data):
        from business_adapters import Adapters
        with self.office.lock:
            self.authority(actor)
            adapter = Adapters(self.office)._row(adapter_id)
            if adapter['profile'] not in PROFILES:
                raise Problem(404, 'Keine Katalogquelle.')
            if not isinstance(data, dict) or set(data) - {'_query'}:
                raise Problem(400, 'Nur Suchparameter für die Historie erwartet.')
            query = data.get('_query', {})
            if not isinstance(query, dict) or set(query) - {'offset', 'limit'}:
                raise Problem(400, 'Unbekannter Historienfilter.')
            def number(key, default, maximum):
                raw = query.get(key, str(default))
                if not isinstance(raw, str) or not re.fullmatch(r'0|[1-9][0-9]{0,8}', raw) or int(raw) > maximum:
                    raise Problem(400, 'Ungültige Seitengrenze.')
                return int(raw)
            offset, limit = number('offset', 0, 100000000), number('limit', 20, 50)
            if not limit:
                raise Problem(400, 'Mindestens ein Historieneintrag ist erforderlich.')
            total = self.office.db.execute("SELECT COUNT(*) FROM business_adapter_runs WHERE adapter_id=? AND status IN ('staged','applied')", (adapter_id,)).fetchone()[0]
            result = []
            for row in self.office.db.execute("SELECT * FROM business_adapter_runs WHERE adapter_id=? AND status IN ('staged','applied') ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (adapter_id, limit, offset)):
                item = Adapters(self.office)._run(row['id'], actor)
                result.append({**{key: item[key] for key in ('id', 'adapter_id', 'profile', 'status', 'source_sha256', 'created_at', 'original')}, 'row_count': len(item['rows'])})
            return dict(items=result, offset=offset, limit=limit, total=total)

    def detail(self, actor, run_id):
        from business_adapters import Adapters
        with self.office.lock:
            self.authority(actor)
            _raw_run(self.office, run_id)
            return Adapters(self.office)._run(run_id, actor)

    def original(self, actor, run_id):
        with self.office.lock:
            self.authority(actor)
            run = self.detail(actor, run_id)
            if not run['original']['available']:
                raise Problem(404, 'Für diesen älteren Import wurde keine Originaldatei gespeichert.')
            original = self.office.db.execute('SELECT * FROM business_catalog_originals WHERE run_id=?', (run_id,)).fetchone()
            return BinaryAttachment(bytes(original['content']), original['filename']), 200, 'application/octet-stream'

    def preview(self, actor, run_id, data):
        """Project the actual v1 decision, including its unchanged-source no-op.

        This path never issues an article command, request receipt, audit event
        or temporary database write. Inputs are explicit; no price role, VAT or
        DATANORM scaling is inferred.
        """
        from business_adapters import Adapters, _hash
        from business_documents import Documents, _text, decimal_value, calculate_positions
        with self.office.lock:
            self.authority(actor)
            service = Adapters(self.office)
            _raw_run(self.office, run_id)
            run = service._run(run_id, actor)
            adapter = service._row(run['adapter_id'])
            if run['status'] != 'staged' or not adapter['enabled']:
                raise Problem(409, 'Nur ein noch nicht übernommener Import einer aktivierten Quelle kann geprüft werden.')
            expected = set() if run['profile'] == PROFILES[0] else {'price_scale', 'target_price', 'tax_rate'}
            if not isinstance(data, dict) or set(data) != expected:
                raise Problem(400, 'Für CSV ist ein leerer Prüfauftrag, für DATANORM die vollständige Preiszuordnung erforderlich.')
            rows = []
            documents = Documents(self.office)
            for item in run['rows']:
                values, old, prior_row, source_hash, action = service._catalog_line(run, adapter, item, data)
                before = json.loads(prior_row['payload_json']) if prior_row else None
                if action == 'noop':
                    after = dict(before)
                else:
                    # This is the plain material branch of Documents.save_article:
                    # catalog v1 always supplies both prices, kind and unit and
                    # never supplies a pricing calculation or components.
                    after = {**(before or {'code': '', 'currency': 'EUR', 'active': True,
                                          'cost_price_net': '0', 'cost_known': False, 'tax_rate': '19'}),
                             **values, 'cost_known': True}
                    after.pop('pricing_snapshot', None)
                    for key in ('name', 'unit'):
                        after[key] = _text(after.get(key), key, 500)
                    after['code'] = _text(after.get('code', ''), 'Artikelnummer', 100, empty=True)
                    if old:
                        documents._require_stock_identity(old['article_id'], before, after)
                    for key in ('cost_price_net', 'unit_price_net', 'tax_rate'):
                        decimal_value(after[key])
                    after.setdefault('tax_category', 'S' if Decimal(after['tax_rate']) else 'Z')
                    after.setdefault('tax_exemption_reason', '')
                    components = after.get('components', [])
                    if not isinstance(components, list) or components:
                        raise Problem(400, 'Stückliste nur für eine Leistung erwartet')
                    after['components'] = []
                    calculate_positions([{**after, 'description': after['name'], 'quantity': '1'}])
                rows.append(dict(code=item['code'], action=action,
                                 article_id=old['article_id'] if old else None,
                                 revision=prior_row['revision'] if prior_row else None,
                                 before=before, after=after))
            value = dict(run_id=run_id, source_sha256=run['source_sha256'], profile=run['profile'],
                         price_mapping=dict(data), rows=rows)
            return dict(value, preview_sha256=_hash(value))


def methods(path):
    if re.fullmatch(r'/adapters/imports/' + ID + r'/catalog-preview', path):
        return 'POST'
    return 'GET' if re.fullmatch(r'/adapters/(?:' + ID + r'/imports|imports/' + ID + r'(?:/original)?)', path) else None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method != methods(path):
        raise Problem(405, 'HTTP-Methode nicht erlaubt.')
    service = CatalogImports(office)
    preview = re.fullmatch(r'/adapters/imports/(' + ID + r')/catalog-preview', path)
    if preview:
        return service.preview(actor, preview[1], data), 200, 'application/json'
    match = re.fullmatch(r'/adapters/(' + ID + r')/imports', path)
    if match:
        return service.history(actor, match[1], data), 200, 'application/json'
    if data:
        raise Problem(400, 'Dieser Originalabruf akzeptiert keine zusätzlichen Felder oder Filter.')
    match = re.fullmatch(r'/adapters/imports/(' + ID + r')(/original)?', path)
    return service.original(actor, match[1]) if match[2] else (service.detail(actor, match[1]), 200, 'application/json')
