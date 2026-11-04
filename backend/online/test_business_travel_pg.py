"""Real PostgreSQL travel sources, concurrent writers, old migration and restore."""
import base64
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
import uuid

import psycopg
import business_schema
from core import Problem
from business_personnel_workflow import _sha
from business_travel_allowances import TravelAllowances,_ref,protected_tables,validate_integrity
from travel_allowance_cash import record_payment,public_source
from online import release,test_business_company_handover_pg as bound
from online.store import PostgresOffice,migrate
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve

fixture=bound.fixture.fixture
req=bound.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class TravelPostgres(unittest.TestCase):
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    login=bound.CompanyHandoverPostgres.login
    call=bound.CompanyHandoverPostgres.call

    def original_sources(self):
        uid=self.call('POST','/users',dict(email='travel-pg-tech@example.test',password='Synthetic-travel-pg-password-123',role='technician'),status=201).json['id']
        tech=self.login('travel-pg-tech@example.test','Synthetic-travel-pg-password-123')
        employee=self.call('POST','/business/employees',req(user_id=uid,name='Synthetic Travel Employee',weekly_minutes=1200,hourly_cost_minor=2300,employment_from='2026-01-01',employment_to=None),status=201).json
        original=b'%PDF-1.4\nSynthetic actual private travel source\n%%EOF'
        file=self.call('POST','/business/personnel/files',req(employee_id=employee['id'],purpose='expense_receipt',owner_visible=True,filename='actual-travel.pdf',media_type='application/pdf',content_base64=base64.b64encode(original).decode()),token=tech).json
        account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='TRAVEL',name='Synthetic actual travel bank',kind='bank'),status=201).json
        return dict(employee=employee,tech=tech,file=file,original=original,account=account)

    def workflow(self,data=None,*,mixed=False):
        data=data or self.original_sources();employee=data['employee'];sites=[]
        for kind in ('home','external_fixed'):
            body=req(employee_id=employee['id'],id=uuid.uuid4().hex,revision=0,status='active',correction_reason='',details=dict(name='Synthetic '+kind,kind=kind,address='Private synthetic address',rate_id='de_2026',timezone='Europe/Berlin',effective_from='2026-01-01',effective_to=None,assignment_basis='Verified assignment',regular_days_per_week=2,history_complete_from='2025-09-01',prior_visit_dates=[],source_file_ids=[data['file']['id']]))
            sites.append(self.call('POST','/business/personnel/travel/sites',body,token=data['tech']).json['result'])
        begin='2026-10-26T08:00:00+01:00';end='2026-10-26T18:00:00+01:00'
        body=req(employee_id=employee['id'],id=uuid.uuid4().hex,revision=0,correction_reason='',details=dict(purpose='Private real customer journey',project_id=None,departed_at=begin,returned_at=end,timezone='Europe/Berlin',source_file_ids=[data['file']['id']],home_site_ref=_ref(sites[0]),first_workplace_ref=None,segments=[dict(id=uuid.uuid4().hex,**{'from':begin,'to':end},site_ref=_ref(sites[1]),activity='work',transport='ground',necessary_stopover=False)],overnights=[],meals=[],expense_refs=[],requested_meal_minor=1400,requested_lodging_minor=0,tax_choice='tax_free_only',private_intervals=[]))
        if mixed:
            sessions=[dict(id=uuid.uuid4().hex,**{'from':'2026-10-26T08:00:00+01:00','to':'2026-10-26T12:00:00+01:00'},kind='business',source_file_ids=[data['file']['id']]),
                      dict(id=uuid.uuid4().hex,**{'from':'2026-10-26T13:00:00+01:00','to':'2026-10-26T15:00:00+01:00'},kind='private',source_file_ids=[data['file']['id']])]
            body['details'].update(requested_meal_minor=933,private_intervals=[{k:sessions[1][k] for k in ('from','to')}],
                mixed_assessment=dict(method='documented_program_ratio',program_sessions=sessions,program_complete=True,cost_allocation_reviewed=True,source_file_ids=[data['file']['id']],review_note='Complete original programme and separate cost records checked.'))
        if data.get('expense'):
            expense=data['expense'];body['details'].update(expense_refs=[_ref(expense)],expense_allocations=[dict(expense_ref=_ref(expense),receipt_file_id=data['file']['id'],kind='transport',business_minor=2000,private_minor=0,provided_minor=0,review_note='Actual completely business travel ticket')])
        draft=self.call('POST','/business/personnel/travel/trips',body,token=data['tech']).json['result']
        current=self.call('GET','/business/personnel/travel/trips/'+draft['id'],token=data['tech']).json
        trip=self.call('POST','/business/personnel/travel/trips/'+draft['id']+'/submit',req(employee_id=employee['id'],revision=1,source_hash=current['source_hash'],confirmed=True),token=data['tech']).json['result']
        value=dict(employee_id=employee['id'],trip_refs=[_ref(trip)],period_from='2026-10-26',period_to='2026-10-26',settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=933 if mixed else 1400,requested_lodging_minor=0,correction_of=None,review_note='Independently checked full sources')
        preview=self.call('POST','/business/personnel/travel/settlements/preview',value).json
        command=req(**value,id=uuid.uuid4().hex,revision=0,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)
        return data|dict(trip=trip,command=command)

    def payment(self,data,settlement):
        original=b'%PDF-1.4\nSynthetic actual bank confirmation '+uuid.uuid4().hex.encode()+b'\n%%EOF'
        file=self.call('POST','/business/personnel/files',req(employee_id=data['employee']['id'],purpose='personnel',owner_visible=False,filename='actual-bank.pdf',media_type='application/pdf',content_base64=base64.b64encode(original).decode())).json
        current=self.call('GET','/business/personnel/travel/sources?employee_id='+data['employee']['id']).json
        return req(employee_id=data['employee']['id'],id=uuid.uuid4().hex,revision=0,action='record',settlement_ref=_ref(settlement),instance_id=self.instance,account_id=data['account']['id'],account_revision=data['account']['revision'],kind='reimbursement',paid_on='2026-10-27',amount_minor=1400,reference='Synthetic actual travel payment',reference_file_id=file['id'],source_hash=current['source_hash'],correction_reason='',confirmed=True)

    def test_actual_mfa_http_private_boundary_runtime_guards_and_restart(self):
        data=self.workflow();accepted=self.call('POST','/business/personnel/travel/settlements',data['command']).json
        payment=self.payment(data,accepted['result']);paid=self.call('POST','/business/personnel/travel/payments',payment).json
        public=self.call('GET','/business/personnel/travel/financial/'+paid['target_id']+'?revision=1').json
        self.assertEqual(public['cash_movements'][0]['amount'],'14.00')
        self.call('GET','/business/personnel/travel/financial/'+paid['target_id'],token=data['tech'],status=403)
        for table in protected_tables():
            column='id' if table.endswith(('sites','trips','settlements','payments','cash_events')) else 'request_id' if table.endswith('requests') else 'claim_key' if table.endswith('claims') else 'evidence_key'
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.assertRaisesRegex(psycopg.Error,'immutable travel evidence'):
                        with operator.transaction():operator.execute('SET LOCAL ROLE "smartplan-migrator"');operator.execute(statement)
        self.reopen();self.assertEqual(self.call('POST','/business/personnel/travel/settlements',data['command']).json,accepted)
        self.assertEqual(self.call('GET','/business/personnel/travel/requests/'+payment['request_id']).json,paid)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_two_actual_connections_one_daily_claim_and_exact_payment_receipt(self):
        data=self.workflow();commands=[data['command'],data['command']|req(id=uuid.uuid4().hex)]
        def approve_one(command):
            office=PostgresOffice(self.runtime)
            try:
                try:return TravelAllowances(office).approve(self.owner,command)
                except Problem as error:return error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(approve_one,commands))
        self.assertEqual(sum(isinstance(r,dict) for r in results),1);self.assertIn(409,results)
        settlement=next(r['result'] for r in results if isinstance(r,dict));payment=self.payment(data,settlement)
        def pay(_):
            office=PostgresOffice(self.runtime)
            try:return record_payment(TravelAllowances(office),self.owner,payment)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:paid=list(pool.map(pay,range(2)))
        self.assertEqual(paid[0],paid[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)
        self.assertTrue(validate_integrity(self.office))

    def test_actual_old_reimbursement_adoption_is_one_finance_source_without_second_payment(self):
        data=self.original_sources();employee=data['employee']
        expense=self.call('POST','/business/personnel/expenses',req(employee_id=employee['id'],revision=0,purpose='Actual earlier train ticket',start_date='2026-10-26',end_date='2026-10-26',items=[dict(date='2026-10-26',description='Actual business train',amount_minor=2000,currency='EUR',receipt_file_id=data['file']['id'],project_id=None)]),token=data['tech']).json
        expense=self.call('POST','/business/personnel/expenses/'+expense['id']+'/submit',req(revision=expense['revision']),token=data['tech']).json
        expense=self.call('POST','/business/personnel/expenses/'+expense['id']+'/approve',req(revision=expense['revision'],reason='Verified actual business receipt')).json
        expense=self.call('POST','/business/personnel/expenses/'+expense['id']+'/reimburse',req(revision=expense['revision'],payment_reference='Synthetic actual legacy reimbursement',paid_on='2026-10-27',amount_minor=2000,confirmed=True)).json
        data=self.workflow(data|dict(expense=expense));settlement=self.call('POST','/business/personnel/travel/settlements',data['command']).json['result']
        original=expense['payments'][0]
        body=self.payment(data,settlement)|dict(action='adopt_legacy',amount_minor=2000,reference=original['reference'],legacy_payment=dict(expense_ref=_ref(expense),payment_index=0,payment_hash=_sha(original)))
        accepted=self.call('POST','/business/personnel/travel/payments',body).json
        self.assertEqual(self.call('POST','/business/personnel/travel/payments',body).json,accepted)
        public=self.call('GET','/business/personnel/travel/financial/'+accepted['target_id']).json
        self.assertEqual(public['cash_movements'][0]['amount'],'20.00')
        self.call('POST','/business/personnel/travel/payments',self.payment(data,settlement))
        self.assertEqual(TravelAllowances(self.office).hr._latest(expense['id'],'expense'),expense)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],2)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_additive_old_personnel_migration_actual_dump_restore_and_payment_horizon(self):
        self.office.db.close();full=business_schema.registry()
        # Model the actual pre-travel financial registry. Later opening-balance
        # and historical-asset modules require that missing predecessor and
        # must be migrated together with it, not installed in the old fixture.
        later_financial_modules={'business_travel_allowances','business_accounting_openings','business_accounting_asset_openings','business_accounting_open_items','business_accounting_year_openings'}
        prior=tuple(s for s in full if s.name not in later_financial_modules)
        with patch.object(business_schema,'registry',return_value=prior),patch.object(business_schema,'MODULE_NAMES',tuple(s.name for s in prior)):
            self.setUp();data=self.original_sources();before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        after=release.snapshot_fingerprint(fixture.DSN)
        for table,value in before.items():
            if table not in ('business_schema_migrations','business_schema_state','business_schema_events'):self.assertEqual(after[table],value,table)
        release.secure_database(fixture.DSN,test_mode=True);self.reopen();data=self.workflow(data)
        accepted=self.call('POST','/business/personnel/travel/settlements',data['command']).json
        payment=self.payment(data,accepted['result']);paid=self.call('POST','/business/personnel/travel/payments',payment).json
        pdf=self.call('GET','/business/personnel/travel/settlements/'+accepted['target_id']+'/export?format=pdf&revision=1').data
        frozen=public_source(self.office,paid['target_id'],1);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            operator=PostgresOffice(target)
            try:
                evidence=evidence_for(operator,report);self.assertEqual(evidence['schema'],16)
                self.assertEqual(evidence['accounting_horizon']['travel_cash']['table_counts']['business_travel_payments'],1)
                approve(operator,evidence)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=TravelAllowances(restored)
                self.assertEqual(api.status(self.owner,payment['request_id']),paid)
                self.assertEqual(api.export(self.owner,accepted['target_id'],1,'pdf')[0],pdf)
                self.assertEqual(public_source(restored,paid['target_id'],1),frozen)
                self.assertEqual(bytes(api.hr._file(data['file']['id'])['original']),data['original'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()

    @patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v2')
    @patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v2')
    def test_v3_original_programme_http_actual_payment_and_dump_restore_under_v2_default(self):
        with patch('payroll_travel_2026.RULE_VERSION','de_travel_2026_v3'),patch('business_travel_allowances.RULE_VERSION','de_travel_2026_v3'):
            data=self.workflow(mixed=True);accepted=self.call('POST','/business/personnel/travel/settlements',data['command']).json
            calculation=accepted['result']['calculation']
            self.assertEqual(calculation['rule_version'],'de_travel_2026_v3')
            self.assertEqual(calculation['days'][0]['business_share'],dict(numerator=2,denominator=3))
            self.assertEqual(calculation['totals']['tax_free_minor'],933)
            self.assertEqual(calculation['mixed_program_sources'][0]['source_file_ids'],[data['file']['id']])
        payment=self.payment(data,accepted['result'])|dict(amount_minor=933)
        paid=self.call('POST','/business/personnel/travel/payments',payment).json
        self.assertEqual(self.call('POST','/business/personnel/travel/payments',payment).json,paid)
        frozen=public_source(self.office,paid['target_id'],1)
        self.assertEqual(frozen['cash_movements'][0]['amount'],'9.33')
        document=self.call('GET','/business/personnel/travel/settlements/'+accepted['target_id']+'/export?format=json&revision=1').data
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=TravelAllowances(restored)
                self.assertEqual(api.status(self.owner,payment['request_id']),paid)
                self.assertEqual(api.export(self.owner,accepted['target_id'],1,'json')[0],document)
                self.assertEqual(public_source(restored,paid['target_id'],1),frozen)
                self.assertEqual(bytes(api.hr._file(data['file']['id'])['original']),data['original'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
