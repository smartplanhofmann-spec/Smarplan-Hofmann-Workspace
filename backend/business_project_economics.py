"""Source-bound project costs and a documentary net operating view.

This is not an EÜR, tax determination or cash journal. A reviewed supplier
receipt is classified exactly once per immutable version, including explicit
stock/excluded portions so inventory costs cannot be silently counted twice.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import uuid

from core import Problem, canonical
from business_operations import Domain, identifier, iso_date, money, text, transaction
from business_documents import Documents, INVOICES, require, financial_release
from business_finance import Finance


FEATURES = ('project_economics',)
CATEGORIES = ('external_service', 'machine', 'other', 'stock_material', 'excluded')
_TABLES = ('business_project_cost_versions', 'business_project_cost_requests')
_INPUT = {'project_id', 'receipt_id', 'source_revision', 'expected_revision', 'allocations', 'reason'}


def schema_statements(binary_type='BYTEA'):
    if binary_type not in ('BLOB', 'BYTEA'):
        raise ValueError('Unsupported binary type')
    return [
        '''CREATE TABLE IF NOT EXISTS business_project_cost_versions(
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
        receipt_id TEXT NOT NULL REFERENCES business_incoming_receipts(id),
        revision INTEGER NOT NULL CHECK(revision>0), source_revision INTEGER NOT NULL CHECK(source_revision>0),
        original_sha256 TEXT NOT NULL CHECK(length(original_sha256)=64),
        previous_hash TEXT NOT NULL, entry_json TEXT NOT NULL, entry_sha256 TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
        UNIQUE(receipt_id,revision))''',
        '''CREATE TABLE IF NOT EXISTS business_project_cost_requests(
        user_id TEXT NOT NULL REFERENCES users(id), request_id TEXT NOT NULL,
        request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
        entry_id TEXT NOT NULL UNIQUE REFERENCES business_project_cost_versions(id),
        PRIMARY KEY(user_id,request_id))''',
        'CREATE INDEX IF NOT EXISTS business_project_cost_original ON business_project_cost_versions(original_sha256,receipt_id)',
    ]


def protected_tables():
    return _TABLES


def runtime_privileges():
    return {table: ('SELECT', 'INSERT') for table in _TABLES}


def guard_statements(dialect):
    if dialect == 'sqlite':
        guards = [f"CREATE TRIGGER IF NOT EXISTS {table}_{action.lower()}_guard BEFORE {action} ON {table} "
                  "BEGIN SELECT RAISE(ABORT,'immutable project cost history'); END"
                  for table in _TABLES for action in ('UPDATE', 'DELETE')]
        for table, condition in zip(_TABLES, ('id=NEW.id OR (receipt_id=NEW.receipt_id AND revision=NEW.revision)',
                '(user_id=NEW.user_id AND request_id=NEW.request_id) OR entry_id=NEW.entry_id')):
            guards.append(f'CREATE TRIGGER IF NOT EXISTS {table}_insert_guard BEFORE INSERT ON {table} '
                          f'WHEN EXISTS(SELECT 1 FROM {table} WHERE {condition}) '
                          "BEGIN SELECT RAISE(ABORT,'immutable project cost history'); END")
        return guards
    if dialect != 'postgresql':
        raise ValueError('Unsupported guard dialect')
    guards = ["""CREATE OR REPLACE FUNCTION business_project_cost_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'immutable project cost history'; END; $$"""]
    for table in _TABLES:
        for action in ('UPDATE', 'DELETE'):
            name = table + '_' + action.lower() + '_guard'
            guards.append(f"DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='{name}' AND tgrelid='{table}'::regclass) "
                          f'THEN CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION '
                          'business_project_cost_immutable_guard(); END IF; END $$')
    return guards


def _sha(value):
    return hashlib.sha256(value.encode('utf-8') if isinstance(value, str) else value).hexdigest()


def _amount(value, *, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,12})\.[0-9]{2}', value):
        raise Problem(400, 'Dokumentierte EUR-Centbeträge erwartet')
    amount = Decimal(value)
    if positive and amount <= 0:
        raise Problem(400, 'Positive EUR-Centbeträge erwartet')
    return amount


def _signed_amount(value):
    if not isinstance(value, str) or not re.fullmatch(r'-?(?:0|[1-9][0-9]{0,20})\.[0-9]{2}', value):
        raise Problem(409, 'Ungültiger dokumentierter Summenbetrag')
    return Decimal(value)


def _body(data):
    if not isinstance(data, dict) or set(data) != _INPUT:
        raise Problem(400, 'Vollständige eindeutige Projektkosteneinordnung erwartet')
    result = {key: data[key] for key in _INPUT}
    identifier(result['project_id'], 'Projekt-ID'); identifier(result['receipt_id'], 'Beleg-ID')
    for field, minimum in (('source_revision', 1), ('expected_revision', 0)):
        if type(result[field]) is not int or not minimum <= result[field] <= 1_000_000:
            raise Problem(400, 'Gültige Beleg- und Einordnungsversion erwartet')
    rows = result['allocations']
    if not isinstance(rows, list) or len(rows) > len(CATEGORIES):
        raise Problem(400, 'Belegte Kostenanteile erwartet')
    seen = set(); normalized = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'category', 'amount_net'} or row.get('category') not in CATEGORIES:
            raise Problem(400, 'Unbekannte Projektkostenart')
        if row['category'] in seen:
            raise Problem(400, 'Kostenart doppelt eingeordnet')
        seen.add(row['category']); _amount(row['amount_net'], positive=True)
        normalized.append(dict(row))
    result['allocations'] = sorted(normalized, key=lambda row: row['category'])
    result['reason'] = text(result['reason'], 'Begründung', 4000, required=True)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in result['reason']):
        raise Problem(400, 'Gültige UTF-8-Begründung erwartet')
    return result


class ProjectEconomics(Domain):
    def _duplicate_original(self, receipt_id, original_hash):
        for row in self.office.db.execute('SELECT entry_json,entry_sha256 FROM business_project_cost_versions WHERE original_sha256=? AND receipt_id<>?',
                                           (original_hash, receipt_id)).fetchall():
            if _sha(row['entry_json']) != row['entry_sha256']:
                raise Problem(409, 'Bestehende Originalzuordnung besteht die Integritätsprüfung nicht')
            value = json.loads(row['entry_json'])
            if any(item['category'] != 'excluded' for item in value['allocations']):
                return True
        return False

    def _access(self, actor, project_id, *, write=False):
        identifier(project_id, 'Projekt-ID')
        fresh = require(self.office, actor, 'finance.read', project_id)
        self.office.project(fresh, project_id)
        if write:
            require(self.office, fresh, 'finance.write', project_id)
            require(self.office, fresh, 'finance.approve', project_id)
            from business_schema import require_capability
            from business_organization import require_active
            require_capability(self.office, 'business_project_economics')
            require_active(self.office, fresh, '/project-economics/confirm', 'business_project_economics')
        return fresh

    def _source(self, actor, project_id, receipt_id, revision=None):
        """Current authority and exact historical original/review; no OCR guessing."""
        row = Finance(self.office)._incoming(actor, receipt_id) if actor is not None else self.office.db.execute(
            'SELECT * FROM business_incoming_receipts WHERE id=?', (receipt_id,)).fetchone()
        if row is None or row['project_id'] != project_id:
            raise Problem(404, 'Eingangsbeleg ist diesem Projekt nicht zugeordnet')
        original = bytes(row['original']); capture = json.loads(row['payload_json'])
        if not original or _sha(original) != row['sha256'] or capture.get('sha256') != row['sha256']:
            raise Problem(409, 'Eingangsoriginal besteht die Integritätsprüfung nicht')
        review = self.office.db.execute('SELECT * FROM business_receipt_reviews WHERE receipt_id=? ' +
            ('AND revision=?' if revision is not None else 'ORDER BY revision DESC LIMIT 1'),
            (receipt_id, revision) if revision is not None else (receipt_id,)).fetchone()
        if not review:
            return None
        if _sha(review['payload_json']) != review['payload_sha256']:
            raise Problem(409, 'Belegprüfung besteht die Integritätsprüfung nicht')
        value = json.loads(review['payload_json'])
        if value.get('status') not in ('reviewed', 'rejected'):
            return None
        if value.get('currency') != 'EUR' or _amount(value['net']) + _amount(value['tax']) != _amount(value['gross']):
            raise Problem(409, 'Geprüfte Belegbeträge sind nicht konsistent')
        iso_date(value['issue_date'])
        proof = dict(receipt={key: row[key] for key in row.keys() if key != 'original'}, review=dict(review))
        return dict(receipt_id=receipt_id, project_id=project_id, filename=row['filename'],
            original_sha256=row['sha256'], review_sha256=review['payload_sha256'],
            source_hash=_sha(canonical(proof)), review_revision=review['revision'], review_status=value['status'],
            source_path='/finance/receipts/' + receipt_id,
            **{key: value[key] for key in ('vendor', 'invoice_number', 'issue_date', 'net', 'tax', 'gross', 'currency')})

    def _entries(self, project_id, receipt_id):
        rows = self.office.db.execute('SELECT * FROM business_project_cost_versions WHERE receipt_id=? ORDER BY revision',
                                     (receipt_id,)).fetchall()
        result = []; previous_hash = '0' * 64
        for row in rows:
            value = json.loads(row['entry_json'])
            if (row['project_id'] != project_id or row['revision'] != len(result) + 1 or row['previous_hash'] != previous_hash
                    or _sha(row['entry_json']) != row['entry_sha256'] or value.get('entry_hash') is not None):
                raise Problem(409, 'Projektkostenhistorie besteht die Integritätsprüfung nicht')
            expected = {'id', 'project_id', 'receipt_id', 'revision', 'source_revision', 'source', 'allocations',
                        'reason', 'previous_hash', 'preview_hash', 'created_by', 'created_at'}
            if set(value) != expected or any(value[key] != row[key] for key in
                    ('id', 'project_id', 'receipt_id', 'revision', 'source_revision', 'previous_hash', 'created_by', 'created_at')):
                raise Problem(409, 'Projektkosteneinordnung und Index stimmen nicht überein')
            normalized = _body({key: value[key] for key in _INPUT - {'expected_revision'}} |
                               {'expected_revision': value['revision'] - 1})
            if normalized['allocations'] != value['allocations'] or normalized['reason'] != value['reason']:
                raise Problem(409, 'Ungültige gespeicherte Kostenanteile')
            source = self._source(None, project_id, receipt_id, value['source_revision'])
            if source != value['source'] or source is None or sum((_amount(a['amount_net']) for a in value['allocations']), Decimal(0)) != _amount(source['net']):
                raise Problem(409, 'Kostenanteile stimmen nicht mit dem ursprünglichen Beleg überein')
            if source['original_sha256'] != row['original_sha256']:
                raise Problem(409, 'Projektkosten-Originalbindung stimmt nicht überein')
            if source['review_status'] == 'rejected' and any(item['category'] != 'excluded' for item in value['allocations']):
                raise Problem(409, 'Abgelehnter Beleg enthält bestätigte Projektkosten')
            if any(item['category'] != 'excluded' for item in value['allocations']) and self._duplicate_original(receipt_id, source['original_sha256']):
                raise Problem(409, 'Dasselbe Eingangsoriginal ist mehrfach als Projektkostenquelle eingeordnet')
            preview = dict(normalized, source=source, previous_entry_id=result[-1]['id'] if result else None)
            if value['preview_hash'] != _sha(canonical(preview)):
                raise Problem(409, 'Kostenfreigabe stimmt nicht mit ihrer Vorschau überein')
            previous_hash = row['entry_sha256']
            result.append(dict(value, entry_hash=previous_hash))
        return result

    def _preview(self, actor, data):
        inputs = _body(data)
        self._access(actor, inputs['project_id'], write=True)
        source = self._source(actor, inputs['project_id'], inputs['receipt_id'])
        if source is None:
            raise Problem(409, 'Eingangsbeleg zuerst vollständig prüfen')
        entries = self._entries(inputs['project_id'], inputs['receipt_id'])
        if source['review_revision'] != inputs['source_revision']:
            raise Problem(409, 'Belegprüfung wurde inzwischen geändert')
        if len(entries) != inputs['expected_revision']:
            raise Problem(409, 'Projektkosteneinordnung wurde inzwischen geändert')
        if sum((_amount(a['amount_net']) for a in inputs['allocations']), Decimal(0)) != _amount(source['net']):
            raise Problem(409, 'Alle Kostenanteile müssen genau den dokumentierten Nettobetrag ergeben')
        if source['review_status'] == 'rejected' and any(item['category'] != 'excluded' for item in inputs['allocations']):
            raise Problem(409, 'Abgelehnte Eingangsbelege dürfen nur begründet ausgeschlossen werden')
        if any(item['category'] != 'excluded' for item in inputs['allocations']) and self._duplicate_original(inputs['receipt_id'], source['original_sha256']):
            raise Problem(409, 'Dieses Original wurde bereits eingeordnet; doppelte Erfassung begründet ausschließen')
        value = dict(inputs, source=source, previous_entry_id=entries[-1]['id'] if entries else None)
        return dict(value, preview_hash=_sha(canonical(value)))

    def preview(self, actor, data):
        with transaction(self.office):
            return self._preview(actor, data)

    def confirm(self, actor, data):
        if not isinstance(data, dict) or set(data) != _INPUT | {'request_id', 'preview_hash'}:
            raise Problem(400, 'Vollständige geprüfte Projektkosteneinordnung erwartet')
        identifier(data['request_id'], 'Vorgangs-ID')
        if not isinstance(data['preview_hash'], str) or not re.fullmatch(r'[a-f0-9]{64}', data['preview_hash']):
            raise Problem(400, 'Vorschau-Prüfsumme erwartet')
        try:
            request_json = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            if len(request_json.encode('utf-8')) > 1_000_000:
                raise Problem(413, 'Projektkosteneinordnung ist zu groß')
            digest = _sha(request_json)
        except (ValueError, TypeError, UnicodeError):
            raise Problem(400, 'Gültige JSON-Einordnung erwartet') from None
        with transaction(self.office):
            fresh = self._access(actor, data['project_id'], write=True)
            # The original is reauthorized even for successful historical replay.
            self._source(fresh, data['project_id'], data['receipt_id'])
            request = self.office.db.execute('SELECT * FROM business_project_cost_requests WHERE user_id=? AND request_id=?',
                                            (fresh['id'], data['request_id'])).fetchone()
            if request:
                if request['request_hash'] != digest or request['request_json'] != request_json:
                    raise Problem(409, 'Vorgangskennung wurde bereits anders verwendet')
                entries = self._entries(data['project_id'], data['receipt_id'])
                result = next((entry for entry in entries if entry['id'] == request['entry_id']), None)
                if result is None:
                    raise Problem(409, 'Empfangsbestätigung ohne zugehörige Kosteneinordnung')
                return result
            try:
                financial_release(self.office)
                preview = self._preview(fresh, {key: data[key] for key in _INPUT})
                if preview['preview_hash'] != data['preview_hash']:
                    raise Problem(409, 'Geprüfte Kostenvorschau wurde geändert')
            except Problem as error:
                if error.status == 409:
                    raise Problem(409, error.message, request_resolution='not_accepted') from None
                raise
            previous = self._entries(data['project_id'], data['receipt_id'])
            value = {key: preview[key] for key in ('project_id', 'receipt_id', 'source_revision', 'source', 'allocations', 'reason', 'preview_hash')}
            value.update(id=uuid.uuid4().hex, revision=len(previous) + 1, previous_hash=previous[-1]['entry_hash'] if previous else '0' * 64,
                         created_by=fresh['id'], created_at=self.now())
            encoded = canonical(value); entry_hash = _sha(encoded)
            self.office.db.execute('INSERT INTO business_project_cost_versions(id,project_id,receipt_id,revision,source_revision,'
                'previous_hash,original_sha256,entry_json,entry_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                tuple(value[key] for key in ('id', 'project_id', 'receipt_id', 'revision', 'source_revision', 'previous_hash')) +
                (value['source']['original_sha256'], encoded, entry_hash, fresh['id'], value['created_at']))
            self.office.db.execute('INSERT INTO business_project_cost_requests(user_id,request_id,request_json,request_hash,entry_id) VALUES(?,?,?,?,?)',
                                  (fresh['id'], data['request_id'], request_json, digest, value['id']))
            self.office.audit(fresh, 'business.project_cost.classified', value['id'])
            return dict(value, entry_hash=entry_hash)

    def sources(self, actor, project_id):
        with transaction(self.office):
            self._access(actor, project_id)
            items = []
            for row in self.office.db.execute('SELECT id FROM business_incoming_receipts WHERE project_id=? ORDER BY created_at,id', (project_id,)).fetchall():
                receipt = Finance(self.office).receipt(actor, row['id'])
                source = self._source(actor, project_id, row['id'])
                entries = self._entries(project_id, row['id'])
                last = entries[-1] if entries else None
                status = ('unreviewed' if source is None else 'unclassified' if last is None else
                          'current' if last['source'] == source else 'source_changed')
                items.append(dict(receipt, latest_entry=last, classification_revision=len(entries),
                                  classification_status=status, source=source,
                                  source_path='/finance/receipts/' + row['id']))
            return dict(items=items)

    def history(self, actor, project_id, receipt_id):
        with transaction(self.office):
            self._access(actor, project_id)
            self._source(actor, project_id, receipt_id)
            return dict(items=self._entries(project_id, receipt_id))

    def summary(self, actor, project_id):
        from business_inventory import BusinessInventory
        from business_accounting_allocations import effective_allocations, effective_paid, installed
        with transaction(self.office):
            self._access(actor, project_id)
            inventory = BusinessInventory(self.office).cost_report(actor, project_id)
            sources = self.sources(actor, project_id)['items']
            issues = []
            if inventory['missing_rates_count']:
                issues.append(dict(code='missing_labor_rates', message='Für genehmigte Zeiten fehlen historische Kostensätze.'))
            extra = {category: Decimal(0) for category in CATEGORIES}
            allocations = []
            for source in sources:
                last = source['latest_entry']
                if source['classification_status'] != 'current':
                    issues.append(dict(code='receipt_' + source['classification_status'], source_id=source['id'],
                        source_path=source['source_path'], message='Eingangsbeleg prüfen oder seine Kosteneinordnung mit der aktuellen Belegprüfung abgleichen.'))
                if last:
                    for item in last['allocations']:
                        extra[item['category']] += _amount(item['amount_net'])
                        allocations.append(dict(item, entry_id=last['id'], receipt_id=source['id'], revision=last['revision'],
                            source_revision=last['source_revision'], vendor=last['source']['vendor'],
                            invoice_number=last['source']['invoice_number'], source_path=source['source_path'],
                            classification_status=source['classification_status']))
            costs = dict(material_net=inventory['material_actual_net'], labor_net=inventory['labor_actual_net'],
                external_service_net=money(extra['external_service']), machine_net=money(extra['machine']), other_net=money(extra['other']))
            actual = sum((_signed_amount(value) for value in costs.values()), Decimal(0))
            costs['total_net'] = money(actual)
            documents = []; invoice_net = invoice_gross = credit_net = credit_gross = Decimal(0)
            invoice_ids = set()
            for row in self.office.db.execute("SELECT * FROM business_documents WHERE project_id=? AND status='final' ORDER BY finalized_at,id", (project_id,)).fetchall():
                if row['kind'] not in INVOICES:
                    continue
                if _sha(row['payload_json']) != row['payload_sha256']:
                    raise Problem(409, 'Rechnungsarchiv besteht die Integritätsprüfung nicht')
                value = Documents(self.office).get(actor, row['id'])
                net, gross = _amount(value['totals']['net']), _amount(value['totals']['gross'])
                # Cumulative/final totals already contain only the additional
                # liability. Contract totals must never be added again.
                if row['kind'] == 'credit_note':
                    credit_net += net; credit_gross += gross
                else:
                    invoice_net += net; invoice_gross += gross; invoice_ids.add(row['id'])
                documents.append(dict(id=row['id'], number=row['number'], kind=row['kind'], issue_date=value['issue_date'],
                    net=money(net), gross=money(gross), source_path='/documents/' + row['id']))
            payments = []; receipts_gross = refunds_gross = Decimal(0)
            candidates = set()
            for doc_id in invoice_ids:
                candidates.update(row['payment_id'] for row in self.office.db.execute('SELECT payment_id FROM business_payment_allocations WHERE document_id=?', (doc_id,)).fetchall())
                if installed(self.office):
                    candidates.update(row['payment_id'] for row in self.office.db.execute('SELECT payment_id FROM business_accounting_allocation_entries WHERE document_id=?', (doc_id,)).fetchall())
            for payment_id in sorted(candidates):
                payment = self.office.db.execute('SELECT id,kind,booking_date FROM business_payments WHERE id=?', (payment_id,)).fetchone()
                if not payment or payment['kind'] not in ('receipt', 'refund'):
                    raise Problem(409, 'Zahlungsquelle fehlt oder ist ungültig')
                for allocation in effective_allocations(self.office, payment_id):
                    if allocation['document_id'] not in invoice_ids:
                        continue
                    amount = _amount(allocation['amount'])
                    if payment['kind'] == 'receipt': receipts_gross += amount
                    else: refunds_gross += amount
                    # Expose only this project's allocation, never another
                    # project's amounts or the full mixed payment reference.
                    payments.append(dict(payment_id=payment_id, document_id=allocation['document_id'], kind=payment['kind'],
                        amount_gross=money(amount), booking_date=payment['booking_date'], scope='project_allocation',
                        source_path='/documents/' + allocation['document_id']))
            net_inflow = receipts_gross - refunds_gross
            if sum((effective_paid(self.office, doc_id) for doc_id in invoice_ids), Decimal(0)) != net_inflow:
                raise Problem(409, 'Zahlungsquellen stimmen nicht mit der Projektzuordnung überein')
            revenue_net = invoice_net - credit_net
            budget_total = _signed_amount(inventory['budget_net']) + _signed_amount(inventory['approved_changes_net'])
            complete = not issues
            supplier_payments = []; supplier_outflows = Decimal(0); cash_complete = True
            from business_accounting import Accounting
            accounting = Accounting(self.office)
            try:
                accounting_actor = accounting._access(actor)
            except Problem as error:
                if error.status not in (403, 404): raise
                cash_complete = False
                issues.append(dict(code='supplier_cash_access_missing', message='Bestätigte Lieferantenauszahlungen benötigen die gesonderte Buchhaltungs-Lesefreigabe.'))
            if cash_complete:
                for row in self.office.db.execute("SELECT l.event_id,l.receipt_id FROM business_accounting_source_links l "
                        "JOIN business_incoming_receipts r ON r.id=l.receipt_id WHERE l.kind='receipt' AND r.project_id=? ORDER BY l.receipt_id,l.cash_revision", (project_id,)).fetchall():
                    event = accounting._event(accounting_actor, row['event_id'])
                    if event['direction'] != 'out':
                        raise Problem(409, 'Ungültige Richtung des belegten Lieferantengeldflusses')
                    supplier_outflows += _amount(event['amount'])
                    supplier_payments.append(dict(event_id=event['id'], receipt_id=row['receipt_id'], amount_gross=event['amount'],
                        cash_date=event['cash_date'], source_path='/accounting/events/' + event['id']))
            from business_schema import state
            environment = state(self.office)
            if environment.get('restore_pending') or environment.get('financial_reconciliation_required'):
                cash_complete = False
                issues.append(dict(code='cash_restore_reconciliation_pending',
                    message='Nach Wiederherstellung muss der tatsächliche Zahlungsstand zunächst abgeglichen werden.'))
            return dict(project_id=project_id, currency='EUR', valuation_basis='document_net', tax_result_available=False,
                budget=dict(revision=inventory['budget_revision'], base_net=inventory['budget_net'],
                    approved_changes_net=inventory['approved_changes_net'], total_net=money(budget_total),
                    remaining_net=money(budget_total-actual) if complete and inventory['budget_revision'] else None),
                costs=costs, revenue=dict(invoiced_net=money(invoice_net), credited_net=money(credit_net), revenue_net=money(revenue_net),
                    invoiced_gross=money(invoice_gross), credited_gross=money(credit_gross)),
                payments=dict(receipts_gross=money(receipts_gross), refunds_gross=money(refunds_gross),
                    net_inflow_gross=money(net_inflow), open_gross=money(invoice_gross-credit_gross-net_inflow),
                    supplier_outflows_gross=money(supplier_outflows) if cash_complete else None,
                    cash_balance_gross=money(net_inflow-supplier_outflows) if cash_complete else None, complete=cash_complete),
                result=dict(document_net_contribution=money(revenue_net-actual) if complete else None,
                    complete_for_recorded_sources=complete, scope='recorded_sources_only'), issues=issues,
                sources=dict(material_movements=inventory['material_movements'], approved_times=inventory['approved_times'],
                    receipt_allocations=allocations, documents=documents, payment_allocations=payments,
                    approved_changes=inventory['approved_changes'], supplier_payments=supplier_payments))


def validate_integrity(office):
    api = ProjectEconomics(office)
    try:
        entries = {}
        for row in office.db.execute('SELECT DISTINCT project_id,receipt_id FROM business_project_cost_versions').fetchall():
            for entry in api._entries(row['project_id'], row['receipt_id']):
                entries[entry['id']] = entry
        seen = set()
        for row in office.db.execute('SELECT * FROM business_project_cost_requests').fetchall():
            identifier(row['request_id'])
            if _sha(row['request_json']) != row['request_hash']:
                raise ValueError('Invalid project cost request hash')
            data = json.loads(row['request_json']); inputs = _body({key: data[key] for key in _INPUT})
            entry = entries.get(row['entry_id'])
            if (not entry or entry['id'] in seen or entry['created_by'] != row['user_id'] or data['request_id'] != row['request_id']
                    or set(data) != _INPUT | {'request_id', 'preview_hash'} or data['preview_hash'] != entry['preview_hash']
                    or inputs['expected_revision'] != entry['revision'] - 1
                    or any(inputs[key] != entry[key] for key in _INPUT - {'expected_revision'})):
                raise ValueError('Invalid project cost confirmation')
            seen.add(entry['id'])
        if seen != set(entries):
            raise ValueError('Project cost history lacks confirmations')
    except (Problem, ValueError, KeyError, TypeError, InvalidOperation, UnicodeError) as error:
        raise ValueError('Invalid project cost ledger') from error
    return True


def methods(path):
    if path in ('/project-economics', '/project-economics/sources') or re.fullmatch(r'/project-economics/receipts/[a-f0-9]{32}', path):
        return 'GET'
    if path in ('/project-economics/preview', '/project-economics/confirm'):
        return 'POST'
    return None


def dispatch(office, actor, path, method, data):
    if methods(path) is None:
        return None
    if method != methods(path):
        raise Problem(405, 'Methode nicht unterstützt')
    if not isinstance(data, dict):
        raise Problem(400, 'JSON-Objekt erwartet')
    api = ProjectEconomics(office)
    if method == 'GET':
        if set(data) != {'_query'} or not isinstance(data['_query'], dict) or set(data['_query']) != {'project_id'}:
            raise Problem(400, 'Genau eine Projektkennung erwartet')
        project_id = data['_query']['project_id']; identifier(project_id, 'Projekt-ID')
        if path == '/project-economics': result = api.summary(actor, project_id)
        elif path.endswith('/sources'): result = api.sources(actor, project_id)
        else: result = api.history(actor, project_id, path.rsplit('/', 1)[-1])
        return result, 200, 'application/json'
    if '_query' in data:
        raise Problem(400, 'Keine zusätzlichen Filter erlaubt')
    action = path.rsplit('/', 1)[-1]
    return getattr(api, action)(actor, data), 201 if action == 'confirm' else 200, 'application/json'
