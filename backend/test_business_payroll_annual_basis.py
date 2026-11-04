"""Real private annual-history facts: source records, receipts and corrections."""
import base64
from copy import deepcopy
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_annual_basis as annual
from business_foundation import BusinessFoundation
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import canonical
import test_business_payroll_facts as facts_fixture
import test_business_payroll as monthly


class PayrollAnnualBasisTests(monthly.BusinessFixture,unittest.TestCase):
    case=facts_fixture.PayrollFactTests.case
    identity_details=facts_fixture.PayrollFactTests.identity_details
    save_account=facts_fixture.PayrollFactTests.save_account
    account_api=facts_fixture.PayrollFactTests.account_api
    terms_details=facts_fixture.PayrollFactTests.terms_details
    body=facts_fixture.PayrollFactTests.body
    terms=facts_fixture.PayrollFactTests.terms
    pause=facts_fixture.PayrollFactTests.pause
    period_details=facts_fixture.PayrollFactTests.period_details
    preview_body=facts_fixture.PayrollFactTests.preview_body
    period=facts_fixture.PayrollFactTests.period

    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_annual_basis' not in names:names+=('business_payroll_annual_basis',)
        self.registry=patch.object(business_schema,'MODULE_NAMES',names)
        self.registry.start();self.addCleanup(self.registry.stop)
        facts_fixture.PayrollFactTests.setUp(self)
        self.annual=annual.PayrollAnnualBasis(self.office,clock=lambda:self.now)
        self.original=dict(id=self.data['file']['id'],revision=1,content_hash=self.data['file']['content_hash'])

    def imported_details(self):
        return dict(employer_identity_ref=reference(self.identity),verification_note='Vollständige geschützte Originalperiode geprüft',
            period_start='2026-10-15',period_end='2026-10-31',employment_from='2026-10-15',employment_to=None,section_key='regular',
            profile=dict(scheme='regular_standard',health_insurance='statutory_mandatory',health_additional_percent='2.900',
                saxony=False,childless_surcharge=True,care_child_discounts=0,minijob_rv_exempt=False,pension_other_compulsory=False,u1_percent='1.100',u2_percent='0.220'),
            branches={branch:dict(eligible_intervals=[dict(start='2026-10-15',end='2026-10-31',legal_reason='paid_employment',evidence_ref=self.original)],
                total_minor=100000,employee_minor=100000) for branch in annual.BRANCHES},
            running_gross_minor=100000,running_taxable_minor=100000,
            running_receipts=[dict(received_on='2026-10-31',taxable_minor=100000,evidence_ref=self.original)],
            original_rule_version='Original payroll procedure 2026',original_rule_hash='a'*64,
            original_payroll_reference='Original-2026-10-01',document_refs=[self.original])

    def request(self,kind,details):
        body=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind=kind,
                  details=details,source_file_ids=[self.data['file']['id']])
        preview=self.annual.preview(self.owner,body)
        return body|dict(request_id=monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']),preview

    def save(self,kind='imported_period',details=None):
        body,preview=self.request(kind,details or self.imported_details())
        return self.annual.save(self.owner,body),body,preview

    def basis_details(self,period,**changes):
        return dict(employer_identity_ref=reference(self.identity),verification_note='Alle Originalperioden und Lücken abgeglichen',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[],payroll_payment_refs=[],imported_period_refs=[reference(period)],
            imported_one_off_refs=[],current_calculation_case_ref=None,
            gaps=[dict(start='2026-01-01',end='2026-10-14',reason='not_employed',evidence_ref=self.original)],completeness_confirmed=True)|changes

    def test_original_period_annual_room_replay_and_no_payroll_or_payment_effect(self):
        before={name:self.office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]
                for name in ('business_payroll_events','business_payroll_cash_batches','business_euer_entries')}
        period,body,_=self.save();basis,_,_=self.save('annual_basis',self.basis_details(period))
        room=self.annual.social_room(self.owner,self.employee['id'],reference(basis),through='2026-10-31',section_key='regular')
        self.assertEqual((room['branches']['health']['sv_days'],room['branches']['health']['room_minor']),(17,229375))
        self.assertEqual(room['branches']['pension']['room_minor'],378833)
        self.assertEqual(basis['plan']['running_taxable_minor'],100000)
        self.assertEqual(self.annual.save(self.owner,body),period)
        self.assertNotIn('accepted_command',period)
        self.assertEqual(before,{name:self.office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in before})
        self.assertTrue(annual.validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_missing_calendar_day_and_omitted_known_period_are_not_zero(self):
        period,_,_=self.save();details=self.basis_details(period)
        details['gaps'][0]['end']='2026-10-13'
        self.problem(409,lambda:self.request('annual_basis',details))
        details=self.basis_details(period,imported_period_refs=[],gaps=[dict(start='2026-01-01',end='2026-10-31',reason='not_employed',evidence_ref=self.original)])
        self.problem(409,lambda:self.request('annual_basis',details))

    def test_later_bonus_does_not_consume_earlier_cutoff_room(self):
        period,_,_=self.save()
        bonus=dict(employer_identity_ref=reference(self.identity),verification_note='Tatsächlichen späteren Zufluss geprüft',
            receipt_date='2026-11-01',amount_minor=50000,assigned_period_ref=reference(period),section_key='regular',
            bases_minor={k:50000 for k in annual.BRANCHES},original_reference='Bonus-2026-11-01',document_refs=[self.original])
        paid,_,_=self.save('imported_one_off',bonus)
        early,_,_=self.save('annual_basis',self.basis_details(period))
        self.assertEqual(early['plan']['section_rooms']['regular']['health']['room_minor'],229375)
        late,_,_=self.save('annual_basis',self.basis_details(period,as_of_date='2026-11-01',imported_one_off_refs=[reference(paid)]))
        self.assertEqual(late['plan']['section_rooms']['regular']['health']['room_minor'],179375)
        self.problem(409,lambda:self.request('annual_basis',self.basis_details(period,imported_one_off_refs=[reference(paid)])))

    def test_original_file_supersession_blocks_new_use_preserves_old_replay(self):
        period,body,_=self.save()
        self.hr.upload(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],purpose='personnel',owner_visible=False,
            filename='annual-replacement.pdf',media_type='application/pdf',supersedes=self.data['file']['id'],
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic revised historical record\n%%EOF').decode()))
        self.problem(409,lambda:self.annual.resolve(self.owner,self.employee['id'],reference(period)))
        self.assertEqual(self.annual.save(self.owner,body),period)
        self.assertTrue(annual.validate_integrity(self.office))

    def test_replay_after_employee_change_and_module_pause_is_exact(self):
        period,body,_=self.save()
        self.employee=self.call(self.planning,'save_employee',self.owner,dict(request_id=monthly.rid(),id=self.employee['id'],revision=self.employee['revision'],name='Berichtigter Quellenname'))
        self.pause();self.assertEqual(self.annual.save(self.owner,body),period)
        self.problem(423,lambda:self.annual.save(self.owner,body|dict(request_id=monthly.rid(),employee_revision=self.employee['revision'])))

    def test_fresh_private_rights_apply_even_to_accepted_receipt(self):
        uid=self.office.add_user('annual-delegate@example.test','Synthetic-Annual-password-123','technician')
        actor=dict(id=uid,email='annual-delegate@example.test',role='technician');grants=BusinessFoundation(self.office)
        for name in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,dict(request_id=monthly.rid(),user_id=uid,permission=name,scope='*',effect='allow',revision=0))
        body,_=self.request('imported_period',self.imported_details());period=self.annual.save(actor,body)
        grants.save_grant(self.owner,dict(request_id=monthly.rid(),user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        for action in (lambda:self.annual.save(actor,body),lambda:self.annual.get(actor,period['id']),lambda:self.annual.sources(actor,dict(employee_id=self.employee['id']))):self.problem(403,action)

    def test_immutable_tables_and_rehashed_result_rejected(self):
        period,_,_=self.save()
        for table in annual.TABLES:
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        self.office.db.execute('DROP TRIGGER business_payroll_annual_events_update_guard')
        row=dict(self.annual._row(period['id']));payload=json.loads(row['payload_json']);payload['plan']['running_gross_minor']+=1
        envelope={k:v for k,v in row.items() if k not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=json.loads(row['sources_json']))
        self.office.db.execute('UPDATE business_payroll_annual_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),_sha(envelope),period['id']))
        with self.assertRaises(ValueError):annual.validate_integrity(self.office)

    def test_unknown_amounts_and_changed_preview_are_atomic(self):
        body,_=self.request('imported_period',self.imported_details())
        for details in (body['details']|dict(ready_annual_room_minor=123),body['details']|dict(running_gross_minor=True)):
            self.problem(400,lambda details=details:self.annual.save(self.owner,body|dict(details=details)))
        self.problem(409,lambda:self.annual.save(self.owner,body|dict(preview_hash='0'*64)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_annual_events').fetchone()[0],0)

    def claim_details(self,terms,reference_text='Contract bonus position 1'):
        return dict(employer_identity_ref=reference(self.identity),verification_note='Konkrete Anspruchsposition und Beschäftigung geprüft',
            claim_key=self.original,claim_reference=reference_text,planned_receipt_date='2026-10-31',amount_minor=50000,
            tax_classification='other_payment',social_classification='one_off_remuneration',section_key='regular',
            employment_terms_refs=[reference(terms)],claim_periods=[dict(start='2026-10-15',end='2026-10-31',evidence_ref=self.original)],
            document_refs=[self.original])

    def regular_contract(self):
        old=self.data['profile'];agreement=self.data['agreement']
        self.data['profile']=self.payroll.save_profile(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            id=old['id'],revision=old['revision'],profile=monthly.profile('regular',regular_annual_gross_minor=3600000,
                health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0),
            source_file_id=self.original['id'],confirmed=True,correction_reason='Regulären Originalfall belegt berichtigt'))
        self.data['agreement']=self.hr.save_agreement(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            id=agreement['id'],revision=agreement['revision'],effective_from=agreement['effective_from'],employment_kind='regular',
            pay_basis='monthly',amount_minor=300000,currency='EUR',reference_file_id=self.original['id'],correction_reason='Regulären Originalvertrag belegt berichtigt'))
        self.identity,_=self.save_account(self.data,'identity',self.identity_details(self.data,employment_from='2026-10-15',employment_to=None))

    def forecast_details(self,basis,earning,terms):
        return dict(employer_identity_ref=reference(self.identity),verification_note='Tatsächliche Vorbezüge und Vertragsmonate geprüft',
            annual_basis_ref=reference(basis),receipt_date='2026-10-31',remaining_periods=[dict(month=month,
                employment_terms_ref=reference(terms),agreement_refs=[reference(self.data['agreement'])],work_schedule_ref=None)
                for month in ('2026-11','2026-12')],previous_employers=[],no_previous_employer_ref=self.original,
            identity_ref=reference(self.identity),current_one_off_ref=reference(earning),other_tax_receipt_refs=[])

    def test_forecast_uses_actual_contract_months_excludes_current_bonus_and_preserves_times(self):
        self.regular_contract()
        terms,_=self.terms();period,_,_=self.save();basis,_,_=self.save('annual_basis',self.basis_details(period))
        earning,_,_=self.save('one_off_earning',self.claim_details(terms))
        before=[dict(row) for row in self.office.db.execute('SELECT * FROM business_time_days')]
        forecast,body,_=self.save('annual_tax_forecast',self.forecast_details(basis,earning,terms))
        self.assertEqual(forecast['plan']['annual_pay_before_minor'],700000)
        self.assertEqual(forecast['plan']['one_off_minor'],50000)
        self.assertEqual(forecast['plan']['forecast_future_minor'],600000)
        self.assertTrue(forecast['plan']['current_one_off_excluded'])
        self.assertEqual(before,[dict(row) for row in self.office.db.execute('SELECT * FROM business_time_days')])
        self.assertEqual(self.annual.save(self.owner,body),forecast)
        self.assertTrue(annual.validate_integrity(self.office))

    def test_later_actual_agreement_cannot_be_omitted_from_future_wages(self):
        self.regular_contract()
        terms,_=self.terms();period,_,_=self.save();basis,_,_=self.save('annual_basis',self.basis_details(period))
        earning,_,_=self.save('one_off_earning',self.claim_details(terms))
        details=self.forecast_details(basis,earning,terms)
        self.hr.save_agreement(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],revision=0,
            effective_from='2026-11-01',employment_kind='regular',pay_basis='monthly',amount_minor=310000,currency='EUR',reference_file_id=self.original['id']))
        self.problem(409,lambda:self.request('annual_tax_forecast',details))

    def test_two_documented_claim_positions_in_one_original_are_distinct(self):
        terms,_=self.terms()
        first,_,_=self.save('one_off_earning',self.claim_details(terms))
        second,_,_=self.save('one_off_earning',self.claim_details(terms,'Contract bonus position 2'))
        self.assertNotEqual(first['id'],second['id'])
        self.problem(409,lambda:self.save('one_off_earning',self.claim_details(terms)))

    def test_real_source3_current_period_provides_exact_minijob_days_and_no_individual_tax(self):
        import business_payroll_calculation_cases as cases
        base,_,_=self.period();api=cases.PayrollCalculationCases(self.office,clock=lambda:self.now)
        details=dict(month='2026-10',period_case_ref=reference(base),employment_terms_refs=[reference(base['sources']['employment_terms'])],
            profile_refs=[reference(self.data['profile'])],identity_refs=[reference(self.identity)],segment_events=[],thirty_day_rule=None,
            entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,verification_note='Tatsächliche laufende Monatsquelle geprüft')
        request=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind='calculation_case',
            rule_version=cases.CALCULATION_RULE_VERSION,source_contract_version=cases.SOURCE_CONTRACT_VERSION,details=details,source_file_ids=[self.original['id']])
        preview=api.preview(self.owner,request)
        current=api.save(self.owner,request|dict(request_id=monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        basis_details=dict(employer_identity_ref=reference(self.identity),verification_note='Jahresdeckung mit echter aktueller Monatsquelle geprüft',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[],payroll_payment_refs=[],imported_period_refs=[],imported_one_off_refs=[],
            current_calculation_case_ref=reference(current),gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=self.original)],completeness_confirmed=True)
        basis,_,_=self.save('annual_basis',basis_details)
        self.assertEqual(basis['plan']['running_taxable_minor'],0)
        self.assertEqual(basis['plan']['section_rooms']['minijob']['pension']['sv_days'],17)
        self.assertEqual(basis['plan']['section_rooms']['minijob']['pension']['contributed_minor'],33068)
        # Bind the actually accepted running record next, retaining the old
        # planning snapshot as its immutable earlier annual-fact revision.
        payroll_input=dict(source_schema_version=3,employee_id=self.employee['id'],calculation_case_ref=reference(current))
        run_preview=self.payroll.preview(self.owner,payroll_input)
        run=self.payroll.finalize(self.owner,payroll_input|dict(request_id=monthly.rid(),revision=0,confirmed=True,
            preview_hash=run_preview['preview_hash'],accepted_scope=run_preview['calculation']['scope']))
        accepted_details=basis_details|dict(current_calculation_case_ref=None,payroll_run_refs=[reference(run)])
        body,_=self.request('annual_basis',accepted_details)
        accepted_command=body|dict(id=basis['id'],revision=basis['revision'],correction_reason='Tatsächlich bestätigte Monatsrechnung gebunden')
        accepted=self.annual.save(self.owner,accepted_command)
        self.assertEqual(accepted['plan']['section_rooms'],basis['plan']['section_rooms'])
        self.assertEqual(accepted['sources']['payroll_runs'],[run])
        self.assertFalse(accepted['plan']['contains_planned_current_period'])
        from test_business_payroll_accounts import PayrollAccountTests
        payment,_=self.save_account(self.data,'payment',PayrollAccountTests.payment_details(self,run,self.identity))
        self.problem(409,lambda:self.annual.resolve(self.owner,self.employee['id'],reference(accepted)))
        self.assertEqual(self.annual.save(self.owner,accepted_command),accepted)
        payment_details=accepted_details|dict(payroll_payment_refs=[reference(payment)])
        body,_=self.request('annual_basis',payment_details)
        actual=self.annual.save(self.owner,body|dict(id=accepted['id'],revision=accepted['revision'],correction_reason='Tatsächlichen Lohnkontozufluss gebunden'))
        self.assertEqual(actual['sources']['payroll_payments'],[payment])
        catalog=self.annual.sources(self.owner,dict(employee_id=self.employee['id']))
        self.assertEqual(catalog['calculation_cases'],[current])
        self.assertEqual(catalog['payroll_payments'],[payment])
        self.assertEqual(catalog['payroll_runs'],[run])
        self.assertTrue(annual.validate_integrity(self.office))

    def test_pauschal_minijob_identity_never_becomes_individual_annual_tax_wage(self):
        terms,_=self.terms();period,_,_=self.save();basis,_,_=self.save('annual_basis',self.basis_details(period))
        earning,_,_=self.save('one_off_earning',self.claim_details(terms))
        self.problem(409,lambda:self.request('annual_tax_forecast',self.forecast_details(basis,earning,terms)))

    def test_missing_actual_running_receipt_blocks_forecast_not_social_period_evidence(self):
        self.regular_contract();terms,_=self.terms()
        period,_,_=self.save(details=self.imported_details()|dict(running_receipts=[]))
        basis,_,_=self.save('annual_basis',self.basis_details(period));earning,_,_=self.save('one_off_earning',self.claim_details(terms))
        self.assertEqual(basis['plan']['unpaid_tax_sources'],[reference(period)])
        self.problem(409,lambda:self.request('annual_tax_forecast',self.forecast_details(basis,earning,terms)))

    def test_previous_employer_certificate_is_counted_once_and_cannot_overlap_current_employment(self):
        self.regular_contract();terms,_=self.terms();period,_,_=self.save();basis,_,_=self.save('annual_basis',self.basis_details(period))
        earning,_,_=self.save('one_off_earning',self.claim_details(terms));details=self.forecast_details(basis,earning,terms)
        prior=dict(employer_name='Previous synthetic employer',employer_tax_number='111/222/33333',start='2026-01-01',end='2026-09-30',
                   running_taxable_minor=1800000,other_paid_minor=100000,evidence_ref=self.original)
        details.update(previous_employers=[prior],no_previous_employer_ref=None)
        value,_,_=self.save('annual_tax_forecast',details)
        self.assertEqual(value['plan']['annual_pay_before_minor'],2600000)
        self.problem(409,lambda:self.request('annual_tax_forecast',details|dict(previous_employers=[prior,prior])))
        self.problem(409,lambda:self.request('annual_tax_forecast',details|dict(previous_employers=[prior|dict(end='2026-10-16')])))


if __name__=='__main__':unittest.main()
