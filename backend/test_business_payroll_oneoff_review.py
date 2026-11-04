"""Independent actual-authority and original-evidence checks for private v6 cases."""
import base64
import unittest
from business_foundation import BusinessFoundation
from business_payroll_facts import reference
import business_payroll_oneoff_cases as cases
from test_business_payroll import rid
import test_business_payroll_oneoff_cases as fixture


class OneoffPrivateIndependentReview(unittest.TestCase):
    def setUp(self):
        self.w = fixture.OneoffCaseWorkflow('runTest')
        self.w.setUp()
        self.addCleanup(self.w.doCleanups)
        self.f = self.w.f
        self.api = self.w.api

    def test_read_permission_alone_cannot_replay_a_previously_approved_case(self):
        f = self.f
        uid = f.office.add_user('oneoff-independent@example.test', 'Synthetic-oneoff-independent-123', 'technician')
        actor = dict(id=uid, email='oneoff-independent@example.test', role='technician')
        grants = BusinessFoundation(f.office)
        for permission in ('personnel.read', 'personnel.approve'):
            grants.save_grant(f.owner, dict(request_id=rid(), user_id=uid, permission=permission, scope='*', effect='allow', revision=0))
        body, _ = self.w.request()
        accepted = self.api.save(actor, body)
        grants.save_grant(f.owner, dict(request_id=rid(), user_id=uid, permission='personnel.approve', scope='*', effect='deny', revision=1))
        self.assertEqual(accepted, self.api.get(actor, accepted['id']))
        self.assertFalse(self.api.sources(actor, dict(employee_id=f.employee['id'], month='2026-10'))['can_approve'])
        f.problem(403, lambda: self.api.save(actor, body))
        self.assertEqual(1, f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[1]).fetchone()[0])

    def test_superseded_original_cannot_be_used_fresh_but_accepted_receipt_is_unchanged(self):
        f = self.f; body, _ = self.w.request(); accepted = self.api.save(f.owner, body)
        f.hr.upload(f.owner, dict(request_id=rid(), employee_id=f.employee['id'], purpose='personnel', owner_visible=False,
            filename='oneoff-corrected-original.pdf', media_type='application/pdf', supersedes=f.original['id'],
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic changed oneoff original\n%%EOF').decode()))
        f.problem(409, lambda: self.api.resolve_one_off_case(f.owner, f.employee['id'], reference(accepted)))
        self.assertEqual(accepted, self.api.save(f.owner, body))
        self.assertTrue(cases.validate_integrity(f.office))

    def test_changed_employee_cannot_reauthorize_old_preview_as_a_new_effect(self):
        f = self.f; body, _ = self.w.request(); accepted = self.api.save(f.owner, body)
        changed = f.call(f.planning, 'save_employee', f.owner, dict(request_id=rid(), id=f.employee['id'],
            revision=f.employee['revision'], name='Synthetic current oneoff employee name'))
        f.problem(409, lambda: self.api.resolve_one_off_case(f.owner, changed['id'], reference(accepted)))
        f.problem(409, lambda: self.api.save(f.owner, body | dict(request_id=rid(), employee_revision=changed['revision'],
            id=accepted['id'], revision=accepted['revision'], correction_reason='Reusing unrefreshed preview')))
        self.assertEqual(accepted, self.api.save(f.owner, body))
        self.assertEqual([accepted], self.api.get(f.owner, accepted['id'], True)['items'])

    def test_public_dtos_never_expose_any_nested_acceptance_command(self):
        f = self.f; body, _ = self.w.request(); accepted = self.api.save(f.owner, body)
        def inspect(value):
            if isinstance(value, dict):
                self.assertNotIn('accepted_command', value)
                for nested in value.values(): inspect(nested)
            elif isinstance(value, list):
                for nested in value: inspect(nested)
        for value in [accepted, self.api.get(f.owner, accepted['id'], True),
                self.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))]: inspect(value)


if __name__ == '__main__': unittest.main()
