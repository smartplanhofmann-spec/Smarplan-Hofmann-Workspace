"""Independent source reconstruction review; shared setup, no inherited tests."""
from copy import deepcopy
import json
import unittest

from business_foundation import BusinessFoundation
import business_payroll_entitlements as entitlements
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import canonical, Problem
import test_business_payroll as monthly
import test_business_payroll_entitlements as fixtures


class IndependentEntitlementSourceReview(monthly.BusinessFixture, unittest.TestCase):
    # Only fixture functions are shared. Expectations and corruption operations
    # below are independent of the implementation author's test methods.
    setUp = fixtures.PayrollEntitlementTests.setUp
    case = fixtures.PayrollEntitlementTests.case
    identity_details = fixtures.PayrollEntitlementTests.identity_details
    save_account = fixtures.PayrollEntitlementTests.save_account
    account_api = fixtures.PayrollEntitlementTests.account_api
    terms_details = fixtures.PayrollEntitlementTests.terms_details
    body = fixtures.PayrollEntitlementTests.body
    terms = fixtures.PayrollEntitlementTests.terms
    pause = fixtures.PayrollEntitlementTests.pause
    details = fixtures.PayrollEntitlementTests.details
    request = fixtures.PayrollEntitlementTests.request
    save = fixtures.PayrollEntitlementTests.save
    hourly = fixtures.PayrollEntitlementTests.hourly
    schedule = fixtures.PayrollEntitlementTests.schedule
    absence_preparation = fixtures.PayrollEntitlementTests.absence_preparation

    def sick_claim(self):
        self.hourly()
        details = self.details('sickness_history')
        details['input']['pay_basis'] = 'hourly'
        history, _, _ = self.save('sickness_history', details)
        schedule = self.schedule('2026-11')
        preparation = self.absence_preparation('2026-11-16', '2026-11-16', 'sick')
        details = self.details()
        details.update(work_schedule_refs=[reference(schedule)],
                       preparation_refs=[reference(preparation)],
                       sickness_history_ref=reference(history))
        details['input'] = dict(kind='sickness', hourly_rate_minor=1800,
            evidence_refs=[self.original], days=[dict(date='2026-11-16',
            scheduled_regular_seconds=28800, worked_regular_seconds=0,
            entitled=True, absence_is_only_cause=True,
            holiday_adjacent_unexcused=None, evidence_refs=[self.original])])
        return self.save('regular_absence', details)

    def rewrite(self, saved, mutate):
        """Simulate a damaged import with valid outer hashes and receipt.

        Real runtime UPDATEs are forbidden. Dropping guards in this isolated
        fixture demonstrates why canonical-source validation is also needed.
        """
        row = dict(self.claims._row(saved['id'], saved['revision']))
        payload, sources = json.loads(row['payload_json']), json.loads(row['sources_json'])
        mutate(payload, sources, row)
        payload['plan'] = entitlements.build_entitlement_plan(sources)
        payload['preview_hash'] = _sha(dict(source_snapshot=sources, plan=payload['plan']))
        envelope = {k:v for k,v in row.items()
                    if k not in ('payload_json', 'sources_json', 'content_hash')}
        envelope.update(source_hash=_sha(sources), payload=payload, sources=sources)
        digest = _sha(envelope)
        for table in entitlements.TABLES:
            self.office.db.execute('DROP TRIGGER IF EXISTS '+table+'_update_guard')
        self.office.db.execute('UPDATE business_payroll_entitlement_events SET '
            'payload_json=?,sources_json=?,source_hash=?,content_hash=?,effective_from=?,effective_to=? '
            'WHERE id=? AND revision=?',
            (canonical(payload), canonical(sources), _sha(sources), digest,
             row['effective_from'], row['effective_to'], saved['id'], saved['revision']))
        self.office.db.execute('UPDATE business_payroll_entitlement_requests SET fact_content_hash=? '
            'WHERE fact_id=? AND fact_revision=?', (digest, saved['id'], saved['revision']))
        altered = self.claims._get(saved['id'], saved['revision'])
        self.assertEqual(digest, altered['content_hash'])
        return altered

    def rejected_archive(self, altered, original_request):
        with self.assertRaises(ValueError):
            entitlements.validate_entitlement_sources(self.office, altered)
        with self.assertRaises(ValueError):
            entitlements.validate_integrity(self.office)
        with self.assertRaises((Problem, ValueError)):
            self.claims.save(self.owner, original_request)

    def test_recomputed_claim_cannot_replace_canonical_hourly_contract(self):
        saved, body, _ = self.sick_claim()
        self.assertEqual(14400, saved['plan']['gross_minor'])
        def mutate(payload, sources, row):
            sources['agreements'][0]['amount_minor'] = 1900
            sources['preparations'][0]['snapshot']['agreements'][0]['amount_minor'] = 1900
            payload['details']['input']['hourly_rate_minor'] = 1900
            sources['details'] = deepcopy(payload['details'])
        changed = self.rewrite(saved, mutate)
        self.assertEqual(15200, changed['plan']['gross_minor'])
        self.rejected_archive(changed, body)

    def test_recomputed_plan_and_schedule_cannot_invent_four_more_absence_hours(self):
        saved, body, _ = self.sick_claim()
        def mutate(payload, sources, row):
            payload['details']['input']['days'][0]['scheduled_regular_seconds'] = 43200
            sources['details'] = deepcopy(payload['details'])
            for day in sources['work_schedules'][0]['details']['days']:
                if day['date'] == '2026-11-16':
                    day['scheduled_seconds'] = 43200
        changed = self.rewrite(saved, mutate)
        self.assertEqual(21600, changed['plan']['gross_minor'])
        self.rejected_archive(changed, body)

    def test_rehashed_original_file_cannot_change_person_or_content(self):
        saved, body, _ = self.save()
        def mutate(payload, sources, row):
            sources['source_files'][0]['content_hash'] = '0'*64
            sources['source_files'][0]['employee_id'] = 'f'*32
        self.rejected_archive(self.rewrite(saved, mutate), body)

    def test_claim_window_is_reconstructed_even_when_envelope_is_valid(self):
        saved, body, _ = self.save()
        def mutate(payload, sources, row):
            row['effective_from'] = '2026-11-01'
        self.rejected_archive(self.rewrite(saved, mutate), body)

    def test_reading_another_existing_employee_revision_cannot_launder_acceptance(self):
        saved, body, _ = self.save()
        later = self.call(self.planning, 'save_employee', self.owner,
            dict(request_id=monthly.rid(), id=self.employee['id'],
                 revision=self.employee['revision'], weekly_minutes=2300))
        def mutate(payload, sources, row):
            sources['employee']['revision'] = later['revision']
        self.rejected_archive(self.rewrite(saved, mutate), body)

    def test_revoked_approval_blocks_exact_lost_ack_even_while_read_is_allowed(self):
        uid = self.office.add_user('entitlement-review@example.test',
            'Synthetic-review-password-123', 'technician')
        actor = dict(id=uid, email='entitlement-review@example.test', role='technician')
        grants = BusinessFoundation(self.office)
        for name in ('personnel.read', 'personnel.approve'):
            grants.save_grant(self.owner, dict(request_id=monthly.rid(), user_id=uid,
                permission=name, scope='*', effect='allow', revision=0))
        body, _ = self.request()
        saved = self.claims.save(actor, body)
        grants.save_grant(self.owner, dict(request_id=monthly.rid(), user_id=uid,
            permission='personnel.approve', scope='*', effect='deny', revision=1))
        self.assertEqual(saved, self.claims.get(actor, saved['id']))
        self.problem(403, lambda:self.claims.save(actor, body))
        self.assertTrue(entitlements.validate_integrity(self.office))

    def test_corrected_history_preserves_accepted_claim_but_blocks_fresh_use(self):
        saved, body, _ = self.sick_claim()
        history = saved['sources']['sickness_history']
        details = deepcopy(history['details'])
        details['verification_note'] = 'Später korrigierter tatsächlicher Nachweis'
        request, _ = self.request('sickness_history', details)
        request.update(id=history['id'], revision=history['revision'],
                       correction_reason='Nachweisstand berichtigt')
        self.claims.save(self.owner, request)
        self.assertEqual(saved, self.claims.save(self.owner, body))
        self.assertTrue(entitlements.validate_integrity(self.office))
        self.problem(409, lambda:self.claims.resolve_entitlement_case(
            self.owner, self.employee['id'], reference(saved)))

    def test_actual_approved_vacation_cannot_be_paid_as_sickness(self):
        self.hourly()
        details = self.details('sickness_history')
        details['input']['pay_basis'] = 'hourly'
        history, _, _ = self.save('sickness_history', details)
        schedule = self.schedule('2026-11')
        preparation = self.absence_preparation('2026-11-16', '2026-11-16', 'vacation')
        details = self.details()
        details.update(work_schedule_refs=[reference(schedule)],
            preparation_refs=[reference(preparation)], sickness_history_ref=reference(history))
        details['input'] = dict(kind='sickness', hourly_rate_minor=1800,
            evidence_refs=[self.original], days=[dict(date='2026-11-16',
            scheduled_regular_seconds=28800, worked_regular_seconds=0,
            entitled=True, absence_is_only_cause=True,
            holiday_adjacent_unexcused=None, evidence_refs=[self.original])])
        self.problem(409, lambda:self.request('regular_absence', details))


if __name__ == '__main__':
    unittest.main()
