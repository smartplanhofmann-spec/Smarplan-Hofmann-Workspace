"""Deterministic v1 evidence supplement to an already frozen EÜR export.

Read only. This version must remain reproducible; incompatible output changes
belong in a new format module. Private payroll/travel rows are never collected.
"""
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from core import Problem, canonical
from business_accounting import Accounting
from business_accounting_euer import EuerAccounting
from business_company_handover import snapshot_transaction, _binding
from business_operations import identifier

FORMAT = 'smartplan-year-evidence-v1'
MAX_BYTES = 128 * 1024 * 1024
MAX_FILES = 10000
MAX_JOURNAL = 100000
BASE = '/accounting/euer/exports/'
README = '''SMARTPLAN – JAHRESPRÜFSTAND MIT ORIGINALEN, VERSION 1

report.json und postings.csv sind der ursprünglich bestätigte EÜR-Prüfstand.
journal.json enthält die zugehörigen Entscheidungen und ursprünglichen Befehle.
proofs.json verbindet die Quellen mit den unveränderten Dateien in originals/.
Andere Journalpositionen sind nur durch Sequenz und Hash gebunden. Notwendige
frühere Belege können außerhalb des Berichtsjahres liegen.

Dies ist ein eigenes Prüf-/Übergabeformat, kein DATEV-Importformat, keine
Steuererklärung, keine elektronische Signatur und keine fachliche Steuerfreigabe.
Offene Fragen des ursprünglichen Berichts bleiben offen. Öffentliche Lohn- und
Reisegeldprojektionen enthalten ausdrücklich keine privaten Personaloriginale.
Ihre private Berechnung kann mit diesem Finanzpaket nicht geprüft werden.

Das Archiv enthält finanzielle Originale und ist nicht verschlüsselt. Es wurde
an niemanden gesendet. Nur berechtigten Empfängern in geschützter Ablage geben.
Zuerst den ZIPhash mit dem separat in Smartplan angezeigten Hash vergleichen.
Den Prüfer aus einer vertrauenswürdigen Installation verwenden; ein fremdes
Archivskript nicht ungeprüft starten. Der beigefügte Prüfer ist eigenständig:
python verify_year_package.py DATEI.zip --sha256 SEPARAT_BESTAETIGTER_ZIPHASH
Es werden keine Archivdateien extrahiert oder ausgeführt und keine Dienste
kontaktiert. Hashkonsistenz allein beweist keine externe Herkunft.

GRENZE DER ALTEN JOURNALE: Das Paket enthält die aufgelösten Originale.
Die alten Export-/Quellpayloads binden keinen vollständigen Abhängigkeitsindex;
intrinsische Vollständigkeit sämtlicher Ursprungsnachweise ist nicht bewiesen.
Die Verifikation benötigt deshalb zwingend den separat in der authentisierten
Smartplan-Sitzung bestätigten Archivhash. Ein im Archiv selbst mitgelieferter
oder aus einer unbekannten Datei berechneter Hash ersetzt diesen Anker nicht.
Erfolgreiche Archivhashprüfung bedeutet keine vollständige fachliche Prüfung.
'''


def sha(value):
    if not isinstance(value, bytes):
        value = (value if isinstance(value, str) else canonical(value)).encode()
    return hashlib.sha256(value).hexdigest()


