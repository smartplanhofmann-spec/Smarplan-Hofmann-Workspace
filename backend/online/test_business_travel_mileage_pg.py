"""Real bound PostgreSQL/MFA mileage originals, cash, archive and restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
import zipfile

import business_schema
from business_accounting_euer import EuerAccounting
from business_bank_reconciliation import BankReconciliation
from business_travel_allowances import TravelAllowances, _ref
from business_travel_mileage import MileageTravel
from company_export_archive import verify
from core import Problem
from online import test_business_travel_pg as existing
from online.store import PostgresOffice
from online.instance import bind
from online.storage import Storage
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_bank_reconciliation as bank
import test_business_travel_finance as finance

fixture=existing.fixture
req=existing.req
PREFIX='/business/personnel/travel/mileage'


@unittest.skipUnless(fixture.DSN,'Own guarded synthetic local PostgreSQL required')
class MileagePostgres(unittest.TestCase):
    reopen=existing.TravelPostgres.reopen
    login=existing.TravelPostgres.login
    call=existing.TravelPostgres.call
    original_sources=existing.TravelPostgres.original_sources
    payment=existing.TravelPostgres.payment

    def setUp(self):
        self.instance=None
        existing.bound.fixture.EuerPostgres.setUp(self)
        self.directory=tempfile.TemporaryDirectory(prefix='synthetic-mileage-pg-');self.addCleanup(self.directory.cleanup)
        root=Path(self.directory.name).resolve(strict=True)
        self.instance=req()['request_id'];self.storage_config={'server':{'path':str(root/'company')}}
        operator=PostgresOffice(fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()
        self.owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())

    def workflow(self):
        data=self.original_sources();employee=data['employee'];files=[]
        for label in ('vehicle','complete-route'):
            raw=('%PDF-1.4\nSynthetic private mileage '+label+' '+req()['request_id']+'\n%%EOF').encode()
            files.append(self.call('POST','/business/personnel/files',req(employee_id=employee['id'],purpose='personnel',
                owner_visible=True,filename=label+'.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())).json)
        sites=[]
        for kind in ('home','external_fixed'):
            sites.append(self.call('POST','/business/personnel/travel/sites',req(employee_id=employee['id'],id=req()['request_id'],revision=0,
                status='active',correction_reason='',details=dict(name='Synthetic '+kind,kind=kind,address='Private synthetic address',
                rate_id='de_2026',timezone='Europe/Berlin',effective_from='2026-01-01',effective_to=None,
                assignment_basis='Actual employee assignment',regular_days_per_week=2,history_complete_from='2025-09-01',
                prior_visit_dates=[],source_file_ids=[files[1]['id']])),token=data['tech']).json['result'])
        h,p=sites;vehicle,evidence=files
        body=req(employee_id=employee['id'],id=req()['request_id'],revision=0,correction_reason='',details=dict(
            purpose='Actual private PostgreSQL customer journey',project_id=None,departed_at='2026-10-26T08:00:00+01:00',
            returned_at='2026-10-26T13:00:00+01:00',timezone='Europe/Berlin',home_site_ref=_ref(h),first_workplace_ref=None,
            source_file_ids=[vehicle['id'],evidence['id']],mileage=dict(schema_version=1,vehicle_kind='private_car',
                vehicle_registration='SYNTHETIC-PG-1',vehicle_file_id=vehicle['id'],declaration_file_id=evidence['id'],
                employee_bears_vehicle_costs=True,no_employer_vehicle=True,only_business_travel=True,
                no_commuting_or_family_home=True,no_collection_point_or_wide_area=True,no_other_reimbursement=True,
                review_note='Actual complete original route reviewed',legs=[
                    dict(id=req()['request_id'],departed_at='2026-10-26T08:00:00+01:00',arrived_at='2026-10-26T09:00:00+01:00',
                        from_site_ref=_ref(h),to_site_ref=_ref(p),distance_m=50000,evidence_file_id=evidence['id']),
                    dict(id=req()['request_id'],departed_at='2026-10-26T12:00:00+01:00',arrived_at='2026-10-26T13:00:00+01:00',
                        from_site_ref=_ref(p),to_site_ref=_ref(h),distance_m=50000,evidence_file_id=evidence['id'])])))
        draft=self.call('POST',PREFIX+'/trips',body,token=data['tech']).json
        sources=self.call('GET',PREFIX+'/sources?employee_id='+employee['id'],token=data['tech']).json
        submit=req(employee_id=employee['id'],revision=1,source_hash=sources['source_hash'],confirmed=True)
        trip=self.call('POST',PREFIX+'/trips/'+body['id']+'/submit',submit,token=data['tech']).json['result']
        base=dict(employee_id=employee['id'],trip_refs=[_ref(trip)],period_from='2026-10-26',period_to='2026-10-26',settlement_unit='trip',
            tax_choice='tax_free_only',requested_meal_minor=0,requested_lodging_minor=0,correction_of=None,review_note='Actual independent PostgreSQL review')
        preview=self.call('POST',PREFIX+'/settlements/preview',base).json
        command=req(**base,id=req()['request_id'],revision=0,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)
        return dict(data,trip=trip,draft_command=body,draft=draft,submit=submit,command=command,files=files,sites=sites)

    def test_actual_mfa_cash_bank_euer_company_archive_and_frozen_dump_restore(self):
        data=self.workflow();settlement_receipt=self.call('POST',PREFIX+'/settlements',data['command']).json
        settlement=settlement_receipt['result']
        pdf=self.call('GET',PREFIX+'/settlements/'+settlement['id']+'/export?format=pdf&revision=1').data
        self.call('GET',PREFIX+'/trips/'+data['trip']['id'])
        payments=[];commands=[]
        for amount in (1000,2000):
            command=self.payment(data,settlement)|dict(amount_minor=amount,reference='Synthetic mileage transfer '+req()['request_id'])
            commands.append(command);payments.append(self.call('POST',PREFIX+'/payments',command).json)
        ledger=finance.TravelFinanceTests('runTest');ledger.f=SimpleNamespace(now=datetime(2026,11,3,tzinfo=timezone.utc))
        ledger.office=self.office;ledger.owner=self.owner;ledger.euer=EuerAccounting(self.office,clock=lambda:ledger.f.now)
        ledger.b=bank.BankTests('runTest');ledger.b.office=self.office;ledger.b.owner=self.owner;ledger.b.account=data['account']
        ledger.b.bank=BankReconciliation(self.office,clock=lambda:ledger.f.now);ledger.b.configure()
        for payment in payments:ledger.post('travel_cash',ledger.payload(payment['result']))
        statement,report,bank_command=ledger.bank_match(*(x['result'] for x in payments))
        self.assertEqual(ledger.euer.report(self.owner,2026)['totals']['confirmed_expenses'],'30.00')
        archive_command=existing.bound.CompanyHandoverPostgres.command(self)
        exported=self.call('POST','/business/company-handover/exports',archive_command,status=201).json
        raw=self.call('GET','/business/company-handover/exports/'+exported['id']+'/archive').data
        self.assertTrue(verify(raw,instance_id=self.instance)['valid'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            text=archive.read('data/business_travel_trips.jsonl').decode()
            self.assertIn('SYNTHETIC-PG-1',text)
            self.assertIn(data['files'][1]['id'],text)
            self.assertIn('data/business_travel_payments.jsonl',archive.namelist())
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.reopen()
        self.assertEqual(self.call('POST',PREFIX+'/settlements',data['command']).json,settlement_receipt)
        self.assertEqual(self.call('POST',PREFIX+'/payments',commands[0]).json,payments[0])
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=MileageTravel(restored)
                self.assertEqual(api.status(self.owner,data['command']['request_id']),settlement_receipt)
                self.assertEqual(api.status(self.owner,commands[0]['request_id']),payments[0])
                self.assertEqual(api.export(self.owner,settlement['id'],1,'pdf')[0],pdf)
                from business_company_handover import CompanyHandover
                self.assertEqual(bytes(CompanyHandover(restored).exported(self.owner,exported['id'],action='archive')),raw)
                self.assertEqual(EuerAccounting(restored).report(self.owner,2026)['totals']['confirmed_expenses'],'30.00')
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()

    def test_two_actual_postgresql_connections_claim_one_original_day_and_retry_one_payment(self):
        data=self.workflow();barrier=threading.Barrier(2)
        commands=[data['command'],dict(data['command'],id=req()['request_id'],request_id=req()['request_id'])]
        def writer(command):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:return MileageTravel(office).approve(self.owner,command)
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,commands))
        accepted=[v for v in results if isinstance(v,dict)];rejected=[v for v in results if isinstance(v,int)]
        self.assertEqual(len(accepted),1);self.assertEqual(rejected,[409])
        payment=self.payment(data,accepted[0]['result'])|dict(amount_minor=3000)
        from travel_allowance_cash import record_payment
        def payer(_):
            office=PostgresOffice(self.runtime)
            try:return record_payment(MileageTravel(office),self.owner,payment)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:paid=list(pool.map(payer,range(2)))
        self.assertEqual(paid[0],paid[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__=='__main__':unittest.main()
