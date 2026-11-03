"""Independent adversarial history/source tests, sharing setup but no test cases."""
from copy import deepcopy
import json
import unittest

import business_payroll_facts as facts
from business_foundation import BusinessFoundation
from business_personnel_workflow import _sha
from core import canonical, Problem
import test_business_payroll_facts as fixtures
from test_business_planning import BusinessFixture, rid


class IndependentPayrollFactsReviewTests(BusinessFixture, unittest.TestCase):
    setUp = fixtures.PayrollFactTests.setUp
    case = fixtures.PayrollFactTests.case
    identity_details = fixtures.PayrollFactTests.identity_details
    save_account = fixtures.PayrollFactTests.save_account
    account_api = fixtures.PayrollFactTests.account_api
    terms_details = fixtures.PayrollFactTests.terms_details
    body = fixtures.PayrollFactTests.body
    terms = fixtures.PayrollFactTests.terms
    period_details = fixtures.PayrollFactTests.period_details
    preview_body = fixtures.PayrollFactTests.preview_body
    period = fixtures.PayrollFactTests.period
    pause = fixtures.PayrollFactTests.pause

    def rewrite_with_consistent_hashes(self, saved, mutate):
        """Emulate corrupted import: rewrite event AND its matching receipt.

        The ordinary database prevents these mutations. Deliberately removing
        the guards demonstrates that validation checks semantics independently.
        """
        row = dict(self.api._row(saved['id'], saved['revision']))
        payload, sources = json.loads(row['payload_json']), json.loads(row['sources_json'])
        mutate(payload, sources)
        row['source_hash'] = _sha(sources)
        envelope = {key:value for key,value in row.items()
                    if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources)
        changed_hash = _sha(envelope)
        for name in ('business_payroll_fact_events_update_guard','business_payroll_fact_requests_update_guard'):
            self.office.db.execute('DROP TRIGGER IF EXISTS '+name)
        self.office.db.execute('UPDATE business_payroll_fact_events SET payload_json=?,sources_json=?,source_hash=?,content_hash=? WHERE id=? AND revision=?',
            (canonical(payload),canonical(sources),row['source_hash'],changed_hash,saved['id'],saved['revision']))
        self.office.db.execute('UPDATE business_payroll_fact_requests SET fact_content_hash=? WHERE fact_id=? AND fact_revision=?',
            (changed_hash,saved['id'],saved['revision']))
        altered = self.api._get(saved['id'],saved['revision'])
        self.assertEqual(altered['content_hash'],changed_hash)
        return altered

    def test_rehashed_plan_and_matching_receipt_still_fail_source_reconstruction(self):
        saved, _, _ = self.period()
        def mutate(payload, sources):
            payload['plan']['gross_minor'] += 1
            plan = dict(payload['plan'])
            plan.pop('plan_hash'); plan.pop('can_confirm'); plan.pop('can_calculate')
            payload['plan']['plan_hash'] = _sha(plan)
            payload['preview_hash'] = _sha(dict(source_snapshot=sources,plan=payload['plan']))
        altered = self.rewrite_with_consistent_hashes(saved,mutate)
        with self.assertRaises(ValueError): facts.validate_fact_sources(self.office,altered)
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)

    def test_recomputed_plan_cannot_launder_a_modified_bound_payroll_profile(self):
        saved, _, _ = self.period()
        def mutate(payload, sources):
            sources['profiles'][0]['profile']['minijob_rv_exempt'] = True
            payload['plan'] = facts.build_plan(sources)
            payload['preview_hash'] = _sha(dict(source_snapshot=sources,plan=payload['plan']))
        altered = self.rewrite_with_consistent_hashes(saved,mutate)
        self.assertTrue(altered['sources']['profiles'][0]['profile']['minijob_rv_exempt'])
        with self.assertRaises(ValueError): facts.validate_fact_sources(self.office,altered)
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)

    def test_rehashed_file_metadata_cannot_replace_archived_original_metadata(self):
        saved, _ = self.terms()
        def mutate(payload, sources):
            sources['source_files'][0]['employee_id'] = '0'*32
        altered = self.rewrite_with_consistent_hashes(saved,mutate)
        with self.assertRaises(ValueError): facts.validate_fact_sources(self.office,altered)
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)

    def test_replay_checks_accepted_employee_revision_not_only_command_digest(self):
        saved, body = self.terms()
        # A later revision really exists. Reject the altered acceptance even
        # when it cannot be detected merely by checking revision existence.
        later = self.call(self.planning,'save_employee',self.owner,dict(request_id=rid(),
            id=self.employee['id'],revision=self.employee['revision'],weekly_minutes=2300))
        def mutate(payload, sources):
            sources['employee']['revision'] = later['revision']
        self.rewrite_with_consistent_hashes(saved,mutate)
        with self.assertRaises((Problem,ValueError)):
            self.api.save(self.owner,body)

    def test_original_employee_user_binding_survives_consistent_rehash(self):
        saved, body = self.terms()
        def mutate(payload, sources):
            sources['employee']['user_id'] = self.owner['id']
        altered = self.rewrite_with_consistent_hashes(saved,mutate)
        with self.assertRaises(ValueError): facts.validate_fact_sources(self.office,altered)
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)
        with self.assertRaises((Problem,ValueError)): self.api.save(self.owner,body)

    def test_corrected_schedule_keeps_original_period_snapshot_but_stales_fresh_use(self):
        details = dict(month='2026-10',days=[dict(date=f'2026-10-{day:02}',
            scheduled_seconds=28800 if day < 20 else 0,workplace='Synthetic office',
            federal_state='BW') for day in range(1,32)],reason='Original signed schedule')
        schedule_body = self.body('work_schedule',details)
        schedule = self.api.save(self.owner,schedule_body)
        terms = self.api.save(self.owner,self.body('employment_terms',
            self.terms_details() | dict(proration_method='scheduled_seconds')))
        period_details = self.period_details(terms,work_schedule_ref=facts.reference(schedule))
        preview = self.api.preview(self.owner,self.preview_body(period_details))
        body = self.body('period_case',period_details,preview_hash=preview['preview_hash'])
        saved = self.api.save(self.owner,body)
        corrected = deepcopy(details)
        corrected['days'][14]['scheduled_seconds'] = 14400
        self.api.save(self.owner,self.body('work_schedule',corrected,id=schedule['id'],revision=1,
            correction_reason='Later corrected signed schedule'))
        self.assertEqual(self.api.save(self.owner,body),saved)
        self.assertEqual(self.api.save(self.owner,schedule_body),schedule)
        self.assertEqual(self.api.resolve_period_case(self.owner,self.employee['id'],facts.reference(saved),fresh=False),saved)
        self.problem(409,lambda:self.api.resolve_period_case(self.owner,self.employee['id'],facts.reference(saved)))
        self.assertEqual(saved['sources']['work_schedule']['details']['days'][14]['scheduled_seconds'],28800)
        self.assertTrue(facts.validate_integrity(self.office))

    def test_personnel_write_does_not_grant_monthly_approval_and_replay_uses_fresh_grants(self):
        uid = self.office.add_user('independent-facts@example.test','Synthetic-facts-password-456','technician')
        actor = dict(id=uid,email='independent-facts@example.test',role='technician')
        foundation = BusinessFoundation(self.office)
        for permission in ('personnel.read','personnel.write'):
            foundation.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        terms, _ = self.terms()
        details = self.period_details(terms)
        preview = self.api.preview(actor,self.preview_body(details))
        body = self.body('period_case',details,preview_hash=preview['preview_hash'])
        self.problem(403,lambda:self.api.save(actor,body))
        foundation.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission='personnel.approve',scope='*',effect='allow',revision=0))
        saved = self.api.save(actor,body)
        foundation.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        self.problem(403,lambda:self.api.save(actor,body))
        self.assertEqual(self.api.get(actor,saved['id']),saved)
        self.assertTrue(facts.validate_integrity(self.office))

    def test_archiving_after_stammdaten_change_preserves_old_revision_and_receipts(self):
        saved, body, _ = self.period()
        self.employee = self.call(self.planning,'save_employee',self.owner,dict(request_id=rid(),
            id=self.employee['id'],revision=self.employee['revision'],name='Later legitimate employee name'))
        void_body = body | dict(request_id=rid(),id=saved['id'],revision=1,status='void',
            employee_revision=self.employee['revision'],correction_reason='Archive superseded facts')
        archived = self.api.save(self.owner,void_body)
        self.pause()
        self.assertEqual(self.api.save(self.owner,body),saved)
        self.assertEqual(self.api.save(self.owner,void_body),archived)
        self.assertEqual(archived['sources'],saved['sources'])
        self.assertEqual(self.api.get(self.owner,saved['id'],history=True)['items'],[saved,archived])
        self.assertTrue(facts.validate_integrity(self.office))

    def test_profile_after_actual_exit_is_not_required_for_earlier_payroll_period(self):
        self.employee = self.call(self.planning,'save_employee',self.owner,dict(request_id=rid(),
            id=self.employee['id'],revision=self.employee['revision'],employment_to='2026-10-20'))
        prepared = self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month='2026-10'))
        old = self.data['preparation']
        self.data['preparation'] = self.hr.close_preparation(self.owner,dict(request_id=rid(),
            id=old['id'],revision=old['revision'],employee_id=self.employee['id'],month='2026-10',
            source_hash=prepared['source_hash'],completeness_confirmed=True,
            correction_reason='Actual employment end recorded'))
        self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],revision=0,
            profile=self.data['profile']['profile'] | dict(effective_from='2026-10-25'),
            source_file_id=self.data['file']['id'],confirmed=True))
        terms = self.api.save(self.owner,self.body('employment_terms',
            self.terms_details() | dict(employment_to='2026-10-20')))
        details = self.period_details(terms)
        preview = self.api.preview(self.owner,self.preview_body(details))
        self.assertTrue(preview['can_calculate'],preview['plan']['blockers'])
        self.assertEqual(preview['plan']['employment_intervals'],[
            dict(start='2026-10-15',end='2026-10-20',calendar_days=6)])
        self.assertEqual(preview['source_snapshot']['profiles'],[self.data['profile']])

    def test_finalized_run_keeps_original_after_fact_void_and_module_pause(self):
        saved, fact_body, _ = self.period()
        inputs = dict(source_schema_version=2,employee_id=self.employee['id'],
            period_case_ref=facts.reference(saved))
        preview = self.payroll.preview(self.owner,inputs)
        body = inputs | dict(request_id=rid(),preview_hash=preview['preview_hash'],
            accepted_scope=preview['calculation']['scope'],confirmed=True,revision=0)
        run = self.payroll.finalize(self.owner,body)
        original_json = self.payroll.export(self.owner,run['id'],'json')[0]
        original_pdf = self.payroll.export(self.owner,run['id'],'pdf')[0]
        self.api.save(self.owner,fact_body | dict(request_id=rid(),id=saved['id'],revision=1,
            status='void',correction_reason='Withdrawn facts need a new explicit correction'))
        self.problem(409,lambda:self.payroll.preview(self.owner,inputs))
        self.pause()
        self.assertEqual(self.payroll.finalize(self.owner,body),run)
        self.assertEqual(self.payroll.export(self.owner,run['id'],'json','1')[0],original_json)
        self.assertEqual(self.payroll.export(self.owner,run['id'],'pdf','1')[0],original_pdf)
        self.problem(403,lambda:self.payroll.get(self.technician,'run',run['id']))


if __name__ == '__main__':
    unittest.main()
