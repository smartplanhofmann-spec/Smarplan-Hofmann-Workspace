"""Actual V15 run, original payment/cash/EÜR chain and rollback guards."""
from copy import deepcopy
from decimal import Decimal
import unittest
from unittest.mock import patch

from core import Problem,canonical
import business_schema
from business_payroll_facts import reference
from test_business_payroll import rid
import test_business_payroll_factor_oneoff_cases as originals
import test_business_payroll_oneoff_runs as ordinary
import test_business_payroll_calculations as calculation_fixture
import test_business_payroll_periods as period_fixture


class FactorOneoffRunTests(unittest.TestCase):
    command=ordinary.OneoffRunWorkflow.command
    payment=ordinary.OneoffRunWorkflow.payment
    finance=calculation_fixture.CalculationPayrollWorkflow.finance

    def setUp(self):
        self.fixture=originals.FactorOneoffCaseTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.source=self.fixture.source;self.case,self.case_body,_=self.fixture.saved()

    def test_actual_run_payment_cash_euer_and_original_receipts(self):
        f=self.f;command=self.command(self.case);run=f.payroll.finalize(f.owner,command)
        self.assertEqual('regular_standard_factor_claims_oneoff',run['calculation']['scope'])
        self.assertEqual(self.case['plan'],run['calculation']);self.assertEqual(run,f.payroll.finalize(f.owner,command))
        self.assertEqual(self.source['running_calculation_case'],run['source']['calculation_case'])
        self.assertGreater(run['calculation']['one_off_details']['tax']['STS'],0)
        self.assertGreater(run['calculation']['one_off_details']['tax']['SOLZS'],0)
        self.assertIn(b'Sonstiger Bezug',f.payroll.export(f.owner,run['id'],'pdf')[0])
        payment,payment_command=self.payment(run);self.assertEqual(payment,f.account_api().save(f.owner,payment_command))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(reference(self.case),ledger['months'][9]['source_refs']['one_off_case'])
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        finance=self.finance();net=finance.import_cash(finance.body(payment));remittance=finance.import_cash(finance.remittance(f.data,run,payment))
        out=sum(int(Decimal(value['public_source']['cash_movements'][0]['amount'])*100) for value in (net,remittance))
        self.assertEqual(run['calculation']['employer_total_excluding_accident_insurance_minor'],out)
        entries=[finance.post('payroll_cash',finance.payload(batch)) for batch in (net,remittance)]
        report=finance.euer.report(f.owner,2026);self.assertEqual(Decimal(out)/100,Decimal(report['totals']['confirmed_expenses']))
        public=canonical(dict(net=net['public_source'],remittance=remittance['public_source'],entries=entries,report=report))
        for value in (f.employee['id'],self.case['id'],self.source['one_off_earning']['id'],self.source['current_annual_basis']['id'],self.source['annual_tax_forecast']['id'],self.case['details']['verification_note']):self.assertNotIn(value,public)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_claim_consumption_failure_rolls_back_run_and_receipt(self):
        f=self.f;command=self.command(self.case);before=[dict(row) for row in f.office.db.execute('SELECT * FROM business_payroll_requests')]
        with patch('business_payroll_oneoff_cases.record_run_consumption',side_effect=Problem(409,'Controlled V15 atomic reservation failure')):
            f.problem(409,lambda:f.payroll.finalize(f.owner,command))
        self.assertEqual([],f.payroll._all('run',f.employee['id']));self.assertEqual(before,[dict(row) for row in f.office.db.execute('SELECT * FROM business_payroll_requests')])
        run=f.payroll.finalize(f.owner,command);self.assertEqual(run,f.payroll.finalize(f.owner,command))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_paid_running_original_only_adds_actual_bonus_difference(self):
        f=self.f;running=self.source['running_calculation_case'];inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(running))
        old=f.payroll.finalize(f.owner,period_fixture.command(f.payroll,f.owner,inputs))
        original_part=dict(paid_on='2026-10-31',amount_minor=old['calculation']['payout_minor'],payment_reference='SYN-V12-ACTUAL-ORIGINAL')
        from test_business_payroll_accounts import PayrollAccountTests
        old_payment,_=f.save_account(f.data,'payment',PayrollAccountTests.payment_details(f,old,f.identity,payments=[original_part]))
        finance=self.finance();first=finance.import_cash(finance.body(old_payment))
        current=f.payroll.finalize(f.owner,self.command(self.case,id=old['id'],revision=1,correction_reason='Actual separately evidenced factor bonus added'))
        extra=current['calculation']['payout_minor']-old['calculation']['payout_minor'];self.assertGreater(extra,0)
        f.problem(409,lambda:self.payment(current))
        payment,_=self.payment(current,payments=[original_part,dict(paid_on='2026-10-31',amount_minor=extra,payment_reference='SYN-V15-ONLY-ACTUAL-BONUS')])
        f.problem(409,lambda:finance.api.preview(f.owner,finance.body(payment)))
        body=finance.body(payment);body['sources'][0]['payment_indexes']=[1];last=finance.import_cash(body)
        self.assertEqual(current['calculation']['payout_minor'],sum(int(Decimal(value['public_source']['cash_movements'][0]['amount'])*100) for value in (first,last)))
        self.assertEqual(first['public_source'],finance.api.get(f.owner,first['id'])['public_source'])
        self.assertEqual(old,f.payroll.get(f.owner,'run',old['id'],history=True)['items'][0])
        self.assertEqual(1,len(f.payroll._all('run',f.employee['id'])))
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
