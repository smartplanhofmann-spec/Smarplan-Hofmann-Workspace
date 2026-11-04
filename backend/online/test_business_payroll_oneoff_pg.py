"""Real globally registered Source4 MFA/PG, claim ownership and restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import tempfile
import threading
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_api
import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_facts import reference
from business_payroll_oneoff_cases import PayrollOneoffCases, RULE_VERSION, TABLES, _consumption_row
from core import Problem
from payroll_travel_recording import validate_tax_recording
from online import release, test_business_payroll_calculations_pg as running_pg
from online.backup import backup
from online.restore import restore, complete_restore
from online.store import PostgresOffice

fixture = running_pg.fixture
journey = running_pg.journey
req = fixture.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable loopback PostgreSQL fixture required')
class OneoffPayrollPostgres(unittest.TestCase):
    reopen = journey.CustomerExecutionJourneyPostgres.reopen
    login = journey.CustomerExecutionJourneyPostgres.login
    call = journey.CustomerExecutionJourneyPostgres.call
    sources = running_pg.CalculationPayrollPostgres.sources

    def setUp(self):
        self.assertEqual(business_schema.MODULE_NAMES.count('business_payroll_oneoff_cases'), 1)
        self.assertEqual(business_api.MODULES.count('business_payroll_oneoff_cases'), 1)
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)

    def workflow(self, *, save_case=True):
        data = running_pg.CalculationPayrollPostgres.workflow(self)
        employee = data['employee']; case = data['case']; terms = case['sources']['employment_terms'][0]
        original = dict(id=data['file']['id'], revision=1, content_hash=data['file']['content_hash'])
        common = dict(employee_id=employee['id'], employee_revision=employee['revision'], source_file_ids=[data['file']['id']])
        original_details = dict(employer_identity_ref=reference(data['identity']), verification_note='Actual synthetic PG original annual evidence')

        def annual(kind, details):
            proposal = dict(common, kind=kind, details=original_details | details)
            preview = self.call('POST', '/business/payroll/annual-facts/preview', proposal).json
            return self.call('POST', '/business/payroll/annual-facts', req(**proposal, revision=0,
                status='active', confirmed=True, preview_hash=preview['preview_hash'])).json

        basis = annual('annual_basis', dict(year=2026, coverage_to='2026-10-31', as_of_date='2026-10-31',
            payroll_run_refs=[], payroll_payment_refs=[], imported_period_refs=[], imported_one_off_refs=[],
            current_calculation_case_ref=reference(case), completeness_confirmed=True,
            gaps=[dict(start='2026-01-01', end='2026-09-30', reason='not_employed', evidence_ref=original)]))
        earning = annual('one_off_earning', dict(claim_key=original, claim_reference='PG documented contractual bonus position 1',
            planned_receipt_date='2026-10-31', amount_minor=50000, tax_classification='other_payment',
            social_classification='one_off_remuneration', section_key='regular', employment_terms_refs=[reference(terms)],
            claim_periods=[dict(start='2026-10-15', end='2026-10-31', evidence_ref=original)], document_refs=[original]))
        forecast = annual('annual_tax_forecast', dict(annual_basis_ref=reference(basis), receipt_date='2026-10-31',
            identity_ref=reference(data['identity']), current_one_off_ref=reference(earning), previous_employers=[],
            no_previous_employer_ref=original, other_tax_receipt_refs=[], remaining_periods=[dict(month=month,
                employment_terms_ref=reference(terms), agreement_refs=[reference(data['agreement'])], work_schedule_ref=None)
                for month in ('2026-11','2026-12')]))
        details = dict(month='2026-10', running_calculation_case_ref=reference(case), one_off_earning_ref=reference(earning),
            current_annual_basis_ref=reference(basis), previous_annual_basis_ref=None, annual_tax_forecast_ref=reference(forecast),
            verification_note='Actual Source4 protected original and annual assignment inspected')
        proposal = dict(common, kind='one_off_case', rule_version=RULE_VERSION, source_contract_version=1, details=details)
        preview = self.call('POST', '/business/payroll/one-off-cases/preview', proposal).json
        self.assertTrue(preview['can_calculate'], preview['plan']['blockers'])
        command = req(**proposal, revision=0, status='active', confirmed=True, preview_hash=preview['preview_hash'])
        data.update(oneoff_command=command, earning=earning, annual_basis=basis)
        if save_case:
            data['oneoff_case'] = self.call('POST', '/business/payroll/one-off-cases', command).json
            inputs = dict(employee_id=employee['id'], source_schema_version=4, one_off_case_ref=reference(data['oneoff_case']))
            preview = self.call('POST', '/business/payroll/preview', inputs).json
            self.assertTrue(preview['can_finalize'])
            data['run_command'] = req(**inputs, revision=0, confirmed=True, preview_hash=preview['preview_hash'],
                accepted_scope=preview['calculation']['scope'])
        return data

    def test_two_real_finalize_writers_create_one_claim_consumption_with_private_mfa_acl(self):
        data = self.workflow(); barrier = threading.Barrier(2)
        def writer(_):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10); return Payroll(office).finalize(self.owner, data['run_command'])
            finally: office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool: runs = list(pool.map(writer, range(2)))
        self.assertEqual(runs[0], runs[1]); run = runs[0]
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + TABLES[2]).fetchone()[0], 1)
        proof = _consumption_row(self.office, run['id'], run['revision'])
        self.assertEqual(proof['payload']['earning_ref'], reference(data['earning']))
        self.assertEqual(proof['payload']['amount_minor'], 50000)
        path = '/business/payroll/one-off-cases/' + data['oneoff_case']['id']
        self.call('GET', path, token=data['tech'], status=403)
        offline = self.call('POST', '/business/offline/access', {}, status=201).json['token']
        self.call('GET', path, token=offline, status=403)
        self.call('POST', '/business/payroll/one-off-cases?ignored=1', data['oneoff_command'], status=400)
        self.call('GET', path, {}, status=400)
        self.call('DELETE', '/business/payroll/one-off-cases', {}, status=405)
        for table in TABLES:
            column = 'id' if table.endswith('events') else 'request_id' if table.endswith('requests') else 'run_id'
            for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db: self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN, autocommit=True) as operator:
                for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                    with self.assertRaisesRegex(psycopg.Error, 'immutable payroll oneoff'):
                        with operator.transaction():
                            operator.execute('SET LOCAL ROLE "smartplan-migrator"'); operator.execute(statement)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_distinct_parallel_first_commands_cannot_reserve_same_claim_twice(self):
        data = self.workflow(save_case=False); barrier = threading.Barrier(2)
        def writer(index):
            office = PostgresOffice(self.runtime)
            command = data['oneoff_command'] | req()
            try:
                barrier.wait(timeout=10)
                try: return ('accepted', PayrollOneoffCases(office).save(self.owner, command), command)
                except Problem as error: return ('rejected', error.status, command)
            finally: office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(writer, range(2)))
        self.assertEqual(sorted(value[0] for value in outcomes), ['accepted','rejected'])
        accepted = next(value for value in outcomes if value[0]=='accepted')
        self.assertEqual(next(value[1] for value in outcomes if value[0]=='rejected'), 409)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + TABLES[0]).fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM ' + TABLES[1]).fetchone()[0], 1)
        self.assertEqual(self.call('POST','/business/payroll/one-off-cases',accepted[2]).json, accepted[1])
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_backup_restore_retains_original_run_receipts_consumption_and_pdf(self):
        self._actual_backup_restore(include_annual=False)

    def test_actual_paid_source4_annual_projection_survives_backup_restore(self):
        self._actual_backup_restore(include_annual=True)

    def _actual_backup_restore(self, *, include_annual):
        data = self.workflow(); run = self.call('POST', '/business/payroll/runs', data['run_command']).json
        proof = _consumption_row(self.office, run['id'], run['revision'])
        tax_recording = validate_tax_recording(self.office, run)
        actual = run['calculation']['net_minor'] - run['calculation']['net_deductions_minor']
        payment_details = running_pg.entitlement_pg.accounts.PayrollAccountTests.payment_details(self, run, data['identity'],
            payments=[dict(paid_on=run['calculation']['one_off_details']['receipt_date'], amount_minor=actual,
                payment_reference='SYN-PG-V6-ACTUAL-NET-001')])
        payment_command = req(employee_id=data['employee']['id'], kind='payment', revision=0,
            source_file_id=data['file']['id'], confirmed=True, details=payment_details)
        payment = self.call('POST', '/business/payroll/account-records', payment_command).json
        annual = annual_command = None
        if include_annual:
            details = deepcopy(data['annual_basis']['details'])
            details.update(as_of_date='2026-11-01', current_calculation_case_ref=None,
                payroll_run_refs=[reference(run)], payroll_payment_refs=[reference(payment)])
            proposal = dict(employee_id=data['employee']['id'], employee_revision=data['employee']['revision'],
                kind='annual_basis', details=details, source_file_ids=[data['file']['id']])
            preview = self.call('POST', '/business/payroll/annual-facts/preview', proposal).json
            annual_command = req(**proposal, revision=0, status='active', confirmed=True,
                preview_hash=preview['preview_hash'])
            annual = self.call('POST', '/business/payroll/annual-facts', annual_command).json
            self.assertEqual(annual['plan']['earlier_other_taxable_minor'], 50000)
            self.assertEqual(len(annual['plan']['projection']['prior_one_offs']), 1)
            self.assertEqual(annual['plan']['projection']['prior_one_offs'][0]['bases_minor'],
                dict.fromkeys(('health', 'care', 'pension', 'unemployment'), 50000))
            compact = annual['sources']['payroll_runs'][0]
            self.assertEqual(compact['projection_format'], 'source4_annual_reference_v1')
            self.assertNotIn('calculation', compact)
            self.assertNotIn('sources', annual['sources']['payroll_payments'][0])
            self.call('GET', '/business/payroll/annual-facts/' + annual['id'], token=data['tech'], status=403)
            self.assertTrue(business_schema.validate_integrity(self.office))
        ledger_query = dict(employee_id=data['employee']['id'], year='2026')
        ledger = self.call('GET', '/business/payroll/ledger?employee_id=' + data['employee']['id'] + '&year=2026').json['ledger']
        ledger_pdf = Payroll(self.office).export_ledger(self.owner, ledger_query | dict(snapshot_hash=ledger['snapshot_hash']), 'pdf')[0]
        pdf = self.call('GET', '/business/payroll/runs/' + run['id'] + '/pdf').data
        self.office.db.close(); target = make_conninfo(fixture.DSN, dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN, target, test_mode=True)
        with psycopg.connect(fixture.DSN, autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-v6-backup-') as directory:
                archive = backup(fixture.DSN, directory)
                self.assertTrue(restore(archive, fixture.DSN, target, privileged_operator=True, test_mode=True)['restore_pending'])
            runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
            verifier = PostgresOffice(runtime, allow_restore_pending=True)
            try: self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally: verifier.db.close()
            restored = PostgresOffice(runtime)
            try:
                payroll = Payroll(restored); api = PayrollOneoffCases(restored)
                self.assertEqual(payroll.finalize(self.owner, data['run_command']), run)
                self.assertEqual(api.save(self.owner, data['oneoff_command']), data['oneoff_case'])
                self.assertEqual(PayrollAccounts(restored).save(self.owner, payment_command), payment)
                if include_annual:
                    annual_api = PayrollAnnualBasis(restored)
                    self.assertEqual(annual_api.save(self.owner, annual_command), annual)
                    self.assertEqual(annual_api.resolve(self.owner, data['employee']['id'], reference(annual)), annual)
                self.assertEqual(_consumption_row(restored, run['id'], run['revision']), proof)
                self.assertEqual(validate_tax_recording(restored, run), tax_recording)
                self.assertEqual(payroll.ledger(self.owner, ledger_query)['ledger'], ledger)
                self.assertEqual(payroll.export_ledger(self.owner, ledger_query | dict(snapshot_hash=ledger['snapshot_hash']), 'pdf')[0], ledger_pdf)
                self.assertEqual(payroll.export(self.owner, run['id'], 'pdf')[0], pdf)
                self.assertEqual(bytes(payroll.hr._file(data['file']['id'])['original']), data['original'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally: restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN, autocommit=True) as operator:
                operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()


if __name__ == '__main__': unittest.main()
