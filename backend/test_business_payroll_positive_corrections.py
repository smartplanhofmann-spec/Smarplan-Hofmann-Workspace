"""Real accepted same-gross Source5 corrections, cumulative net and originals."""
from copy import deepcopy
import unittest
import base64

from business_payroll_facts import reference
from test_business_payroll import rid
import test_business_payroll_accounts as accounts_fixture
import test_business_payroll_calculations as calculation_fixture
import test_business_payroll_multiple as original
import business_schema
from core import Problem,canonical


class PositiveCorrectionFixture(unittest.TestCase):
    def setUp(self):
        self.m=original.MultipleWorkflow('runTest');self.m.setUp();self.addCleanup(self.m.doCleanups)
        self.f=self.m.f;self.case=None;self.run=None;self.payment=None

    def forecast(self,amount):
        f=self.f
        document=f.hr.upload(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],purpose='personnel',owner_visible=False,
            filename='previous-employer-'+str(amount)+'.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(('%PDF-1.4\nSynthetic previous-employer certificate '+str(amount)+'\n%%EOF').encode()).decode()))
        old=self.m.source['annual_tax_forecasts'][0]['annual_tax_forecast'];details=deepcopy(old['details'])
        details['previous_employers']=[dict(employer_name='Previous synthetic employer',employer_tax_number='111/222/33333',
            start='2026-01-01',end='2026-09-30',running_taxable_minor=amount,other_paid_minor=0,
            evidence_ref=dict(id=document['id'],revision=1,content_hash=document['content_hash']))]
        details['no_previous_employer_ref']=None
        proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='annual_tax_forecast',
            details=details,source_file_ids=[f.original['id'],document['id']])
        preview=f.annual.preview(f.owner,proposal)
        command=proposal|dict(request_id=rid(),revision=old['revision'],status='active',confirmed=True,
            preview_hash=preview['preview_hash'],id=old['id'],correction_reason='Corrected exact prior-employer certificate')
        updated=f.annual.save(f.owner,command)
        self.m.source['annual_tax_forecasts'][0]['annual_tax_forecast']=updated
        return updated

    def first(self,*,cash=False):
        self.forecast(2000000);self.case,self.case_command=self.m.case()
        self.run_input=dict(source_schema_version=5,employee_id=self.f.employee['id'],multiple_one_off_case_ref=reference(self.case))
        self.preview=self.f.payroll.preview(self.f.owner,self.run_input)
        self.command=self.m.run_command(self.case);self.run=self.f.payroll.finalize(self.f.owner,self.command)
        running=self.run['calculation']['running_calculation'];a=running['net_minor']-running['net_deductions_minor']
        b=self.run['calculation']['net_minor']-self.run['calculation']['net_deductions_minor']-a
        event=self.run['calculation']['multiple_one_off_details']['receipt_events'][0]
        parts=[dict(paid_on='2026-10-30',amount_minor=a,payment_reference='SOURCE5-ORIGINAL-RUNNING'),
            dict(paid_on=event['receipt_date'],amount_minor=b,payment_reference='SOURCE5-ORIGINAL-BONUS')]
        details=accounts_fixture.PayrollAccountTests.payment_details(self.f,self.run,self.f.identity,payments=parts)
        details.update(payment_source_schema_version=1,prior_payment_ref=None,settlement_allocations=[
            dict(payment_index=0,running_minor=a,one_off_allocations=[]),
            dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=event['event_key'],net_minor=b)])])
        self.payment,self.payment_command=self.f.save_account(self.f.data,'payment',details)
        if cash:
            self.finance=calculation_fixture.CalculationPayrollWorkflow.finance(self.m)
            self.net_batch=self.finance.import_cash(self.finance.body(self.payment))
        return self.run,self.payment

    def correction_input(self,amount=1000000):
        self.forecast(amount)
        self.case,self.case_command=self.m.case(id=self.case['id'],revision=self.case['revision'],correction_reason='Same gross event, corrected evidenced annual forecast')
        inputs=dict(source_schema_version=5,employee_id=self.f.employee['id'],multiple_one_off_case_ref=reference(self.case),
            settlement_review=dict(schema_version=1,payments_complete=True,remittances_complete=True,evidence_ref=self.f.original))
        self.run_input=inputs
        return inputs

    def correction(self,amount=1000000):
        from test_business_payroll_periods import command
        inputs=self.correction_input(amount)
        self.preview=self.f.payroll.preview(self.f.owner,inputs)
        self.command=command(self.f.payroll,self.f.owner,inputs)|dict(id=self.run['id'],revision=self.run['revision'],correction_reason='Positive net due to corrected actual annual source')
        self.run=self.f.payroll.finalize(self.f.owner,self.command)
        return self.run

    def payment_details(self,reference_text='SOURCE5-CORRECTED-BONUS'):
        old=self.payment;run=self.run;t=run['settlement_transition'];parts=deepcopy(old['details']['payments'])
        parts.append(dict(paid_on=t['receipt_date'],amount_minor=t['additional_net_minor'],payment_reference=reference_text))
        allocations=deepcopy(old['details']['settlement_allocations'])
        allocations.append(dict(payment_index=len(parts)-1,running_minor=0,one_off_allocations=[dict(event_key=t['event_key'],net_minor=t['additional_net_minor'])]))
        details=accounts_fixture.PayrollAccountTests.payment_details(self.f,run,self.f.identity,payments=parts)
        details.update(payment_source_schema_version=2,prior_payment_ref=reference(old),settlement_allocations=allocations)
        return details

    def pay(self,reference_text='SOURCE5-CORRECTED-BONUS'):
        details=self.payment_details(reference_text)
        self.payment,self.payment_command=self.f.save_account(self.f.data,'payment',details)
        return self.payment


