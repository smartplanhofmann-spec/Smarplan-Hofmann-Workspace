"""Actual immutable factor periods, original trips and paid reimbursement proofs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from cryptography.fernet import Fernet
from core import Problem, canonical
from business_accounting import Accounting
from business_payroll_calculation_cases import PayrollCalculationCases, validate_integrity
from business_payroll_facts import reference
from business_payroll_statements import PayrollStatements
from business_travel_allowances import TravelAllowances
from online.instance import bind
from online.storage import Storage
from payroll_factor_taxfree_travel_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION, SCOPE, AMOUNTS, calculate_source
from payroll_factor_taxfree_sources import paid_taxfree_source
from payroll_factor_periods_2026 import calculate_factor_period_source
import test_business_payroll_periods as period_fixture
from test_business_payroll_periods import command
import test_business_travel_allowances as travel_fixture
from test_business_planning import rid
from travel_allowance_cash import record_payment


class FactorTravelFixture(unittest.TestCase):
    def setUp(self):
        self.parent = period_fixture.PayrollPeriodWorkflowTests('runTest'); self.parent.setUp()
        self.addCleanup(self.parent.doCleanups); self.f = self.parent.f
        f = self.f
        f.employee = f.call(f.planning, 'save_employee', f.owner, dict(request_id=rid(),
            id=f.employee['id'], revision=f.employee['revision'], employment_from='2026-10-01', employment_to=None))
        self.parent.regular(tax_class=4, special_cases=['tax_factor'], tax_factor='0.753')
        f.identity, _ = f.save_account(f.data, 'identity', f.identity_details(f.data, employment_from='2026-10-01', employment_to=None),
            id=f.identity['id'],revision=f.identity['revision'],correction_reason='Synthetic full-month employment identity')
        terms = f.api.save(f.owner, f.body('employment_terms', f.terms_details() | dict(employment_from='2026-10-01')))
        details = f.period_details(terms)
        preview = f.api.preview(f.owner, f.preview_body(details))
        self.base = f.api.save(f.owner, f.body('period_case', details, preview_hash=preview['preview_hash']))
        self.travel = t = travel_fixture.TravelWorkflowTests('runTest')
        for key in ('office', 'owner', 'technician', 'employee', 'project', 'now', 'temporary', 'hr'):
            setattr(t, key, getattr(f, key))
        t.api = TravelAllowances(f.office, clock=lambda:f.now)
        t.file = t.upload(purpose='expense_receipt', actor=f.technician, visible=True)
        t.home = t.save_site('home'); t.place = t.save_site('external_fixed')
        t.instance = rid(); key = Fernet.generate_key()
        self.storage = Storage(f.office, key, 'factor-travel.example.test',
            config={'server': {'path':str(Path(f.temporary.name)/'company')}})
        bind(f.office, t.instance, 'factor-travel.example.test', key, self.storage)
        t.account = Accounting(f.office, clock=lambda:f.now).create_account(f.owner,
            dict(request_id=rid(), confirmation=True, code='1200', name='Synthetic factor travel bank', kind='bank'))
        self.settlement = t.api.approve(f.owner, t.approval(t.submitted()))['result']
        self.payment, self.payment_command = self.pay(1400)
        self.api = PayrollCalculationCases(f.office, clock=lambda:f.now)

    def pay(self, amount, **changes):
        body = self.travel.payment(self.settlement, amount, **changes)
        return record_payment(self.travel.api, self.f.owner, body)['result'], body

    def details(self):
        return dict(month='2026-10', period_case_ref=reference(self.base),
            employment_terms_refs=[reference(self.base['sources']['employment_terms'])],
            profile_refs=[reference(self.f.data['profile'])], identity_refs=[reference(self.f.identity)],
            segment_events=[], thirty_day_rule=None, entitlement_case_refs=[],
            travel_settlement_refs=[reference(self.settlement)], travel_payment_refs=[reference(self.payment)],
            flat_tax_decision=None, verification_note='Synthetic complete paid tax-free original checked')

    def prepare(self):
        data = dict(employee_id=self.f.employee['id'], employee_revision=self.f.employee['revision'],
            kind='calculation_case', rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
            details=self.details(), source_file_ids=[self.f.data['file']['id']])
        preview = self.api.preview(self.f.owner, data)
        body = dict(data, request_id=rid(), revision=0, status='active', confirmed=True, preview_hash=preview['preview_hash'])
        return body, preview

    def correct_factor(self, saved, run):
        f=self.f;old=f.data['profile']
        f.data['profile']=f.payroll.save_profile(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],
            id=old['id'],revision=old['revision'],profile=dict(old['profile'],tax_factor='0.900'),
            source_file_id=f.data['file']['id'],confirmed=True,correction_reason='Synthetic corrected factor evidence'))
        f.identity,_=f.save_account(f.data,'identity',f.identity_details(f.data,employment_from='2026-10-01',employment_to=None))
        period_details=f.period_details(self.base['sources']['employment_terms'])
        period_preview=f.api.preview(f.owner,f.preview_body(period_details))
        self.base=f.api.save(f.owner,f.body('period_case',period_details,id=self.base['id'],revision=self.base['revision'],
            preview_hash=period_preview['preview_hash'],correction_reason='Synthetic corrected factor period'))
        data=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='calculation_case',
            rule_version=RULE_VERSION,source_contract_version=SOURCE_CONTRACT_VERSION,details=self.details(),
            source_file_ids=[f.data['file']['id']])
        preview=self.api.preview(f.owner,data)
        body=dict(data,request_id=rid(),id=saved['id'],revision=saved['revision'],status='active',confirmed=True,
            preview_hash=preview['preview_hash'],correction_reason='Synthetic explicit factor correction preserving original travel')
        corrected=self.api.save(f.owner,body)
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(corrected))
        run_body=command(f.payroll,f.owner,inputs)|dict(id=run['id'],revision=run['revision'],correction_reason='Synthetic factor payroll correction')
        return body,preview,corrected,inputs,run_body,f.payroll.finalize(f.owner,run_body)


class FactorTravelTests(FactorTravelFixture):
    def test_actual_paid_trip_keeps_all_v9_and_v8_money_and_original_receipts(self):
        f=self.f;body,preview=self.prepare();saved=self.api.save(f.owner,body)
        self.assertTrue(saved['plan']['can_calculate']);self.assertEqual(saved['plan']['travel_paid_minor'],1400)
        self.assertEqual(saved,self.api.save(f.owner,body))
        self.assertEqual(saved['sources']['period_case'],self.base)
        calculated=calculate_source(saved['sources'])
        original=calculate_factor_period_source(self.base['sources'])
        self.assertEqual(calculated['scope'],SCOPE)
        for key in AMOUNTS:self.assertEqual(calculated[key],original[key],key)
        self.assertEqual(calculated['individual_wage_tax_minor'],58908)
        self.assertEqual(calculated['net_minor'],332342)
        self.assertFalse(calculated['travel_expenses_included_in_net'])
        run_input=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(saved))
        run_command=command(f.payroll,f.owner,run_input);run=f.payroll.finalize(f.owner,run_command)
        self.assertEqual(run,f.payroll.finalize(f.owner,run_command))
        statement=PayrollStatements(f.office).get(f.owner,run['id'])['statement']
        self.assertEqual(statement['travel_summary']['tax_free_external_minor'],1400)
        self.assertNotIn('cash_source_hash',canonical(statement))
        self.assertNotIn('account_id',canonical(saved['sources']['travel_sources']))
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)
        self.assertTrue(validate_integrity(f.office))

    def test_missing_payment_and_foreign_month_are_not_a_zero_money_shortcut(self):
        with self.assertRaises(Problem):
            paid_taxfree_source(self.f.office,self.f.owner,self.f.employee['id'],reference(self.settlement),[],'2026-10',fresh=True)
        with self.assertRaises(Problem):
            paid_taxfree_source(self.f.office,self.f.owner,self.f.employee['id'],reference(self.settlement),[reference(self.payment)],'2026-11',fresh=True)
        body,_=self.prepare()
        for wrong in (None,1,True,[], 'invalid'):
            with self.subTest(details=wrong),self.assertRaises(Problem) as caught:
                self.api.save(self.f.owner,dict(body,details=wrong))
            self.assertEqual(caught.exception.status,400)
            preview={key:body[key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
            with self.assertRaises(Problem) as caught:self.api.preview(self.f.owner,dict(preview,details=wrong))
            self.assertEqual(caught.exception.status,400)

    def test_repayment_requires_current_complete_payment_prefix_but_keeps_old_original(self):
        body,_=self.prepare();saved=self.api.save(self.f.owner,body)
        repayment,_=self.pay(100,kind='repayment')
        self.assertEqual(self.api.save(self.f.owner,body),saved)
        with self.assertRaises(Problem):self.api.resolve_calculation_case(self.f.owner,self.f.employee['id'],reference(saved))
        self.assertTrue(validate_integrity(self.f.office))
        with self.assertRaises(Problem):paid_taxfree_source(self.f.office,self.f.owner,self.f.employee['id'],
            reference(self.settlement),[reference(self.payment),reference(repayment)],'2026-10',fresh=True)

    def test_fresh_financial_rights_and_no_foreign_payment_adoption(self):
        with self.assertRaises(Problem):
            paid_taxfree_source(self.f.office,self.f.technician,self.f.employee['id'],
                reference(self.settlement),[reference(self.payment)],'2026-10',fresh=True)
        body,_=self.prepare();saved=self.api.save(self.f.owner,body)
        self.f.pause()
        self.assertEqual(saved,self.api.save(self.f.owner,body))
        with self.assertRaises(Problem):self.api.save(self.f.owner,dict(body,request_id=rid()))

    def test_taxable_flat_non_cash_and_m_require_distinct_supported_rules(self):
        from business_personnel_workflow import _sha
        from payroll_factor_taxfree_travel_2026 import build_plan
        body,preview=self.prepare()
        for key in ('individual_taxable_payroll_minor','flat_taxable_payroll_minor','benefit_in_kind_non_cash_minor','letter_m'):
            source=deepcopy(preview['source_snapshot']);travel=source['travel_sources'][0]
            if key=='letter_m':travel[key]=True
            else:
                travel[key]=100
                kind={'individual_taxable_payroll_minor':'individual_taxable_payroll',
                    'flat_taxable_payroll_minor':'flat_taxable_payroll','benefit_in_kind_non_cash_minor':'benefit_in_kind_non_cash'}[key]
                travel['allocations']=[dict(key=key,kind=kind,month='2026-10',amount_minor=100,source_hash=travel['settlement_ref']['content_hash'])]
            travel['source_hash']=_sha({k:v for k,v in travel.items() if k!='source_hash'})
            plan=build_plan(source)
            self.assertFalse(plan['can_calculate'],key)
            self.assertIsNone(calculate_source(source)['net_minor'],key)

    def test_forged_original_payment_source_is_recomputed_from_database(self):
        from business_payroll_calculation_cases import validate_case_sources
        body,_=self.prepare();saved=self.api.save(self.f.owner,body);forged=deepcopy(saved)
        forged['sources']['travel_sources'][0]['payment_proof']['paid_minor']+=1
        with self.assertRaises(ValueError):validate_case_sources(self.f.office,forged)

    def test_factor_correction_preserves_run_pdf_case_and_original_travel_payment(self):
        from travel_allowance_cash import public_source
        f=self.f;body,_=self.prepare();saved=self.api.save(f.owner,body)
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(saved))
        run_body=command(f.payroll,f.owner,inputs);run=f.payroll.finalize(f.owner,run_body)
        original_pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        original_json=f.payroll.export(f.owner,run['id'],'json')[0]
        travel_cash=public_source(f.office,self.payment['id'])
        _,_,corrected,_,correction_body,correction=self.correct_factor(saved,run)
        self.assertEqual(correction['calculation']['net_minor'],320834)
        self.assertEqual(correction['delta']['net_minor'],-11508)
        self.assertEqual(correction['calculation']['period_details']['travel_paid_minor'],1400)
        self.assertEqual(f.payroll.finalize(f.owner,run_body),run)
        self.assertEqual(f.payroll.finalize(f.owner,correction_body),correction)
        self.assertEqual(self.api.save(f.owner,body),saved)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf','1')[0],original_pdf)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'json','1')[0],original_json)
        self.assertEqual(public_source(f.office,self.payment['id']),travel_cash)
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)
        self.assertEqual(self.api.get(f.owner,saved['id'],True)['items'],[saved,corrected])
        self.assertTrue(validate_integrity(f.office))

    def test_oneoff_source_pickers_do_not_offer_factor_travel_as_supported_bonus_basis(self):
        from business_payroll_oneoff_cases import PayrollOneoffCases
        from business_payroll_multiple_cases import PayrollMultipleCases
        body,_=self.prepare();saved=self.api.save(self.f.owner,body)
        for service in (PayrollOneoffCases,PayrollMultipleCases):
            sources=service(self.f.office).sources(self.f.owner,dict(employee_id=self.f.employee['id'],month='2026-10'))
            self.assertNotIn(saved['id'],[value['id'] for value in sources['calculation_cases']])

    def test_existing_cash_and_euer_count_the_external_travel_payment_exactly_once(self):
        from business_accounting_profile import AccountingPreparationProfile
        from business_accounting_euer import EuerAccounting
        from business_payroll_cash import PayrollCash
        from travel_allowance_cash import public_source
        import test_business_payroll_cash as cash_fixture
        import test_business_payroll_accounts as account_fixture
        f=self.f;body,_=self.prepare();saved=self.api.save(f.owner,body)
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(saved))
        run=f.payroll.finalize(f.owner,command(f.payroll,f.owner,inputs))
        profile=AccountingPreparationProfile(f.office,clock=lambda:f.now);state=profile.state(f.owner)
        data=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic complete EÜR facts',
            evidence_reference='Synthetic owner evidence',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',
            vat_regime='regular',vat_timing='cash',vat_effective_from='2026-01-01',bookkeeping_start='2026-01-01'))
        proof=profile.preview(f.owner,data)
        profile.confirm(f.owner,dict(data,request_id=rid(),confirmation=True,preview_hash=proof['preview_hash']))
        helper=cash_fixture.PayrollCashTests('runTest')
        helper.office=f.office;helper.owner=f.owner;helper.f=f;helper.instance=self.travel.instance;helper.account=self.travel.account
        helper.api=PayrollCash(f.office,clock=lambda:f.now);helper.euer=EuerAccounting(f.office,clock=lambda:f.now)
        paid,_=f.save_account(f.data,'payment',account_fixture.PayrollAccountTests.payment_details(f,run,f.identity))
        net=helper.import_cash(helper.body(paid));helper.post('payroll_cash',helper.payload(net))
        remittance=helper.import_cash(helper.remittance(f.data,run,paid));helper.post('payroll_cash',helper.payload(remittance))
        travel=public_source(f.office,self.payment['id'])
        helper.post('travel_cash',dict(payment_id=self.payment['id'],revision=1,source_hash=travel['source_hash'],accounts={'travel_allowance':'6664'}))
        report=helper.euer.report(f.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'6206.00')
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_travel_payments').fetchone()[0],1)


if __name__=='__main__':unittest.main()