def select_entries(export, prefix):
    """Same economic targets and their earlier proofs, never later decisions."""
    report = export['artifact']['report']; year = str(report['year'])
    selected = {row['entry_id'] for row in report['postings']}
    selected.update(row['entry_id'] for row in report['sources'])
    selected.update(row['entry_id'] for row in report['assets'])
    by_id = {row['id']: row for row in prefix}
    while True:
        before = set(selected)
        targets = {by_id[key]['target'] for key in selected}
        for row in prefix:
            if row['target'] in targets and row['operation'] != 'export':
                selected.add(row['id'])
            if row['operation'] == 'period' and row['payload']['period'].startswith(year):
                selected.add(row['id'])
        for key in list(selected):
            row = by_id[key]
            if row['reverses']:
                selected.add(row['reverses'])
            if row['effect'] and row['effect']['operation'] == 'depreciation':
                selected.add(row['effect']['payload']['asset_entry_id'])
            # A cash classification refers to the original input-VAT decision,
            # which may be from a previous year and absent from current totals.
            if row['effect']:
                source = row['effect']['source']
                original = source.get('receipt', {}).get('original_sha256')
                if source['kind'] == 'cash' and source['event']['source']['kind'] == 'receipt':
                    original = source['event']['source']['snapshot']['original_sha256']
                if original:
                    selected.update(v['id'] for v in prefix if v['target'] in ('input_vat:' + original, 'asset:' + original))
        if selected == before:
            return [row for row in prefix if row['id'] in selected]


def authorize_report(office, actor, report):
    """Even unresolved old report references must pass today's source access."""
    from accounting_joint_access import authorize_sources
    from business_accounting_allocations import require_effective_payment_access
    from business_finance import Finance
    seen=set()
    for value in report['cash_movements'] + report['issues']:
        path=value.get('source_path');source_id=value.get('source_id')
        if path is None or path=='/accounting/profile':
            continue
        identity=(path,source_id)
        if identity in seen:continue
        seen.add(identity)
        match=re.fullmatch(r'/accounting/events/([a-f0-9]{32})',path)
        receipt=re.fullmatch(r'/finance/receipts/([a-f0-9]{32})',path)
        if match:authorize_sources(office,actor,match[1])
        elif receipt:Finance(office)._incoming(actor,receipt[1])
        elif path=='/accounting/sources/payments':require_effective_payment_access(office,actor,source_id,'finance.read')
        elif path.startswith('/payroll/cash/financial/'):
            from business_payroll_cash import financial_access
            financial_access(office,actor)
        elif path.startswith('/personnel/travel/financial/'):
            from travel_allowance_cash import financial_access
            financial_access(office,actor)
        elif path.startswith('/accounting/historical-assets/'):
            from business_accounting_asset_openings import financial_access
            financial_access(office,actor)
        elif path=='/accounting/open-items' or path.startswith('/accounting/open-items/'):
            from business_accounting_open_items import financial_access
            financial_access(office,actor)
        else:
            raise Problem(409,'Unbekannter alter Berichtsverweis benötigt einen eigenen Jahrespaketvertrag.')


