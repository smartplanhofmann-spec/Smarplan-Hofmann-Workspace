"""Real MFA/HTTP, concurrent V2 source writers and full PostgreSQL restore."""
from concurrent.futures import ThreadPoolExecutor
import time
import unittest
from cryptography.fernet import Fernet

from business_payroll_facts import reference
from business_payroll_factor_annual_basis import FactorAnnualBasis
from business_payroll_annual_basis import validate_annual_sources
from online import test_business_payroll_factor_claims_pg as original
from online.test_postgres_accounting_components_integration import disposable_restore
from online.store import PostgresOffice
from online.web import create_app
from online.auth import totp

fixture=original.fixture
req=original.req
GOLDEN=original.GOLDEN


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL required')
class FactorAnnualPostgres(unittest.TestCase):
    setUp=original.FactorClaimsPostgres.setUp
    reopen=original.FactorClaimsPostgres.reopen
    call=original.FactorClaimsPostgres.call
    login=original.FactorClaimsPostgres.login
    sources=original.FactorClaimsPostgres.sources

    def create_factor_case(self):
        data=self.sources();employee=data['employee'];proof=data['file']
        employee=self.call('POST','/business/employees',req(id=employee['id'],revision=employee['revision'],
            employment_from='2026-10-01',employment_to=None),status=201).json
        agreement=self.call('POST','/business/personnel/agreements',req(employee_id=employee['id'],
            id=data['agreement']['id'],revision=data['agreement']['revision'],effective_from='2026-01-01',
            employment_kind='regular',pay_basis='monthly',amount_minor=500000,currency='EUR',
            reference_file_id=proof['id'],correction_reason='Actual original regular factor salary')).json
        profile=self.call('POST','/business/payroll/profiles',req(employee_id=employee['id'],id=data['profile']['id'],
            revision=data['profile']['revision'],profile=GOLDEN['profile']['profile'],source_file_id=proof['id'],
            confirmed=True,correction_reason='Actual original class IV factor and insurance')).json
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',
            revision=0,source_file_id=proof['id'],confirmed=True,
            details=dict(GOLDEN['identity']['details'],profile_id=profile['id'],profile_revision=profile['revision']))).json
        preview=self.call('GET','/business/personnel/payroll-preparations/preview?employee_id='+employee['id']+'&month=2026-10').json
        preparation=self.call('POST','/business/personnel/payroll-preparations',req(employee_id=employee['id'],
            id=data['preparation']['id'],revision=data['preparation']['revision'],month='2026-10',
            source_hash=preview['source_hash'],completeness_confirmed=True,
            correction_reason='Actual original full-month factor employment')).json
        common=dict(employee_id=employee['id'],employee_revision=employee['revision'],source_file_ids=[proof['id']])
        original=dict(id=proof['id'],revision=1,content_hash=proof['content_hash'])
        terms=self.call('POST','/business/payroll/facts',req(**common,kind='employment_terms',revision=0,status='active',
            confirmed=True,details=dict(employment_from='2026-10-01',employment_to=None,
                agreement_refs=[reference(agreement)],proration_method='calendar_days_actual',reason='Actual original full-month contract'))).json
        period_details=dict(month='2026-10',preparation_ref=reference(preparation),employment_terms_ref=reference(terms),
            work_schedule_ref=None,profile_refs=[reference(profile)],identity_refs=[reference(identity)],
            tax_treatment='domestic_running_wages',entitlement_decisions=[],verification_note='Actual original full factor month')
        preview=self.call('POST','/business/payroll/periods/preview',dict(common,details=period_details)).json
        period=self.call('POST','/business/payroll/facts',req(**common,kind='period_case',revision=0,status='active',
            confirmed=True,details=period_details,preview_hash=preview['preview_hash'])).json
        claim_details=dict(case_key=req()['request_id'],employment_terms_ref=reference(terms),work_schedule_refs=[],
            preparation_refs=[],agreement_refs=[reference(agreement)],sickness_history_ref=None,
            input=dict(**{'from':'2026-10-20','to':'2026-10-24'},employment_to=None,employment_continues=True,
                no_wage_claim=True,intervening_paid_days=[],evidence_refs=[original],exceptions=[]),
            verification_note='Actual five unpaid days independently evidenced')
        proposal=dict(common,kind='unpaid_continuation',details=claim_details)
        preview=self.call('POST','/business/payroll/entitlements/preview',proposal).json
        claim=self.call('POST','/business/payroll/entitlements',req(**proposal,revision=0,status='active',
            confirmed=True,preview_hash=preview['preview_hash'])).json
        proposal=dict(common,kind='calculation_case',rule_version='de_2026_factor_claims_month_v12',source_contract_version=4,
            details=dict(month='2026-10',period_case_ref=reference(period),employment_terms_refs=[reference(terms)],
                profile_refs=[reference(profile)],identity_refs=[reference(identity)],segment_events=[],thirty_day_rule=None,
                entitlement_case_refs=[reference(claim)],travel_settlement_refs=[],flat_tax_decision=None,
                verification_note='Actual original full factor month and complete independent P4 claims'))
        preview=self.call('POST','/business/payroll/calculation-cases/preview',proposal).json
        case_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        case=self.call('POST','/business/payroll/calculation-cases',case_command).json
        return dict(employee=employee,profile=profile,identity=identity,terms=terms,case=case,original=original,common=common,
            tech=data['tech'],file=proof,agreement=agreement)

    def test_actual_v2_mfa_concurrent_nonce_originals_full_restore_and_old_session_revoke(self):
        data=self.create_factor_case();actor=self.office.user(self.token)
        details=dict(employer_identity_ref=reference(data['identity']),verification_note='Actual V2 factor annual original reviewed',
            year=2026,coverage_to='2026-10-31',as_of_date='2026-10-31',payroll_run_refs=[],payroll_payment_refs=[],
            imported_period_refs=[],imported_one_off_refs=[],current_calculation_case_ref=reference(data['case']),
            gaps=[dict(start='2026-01-01',end='2026-09-30',reason='not_employed',evidence_ref=data['original'])],completeness_confirmed=True)
        proposal=dict(data['common'],kind='annual_basis',details=details)
        self.call('POST','/business/payroll/annual-facts/preview',proposal,status=409)
        preview=self.call('POST','/business/payroll/annual-facts/factor-v2/preview',proposal).json
        command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:return FactorAnnualBasis(office).save(actor,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:first,second=list(pool.map(writer,range(2)))
        self.assertEqual(first,second);self.assertTrue(validate_annual_sources(self.office,first))
        self.assertEqual(first['sources']['current_calculation_case'],data['case'])
        self.assertEqual(first['plan']['running_taxable_minor'],419355)
        self.assertEqual(self.call('POST','/business/payroll/annual-facts/factor-v2',command).json,first)
        self.call('POST','/business/payroll/annual-facts',command,status=409)
        self.call('POST','/business/payroll/annual-facts/factor-v2/preview?ignored=1',proposal,status=400)
        secret=Fernet(self.key).decrypt(self.office.db.execute('SELECT secret FROM mfa WHERE user_id=?',(actor['id'],)).fetchone()['secret'].encode()).decode()
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            restored=PostgresOffice(runtime)
            try:
                api=FactorAnnualBasis(restored)
                self.assertEqual(api.get(actor,first['id']),first)
                self.assertTrue(validate_annual_sources(restored,first))
                app=create_app(office=restored,key=self.key,host='office.example.test',instance_id=self.instance,storage_config=self.storage_config)
                client=app.test_client();base='https://office.example.test'
                path='/api/v1/business/payroll/annual-facts/factor-v2/'+first['id']
                self.assertEqual(client.get(path,headers={'Authorization':'Bearer '+self.token},base_url=base).status_code,401)
                pending=client.post('/api/v1/login',json=dict(email=actor['email'],password='Synthetic-owner-password-123'),base_url=base).json
                authenticated=client.post('/api/v1/login/verify',json=dict(challenge=pending['challenge'],code=totp(secret,int(time.time()//30)+1)),base_url=base)
                self.assertEqual(authenticated.status_code,200)
                response=client.get(path,headers={'Authorization':'Bearer '+authenticated.json['token']},base_url=base)
                self.assertEqual(response.status_code,200);self.assertEqual(response.json,first)
            finally:restored.db.close()
