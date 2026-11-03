"""Synthetic CRM pipeline, history, canonical adoption and failure recovery."""
from datetime import datetime,timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

import business_schema
from business_documents import Documents
from business_foundation import BusinessFoundation
from business_sales import Sales,dispatch,validate_integrity
from core import Office,Problem
from inquiries import Inquiries


def req(**values):return dict(request_id=uuid.uuid4().hex,**values)


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-sales-');self.addCleanup(self.tmp.cleanup)
        self.office=Office(Path(self.tmp.name)/'office.sqlite3');self.addCleanup(self.office.db.close)
        self.owner=dict(id=self.office.add_user('sales-owner@example.test','Synthetic-sales-owner-password','owner'),role='owner')
        self.tech=dict(id=self.office.add_user('sales-tech@example.test','Synthetic-sales-tech-password','technician'),role='technician')
        self.clock=lambda:datetime(2026,11,3,12,tzinfo=timezone.utc)
        self.api=Sales(self.office,self.clock)
        self.contact=BusinessFoundation(self.office).save_contact(self.owner,req(name='Synthetic sales customer',email='customer@example.test',
            persons=[dict(name='Synthetic contact',role_label='billing',email='contact@example.test',phone='')],
            addresses=[dict(purpose='billing',label='Main',street='Teststreet 1',postal_code='10115',city='Berlin',country='DE')]))

    def command(self,**changes):
        value=dict(revision=0,customer_id=self.contact['id'],inquiry_id=None,title='Synthetic installation prospect',
            person_id=self.contact['persons'][0]['id'],stage='qualified',expected_net_minor=123456,probability_percent=50,
            responsible_id=self.owner['id'],follow_up_on='2026-11-02',expected_close_on='2026-11-30',description='Explicit synthetic forecast',closure_reason='')
        value.update(changes);return req(**value)

    def save(self,**changes):return self.api.save(self.owner,self.command(**changes))
    def inquiry(self):return Inquiries(self.office).create(self.owner,req(subject='Synthetic CRM inquiry',message='Please prepare an offer.',sender_email='customer@example.test'))
    def problem(self,code,fn,*args):
        with self.assertRaises(Problem) as caught:fn(*args)
        self.assertEqual(caught.exception.status,code,caught.exception.message)
    def adopt_body(self,item,kind='project',**changes):
        current=self.api.view(self.owner,item['id'])
        body=dict(revision=current['revision'],source_sha256=current['source_sha256'],confirmation=True)
        if kind=='project':body.update(project_id=None,project_name='Synthetic adopted project')
        else:
            article=Documents(self.office).save_article(self.owner,req(code='SYN-SALES',name='Synthetic catalogue service',kind='service',unit='HUR',unit_price_net='79.95',tax_rate='19',active=True))
            body.update(title='Source-priced synthetic offer',issue_date='2026-11-03',due_date='2026-11-17',
                positions=[dict(article_id=article['id'],article_revision=article['revision'],quantity='2')])
        body.update(changes);return req(**body)

    def test_forecast_pipeline_filters_closed_cases_and_history_has_original_values(self):
        first=self.save();self.save(title='Closed result',stage='won',probability_percent=100,closure_reason='Signed external order documented')
        result=self.api.listing(self.owner)
        self.assertEqual(result['summary']['open_count'],1)
        self.assertEqual(result['summary']['expected_net_minor'],123456)
        self.assertEqual(result['summary']['weighted_net_minor'],61728)
        self.assertTrue(result['summary']['forecast_only']);self.assertEqual(result['summary']['overdue_count'],1)
        edited=self.api.save(self.owner,self.command(id=first['id'],revision=1,stage='negotiation',probability_percent=75))
        history=self.api.history(self.owner,first['id'])['items']
        self.assertEqual([v['probability_percent'] for v in history],[50,75])
        self.assertEqual(history[0],first);self.assertEqual(history[1],edited)
        self.assertEqual(len(self.api.listing(self.owner,stage='negotiation')['items']),1)
        business_schema.validate_integrity(self.office)

    def test_duplicate_inquiry_customer_and_person_boundaries_and_explicit_closure(self):
        source=self.inquiry();self.save(inquiry_id=source['id'])
        self.problem(409,self.api.save,self.owner,self.command(inquiry_id=source['id']))
        self.problem(409,self.api.save,self.owner,self.command(person_id=uuid.uuid4().hex))
        for changes in (dict(stage='won',probability_percent=50,closure_reason='Explicit decision'),dict(stage='lost',probability_percent=0),dict(expected_net_minor=True),dict(probability_percent=101)):
            self.problem(400,self.api.save,self.owner,self.command(**changes))
        self.assertEqual(len(self.api.listing(self.owner)['items']),1)

    def test_activities_are_append_only_and_correction_retains_original(self):
        item=self.save();body=req(kind='call',text='Customer asked for a proposal.',occurred_on='2026-11-03',supersedes_id=None,correction_reason='')
        first=self.api.activity(self.owner,item['id'],body)
        self.assertEqual(self.api.activity(self.owner,item['id'],body),first)
        corrected=self.api.activity(self.owner,item['id'],req(kind='call',text='Corrected customer note.',occurred_on='2026-11-03',supersedes_id=first['id'],correction_reason='Original wording was incomplete'))
        self.assertEqual({v['id'] for v in self.api.activities(self.owner,item['id'])['items']},{first['id'],corrected['id']})
        self.problem(409,self.api.activity,self.owner,item['id'],req(kind='note',text='Second correction',occurred_on='2026-11-03',supersedes_id=first['id'],correction_reason='Attempt'))
        self.problem(400,self.api.activity,self.owner,item['id'],req(kind='meeting',text='Future visit',occurred_on='2027-01-01',supersedes_id=None,correction_reason=''))
        validate_integrity(self.office)

    def test_inquiry_project_and_catalogue_offer_are_single_canonical_objects_after_reply_loss(self):
        source=self.inquiry();item=self.save(inquiry_id=source['id'])
        command=self.adopt_body(item);adopted=self.api.adoption(self.owner,item['id'],'project',command)
        self.assertEqual(self.api.adoption(self.owner,item['id'],'project',command),adopted)
        self.assertEqual(Inquiries(self.office).get(self.owner,source['id'])['project_id'],adopted['project_id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
        offer_command=self.adopt_body(item,'offer');offer=self.api.adoption(self.owner,item['id'],'offer',offer_command)
        self.assertEqual(self.api.adoption(self.owner,item['id'],'offer',offer_command),offer)
        document=Documents(self.office).get(self.owner,offer['document_id'])
        self.assertEqual((document['kind'],document['status'],document['totals']['net']),('offer','draft','159.90'))
        self.assertNotEqual(document['totals']['net'],'1234.56')
        self.assertEqual(document['customer_id'],self.contact['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],1)
        self.problem(409,self.api.adoption,self.owner,item['id'],'project',self.adopt_body(item))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_document_outbox').fetchone()[0],0)
        business_schema.validate_integrity(self.office)

    def test_already_converted_inquiry_reuses_project_without_second_allocation(self):
        source=self.inquiry();item=self.save(inquiry_id=source['id'])
        converted=Inquiries(self.office).convert(self.owner,source['id'],req(revision=source['revision'],customer_id=self.contact['id'],project_name='Existing canonical project'))
        linked=self.api.adoption(self.owner,item['id'],'project',self.adopt_body(item))
        self.assertEqual(linked['project_id'],converted['project']['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)

    def test_failed_adoption_rolls_back_project_inquiry_link_and_receipt_together(self):
        source=self.inquiry();item=self.save(inquiry_id=source['id']);body=self.adopt_body(item)
        with patch.object(self.api,'remember',side_effect=RuntimeError('Synthetic interrupted transaction')):
            with self.assertRaises(RuntimeError):self.api.adoption(self.owner,item['id'],'project',body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_sales_adoptions').fetchone()[0],0)
        self.assertIsNone(Inquiries(self.office).get(self.owner,source['id'])['project_id'])
        adopted=self.api.adoption(self.owner,item['id'],'project',body)
        self.assertEqual(Inquiries(self.office).get(self.owner,source['id'])['project_id'],adopted['project_id'])
        business_schema.validate_integrity(self.office)

    def test_fresh_rights_protect_views_history_forecasts_and_known_receipts(self):
        body=self.command();item=self.api.save(self.owner,body)
        for fn,args in ((self.api.listing,()),(self.api.view,(item['id'],)),(self.api.history,(item['id'],)),(self.api.activities,(item['id'],))):
            self.problem(403,fn,self.tech,*args)
        with self.office.db:self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner['id'],))
        self.problem(403,self.api.save,self.owner,body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_sales_versions').fetchone()[0],1)

    def test_stale_contact_catalogue_and_revision_fail_before_adoption(self):
        item=self.save();body=self.adopt_body(item)
        BusinessFoundation(self.office).save_contact(self.owner,req(revision=self.contact['revision'],name='Updated canonical customer'),self.contact['id'])
        self.problem(409,self.api.adoption,self.owner,item['id'],'project',body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],0)
        self.api.adoption(self.owner,item['id'],'project',self.adopt_body(item))
        offer=self.adopt_body(item,'offer');offer['positions'][0]['article_revision']=99
        self.problem(409,self.api.adoption,self.owner,item['id'],'offer',offer)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)

    def test_nonce_collision_and_failed_original_receipt_markers_are_distinct(self):
        body=self.command();item=dispatch(self.office,self.owner,'/sales/opportunities','POST',body)[0]
        with self.assertRaises(Problem) as collision:dispatch(self.office,self.owner,'/sales/opportunities','POST',{**body,'title':'Changed original'})
        self.assertIsNone(collision.exception.request_resolution)
        with self.assertRaises(Problem) as stale:dispatch(self.office,self.owner,'/sales/opportunities','POST',self.command(id=item['id'],revision=0))
        self.assertEqual(stale.exception.status,409)
        self.assertEqual(stale.exception.request_resolution,'not_accepted')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_sales_versions').fetchone()[0],1)

    def test_history_cannot_be_replaced_and_integrity_rejects_tampering(self):
        item=self.save();row=dict(self.office.db.execute('SELECT * FROM business_sales_versions').fetchone())
        with self.assertRaises(sqlite3.DatabaseError),self.office.db:
            self.office.db.execute('INSERT OR REPLACE INTO business_sales_versions('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        self.office.db.execute('BEGIN')
        try:
            self.office.db.execute('DROP TRIGGER business_sales_versions_update_guard')
            self.office.db.execute("UPDATE business_sales_versions SET payload_json='{}'")
            with self.assertRaises(ValueError):validate_integrity(self.office)
        finally:self.office.db.rollback()
        validate_integrity(self.office)

    def test_contact_erasure_keeps_historical_sales_snapshots_and_explains_blocker_without_project(self):
        item=self.save()
        result=BusinessFoundation(self.office).erase_contact(self.owner,self.contact['id'],req(revision=self.contact['revision'],confirmed=True))
        self.assertEqual(result['status'],'blocked')
        self.assertTrue(any('Verkaufschancen' in message for message in result['blockers']))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],0)
        self.assertEqual(self.api.history(self.owner,item['id'])['items'][0],item)
        self.assertIsNone(BusinessFoundation(self.office).contact(self.owner,self.contact['id'])['erased_at'])


if __name__=='__main__':unittest.main()
