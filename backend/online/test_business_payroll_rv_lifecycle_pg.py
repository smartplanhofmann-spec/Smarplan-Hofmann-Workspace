"""Actual MFA/HTTP RV originals, concurrent receipts and full database restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_rv_lifecycle import PayrollRvLifecycle,RULE_VERSION,KIND,TABLES
from business_payroll_facts import reference
from online.store import PostgresOffice
from online import test_business_payroll_entitlements_pg as entitlements
from online import test_business_company_handover_pg as bound
from online import test_business_payroll_payment_dates_pg as dates
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_payroll_accounts as accounts
from test_payroll_minijob_rv_lifecycle_2026 import settled

fixture=entitlements.fixture
req=entitlements.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class RvLifecyclePostgres(unittest.TestCase):
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    call=bound.CompanyHandoverPostgres.call
    login=dates.ActualPaymentDatesPostgres.login
    sources=entitlements.PayrollEntitlementsPostgres.sources

    def test_actual_mfa_original_concurrency_profile_payroll_private_pdf_and_full_restore(self):
        data=self.sources();employee=data['employee'];proof=data['file']
        employee=self.call('POST','/business/employees',req(id=employee['id'],revision=employee['revision'],
            employment_from='2026-01-01',employment_to=None),status=201).json
        original=self.call('POST','/business/payroll/profiles',req(employee_id=employee['id'],id=data['profile']['id'],
            revision=data['profile']['revision'],profile=dict(data['profile']['profile'],minijob_rv_exempt=True),
            source_file_id=proof['id'],confirmed=True,correction_reason='Synthetic actual established original exemption')).json
        preview=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month=2026-10').json
        preparation=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee['id'],month='2026-10',
            id=data['preparation']['id'],revision=data['preparation']['revision'],source_hash=preview['source_hash'],completeness_confirmed=True,
            correction_reason='Synthetic actual full continuing employment original')).json
        file_ref=dict(id=proof['id'],revision=1,content_hash=proof['content_hash'])
        a=dict(schema_version=1,employee_id=employee['id'],episode_id=employee['id'],employment_from='2026-01-01',employment_to=None,
            target_month='2026-10',reviewed_as_of='2026-10-31',sole_continuous_commercial_minijob_confirmed=True,
            no_old_age_or_other_exclusion_confirmed=True,established_exemption=dict(effective_from='2026-01-01',profile_ref=reference(original),
                evidence_ref=file_ref,established_status_confirmed=True),revocation=None,review_note='Synthetic actual original employment and exemption reviewed')
        settled(a)
        proposal=dict(employee_id=employee['id'],employee_revision=employee['revision'],kind=KIND,rule_version=RULE_VERSION,
            source_contract_version=1,details=dict(assessment=a,prior_assessment_refs=[]),source_file_ids=[proof['id']])
        preview=self.call('POST','/business/payroll/rv-lifecycle/preview',proposal).json
        command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        barrier=threading.Barrier(2)
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:barrier.wait(timeout=15);return PayrollRvLifecycle(office).save(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(writer,range(2)))
        record=records[0];self.assertEqual(record,records[1])
        self.assertEqual(self.call('POST','/business/payroll/rv-lifecycle',command).json,record)
        self.call('GET','/business/payroll/rv-lifecycle/sources?employee_id='+employee['id'],token=data['tech'],status=403)
        inputs=dict(employee_id=employee['id'],profile_id=original['id'],profile_revision=original['revision'],
            preparation_id=preparation['id'],preparation_revision=preparation['revision'],gross_minor=60300,full_month_confirmed=True)
        self.call('POST','/business/payroll/preview',inputs,status=409)
        profile_command=req(employee_id=employee['id'],revision=0,profile=dict(original['profile'],effective_from='2026-08-01',minijob_rv_exempt=False),
            source_file_id=proof['id'],confirmed=True,rv_lifecycle_source_contract_version=1,rv_lifecycle_ref=reference(record))
        profile=self.call('POST','/business/payroll/profiles',profile_command).json
        inputs.update(profile_id=profile['id'],profile_revision=profile['revision'])
        preview=self.call('POST','/business/payroll/preview',inputs).json
        self.assertEqual(preview['calculation']['net_minor'],58129)
        run_command=req(**inputs,revision=0,confirmed=True,preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'])
        run=self.call('POST','/business/payroll/runs',run_command).json
        self.assertEqual(self.call('POST','/business/payroll/runs',run_command).json,run)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json
        self.assertEqual(own['statement']['calculation']['net_minor'],58129)
        self.assertNotIn(record['id'],str(own));self.assertNotIn(proof['id'],str(own))
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',
            revision=0,source_file_id=proof['id'],confirmed=True,
            details=accounts.PayrollAccountTests.identity_details(self,dict(profile=profile),employment_from='2026-01-01',employment_to=None,valid_from='2026-08-01'))).json
        payment_command=req(employee_id=employee['id'],kind='payment',revision=0,source_file_id=proof['id'],confirmed=True,
            details=dict(run_id=run['id'],run_revision=run['revision'],identity_id=identity['id'],identity_revision=identity['revision'],
                payments=[dict(paid_on='2026-10-31',amount_minor=58129,payment_reference='SYN-PG-RV-ACTUAL-NET')],
                tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True))
        payment=self.call('POST','/business/payroll/account-records',payment_command).json
        later=deepcopy(proposal);later['details']['prior_assessment_refs']=[reference(record)]
        later['details']['assessment']['review_note']='Synthetic later unchanged original RV review'
        proof_preview=self.call('POST','/business/payroll/rv-lifecycle/preview',later).json
        later_command=req(**later,id=record['id'],revision=1,status='active',confirmed=True,preview_hash=proof_preview['preview_hash'],correction_reason='Synthetic later reviewed original')
        current=self.call('POST','/business/payroll/rv-lifecycle',later_command).json
        self.call('POST','/business/payroll/preview',inputs,status=409)
        self.assertEqual(self.call('POST','/business/payroll/runs',run_command).json,run)
        self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
        self.assertEqual(self.call('POST','/business/payroll/rv-lifecycle',command).json,record)
        self.assertEqual(self.call('POST','/business/payroll/profiles',profile_command).json,profile)
        self.assertTrue(business_schema.validate_integrity(self.office))
        for table in TABLES:
            self.assertFalse(self.office.db.execute('SELECT has_table_privilege(current_user,?,?) AS allowed',(table,'UPDATE')).fetchone()['allowed'])
            self.assertFalse(self.office.db.execute('SELECT has_table_privilege(current_user,?,?) AS allowed',(table,'DELETE')).fetchone()['allowed'])
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=PayrollRvLifecycle(restored)
                self.assertEqual(api.save(self.owner,command),record)
                self.assertEqual(api.save(self.owner,later_command),current)
                self.assertEqual(Payroll(restored).save_profile(self.owner,profile_command),profile)
                self.assertEqual(Payroll(restored).finalize(self.owner,run_command),run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner,payment_command),payment)
                self.assertEqual(Payroll(restored).export(self.owner,run['id'],'pdf',revision='1')[0],pdf)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
            self.runtime=runtime;self.reopen();self.call('GET','/me',status=401)
            self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
            self.assertEqual(self.call('POST','/business/payroll/rv-lifecycle',later_command).json,current)
            self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data,pdf)
            self.office.db.close()


if __name__=='__main__':unittest.main()
