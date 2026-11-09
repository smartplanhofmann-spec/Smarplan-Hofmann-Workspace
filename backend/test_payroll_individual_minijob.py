"""Independent XML comparisons and actual private v11 payroll sources."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from core import Problem, canonical
from business_payroll import Payroll, _sha, validate_integrity as validate_payroll
from business_payroll_accounts import PayrollAccounts, validate_integrity as validate_accounts
from business_payroll_calculation_cases import PayrollCalculationCases, validate_integrity as validate_cases
from business_payroll_facts import PayrollFacts, reference
from business_payroll_statements import project as employee_statement
from business_payroll_annual_basis import PayrollAnnualBasis
from payroll_pap_minijob_2026 import calculate_individual_minijob_tax, parameters
from payroll_individual_minijob_2026 import RULE_VERSION, SOURCE_CONTRACT_VERSION, SCOPE, BOOL_FIELDS
import test_business_payroll as monthly
import test_business_payroll_accounts as account_fixture
import test_business_payroll_calculation_cases as legacy_fixture
from test_business_payroll import rid

ROOT = Path(__file__).resolve().parents[1]


class IndividualMinijobFixture:
    def __init__(self, owner, *, pension_exempt=False, tax_class=5, gross=50000):
        self.f = f = monthly.PayrollWorkflowTests('runTest')
        f.setUp(); owner.addCleanup(f.doCleanups)
        f.now = f.now.replace(month=11, day=3)
        f.employee = f.call(f.planning, 'save_employee', f.owner,
            dict(request_id=rid(), id=f.employee['id'], revision=f.employee['revision'],
                 employment_from='2026-10-01', employment_to='2026-10-31'))
        self.data = f.case('minijob', gross, minijob_tax='individual', health_insurance='statutory_other',
                           tax_class=tax_class, minijob_rv_exempt=pension_exempt)
        self.files = {}
        for role in ('health', 'pension', 'employment', 'income', 'elstam'):
            self.files[role] = f.hr.upload(f.owner, dict(request_id=rid(), employee_id=f.employee['id'],
                purpose='personnel', owner_visible=False, filename=role+'-original.pdf', media_type='application/pdf',
                content_base64=base64.b64encode(('%PDF-1.4\nSynthetic own '+role+' evidence\n%%EOF').encode()).decode()))
        self.accounts = PayrollAccounts(f.office, clock=lambda:f.now)
        self.identity_body = dict(request_id=rid(), employee_id=f.employee['id'], kind='identity', revision=0,
            source_file_id=self.files['elstam']['id'], confirmed=True,
            details=account_fixture.PayrollAccountTests.identity_details(f, self.data, identity_source_schema_version=2,
                tax_source='elstam_imported'))
        self.identity = self.accounts.save(f.owner, self.identity_body)
        self.facts = PayrollFacts(f.office, clock=lambda:f.now)
        base = dict(request_id=rid(), employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            revision=0, status='active', source_file_ids=[self.data['file']['id']], confirmed=True)
        self.terms = self.facts.save(f.owner, dict(base, kind='employment_terms', details=dict(
            employment_from='2026-10-01', employment_to='2026-10-31', agreement_refs=[reference(self.data['agreement'])],
            proration_method='calendar_days_actual', reason='Actual one full-month employment')))
        period_details = dict(month='2026-10', preparation_ref=reference(self.data['preparation']),
            employment_terms_ref=reference(self.terms), work_schedule_ref=None,
            profile_refs=[reference(self.data['profile'])], identity_refs=[reference(self.identity)],
            tax_treatment='domestic_running_wages', entitlement_decisions=[], verification_note='Actual original full month')
        preview=self.facts.preview(f.owner, dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            details=period_details, source_file_ids=base['source_file_ids']))
        self.period=self.facts.save(f.owner, dict(base, request_id=rid(), kind='period_case', details=period_details,
                                                preview_hash=preview['preview_hash']))
        self.api=PayrollCalculationCases(f.office, clock=lambda:f.now)
        self.details=dict(month='2026-10', period_case_ref=reference(self.period), employment_terms_refs=[reference(self.terms)],
            profile_refs=[reference(self.data['profile'])], identity_refs=[reference(self.identity)], segment_events=[],
            thirty_day_rule=None, entitlement_case_refs=[], travel_settlement_refs=[], flat_tax_decision=None,
            verification_note='Reviewed actual original minijob evidence', individual_minijob_assessment=dict(
                schema_version=1, employee_id=f.employee['id'], valid_from='2026-10-01', valid_to='2026-10-31',
                declaration_date='2026-11-03', actual_health_insurance='statutory_family',
                pension_status='exempt' if pension_exempt else 'compulsory',
                **{key:True for key in BOOL_FIELDS},
                **{role+'_evidence_ref':dict(id=value['id'], revision=1, content_hash=value['content_hash'])
                   for role,value in self.files.items()}, verification_note='Evidence applies to this person and full period'))

    def preview(self, details=None, **changes):
        f=self.f
        body=dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'], kind='calculation_case',
            rule_version=RULE_VERSION, source_contract_version=SOURCE_CONTRACT_VERSION,
            details=details or self.details, source_file_ids=[value['id'] for value in self.files.values()])
        body.update(changes)
        return body,self.api.preview(f.owner,body)

    def save(self):
        body,preview=self.preview()
        command=dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.api.save(self.f.owner,command),command

    def legacy_case(self):
        details={key:deepcopy(value) for key,value in self.details.items() if key!='individual_minijob_assessment'}
        body,preview=self.preview(details,rule_version='de_2026_segments_entitlements_v5',source_contract_version=1)
        command=dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.api.save(self.f.owner,command),command

    def upgrade_command(self,legacy):
        body,preview=self.preview()
        return dict(body,request_id=rid(),id=legacy['id'],revision=legacy['revision'],status='active',confirmed=True,
            preview_hash=preview['preview_hash'],correction_reason='Explicit reviewed correction of unsupported individual minijob to v11')

    def run(self):
        case,case_command=self.save()
        inputs=dict(source_schema_version=3,employee_id=self.f.employee['id'],calculation_case_ref=reference(case))
        preview=self.f.payroll.preview(self.f.owner,inputs)
        command=dict(inputs,request_id=rid(),revision=0,confirmed=True,accepted_scope=SCOPE,preview_hash=preview['preview_hash'])
        return self.f.payroll.finalize(self.f.owner,command),command,case,case_command


class IndividualMinijobTests(unittest.TestCase):
    def test_hash_consistent_but_invalid_original_blocks_upgrade_without_mutation(self):
        fixture=IndividualMinijobFixture(self);f=fixture.f
        legacy,old_command=fixture.legacy_case();command=fixture.upgrade_command(legacy)
        # Deliberate damage only in this disposable fixture: the original has
        # a correct envelope hash but cannot possibly be a valid payroll run.
        envelope=dict(id=rid(),kind='run',employee_id=f.employee['id'],revision=1,previous_hash=None,
            identity_key=None,created_by=f.owner['id'],created_at=f.hr.now(),pdf_sha256=None,payload={})
        f.office.db.execute('INSERT INTO business_payroll_events '
            '(id,kind,employee_id,revision,previous_hash,identity_key,created_by,created_at,pdf_sha256,payload_json,content_hash) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(envelope[key] for key in ('id','kind','employee_id','revision',
                'previous_hash','identity_key','created_by','created_at','pdf_sha256'))+(canonical({}),_sha(envelope)))
        damaged=dict(f.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(envelope['id'],)).fetchone())
        self.assertEqual(Payroll(f.office)._event(damaged)['id'],envelope['id'])
        with self.assertRaises(ValueError):validate_payroll(f.office)
        counts={table:f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in
            ('business_payroll_calculation_case_events','business_payroll_calculation_case_requests')}
        with self.assertRaises(Problem) as error:fixture.api.save(f.owner,command)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(fixture.api.save(f.owner,old_command),legacy)
        self.assertEqual(fixture.api.get(f.owner,legacy['id'],True)['items'],[legacy])
        self.assertEqual(dict(f.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(envelope['id'],)).fetchone()),damaged)
        for table,count in counts.items():self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],count)

    def test_already_finalized_historical_v5_keeps_its_original_contract(self):
        legacy=legacy_fixture.CalculationCaseTests('runTest');legacy.setUp();self.addCleanup(legacy.doCleanups)
        body,_=legacy.request();case=legacy.api.save(legacy.f.owner,body)
        f=legacy.f;inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(case))
        preview=f.payroll.preview(f.owner,inputs)
        command=dict(inputs,request_id=rid(),revision=0,confirmed=True,
            accepted_scope=preview['calculation']['scope'],preview_hash=preview['preview_hash'])
        run=f.payroll.finalize(f.owner,command)
        from payroll_individual_minijob_sources import require_unused_upgrade
        target=dict(kind='calculation_case',status='active',rule_version=RULE_VERSION,source_contract_version=3,plan={'can_calculate':True})
        with self.assertRaises(Problem) as error:require_unused_upgrade(legacy.api,case,target)
        self.assertEqual(error.exception.status,400)
        self.assertEqual(legacy.api.save(f.owner,body),case)
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertTrue(validate_payroll(f.office));self.assertTrue(validate_cases(f.office))

    def test_explicit_unsupported_v5_upgrade_retains_original_receipts_and_history(self):
        fixture=IndividualMinijobFixture(self);f=fixture.f
        legacy,old_command=fixture.legacy_case()
        self.assertFalse(legacy['plan']['can_calculate'])
        with self.assertRaises(Problem):f.payroll.finalize(f.owner,dict(source_schema_version=3,
            employee_id=f.employee['id'],calculation_case_ref=reference(legacy),request_id=rid(),revision=0,
            confirmed=True,accepted_scope=SCOPE,preview_hash='0'*64))
        command=fixture.upgrade_command(legacy)
        with self.assertRaises(Problem):fixture.api.save(f.owner,dict(command,correction_reason=''))
        with self.assertRaises(Problem) as invalid_reason:fixture.api.save(f.owner,dict(command,correction_reason='Invalid \ud800'))
        self.assertEqual(invalid_reason.exception.status,400)
        upgraded=fixture.api.save(f.owner,command)
        self.assertEqual(upgraded['revision'],2);self.assertTrue(upgraded['plan']['can_calculate'])
        self.assertEqual(upgraded['previous_hash'],legacy['content_hash'])
        self.assertEqual(fixture.api.save(f.owner,old_command),legacy)
        self.assertEqual(fixture.api.get(f.owner,legacy['id'],True)['items'],[legacy,upgraded])
        self.assertEqual(fixture.api.resolve_calculation_case(f.owner,f.employee['id'],reference(legacy),fresh=False),legacy)
        self.assertTrue(validate_cases(f.office))
        # A real accepted v11 run does not rewrite the old unsupported case.
        inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(upgraded))
        preview=f.payroll.preview(f.owner,inputs)
        run=f.payroll.finalize(f.owner,dict(inputs,request_id=rid(),revision=0,confirmed=True,
            accepted_scope=SCOPE,preview_hash=preview['preview_hash']))
        annual=PayrollAnnualBasis(f.office,clock=lambda:f.now)
        projected=annual._project_run(run,as_of_date='2026-11-03')
        self.assertEqual(projected['running_taxable_minor'],0)  # No payment is invented by the correction.
        self.assertEqual(projected['periods'][0]['section_key'],'minijob')
        self.assertEqual(fixture.api.save(f.owner,old_command),legacy)
        with self.assertRaises(Problem):fixture.api.save(f.owner,dict(old_command,request_id=rid(),id=legacy['id'],
            revision=2,correction_reason='No reverse implicit migration'))
        self.assertTrue(validate_payroll(f.office));self.assertTrue(validate_cases(f.office))

    def test_upgrade_requires_calculable_target_and_unambiguous_unused_sources(self):
        fixture=IndividualMinijobFixture(self);legacy,_=fixture.legacy_case();f=fixture.f
        details=deepcopy(fixture.details);details['individual_minijob_assessment']['sole_employment_confirmed']=False
        body,preview=fixture.preview(details)
        with self.assertRaises(Problem) as error:fixture.api.save(f.owner,dict(body,request_id=rid(),id=legacy['id'],revision=1,
            status='active',confirmed=True,preview_hash=preview['preview_hash'],correction_reason='Incomplete target'))
        self.assertEqual(error.exception.status,400)
        # A corrupted retained dependent record can never establish non-use.
        # No fake release/acceptance is treated as a valid business record.
        from payroll_individual_minijob_sources import require_unused_upgrade
        valid=dict(kind='calculation_case',status='active',rule_version=RULE_VERSION,source_contract_version=3,plan={'can_calculate':True})
        f.office.db.execute('INSERT INTO business_payroll_events(id,kind,employee_id,revision,payload_json,content_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
            (rid(),'run',f.employee['id'],1,'{}','0'*64,f.owner['id'],f.hr.now()))
        # Missing required original fields is ambiguity, even without an ID hit.
        with self.assertRaises(Problem) as error:require_unused_upgrade(fixture.api,legacy,valid)
        self.assertEqual(error.exception.status,409)

    def test_independent_xml_vectors_and_original_32_kernels(self):
        vectors=json.loads((ROOT/'backend/testdata/minijob_individual_xml_2026.json').read_text())
        self.assertFalse(vectors['production_code_loaded']);self.assertEqual(len(vectors['cases']),36)
        for case in vectors['cases']:
            p=case['input']
            with self.subTest(case=case['id']):
                result=calculate_individual_minijob_tax(gross_minor=p['RE4'],tax_class=p['STKL'],pension_exempt=p['KRV']==1)
                self.assertEqual(result,{key:case['xml_output'][key] for key in result})
                technical=parameters(gross_minor=p['RE4'],tax_class=p['STKL'],pension_exempt=p['KRV']==1)
                self.assertEqual({key:p[key] for key in technical},technical)
        hashes=json.loads((ROOT/'docs/evidence/minijob-individual-v11-2026-11-09/historical-kernel-hashes.json').read_text())
        self.assertEqual(len(hashes),32)
        for name,value in hashes.items():self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),value,name)
        for changes in (dict(gross_minor=17499),dict(gross_minor=60301),dict(gross_minor=True),dict(tax_class=2),dict(pension_exempt=1)):
            with self.assertRaises(Problem):calculate_individual_minijob_tax(**(dict(gross_minor=50000,tax_class=5,pension_exempt=False)|changes))

    def test_actual_full_month_compulsory_rv_source_and_employee_statement(self):
        fixture=IndividualMinijobFixture(self);run,command,case,case_command=fixture.run();f=fixture.f
        result=run['calculation']
        self.assertTrue(result['payroll_calculation_complete'],result['blockers'])
        self.assertEqual(result['individual_wage_tax_minor'],4866)
        self.assertEqual(result['employee_contributions']['pension'],1800)
        self.assertEqual(result['net_minor'],43334)
        self.assertEqual(result['employer_contributions']['health_general'],6500)
        self.assertEqual(result['employer_contributions']['pension'],7500)
        self.assertEqual(result['employer_flat_tax_minor'],0)
        self.assertEqual(result['tax_parameters']['actual_health_insurance'],'statutory_family')
        self.assertEqual(result['tax_parameters']['technical_pap_parameters']['PKV'],1)
        self.assertEqual(run['source']['profile']['profile']['health_insurance'],'statutory_other')
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(fixture.api.save(f.owner,case_command),case)
        view=employee_statement(run)
        self.assertEqual(view['calculation']['individual_wage_tax_minor'],4866)
        self.assertNotIn('elstam_evidence_ref',json.dumps(view))
        self.assertTrue(validate_payroll(f.office));self.assertTrue(validate_cases(f.office));self.assertTrue(validate_accounts(f.office))

    def test_actual_full_month_exempt_rv_has_different_tax(self):
        fixture=IndividualMinijobFixture(self,pension_exempt=True)
        run,_,_,_=fixture.run();result=run['calculation']
        self.assertEqual(result['individual_wage_tax_minor'],5516)
        self.assertEqual(result['employee_contributions']['pension'],0)
        self.assertEqual(result['net_minor'],44484)
        self.assertEqual(result['tax_parameters']['technical_pap_parameters']['KRV'],1)

    def test_missing_or_false_actual_facts_never_calculate(self):
        fixture=IndividualMinijobFixture(self)
        for field in BOOL_FIELDS:
            values=deepcopy(fixture.details);values['individual_minijob_assessment'][field]=False
            _,preview=fixture.preview(values)
            self.assertFalse(preview['can_calculate'],field)
        for patch in ({'actual_health_insurance':'private'},{'pension_status':'exempt'},{'valid_to':'2026-10-30'}):
            values=deepcopy(fixture.details);values['individual_minijob_assessment'].update(patch)
            self.assertFalse(fixture.preview(values)[1]['can_calculate'])

    def test_original_file_and_version_requirements_are_strict(self):
        fixture=IndividualMinijobFixture(self)
        for field,value in (('source_contract_version',2),('source_contract_version',True),('rule_version','de_2026_segments_entitlements_v5')):
            with self.assertRaises(Problem):fixture.preview(**{field:value})
        values=deepcopy(fixture.details);values['individual_minijob_assessment']['health_evidence_ref']['content_hash']='0'*64
        with self.assertRaises(Problem):fixture.preview(values)
        values=deepcopy(fixture.details);values['individual_minijob_assessment']['declaration_date']='2026-11-04'
        with self.assertRaises(Problem):fixture.preview(values)
        values=deepcopy(fixture.details);del values['individual_minijob_assessment']['income_evidence_ref']
        with self.assertRaises(Problem):fixture.preview(values)
        for field in ('outer','assessment'):
            values=deepcopy(fixture.details)
            target=values if field=='outer' else values['individual_minijob_assessment']
            target['verification_note']='Invalid surrogate \ud800'
            with self.assertRaises(Problem) as error:fixture.preview(values)
            self.assertEqual(error.exception.status,400)

    def test_actual_payment_ledger_and_individual_annual_projection(self):
        fixture=IndividualMinijobFixture(self);run,_,case,_=fixture.run();f=fixture.f
        body=dict(request_id=rid(),employee_id=f.employee['id'],kind='payment',revision=0,
            source_file_id=fixture.files['income']['id'],confirmed=True,
            details=dict(run_id=run['id'],run_revision=run['revision'],identity_id=fixture.identity['id'],
                identity_revision=fixture.identity['revision'],payments=[dict(paid_on='2026-10-31',
                    amount_minor=run['calculation']['net_minor'],payment_reference='SYN-V11-ORIGINAL')],
                tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True))
        payment=fixture.accounts.save(f.owner,body)
        self.assertEqual(fixture.accounts.save(f.owner,body),payment)
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertTrue(ledger['statutory_wage_account_complete'])
        self.assertEqual(ledger['totals']['individual_wage_tax_minor'],4866)
        self.assertEqual(ledger['totals']['net_minor'],43334)
        annual=PayrollAnnualBasis(f.office,clock=lambda:f.now)
        projected=annual._project_run(run,as_of_date='2026-11-03',payment=payment)
        self.assertEqual(projected['running_taxable_minor'],50000)
        self.assertEqual(projected['tax_receipt_status'],'received_same_year')
        self.assertEqual(projected['periods'][0]['section_key'],'minijob')
        self.assertNotIn(case,annual.sources(f.owner,dict(employee_id=f.employee['id']))['calculation_cases'])
        for kind in ('json','csv','pdf'):
            raw,_=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),kind)
            self.assertTrue(raw)
        self.assertTrue(validate_payroll(f.office));self.assertTrue(validate_accounts(f.office))

    def test_replaced_original_prevents_new_use_and_preserves_history(self):
        fixture=IndividualMinijobFixture(self);saved,command=fixture.save();f=fixture.f
        health=fixture.files['health']
        f.hr.upload(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],purpose='personnel',owner_visible=False,
            supersedes=health['id'],filename='revised-health.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nActually replaced health original\n%%EOF').decode()))
        with self.assertRaises(Problem):fixture.api.resolve_calculation_case(f.owner,f.employee['id'],reference(saved))
        self.assertEqual(fixture.api.save(f.owner,command),saved)
        self.assertEqual(fixture.api.resolve_calculation_case(f.owner,f.employee['id'],reference(saved),fresh=False),saved)
        self.assertTrue(validate_cases(f.office))

    def test_new_identity_is_explicit_and_never_a_flat_tax_relabelling(self):
        fixture=IndividualMinijobFixture(self);f=fixture.f
        for invalid in (None,1,True,[], 'not structured'):
            body=deepcopy(fixture.identity_body);body.update(request_id=rid(),details=invalid)
            with self.assertRaises(Problem) as error:fixture.accounts.save(f.owner,body)
            self.assertEqual(error.exception.status,400)
        for changes in ({'identity_source_schema_version':1},{'tax_source':'flat_minijob_evidence'}):
            body=deepcopy(fixture.identity_body);body['request_id']=rid();body['details'].update(changes)
            with self.assertRaises(Problem):fixture.accounts.save(f.owner,body)
        body=deepcopy(fixture.identity_body);body['request_id']=rid();del body['details']['identity_source_schema_version']
        with self.assertRaises(Problem):fixture.accounts.save(f.owner,body)
        self.assertEqual(fixture.accounts.get(f.owner,fixture.identity['id']),fixture.identity)
        self.assertTrue(validate_accounts(f.office))


if __name__=='__main__':unittest.main()
