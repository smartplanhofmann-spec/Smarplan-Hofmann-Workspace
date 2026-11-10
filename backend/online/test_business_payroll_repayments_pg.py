"""Actual bound MFA employee repayment, expense reduction and full dump restore."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading
import unittest
import psycopg

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_cash import PayrollCash
from business_accounting_euer import EuerAccounting
from business_payroll_facts import reference
from core import Problem
from online.store import LOCK_ID
from online.store import PostgresOffice
from online import test_business_payroll_payment_dates_pg as dates
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve


@unittest.skipUnless(dates.prior.fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class ActualRepaymentPostgres(unittest.TestCase):
    setUpClass=classmethod(dates.ActualPaymentDatesPostgres.setUpClass.__func__)
    windows_calculate=dates.ActualPaymentDatesPostgres.windows_calculate
    setUp=dates.ActualPaymentDatesPostgres.setUp
    reopen=dates.ActualPaymentDatesPostgres.reopen
    call=dates.ActualPaymentDatesPostgres.call
    login=dates.ActualPaymentDatesPostgres.login
    sources=dates.ActualPaymentDatesPostgres.sources
    profile=dates.ActualPaymentDatesPostgres.profile
    post=dates.ActualPaymentDatesPostgres.post
    cash_body=dates.ActualPaymentDatesPostgres.cash_body
    cash_payload=dates.ActualPaymentDatesPostgres.cash_payload
    private_file=dates.ActualPaymentDatesPostgres.private_file
    forecast=dates.ActualPaymentDatesPostgres.forecast
    save_case=dates.ActualPaymentDatesPostgres.save_case
    prepare_run=dates.ActualPaymentDatesPostgres.prepare_run
    review=dates.ActualPaymentDatesPostgres.review
    pay=dates.ActualPaymentDatesPostgres.pay
    workflow=dates.ActualPaymentDatesPostgres.workflow
    correction=dates.ActualPaymentDatesPostgres.correction
    import_net=dates.ActualPaymentDatesPostgres.import_net

    def test_actual_concurrent_repayment_writers_and_fresh_role_withdrawal(self):
        data=self.workflow()
        _,_,positive_command=self.correction(data)
        positive=self.call('POST','/business/payroll/runs',positive_command).json
        paid,_=self.pay(data,positive,data['payment'],day='2026-11-01')
        self.forecast(data,2000000)
        current_case=self.call('GET','/business/payroll/multiple-one-off-cases/'+data['case']['id']).json
        case=self.save_case(data,current_case)
        review=self.review(data);review.update(schema_version=2,contract='source5_actual_net_repayment_review_v1')
        inputs=dict(employee_id=data['employee']['id'],source_schema_version=5,
            multiple_one_off_case_ref=reference(case),settlement_review=review)
        preview=self.call('POST','/business/payroll/preview',inputs).json
        command=dates.prior.req(**inputs,id=positive['id'],revision=positive['revision'],confirmed=True,
            preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],
            correction_reason='Concurrent actual employee repayment with original positive prefix')
        run=self.call('POST','/business/payroll/runs',command).json
        delta=run['settlement_transition']['net_delta_minor'];self.assertLess(delta,0)
        details=deepcopy(paid['details']);index=len(details['payments'])
        details.update(run_id=run['id'],run_revision=run['revision'],payment_source_schema_version=4,prior_payment_ref=reference(paid))
        details['payments'].append(dict(paid_on='2026-11-03',amount_minor=delta,payment_reference='SYN-PG-CONCURRENT-REPAYMENT-20261103'))
        details['settlement_allocations'].append(dict(payment_index=index,running_minor=0,
            one_off_allocations=[dict(event_key=run['settlement_transition']['event_key'],net_minor=delta)]))
        payment_command=dates.prior.req(employee_id=data['employee']['id'],kind='payment',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=details)
        barrier=threading.Barrier(2)
        def apply(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:return 'accepted',PayrollAccounts(office).save(self.owner,payment_command)
                except Problem as error:
                    self.assertEqual(error.status,423)
                    self.assertNotIn('request_resolution',error.response())
                    self.assertEqual(office.db.contexts,[])
                    self.assertEqual(office.db.execute('SELECT 1').fetchone()[0],1)
                    return 'busy',None
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
        print('Actual concurrent repayment outcomes: '+','.join(status for status,_ in results),flush=True)
        accepted=[value for status,value in results if status=='accepted']
        self.assertTrue(accepted)
        self.assertTrue(all(value==accepted[0] for value in accepted))
        self.assertEqual(self.call('POST','/business/payroll/account-records',payment_command).json,accepted[0])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_account_requests WHERE request_id=?',
            (payment_command['request_id'],)).fetchone()[0],1)
        with self.office.db:self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner['id'],))
        self.call('POST','/business/payroll/account-records',payment_command,status=403)
        with self.office.db:self.office.db.execute("UPDATE users SET role='owner' WHERE id=?",(self.owner['id'],))
        self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
        self.assertEqual(self.call('POST','/business/payroll/account-records',payment_command).json,accepted[0])
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_http_busy_keeps_ambiguous_original_and_rolls_back_the_connection(self):
        body=dict(name='Synthetic bounded lock customer',notes='Controlled busy retry; no real customer')
        original=self.call('GET','/customers').json
        self.office.db.execute("SET lock_timeout = '100ms'")
        try:
            with psycopg.connect(dates.prior.fixture.DSN) as blocker:
                blocker.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK_ID,))
                response=self.call('POST','/customers',body,status=423)
                self.assertEqual(set(response.json),{'error'})
                self.assertIn('ursprünglichen Auftrag',response.json['error'])
                self.assertEqual(self.office.db.contexts,[])
                self.assertEqual(self.office.db.execute('SELECT 1').fetchone()[0],1)
        finally:self.office.db.execute("SET lock_timeout = '10s'")
        self.assertEqual(self.call('GET','/customers').json,original)
        self.call('POST','/customers',body,status=201)
        self.assertEqual(len(self.call('GET','/customers').json),len(original)+1)
        self.assertEqual(self.office.db.contexts,[])

    def test_actual_repayment_euer_annual_originals_and_private_mfa_survive_dump_restore(self):
        data=self.workflow(money=True,windows_original=True)
        old=data['run'];old_pdf=self.call('GET','/business/payroll/runs/'+old['id']+'/pdf').data
        _,_,command=self.correction(data)
        positive=self.call('POST','/business/payroll/runs',command).json
        paid,_=self.pay(data,positive,data['payment'],day='2026-11-01')
        addition,_=self.import_net(paid,[2]);self.post('payroll_cash',self.cash_payload(addition))
        self.forecast(data,2000000);case=self.save_case(data,self.call('GET','/business/payroll/multiple-one-off-cases/'+data['case']['id']).json)
        review=self.review(data);review.update(schema_version=2,contract='source5_actual_net_repayment_review_v1')
        inputs=dict(employee_id=data['employee']['id'],source_schema_version=5,
            multiple_one_off_case_ref=reference(case),settlement_review=review)
        preview=self.call('POST','/business/payroll/preview',inputs).json
        command=dates.prior.req(**inputs,id=positive['id'],revision=positive['revision'],confirmed=True,
            preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],
            correction_reason='Actual corrected previous-employer certificate with separate actual employee repayment')
        run=self.call('POST','/business/payroll/runs',command).json
        transition=run['settlement_transition'];delta=transition['net_delta_minor']
        self.assertLess(delta,0)
        details=deepcopy(paid['details']);index=len(details['payments'])
        details.update(run_id=run['id'],run_revision=run['revision'],payment_source_schema_version=4,
            prior_payment_ref=reference(paid))
        details['payments'].append(dict(paid_on='2026-11-03',amount_minor=delta,
            payment_reference='SYN-PG-ACTUAL-EMPLOYEE-REPAYMENT-20261103'))
        details['settlement_allocations'].append(dict(payment_index=index,running_minor=0,
            one_off_allocations=[dict(event_key=transition['event_key'],net_minor=delta)]))
        payment_command=dates.prior.req(employee_id=data['employee']['id'],kind='payment',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=details)
        response=self.client.post('/api/v1/business/payroll/account-records',json=payment_command,
            base_url='https://office.example.test',headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(response.status_code,200,response.json)
        repayment=response.json
        self.assertEqual(repayment['details']['payments'][:index],paid['details']['payments'])
        batch,cash_command=self.import_net(repayment,[index]);movement=batch['public_source']['cash_movements'][0]
        self.assertEqual(movement['direction'],'in');self.assertEqual(movement['date'],'2026-11-03')
        self.assertEqual(Decimal(movement['amount']),Decimal(-delta)/100)
        self.post('payroll_cash',self.cash_payload(batch))
        report=self.call('GET','/business/accounting/euer/report?year=2026').json
        self.assertEqual(Decimal(report['totals']['confirmed_expenses']),
            Decimal(run['calculation']['net_minor']-run['calculation']['net_deductions_minor'])/100)
        annual_details=deepcopy(data['annual_basis']['details'])
        annual_details.update(as_of_date='2026-11-03',current_calculation_case_ref=None,
            payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(repayment)])
        proposal=dict(employee_id=data['employee']['id'],employee_revision=data['employee']['revision'],
            kind='annual_basis',details=annual_details,source_file_ids=[data['file']['id']])
        response=self.client.post('/api/v1/business/payroll/annual-facts/preview',json=proposal,
            base_url='https://office.example.test',headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(response.status_code,200,response.json)
        annual_preview=response.json
        annual_command=dates.prior.req(**proposal,revision=0,status='active',confirmed=True,preview_hash=annual_preview['preview_hash'])
        annual=self.call('POST','/business/payroll/annual-facts',annual_command).json
        self.assertEqual(annual['plan']['earlier_other_taxable_minor'],50000)
        self.assertEqual(len(annual['plan']['projection']['prior_one_offs']),1)
        self.call('GET','/business/payroll/account-records/'+repayment['id'],token=data['tech'],status=403)
        self.call('POST','/business/payroll/account-records',payment_command,token=data['tech'],status=403)
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json
        self.assertNotIn(review['evidence_ref']['id'],str(own));self.assertNotIn('settlement_review',str(own))
        self.assertEqual(self.call('POST','/business/payroll/account-records',payment_command).json,repayment)
        self.assertTrue(business_schema.validate_integrity(self.office));self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner,command),run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner,payment_command),repayment)
                self.assertEqual(PayrollCash(restored).confirm(self.owner,cash_command),batch)
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner,annual_command),annual)
                self.assertEqual(EuerAccounting(restored).report(self.owner,2026)['totals'],report['totals'])
                self.assertEqual(Payroll(restored).export(self.owner,old['id'],'pdf',revision='1')[0],old_pdf)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
