"""Synthetic commercial acceptance: exact decimals and immutable issued records."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import sqlite3
import json
import unittest
import uuid

from core import Office, Problem
import business_documents as documents


class SyntheticDocuments(documents.Documents):
    """Test-only SQLite policy; never imported by production or enabled by ENV.

    The real SQL transactions, numbering, rendering, archive and authorization
    code remain unchanged. Real PostgreSQL tests use the production class.
    """
    def _issuer_security(self,kind):
        if not isinstance(self.db,sqlite3.Connection):return super()._issuer_security(kind)
        return 'synthetic_sqlite_test_only' if kind in documents.INVOICES else 'sqlite_local_trigger_only'


def seed_synthetic_issuer(api,actor):
    """Private, explicitly synthetic settings seed, not an activation endpoint."""
    if not isinstance(api,SyntheticDocuments) or not isinstance(api.db,sqlite3.Connection):raise AssertionError('Synthetic SQLite fixture required')
    with api.office.lock,api.db:
        payload,revision=api._settings_row();payload['issuing_enabled']=True
        body=dict(request_id=uuid.uuid4().hex,revision=revision,issuing_enabled=True)
        _,fingerprint=api._replay(actor,body['request_id'],'settings',body)
        api.db.execute("UPDATE business_commercial_settings SET payload_json=?,revision=revision+1,updated_at=? WHERE id='main'",(documents.canonical(payload),api._now()))
        return api._remember(actor,body['request_id'],'settings',fingerprint,api.settings(actor))


class DocumentsFixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='smartplan-documents-')
        self.addCleanup(self.temp.cleanup)
        self.office=Office(Path(self.temp.name)/'office.db')
        self.addCleanup(self.office.db.close)
        self.owner={'id':uuid.uuid4().hex,'role':'owner','email':'owner@example.test'}
        with self.office.db:
            self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)',tuple(self.owner[k] for k in ('id','email','role')))
            from business_foundation import schema_statements as foundation_schema
            for sql in foundation_schema('BLOB')+documents.schema_statements('BLOB'):self.office.db.execute(sql)
            for sql in documents.guard_statements('sqlite'):self.office.db.execute(sql)
        self.project=self.office.add_project(self.owner,'Synthetic project','Synthetic buyer')
        self.api=SyntheticDocuments(self.office,clock=lambda:datetime(2030,1,10,12,tzinfo=timezone.utc))

    def call(self,name,*args,**kwargs):
        with self.office.lock,self.office.db:return getattr(self.api,name)(self.owner,*args,**kwargs)

    def settings(self):
        local=isinstance(self.office.db,sqlite3.Connection)
        value=self.call('save_settings',dict(request_id=uuid.uuid4().hex,revision=0,company_name='Synthetic Seller GmbH',
            address_line='Teststraße 1',postal_code='10115',city='Berlin',country='DE',vat_id='DE123456789',
            email='seller@example.test',phone='+4930123456',iban='DE89370400440532013000',bic='COBADEFFXXX',
            issuer_mode='own',issuing_enabled=not local,cutover_ack=True,cutover_date='2029-01-01',einvoice_format='none'))
        return seed_synthetic_issuer(self.api,self.owner) if local else value

    def draft(self,**changes):
        data=dict(request_id=uuid.uuid4().hex,project_id=self.project,kind='offer',title='Synthetisches Angebot',
            issue_date='2030-01-10',due_date='2030-01-24',buyer_reference='TEST-BUYER',
            buyer=dict(name='Synthetic Buyer',address_line='Testweg 2',postal_code='10117',city='Berlin',country='DE',email='buyer@example.test'),
            positions=[dict(description='Arbeitszeit',quantity='2.5',unit='HUR',unit_price_net='55.50',tax_rate='19',kind='labor'),
                       dict(description='Material',quantity='3',unit='C62',unit_price_net='10.005',tax_rate='7',kind='material')])
        data.update(changes)
        return self.call('create',data)

    def issue(self,draft,request=None):
        with self.office.lock,self.office.db:prepared=self.api.prepare_finalization(self.owner,draft['id'],draft['revision'])
        rendered=documents.render_prepared(prepared)
        with self.office.lock,self.office.db:return self.api.finalize(self.owner,draft['id'],rendered,request or uuid.uuid4().hex)


class DocumentTests(DocumentsFixture,unittest.TestCase):
    def test_decimal_rounding_tax_groups_and_material_labor_are_exact(self):
        totals=documents.calculate_positions([
            dict(description='A',quantity='1',unit='C62',unit_price_net='0.005',tax_rate='19',kind='material'),
            dict(description='B',quantity='3',unit='HUR',unit_price_net='10',tax_rate='7',kind='labor')])
        self.assertEqual(('30.01','2.10','32.11'),tuple(totals['totals'][k] for k in ('net','tax','gross')))
        self.assertEqual('0.01',totals['positions'][0]['net'])
        self.assertEqual('30.00',totals['totals']['labor_net'])
        equal=documents.calculate_positions([dict(description='A',quantity='1',unit='C62',unit_price_net='0.03',tax_rate=rate) for rate in ('19','19.00')])
        self.assertEqual('0.01',equal['totals']['tax']);self.assertEqual(1,len(equal['totals']['tax_breakdown']))

    def test_article_snapshot_survives_later_price_change_and_conversion(self):
        self.settings()
        article=self.call('save_article',dict(request_id=uuid.uuid4().hex,code='SYN-1',name='Synthetic article',kind='material',
            unit='C62',unit_price_net='10.50',cost_price_net='7.25',tax_rate='19',currency='EUR',active=True))
        draft=self.draft(positions=[dict(article_id=article['id'],article_revision=1,quantity='2')])
        self.call('save_article',dict(request_id=uuid.uuid4().hex,revision=1,unit_price_net='99.00'),article['id'])
        order=self.call('convert',draft['id'],dict(request_id=uuid.uuid4().hex,revision=1,target_kind='order_confirmation'))
        self.assertEqual('10.50',order['positions'][0]['unit_price_net'])
        self.assertEqual('21.00',order['totals']['net'])

    def test_issue_is_gapless_atomic_immutable_and_replay_after_restart(self):
        self.settings()
        first=self.draft(kind='invoice')
        request=uuid.uuid4().hex
        issued=self.issue(first,request)
        self.assertEqual('RE-2030-000001',issued['number'])
        self.assertEqual('final',issued['status'])
        self.assertTrue(self.call('archive',issued['id'],'pdf').startswith(b'%PDF-'))
        self.assertEqual(issued['id'],self.issue(first,request)['id'])
        with self.assertRaises(Exception):
            with self.office.db:self.office.db.execute("UPDATE business_document_archives SET pdf=? WHERE document_id=?",(b'tampered',issued['id']))
        documents.validate_integrity(self.office)

    def test_stale_preparation_and_rollback_do_not_consume_number(self):
        self.settings()
        draft=self.draft(kind='invoice')
        with self.office.lock,self.office.db:prepared=self.api.prepare_finalization(self.owner,draft['id'],1)
        rendered=documents.render_prepared(prepared)
        try:
            with self.office.lock,self.office.db:
                self.office.db.execute('BEGIN')
                self.api.finalize(self.owner,draft['id'],rendered,uuid.uuid4().hex)
                raise RuntimeError('synthetic rollback')
        except RuntimeError:pass
        issued=self.issue(draft)
        self.assertEqual('RE-2030-000001',issued['number'])
        second=self.draft(kind='invoice')
        with self.office.lock,self.office.db:stale=self.api.prepare_finalization(self.owner,second['id'],1)
        self.call('update',second['id'],dict(request_id=uuid.uuid4().hex,revision=1,title='Changed'))
        with self.assertRaises(Problem):
            with self.office.lock,self.office.db:self.api.finalize(self.owner,second['id'],documents.render_prepared(stale),uuid.uuid4().hex)

    def test_default_issuer_disables_real_invoice_issue(self):
        draft=self.draft(kind='invoice')
        with self.assertRaises(Problem):self.issue(draft)

    def test_floats_nan_and_negative_regular_quantities_are_not_accepted(self):
        for value in (1.2,'NaN','Infinity','-1','1e300'):
            with self.subTest(value=value),self.assertRaises(Problem):
                self.draft(positions=[dict(description='Synthetic',quantity=value,unit='C62',unit_price_net='1',tax_rate='19',kind='material')])

    def test_cumulative_chain_deducts_issued_liability_not_confirmed_payments(self):
        self.settings()
        def positions(net):return [dict(description='Leistung',quantity='1',unit='HUR',unit_price_net=net,tax_rate='19',kind='labor')]
        first=self.issue(self.draft(kind='advance_invoice',positions=positions('100')))
        second=self.issue(self.draft(kind='cumulative_invoice',positions=positions('200'),previous_document_ids=[first['id']]))
        last=self.issue(self.draft(kind='final_invoice',positions=positions('300'),previous_document_ids=[second['id']]))
        self.assertEqual('119.00',second['totals']['gross']);self.assertEqual('119.00',last['totals']['gross'])
        self.assertEqual('357.00',last['contract_totals']['gross']);self.assertEqual('238.00',last['previous_issued_gross'])
        with self.assertRaises(Problem):self.issue(self.draft(kind='final_invoice',positions=positions('300'),previous_document_ids=[first['id']]))

    def test_cancel_appends_credit_without_rewriting_invoice_or_reusing_number(self):
        self.settings();invoice=self.issue(self.draft(kind='invoice'));original=self.call('archive',invoice['id'])
        draft=self.call('cancel',invoice['id'],dict(request_id=uuid.uuid4().hex,revision=invoice['revision'],reason='Synthetic cancellation'))
        self.assertEqual('draft',draft['status']);credit=self.issue(draft)
        self.assertEqual('GS-2030-000001',credit['number']);self.assertEqual(invoice['totals']['gross'],credit['totals']['gross'])
        self.assertEqual(original,self.call('archive',invoice['id']));self.assertEqual('final',self.call('get',invoice['id'])['status'])

    def test_stale_concurrent_candidate_cannot_duplicate_number_and_counters_cannot_reset(self):
        self.settings();a=self.draft(kind='invoice');b=self.draft(kind='invoice')
        pa=self.api.prepare_finalization(self.owner,a['id'],1);pb=self.api.prepare_finalization(self.owner,b['id'],1)
        self.api.finalize(self.owner,a['id'],documents.render_prepared(pa),uuid.uuid4().hex)
        with self.assertRaises(Problem):self.api.finalize(self.owner,b['id'],documents.render_prepared(pb),uuid.uuid4().hex)
        self.assertEqual('RE-2030-000002',self.issue(b)['number'])
        with self.assertRaises(Exception),self.office.db:self.office.db.execute('UPDATE business_document_counters SET next_value=1')
        with self.assertRaises(Exception),self.office.db:self.office.db.execute('DELETE FROM business_document_counters')

    def test_service_bom_text_template_and_price_history_are_real_snapshots(self):
        a=self.call('save_article',dict(request_id=uuid.uuid4().hex,name='Material',code='M1',kind='material',unit='C62',unit_price_net='10',cost_price_net='4',tax_rate='19',active=True))
        service=self.call('save_article',dict(request_id=uuid.uuid4().hex,name='Montage',code='S1',kind='service',unit='C62',unit_price_net='50',cost_price_net='8',tax_rate='19',active=True,
            components=[dict(article_id=a['id'],article_revision=1,quantity='2')]))
        self.assertEqual('8.00',service['components'][0]['cost_net'])
        self.call('save_article',dict(request_id=uuid.uuid4().hex,revision=1,cost_price_net='99'),a['id'])
        historical=self.office.db.execute('SELECT payload_json FROM business_article_versions WHERE article_id=? AND revision=1',(a['id'],)).fetchone()
        self.assertIn('"cost_price_net":"4"',historical['payload_json'])
        text=self.call('save_text_block',dict(request_id=uuid.uuid4().hex,name='Begrüßung',text='Guten Tag & willkommen'))
        template=self.call('save_template',dict(request_id=uuid.uuid4().hex,name='Standard',kind='estimate',title='Kostenvoranschlag',intro=text['text'],positions=self.draft()['positions']))
        draft=self.draft(kind='estimate',template_id=template['id'],template_revision=1);self.assertEqual('Guten Tag & willkommen',draft['intro'])
        self.assertEqual(1,draft['template_source']['revision'])

    def test_girocode_is_bounded_valid_iban_and_never_a_receipt(self):
        self.settings();draft=self.draft(kind='invoice');snapshot=self.api.prepare_finalization(self.owner,draft['id'],1)['snapshot']
        value=documents.epc_payload(snapshot);self.assertTrue(value.startswith('BCD\n002\n1\nSCT\n'));self.assertIn('DE89370400440532013000',value)
        snapshot['issuer']['iban']='DE00370400440532013000';self.assertIsNone(documents.epc_payload(snapshot))

    def test_simple_signature_bound_to_final_hash_and_advanced_claim_rejected(self):
        self.settings();document=self.issue(self.draft())
        data=dict(request_id=uuid.uuid4().hex,revision=document['revision'],signer='Synthetic person',strokes=[[[0.1,0.2],[0.9,0.3]]],confirmation=True,level='simple')
        signed=self.call('sign',document['id'],data);self.assertEqual('simple',signed['level']);self.assertEqual(signed,self.call('sign',document['id'],data))
        signed_pdf=self.call('signed_pdf',document['id'],signed['id']);original=self.call('archive',document['id'])
        self.assertTrue(signed_pdf.startswith(b'%PDF-'));self.assertNotEqual(original,signed_pdf)
        self.assertEqual(documents._hash(signed_pdf),signed['signed_pdf_sha256']);documents.validate_integrity(self.office)
        data['request_id']=uuid.uuid4().hex;data['level']='qualified'
        with self.assertRaises(Problem):self.call('sign',document['id'],data)

    def test_modified_guard_definition_is_not_accepted_as_valid_archive(self):
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_document_archives_update_guard')
            self.office.db.execute("CREATE TRIGGER business_document_archives_update_guard BEFORE UPDATE ON business_document_archives WHEN 0 BEGIN SELECT RAISE(ABORT,'immutable commercial archive'); END")
        with self.assertRaises(ValueError):documents.validate_integrity(self.office)

    def test_cancelled_cumulative_document_releases_its_predecessor_for_corrected_chain(self):
        self.settings()
        def positions(value):return [dict(description='Synthetic chain',quantity='1',unit='HUR',unit_price_net=value,tax_rate='19',kind='labor')]
        first=self.issue(self.draft(kind='advance_invoice',positions=positions('100')))
        second=self.issue(self.draft(kind='cumulative_invoice',positions=positions('200'),previous_document_ids=[first['id']]))
        credit=self.call('cancel',second['id'],dict(request_id=uuid.uuid4().hex,revision=second['revision'],reason='Synthetic corrected chain'))
        self.issue(credit)
        replacement=self.issue(self.draft(kind='cumulative_invoice',positions=positions('250'),previous_document_ids=[first['id']]))
        self.assertEqual('178.50',replacement['totals']['gross']);documents.validate_integrity(self.office)

    def test_stale_template_revision_is_rejected_and_original_snapshot_retained(self):
        template=self.call('save_template',dict(request_id=uuid.uuid4().hex,name='Synthetic template',kind='offer',title='Version1',positions=self.draft()['positions']))
        draft=self.draft(template_id=template['id'],template_revision=1)
        self.call('save_template',dict(request_id=uuid.uuid4().hex,revision=1,title='Version2'),template['id'])
        with self.assertRaises(Problem):self.draft(template_id=template['id'],template_revision=1)
        self.assertEqual('Version1',self.call('get',draft['id'])['template_source']['snapshot']['title'])

    def test_financial_restore_gate_blocks_preparation_and_commit_without_consuming_numbers(self):
        self.settings();draft=self.draft(kind='invoice');prepared=self.api.prepare_finalization(self.owner,draft['id'],1);rendered=documents.render_prepared(prepared)
        with self.office.db:self.office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=1,restore_id=? WHERE singleton=1',(uuid.uuid4().hex,))
        with self.assertRaises(Problem):self.api.prepare_finalization(self.owner,draft['id'],1)
        with self.assertRaises(Problem):self.api.finalize(self.owner,draft['id'],rendered,uuid.uuid4().hex)
        self.assertEqual(0,self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0])

    def test_production_sqlite_cannot_activate_or_issue_even_when_imported_settings_are_enabled(self):
        self.settings();draft=self.draft(kind='invoice')
        production=documents.Documents(self.office,clock=self.api.clock)
        with self.assertRaises(Problem) as error:production.save_settings(self.owner,dict(request_id=uuid.uuid4().hex,revision=2,issuing_enabled=True))
        self.assertEqual(409,error.exception.status)
        with self.assertRaises(Problem) as error:production.prepare_finalization(self.owner,draft['id'],1)
        self.assertEqual(409,error.exception.status)
        synthetic=self.api.prepare_finalization(self.owner,draft['id'],1)
        self.assertEqual('synthetic_sqlite_test_only',synthetic['snapshot']['archive_security'])
        with self.assertRaises(Problem):production.finalize(self.owner,draft['id'],documents.render_prepared(synthetic),uuid.uuid4().hex)
        self.assertEqual(0,self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0])


if __name__=='__main__':unittest.main()