class PositiveCorrectionWorkflow(PositiveCorrectionFixture):
    def test_actual_positive_net_preserves_all_originals_and_only_new_cash(self):
        old,paid=self.first(cash=True);old_pdf=self.f.payroll.export(self.f.owner,old['id'],'pdf')[0]
        run=self.correction();self.assertEqual(run['settlement_transition']['additional_net_minor'],3900)
        with self.assertRaises(Problem):
            self.f.save_account(self.f.data,'payment',paid['details'],id=paid['id'],revision=paid['revision'],correction_reason='Cannot change consumed payment prefix')
        payment=self.pay();self.assertEqual(payment['details']['payments'][:2],paid['details']['payments'])
        self.assertEqual(payment['details']['settlement_allocations'][:2],paid['details']['settlement_allocations'])
        self.assertEqual(payment['sources']['single_payment_plan']['new_payment_indexes'],[2])
        body=self.finance.body(payment);body['sources'][0]['payment_indexes']=[2]
        extra=self.finance.import_cash(body)
        self.assertEqual(extra['public_source']['cash_movements'][0]['amount'],format(run['settlement_transition']['additional_net_minor']/100,'.2f'))
        self.assertEqual(self.f.payroll.finalize(self.f.owner,self.command),run)
        self.assertEqual(self.f.payroll.export(self.f.owner,old['id'],'pdf',revision='1')[0],old_pdf)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_review_is_not_silently_accepted_in_initial_or_unpaid_branch(self):
        case,_=self.m.case();inputs=dict(source_schema_version=5,employee_id=self.f.employee['id'],multiple_one_off_case_ref=reference(case))
        review=dict(schema_version=1,payments_complete=True,remittances_complete=True,evidence_ref=self.f.original)
        with self.assertRaises(Problem):self.f.payroll.preview(self.f.owner,dict(inputs,settlement_review=review))
        preview=self.f.payroll.preview(self.f.owner,inputs)
        self.assertNotIn('settlement_transition',preview)
        self.assertNotIn('settlement_review',preview['source']['input'])
        self.f.payroll.finalize(self.f.owner,self.m.run_command(case))
        with self.assertRaises(Problem):self.f.payroll.preview(self.f.owner,dict(inputs,settlement_review=review))

    def test_pure_v2_plan_rejects_changed_sources_prefix_and_false_hashes(self):
        from payroll_multiple_corrections import build_positive_payment_plan
        from business_personnel_workflow import _sha
        old,paid=self.first();run=self.correction();details=self.payment_details()
        def build(r=run,d=details,p=paid):
            return build_positive_payment_plan(r,payments=d['payments'],allocations=d['settlement_allocations'],
                as_of='2026-11-03',prior_settlement=dict(run=old,payment=p))
        plan=build();self.assertEqual(plan['additional_net_minor'],3900)
        self.assertEqual(plan['payments'][:2],paid['details']['payments'])
        for kind in ('transition','total','review','date','prior_plan','prefix','wrong_run'):
            r,d,p=deepcopy(run),deepcopy(details),deepcopy(paid)
            if kind=='transition':r['settlement_transition']['transition_hash']='0'*64
            elif kind=='total':
                r['settlement_transition']['total_net_minor']+=1;r['settlement_transition']['additional_net_minor']+=1
                r['settlement_transition']['transition_hash']=_sha({k:v for k,v in r['settlement_transition'].items() if k!='transition_hash'})
            elif kind=='review':r['settlement_transition']['settlement_review']['remittances_complete']=1
            elif kind=='date':d['payments'][-1]['paid_on']='2026-11-01'
            elif kind=='prior_plan':p['sources']['single_payment_plan']['plan_hash']='0'*64
            elif kind=='prefix':d['settlement_allocations'][1]['one_off_allocations']=[]
            else:r['id']='0'*32
            with self.subTest(kind=kind),self.assertRaises(Problem):build(r,d,p)

    def test_superseded_complete_review_blocks_new_payment_but_keeps_run_replay(self):
        self.first();run=self.correction();command=deepcopy(self.command)
        self.f.hr.upload(self.f.owner,dict(request_id=rid(),employee_id=self.f.employee['id'],purpose='personnel',owner_visible=False,
            filename='new-settlement-review.pdf',media_type='application/pdf',supersedes=self.f.original['id'],
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic superseding actual-settlement review\n%%EOF').decode()))
        with self.assertRaises(Problem):self.pay()
        self.assertEqual(self.f.payroll.finalize(self.f.owner,command),run)

    def test_unpaid_intermediate_revision_is_not_an_actual_payment(self):
        original,paid=self.first();unpaid=self.correction(1000000)
        latest=self.correction(1500000);self.assertEqual(latest['delta']['net_minor'],-2900)
        transition=latest['settlement_transition']
        self.assertEqual(transition['previous_run_ref'],reference(unpaid))
        self.assertEqual(transition['prior_run_ref'],reference(original))
        self.assertEqual(transition['prior_payment_ref'],reference(paid))
        self.assertEqual(transition['additional_net_minor'],1000)
        payment=self.pay();self.assertEqual(payment['details']['payments'][:2],paid['details']['payments'])
        self.assertEqual(payment['details']['payments'][-1]['amount_minor'],1000)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_second_positive_correction_retains_the_original_cumulative_prefix(self):
        self.first();self.correction(1500000);first=self.pay();self.correction(1000000);second=self.pay('SOURCE5-SECOND-CORRECTED-BONUS')
        self.assertEqual(second['details']['payments'][:3],first['details']['payments'])
        self.assertEqual(second['sources']['single_payment_plan']['preserved_prior_payment_indexes'],[0,1,2])
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_all_actual_settlements_need_explicit_complete_review_and_original(self):
        old,paid=self.first();inputs=self.correction_input();original=canonical(old)
        for field in ('missing','payments_complete','remittances_complete','schema_version','evidence_ref'):
            value=deepcopy(inputs)
            if field=='missing':value.pop('settlement_review')
            elif field in ('payments_complete','remittances_complete'):value['settlement_review'][field]=False
            elif field=='schema_version':value['settlement_review'][field]=True
            else:value['settlement_review']['evidence_ref']['content_hash']='0'*64
            with self.subTest(field=field),self.assertRaises(Problem):self.f.payroll.preview(self.f.owner,value)
        self.assertEqual(canonical(self.f.payroll.get(self.f.owner,'run',old['id'])),original)
        self.assertEqual(self.f.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],1)

    def test_prior_actual_remittance_over_corrected_debt_blocks_positive_run(self):
        old,paid=self.first(cash=True)
        self.finance.import_cash(self.finance.remittance(self.f.data,old,paid))
        inputs=self.correction_input()
        with self.assertRaises(Problem) as caught:self.f.payroll.preview(self.f.owner,inputs)
        self.assertEqual(caught.exception.status,409)
        self.assertIn('abgeführte',caught.exception.message)
        self.assertEqual(self.f.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],1)

    def test_changed_prefix_later_payment_or_old_version_cannot_create_payment(self):
        self.first();self.correction();details=self.payment_details()
        for change in ('prefix','allocation','later','amount','version','prior'):
            value=deepcopy(details)
            if change=='prefix':value['payments'][0]['payment_reference']='Replaced original payment'
            elif change=='allocation':value['settlement_allocations'][1]['running_minor']=1
            elif change=='later':value['payments'][-1]['paid_on']='2026-11-01'
            elif change=='amount':value['payments'][-1]['amount_minor']+=1
            elif change=='version':value['payment_source_schema_version']=1
            else:value['prior_payment_ref']['content_hash']='0'*64
            with self.subTest(change=change),self.assertRaises(Problem):self.f.save_account(self.f.data,'payment',value)
        accepted=self.pay();self.assertEqual(accepted['details'],details)


if __name__=='__main__':unittest.main()
