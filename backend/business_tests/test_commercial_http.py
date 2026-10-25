"""Actual Flask authentication/route/SQL/PDF commercial integration."""
from datetime import date
import hashlib
import base64
import uuid
import unittest
from unittest.mock import patch

from online import test_plan_imports as fixture
from test_documents import SyntheticDocuments,seed_synthetic_issuer


class CommercialHttpTests(unittest.TestCase):
    tearDown=fixture.PlanImportApiTests.tearDown
    open_app=fixture.PlanImportApiTests.open_app
    call=fixture.PlanImportApiTests.call

    def setUp(self):
        fixture.PlanImportApiTests.setUp(self)
        # Only the authority policy is synthetic. HTTP/auth/SQL/financial
        # calculations/PDF/archive handling are the actual production code.
        factory=patch('business_documents.Documents',SyntheticDocuments)
        factory.start();self.addCleanup(factory.stop)

    def req(self,**data):return dict(request_id=uuid.uuid4().hex,**data)

    def seller(self):
        body=self.req(revision=0,company_name='Synthetic Seller GmbH',address_line='Teststraße1',postal_code='10115',city='Berlin',country='DE',
            vat_id='DE123456789',email='seller@example.test',phone='+4930123456',iban='DE89370400440532013000',issuer_mode='own',issuing_enabled=True,cutover_ack=True,cutover_date='2020-01-01')
        self.call('POST','/business/commercial/settings',body,status=409)
        response=self.call('POST','/business/commercial/settings',{**body,'request_id':uuid.uuid4().hex,'issuing_enabled':False})
        seed_synthetic_issuer(SyntheticDocuments(self.office),self.owner)
        return response

    def draft(self,kind='invoice'):
        today=date.today().isoformat()
        return self.call('POST','/business/documents',self.req(project_id=self.project,kind=kind,title='Synthetic HTTP invoice',issue_date=today,due_date=today,
            buyer=dict(name='Synthetic customer',address_line='Testweg2',postal_code='10117',city='Berlin',country='DE',email='buyer@example.test'),
            positions=[dict(description='Synthetic service',quantity='1',unit='HUR',unit_price_net='100',tax_rate='19',kind='labor')])).json

    def issue(self,draft):return self.call('POST','/business/documents/'+draft['id']+'/finalize',self.req(revision=draft['revision'])).json

    def test_real_http_invoice_pdf_part_payment_and_nested_project_filter(self):
        self.seller();invoice=self.issue(self.draft());path='/business/documents/'+invoice['id']
        pdf=self.call('GET',path+'/pdf');self.assertEqual('application/pdf',pdf.mimetype);self.assertTrue(pdf.data.startswith(b'%PDF-'))
        payment=self.req(source_id='synthetic-bank:'+uuid.uuid4().hex,amount='50.00',booking_date=date.today().isoformat(),allocations=[dict(document_id=invoice['id'],amount='50.00')])
        saved=self.call('POST','/business/finance/payments',payment).json
        self.assertEqual(saved,self.call('POST','/business/finance/payments',payment).json)
        self.assertEqual('69.00',self.call('GET','/business/finance/open-items?project_id='+self.project).json['items'][0]['open'])
        foreign=self.office.add_project(self.owner,'Other synthetic project','Other synthetic customer')
        self.assertEqual([],self.call('GET','/business/documents?project_id='+foreign).json['items'])
        self.assertEqual([],self.call('GET','/business/finance/open-items?project_id='+foreign).json['items'])
        self.call('GET',path+'/pdf',token=None,status=401)

    def test_signed_artifact_is_separate_and_revoked_financial_read_fails_closed(self):
        self.seller();offer=self.issue(self.draft('offer'));path='/business/documents/'+offer['id']
        original=self.call('GET',path+'/pdf').data
        signature=self.call('POST',path+'/sign',self.req(revision=offer['revision'],level='simple',confirmation=True,signer='Synthetic person',strokes=[[[0.1,0.2],[0.9,0.3]]])).json
        signed=self.call('GET',path+'/signatures/'+signature['id']+'/pdf').data
        self.assertNotEqual(original,signed);self.assertEqual(hashlib.sha256(signed).hexdigest(),signature['signed_pdf_sha256'])
        self.assertEqual(original,self.call('GET',path+'/pdf').data)
        self.office.assign(self.owner,self.project,self.owner_id)
        with self.office.db:self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner_id,))
        self.call('GET',path+'/pdf',status=403)
        self.call('GET',path+'/signatures/'+signature['id']+'/pdf',status=403)

    def test_incoming_supplier_invoice_is_immutable_reviewed_and_not_own_revenue(self):
        from business_einvoice import UBL,CAC,CBC
        original=('<Invoice xmlns="'+UBL+'" xmlns:cbc="'+CBC+'" xmlns:cac="'+CAC+'">'
            '<cbc:ID>SUPPLIER-SYN-009</cbc:ID><cbc:IssueDate>2026-10-01</cbc:IssueDate><cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>'
            '<cac:LegalMonetaryTotal><cbc:TaxInclusiveAmount>119.00</cbc:TaxInclusiveAmount><cbc:PayableAmount>119.00</cbc:PayableAmount></cac:LegalMonetaryTotal></Invoice>').encode()
        source=self.call('POST','/business/finance/receipts',self.req(project_id=self.project,filename='synthetic-supplier.xml',media_type='application/xml',original_base64=base64.b64encode(original).decode())).json
        self.assertEqual('needs_review',source['status']);self.assertEqual('SUPPLIER-SYN-009',source['suggestion']['number'])
        path='/business/finance/receipts/'+source['id']
        reviewed=self.call('POST',path,self.req(revision=0,vendor='Synthetic external supplier',invoice_number='SUPPLIER-SYN-009',issue_date='2026-10-01',net='100.00',tax='19.00',gross='119.00',currency='EUR',status='reviewed')).json
        self.assertEqual('reviewed',reviewed['status']);self.assertEqual(original,self.call('GET',path+'/original').data)
        self.assertEqual([],self.call('GET','/business/finance/open-items').json['items'])
        self.assertEqual(0,self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0])
        self.assertEqual(1,len(self.call('GET','/business/finance/receipts?project_id='+self.project).json['items']))

    def test_catalog_detail_routes_return_one_bound_item_and_reject_wrong_service_type(self):
        article=self.call('POST','/business/articles',self.req(name='Synthetic material',code='SYN-M',kind='material',unit='C62',unit_price_net='12.50',cost_price_net='8.00',tax_rate='19',active=True)).json
        detail=self.call('GET','/business/articles/'+article['id']).json
        self.assertEqual(article['id'],detail['id']);self.assertEqual('12.50',detail['unit_price_net']);self.assertNotIn('items',detail)
        self.call('GET','/business/services/'+article['id'],status=404)
        template=self.call('POST','/business/templates',self.req(name='Synthetic template',kind='offer',title='Synthetic offer',positions=[dict(description='Synthetic',quantity='1',unit='C62',unit_price_net='12.50',tax_rate='19')])).json
        self.assertEqual(template['id'],self.call('GET','/business/templates/'+template['id']).json['id'])
        text=self.call('POST','/business/text-blocks',self.req(name='Synthetic greeting',text='Synthetic text')).json
        self.assertEqual(text['id'],self.call('GET','/business/text-blocks/'+text['id']).json['id'])


if __name__=='__main__':unittest.main()
