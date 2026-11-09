"""Actual MFA/HTTP, independent PG writers, historic v2 and v3 cash restore."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

import business_schema
from business_accounting_euer import EuerAccounting
from business_foundation import BusinessFoundation
from business_payroll import Payroll,validate_integrity,TABLES
from business_payroll_cash import PayrollCash
from core import Problem
from online import release,test_business_company_handover_pg as bound,test_business_payroll_pg as payroll
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
from payroll_cash_sources import calculated
from test_payroll_transition_2026 import assessment
import test_business_payroll_accounts as accounts
import test_business_payroll_cash as cash

fixture=bound.fixture.fixture
req=bound.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class TransitionPostgres(unittest.TestCase):
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    login=bound.CompanyHandoverPostgres.login
    call=bound.CompanyHandoverPostgres.call
    profile=bound.fixture.EuerPostgres.profile
    post=bound.fixture.EuerPostgres.post
    body=cash.PayrollCashTests.body
    payload=cash.PayrollCashTests.payload

    def workflow(self):
        old=payroll.RegularPayrollPostgres.workflow(self)
        employee=old['hr']['employee']['id'];original=old['hr']['file']
        profile=self.call('POST','/business/payroll/profiles',req(employee_id=employee,id=old['profile']['id'],revision=1,
            profile=old['profile']['profile']|dict(regular_annual_gross_minor=1200000,
                transition_assessment=assessment(assessed_on=self.today)),source_file_id=original['id'],confirmed=True,
            correction_reason='Explicit reviewed transition-area forecast and corrected original contract')).json
        self.call('POST','/business/personnel/agreements',req(employee_id=employee,id=old['hr']['agreement']['id'],revision=2,
            effective_from=self.today[:7]+'-01',employment_kind='regular',pay_basis='monthly',amount_minor=100000,currency='EUR',
            reference_file_id=original['id'],correction_reason='Synthetic corrected monthly wage evidence'))
        self.call('POST','/business/payroll/preview',old['inputs'],status=409)
        current=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee+'&month='+self.today[:7]).json
        prepared=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee,id=old['inputs']['preparation_id'],
            revision=old['inputs']['preparation_revision'],month=self.today[:7],source_hash=current['source_hash'],
            completeness_confirmed=True,correction_reason='Actual corrected wage source confirmed')).json
        inputs=old['inputs']|dict(profile_revision=profile['revision'],preparation_revision=prepared['revision'],gross_minor=100000)
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertEqual(preview['calculation']['net_minor'],87467)
        command=req(**inputs,preview_hash=preview['preview_hash'],accepted_scope='regular_transition_monthly',confirmed=True,
            id=old['run']['id'],revision=1,correction_reason='Explicitly elected new rule on reviewed actual evidence')
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        self.assertEqual(self.call('POST','/business/payroll/runs',old['command']).json,old['run'])
        self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf?revision=1').data,old['pdf'])
        return dict(old=old,hr=old['hr'],profile=profile,run=run,command=command,inputs=inputs)

    def test_new_monthly_rule_mfa_private_history_fresh_permissions_and_restart(self):
        data=self.workflow();employee=data['hr']['employee']['id']
        tech=data['hr']['token']
        self.call('GET','/business/payroll/runs/'+data['run']['id']+'/json',token=tech,status=403)
        self.call('POST','/business/payroll/preview',data['inputs'],token=tech,status=403)
        grant=self.call('POST','/business/offline/access/v2',{},status=201).json
        origin=grant['binding']['instance_id']+':'+grant['binding']['account_id']
        self.call('GET','/business/payroll/runs/'+data['run']['id'],token=grant['token'],offline_origin=origin,status=403)
        uid=self.call('POST','/users',dict(email='midijob-reviewer@example.test',password='Synthetic-reviewed-midijob-password123',role='accountant'),status=201).json['id']
        token=self.login('midijob-reviewer@example.test','Synthetic-reviewed-midijob-password123')
        foundation=BusinessFoundation(self.office)
        for permission in ('personnel.read','personnel.approve'):
            foundation.save_grant(self.owner,req(user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        command=data['command']|req(revision=2,correction_reason='Synthetic independent evidence review')
        accepted=self.call('POST','/business/payroll/runs',command,token=token).json
        self.assertEqual(accepted['revision'],3)
        foundation.save_grant(self.owner,req(user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        denied=self.call('POST','/business/payroll/runs',command,token=token,status=403).json
        self.assertNotIn('request_resolution',denied)
        foundation.save_grant(self.owner,req(user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        self.call('GET','/business/payroll/profiles?employee_id='+employee,token=token,status=403)
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,data['run'])
        self.assertEqual(self.call('GET','/business/payroll/runs/'+data['run']['id']+'/json?revision=1').json,data['old']['run'])
        ledger=self.call('GET','/business/payroll/ledger?employee_id='+employee+'&year=2026').json['ledger']
        self.assertEqual(ledger['totals']['net_minor'],87467);self.assertEqual(ledger['recorded_months'],1)
        self.assertTrue(validate_integrity(self.office));business_schema.validate_integrity(self.office)

    def test_two_database_connections_repeat_one_identical_confirmed_revision(self):
        data=self.workflow();barrier=threading.Barrier(2)
        command=data['command']|req(revision=2,correction_reason='Synthetic concurrent same reviewed correction')
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return Payroll(office).finalize(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0]['revision'],3)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],3)
        self.assertTrue(validate_integrity(self.office));business_schema.validate_integrity(self.office)

    def test_actual_midijob_cash_euer_and_dump_restore_keep_v2_v3_evidence(self):
        data=self.workflow();employee=data['hr']['employee']['id'];original=data['hr']['file']
        details=accounts.PayrollAccountTests.identity_details(self,data,employment_from=self.today[:7]+'-01',employment_to='2026-11-30',
            valid_from=data['profile']['profile']['effective_from'])
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=employee,kind='identity',revision=0,
            source_file_id=original['id'],confirmed=True,details=details)).json
        paid=self.call('POST','/business/payroll/account-records',req(employee_id=employee,kind='payment',revision=0,
            source_file_id=original['id'],confirmed=True,details=dict(run_id=data['run']['id'],run_revision=2,identity_id=identity['id'],identity_revision=1,
                payments=[dict(paid_on=self.today,amount_minor=87467,payment_reference='SYN-MIDI-NET-001')],tax_free_payments_minor=0,
                tax_free_basis='',standard_case_confirmed=True))).json
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='MIDI',name='Synthetic actual payroll bank',kind='bank'),status=201).json
        self.profile()
        def post_cash(body):
            preview=self.call('POST','/business/payroll/cash/preview',body).json
            command=req(**body,preview_hash=preview['preview_hash'],confirmation=True)
            batch=self.call('POST','/business/payroll/cash/batches',command,status=201).json
            self.post('payroll_cash',self.payload(batch))
            return batch,command
        net,cash_command=post_cash(self.body(paid))
        amounts=calculated(data['run']['calculation'])
        post_cash(self.body(paid,kind='remittance',sources=[dict(source_kind='run',id=data['run']['id'],revision=2,content_hash=data['run']['content_hash'],amounts=amounts)],
            settlement=dict(paid_on=self.today,payment_reference='SYN-MIDI-SV-001',amount_minor=sum(amounts.values()),
                source_file_id=original['id'],employee_id=employee,sha256=original['sha256'])))
        self.assertEqual(self.call('GET','/business/accounting/euer/report?year=2026').json['totals']['confirmed_expenses'],'1264.03')
        export,_=self.post('export',dict(year=2026));frozen=self.call('GET','/business/accounting/euer/exports/'+export['id']).json
        fingerprints=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                api=Payroll(restored)
                self.assertEqual(api.get(self.owner,'run',data['run']['id']),data['run'])
                self.assertEqual(api.export(self.owner,data['run']['id'],'pdf','1')[0],data['old']['pdf'])
                self.assertEqual(EuerAccounting(restored).exported(self.owner,export['id']),frozen)
                # A stored calculation receipt is readable before financial
                # approval; adopting actual money remains explicitly fenced.
                self.assertEqual(api.finalize(self.owner,data['command']),data['run'])
                with self.assertRaises(Problem) as error:PayrollCash(restored).confirm(self.owner,cash_command)
                self.assertEqual(error.exception.status,409)
                evidence=evidence_for(restored,report)
                with self.assertRaises(Problem) as error:approve(restored,evidence)
                self.assertEqual(error.exception.status,403)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:approve(operator,evidence)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner,data['old']['command']),data['old']['run'])
                self.assertEqual(Payroll(restored).finalize(self.owner,data['command']),data['run'])
                self.assertEqual(PayrollCash(restored).confirm(self.owner,cash_command),net)
                self.assertTrue(validate_integrity(restored));business_schema.validate_integrity(restored)
            finally:restored.db.close()
            after=release.snapshot_fingerprint(target)
            for table in TABLES:self.assertEqual(after[table],fingerprints[table])


if __name__=='__main__':unittest.main()
