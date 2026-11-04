"""Independent U calendar, original, permission and annual-boundary checks."""
import base64
from copy import deepcopy
from datetime import date, timedelta
import unittest

from business_foundation import BusinessFoundation
from business_payroll_facts import reference
from business_payroll_wage_interruptions import build_plan
from payroll_wage_interruptions_2026 import calculate_wage_interruptions
from payroll_entitlement_dispatch import build_entitlement_plan
from test_business_payroll import rid
import test_business_payroll_wage_interruptions as domain
from test_payroll_calculations_2026 import source as running_source, calculate as calculate_running
from test_payroll_sickness_phases_2026 import history
from test_payroll_entitlements_2026 import episode

REF = dict(id='1' * 32, revision=1, content_hash='2' * 64)


def source(first, last, workdays, *, preserved=()):
    left, right = date.fromisoformat(first), date.fromisoformat(last)
    rows = []
    for index in range((right - left).days + 1):
        current = (left + timedelta(days=index)).isoformat()
        rows.append(dict(date=current, contractual_workday=current in workdays,
            wage_claim='preserved' if current in preserved else 'none', section41_1_4_payment_kind='none',
            claim_evidence_refs=[REF], schedule_evidence_refs=[REF], exception_evidence_refs=[REF]))
    return dict(year=2026, assessment_through=last,
        employment_intervals=[dict(**{'from': first, 'to': last}, evidence_refs=[REF])],
        days=rows, carry_in_loss=False, tax_scope='individual')


class IndependentUCalendar(unittest.TestCase):
    def test_ten_actual_workdays_across_month_boundary_are_one_period(self):
        workdays = ['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30',
            '2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06']
        original = source(workdays[0], workdays[-1], workdays); before = deepcopy(original)
        result = calculate_wage_interruptions(original)
        self.assertEqual((result['number_u'], result['periods'][0]['workday_count']), (1,10))
        self.assertEqual(original, before)

    def test_actual_weekend_shifts_are_workdays_and_paid_holiday_breaks_sequence(self):
        weekend = ['2026-10-23','2026-10-24','2026-10-25','2026-10-26','2026-10-27']
        self.assertEqual(calculate_wage_interruptions(source(weekend[0], weekend[-1], weekend))['number_u'], 1)
        workdays = ['2026-10-19','2026-10-20','2026-10-21','2026-10-22','2026-10-23',
            '2026-10-26','2026-10-27','2026-10-28','2026-10-29']
        result = calculate_wage_interruptions(source(workdays[0], workdays[-1], workdays, preserved=['2026-10-23']))
        self.assertEqual(result['number_u'], 0)
        self.assertEqual([part['workday_count'] for part in result['candidates']], [4,4])

    def sickness_projection(self, onset):
        running = running_source(month='2026-01', start='2025-01-01', amount=300000)
        terms = running['employment_terms'][0]
        details = dict(employment_terms_ref=reference(terms),
            input=history([episode(onset,'2026-01-31')]))
        snapshot = dict(schema_version=1, kind='sickness_history', details=details)
        claim = dict(id='3' * 32, revision=1, content_hash='4' * 64, employee_id=running['employee_id'],
            kind='sickness_history', status='active', details=details, sources=snapshot,
            plan=build_entitlement_plan(snapshot))
        unpaid = [part for part in claim['plan']['phases'] if not part['entitled'] and not part['first_day_remaining_regular_wage']]
        # The current-year SV proof covers the actually documented benefit
        # month. It does not erase the sickness source's earlier wage loss.
        continuation_details = dict(employment_terms_ref=reference(terms), input=dict(
            **{'from':'2026-01-01','to':'2026-01-31'}, employment_to=None,
            employment_continues=True, no_wage_claim=True, intervening_paid_days=[], evidence_refs=[REF],
            exceptions=[dict(kind='sickness_benefit', **{'from':'2026-01-01','to':'2026-01-31'},
                employment_scope='this_employment', evidence_refs=[REF])]))
        continuation_snapshot = dict(schema_version=1, kind='unpaid_continuation', details=continuation_details)
        continuation = dict(id='9' * 32, revision=1, content_hash='a' * 64,
            employee_id=running['employee_id'], kind='unpaid_continuation', status='active',
            details=continuation_details, sources=continuation_snapshot,
            plan=build_entitlement_plan(continuation_snapshot))
        running['entitlements'] = [claim, continuation]
        calculation = calculate_running(running)
        self.assertTrue(calculation['payroll_calculation_complete'], calculation['blockers'])
        self.assertIn('2026-01-01', calculation['period_details']['unpaid_dates'])
        run = dict(id='5' * 32, revision=1, content_hash='6' * 64, source=dict(source_schema_version=3,
            month='2026-01', calculation_case=dict(sources=running)), calculation=calculation)
        schedule = dict(id='7' * 32, revision=1, content_hash='8' * 64,
            details=dict(month='2026-01', days=[dict(date='2026-01-' + format(day, '02'),
                scheduled_seconds=28800 if date(2026,1,day).weekday()<5 else 0) for day in range(1,32)]))
        result = build_plan(dict(details=dict(assessment_through='2026-01-31', excluded_payments=[],
            exception_review_file_refs=[REF]), employment_terms=[terms], runs=[run], work_schedules=[schedule], entitlements=[claim, continuation]))
        return result, unpaid

    def test_sickness_loss_already_in_previous_year_cannot_bypass_carryin_blocker(self):
        # The actual pure P4 rule exhausts six weeks on 12 December 2025.
        result, unpaid = self.sickness_projection('2025-11-01')
        self.assertTrue(any(part['from_date'] <= '2025-12-31' < '2026-01-01' <= part['to_date'] for part in unpaid))
        self.assertFalse(result['can_determine'])
        self.assertIsNone(result['number_u'])
        self.assertIn('year_carry_in_requires_rule', [value['code'] for value in result['blockers']])

    def test_efz_through_december31_is_first_loss_in_january_and_has_no_carryin(self):
        result, unpaid = self.sickness_projection('2025-11-20')
        self.assertFalse(any(part['from_date'] <= '2025-12-31' <= part['to_date'] for part in unpaid))
        self.assertTrue(result['can_determine'], result['blockers'])
        self.assertEqual(result['number_u'], 1)


