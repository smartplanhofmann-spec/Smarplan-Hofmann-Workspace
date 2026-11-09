"""Canonical factor period evidence, run/statement/ledger and original replay."""
import json
import unittest
from unittest.mock import patch

import business_schema
from business_payroll_facts import validate_integrity as validate_facts
from business_payroll_statements import PayrollStatements
from payroll_factor_periods_2026 import FACTOR_PERIOD_RULE_VERSION,FACTOR_PERIOD_SCOPE
from payroll_periods_2026 import build_period_plan
import test_business_payroll_periods as periods


class FactorPeriodWorkflow(unittest.TestCase):
    def setUp(self):
        self.base=periods.PayrollPeriodWorkflowTests('runTest');self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.f=self.base.f
        self.base.regular(tax_class=4,special_cases=['tax_factor'],tax_factor='0.753')

    def run_case(self):
        f=self.f;fact,body,preview=f.period()
        inputs=periods.inputs(f.employee['id'],fact)
        command=periods.command(f.payroll,f.owner,inputs)
        run=f.payroll.finalize(f.owner,command)
        return fact,command,run

    def test_canonical_source_run_statement_ledger_and_exact_original(self):
        f=self.f;fact,command,run=self.run_case()
        self.assertEqual(fact['plan']['rule_version'],FACTOR_PERIOD_RULE_VERSION)
        self.assertEqual(run['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        self.assertEqual(run['source']['period_case'],fact)
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(run['calculation']['gross_minor'],274194)
        self.assertEqual(run['calculation']['tax_parameters']['tax_factor'],'0.753')
        pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        self.assertIn(b'0.753',pdf);self.assertIn(b'Zeitnachweis',pdf)
        statement=PayrollStatements(f.office).get(f.owner,run['id'])['statement']
        self.assertEqual(statement['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        self.assertEqual(statement['period_summary']['tax_periods'][0]['tax_days'],17)
        self.assertNotIn('source_file',json.dumps(statement));self.assertNotIn('verification_note',json.dumps(statement))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['totals']['net_minor'],run['calculation']['net_minor'])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_historical_v4_blocked_factor_case_keeps_its_original_plan(self):
        f=self.f
        with patch('business_payroll_facts.build_plan',side_effect=lambda snapshot,**_:build_period_plan(snapshot)):
            fact,body,preview=f.period()
        self.assertFalse(fact['plan']['can_calculate'])
        self.assertEqual(f.api.get(f.owner,fact['id']),fact)
        self.assertTrue(validate_facts(f.office))
        original=f.api.resolve_period_case(f.owner,f.employee['id'],periods.reference(fact),fresh=False)
        self.assertEqual(original,fact)
        self.assertEqual(f.payroll.preview(f.owner,periods.inputs(f.employee['id'],fact))['calculation']['rule_version'],'de_2026_periods_pap_v4')

    def test_revoked_rights_and_paused_module_cannot_replay_as_new_action(self):
        f=self.f;fact,command,run=self.run_case()
        f.problem(403,lambda:f.payroll.get(f.technician,'run',run['id']))
        own=PayrollStatements(f.office).get(f.technician,run['id'])['statement']
        self.assertEqual(own['employee_id'],f.employee['id'])
        self.assertNotIn('verification_note',json.dumps(own))
        f.pause();self.assertEqual(f.payroll.finalize(f.owner,command),run)
        f.problem(423,lambda:f.payroll.finalize(f.owner,dict(command,request_id=periods.rid())))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def correct(self,fact,run):
        f=self.f;old=f.data['profile']
        f.data['profile']=f.payroll.save_profile(f.owner,dict(request_id=periods.rid(),
            employee_id=f.employee['id'],id=old['id'],revision=old['revision'],
            profile=dict(old['profile'],tax_factor='0.900'),source_file_id=f.data['file']['id'],
            confirmed=True,correction_reason='Synthetic corrected actual ELStAM factor'))
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-15',employment_to=None))
        details=f.period_details(fact['sources']['employment_terms'])
        preview=f.api.preview(f.owner,f.preview_body(details))
        changed=f.api.save(f.owner,f.body('period_case',details,id=fact['id'],revision=fact['revision'],
            preview_hash=preview['preview_hash'],correction_reason='Synthetic explicit updated factor and identity evidence'))
        inputs=periods.inputs(f.employee['id'],changed);run_preview=f.payroll.preview(f.owner,inputs)
        command=periods.command(f.payroll,f.owner,inputs)|dict(id=run['id'],revision=run['revision'],
            correction_reason='Synthetic partial factor payroll correction')
        return changed,run_preview,command,f.payroll.finalize(f.owner,command)

    def test_factor_correction_preserves_paid_original_pdf_and_old_ack(self):
        f=self.f;fact,command,run=self.run_case()
        original_pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        original_json=f.payroll.export(f.owner,run['id'],'json')[0]
        paid,_=f.save_account(f.data,'payment',periods.account_fixture.PayrollAccountTests.payment_details(f,run,f.identity))
        changed,preview,body,corrected=self.correct(fact,run)
        self.assertEqual(corrected['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        self.assertEqual(corrected['delta']['net_minor'],-corrected['delta']['employee_tax_minor'])
        self.assertGreater(corrected['delta']['employee_tax_minor'],0)
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(f.payroll.finalize(f.owner,body),corrected)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf','1')[0],original_pdf)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'json','1')[0],original_json)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_factor_period_is_not_offered_to_unsupported_claim_composition(self):
        from business_payroll_calculation_cases import PayrollCalculationCases
        f=self.f;fact,_,_=self.run_case()
        options=PayrollCalculationCases(f.office,clock=lambda:f.now).sources(f.owner,dict(employee_id=f.employee['id'],month='2026-10'))
        self.assertNotIn(fact['id'],[item['id'] for item in options['facts']])


class FactorPeriodCashFlow(unittest.TestCase):
    def test_actual_net_and_remittances_reach_euer_once_without_private_sources(self):
        from test_business_payroll_cash import PayrollCashTests
        from business_payroll_facts import PayrollFacts,reference
        from core import canonical
        c=PayrollCashTests('runTest');c.setUp();self.addCleanup(c.doCleanups);f=c.f
        f.employee=f.call(f.planning,'save_employee',f.owner,dict(request_id=periods.rid(),id=f.employee['id'],
            revision=f.employee['revision'],employment_from='2026-10-15',employment_to=None))
        data=f.case('regular',500000,tax_class=4,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,special_cases=['tax_factor'],tax_factor='0.753')
        identity,_=f.save_account(data,'identity',f.identity_details(data,employment_from='2026-10-15',employment_to=None))
        api=PayrollFacts(f.office,clock=lambda:f.now)
        common=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],revision=0,
            status='active',confirmed=True,source_file_ids=[data['file']['id']])
        terms=api.save(f.owner,dict(common,request_id=periods.rid(),kind='employment_terms',details=dict(
            employment_from='2026-10-15',employment_to=None,agreement_refs=[reference(data['agreement'])],
            proration_method='calendar_days_actual',reason='Synthetic actual factor partial contract')))
        details=dict(month='2026-10',preparation_ref=reference(data['preparation']),employment_terms_ref=reference(terms),
            work_schedule_ref=None,profile_refs=[reference(data['profile'])],identity_refs=[reference(identity)],
            tax_treatment='domestic_running_wages',entitlement_decisions=[],verification_note='Synthetic explicit source review')
        preview=api.preview(f.owner,dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],
            details=details,source_file_ids=common['source_file_ids']))
        fact=api.save(f.owner,dict(common,request_id=periods.rid(),kind='period_case',details=details,preview_hash=preview['preview_hash']))
        run=f.payroll.finalize(f.owner,periods.command(f.payroll,f.owner,periods.inputs(f.employee['id'],fact)))
        self.assertEqual(run['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        paid,_=f.save_account(data,'payment',f.payment_details(run,identity))
        net=c.import_cash(c.body(paid));c.post('payroll_cash',c.payload(net))
        remittance=c.import_cash(c.remittance(data,run,paid));c.post('payroll_cash',c.payload(remittance))
        expected=run['calculation']['employer_total_excluding_accident_insurance_minor']
        self.assertEqual(c.euer.report(f.owner,2026)['totals']['confirmed_expenses'],f'{expected//100}.{expected%100:02d}')
        self.assertEqual(c.euer.report(f.owner,2026)['totals']['confirmed_input_vat'],'0.00')
        self.assertNotIn('tax_factor',canonical(net['public_source']))
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
