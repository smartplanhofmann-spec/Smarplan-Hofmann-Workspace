"""Actual MFA/HTTP, independent writers and cash/restore for evidenced periods."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

import business_schema
from business_accounting_euer import EuerAccounting
from business_foundation import BusinessFoundation
from business_payroll import Payroll,validate_integrity,TABLES
from business_payroll_cash import PayrollCash
from business_payroll_facts import reference
from core import Problem
from online import release,test_business_payroll_facts_pg as facts,test_business_accounting_euer_pg as euer
from online.store import PostgresOffice
from online.instance import bind
from online.storage import Storage
from online.web import create_app
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
from payroll_cash_sources import calculated
from test_payroll_de_2026 import profile
from test_payroll_transition_2026 import assessment
import test_business_payroll_accounts as accounts
import test_business_payroll_cash as cash
from test_business_payroll_periods import reconcile_payroll_batches

fixture=facts.fixture
req=fixture.request


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class PeriodPayrollPostgres(unittest.TestCase):
    login=facts.PayrollFactsPostgres.login
    call=facts.PayrollFactsPostgres.call
    sources=facts.PayrollFactsPostgres.sources
    profile=euer.EuerPostgres.profile
    post=euer.EuerPostgres.post
    body=cash.PayrollCashTests.body
    payload=cash.PayrollCashTests.payload

    def setUp(self):
        self.instance=None
        facts.PayrollFactsPostgres.setUp(self)
        self.directory=tempfile.TemporaryDirectory(prefix='synthetic-period-payroll-pg-');self.addCleanup(self.directory.cleanup)
        self.instance=uuid.uuid4().hex
        self.storage_config={'server':{'path':str(Path(self.directory.name)/'company')}}
        operator=PostgresOffice(fixture.DSN)
        try:bind(operator,self.instance,'office.example.test',self.key,Storage(operator,self.key,'office.example.test',config=self.storage_config))
        finally:operator.db.close()
        self.reopen()

    def reopen(self):
        if not self.instance:return facts.PayrollFactsPostgres.reopen(self)
        self.office.db.close();self.office=PostgresOffice(self.runtime);self.addCleanup(self.office.db.close)
        storage=Storage(self.office,self.key,'office.example.test',config=self.storage_config)
        self.app=create_app(office=self.office,key=self.key,host='office.example.test',storage=storage,instance_id=self.instance)
        self.client=self.app.test_client()

    def workflow(self,kind='regular',transition=False):
        data=self.sources();employee=data['employee'];original=data['file']
        if kind=='regular':
            amount=100000 if transition else 500000
            data['agreement']=self.call('POST','/business/personnel/agreements',req(employee_id=employee['id'],id=data['agreement']['id'],revision=1,
                effective_from='2026-01-01',employment_kind='regular',pay_basis='monthly',amount_minor=amount,currency='EUR',
                reference_file_id=original['id'],correction_reason='Synthetic original regular partial contract')).json
            values=profile('regular',regular_annual_gross_minor=amount*12,health_additional_percent='2.90',
                tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
            if transition:values['transition_assessment']=assessment(assessed_on='2026-01-01')
            data['profile']=self.call('POST','/business/payroll/profiles',req(employee_id=employee['id'],id=data['profile']['id'],revision=1,
                profile=values,source_file_id=original['id'],confirmed=True,correction_reason='Synthetic verified regular source')).json
            current=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month=2026-10').json
            data['preparation']=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee['id'],month='2026-10',
                id=data['preparation']['id'],revision=1,source_hash=current['source_hash'],completeness_confirmed=True,
                correction_reason='Synthetic changed original agreement')).json
            data['identity']=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',revision=0,
                source_file_id=original['id'],confirmed=True,details=accounts.PayrollAccountTests.identity_details(self,data,
                    employment_from='2026-10-15',employment_to=None))).json
        common=dict(employee_id=employee['id'],employee_revision=employee['revision'],revision=0,status='active',source_file_ids=[original['id']],confirmed=True)
        terms=self.call('POST','/business/payroll/facts',req(**common,kind='employment_terms',details=dict(employment_from='2026-10-15',employment_to=None,
            agreement_refs=[reference(data['agreement'])],proration_method='calendar_days_actual',reason='Actual independently evidenced contractual quotient'))).json
        details=dict(month='2026-10',preparation_ref=reference(data['preparation']),employment_terms_ref=reference(terms),work_schedule_ref=None,
            profile_refs=[reference(data['profile'])],identity_refs=[reference(data['identity'])],tax_treatment='domestic_running_wages',entitlement_decisions=[],
            verification_note='Actual calendar/SV/tax periods reviewed separately')
        prepared=self.call('POST','/business/payroll/periods/preview',dict(employee_id=employee['id'],employee_revision=employee['revision'],
            details=details,source_file_ids=[original['id']])).json
        self.assertTrue(prepared['can_calculate'])
        fact=self.call('POST','/business/payroll/facts',req(**common,kind='period_case',details=details,preview_hash=prepared['preview_hash'])).json
        inputs=dict(source_schema_version=2,employee_id=employee['id'],period_case_ref=reference(fact))
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertTrue(preview['can_finalize'])
        command=req(**inputs,preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],confirmed=True,revision=0)
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        return data|dict(fact=fact,run=run,command=command,inputs=inputs)

    def test_actual_mfa_regular_partial_private_sources_permissions_and_restart(self):
        data=self.workflow();run=data['run'];employee=data['employee']['id']
        self.assertEqual(run['calculation']['gross_minor'],274194)
        self.assertEqual(run['calculation']['scope'],'regular_standard_period')
        original=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.call('GET','/business/payroll/runs/'+run['id'],token=data['tech'],status=403)
        self.call('GET','/business/payroll/ledger?employee_id='+employee+'&year=2026',token=data['tech'],status=403)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('POST','/business/payroll/preview',data['inputs'],token=device,status=403)
        uid=self.call('POST','/users',dict(email='period-review@example.test',password='Synthetic-period-reviewer123',role='accountant'),status=201).json['id']
        token=self.login('period-review@example.test','Synthetic-period-reviewer123');grants=BusinessFoundation(self.office)
        for permission in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,req(user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        command=data['command']|req(id=run['id'],revision=1,correction_reason='Actual repeated independent source review')
        accepted=self.call('POST','/business/payroll/runs',command,token=token).json
        self.assertEqual(accepted['revision'],2)
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        denied=self.call('POST','/business/payroll/runs',command,token=token,status=403).json
        self.assertNotIn('request_resolution',denied)
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,run)
        self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf?revision=1').data,original)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_two_pg_connections_accept_only_one_original_partial_revision(self):
        data=self.workflow('minijob');barrier=threading.Barrier(2)
        command=data['command']|req(id=data['run']['id'],revision=1,correction_reason='Synthetic concurrent independent review')
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return Payroll(office).finalize(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0]['revision'],2)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],2)
        self.assertTrue(validate_integrity(self.office))

    def test_actual_partial_midijob_payment_euer_and_frozen_dump_restore(self):
        data=self.workflow(transition=True);run=data['run'];employee=data['employee']['id'];original=data['file'];net_minor=run['calculation']['net_minor']
        paid=self.call('POST','/business/payroll/account-records',req(employee_id=employee,kind='payment',revision=0,source_file_id=original['id'],confirmed=True,
            details=dict(run_id=run['id'],run_revision=1,identity_id=data['identity']['id'],identity_revision=1,
                payments=[dict(paid_on=self.today,amount_minor=net_minor,payment_reference='SYN-PARTIAL-NET')],
                tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True))).json
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='PARTIAL',name='Actual synthetic partial payroll bank',kind='bank'),status=201).json
        self.profile()
        def post_cash(body):
            preview=self.call('POST','/business/payroll/cash/preview',body).json
            command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
            batch=self.call('POST','/business/payroll/cash/batches',command,status=201).json
            self.post('payroll_cash',self.payload(batch))
            return batch,command
        net,cash_command=post_cash(self.body(paid));amounts=calculated(run['calculation'])
        remittance,_=post_cash(self.body(paid,kind='remittance',sources=[dict(source_kind='run',id=run['id'],revision=1,content_hash=run['content_hash'],amounts=amounts)],
            settlement=dict(paid_on=self.today,payment_reference='SYN-PARTIAL-SV',amount_minor=sum(amounts.values()),source_file_id=original['id'],employee_id=employee,sha256=original['sha256'])))
        bank_report=reconcile_payroll_batches(self.office,self.owner,self.account,[net,remittance],lambda:self.now)
        expected=run['calculation']['employer_total_excluding_accident_insurance_minor']
        self.assertEqual(self.call('GET','/business/accounting/euer/report?year=2026').json['totals']['confirmed_expenses'],f'{expected//100}.{expected%100:02d}')
        original_pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        exported,_=self.post('export',dict(year=2026));frozen=self.call('GET','/business/accounting/euer/exports/'+exported['id']).json
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner,data['command']),run)
                self.assertEqual(Payroll(restored).export(self.owner,run['id'],'pdf')[0],original_pdf)
                self.assertEqual(EuerAccounting(restored).exported(self.owner,exported['id']),frozen)
                from business_bank_reconciliation import BankReconciliation
                restored_bank=BankReconciliation(restored).reconciliation(self.owner,bank_report['record']['id'])
                self.assertEqual({key:restored_bank[key] for key in ('record','exports')},bank_report)
                self.assertTrue(restored_bank['current'])
                with self.assertRaises(Problem) as error:PayrollCash(restored).confirm(self.owner,cash_command)
                self.assertEqual(error.exception.status,409)
                evidence=evidence_for(restored,report)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:approve(operator,evidence)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(PayrollCash(restored).confirm(self.owner,cash_command),net)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
            after=release.snapshot_fingerprint(target)
            for table in TABLES:self.assertEqual(after[table],before[table])


if __name__=='__main__':unittest.main()
