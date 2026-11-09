"""Independent negative boundaries; intentionally damaged data is never a release."""
from copy import deepcopy
import unittest

from core import Problem, canonical
from business_payroll import Payroll, _sha, validate_integrity as validate_payroll
from business_payroll_facts import reference
from business_payroll_calculation_cases import validate_integrity as validate_cases
import test_business_payroll_accounts as accounts
from test_business_payroll import rid
from test_payroll_individual_minijob import IndividualMinijobFixture


class MinijobV11IndependentReview(unittest.TestCase):
    def _replace_identity(self, fixture, details, source_file):
        f = fixture.f
        prior_identity = fixture.identity
        fixture.identity = fixture.accounts.save(f.owner, dict(request_id=rid(),
            employee_id=f.employee['id'], kind='identity', id=prior_identity['id'],
            revision=prior_identity['revision'], source_file_id=source_file, confirmed=True,
            correction_reason='Explicit correction of the original identity evidence', details=details))
        before = fixture.period
        details = dict(before['details'], identity_refs=[reference(fixture.identity)])
        proposal = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            details=details, source_file_ids=[fixture.data['file']['id']])
        preview = fixture.facts.preview(f.owner, proposal)
        fixture.period = fixture.facts.save(f.owner, dict(proposal, request_id=rid(), kind='period_case',
            id=before['id'], revision=before['revision'], status='active', confirmed=True,
            preview_hash=preview['preview_hash'], correction_reason='Explicit new original identity source'))
        fixture.details.update(period_case_ref=reference(fixture.period), identity_refs=[reference(fixture.identity)])

    def test_actual_legacy_identity_is_not_relabelled_by_explicit_v11_upgrade(self):
        fixture = IndividualMinijobFixture(self)
        f = fixture.f
        self._replace_identity(fixture, accounts.PayrollAccountTests.identity_details(f, fixture.data),
                               fixture.data['file']['id'])
        old, old_command = fixture.legacy_case()
        old_identity = deepcopy(old['sources']['identities'][0])
        self.assertNotIn('identity_source_schema_version', old_identity['details'])
        self.assertEqual(old_identity['details']['tax_source'], 'flat_minijob_evidence')
        self._replace_identity(fixture, accounts.PayrollAccountTests.identity_details(f, fixture.data,
            identity_source_schema_version=2, tax_source='elstam_imported'), fixture.files['elstam']['id'])
        current = fixture.api.save(f.owner, fixture.upgrade_command(old))
        self.assertTrue(current['plan']['can_calculate'])
        self.assertEqual(current['sources']['identities'][0]['details']['identity_source_schema_version'], 2)
        self.assertEqual(current['sources']['identities'][0]['details']['tax_source'], 'elstam_imported')
        self.assertEqual(fixture.api.save(f.owner, old_command), old)
        self.assertEqual(fixture.api.get(f.owner, old['id'], True)['items'][0]['sources']['identities'][0], old_identity)
        self.assertTrue(validate_cases(f.office))

    def _switch_tax_mode(self, fixture, mode):
        f = fixture.f
        before = fixture.data['profile']
        fixture.data['profile'] = f.payroll.save_profile(f.owner, dict(
            request_id=rid(), employee_id=f.employee['id'], id=before['id'], revision=before['revision'],
            profile=dict(before['profile'], minijob_tax=mode), source_file_id=fixture.data['file']['id'],
            confirmed=True, correction_reason='Independent evidenced change of the original tax mode'))
        before = fixture.data['preparation']
        proposal = f.hr.preview(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))
        fixture.data['preparation'] = f.hr.close_preparation(f.owner, dict(request_id=rid(),
            employee_id=f.employee['id'], month='2026-10', id=before['id'], revision=before['revision'],
            source_hash=proposal['source_hash'], completeness_confirmed=True,
            correction_reason='Independent updated source preparation'))
        individual = mode == 'individual'
        details = accounts.PayrollAccountTests.identity_details(f, fixture.data,
            **({'identity_source_schema_version':2, 'tax_source':'elstam_imported'} if individual else {}))
        fixture.identity = fixture.accounts.save(f.owner, dict(request_id=rid(), employee_id=f.employee['id'],
            kind='identity', revision=0, source_file_id=fixture.files['elstam']['id'] if individual else fixture.data['file']['id'],
            confirmed=True, details=details))
        before = fixture.period
        details = dict(before['details'], preparation_ref=reference(fixture.data['preparation']),
            profile_refs=[reference(fixture.data['profile'])], identity_refs=[reference(fixture.identity)])
        proposal = dict(employee_id=f.employee['id'], employee_revision=f.employee['revision'],
            details=details, source_file_ids=[fixture.data['file']['id']])
        preview = fixture.facts.preview(f.owner, proposal)
        fixture.period = fixture.facts.save(f.owner, dict(proposal, request_id=rid(), kind='period_case',
            revision=before['revision'], id=before['id'], status='active', confirmed=True,
            preview_hash=preview['preview_hash'], correction_reason='Independent source period correction'))
        fixture.details.update(period_case_ref=reference(fixture.period),
            profile_refs=[reference(fixture.data['profile'])], identity_refs=[reference(fixture.identity)])

    def test_previously_used_older_revision_blocks_an_otherwise_eligible_upgrade(self):
        fixture = IndividualMinijobFixture(self)
        f = fixture.f
        self._switch_tax_mode(fixture, 'flat_2_employer')
        original, original_command = fixture.legacy_case()
        self.assertTrue(original['plan']['can_calculate'])
        inputs = dict(source_schema_version=3, employee_id=f.employee['id'], calculation_case_ref=reference(original))
        preview = f.payroll.preview(f.owner, inputs)
        command = dict(inputs, request_id=rid(), revision=0, confirmed=True,
            accepted_scope=preview['calculation']['scope'], preview_hash=preview['preview_hash'])
        run = f.payroll.finalize(f.owner, command)
        self._switch_tax_mode(fixture, 'individual')
        legacy_details = {key:deepcopy(value) for key,value in fixture.details.items()
                          if key != 'individual_minijob_assessment'}
        proposal, preview = fixture.preview(legacy_details,
            rule_version='de_2026_segments_entitlements_v5', source_contract_version=1)
        latest = fixture.api.save(f.owner, dict(proposal, request_id=rid(), id=original['id'], revision=1,
            status='active', confirmed=True, preview_hash=preview['preview_hash'],
            correction_reason='Independent later unsupported original tax source'))
        self.assertFalse(latest['plan']['can_calculate'])
        self.assertIn('minijob_individual_tax', [v['code'] for v in latest['plan']['blockers']])
        with self.assertRaises(Problem) as rejected:
            fixture.api.save(f.owner, fixture.upgrade_command(latest))
        self.assertEqual(rejected.exception.status, 409)
        self.assertEqual(fixture.api.get(f.owner, latest['id'], True)['items'], [original, latest])
        self.assertEqual(fixture.api.save(f.owner, original_command), original)
        self.assertEqual(f.payroll.finalize(f.owner, command), run)
        self.assertTrue(validate_payroll(f.office))
        self.assertTrue(validate_cases(f.office))

    def test_hash_consistent_unreadable_dependent_history_is_not_proof_of_nonuse(self):
        fixture = IndividualMinijobFixture(self)
        previous, _ = fixture.legacy_case()
        command = fixture.upgrade_command(previous)
        f = fixture.f
        # Deliberately corrupt only this disposable SQLite fixture. The hash is
        # valid, but this is not a valid payroll run and must block migration.
        envelope = dict(id=rid(), kind='run', employee_id=f.employee['id'], revision=1,
            previous_hash=None, identity_key=None, created_by=f.owner['id'],
            created_at=f.hr.now(), pdf_sha256=None, payload={})
        f.office.db.execute('INSERT INTO business_payroll_events '
            '(id,kind,employee_id,revision,previous_hash,identity_key,created_by,created_at,pdf_sha256,payload_json,content_hash) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            tuple(envelope[key] for key in ('id','kind','employee_id','revision','previous_hash','identity_key',
                                            'created_by','created_at','pdf_sha256')) + (canonical({}), _sha(envelope)))
        row = f.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?', (envelope['id'],)).fetchone()
        self.assertEqual(Payroll(f.office)._event(row)['id'], envelope['id'])
        with self.assertRaises(ValueError):
            validate_payroll(f.office)
        count_before = f.office.db.execute('SELECT COUNT(*) FROM business_payroll_calculation_case_requests').fetchone()[0]
        with self.assertRaises(Problem) as rejected:
            fixture.api.save(f.owner, command)
        self.assertEqual(rejected.exception.status, 409)
        self.assertEqual(fixture.api.get(f.owner, previous['id'], True)['items'], [previous])
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_payroll_calculation_case_requests').fetchone()[0], count_before)
        self.assertEqual(dict(f.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?', (envelope['id'],)).fetchone()), dict(row))


if __name__ == '__main__':
    unittest.main()
