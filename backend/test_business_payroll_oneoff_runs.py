"""Actual Source4 run, immutable claim consumption and real money ownership."""
from copy import deepcopy
from decimal import Decimal
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_oneoff_cases as cases
from business_payroll_facts import reference
from core import Problem,canonical
from payroll_travel_recording import validate_tax_recording
from test_business_payroll import rid
import test_business_payroll_accounts as account_fixture
import test_business_payroll_calculations as calculation_fixture
import test_business_payroll_oneoff_cases as case_fixture
import test_business_payroll_periods as period_fixture
import test_payroll_oneoff_composition_2026 as composition_fixture


class OneoffRunWorkflow(unittest.TestCase):
    details=case_fixture.OneoffCaseWorkflow.details
    request=case_fixture.OneoffCaseWorkflow.request
    finance=calculation_fixture.CalculationPayrollWorkflow.finance

    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_oneoff_cases' not in names:names+=('business_payroll_oneoff_cases',)
        registry=patch.object(business_schema,'MODULE_NAMES',names);registry.start();self.addCleanup(registry.stop)
        self.c=composition_fixture.OneoffCompositionTests('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.f=self.c.f;self.api=cases.PayrollOneoffCases(self.f.office,clock=lambda:self.f.now)

    def workflow(self,**changes):
        self.source=self.c.source(**changes);body,_=self.request();case=self.api.save(self.f.owner,body)
        return case,body

    def command(self,case,**changes):
        inputs=dict(source_schema_version=4,employee_id=self.f.employee['id'],one_off_case_ref=reference(case))
        return period_fixture.command(self.f.payroll,self.f.owner,inputs)|changes

    def payment(self,run,**changes):
        f=self.f;due=run['calculation']['net_minor']-run['calculation']['net_deductions_minor']
        payment=[dict(paid_on=run['calculation']['one_off_details']['receipt_date'],amount_minor=due,payment_reference='SYN-V6-ACTUAL-NET-001')]
        details=account_fixture.PayrollAccountTests.payment_details(f,run,f.identity,payments=payment)|changes
        return f.save_account(f.data,'payment',details)

    def test_actual_source4_run_account_ledger_pdf_and_original_replay(self):
        f=self.f;case,body=self.workflow();command=self.command(case);run=f.payroll.finalize(f.owner,command)
        self.assertEqual('regular_standard_oneoff',run['calculation']['scope'])
        self.assertEqual(self.source['running_calculation_case'],run['source']['calculation_case'])
        self.assertEqual(case,run['source']['one_off_case'])
        self.assertEqual(case['plan'],run['calculation'])
        self.assertEqual(run,f.payroll.finalize(f.owner,command))
        payment,payment_command=self.payment(run)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(reference(case),ledger['months'][9]['source_refs']['one_off_case'])
        self.assertEqual(50000,ledger['recorded_one_off_payments'][0]['details']['amount_minor'])
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        for kind in ('pdf','csv','json'):
            content,_=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),kind)
            self.assertTrue(content)
        self.assertIn(b'Sonstiger Bezug',f.payroll.export(f.owner,run['id'],'pdf')[0])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        f.problem(400,lambda:f.payroll.preview(f.owner,dict(source_schema_version=4,employee_id=f.employee['id'],one_off_case_ref=reference(case),gross_minor=1)))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_claim_consumption_failure_rolls_back_run_and_receipt(self):
        f=self.f;case,_=self.workflow();command=self.command(case)
        before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_payroll_requests')]
        with patch('business_payroll_oneoff_cases.record_run_consumption',side_effect=Problem(409,'Synthetic atomic claim reservation failure')):
            f.problem(409,lambda:f.payroll.finalize(f.owner,command))
        self.assertEqual([],f.payroll._all('run',f.employee['id']))
        self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_payroll_requests')])
        run=f.payroll.finalize(f.owner,command);self.assertEqual(run,f.payroll.finalize(f.owner,command))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_flat_travel_shift_and_bonus_keep_original_and_true_money(self):
        f=self.f;case,_=self.workflow(flat_travel=True,shifted=True);run=f.payroll.finalize(f.owner,self.command(case))
        calc=run['calculation'];running=calc['running_calculation'];extra=calc['one_off_details']
        self.assertEqual(109,calc['net_deductions_minor']);self.assertEqual(running['net_deductions_minor'],calc['net_deductions_minor'])
        self.assertEqual(109,validate_tax_recording(f.office,run)['statutory_employer_due_minor'])
        self.assertEqual(running['net_minor']+50000-extra['social']['employee_total_minor']-extra['tax']['STS']
            -extra['tax']['SOLZS']-extra['church_tax_minor'],calc['net_minor'])
        payment,_=self.payment(run);finance=self.finance()
        net=finance.import_cash(finance.body(payment));remittance=finance.import_cash(finance.remittance(f.data,run,payment))
        out=sum(int(Decimal(batch['public_source']['cash_movements'][0]['amount'])*100) for batch in (net,remittance))
        self.assertEqual(calc['employer_total_excluding_accident_insurance_minor'],out)
        entries=[finance.post('payroll_cash',finance.payload(batch)) for batch in (net,remittance)]
        report=finance.euer.report(f.owner,2026)
        self.assertEqual(Decimal(out)/100,Decimal(report['totals']['confirmed_expenses']))
        public=canonical(dict(net=net['public_source'],remittance=remittance['public_source'],entries=entries,report=report))
        for value in (f.employee['id'],case['id'],self.source['one_off_earning']['id'],self.source['current_annual_basis']['id'],
                self.source['annual_tax_forecast']['id'],f.original['id'],case['details']['verification_note'],
                self.source['running_calculation_case']['details']['verification_note']):
            self.assertNotIn(value,public)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_actual_receipt_date_is_not_a_free_payment_date_and_cannot_erase_claim(self):
        f=self.f;case,_=self.workflow();run=f.payroll.finalize(f.owner,self.command(case))
        due=run['calculation']['net_minor']-run['calculation']['net_deductions_minor']
        f.problem(409,lambda:self.payment(run,payments=[dict(paid_on='2026-11-02',amount_minor=due,payment_reference='SYN-WRONG-RECEIPT')]))
        running=run['source']['calculation_case']
        old_input=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(running))
        command=period_fixture.command(f.payroll,f.owner,old_input)|dict(id=run['id'],revision=1,correction_reason='Attempted unbound claim removal')
        f.problem(409,lambda:f.payroll.finalize(f.owner,command))
        self.assertEqual(run,f.payroll.get(f.owner,'run',run['id']))

    def test_paid_v5_original_part_is_preserved_and_only_new_bonus_difference_becomes_cash(self):
        f=self.f;case,_=self.workflow();running=case['sources']['calculation_source']['running_calculation_case']
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(running))
        old=f.payroll.finalize(f.owner,period_fixture.command(f.payroll,f.owner,inputs))
        original_part=dict(paid_on='2026-10-31',amount_minor=old['calculation']['payout_minor'],payment_reference='SYN-V5-ORIGINAL-PAID')
        old_payment,_=f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,old,f.identity,payments=[original_part]))
        finance=self.finance();first=finance.import_cash(finance.body(old_payment))
        current=f.payroll.finalize(f.owner,self.command(case,id=old['id'],revision=1,correction_reason='Actual separately evidenced bonus added'))
        extra=current['calculation']['payout_minor']-old['calculation']['payout_minor']
        self.assertGreater(extra,0)
        parts=[original_part,dict(paid_on='2026-10-31',amount_minor=extra,payment_reference='SYN-V6-ONLY-BONUS-DIFFERENCE')]
        # A newly invented combined transfer cannot replace the actual paid part.
        f.problem(409,lambda:self.payment(current))
        new_payment,_=self.payment(current,payments=parts)
        f.problem(409,lambda:finance.api.preview(f.owner,finance.body(new_payment)))
        body=finance.body(new_payment);body['sources'][0]['payment_indexes']=[1]
        last=finance.import_cash(body)
        self.assertEqual(current['calculation']['payout_minor'],sum(int(Decimal(value['public_source']['cash_movements'][0]['amount'])*100) for value in (first,last)))
        self.assertEqual(first['public_source'],finance.api.get(f.owner,first['id'])['public_source'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_paid_v5_part_cannot_be_moved_to_a_different_bonus_receipt_date(self):
        f=self.f;case,_=self.workflow();running=case['sources']['calculation_source']['running_calculation_case']
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(running))
        old=f.payroll.finalize(f.owner,period_fixture.command(f.payroll,f.owner,inputs))
        original_part=dict(paid_on='2026-10-30',amount_minor=old['calculation']['payout_minor'],payment_reference='SYN-V5-ORIGINAL-EARLIER-DAY')
        old_payment,_=f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,old,f.identity,payments=[original_part]))
        finance=self.finance();first=finance.import_cash(finance.body(old_payment))
        current=f.payroll.finalize(f.owner,self.command(case,id=old['id'],revision=1,correction_reason='Actual later bonus; original money immutable'))
        extra=current['calculation']['payout_minor']-old['calculation']['payout_minor']
        bonus=dict(paid_on='2026-10-31',amount_minor=extra,payment_reference='SYN-V6-ACTUAL-LATER-BONUS')
        f.problem(409,lambda:self.payment(current,payments=[original_part,bonus]))
        f.problem(409,lambda:self.payment(current,payments=[original_part|dict(paid_on='2026-10-31'),bonus]))
        self.assertEqual(first['public_source'],finance.api.get(f.owner,first['id'])['public_source'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_missing_actual_consumption_blocks_read_export_payment_and_restore_without_cash(self):
        f=self.f;case,_=self.workflow();command=self.command(case);run=f.payroll.finalize(f.owner,command)
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0])
        f.office.db.execute('DROP TRIGGER '+cases.TABLES[2]+'_delete_guard')
        f.office.db.execute('DELETE FROM '+cases.TABLES[2])
        for action in (lambda:f.payroll.get(f.owner,'run',run['id']),lambda:f.payroll.finalize(f.owner,command),
                       lambda:f.payroll.export(f.owner,run['id'],'pdf'),lambda:self.payment(run),
                       lambda:f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))):
            f.problem(500,action)
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)


if __name__=='__main__':unittest.main()
