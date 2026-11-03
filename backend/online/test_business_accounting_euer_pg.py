"""Actual PostgreSQL runtime + MFA/HTTP coherent EÜR/period/adviser workflow."""
import base64
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid
from unittest.mock import patch

from online import test_business_project_economics_pg as economics_fixture
from business_accounting_euer import validate_integrity
from business_schema import require_runtime_security
from business_accounting_euer import EuerAccounting
import business_schema
from core import Problem
from online import release
from online.store import PostgresOffice, migrate
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve

fixture=economics_fixture.fixture
req=economics_fixture.req


@unittest.skipUnless(fixture.DSN,'Disposable loopback SMARTPLAN_TEST_DSN required')
class EuerPostgres(unittest.TestCase):
    setUp=economics_fixture.ProjectEconomicsPostgres.setUp
    reopen=economics_fixture.ProjectEconomicsPostgres.reopen
    call=economics_fixture.ProjectEconomicsPostgres.call
    login=economics_fixture.ProjectEconomicsPostgres.login
    project=economics_fixture.ProjectEconomicsPostgres.project
    issuer=economics_fixture.ProjectEconomicsPostgres.issuer
    invoice=economics_fixture.ProjectEconomicsPostgres.invoice
    payment=economics_fixture.ProjectEconomicsPostgres.payment

    def profile(self):
        state=self.call('GET','/business/accounting/profile').json
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic explicit profile',evidence_reference='Synthetic owner decision',
                  profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',
                               vat_effective_from=self.today[:4]+'-01-01',bookkeeping_start=self.today[:4]+'-01-01'))
        preview=self.call('POST','/business/accounting/profile/preview',body).json
        self.call('POST','/business/accounting/profile/confirm',req(**body,confirmation=True,preview_hash=preview['preview_hash']),status=201)

    def post(self,operation,payload):
        state=self.call('GET','/business/accounting/euer').json
        body=dict(operation=operation,payload=payload,expected_revision=state['revision'],state_hash=state['state_hash'],
                  reason='Synthetic verified facts and SKR04 mapping',evidence_reference='Synthetic original source')
        preview=self.call('POST','/business/accounting/euer/preview',body).json
        command=req(**body,confirmation=True,preview_hash=preview['preview_hash'])
        result=self.call('POST','/business/accounting/euer/confirm',command,status=201).json
        return result,command

    def incoming(self,project,net='50.00',tax='9.50',gross='59.50'):
        receipt=self.call('POST','/business/finance/receipts',req(project_id=project,filename='synthetic-proof.pdf',media_type='application/pdf',
            original_base64=base64.b64encode(b'%PDF-1.4\nSynthetic Euer '+uuid.uuid4().hex.encode()).decode())).json
        return self.call('POST','/business/finance/receipts/'+receipt['id'],req(revision=0,vendor='Synthetic source',invoice_number='SYN-'+uuid.uuid4().hex,
            issue_date=self.today,net=net,tax=tax,gross=gross,currency='EUR',status='reviewed',note='Explicit original check')).json

    def source(self,kind,identifier):
        return next(value for value in self.call('GET','/business/accounting/euer/sources').json['items'] if value['kind']==kind and value['id']==identifier)['source']

    def document(self,event):
        base='/business/accounting/components/events/'+event['id']
        state=self.call('GET',base).json; portion=self.call('GET',base+'/portions').json['items'][0]
        body=dict(source_hash=state['source_hash'],expected_revision=state['revision'],state_hash=state['state_hash'],portion_id=portion['portion_id'],
                  portion_state_hash=portion['portion_state_hash'],groups=[dict(group_id=portion['groups'][0]['group_id'],amount=portion['amount'])],reason='Exact documentary cents')
        preview=self.call('POST',base+'/preview',body).json
        self.call('POST',base+'/confirm',req(**body,confirmation=True,preview_hash=preview['preview_hash']),status=201)

    def cash(self,event,expense=False):
        source=self.source('cash',event['id'])
        return dict(event_id=event['id'],source_hash=source['source_hash'],euer_date=event['cash_date'],year_rule={'kind':'cash'},
                    lines=[dict(unit_id=unit['unit_id'],category='materials' if expense else 'sales',business_net=unit['net'],deductible_net=unit['net'] if expense else '0.00',
                                business_tax=unit['tax'],deductible_input_tax=unit['tax'] if expense else '0.00',deductible_tax_cost='0.00',
                                account='5400' if expense else '4400',vat_account='1406' if expense else '3806') for unit in source['units']])

    def test_real_issuer_cash_original_vat_period_correction_export_and_restart(self):
        self.assertTrue(require_runtime_security(self.office)); self.profile(); project=self.project(); self.issuer()
        account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='BANK',name='Synthetic bank',kind='bank'),status=201).json
        invoice=self.invoice(project,'100.00'); payment=self.payment(invoice,'119.00')
        source=next(value for value in self.call('GET','/business/accounting/sources/payments').json['items'] if value['payment_id']==payment['id'])
        cash=self.call('POST','/business/accounting/events/import-payment',req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],
            account_id=account['id'],account_revision=account['revision'],cash_date=self.today,evidence_reference='Synthetic bank incoming'),status=201).json
        self.document(cash); sale,sale_command=self.post('cash',self.cash(cash))
        receipt=self.incoming(project); source=self.source('receipt',receipt['id'])
        self.post('input_vat',dict(receipt_id=receipt['id'],source_hash=source['source_hash'],invoice_received_date=self.today,service_date=self.today,
                                 prepayment=False,payment_event_id=None,entitlement_date=self.today,deductible_tax='9.50',account='1406',conditions_confirmed=True))
        payout_source=next(value for value in self.call('GET','/business/accounting/sources/receipts').json['items'] if value['receipt_id']==receipt['id'])
        payout=self.call('POST','/business/accounting/events/payout',req(confirmation=True,receipt_id=receipt['id'],source_hash=payout_source['source_hash'],
            review_revision=payout_source['review_revision'],review_sha256=payout_source['review_sha256'],original_sha256=payout_source['original_sha256'],
            account_id=account['id'],account_revision=1,expected_cash_revision=0,amount='59.50',cash_date=self.today,
            evidence_reference='Synthetic bank outgoing',reference='Supplier paid'),status=201).json
        self.document(payout); self.post('cash',self.cash(payout,True))
        tax=self.incoming(project,'9.50','0.00','9.50'); source=self.source('receipt',tax['id'])
        self.post('external_cash',dict(receipt_id=tax['id'],source_hash=source['source_hash'],account_id=account['id'],account_revision=1,
            evidence_key='Synthetic bank VAT payment',cash_date=self.today,amount='9.50',direction='out',category='vat_payment',euer_date=self.today,year_rule={'kind':'cash'},account='3820'))
        report=self.call('GET','/business/accounting/euer/report?year='+self.today[:4]).json
        self.assertEqual(report['totals']['euer_surplus'],'50.00'); self.assertTrue(report['complete_for_recorded_sources'])
        self.assertEqual(report['totals']['vat_balance'],'9.50'); self.assertEqual(len(report['cash_movements']),3)
        close=dict(period=self.today[:7],action='close',expected_period_revision=0,attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True))
        self.post('period',close)
        state=self.call('GET','/business/accounting/euer').json
        blocked=dict(operation='reverse',payload=dict(entry_id=sale['id']),expected_revision=state['revision'],state_hash=state['state_hash'],reason='Correction',evidence_reference='Checked')
        self.call('POST','/business/accounting/euer/preview',blocked,status=409)
        self.post('period',dict(close,action='reopen',expected_period_revision=1))
        self.post('correct',dict(entry_id=sale['id'],operation='cash',payload=self.cash(cash)))
        exported,command=self.post('export',{'year':int(self.today[:4])})
        saved=self.call('GET','/business/accounting/euer/exports/'+exported['id']).json
        self.assertEqual(saved['report']['totals']['euer_surplus'],'50.00')
        self.reopen()
        self.assertEqual(self.call('POST','/business/accounting/euer/confirm',command,status=201).json,exported)
        self.assertEqual(self.call('GET','/business/accounting/euer/exports/'+exported['id']).json,saved)
        self.assertEqual(self.call('POST','/business/accounting/euer/confirm',sale_command,status=201).json,sale)
        self.assertTrue(validate_integrity(self.office))
        with self.assertRaises(Exception):
            with self.office.db:self.office.db.execute('DELETE FROM business_euer_entries')
        self.assertTrue(validate_integrity(self.office))

    def test_http_strictness_opaque_rights_and_safe_missing_receipt_resolution(self):
        self.profile(); project=self.project(); receipt=self.incoming(project); source=self.source('receipt',receipt['id'])
        payload=dict(receipt_id=receipt['id'],source_hash=source['source_hash'],invoice_received_date=self.today,service_date=self.today,prepayment=False,
                     payment_event_id=None,entitlement_date=self.today,deductible_tax='9.50',account='1406',conditions_confirmed=True)
        entry,command=self.post('input_vat',payload)
        rejected=self.call('POST','/business/accounting/euer/confirm',dict(command,request_id=uuid.uuid4().hex),status=409).json
        self.assertEqual(rejected['request_resolution'],'not_accepted')
        self.call('GET','/business/accounting/euer/report?year=2026&year=2027',status=400)
        self.call('GET','/business/accounting/euer',{'body':'forbidden'},status=400)
        self.call('POST','/business/accounting/euer/confirm?unexpected=yes',command,status=400)
        user=self.office.add_user('euer-technician@example.test','Synthetic-technician-password-123','technician')
        technician=self.login('euer-technician@example.test','Synthetic-technician-password-123')
        response=self.call('POST','/business/accounting/euer/confirm',command,token=technician,status=403).json
        self.assertNotIn('request_resolution',response)
        self.assertEqual(self.call('POST','/business/accounting/euer/confirm',command,status=201).json,entry)

    def test_identical_request_across_two_real_connections_posts_only_once(self):
        self.profile(); project=self.project(); receipt=self.incoming(project); source=self.source('receipt',receipt['id'])
        payload=dict(receipt_id=receipt['id'],source_hash=source['source_hash'],invoice_received_date=self.today,service_date=self.today,prepayment=False,
                     payment_event_id=None,entitlement_date=self.today,deductible_tax='9.50',account='1406',conditions_confirmed=True)
        state=self.call('GET','/business/accounting/euer').json
        body=dict(operation='input_vat',payload=payload,expected_revision=state['revision'],state_hash=state['state_hash'],reason='Concurrent explicit decision',evidence_reference='Synthetic checked source')
        preview=self.call('POST','/business/accounting/euer/preview',body).json
        command=req(**body,confirmation=True,preview_hash=preview['preview_hash'])
        owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        def run(unused):
            office=PostgresOffice(self.runtime)
            try:return EuerAccounting(office).confirm(owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(run,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_euer_entries').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_euer_requests').fetchone()[0],1)

    def test_pre_euer_migration_preserves_originals_and_real_restore_requires_schema10_horizon(self):
        full=business_schema.registry(); prior=tuple(spec for spec in full if spec.name not in ('business_accounting_euer','business_payroll_cash', 'business_bank_reconciliation'))
        self.office.db.close()
        with patch.object(business_schema,'registry',return_value=prior),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in prior)):
            self.setUp(); self.profile(); project=self.project(); self.issuer()
            account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='BANK',name='Synthetic bank',kind='bank'),status=201).json
            invoice=self.invoice(project,'100.00'); payment=self.payment(invoice,'119.00')
            source=next(value for value in self.call('GET','/business/accounting/sources/payments').json['items'] if value['payment_id']==payment['id'])
            cash=self.call('POST','/business/accounting/events/import-payment',req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],
                account_id=account['id'],account_revision=1,cash_date=self.today,evidence_reference='Synthetic pre-Euer money source'),status=201).json
            self.document(cash)
            self.assertEqual(business_schema.financial_accounting_horizon(self.office)['schema_version'],7)
            before=release.snapshot_fingerprint(fixture.DSN); self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        upgraded=release.snapshot_fingerprint(fixture.DSN)
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.DSN),upgraded)
        for table,value in before.items():
            if table!='business_schema_migrations':self.assertEqual(upgraded[table],value,table)
        release.secure_database(fixture.DSN,test_mode=True); self.reopen()
        entry,command=self.post('cash',self.cash(cash)); exported,unused=self.post('export',dict(year=int(self.today[:4])))
        owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        horizon=business_schema.financial_accounting_horizon(self.office)
        self.assertEqual(horizon['schema_version'],10)
        self.assertEqual(set(horizon['euer']['table_counts'].values()),{2})
        original=EuerAccounting(self.office).exported(owner,exported['id'])
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            office=PostgresOffice(runtime)
            try:
                api=EuerAccounting(office)
                self.assertEqual(api.exported(owner,exported['id']),original)
                self.assertEqual(business_schema.financial_accounting_horizon(office),horizon)
                self.assertFalse(api.state(owner)['writes_allowed'])
                with self.assertRaises(Problem) as blocked:api.confirm(owner,command)
                self.assertEqual(blocked.exception.status,409); self.assertIsNone(blocked.exception.request_resolution)
                self.assertIn('restore_reconciliation_pending',[issue['code'] for issue in api.report(owner,int(self.today[:4]))['issues']])
            finally:office.db.close()
            operator=PostgresOffice(target)
            try:
                evidence=evidence_for(operator,report); self.assertEqual(evidence['schema'],11)
                altered=dict(evidence,accounting_horizon=dict(horizon,euer=dict(horizon['euer'],sha256='0'*64)))
                with self.assertRaises((Problem,ValueError)):approve(operator,altered)
                approve(operator,evidence)
            finally:operator.db.close()
            office=PostgresOffice(runtime)
            try:
                self.assertEqual(EuerAccounting(office).confirm(owner,command),entry)
                self.assertEqual(EuerAccounting(office).exported(owner,exported['id']),original)
                self.assertEqual(EuerAccounting(office).report(owner,int(self.today[:4]))['totals']['euer_surplus'],'119.00')
                self.assertTrue(business_schema.validate_integrity(office))
            finally:office.db.close()


if __name__=='__main__':unittest.main()
