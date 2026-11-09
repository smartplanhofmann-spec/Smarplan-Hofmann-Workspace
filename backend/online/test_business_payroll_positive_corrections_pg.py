"""Actual MFA/PostgreSQL proof for same-gross positive Source5 corrections."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import threading
import unittest
from unittest.mock import patch

import business_schema
from business_accounting_euer import EuerAccounting
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_cash import PayrollCash
from business_payroll_facts import reference
from core import Problem
from payroll_cash_sources import COMPONENTS, calculated
from online import test_business_company_handover_pg as bound
from online import test_business_payroll_multiple_pg as original
from online import test_business_payroll_cash_pg as cash
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve
import test_business_payroll_oneoff_provenance as transport

fixture=original.fixture
req=original.req


@unittest.skipUnless(fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class PositiveCorrectionPostgres(unittest.TestCase):
    setUpClass=classmethod(transport.OneoffOriginalTransport.setUpClass.__func__)
    windows_calculate=transport.OneoffOriginalTransport.windows_calculate
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    login=bound.CompanyHandoverPostgres.login
    call=bound.CompanyHandoverPostgres.call
    sources=original.MultiplePayrollPostgres.sources
    profile=cash.PayrollCashPostgres.profile
    post=cash.PayrollCashPostgres.post
    cash_body=cash.PayrollCashPostgres.body
    cash_payload=cash.PayrollCashPostgres.payload

    def private_file(self, data, title):
        content=('%PDF-1.4\nSynthetic '+title+'\n%%EOF').encode()
        return self.call('POST','/business/personnel/files',req(
            employee_id=data['employee']['id'],purpose='personnel',owner_visible=False,
            filename='synthetic-private-proof.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(content).decode())).json

    def forecast(self, data, amount):
        reference_before=data['multiple_command']['details']['annual_tax_forecasts'][0]['annual_tax_forecast_ref']
        old=self.call('GET','/business/payroll/annual-facts/'+reference_before['id']).json
        proof=self.private_file(data,'corrected prior-employer taxable amount '+str(amount))
        details=deepcopy(old['details'])
        details.update(previous_employers=[dict(employer_name='Previous synthetic employer',
            employer_tax_number='111/222/33333',start='2026-01-01',end='2026-09-30',
            running_taxable_minor=amount,other_paid_minor=0,
            evidence_ref=dict(id=proof['id'],revision=1,content_hash=proof['content_hash']))],
            no_previous_employer_ref=None)
        proposal=dict(employee_id=data['employee']['id'],employee_revision=data['employee']['revision'],
            kind='annual_tax_forecast',details=details,source_file_ids=[data['file']['id'],proof['id']])
        preview=self.call('POST','/business/payroll/annual-facts/preview',proposal).json
        command=req(**proposal,id=old['id'],revision=old['revision'],status='active',confirmed=True,
            preview_hash=preview['preview_hash'],correction_reason='Actual corrected prior-employer certificate')
        current=self.call('POST','/business/payroll/annual-facts',command).json
        data['multiple_command']['details']['annual_tax_forecasts'][0]['annual_tax_forecast_ref']=reference(current)
        return current

    def save_case(self, data, previous=None):
        proposal={key:deepcopy(data['multiple_command'][key]) for key in (
            'employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        preview=self.call('POST','/business/payroll/multiple-one-off-cases/preview',proposal).json
        command=req(**proposal,revision=previous['revision'] if previous else 0,
            status='active',confirmed=True,preview_hash=preview['preview_hash'])
        if previous:command.update(id=previous['id'],correction_reason='Same original gross with corrected certificate')
        return self.call('POST','/business/payroll/multiple-one-off-cases',command).json

    def prepare_run(self, data, case, previous=None):
        inputs=dict(employee_id=data['employee']['id'],source_schema_version=5,multiple_one_off_case_ref=reference(case))
        if previous:
            inputs['settlement_review']=self.review(data)
        preview=self.call('POST','/business/payroll/preview',inputs).json
        command=req(**inputs,revision=previous['revision'] if previous else 0,confirmed=True,
            preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'])
        if previous:command.update(id=previous['id'],correction_reason='Positive net correction with preserved actual transfers')
        return preview,command

    def review(self, data):
        proof=self.private_file(data,'all actual net payments and remittances reviewed and complete')
        return dict(schema_version=1,payments_complete=True,remittances_complete=True,
            evidence_ref=dict(id=proof['id'],revision=1,content_hash=proof['content_hash']))

    def pay(self, data, run, prior=None):
        if prior:
            transition=run['settlement_transition'];parts=deepcopy(prior['details']['payments'])
            allocations=deepcopy(prior['details']['settlement_allocations']);index=len(parts)
            parts.append(dict(paid_on=transition['receipt_date'],amount_minor=transition['additional_net_minor'],
                payment_reference='SYN-PG-POSITIVE-DIFFERENCE-'+str(run['revision'])))
            allocations.append(dict(payment_index=index,running_minor=0,one_off_allocations=[
                dict(event_key=transition['event_key'],net_minor=transition['additional_net_minor'])]))
        else:
            current=run['calculation'];running=current['running_calculation']
            net_running=running['net_minor']-running['net_deductions_minor']
            net_bonus=current['net_minor']-current['net_deductions_minor']-net_running
            event=current['multiple_one_off_details']['receipt_events'][0]
            parts=[dict(paid_on='2026-10-30',amount_minor=net_running,payment_reference='SYN-PG-ORIGINAL-RUNNING'),
                dict(paid_on=event['receipt_date'],amount_minor=net_bonus,payment_reference='SYN-PG-ORIGINAL-BONUS')]
            allocations=[dict(payment_index=0,running_minor=net_running,one_off_allocations=[]),
                dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=event['event_key'],net_minor=net_bonus)])]
        details=original.original_pg.running_pg.entitlement_pg.accounts.PayrollAccountTests.payment_details(
            self,run,data['identity'],payments=parts)
        details.update(payment_source_schema_version=2 if prior else 1,
            prior_payment_ref=reference(prior) if prior else None,settlement_allocations=allocations)
        command=req(employee_id=data['employee']['id'],kind='payment',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=details)
        return self.call('POST','/business/payroll/account-records',command).json,command

    def import_net(self, payment, indices):
        body=self.cash_body(payment)
        body['sources'][0]['payment_indexes']=indices
        preview=self.call('POST','/business/payroll/cash/preview',body).json
        command=req(**body,confirmation=True,preview_hash=preview['preview_hash'])
        batch=self.call('POST','/business/payroll/cash/batches',command,status=201).json
        return batch,command

    def workflow(self, *, money=False, windows_original=False):
        data=original.MultiplePayrollPostgres.workflow(self,save_case=False)
        self.forecast(data,2000000)
        if windows_original:
            # Produce the actual old v7 metadata in an independent CRLF
            # process, then resume normal native execution for the correction.
            with patch('business_payroll_multiple_cases.calculate_multiple_source',side_effect=self.windows_calculate):
                case=self.save_case(data)
        else:
            case=self.save_case(data)
        _,command=self.prepare_run(data,case)
        run=self.call('POST','/business/payroll/runs',command).json
        payment,payment_command=self.pay(data,run)
        data.update(case=case,run=run,run_command=command,payment=payment,payment_command=payment_command)
        if money:
            self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='POSNET',
                name='Synthetic positive correction bank',kind='bank'),status=201).json
            self.profile()
            data['batch'],data['cash_command']=self.import_net(payment,[0,1])
            self.post('payroll_cash',self.cash_payload(data['batch']))
        return data

    def correction(self,data):
        self.forecast(data,1000000)
        case=self.save_case(data,data['case'])
        return case,*self.prepare_run(data,case,data['run'])

    def remittance_command(self, data):
        run=data['run'];amounts=dict.fromkeys(COMPONENTS,0)
        amounts['employee_tax']=calculated(run['calculation'])['employee_tax']
        self.assertGreater(amounts['employee_tax'],0)
        body=self.cash_body(data['payment'],kind='remittance',sources=[dict(source_kind='run',
            id=run['id'],revision=run['revision'],content_hash=run['content_hash'],amounts=amounts)],
            settlement=dict(paid_on='2026-10-31',payment_reference='SYN-PG-ORIGINAL-FULL-TAX',
                amount_minor=amounts['employee_tax'],source_file_id=data['file']['id'],
                employee_id=data['employee']['id'],sha256=data['file']['sha256']))
        preview=self.call('POST','/business/payroll/cash/preview',body).json
        return req(**body,confirmation=True,preview_hash=preview['preview_hash'])

    def test_actual_positive_payment_euer_private_mfa_and_originals_survive_restore(self):
        data=self.workflow(money=True,windows_original=True);old=data['run'];old_payment=data['payment']
        old_pdf=self.call('GET','/business/payroll/runs/'+old['id']+'/pdf').data
        case,preview,command=self.correction(data)
        self.assertEqual(preview['calculation']['running_calculation'],old['calculation']['running_calculation'])
        self.assertEqual(preview['calculation']['gross_minor'],old['calculation']['gross_minor'])
        run=self.call('POST','/business/payroll/runs',command).json
        self.assertGreater(run['settlement_transition']['additional_net_minor'],0)
        payment,payment_command=self.pay(data,run,old_payment)
        self.assertEqual(payment['details']['payments'][:2],old_payment['details']['payments'])
        self.assertEqual(payment['details']['settlement_allocations'][:2],old_payment['details']['settlement_allocations'])
        batch,cash_command=self.import_net(payment,[2]);self.post('payroll_cash',self.cash_payload(batch))
        self.assertEqual(sum(Decimal(m['amount']) for m in batch['public_source']['cash_movements']),
            Decimal(run['settlement_transition']['additional_net_minor'])/100)
        report=self.call('GET','/business/accounting/euer/report?year=2026').json
        self.assertEqual(Decimal(report['totals']['confirmed_expenses']),
            Decimal(run['calculation']['net_minor']-run['calculation']['net_deductions_minor'])/100)
        annual_details=deepcopy(data['annual_basis']['details'])
        annual_details.update(as_of_date='2026-11-01',current_calculation_case_ref=None,
            payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(payment)])
        proposal=dict(employee_id=data['employee']['id'],employee_revision=data['employee']['revision'],
            kind='annual_basis',details=annual_details,source_file_ids=[data['file']['id']])
        annual_preview=self.call('POST','/business/payroll/annual-facts/preview',proposal).json
        annual_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=annual_preview['preview_hash'])
        annual=self.call('POST','/business/payroll/annual-facts',annual_command).json
        self.assertEqual(annual['plan']['earlier_other_taxable_minor'],50000)
        self.assertEqual(len(annual['plan']['projection']['prior_one_offs']),1)
        self.assertEqual(annual['sources']['payroll_runs'][0]['projection_format'],'source5_annual_reference_v1')
        self.call('GET','/business/payroll/annual-facts/'+annual['id'],token=data['tech'],status=403)
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json
        for secret in ('settlement_review','remittance_observation',run['settlement_transition']['settlement_review']['evidence_ref']['id']):
            self.assertNotIn(secret,str(own))
        self.call('GET','/business/payroll/runs/'+run['id'],token=data['tech'],status=403)
        self.call('GET','/business/payroll/account-records/'+payment['id'],token=data['tech'],status=403)
        grant=self.call('POST','/business/offline/access/v2',{},status=201).json
        origin=grant['binding']['instance_id']+':'+grant['binding']['account_id']
        self.call('GET','/business/payroll/runs/'+run['id'],token=grant['token'],offline_origin=origin,status=403)
        self.assertEqual(self.call('POST','/business/payroll/runs',command).json,run)
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner,command),run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner,payment_command),payment)
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner,annual_command),annual)
                self.assertEqual(PayrollAnnualBasis(restored).resolve(self.owner,data['employee']['id'],reference(annual)),annual)
                self.assertEqual(PayrollCash(restored).confirm(self.owner,cash_command),batch)
                self.assertEqual(Payroll(restored).export(self.owner,old['id'],'pdf',revision='1')[0],old_pdf)
                self.assertEqual(EuerAccounting(restored).report(self.owner,2026)['totals'],report['totals'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()

    def test_two_actual_finalize_writers_accept_one_correction_and_one_claim_revision(self):
        data=self.workflow();_,_,command=self.correction(data);barrier=threading.Barrier(2)
        def apply(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return Payroll(office).finalize(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(results[0]['revision'],2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_multiple_consumptions').fetchone()[0],2)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_already_paid_full_tax_blocks_positive_net_without_changing_originals(self):
        data=self.workflow(money=True);command=self.remittance_command(data)
        paid=self.call('POST','/business/payroll/cash/batches',command,status=201).json
        self.forecast(data,1000000);case=self.save_case(data,data['case'])
        inputs=dict(employee_id=data['employee']['id'],source_schema_version=5,
            multiple_one_off_case_ref=reference(case),settlement_review=self.review(data))
        self.call('POST','/business/payroll/preview',inputs,status=409)
        self.assertEqual(self.call('POST','/business/payroll/runs',data['run_command']).json,data['run'])
        self.assertEqual(self.call('POST','/business/payroll/cash/batches',command,status=201).json,paid)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_multiple_consumptions').fetchone()[0],1)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_concurrent_actual_tax_remittance_and_net_correction_cannot_both_commit(self):
        data=self.workflow(money=True);cash_command=self.remittance_command(data)
        _,_,run_command=self.correction(data);barrier=threading.Barrier(2)
        def apply(kind):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                try:
                    result=(Payroll(office).finalize(self.owner,run_command) if kind=='run'
                        else PayrollCash(office).confirm(self.owner,cash_command))
                    return kind,'accepted',result
                except Problem as error:
                    self.assertEqual(error.status,409)
                    return kind,'rejected',error.status
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,('run','tax')))
        self.assertEqual(sorted(result[1] for result in results),['accepted','rejected'])
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__=='__main__':unittest.main()
