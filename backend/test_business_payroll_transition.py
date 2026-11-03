"""Midijob election, immutable revisions, source freshness and actual EÜR cash."""
import json
import unittest

from core import canonical
from business_payroll import validate_integrity,dispatch
from business_personnel_workflow import _sha
import test_business_payroll as monthly
from test_business_planning import BusinessFixture,rid
from test_payroll_transition_2026 import assessment


class TransitionWorkflowTests(BusinessFixture,unittest.TestCase):
    setUp=monthly.PayrollWorkflowTests.setUp
    case=monthly.PayrollWorkflowTests.case
    command=monthly.PayrollWorkflowTests.command

    def midijob(self):
        return self.case('regular',100000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,
            tax_addition_monthly_minor=0,transition_assessment=assessment())

    def test_confirmed_actual_sources_pdf_json_and_yearly_exports(self):
        data=self.midijob();command=self.command(data)
        run=self.payroll.finalize(self.owner,command)
        self.assertEqual(self.payroll.finalize(self.owner,command),run)
        self.assertEqual(run['calculation']['net_minor'],87467)
        self.assertEqual(run['accepted_scope'],'regular_transition_monthly')
        self.assertEqual(run['source']['profile']['source_file']['sha256'],data['file']['sha256'])
        pdf,_=self.payroll.export(self.owner,run['id'],'pdf')
        self.assertEqual(_sha(pdf),run['pdf_sha256']);self.assertIn(b'Midijob',pdf)
        source,_=self.payroll.export(self.owner,run['id'],'json');self.assertEqual(json.loads(source),run)
        preview=self.payroll.ledger(self.owner,dict(employee_id=self.employee['id'],year='2026'))
        ledger=preview['ledger'];self.assertEqual(ledger['totals']['net_minor'],87467)
        self.assertEqual(ledger['months'][9]['calculation']['transition']['employee_assessment_minor'],56836)
        for format_ in ('pdf','csv','json'):
            output,_=self.payroll.export_ledger(self.owner,dict(employee_id=self.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),format_)
            self.assertEqual(_sha(output),preview['exports'][format_]['sha256'])
            self.assertIn(b'de_2026_transition_monthly_pap_v3',output)
        self.assertTrue(validate_integrity(self.office))
        rules=dispatch(self.office,self.owner,'/payroll/rules','GET',{})[0]
        self.assertEqual(rules['regular_transition_rules']['transition_factor'],'0.6619')

    def test_new_profile_requires_explicit_election_and_forecast_original(self):
        data=self.case('regular',100000,tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        initial=self.payroll.preview(self.owner,data['inputs'])
        self.assertFalse(initial['can_finalize']);self.assertNotIn('transition_assessment',data['profile']['profile'])
        body=dict(request_id=rid(),employee_id=self.employee['id'],id=data['profile']['id'],revision=1,
            profile=data['profile']['profile']|dict(transition_assessment=assessment()),source_file_id=data['file']['id'],
            confirmed=False,correction_reason='Synthetic reviewed transition-area forecast')
        self.problem(400,lambda:self.payroll.save_profile(self.owner,body))
        self.problem(400,lambda:self.payroll.save_profile(self.owner,body|dict(confirmed=True,
            profile=body['profile']|dict(transition_assessment=assessment(assessed_on='2099-01-01')))))
        body['confirmed']=True;updated=self.payroll.save_profile(self.owner,body)
        self.problem(409,lambda:self.payroll.preview(self.owner,data['inputs']))
        data['inputs']['profile_revision']=updated['revision']
        self.assertTrue(self.payroll.preview(self.owner,data['inputs'])['can_finalize'])
        self.assertEqual(self.payroll.get(self.owner,'profile',updated['id'],True)['items'][0],data['profile'])
        self.assertTrue(validate_integrity(self.office))

    def test_tax_fund_correction_replays_old_receipts_and_never_double_counts_year(self):
        data=self.midijob();command=self.command(data);run=self.payroll.finalize(self.owner,command)
        old_json=self.payroll.export(self.owner,run['id'],'json')[0];old_pdf=self.payroll.export(self.owner,run['id'],'pdf')[0]
        changed=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=data['profile']['id'],
            revision=1,profile=data['profile']['profile']|dict(health_additional_percent='3.10',u2_percent='0.37'),
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic verified fund-rate correction'))
        self.assertEqual(self.payroll.finalize(self.owner,command),run)
        data['inputs']['profile_revision']=changed['revision']
        correction=self.payroll.finalize(self.owner,self.command(data,id=run['id'],revision=1,correction_reason='Fund rates corrected from reviewed evidence'))
        self.assertEqual(correction['delta']['employee_social_total_minor'],57)
        self.assertEqual(correction['delta']['net_minor'],-57)
        self.assertEqual(correction['delta']['employee_tax_minor'],0)
        self.assertEqual(self.payroll.export(self.owner,run['id'],'json','1')[0],old_json)
        self.assertEqual(self.payroll.export(self.owner,run['id'],'pdf','1')[0],old_pdf)
        ledger=self.payroll.ledger(self.owner,dict(employee_id=self.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['recorded_months'],1)
        self.assertEqual(ledger['totals']['gross_minor'],100000)
        self.assertEqual(ledger['totals']['net_minor'],87410)
        self.assertEqual(len(ledger['correction_history']),1)
        self.assertTrue(validate_integrity(self.office))

    def test_hourly_actual_pay_can_fluctuate_without_a_new_status(self):
        data=self.midijob()
        agreement=data['agreement']
        self.hr.save_agreement(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=agreement['id'],revision=1,
            effective_from='2026-01-01',employment_kind='regular',pay_basis='hourly',amount_minor=1500,currency='EUR',
            reference_file_id=data['file']['id'],correction_reason='Synthetic documented hourly agreement'))
        from business_time import TimeTracking
        time=TimeTracking(self.office,clock=lambda:self.now)
        common=dict(entry_id=rid(),device_id='synthetic-midijob-hours',project_id=self.project)
        for action,sequence,at in (('start',1,'08:00:00'),('stop',2,'09:00:00')):
            time.event(self.technician,dict(common,request_id=rid(),action=action,sequence=sequence,revision=sequence-1,
                occurred_at='2026-10-26T'+at+'+01:00'))
        summary=time.summary(self.owner,dict(employee_id=self.employee['id'],**{'from':'2026-10-26','to':'2026-10-26'}))
        time.approve_day(self.owner,'2026-10-26',dict(request_id=rid(),employee_id=self.employee['id'],revision=summary['days'][0]['revision']))
        current=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month='2026-10'))
        prepared=self.hr.close_preparation(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],month='2026-10',
            id=data['preparation']['id'],revision=1,source_hash=current['source_hash'],completeness_confirmed=True,
            correction_reason='Explicit hourly contract and approved actual working time'))
        self.assertEqual(prepared['snapshot']['net_work_seconds'],3600)
        data['inputs'].update(preparation_revision=prepared['revision'],gross_minor=1500)
        result=self.payroll.preview(self.owner,data['inputs'])['calculation']
        self.assertTrue(result['payroll_calculation_complete'])
        self.assertEqual(result['transition']['regime'],'below_or_at_lower_limit')
        self.payroll.finalize(self.owner,self.command(data))
        wrong=self.payroll.preview(self.owner,data['inputs']|dict(gross_minor=1501))
        self.assertIn('wage_source_mismatch',[item['code'] for item in wrong['calculation']['blockers']])
        self.assertTrue(validate_integrity(self.office))

    def test_new_election_can_correct_v2_with_old_history_exact(self):
        data=self.case('regular',500000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        command=self.command(data);old=self.payroll.finalize(self.owner,command)
        old_json=self.payroll.export(self.owner,old['id'],'json')[0];old_pdf=self.payroll.export(self.owner,old['id'],'pdf')[0]
        self.hr.save_agreement(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=data['agreement']['id'],revision=1,
            effective_from='2026-01-01',employment_kind='regular',pay_basis='monthly',amount_minor=100000,currency='EUR',
            reference_file_id=data['file']['id'],correction_reason='Synthetic corrected wage evidence'))
        changed=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=data['profile']['id'],revision=1,
            profile=data['profile']['profile']|dict(regular_annual_gross_minor=1200000,transition_assessment=assessment()),
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic confirmed prospective status evidence'))
        self.problem(409,lambda:self.payroll.preview(self.owner,data['inputs']))
        hr_preview=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month='2026-10'))
        prepared=self.hr.close_preparation(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],month='2026-10',id=data['preparation']['id'],
            revision=1,source_hash=hr_preview['source_hash'],completeness_confirmed=True,correction_reason='Revised original monthly evidence'))
        data['inputs'].update(profile_revision=changed['revision'],preparation_revision=prepared['revision'],gross_minor=100000)
        updated=self.payroll.finalize(self.owner,self.command(data,id=old['id'],revision=1,correction_reason='Explicit new rule election on corrected sources'))
        self.assertEqual(updated['calculation']['net_minor'],87467)
        self.assertEqual(self.payroll.finalize(self.owner,command),old)
        self.assertEqual(self.payroll.export(self.owner,old['id'],'json','1')[0],old_json)
        self.assertEqual(self.payroll.export(self.owner,old['id'],'pdf','1')[0],old_pdf)
        self.assertTrue(validate_integrity(self.office))


