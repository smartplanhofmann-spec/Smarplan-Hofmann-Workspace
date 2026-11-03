"""Acceptance B/C joined through real PostgreSQL, MFA, HTTP and dump/restore.

Synthetic evidence only. The inherited frozen capture is a server-contract
check; actual offline Flutter persistence and device acceptance remain separate.
"""
import base64
from decimal import Decimal
import time
import unittest

import business_schema
from core import Problem
from online import test_customer_execution_journey_pg as execution
from online import test_business_accounting_euer_pg as euer
from online.auth import totp
from online.store import PostgresOffice
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve

req=execution.request


@unittest.skipUnless(execution.fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class CustomerFinanceServiceJourneyPostgres(unittest.TestCase):
    setUp=execution.CustomerExecutionJourneyPostgres.setUp
    reopen=execution.CustomerExecutionJourneyPostgres.reopen
    call=execution.CustomerExecutionJourneyPostgres.call
    workflow=execution.CustomerExecutionJourneyPostgres.workflow
    profile=euer.EuerPostgres.profile
    post=euer.EuerPostgres.post
    incoming=euer.EuerPostgres.incoming
    source=euer.EuerPostgres.source
    document=euer.EuerPostgres.document
    cash=euer.EuerPostgres.cash

    def login(self,email,password):
        pending=self.call('POST','/login',dict(email=email,password=password),token=None).json
        self.assertTrue(pending['mfa_required']);self.assertNotIn('token',pending)
        secrets=getattr(self,'mfa_secrets',{});steps=getattr(self,'mfa_steps',{})
        if 'enrollment' in pending:secrets[email]=pending['enrollment']['secret']
        step=max(int(time.time()//30),steps.get(email,-1)+1);steps[email]=step
        self.mfa_secrets,self.mfa_steps=secrets,steps
        return self.call('POST','/login/verify',dict(challenge=pending['challenge'],code=totp(secrets[email],step)),token=None).json['token']

    def classify(self,project,receipt,category):
        body=dict(project_id=project,receipt_id=receipt['id'],source_revision=receipt['revision'],expected_revision=0,
            allocations=[dict(category=category,amount_net=receipt['net'])],reason='Synthetic original belongs to this recorded project cost source')
        preview=self.call('POST','/business/project-economics/preview',body).json
        command=req(**body,preview_hash=preview['preview_hash'])
        result=self.call('POST','/business/project-economics/confirm',command,status=201).json
        self.assertEqual(self.call('POST','/business/project-economics/confirm',command,status=201).json,result)
        return result

    def pay_supplier(self,receipt,account,category):
        source=self.source('receipt',receipt['id'])
        self.post('input_vat',dict(receipt_id=receipt['id'],source_hash=source['source_hash'],invoice_received_date=self.today,
            service_date=self.today,prepayment=False,payment_event_id=None,entitlement_date=self.today,
            deductible_tax=receipt['tax'],account='1406',conditions_confirmed=True))
        source=next(v for v in self.call('GET','/business/accounting/sources/receipts').json['items'] if v['receipt_id']==receipt['id'])
        command=req(confirmation=True,receipt_id=receipt['id'],source_hash=source['source_hash'],review_revision=source['review_revision'],
            review_sha256=source['review_sha256'],original_sha256=source['original_sha256'],account_id=account['id'],account_revision=1,
            expected_cash_revision=0,amount=receipt['gross'],cash_date=self.today,evidence_reference='SYN-SUPPLIER-'+receipt['id'],reference='Synthetic actual supplier payment')
        event=self.call('POST','/business/accounting/events/payout',command,status=201).json
        self.assertEqual(self.call('POST','/business/accounting/events/payout',command,status=201).json,event)
        self.document(event);payload=self.cash(event,True)
        for line in payload['lines']:line['category']=category
        self.post('cash',payload)
        return event

    def equipment_service(self,data):
        project=data['project'];article=data['article']['id'];location=data['location']['id']
        stock_path='/business/inventory/stock?location_id='+location+'&article_id='+article
        self.assertEqual(self.call('GET',stock_path).json['on_hand'],'0.0000')
        opened=self.call('POST','/business/inventory/counts',req(location_id=location,article_ids=[article],
            title='Synthetic count after both devices were issued',counted_on=self.today,correction_of=None,reason='Physical empty-bin verification'),status=201).json
        path='/business/inventory/counts/'+opened['id']
        counted=self.call('POST',path+'/count',req(revision=1,lines=[dict(article_id=article,quantity='0',reason='Both delivered devices installed')])).json
        self.assertEqual(counted['items'][0]['difference'],'0.0000')
        command=req(revision=2,confirmed=True,zero_stock_unit_costs={})
        approved=self.call('POST',path+'/approve',command).json
        self.assertEqual(self.call('POST',path+'/approve',command).json,approved)
        self.assertEqual(self.call('GET',stock_path).json['on_hand'],'0.0000')
        original=data['photo'];media=self.call('POST','/business/media',req(project_id=project,filename='Synthetic-original-delivery-note.png',
            media_type='image/png',size=len(original),sha256=execution.sha(original),purpose='document',classification='operational'),status=201).json
        self.call('POST','/business/media/'+media['id']+'/chunks/0',dict(content_base64=base64.b64encode(original).decode()))
        self.call('POST','/business/media/'+media['id']+'/complete',req())
        delivery=data['deliveries'][0]
        document=self.call('POST','/business/purchasing/receipts/'+delivery['id']+'/document',req(media_id=media['id'],confirmed=True),status=201).json
        body=req(project_id=project,asset=dict(name='Synthetic actually delivered device',serial_number='SYN-JOURNEY-DEVICE-001'),
            receipt_id=delivery['id'],line_index=0,issue_movement_id=data['issue']['id'],quantity='1',confirmed=True)
        asset=self.call('POST','/business/assets/from-delivery',body,status=201).json
        self.assertEqual(self.call('POST','/business/assets/from-delivery',body,status=201).json,asset)
        self.assertEqual(asset['origin']['receipt_id'],delivery['id'])
        self.assertEqual(self.call('GET','/business'+document['download_path']).data,original)
        contract=self.call('POST','/business/maintenance/contracts',req(project_id=project,asset_id=asset['id'],
            title='Synthetic annual device maintenance',anchor_date=self.today,interval_unit='months',interval_count=12),status=201).json
        visit=self.call('POST','/business/maintenance/schedule',req(project_id=project,as_of=self.today)).json['items'][0]
        service=self.call('POST','/business/service/cases',req(revision=0,customer_id=data['customer'],person_id=None,project_id=project,
            asset_id=None,contract_id=None,visit_id=visit['id'],inquiry_id=None,defect_id=None,title='Synthetic installed device follow-up',
            kind='maintenance',priority='normal',responsible_id=self.office.user(self.token)['id'],follow_up_on=self.today,
            description='Verify the same delivered serial number and its original delivery evidence')).json
        self.assertEqual((service['asset_id'],service['contract_id']),(asset['id'],contract['id']))
        service_path='/business/service/cases/'+service['id']
        self.call('POST',service_path+'/transition',req(revision=service['revision'],source_sha256=service['source_sha256'],
            status='triaged',reason='Synthetic existing maintenance visit reviewed',resolution=''))
        service=self.call('GET',service_path).json
        report=self.call('POST','/business/service-reports',req(project_id=project,title='Synthetic device maintenance',description='Delivered serial number and function checked'),status=201).json
        report=self.call('POST','/business/service-reports/'+report['id']+'/sign',req(revision=report['revision'],expected_hash=report['content_hash'],
            signer='Synthetic Order Buyer',strokes=[[[.1,.2],[.8,.6]]])).json
        body=req(revision=service['revision'],source_sha256=service['source_sha256'],confirmation=True,report_id=report['id'])
        linked=self.call('POST',service_path+'/evidence',body).json
        self.assertEqual(self.call('POST',service_path+'/evidence',body).json,linked)
        current=self.call('GET',service_path).json
        self.call('POST',service_path+'/transition',req(revision=current['revision'],source_sha256=current['source_sha256'],
            status='resolved',reason='Synthetic evidence checked',resolution='Original device and signed report verified'))
        history_path='/business/maintenance/history?project_id='+project+'&asset_id='+asset['id']
        history=self.call('GET',history_path).json
        self.assertEqual((history['items'][0]['status'],history['items'][0]['report_pdf_sha256']),('completed',report['pdf_sha256']))
        self.assertEqual(self.call('GET','/business/projects/'+project+'/costs').json['material_actual_net'],'25.00')
        return dict(asset=asset,service_path=service_path,history_path=history_path,report=report,document=document,
            original=original,history=history,service=self.call('GET',service_path+'/history').json,
            report_pdf=self.call('GET','/business/service-reports/'+report['id']+'/pdf').data)

    def test_same_order_economics_euer_delivery_count_service_and_originals_survive_real_restore(self):
        data=self.workflow();project=data['project'];self.profile()
        self.call('POST','/business/budgets',req(project_id=project,revision=0,material_net='25.00',labor_net='25.00',machine_net='0.00',other_net='50.00'))
        economics_path='/business/project-economics?project_id='+project
        account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='SYN-JOURNEY-BANK',name='Synthetic actual company bank',kind='bank'),status=201).json
        for original,payment in data['payments']:
            source=next(v for v in self.call('GET','/business/accounting/sources/payments').json['items'] if v['payment_id']==payment['id'])
            command=req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],account_id=account['id'],
                account_revision=1,cash_date=self.today,evidence_reference=original['reference'])
            event=self.call('POST','/business/accounting/events/import-payment',command,status=201).json
            self.assertEqual(self.call('POST','/business/accounting/events/import-payment',command,status=201).json,event)
            self.document(event);self.post('cash',self.cash(event))
        receipts=[];payouts=[]
        for net,tax,gross,project_category,tax_category in (
                ('25.00','4.75','29.75','stock_material','materials'),
                ('20.00','3.80','23.80','external_service','external_services'),
                ('10.00','1.90','11.90','other','other_expense')):
            receipt=self.incoming(project,net,tax,gross);receipts.append(receipt)
            incomplete=self.call('GET',economics_path).json
            self.assertFalse(incomplete['result']['complete_for_recorded_sources']);self.assertIsNone(incomplete['result']['document_net_contribution'])
            self.classify(project,receipt,project_category)
            payouts.append(self.pay_supplier(receipt,account,tax_category))
        economics=self.call('GET',economics_path).json
        self.assertEqual(economics['costs'],dict(material_net='25.00',labor_net='17.50',external_service_net='20.00',machine_net='0.00',other_net='10.00',total_net='72.50'))
        self.assertEqual(economics['budget']['remaining_net'],'27.50');self.assertEqual(economics['result']['document_net_contribution'],'27.50')
        self.assertTrue(economics['result']['complete_for_recorded_sources']);self.assertTrue(economics['payments']['complete'])
        self.assertEqual(economics['revenue']['revenue_net'],'100.00');self.assertEqual(economics['payments']['net_inflow_gross'],'119.00')
        self.assertEqual(economics['payments']['open_gross'],'0.00');self.assertEqual(economics['payments']['supplier_outflows_gross'],'65.45')
        self.assertEqual(economics['payments']['cash_balance_gross'],'53.55')
        self.assertEqual({v['id'] for v in economics['sources']['material_movements']},{data['issue']['id']})
        self.assertEqual({v['entry_id'] for v in economics['sources']['approved_times']},{data['time_entry_id']})
        self.assertEqual({v['receipt_id'] for v in economics['sources']['receipt_allocations']},{v['id'] for v in receipts})
        self.assertEqual({v['event_id'] for v in economics['sources']['supplier_payments']},{v['id'] for v in payouts})
        report_path='/business/accounting/euer/report?year='+self.today[:4]
        report=self.call('GET',report_path).json
        self.assertTrue(report['complete_for_recorded_sources']);self.assertEqual(report['totals']['euer_surplus'],'53.55')
        self.assertEqual(report['totals']['vat_balance'],'8.55');self.assertEqual(len(report['cash_movements']),5)
        # Approved operational wage costs are not an invented employer payment;
        # retained VAT is not yet a fabricated remittance to the tax authority.
        self.assertEqual(Decimal(report['totals']['euer_surplus'])-Decimal(economics['result']['document_net_contribution']),Decimal('17.50')+Decimal('8.55'))
        equipment=self.equipment_service(data)
        self.assertEqual(self.call('GET',economics_path).json,economics)
        self.assertEqual(self.call('GET',report_path).json,report)
        self.call('GET',report_path,token=data['tech_token'],status=403)
        self.call('GET',economics_path,token=data['device_token'],status=403)
        exported,command=self.post('export',dict(year=int(self.today[:4])))
        export_path='/business/accounting/euer/exports/'+exported['id'];frozen=self.call('GET',export_path).json
        persisted_report=self.call('GET',report_path).json
        self.assertEqual(persisted_report['totals'],report['totals'])
        self.assertEqual(persisted_report['cash_movements'],report['cash_movements'])
        originals={'/business/documents/'+data['invoice']['id']+'/pdf':data['invoice_pdf'],
            '/business/service-reports/'+data['signed']['id']+'/pdf':data['report_pdf'],
            '/business/service-reports/'+equipment['report']['id']+'/pdf':equipment['report_pdf'],
            '/business'+equipment['document']['download_path']:equipment['original']}
        for receipt in receipts:
            path='/business/finance/receipts/'+receipt['id']+'/original';originals[path]=self.call('GET',path).data
        self.assertTrue(business_schema.validate_integrity(self.office));self.reopen()
        self.assertEqual(self.call('POST','/business/accounting/euer/confirm',command,status=201).json,exported)
        self.assertEqual(self.call('GET',economics_path).json,economics)
        runtime,previous_token=self.runtime,self.token;self.office.db.close()
        with disposable_restore(runtime) as (target,restored_runtime,restored):
            self.office=PostgresOffice(restored_runtime)
            try:
                self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage_config={});self.client=self.app.test_client()
                self.call('GET',economics_path,token=previous_token,status=401)
                self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                pending=self.call('GET',economics_path).json
                self.assertFalse(pending['payments']['complete']);self.assertIsNone(pending['payments']['cash_balance_gross'])
                self.call('POST','/business/accounting/euer/confirm',command,status=409)
                with self.assertRaises(Problem) as denied:approve(self.office,evidence_for(self.office,restored))
                self.assertEqual(denied.exception.status,403)
                operator=PostgresOffice(target)
                try:
                    with self.assertRaises(Problem) as active:approve(operator,evidence_for(operator,restored))
                    self.assertEqual(active.exception.status,409)
                    self.office.db.close()
                    approve(operator,evidence_for(operator,restored))
                finally:operator.db.close()
                self.office=PostgresOffice(restored_runtime)
                self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage_config={});self.client=self.app.test_client()
                self.assertEqual(self.call('POST','/business/accounting/euer/confirm',command,status=201).json,exported)
                self.assertEqual(self.call('GET',export_path).json,frozen)
                self.assertEqual(self.call('GET',economics_path).json,economics)
                self.assertEqual(self.call('GET',report_path).json,persisted_report)
                self.assertEqual(self.call('GET',equipment['history_path']).json,equipment['history'])
                self.assertEqual(self.call('GET',equipment['service_path']+'/history').json,equipment['service'])
                for path,original in originals.items():self.assertEqual(self.call('GET',path).data,original)
                self.assertEqual(self.call('GET','/business/assets/'+equipment['asset']['id']+'/origin').json,equipment['asset']['origin'])
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],1)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_assets').fetchone()[0],1)
                self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_cash_events').fetchone()[0],5)
                self.assertTrue(business_schema.validate_integrity(self.office))
            finally:self.office.db.close()


if __name__=='__main__':unittest.main()
