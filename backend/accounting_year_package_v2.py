"""Version 2 adds the original same-year journal carryover; v1 stays frozen."""
import io
import json
from pathlib import Path
import zipfile

from core import Problem, canonical
from business_accounting_euer import EuerAccounting
from business_company_handover import snapshot_transaction, _binding
from business_operations import identifier
import accounting_year_package_v1 as v1
from accounting_year_package_v1 import sha, MAX_BYTES, MAX_FILES, MAX_JOURNAL, BASE, select_entries

FORMAT='smartplan-year-evidence-v2'
README=v1.README.replace('VERSION 1','VERSION 2')+'\nVersion 2 bindet zusätzlich belegte ursprüngliche Jahresvorträge, deren\nAnnahmequittungen und Originaljournale. Alte Zahlungen bleiben historische\nZeilen; das Paket erzeugt keine Geldbewegung und keinen Vorsteueranspruch.\n'


def needed(export,prefix):
    report=export['artifact']['report']
    return (any(row['effect'] and row['effect']['source']['kind']=='opening_year_values'
                for row in select_entries(export,prefix))
            or any(str(row.get('source_path','')).startswith('/accounting/year-values')
                   for row in report['cash_movements']+report['issues']))


def build_selected(office,actor,export_id):
    """Select only from the retained export, never today's source catalog."""
    identifier(export_id)
    with snapshot_transaction(office):
        api=EuerAccounting(office);api._access(actor);ledger=api._ledger();export=ledger['by_id'].get(export_id)
        if not export or export['operation']!='export':raise Problem(404,'Bestätigter Jahresprüfstand nicht verfügbar.')
        prefix=ledger['entries'][:export['artifact']['report']['revision']]
        selected=build if needed(export,prefix) else v1.build
    # The selected export is immutable. The builder starts its own fresh rights
    # and MVCC snapshot; PostgreSQL deliberately refuses nested snapshots.
    return selected(office,actor,export_id)


def authorize_report(office,actor,report):
    from business_accounting_year_openings import financial_access,BASE as YEAR_BASE
    def keep(row):
        path=row.get('source_path','')
        if path==YEAR_BASE or path.startswith(YEAR_BASE+'/'):
            financial_access(office,actor);return False
        return True
    v1.authorize_report(office,actor,dict(report,
        cash_movements=[r for r in report['cash_movements'] if keep(r)],
        issues=[r for r in report['issues'] if keep(r)]))


class Collector(v1.Collector):
    def old_item(self,item_id,item_hash):
        from business_accounting_open_items import OpeningItems
        domain=OpeningItems(self.office);domain._access(self.actor);ledger=domain._ledger();current=ledger['by_id'][item_id]
        if current['operation']!='item' or current['content_hash']!=item_hash:
            raise Problem(409,'Ursprüngliche Jahres-Altpostenbindung fehlt.')
        links=[]
        for row in ledger['entries']:
            if row['operation']!='item' or row['entity_key']!=current['entity_key'] or row['sequence']>current['sequence']:continue
            originals=[]
            for proof in row['proofs']:
                original,raw=domain._original(proof['id'])
                originals.append(self.original(raw,proof['sha256'],dict(kind='opening_item',id=original['id'],filename=original['filename'],media_type=original['media_type'])))
            links.append(self.node('opening_item:'+row['id'],'opening_item',row,originals=originals))
        return links

    def year_values(self,source):
        from business_accounting_year_openings import YearValues,public_source,BASE as YEAR_BASE,TABLES
        from business_accounting_open_items import OpeningItems,BASE as ITEM_BASE
        domain=YearValues(self.office);domain._access(self.actor);ledger=domain._ledger()
        if public_source(self.office,source['id'],source['revision'])!=source:
            raise Problem(409,'Genau passende ursprüngliche Jahresvortragsquelle erforderlich.')
        item_domain=OpeningItems(self.office);links=[]
        for entry in ledger['entries']:
            if entry['entity_key']!=source['id'] or entry['revision']>source['revision']:continue
            originals=[];child=[]
            for proof in entry['proofs']:
                if proof['path']==YEAR_BASE+'/originals/'+proof['id']:original,raw=domain._original(proof['id']);kind='year_values'
                elif proof['path']==ITEM_BASE+'/originals/'+proof['id']:
                    item_domain._access(self.actor);original,raw=item_domain._original(proof['id']);kind='opening_item'
                else:raise Problem(409,'Unbekannte ursprüngliche Jahresoriginalquelle.')
                if original!=proof:raise Problem(409,'Veränderte ursprüngliche Jahresoriginalmetadaten.')
                originals.append(self.original(raw,proof['sha256'],dict(kind=kind,id=original['id'],filename=original['filename'],media_type=original['media_type'])))
            for ref in entry['payload']['sources']:
                if ref['kind']=='opening_item':child.extend(self.old_item(ref['entry_id'],ref['entry_hash']))
                elif ref['kind']!='closed_trade':raise Problem(409,'Unbekannte ursprüngliche Jahresbelegart.')
            if entry['previous_ref']:child.append('year_values:'+entry['previous_ref']['id'])
            receipts=[dict(row) for row in self.office.db.execute("SELECT * FROM "+TABLES[2]+" WHERE operation='confirm'")
                      if json.loads(row['result_json'])=={'entry_id':entry['id']}]
            if len(receipts)!=1:raise Problem(409,'Ursprüngliche Jahresvortragsannahme fehlt.')
            links.append(self.node('year_values:'+entry['id'],'year_values',dict(entry=entry,acceptance=receipts[0]),links=child,originals=originals))
        return links

    def source(self,source):
        if source.get('kind')!='opening_year_values':return super().source(source)
        key='source:'+source['source_hash']
        if key in self.nodes:return key
        EuerAccounting(self.office)._source_access(self.actor,source)
        return self.node(key,'source',source,links=self.year_values(source))

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
            'verify_year_package.py': Path(__file__).with_name('accounting_year_verify_v2.py').read_bytes(),
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
        from accounting_year_verify_v2 import verify
        verify(raw,sha(raw))
        return raw, manifest