class IndependentUOriginals(unittest.TestCase):
    def setUp(self):
        self.w = domain.WageInterruptionWorkflow('runTest'); self.w.setUp()
        self.addCleanup(self.w.doCleanups); self.f = self.w.f

    def test_changed_actual_schedule_invalidates_current_projection_preserves_original_receipt(self):
        w, f = self.w, self.f; details = w.originals(); body, _ = w.command(details)
        saved = w.api.save(f.owner, body)
        changed = deepcopy(w.schedule['details'])
        next(value for value in changed['days'] if value['date']=='2026-10-26')['scheduled_seconds'] = 0
        corrected = f.api.save(f.owner, f.body('work_schedule', changed, id=w.schedule['id'],
            revision=w.schedule['revision'], correction_reason='Original scheduled day was not contractual work'))
        ledger = f.payroll.ledger(f.owner, dict(employee_id=f.employee['id'], year='2026'))['ledger']
        self.assertEqual(ledger['recorded_wage_interruptions']['status'], 'outdated')
        self.assertIsNone(ledger['recorded_wage_interruptions']['number_u'])
        self.assertEqual(w.api.save(f.owner, body), saved)
        new_body, preview = w.command(details | dict(work_schedule_refs=[reference(corrected)]),
            id=saved['id'], revision=saved['revision'], correction_reason='Actual corrected workday schedule bound')
        self.assertEqual(preview['plan']['number_u'], 0)
        revised = w.api.save(f.owner, new_body)
        self.assertEqual(w.api.get(f.owner, saved['id'], True)['items'], [saved, revised])

    def test_superseded_protected_original_blocks_new_use_but_keeps_original_acceptance(self):
        w, f = self.w, self.f; details = w.originals(); body, _ = w.command(details)
        saved = w.api.save(f.owner, body)
        f.hr.upload(f.owner, dict(request_id=rid(), employee_id=f.employee['id'], purpose='personnel',
            owner_visible=False, filename='u-reviewed-original-corrected.pdf', media_type='application/pdf',
            supersedes=f.data['file']['id'], content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic revised U original\n%%EOF').decode()))
        f.problem(409, lambda: w.command(details))
        self.assertEqual(w.api.save(f.owner, body), saved)

    def test_revoked_approval_still_allows_private_read_but_denies_original_command_replay(self):
        w, f = self.w, self.f; details = w.originals(); body, _ = w.command(details)
        uid = f.office.add_user('u-reviewer@example.test','Synthetic-U-review-password-123','technician')
        actor = dict(id=uid, email='u-reviewer@example.test', role='technician'); grants = BusinessFoundation(f.office)
        for permission in ('personnel.read','personnel.approve'):
            grants.save_grant(f.owner, dict(request_id=rid(), user_id=uid, permission=permission, scope='*', effect='allow', revision=0))
        saved = w.api.save(actor, body)
        grants.save_grant(f.owner, dict(request_id=rid(), user_id=uid, permission='personnel.approve', scope='*', effect='deny', revision=1))
        self.assertEqual(w.api.get(actor, saved['id']), saved)
        f.problem(403, lambda: w.api.save(actor, body))


if __name__ == '__main__': unittest.main()
