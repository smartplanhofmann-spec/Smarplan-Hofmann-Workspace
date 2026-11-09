"""Canonical CRM history, narrow source rights, corrections and snapshot paging."""
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from core import Problem
from business_foundation import BusinessFoundation
from business_sales import Sales, dispatch
from business_service import Service
from communication_history import CommunicationHistory
import test_business_sales as sales

req = sales.req


class CommunicationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.f = sales.SalesTests('runTest'); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.office, self.owner, self.contact = self.f.office, self.f.owner, self.f.contact
        self.history = CommunicationHistory(self.office)

    def listing(self, actor=None, **query):
        return self.history.listing(actor or self.owner, dict(customer_id=self.contact['id'], **query))

    def seed(self):
        inquiry = self.f.inquiry()
        chance = self.f.save(inquiry_id=inquiry['id'])
        project = self.f.api.adoption(self.owner, chance['id'], 'project', self.f.adopt_body(chance))['project_id']
        call = self.f.api.activity(self.owner, chance['id'], req(kind='call', text='Synthetic call original',
            occurred_on='2026-11-02', supersedes_id=None, correction_reason=''))
        corrected = self.f.api.activity(self.owner, chance['id'], req(kind='call', text='Synthetic corrected call',
            occurred_on='2026-11-02', supersedes_id=call['id'], correction_reason='Synthetic original correction'))
        note = BusinessFoundation(self.office).post_message(self.owner,
            req(project_id=project, text='Synthetic project note'))
        service = Service(self.office, self.f.clock)
        case = service.save(self.owner, req(revision=0, customer_id=self.contact['id'],
            project_id=project, person_id=None, asset_id=None, contract_id=None, visit_id=None,
            inquiry_id=None, defect_id=None, title='Synthetic service history', kind='complaint',
            priority='normal', responsible_id=self.owner['id'], follow_up_on=None,
            description='Synthetic service context'))
        detail = service.view(self.owner, case['id'])
        event = service.command(self.owner, case['id'], 'events', req(revision=case['revision'],
            source_sha256=detail['source_sha256'], kind='email', text='Synthetic manually documented email',
            occurred_on='2026-11-01', supersedes_id=None, correction_reason=''))['event']
        return dict(inquiry=inquiry, chance=chance, project_id=project, call=call,
                    corrected=corrected, note=note, service=case, service_event=event)

    def test_explicit_cross_source_links_preserve_origin_and_corrections(self):
        seed = self.seed(); result = self.listing(project_id=seed['project_id'])
        self.assertEqual({item['kind'] for item in result['items']}, {'inquiry','sales','service','project_note'})
        self.assertEqual(len({item['key'] for item in result['items']}), len(result['items']))
        old = next(i for i in result['items'] if i['source_id']==seed['call']['id'])
        new = next(i for i in result['items'] if i['source_id']==seed['corrected']['id'])
        self.assertTrue(old['superseded']); self.assertEqual(new['supersedes_key'], old['key'])
        self.assertEqual(new['precision'], 'day'); self.assertEqual(new['occurred_at'], '2026-11-02')
        self.assertNotEqual(new['recorded_at'][:10], new['occurred_at'])
        manual = next(i for i in result['items'] if i['source_id']==seed['service_event']['id'])
        self.assertEqual(manual['provenance'], 'manual_activity')
        self.assertEqual(manual['status'], 'recorded_activity')
        self.assertTrue(all(not i['recipient_delivery_confirmed'] for i in result['items']))
        self.assertEqual(self.listing(project_id=seed['project_id']), result)

    def test_equal_email_does_not_link_unassigned_or_foreign_customer_inquiry(self):
        seed=self.seed()
        unrelated=self.f.inquiry()
        self.assertNotIn(unrelated['id'],[i['source_id'] for i in self.listing()['items']])
        other=BusinessFoundation(self.office).save_contact(self.owner,req(name='Another canonical customer',email='customer@example.test'))
        chance=self.f.api.save(self.owner,self.f.command(customer_id=other['id'],person_id=None,title='Foreign history title'))
        self.assertNotIn(chance['id'],[i['source_id'] for i in self.listing()['items']])
        self.assertIn(seed['inquiry']['id'],[i['source_id'] for i in self.listing()['items']])

    def test_read_only_projection_never_adds_history_or_replays_a_write(self):
        self.seed()
        before=self.office.db.total_changes
        a=self.listing();self.assertEqual(a,self.listing());self.assertEqual(before,self.office.db.total_changes)
        with self.assertRaises(Problem) as error:dispatch(self.office,self.owner,'/sales/communication-history','POST',{})
        self.assertEqual(error.exception.status,405)

    def document_mail(self,project_id):
        from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
        from business_documents import render_prepared
        from business_delivery import DeliveryReceipt
        api=SyntheticDocuments(self.office,clock=self.f.clock)
        api.save_settings(self.owner,req(revision=0,company_name='Synthetic Seller',address_line='Testweg 1',
            postal_code='10115',city='Berlin',country='DE',vat_id='DE123456789',email='seller@example.test',
            issuer_mode='own',issuing_enabled=False,cutover_ack=True,cutover_date='2026-01-01',einvoice_format='none'))
        seed_synthetic_issuer(api,self.owner)
        draft=api.create(self.owner,req(project_id=project_id,kind='offer',title='Synthetic source offer',
            issue_date='2026-11-03',due_date='2026-11-20',buyer_reference='',
            positions=[dict(description='Synthetic work',quantity='1',unit='HUR',unit_price_net='10',tax_rate='19',kind='labor')]))
        prepared=api.prepare_finalization(self.owner,draft['id'],draft['revision'])
        issued=api.finalize(self.owner,draft['id'],render_prepared(prepared),req()['request_id'])
        class SyntheticTransport:
            def send(self,job):return DeliveryReceipt('accepted',job['operation_id'],'synthetic-acceptance',accepted_by_server=True)
        with patch.dict('os.environ',{'SMARTPLAN_SMTP_ENABLED':'1','SMARTPLAN_SMTP_FROM':'seller@example.test'}):
            preview=api.email_preview(self.owner,issued['id'])
            state=api.send_mail(self.owner,issued['id'],req(revision=issued['revision'],
                preview_sha256=preview['preview_sha256'],confirmation=True),transport=SyntheticTransport())
        return dict(document=issued,delivery=state)

    def test_real_document_outbox_records_transport_acceptance_without_invented_delivery(self):
        seed=self.seed();mail=self.document_mail(seed['project_id']);result=self.listing()
        self.assertIn('document',{i['kind'] for i in result['items']})
        receipts=[i for i in result['items'] if i['kind']=='delivery']
        self.assertEqual({i['status'] for i in receipts},{'pending','sending','accepted'})
        self.assertEqual(sum(i['accepted_by_server'] for i in receipts),1)
        self.assertFalse(any(i['recipient_delivery_confirmed'] for i in receipts))
        actor=self.f.tech;self.office.assign(self.owner,seed['project_id'],actor['id'])
        BusinessFoundation(self.office).save_grant(self.owner,req(user_id=actor['id'],permission='contacts.read',scope='*',effect='allow',revision=0))
        self.assertFalse({'document','delivery'}&{i['kind'] for i in self.listing(actor)['items']})

    def test_snapshot_paging_has_no_duplicates_and_rejects_changed_sources_or_filter(self):
        seed=self.seed(); first=self.listing(limit='2')
        self.assertTrue(first['has_more']); second=self.listing(limit='2',cursor=first['next_cursor'])
        self.assertFalse({i['key'] for i in first['items']} & {i['key'] for i in second['items']})
        self.assertEqual(first['snapshot_sha256'],second['snapshot_sha256'])
        with self.assertRaises(Problem) as changed:self.listing(limit='2',q='Synthetic',cursor=first['next_cursor'])
        self.assertEqual(changed.exception.status,409)
        self.f.api.activity(self.owner,seed['chance']['id'],req(kind='note',text='Late actual record',
            occurred_on='2026-11-03',supersedes_id=None,correction_reason=''))
        with self.assertRaises(Problem) as changed:self.listing(limit='2',cursor=first['next_cursor'])
        self.assertEqual(changed.exception.status,409)

    def test_filters_are_exact_and_do_not_infer_time_for_day_activity(self):
        self.seed()
        result=self.listing(kind='sales',q='corrected',**{'from':'2026-11-02','to':'2026-11-02'})
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['items'][0]['text'],'Synthetic corrected call')
        self.assertEqual(result['items'][0]['precision'],'day')

    def test_fresh_project_assignment_and_contact_denial_apply_to_every_source(self):
        seed=self.seed(); actor=self.f.tech
        self.office.assign(self.owner,seed['project_id'],actor['id'])
        grant=BusinessFoundation(self.office)
        grant.save_grant(self.owner,req(user_id=actor['id'],permission='contacts.read',scope='*',effect='allow',revision=0))
        visible=self.listing(actor,project_id=seed['project_id'])
        self.assertNotIn('inquiry',{i['kind'] for i in visible['items']})
        self.assertNotIn('document',{i['kind'] for i in visible['items']})
        grant.save_grant(self.owner,req(user_id=actor['id'],permission='contacts.read',scope=seed['project_id'],effect='deny',revision=0))
        with self.assertRaises(Problem) as blocked:self.listing(actor,project_id=seed['project_id'])
        self.assertEqual(blocked.exception.status,403)
        self.office.assign(self.owner,seed['project_id'],actor['id'],remove=True)
        with self.assertRaises(Problem) as blocked:self.listing(actor)
        self.assertEqual(blocked.exception.status,403)

    def test_other_customer_project_or_deactivated_identity_never_leaks_history(self):
        seed=self.seed()
        other=self.office.add_project(self.owner,'Unrelated project','Unrelated customer')
        with self.assertRaises(Problem) as blocked:self.listing(project_id=other)
        self.assertEqual(blocked.exception.status,404)
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner['id'],))
        with self.assertRaises(Problem) as blocked:self.listing()
        self.assertEqual(blocked.exception.status,401)

    def test_financial_personnel_and_restricted_project_notes_are_not_copied(self):
        seed=self.seed(); foundation=BusinessFoundation(self.office)
        for visibility in ('financial','personnel','restricted'):
            foundation.post_message(self.owner,req(project_id=seed['project_id'],text='PRIVATE '+visibility,visibility=visibility))
        self.assertNotIn('PRIVATE',json.dumps(self.listing()))

    def test_bad_filters_and_cursors_are_rejected_with_no_writes(self):
        for query in ({'unknown':'x'},{'limit':True},{'limit':0},{'limit':'101'},{'kind':'private'},
                {'from':'2026-02-29'},{'from':'2026-11-03','to':'2026-11-02'},
                {'q':'bad\nquery'},{'cursor':'a'},{'cursor':'e30'},{'project_id':True}):
            with self.subTest(query=query):
                with self.assertRaises(Problem) as error:self.listing(**query)
                self.assertEqual(error.exception.status,400)

    def test_current_visible_budget_reports_explicitly_without_silent_truncation(self):
        self.seed()
        with patch('communication_history.MAX_ENTRIES',2),self.assertRaises(Problem) as error:self.listing()
        self.assertEqual(error.exception.status,413)
        with patch('communication_history.MAX_ENTRIES',2):
            self.assertEqual(len(self.listing(q='corrected call')['items']),1)
        with patch('communication_history.MAX_TEXT_BYTES',1),self.assertRaises(Problem) as error:self.listing()
        self.assertEqual(error.exception.status,413)

    def test_separate_company_with_equal_contact_details_cannot_read_foreign_ids(self):
        self.seed()
        other=sales.SalesTests('runTest');other.setUp();self.addCleanup(other.doCleanups)
        chance=other.save(title='PRIVATE OTHER COMPANY HISTORY')
        with self.assertRaises(Problem) as blocked:
            CommunicationHistory(other.office).listing(other.owner,dict(customer_id=self.contact['id']))
        self.assertEqual(blocked.exception.status,404)
        self.assertNotIn(chance['id'],[i['source_id'] for i in self.listing()['items']])
        self.assertNotIn('PRIVATE OTHER COMPANY',json.dumps(self.listing()))

    def test_project_without_canonical_customer_retains_its_operational_notes(self):
        # Historical nullable project schema; current create deliberately requires a customer.
        pid=req()['request_id']
        self.office.db.execute('INSERT INTO projects(id,name,customer,customer_id) VALUES(?,?,?,NULL)',
            (pid,'Legacy unbound history','Historical display name'))
        note=BusinessFoundation(self.office).post_message(self.owner,req(project_id=pid,text='Unbound project note'))
        result=self.history.listing(self.owner,dict(project_id=pid))
        self.assertIsNone(result['customer']);self.assertIsNone(result['scope']['customer_id'])
        self.assertEqual([i['source_id'] for i in result['items']],[note['id']])

    def test_real_flask_adapter_enforces_strict_methods_bodies_and_device_boundary(self):
        from cryptography.fernet import Fernet
        from online.web import create_app
        self.seed()
        client=create_app(office=self.office,key=Fernet.generate_key(),host='history.example.test').test_client()
        token=self.office.login('sales-owner@example.test','Synthetic-sales-owner-password')
        path='/api/v1/business/sales/communication-history?customer_id='+self.contact['id']
        def call(method,path=path,body=None):return client.open(path,method=method,json=body,
            base_url='https://history.example.test',headers={'Authorization':'Bearer '+token})
        self.assertEqual(call('GET').status_code,200)
        self.assertEqual(call('POST',body={}).status_code,405)
        self.assertEqual(call('GET',body={'ignored':True}).status_code,400)
        self.assertEqual(call('GET',path+'&ignored=1').status_code,400)
        self.assertEqual(call('GET',path+'&customer_id='+self.contact['id']).status_code,400)
        from business_api import offline_path
        self.assertFalse(offline_path('/business/sales/communication-history','GET',('time_events','field_media')))


if __name__=='__main__':unittest.main()