class Collector:
    def __init__(self, office, actor):
        self.office, self.actor = office, actor
        self.nodes, self.originals, self.visited = {}, {}, set()
        self.bytes = 0
        self.node_bytes = 0

    def node(self, key, kind, payload, *, links=(), originals=()):
        value = dict(id=key, kind=kind, payload=payload, payload_sha256=sha(payload),
                     links=sorted(set(links)), originals=sorted(set(originals)))
        if key in self.nodes and self.nodes[key] != value:
            raise Problem(409, 'Widersprüchliche ursprüngliche Nachweisbindung.')
        if key not in self.nodes:
            self.node_bytes += len(canonical(value).encode())
            if self.node_bytes + self.bytes > MAX_BYTES:
                raise Problem(413, 'Jahresnachweise überschreiten die geprüfte Größe.')
        self.nodes[key] = value
        if len(self.nodes) > MAX_FILES:
            raise Problem(413, 'Jahresnachweis überschreitet die geprüfte Anzahl.')
        return key

    def original(self, raw, expected, metadata):
        if not isinstance(raw, bytes) or sha(raw) != expected:
            raise Problem(409, 'Originalbytes stimmen nicht mit der gebundenen Prüfsumme überein.')
        path = 'originals/' + expected + '.bin'
        if path not in self.originals:
            self.bytes += len(raw)
            if self.bytes + self.node_bytes > MAX_BYTES:
                raise Problem(413, 'Jahresoriginale überschreiten die geprüfte Größe.')
            self.originals[path] = dict(raw=raw, sha256=expected, size=len(raw), descriptions=[])
        if metadata not in self.originals[path]['descriptions']:
            self.originals[path]['descriptions'].append(metadata)
        return path

    def receipt(self, receipt_id, revision):
        key = 'receipt:' + receipt_id + ':' + str(revision)
        if key in self.nodes:
            return key
        public, proof = Accounting(self.office)._receipt_source(self.actor, receipt_id, revision)
        if public is None or public['review_revision'] != revision:
            raise Problem(409, 'Ursprüngliche geprüfte Eingangsbelegfassung fehlt.')
        row = self.office.db.execute('SELECT original FROM business_incoming_receipts WHERE id=?', (receipt_id,)).fetchone()
        path = self.original(bytes(row['original']), public['original_sha256'],
                             dict(kind='receipt', id=receipt_id, filename=public['filename'], media_type=public['media_type']))
        return self.node(key, 'receipt', dict(public=public, proof=proof), originals=[path])

    def document(self, document_id):
        key = 'document:' + document_id
        if key in self.nodes:
            return key
        from business_documents import Documents
        row = Documents(self.office)._row(self.actor, document_id)
        proof = Accounting(self.office)._document_proof(row)
        archive = self.office.db.execute('SELECT * FROM business_document_archives WHERE document_id=?', (document_id,)).fetchone()
        originals = [self.original(bytes(archive['pdf']), proof['pdf_sha256'],
                    dict(kind='document_pdf', id=document_id, filename=proof['number']+'.pdf', media_type='application/pdf'))]
        if archive['xml'] is not None:
            originals.append(self.original(bytes(archive['xml']), proof['xml_sha256'],
                dict(kind='document_xml', id=document_id, filename=proof['number']+'.xml', media_type='application/xml')))
        payload = json.loads(archive['payload_json'])
        # Mark before following invoice-chain links, so malformed cycles cannot
        # recurse indefinitely. Domain integrity rejects changed original data.
        self.node(key, 'document', dict(proof=proof, payload=payload), originals=originals)
        links = [self.document(value) for value in payload.get('previous_document_ids', [])]
        return self.node_replace(key, links)

    def node_replace(self, key, links):
        self.nodes[key]['links'] = sorted(set(links))
        return key

    def embedded(self, value):
        """Only explicit frozen financial references; never current catalogs."""
        links = set()
        if isinstance(value, list):
            for part in value:
                links.update(self.embedded(part))
        elif isinstance(value, dict):
            if value.get('document_id'):
                links.add(self.document(value['document_id']))
            if value.get('receipt_id') and type(value.get('review_revision')) is int:
                links.add(self.receipt(value['receipt_id'], value['review_revision']))
            # Archive proofs hold the complete historical document under this
            # key rather than a document_id field.
            if isinstance(value.get('document'), dict) and value['document'].get('id'):
                links.add(self.document(value['document']['id']))
            for name, part in value.items():
                if name.endswith('_json') and isinstance(part, str):
                    part = json.loads(part)
                links.update(self.embedded(part))
        return links

    def component(self, version, entry_id):
        names = dict(c1='component', c2='capacity', r1='refund', r2='refunds_v2')
        family = names[version]; key = 'component:' + version + ':' + entry_id
        if key in self.nodes:
            return key
        table = 'business_accounting_' + family + '_entries'
        row = self.office.db.execute('SELECT * FROM ' + table + ' WHERE id=?', (entry_id,)).fetchone()
        if row is None:
            raise Problem(409, 'Ursprüngliche dokumentarische Zahlungsaufteilung fehlt.')
        payload = dict(entry=json.loads(row['entry_json']), entry_sha256=row['entry_sha256'], proof=json.loads(row['proof_json']))
        self.node(key, 'documentary_component', payload)
        links = self.embedded(payload)
        # Historic pool references are explicit entry IDs. Resolve only the
        # four already supported documentary families, not arbitrary tables.
        def walk(value):
            if isinstance(value, dict):
                for name, part in value.items():
                    if name in ('entry_id', 'origin_entry_id', 'component_entry_id') and isinstance(part, str) and part != entry_id:
                        for ver, suffix in names.items():
                            found = self.office.db.execute('SELECT id FROM business_accounting_' + suffix + '_entries WHERE id=?', (part,)).fetchone()
                            if found:
                                links.add(self.component(ver, part))
                    walk(part)
            elif isinstance(value, list):
                for part in value:
                    walk(part)
        walk(payload['proof'])
        return self.node_replace(key, links)

    def asset(self, source):
        from business_accounting_asset_openings import HistoricalAssets
        api = HistoricalAssets(self.office); api._access(self.actor)
        ledger = api._ledger(); current = ledger['by_id'][source['id']]; links = []
        for row in ledger['entries']:
            if row['asset_key'] != current['asset_key'] or row['revision'] > current['revision']:
                continue
            original, raw = api._original(row['source_proof']['original']['id'])
            path = self.original(raw, row['source_proof']['original']['sha256'],
                dict(kind='historical_asset', id=original['id'], filename=original['filename'], media_type=original['media_type']))
            links.append(self.node('asset:' + row['id'], 'historical_asset', row, originals=[path]))
        return links

    def open_item(self, source):
        from business_accounting_open_items import OpeningItems
        api = OpeningItems(self.office); api._access(self.actor)
        ledger = api._ledger(); payment = ledger['by_id'][source['entry_id']]; item = ledger['by_id'][source['item_id']]; links = []
        for row in ledger['entries']:
            relevant = row['entity_key'] == item['entity_key'] or row['operation'] == 'payment' and row['payload']['item_key'] == item['entity_key']
            if not relevant or row['sequence'] > payment['sequence']:
                continue
            paths = []
            for proof in row['proofs']:
                original, raw = api._original(proof['id'])
                paths.append(self.original(raw, proof['sha256'],
                    dict(kind='opening_item', id=original['id'], filename=original['filename'], media_type=original['media_type'])))
            links.append(self.node('opening_item:' + row['id'], 'opening_item', row, originals=paths))
        return links

    def source(self, source):
        if source.get('kind') not in ('receipt','cash','opening_asset','opening_item_cash','payroll_cash','travel_cash'):
            raise Problem(409, 'Diese Finanzquelle benötigt einen ausdrücklichen Jahrespaketvertrag.')
        key = 'source:' + source['source_hash']
        if key in self.nodes:
            return key
        EuerAccounting(self.office)._source_access(self.actor, source)
        kind = source['kind']; links = []
        if kind == 'receipt':
            r = source['receipt']; links.append(self.receipt(r['receipt_id'], r['review_revision']))
        elif kind == 'cash':
            event = source['event']; original = event['source']
            links.append(self.cash_original(event))
            links.extend(self.component(unit['version'], unit['entry_id']) for unit in source['units'])
        elif kind == 'opening_asset':
            links.extend(self.asset(source))
        elif kind == 'opening_item_cash':
            links.extend(self.open_item(source))
        elif kind not in ('payroll_cash', 'travel_cash'):
            raise Problem(409, 'Diese Finanzquelle benötigt einen ausdrücklichen Jahrespaketvertrag.')
        if source.get('payment_event'):
            # The accepted prepayment proof contains the original event only.
            # Later documentary components must not enter an earlier export.
            links.append(self.cash_original(source['payment_event']))
        return self.node(key, 'source', source, links=links)

    def cash_original(self,event):
        original=event['source']
        row=self.office.db.execute('SELECT proof_json FROM business_accounting_source_links WHERE event_id=?',(event['id'],)).fetchone()
        if row is None:raise Problem(409,'Ursprüngliche Geldflussbindung fehlt.')
        proof=json.loads(row['proof_json'])
        if sha(proof)!=original['source_hash']:
            raise Problem(409,'Geldfluss ist mit einem anderen Originalnachweis verbunden.')
        return self.node('cash:'+event['id'],'cash_original',proof,links=self.embedded(original['snapshot']))