class TransitionCashCompatibilityTests(unittest.TestCase):
    def test_evidenced_external_midijob_month_recalculates_and_prevents_duplicate_local_run(self):
        from test_business_payroll_accounts import PayrollAccountTests
        from business_payroll_accounts import validate_integrity as validate_accounts
        from core import Problem
        f=PayrollAccountTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        data=f.case('regular',100000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,
            tax_addition_monthly_minor=0,transition_assessment=assessment())
        identity,_=f.save_account(data,'identity',f.identity_details(data))
        details=dict(month='2026-10',profile_id=data['profile']['id'],profile_revision=1,
            identity_id=identity['id'],identity_revision=1,gross_minor=100000,expected_net_minor=87467,
            expected_employee_tax_minor=0,expected_employee_social_total_minor=12533,expected_employer_social_total_minor=24105,
            expected_employer_total_minor=126403,payments=[dict(paid_on='2026-10-31',amount_minor=87467,payment_reference='SYN-MIDI-PRIOR-001')],
            tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True,status='active')
        saved,body=f.save_account(data,'carryover',details)
        self.assertEqual(f.account_api().save(f.owner,body),saved)
        self.assertEqual(saved['sources']['calculation']['scope'],'regular_transition_monthly')
        self.assertEqual(f.ledger()['totals']['net_minor'],87467)
        with self.assertRaises(Problem) as error:f.payroll.finalize(f.owner,f.command(data))
        self.assertEqual(error.exception.status,409)
        self.assertTrue(validate_accounts(f.office));self.assertTrue(validate_integrity(f.office))

    def test_actual_midijob_net_and_remittances_use_existing_cash_and_euer_once(self):
        from test_business_payroll_cash import PayrollCashTests
        from business_payroll_cash import validate_integrity as validate_cash
        from business_accounting_euer import validate_integrity as validate_euer
        f=PayrollCashTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        data=f.f.case('regular',100000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,
            tax_addition_monthly_minor=0,transition_assessment=assessment())
        run=f.f.payroll.finalize(f.owner,f.f.command(data))
        identity,_=f.f.save_account(data,'identity',f.f.identity_details(data))
        paid,_=f.f.save_account(data,'payment',f.f.payment_details(run,identity))
        self.assertTrue(f.f.ledger()['statutory_wage_account_complete'])
        self.assertEqual(f.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'0.00')
        body=f.body(paid);command=f.command(body);net=f.api.confirm(f.owner,command)
        self.assertEqual(f.api.confirm(f.owner,command),net)
        f.post('payroll_cash',f.payload(net))
        remittance=f.import_cash(f.remittance(data,run,paid));f.post('payroll_cash',f.payload(remittance))
        report=f.euer.report(f.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'1264.03')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(len(report['cash_movements']),2)
        changed=f.f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.f.employee['id'],
            id=data['profile']['id'],revision=1,profile=data['profile']['profile']|dict(health_additional_percent='3.10'),
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic corrected insurer evidence after actual payment'))
        data['inputs']['profile_revision']=changed['revision']
        corrected=f.f.payroll.finalize(f.owner,f.f.command(data,id=run['id'],revision=1,
            correction_reason='Recalculated contribution does not rewrite actual prior cash'))
        self.assertEqual(corrected['calculation']['net_minor'],87410)
        after=f.euer.report(f.owner,2026)
        self.assertEqual(after['totals']['confirmed_expenses'],'1264.03')
        self.assertEqual(after['cash_movements'],report['cash_movements'])
        self.assertTrue(validate_cash(f.office));self.assertTrue(validate_euer(f.office))
        self.assertTrue(validate_integrity(f.office))


if __name__=='__main__':unittest.main()
