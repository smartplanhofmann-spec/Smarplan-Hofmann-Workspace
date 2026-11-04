"""Actual event templates must respect the explicit dated-price boundary."""
import base64
import unittest
import uuid

import business_schema
import test_business_company_events as fixture
from business_catalog_prices import CatalogPrices
from business_documents import Documents
from inquiries import Inquiries
from test_business_catalog_prices import raw, row


class CompanyEventsCatalogV2Integration(unittest.TestCase):
    def scenario(self, dated):
        f=fixture.CompanyEventTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        inquiry=Inquiries(f.office).create(f.owner,fixture.request(subject='Synthetic combined catalog event',message='Quote original source.',sender_email='buyer@example.test'))
        conversion=Inquiries(f.office).convert(f.owner,inquiry['id'],fixture.request(revision=inquiry['revision'],project_name='Synthetic combined event',customer=dict(name='Synthetic combined customer')))
        project=conversion['project']['id'];customer=f.office.project(f.owner,project)['customer_id']
        with f.office.db:
            f.office.db.execute('INSERT INTO business_contact_addresses(id,customer_id,purpose,label,street,postal_code,city,country,position) VALUES(?,?,?,?,?,?,?,?,0)',(uuid.uuid4().hex,customer,'billing','Synthetic address','Synthetic street 2','10117','Berlin','DE'))
        if dated:
            prices=CatalogPrices(f.office,clock=f.clock)
            source=prices.create_source(f.owner,fixture.request(name='Synthetic event price',reference='SYN-EVENT-V2'))
            staged=prices.stage(f.owner,source['id'],fixture.request(catalog_revision='SYN-1',filename='synthetic.csv',content_base64=base64.b64encode(raw(row())).decode()))
            choices=dict(expected_source_version=prices.source(source['id'])['source_version'],replacements={},bindings={'SYN-PRICE':dict(action='create',article_id=None,article_revision=None,expected_binding_revision=0,confirm_name_difference=False)})
            preview=prices.preview(f.owner,staged['id'],choices)
            accepted=prices.apply(f.owner,staged['id'],fixture.request(**choices,preview_sha256=preview['preview_sha256'],confirmation=True))
            article=dict(id=accepted['bindings'][0]['article_id'],revision=1)
        else:
            article=Documents(f.office).save_article(f.owner,fixture.request(name='Synthetic unchanged price',code='SYN-OLD',kind='service',unit='HUR',unit_price_net='123.45',tax_rate='7',active=True))
        f.rule(project_ids=[project],trigger='communication.received',action='offer.draft',template=dict(title='Original catalog event quote',due_days=14,positions=[dict(article_id=article['id'],article_revision=article['revision'],quantity='2')]))
        return f

    def test_undated_original_article_creates_exact_draft_once(self):
        f=self.scenario(False);run,command=f.scan();plan=f.plans_for(run)[0]
        self.assertEqual(plan['status'],'succeeded')
        offer=Documents(f.office).get(f.owner,plan['outcome']['result']['id'])
        self.assertEqual((offer['status'],offer['totals']['net']),('draft','246.90'))
        self.assertEqual(f.api.scan(f.owner,command),run)
        f.scan()
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],1)
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_document_outbox').fetchone()[0],0)
        business_schema.validate_integrity(f.office)

    def test_dated_article_without_explicit_price_is_not_executable_or_a_zero_offer(self):
        f=self.scenario(True);run,command=f.scan();plan=f.plans_for(run)[0]
        self.assertEqual(plan['preparation_error'],dict(code='action_source_unavailable',status_code=409))
        self.assertIsNone(plan['parameters']);self.assertFalse(plan['can_execute'])
        self.assertEqual(plan['blocked']['status_code'],409)
        self.assertIsNone(plan['execution']);self.assertIsNone(plan['outcome'])
        self.assertEqual(run['processing']['items'][0]['status'],'blocked')
        self.assertEqual(f.api.scan(f.owner,command),run)
        f.scan()
        for table in ('business_documents','business_document_versions','business_document_outbox','business_company_event_executions'):
            self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)
        business_schema.validate_integrity(f.office)