def build(office, actor, export_id):
    identifier(export_id)
    with snapshot_transaction(office):
        api = EuerAccounting(office); fresh = api._access(actor)
        instance_id = _binding(office)
        ledger = api._ledger(); export = ledger['by_id'].get(export_id)
        if not export or export['operation'] != 'export':
            raise Problem(404, 'Bestätigter Jahresprüfstand nicht verfügbar.')
        report = export['artifact']['report']; prefix = ledger['entries'][:report['revision']]
        authorize_report(office,fresh,report)
        if len(prefix) > MAX_JOURNAL:
            raise Problem(413, 'Journalpräfix überschreitet die geprüfte Jahrespaketgröße.')
        selected = select_entries(export, prefix); collector = Collector(office, fresh)
        for entry in selected:
            if entry['effect']:
                collector.source(entry['effect']['source'])
        for row in report.get('historical_assets', []):
            collector.source(row['source'])
        decisions = []
        for entry in selected + [export]:
            accepted = office.db.execute('SELECT * FROM business_euer_requests WHERE entry_id=?', (entry['id'],)).fetchone()
            decisions.append(dict(entry=entry, acceptance=dict(accepted)))
        # Access all embedded originals above before emitting a single byte.
        api._access(fresh)
        payloads = {
            'report.json': canonical(report).encode(),
            'postings.csv': export['artifact']['csv'].encode(),
            'journal.json': canonical(dict(export_id=export_id, decisions=decisions,
                prefix=[dict(sequence=row['sequence'], entry_hash=row['entry_hash'], target_hash=sha(row['target'])) for row in prefix])).encode(),
            'proofs.json': canonical(dict(nodes=[collector.nodes[key] for key in sorted(collector.nodes)])).encode(),
            'README.txt': README.encode(),
            'verify_year_package.py': Path(__file__).with_name('accounting_year_verify_v1.py').read_bytes(),
        }
        originals = []
        for path, value in sorted(collector.originals.items()):
            payloads[path] = value['raw']
            originals.append(dict(path=path, sha256=value['sha256'], size=value['size'], descriptions=sorted(value['descriptions'], key=canonical)))
        boundaries = sorted({node['payload']['kind'] for node in collector.nodes.values()
                             if node['kind']=='source' and node['payload']['kind'] in ('payroll_cash','travel_cash')})
        manifest = dict(format=FORMAT, schema_version=1, instance_id=instance_id,
            year=report['year'], export_id=export_id, export_hash=export['entry_hash'],
            report_sha256=export['artifact']['report_sha256'], csv_sha256=export['artifact']['csv_sha256'],
            original_year_complete=report['complete_for_recorded_sources'],
            verification_scope='frozen_report_journal_source_links_and_financial_originals',
            intrinsic_dependency_closure=False,
            required_trust='separately_authenticated_archive_sha256',
            private_source_boundaries=boundaries, private_personnel_originals_included=False,
            official_tax_return=False, datev_certified=False, originals=originals,
            files=[dict(path=key, sha256=sha(raw), size=len(raw)) for key, raw in sorted(payloads.items())])
        payloads['manifest.json'] = canonical(manifest).encode()
        if sum(map(len, payloads.values())) > MAX_BYTES or len(payloads) > MAX_FILES:
            raise Problem(413, 'Jahrespaket überschreitet die geprüfte Ausgabegröße.')
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name, raw in sorted(payloads.items()):
                info = zipfile.ZipInfo(name, (1980,1,1,0,0,0)); info.create_system=3; info.external_attr=0o100600 << 16
                archive.writestr(info, raw)
        raw = stream.getvalue()
        if len(raw) > MAX_BYTES:
            raise Problem(413, 'Jahrespaket überschreitet die geprüfte Ausgabegröße.')
        from accounting_year_verify_v1 import verify
        # The authenticated API publishes this exact newly built hash. This
        # local construction check does not claim independent provenance.
        verify(raw,sha(raw))
        return raw, manifest
