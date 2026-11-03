"""Synthetic original files, mapping, reconciliation and transactional imports."""
import base64
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from business_foundation import BusinessFoundation, _privacy_blockers
from business_migrations import Migrations, FIELDS, parse_rows, protected_tables, validate_integrity, dispatch
from core import Office, Problem


def req(**values):return dict(request_id=uuid.uuid4().hex,**values)


def csv_bytes(rows):
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter=';',lineterminator='\r\n')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-migrations-');self.addCleanup(self.tmp.cleanup)
        self.office=Office(Path(self.tmp.name)/'office.sqlite3');self.addCleanup(self.office.db.close)
        self.owner=dict(id=self.office.add_user('migration-owner@example.test','Synthetic-migration-owner-password','owner'),role='owner')
        self.tech=dict(id=self.office.add_user('migration-tech@example.test','Synthetic-migration-tech-password','technician'),role='technician')
        self.api=Migrations(self.office)
    def problem(self,code,fn,*args):
        with self.assertRaises(Problem) as caught:fn(*args)
        self.assertEqual(caught.exception.status,code,caught.exception.message)
        return caught.exception
    def package(self,**changes):
        values=dict(source_system='hero',source_account='Synthetic source tenant 1',label='Synthetic export',period_from='2026-01-01',period_to='2026-11-03',scope='One synthetic customer, project and historical invoice')
        values.update(changes);return self.api.create(self.owner,req(**values))
    def upload(self,package,name,raw,media='text/csv'):
        body=req(filename=name,media_type=media,content_base64=base64.b64encode(raw).decode())
        result=self.api.upload(self.owner,package['id'],body)
        self.assertEqual(self.api.upload(self.owner,package['id'],body),result)
        return result
    def stage(self,package=None,document_changes=None,contacts=None):
        package=package or self.package();tables=[]
        data={'contact':contacts or [dict(source_id='C1',name='Synthetic historical customer',email='historic@example.test',address='Synthetic street 1',person_name='Synthetic contact',person_email='person@example.test')],
            'project':[dict(source_id='P1',customer_source_id='C1',name='Synthetic historic project')],
            'document':[dict(source_id='D1',customer_source_id='C1',project_source_id='P1',kind='invoice',number='OLD-2026-123',issue_date='2026-06-01',net='100,00',tax='19,00',gross='119,00',currency='EUR',original_filename='invoice.pdf')]}
        data['document'][0].update(document_changes or {})
        for kind,rows in data.items():
            original=self.upload(package,kind+'.csv',csv_bytes(rows))
            tables.append(dict(file_id=original['id'],kind=kind,format='csv',encoding='utf-8-sig',delimiter=';',decimal_separator=',',columns={key:key for key in rows[0]}))
        self.upload(package,'invoice.pdf',b'%PDF-1.7\nSynthetic immutable historical evidence\n%%EOF','application/pdf')
        mapping=self.api.save_mapping(self.owner,package['id'],req(revision=0,tables=tables,decisions=[]))
        return package,mapping
    def apply(self,package):
        preview=self.api.preview(self.owner,package['id']);self.assertTrue(preview['ready'],preview)
        body=req(revision=preview['revision'],preview_sha256=preview['preview_sha256'],confirmation=True)
        return self.api.apply(self.owner,package['id'],body),body

    def test_originals_canonical_links_exact_totals_and_archived_financial_neutrality(self):
        package,mapping=self.stage();preview=self.api.preview(self.owner,package['id'])
        self.assertEqual(preview['counts']['source'],3);self.assertTrue(preview['ready'])
        self.assertEqual(preview['totals'][0]['selected'],dict(net=10000,tax=1900,gross=11900,missing=0,net_exact='100.00',tax_exact='19.00',gross_exact='119.00'))
        report,body=self.apply(package);self.assertFalse(report['financial_effects'])
        self.assertEqual(self.api.apply(self.owner,package['id'],body),report)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM customers').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)
        document=self.office.db.execute('SELECT * FROM business_migration_documents').fetchone()
        historical=json.loads(document['payload_json']);self.assertFalse(historical['issued_by_smartplan'])
        original=self.api.original(self.owner,package['id'],historical['file_id'])[0]
        self.assertEqual(bytes(original),b'%PDF-1.7\nSynthetic immutable historical evidence\n%%EOF')
        person=BusinessFoundation(self.office).contact(self.owner,document['customer_id'])['persons'][0]
        self.assertEqual(person['name'],'Synthetic contact')
        ack_body=req(report_sha256=report['report_sha256'],confirmation=True,note='Synthetic source and selected records compared exactly.')
        ack=self.api.reconcile(self.owner,package['id'],ack_body)
        self.assertEqual(self.api.reconcile(self.owner,package['id'],ack_body),ack)
        self.assertEqual(self.api.view(self.owner,package['id'])['status'],'reconciled')
        validate_integrity(self.office)

    def test_explicit_duplicate_link_reuses_existing_contact_without_overwriting_it(self):
        existing=BusinessFoundation(self.office).save_contact(self.owner,req(name='Synthetic historical customer',email='historic@example.test',address='Synthetic street 1',notes='Keep canonical note'))
        package,mapping=self.stage();preview=self.api.preview(self.owner,package['id'])
        self.assertFalse(preview['ready']);self.assertEqual(preview['rows'][0]['action'],'review')
        self.api.save_mapping(self.owner,package['id'],req(revision=1,tables=mapping['tables'],decisions=[dict(kind='contact',source_id='C1',action='link',target_id=existing['id'],reason='Synthetic customer identity verified')]))
        report,_=self.apply(package)
        self.assertEqual(report['rows'][0]['target_id'],existing['id'])
        self.assertEqual(BusinessFoundation(self.office).contact(self.owner,existing['id'])['notes'],'Keep canonical note')

    def test_changed_target_or_new_duplicate_invalidates_exact_preview(self):
        package,_=self.stage();preview=self.api.preview(self.owner,package['id'])
        BusinessFoundation(self.office).save_contact(self.owner,req(name='New candidate',email='historic@example.test',address='Other address'))
        self.problem(409,self.api.apply,self.owner,package['id'],req(revision=1,preview_sha256=preview['preview_sha256'],confirmation=True))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],0)

    def test_relation_to_foreign_customer_is_blocked_in_preview(self):
        package,mapping=self.stage();foreign=BusinessFoundation(self.office).save_contact(self.owner,req(name='Foreign synthetic customer'))
        foreign_project=self.office.add_project(self.owner,'Foreign synthetic project',customer_id=foreign['id'])
        self.api.save_mapping(self.owner,package['id'],req(revision=1,tables=mapping['tables'],decisions=[dict(kind='project',source_id='P1',action='link',target_id=foreign_project,reason='Attempt incorrect link')]))
        preview=self.api.preview(self.owner,package['id']);self.assertFalse(preview['ready'])
        self.assertTrue(preview['rows'][1]['errors'])

    def test_receipt_replay_and_same_source_in_later_package_never_duplicate(self):
        first,_=self.stage();report,body=self.apply(first)
        second,_=self.stage();preview=self.api.preview(self.owner,second['id'])
        self.assertTrue(preview['ready'],preview);self.assertEqual(preview['counts']['reuse'],3)
        second_report,_=self.apply(second)
        self.assertEqual([r['target_id'] for r in report['rows']],[r['target_id'] for r in second_report['rows']])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_migration_documents').fetchone()[0],1)
        self.problem(409,self.api.apply,self.owner,first['id'],dict(body,confirmation=False))

    def test_changed_source_is_a_conflict_and_other_account_has_separate_identity(self):
        first,_=self.stage();self.apply(first)
        changed,_=self.stage(contacts=[dict(source_id='C1',name='Altered source name',email='historic@example.test')])
        preview=self.api.preview(self.owner,changed['id']);self.assertFalse(preview['ready']);self.assertTrue(preview['rows'][0]['errors'])
        another=self.package(source_account='Different synthetic source tenant')
        self.stage(another);preview=self.api.preview(self.owner,another['id'])
        self.assertEqual(preview['counts']['reuse'],0);self.assertEqual(preview['rows'][0]['action'],'review')

    def test_late_failure_rolls_back_contacts_projects_archive_bindings_and_receipt(self):
        package,_=self.stage();preview=self.api.preview(self.owner,package['id'])
        body=req(revision=1,preview_sha256=preview['preview_sha256'],confirmation=True)
        original=self.office.audit
        def fail(actor,action,*args,**kwargs):
            if action=='business.migration.applied':raise RuntimeError('Synthetic failure after all rows')
            return original(actor,action,*args,**kwargs)
        with patch.object(self.office,'audit',side_effect=fail):
            with self.assertRaises(RuntimeError):self.api.apply(self.owner,package['id'],body)
        for table in ('customers','projects','business_migration_documents','business_migration_bindings','business_migration_applications'):
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_migration_requests WHERE request_id=?',(body['request_id'],)).fetchone())
        self.assertTrue(self.api.apply(self.owner,package['id'],body))

    def test_invalid_amount_can_be_explicitly_excluded_but_is_reported(self):
        package,mapping=self.stage(document_changes={'gross':'500,00'})
        self.assertFalse(self.api.preview(self.owner,package['id'])['ready'])
        self.api.save_mapping(self.owner,package['id'],req(revision=1,tables=mapping['tables'],decisions=[dict(kind='document',source_id='D1',action='skip',target_id=None,reason='Source totals inconsistent; keep original for later review')]))
        report,_=self.apply(package)
        self.assertEqual(report['counts']['skip'],1);self.assertTrue(report['rows'][2]['errors'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_migration_documents').fetchone()[0],0)

    def test_parser_contracts_and_missing_values_are_not_guessed(self):
        for raw in (b'a;a\n1;2',b'a;b\n1;2;3',b'[{"id":"1","id":"2"}]',b'[{"a":1}]'):
            self.problem(400,parse_rows,raw,'json' if raw.startswith(b'[') else 'csv','utf-8-sig',';')
        rows=parse_rows('[{"name":"Müller","value":null}]'.encode(),'json','utf-8-sig',';')[1]
        self.assertIsNone(rows[0]['value'])
        package,_=self.stage(document_changes={'net':'','tax':'','gross':'','currency':''})
        preview=self.api.preview(self.owner,package['id']);self.assertTrue(preview['ready'])
        self.assertEqual(preview['totals'][0]['currency'],'unknown');self.assertEqual(preview['totals'][0]['source']['missing'],1)

    def test_actual_rights_and_original_guards_privacy_and_integrity(self):
        package,_=self.stage();report,body=self.apply(package)
        self.api.reconcile(self.owner,package['id'],req(report_sha256=report['report_sha256'],confirmation=True,note='Synthetic checked scope'))
        self.problem(403,self.api.view,self.tech,package['id']);self.problem(403,self.api.apply,self.tech,package['id'],body)
        self.assertTrue(any('Importierte Originalpakete' in item for item in _privacy_blockers(self.office,report['rows'][0]['target_id'])))
        for table in protected_tables():
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        with self.office.db:self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner['id'],))
        self.problem(401,self.api.apply,self.owner,package['id'],body)

    def test_known_negative_conflict_has_resolution_but_nonce_collision_does_not(self):
        package,_=self.stage();preview=self.api.preview(self.owner,package['id'])
        path='/migrations/'+package['id']+'/apply'
        bad=req(revision=1,preview_sha256='0'*64,confirmation=True)
        error=self.problem(409,dispatch,self.office,self.owner,path,'POST',bad)
        self.assertEqual(error.request_resolution,'not_accepted')
        report,body=self.apply(package)
        error=self.problem(409,dispatch,self.office,self.owner,path,'POST',dict(body,confirmation=False))
        self.assertIsNone(error.request_resolution)
        self.problem(400,dispatch,self.office,self.owner,path,'POST',dict(body,_query={'extra':'x'}))

    def test_archived_customer_keeps_original_receipts_readable_but_cannot_receive_new_imports(self):
        package,_=self.stage();report,body=self.apply(package);customer=report['rows'][0]['target_id']
        foundation=BusinessFoundation(self.office);contact=foundation.contact(self.owner,customer)
        foundation.save_contact(self.owner,req(revision=contact['revision'],active=False),customer)
        self.assertEqual(self.api.apply(self.owner,package['id'],body),report)
        self.assertEqual(self.api.report(self.owner,package['id']),report)
        later,_=self.stage();self.assertFalse(self.api.preview(self.owner,later['id'])['ready'])

    def test_same_package_duplicate_contacts_and_changed_receipt_proof_fail_closed(self):
        package,_=self.stage(contacts=[dict(source_id='C1',name='Same',email=''),dict(source_id='C2',name='Same',email='')])
        preview=self.api.preview(self.owner,package['id']);self.assertFalse(preview['ready'])
        self.assertTrue(any(e['code']=='duplicate_target' for r in preview['rows'] for e in r['errors']))
        clean,_=self.stage(self.package(source_account='Clean source'));report,body=self.apply(clean)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_migration_requests_update_guard')
            self.office.db.execute('UPDATE business_migration_requests SET result_json=? WHERE request_id=?',(json.dumps(dict(report,financial_effects=True)),body['request_id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_large_source_totals_keep_exact_decimal_strings_beyond_browser_integer_precision(self):
        row=dict(kind='document',values=dict(kind='invoice',currency='EUR',net='9999999999999.99',tax='0.00',gross='9999999999999.99'),action='create',errors=[])
        total=self.api.totals([row]*1000)[0]['selected']
        self.assertGreater(total['gross'],2**53-1)
        self.assertEqual(total['gross_exact'],'9999999999999990.00')
        self.assertEqual(total['tax_exact'],'0.00')


if __name__=='__main__':unittest.main()
