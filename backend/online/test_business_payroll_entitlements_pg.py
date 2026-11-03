"""Actual MFA/HTTP, two PG writers, old-data migration and payroll entitlement restore."""
import base64
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_foundation import BusinessFoundation
from business_organization import Organization
from business_payroll_entitlements import PayrollEntitlements, reference, protected_tables, validate_integrity
from business_payroll import Payroll
from core import Problem
from online import release, test_customer_execution_journey_pg as journey
from online.backup import backup
from online.restore import complete_restore, restore
from online.store import PostgresOffice, migrate
from test_payroll_de_2026 import profile
import test_business_payroll_accounts as accounts

fixture = journey.fixture
req = fixture.request


@unittest.skipUnless(fixture.DSN, 'Guarded disposable loopback PostgreSQL fixture required')
class PayrollEntitlementsPostgres(unittest.TestCase):
    reopen = journey.CustomerExecutionJourneyPostgres.reopen
    login = journey.CustomerExecutionJourneyPostgres.login
    call = journey.CustomerExecutionJourneyPostgres.call

    def setUp(self):
        self.previous = tuple(spec for spec in business_schema.registry() if spec.name != 'business_payroll_entitlements')
        if self._testMethodName.startswith('test_additive'):
            with patch.object(business_schema, 'registry', return_value=self.previous), patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in self.previous)):
                journey.CustomerExecutionJourneyPostgres.setUp(self)
        else:
            journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.owner = self.office.user(self.token)

    def sources(self,pay_basis='monthly'):
        uid = self.call('POST', '/users', dict(email='facts-pg-tech@example.test', password='Synthetic-facts-pg-password-123', role='technician'), status=201).json['id']
        tech = self.login('facts-pg-tech@example.test', 'Synthetic-facts-pg-password-123')
        employee = self.call('POST', '/business/employees', req(user_id=uid, name='Synthetic actual partial-month employee', weekly_minutes=600,
            hourly_cost_minor=9999, employment_from='2026-10-15', employment_to=None), status=201).json
        self.employee = employee
        original = b'%PDF-1.4\nSynthetic evidenced partial wage contract\n%%EOF'
        file = self.call('POST', '/business/personnel/files', req(employee_id=employee['id'], purpose='personnel', owner_visible=False,
            filename='actual-partial-contract.pdf', media_type='application/pdf', content_base64=base64.b64encode(original).decode())).json
        agreement = self.call('POST', '/business/personnel/agreements', req(employee_id=employee['id'], revision=0, effective_from='2026-01-01',
            employment_kind='minijob', pay_basis=pay_basis, amount_minor=1800 if pay_basis=='hourly' else 60300, currency='EUR', reference_file_id=file['id'])).json
        selected = self.call('POST', '/business/payroll/profiles', req(employee_id=employee['id'], revision=0, profile=profile('minijob'), source_file_id=file['id'], confirmed=True)).json
        current = self.call('GET', '/business/personnel/payroll-preparations/preview?employee_id=' + employee['id'] + '&month=2026-10').json
        prepared = self.call('POST', '/business/personnel/payroll-preparations', req(employee_id=employee['id'], month='2026-10', revision=0,
            source_hash=current['source_hash'], completeness_confirmed=True)).json
        identity = self.call('POST', '/business/payroll/account-records', req(employee_id=employee['id'], kind='identity', revision=0,
            source_file_id=file['id'], confirmed=True, details=accounts.PayrollAccountTests.identity_details(self, dict(profile=selected),
                employment_from='2026-10-15', employment_to=None))).json
        return dict(employee=employee, file=file, original=original, agreement=agreement, profile=selected, preparation=prepared, identity=identity, tech=tech)

    def workflow(self, data=None):
        data = data or self.sources(); employee = data['employee']
        terms_body = req(employee_id=employee['id'], employee_revision=employee['revision'], kind='employment_terms', revision=0, status='active',
            details=dict(employment_from='2026-10-15', employment_to=None, agreement_refs=[reference(data['agreement'])], proration_method='calendar_days_actual', reason='Actual original contractual proration'),
            source_file_ids=[data['file']['id']], confirmed=True)
        terms = self.call('POST', '/business/payroll/facts', terms_body).json
        file_ref = dict(id=data['file']['id'], revision=1, content_hash=data['file']['content_hash'])
        details = dict(case_key=uuid.uuid4().hex, employment_terms_ref=reference(terms), work_schedule_refs=[], preparation_refs=[],
            agreement_refs=[reference(data['agreement'])], sickness_history_ref=None,
            input=dict(**{'from':'2026-10-20','to':'2026-12-15'},employment_to=None,employment_continues=True,no_wage_claim=True,
                intervening_paid_days=[],evidence_refs=[file_ref],exceptions=[]),verification_note='Actual evidence-bound statutory continuation')
        input_ = dict(employee_id=employee['id'], employee_revision=employee['revision'], kind='unpaid_continuation', details=details, source_file_ids=[data['file']['id']])
        preview = self.call('POST', '/business/payroll/entitlements/preview', input_).json
        self.assertTrue(preview['can_calculate']); self.assertEqual(preview['plan']['continuation_windows'][0]['statutory_deadline'], '2026-11-19')
        command = req(**input_, revision=0, status='active', confirmed=True, preview_hash=preview['preview_hash'])
        saved = self.call('POST', '/business/payroll/entitlements', command).json
        self.assertEqual(self.call('POST', '/business/payroll/entitlements', command).json, saved)
        return data | dict(terms=terms, terms_body=terms_body, saved=saved, command=command, input=input_)

    def test_actual_mfa_http_fresh_rights_offline_denial_module_pause_and_runtime_acl(self):
        data = self.workflow(); object_path = '/business/payroll/entitlements/' + data['saved']['id']
        self.call('GET', object_path, token=data['tech'], status=403)
        device = self.call('POST', '/business/offline/access', {}, status=201).json['token']
        self.call('GET', object_path, token=device, status=403)
        self.call('POST', '/business/payroll/entitlements?ignored=1', data['command'], status=400)
        self.call('GET', object_path, {}, status=400)
        uid = self.call('POST', '/users', dict(email='facts-pg-reviewer@example.test', password='Synthetic-facts-reviewer-123', role='accountant'), status=201).json['id']
        token = self.login('facts-pg-reviewer@example.test', 'Synthetic-facts-reviewer-123')
        grants = BusinessFoundation(self.office)
        for name in ('personnel.read', 'personnel.approve'):
            grants.save_grant(self.owner, req(user_id=uid, permission=name, scope='*', effect='allow', revision=0))
        corrected = data['command'] | req(id=data['saved']['id'], revision=1, correction_reason='Independent exact evidence review')
        result = self.call('POST', '/business/payroll/entitlements', corrected, token=token).json
        grants.save_grant(self.owner, req(user_id=uid, permission='personnel.approve', scope='*', effect='deny', revision=1))
        self.call('POST', '/business/payroll/entitlements', corrected, token=token, status=403)
        grants.save_grant(self.owner, req(user_id=uid, permission='personnel.read', scope='*', effect='deny', revision=1))
        self.call('GET', object_path, token=token, status=403)
        organization = Organization(self.office); current = organization.get(self.owner)
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled']) for key, value in current['modules'].items()}; modules['personnel']['enabled'] = False
        organization.save(self.owner, req(revision=current['revision'], needs=current['needs'], modules=modules))
        self.assertEqual(self.call('POST', '/business/payroll/entitlements', data['command']).json, data['saved'])
        self.call('POST', '/business/payroll/entitlements', data['command'] | req(revision=2, id=result['id'], correction_reason='New action paused'), status=423)
        self.reopen()
        self.assertEqual(self.call('GET', object_path + '/history').json['items'], [data['saved'], result])
        for table in protected_tables():
            column = 'id' if table.endswith('events') else 'request_id'
            for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table, 'TRUNCATE ' + table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db: self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN, autocommit=True) as operator:
                for statement in ('UPDATE ' + table + ' SET ' + column + '=' + column, 'DELETE FROM ' + table):
                    with self.assertRaisesRegex(psycopg.Error, 'immutable payroll entitlement'):
                        with operator.transaction():
                            operator.execute('SET LOCAL ROLE "smartplan-migrator"'); operator.execute(statement)
        self.assertTrue(validate_integrity(self.office)); self.assertTrue(business_schema.validate_integrity(self.office))

    def test_two_pg_connections_accept_one_original_correction_and_deny_stale_fork(self):
        data = self.workflow(); barrier = threading.Barrier(2)
        command = data['command'] | req(id=data['saved']['id'], revision=1, correction_reason='Exact concurrent original correction')
        def writer(_):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return PayrollEntitlements(office).save(self.owner, command)
            finally: office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, range(2)))
        self.assertEqual(results[0], results[1]); self.assertEqual(results[0]['revision'], 2)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_entitlement_events WHERE kind='unpaid_continuation'").fetchone()[0], 2)
        self.call('POST', '/business/payroll/entitlements', command | req(), status=409)
        self.assertTrue(validate_integrity(self.office))

    def test_additive_old_hr_migration_actual_dump_restore_and_unchanged_originals(self):
        with patch.object(business_schema, 'registry', return_value=self.previous), patch.object(business_schema, 'MODULE_NAMES', tuple(spec.name for spec in self.previous)):
            data = self.sources('hourly')
            original_pdf = self.call('GET', '/business/personnel/payroll-preparations/' + data['preparation']['id'] + '/pdf').data
            before = release.snapshot_fingerprint(fixture.DSN); self.office.db.close()
        migrate(fixture.DSN, owner_role='smartplan-migrator', compatibility_mode='business', require_business_modules=True)
        after = release.snapshot_fingerprint(fixture.DSN)
        for table, value in before.items():
            if table not in ('business_schema_state', 'business_schema_migrations', 'business_schema_events'):
                self.assertEqual(after[table], value, table)
        release.secure_database(fixture.DSN, test_mode=True); self.reopen()
        data = self.workflow(data)
        details=dict(data['input']['details'])
        details.update(case_key=uuid.uuid4().hex,input=dict(employment_from='2026-10-15',employment_to=None,
            pay_basis='hourly',complete_from='2026-10-15',complete_through='2026-12-31',
            history_evidence_refs=[dict(id=data['file']['id'],revision=1,content_hash=data['file']['content_hash'])],
            episodes=[dict(id=uuid.uuid4().hex,**{'from':'2026-11-14','to':'2026-12-31'},onset='non_workday',
                first_scheduled_day='2026-11-16',continuation_group=uuid.uuid4().hex,recovery_before=True,unculpable=True,
                evidence_refs=[dict(id=data['file']['id'],revision=1,content_hash=data['file']['content_hash'])])]))
        sickness_input=dict(data['input'],kind='sickness_history',details=details)
        preview=self.call('POST','/business/payroll/entitlements/preview',sickness_input).json
        sickness_command=req(**sickness_input,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        sickness=self.call('POST','/business/payroll/entitlements',sickness_command).json
        self.assertEqual(sickness['plan']['rule_version'],'de_2026_sickness_v2')
        self.assertEqual(sickness['plan']['episodes'][0]['entitlement_to'],'2026-12-26')
        additional=[]
        for version in ('de_2026_sickness_phases_v3','de_2026_sickness_start_v4'):
            revised=deepcopy(details);revised['case_key']=uuid.uuid4().hex
            source=revised['input'];first=source['episodes'][0]
            if version.endswith('v3'):
                first['to']='2026-12-05'
                source['episodes'].append(dict(deepcopy(first),id=uuid.uuid4().hex,continuation_group=uuid.uuid4().hex,
                    **{'from':'2026-11-20','to':'2026-12-31'},onset='during_existing_au',first_scheduled_day=None,recovery_before=False))
            else:
                first.update(**{'from':'2026-10-10','to':'2026-12-31'},onset='before_employment',first_scheduled_day=None)
                source['employment_commencement']=dict(contract_concluded_on='2026-10-01',evidence_refs=deepcopy(source['history_evidence_refs']))
            source['prevention_cases']=[dict(id=uuid.uuid4().hex,episode_ids=[item['id'] for item in source['episodes']],evidence_refs=deepcopy(source['history_evidence_refs']))]
            input_=dict(sickness_input,details=revised)
            preview_=self.call('POST','/business/payroll/entitlements/preview',input_).json
            command_=req(**input_,revision=0,status='active',confirmed=True,preview_hash=preview_['preview_hash'])
            saved_=self.call('POST','/business/payroll/entitlements',command_).json
            self.assertEqual(saved_['plan']['rule_version'],version)
            self.assertEqual(saved_['plan']['prevention_cases'][0]['statutory_deadline'],'2026-12-26' if version.endswith('v3') else '2026-12-23')
            additional.append((saved_,command_))
        self.office.db.close(); target = make_conninfo(fixture.DSN, dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN, target, test_mode=True)
        with psycopg.connect(fixture.DSN, autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-entitlements-backup-') as directory:
                archive = backup(fixture.DSN, directory)
                restored = restore(archive, fixture.DSN, target, privileged_operator=True, test_mode=True)
                self.assertTrue(restored['restore_pending'])
            runtime = make_conninfo(self.runtime, dbname='smartplan_release_check')
            verifier = PostgresOffice(runtime, allow_restore_pending=True)
            try: self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally: verifier.db.close()
            restored_office = PostgresOffice(runtime)
            try:
                api = PayrollEntitlements(restored_office)
                self.assertEqual(api.save(self.owner, data['command']), data['saved'])
                self.assertEqual(api.save(self.owner,sickness_command),sickness)
                self.assertEqual(api.resolve_entitlement_case(self.owner,data['employee']['id'],reference(sickness)),sickness)
                for saved_,command_ in additional:
                    self.assertEqual(api.save(self.owner,command_),saved_)
                    self.assertEqual(api.resolve_entitlement_case(self.owner,data['employee']['id'],reference(saved_)),saved_)
                self.assertEqual(api.resolve_entitlement_case(self.owner, data['employee']['id'], reference(data['saved'])), data['saved'])
                self.assertEqual(bytes(api.hr._file(data['file']['id'])['original']), data['original'])
                self.assertEqual(api.hr.export(self.owner, data['preparation']['id'], 'pdf')[0], original_pdf)
                self.assertTrue(validate_integrity(restored_office)); self.assertTrue(business_schema.validate_integrity(restored_office))
            finally: restored_office.db.close()
        finally:
            with psycopg.connect(fixture.DSN, autocommit=True) as operator:
                operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()
