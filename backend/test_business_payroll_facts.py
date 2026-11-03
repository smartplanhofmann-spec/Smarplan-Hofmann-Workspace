"""Canonical private period facts, exact historical receipts and source drift."""
import base64
import calendar
from datetime import date
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_facts as facts
import test_business_payroll as monthly
import test_business_payroll_accounts as account_fixture
from business_foundation import BusinessFoundation
from business_organization import Organization
from business_personnel_workflow import _sha
from core import canonical


class PayrollFactTests(monthly.BusinessFixture, unittest.TestCase):
    case = monthly.PayrollWorkflowTests.case
    identity_details = account_fixture.PayrollAccountTests.identity_details
    save_account = account_fixture.PayrollAccountTests.save_account
    account_api = account_fixture.PayrollAccountTests.account_api

    def setUp(self):
        names = business_schema.MODULE_NAMES
        if 'business_payroll_facts' not in names:
            names += ('business_payroll_facts',)
        self.registry_patch = patch.object(business_schema, 'MODULE_NAMES', names)
        self.registry_patch.start(); self.addCleanup(self.registry_patch.stop)
        monthly.PayrollWorkflowTests.setUp(self)
        self.now = self.now.replace(month=11, day=3)
        self.employee = self.call(self.planning, 'save_employee', self.owner, dict(request_id=monthly.rid(), id=self.employee['id'],
            revision=self.employee['revision'], employment_from='2026-10-15', employment_to=None))
        self.data = self.case('minijob', 60300)
        self.identity, _ = self.save_account(self.data, 'identity', self.identity_details(self.data, employment_from='2026-10-15', employment_to=None))
        self.api = facts.PayrollFacts(self.office, clock=lambda: self.now)

    def terms_details(self, **changes):
        return dict(employment_from='2026-10-15', employment_to=None, agreement_refs=[facts.reference(self.data['agreement'])],
                    proration_method='calendar_days_actual', reason='Belegter individueller Teilentgeltvertrag', **changes)

    def body(self, kind, details, **changes):
        return dict(request_id=monthly.rid(), employee_id=self.employee['id'], employee_revision=self.employee['revision'], kind=kind,
            revision=0, status='active', details=details, source_file_ids=[self.data['file']['id']], confirmed=True) | changes

    def terms(self):
        body = self.body('employment_terms', self.terms_details())
        return self.api.save(self.owner, body), body

    def period_details(self, terms, **changes):
        return dict(month='2026-10', preparation_ref=facts.reference(self.data['preparation']), employment_terms_ref=facts.reference(terms),
            work_schedule_ref=None, profile_refs=[facts.reference(self.data['profile'])], identity_refs=[facts.reference(self.identity)],
            tax_treatment='domestic_running_wages', entitlement_decisions=[], verification_note='Belegte Zeitachsen und Nachweise geprüft') | changes

    def preview_body(self, details):
        return dict(employee_id=self.employee['id'], employee_revision=self.employee['revision'], details=details,
                    source_file_ids=[self.data['file']['id']])

    def period(self):
        terms, _ = self.terms(); details = self.period_details(terms)
        preview = self.api.preview(self.owner, self.preview_body(details))
        body = self.body('period_case', details, preview_hash=preview['preview_hash'])
        return self.api.save(self.owner, body), body, preview

    def pause(self):
        organization = Organization(self.office); current = organization.get(self.owner)
        modules = {key: dict(visible=value['visibility_override'], enabled=value['enabled']) for key, value in current['modules'].items()}
        modules['personnel']['enabled'] = False
        organization.save(self.owner, dict(request_id=monthly.rid(), revision=current['revision'], needs=current['needs'], modules=modules))

    def test_actual_period_plan_freezes_canonical_sources_and_no_cash(self):
        before = {name: self.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in ('business_payroll_events', 'business_payroll_cash_batches', 'business_euer_entries')}
        saved, body, preview = self.period()
        self.assertTrue(preview['can_confirm']); self.assertTrue(preview['can_calculate'])
        self.assertEqual(preview['plan']['gross_minor'], 33068)
        self.assertEqual(preview['plan']['tax_periods'][0]['tax_days'], 17)
        self.assertEqual(saved['sources'], preview['source_snapshot']); self.assertEqual(saved['plan'], preview['plan'])
        self.assertEqual(self.api.save(self.owner, body), saved)
        self.assertEqual(self.api.resolve_period_case(self.owner, self.employee['id'], facts.reference(saved)), saved)
        self.assertEqual(self.api.get(self.owner, saved['id'], True)['items'], [saved])
        self.assertEqual(before, {name: self.office.db.execute('SELECT COUNT(*) FROM ' + name).fetchone()[0] for name in before})
        self.assertTrue(facts.validate_integrity(self.office)); self.assertTrue(business_schema.validate_integrity(self.office))

    def test_unknown_entitlement_is_visible_blocked_but_recordable(self):
        terms, _ = self.terms()
        details = self.period_details(terms, entitlement_decisions=[dict(kind='sickness_continued_pay', source_absence_id=None,
            source_file_ids=[self.data['file']['id']], reason='Eigenständigen Anspruch noch berechnen', **{'from': '2026-10-20', 'to': '2026-10-21'})])
        preview = self.api.preview(self.owner, self.preview_body(details))
        self.assertTrue(preview['can_confirm']); self.assertFalse(preview['can_calculate'])
        self.assertIn('entitlement_requires_calculation', [item['code'] for item in preview['plan']['blockers']])
        saved = self.api.save(self.owner, self.body('period_case', details, preview_hash=preview['preview_hash']))
        self.assertEqual(saved['plan'], preview['plan']); self.assertTrue(facts.validate_integrity(self.office))

    def test_explicit_work_schedule_every_day_and_no_free_counts(self):
        days = [dict(date=f'2026-10-{number:02}', scheduled_seconds=28800 if date(2026, 10, number).weekday() < 5 else 0,
                     workplace='Synthetischer Arbeitsort', federal_state='BW') for number in range(1, 32)]
        details = dict(month='2026-10', days=days, reason='Belegter vollständiger Sollarbeitsplan')
        schedule = self.api.save(self.owner, self.body('work_schedule', details))
        for change in (dict(days=days[:-1]), dict(days=days[::-1]), dict(days=[days[0] | dict(scheduled_seconds=True)] + days[1:]), dict(paid_days=22)):
            self.problem(400, lambda change=change: self.api.save(self.owner, self.body('work_schedule', details | change)))
        terms = self.api.save(self.owner, self.body('employment_terms', self.terms_details() | dict(proration_method='scheduled_workdays')))
        preview = self.api.preview(self.owner, self.preview_body(self.period_details(terms, work_schedule_ref=facts.reference(schedule))))
        self.assertEqual(preview['plan']['earnings'][0]['numerator'], 12)
        self.assertEqual(preview['plan']['earnings'][0]['denominator'], 22)
        self.assertEqual(preview['plan']['gross_minor'], 32891)
        self.assertTrue(facts.validate_integrity(self.office))

    def test_accepted_replay_after_employee_change_and_module_pause_is_original(self):
        saved, body = self.terms()
        self.employee = self.call(self.planning, 'save_employee', self.owner, dict(request_id=monthly.rid(), id=self.employee['id'], revision=self.employee['revision'], name='Nachweislich berichtigter Name'))
        self.pause()
        self.assertEqual(self.api.save(self.owner, body), saved)
        self.assertEqual(self.api.get(self.owner, saved['id']), saved)
        self.problem(423, lambda: self.api.save(self.owner, body | dict(request_id=monthly.rid(), employee_revision=self.employee['revision'])))
        self.assertTrue(facts.validate_integrity(self.office))

    def test_fresh_private_read_and_write_rights_before_replay(self):
        uid = self.office.add_user('facts-delegate@example.test', 'Synthetic-facts-password-123', 'technician')
        actor = dict(id=uid, email='facts-delegate@example.test', role='technician')
        grants = BusinessFoundation(self.office)
        for name in ('personnel.read', 'personnel.write'):
            grants.save_grant(self.owner, dict(request_id=monthly.rid(), user_id=uid, permission=name, scope='*', effect='allow', revision=0))
        body = self.body('employment_terms', self.terms_details()); saved = self.api.save(actor, body)
        self.assertEqual(self.api.save(actor, body), saved)
        grants.save_grant(self.owner, dict(request_id=monthly.rid(), user_id=uid, permission='personnel.read', scope='*', effect='deny', revision=1))
        for callback in (lambda: self.api.save(actor, body), lambda: self.api.get(actor, saved['id']), lambda: self.api.sources(actor, dict(employee_id=self.employee['id'])), lambda: self.api.get(self.technician, saved['id'])):
            self.problem(403, callback)

    def test_profile_correction_stales_new_calculation_not_old_fact_replay(self):
        saved, body, _ = self.period()
        changed = self.payroll.save_profile(self.owner, dict(request_id=monthly.rid(), employee_id=self.employee['id'], id=self.data['profile']['id'], revision=1,
            profile=self.data['profile']['profile'] | dict(minijob_rv_exempt=True), source_file_id=self.data['file']['id'], confirmed=True, correction_reason='Belegte wirksame Merkmale korrigiert'))
        self.assertEqual(changed['revision'], 2)
        self.problem(409, lambda: self.api.resolve_period_case(self.owner, self.employee['id'], facts.reference(saved)))
        self.assertEqual(self.api.save(self.owner, body), saved)
        self.assertTrue(facts.validate_integrity(self.office))

    def test_fact_correction_preserves_old_replay_and_stales_old_period(self):
        saved, body, _ = self.period(); terms = saved['sources']['employment_terms']
        correction = self.body('employment_terms', terms['details'] | dict(reason='Korrigierter eindeutiger Vertragsvermerk'), id=terms['id'], revision=1, correction_reason='Belegten Vertragsvermerk präzisiert')
        changed = self.api.save(self.owner, correction)
        self.assertEqual(changed['revision'], 2)
        self.assertEqual(self.api.save(self.owner, body), saved)
        self.problem(409, lambda: self.api.resolve_period_case(self.owner, self.employee['id'], facts.reference(saved)))
        self.assertTrue(facts.validate_integrity(self.office))

    def test_void_keeps_historical_replaced_original_and_exact_old_ack(self):
        saved, body, _ = self.period()
        self.hr.upload(self.owner, dict(request_id=monthly.rid(), employee_id=self.employee['id'], purpose='personnel', owner_visible=False,
            filename='replacement.pdf', media_type='application/pdf', supersedes=self.data['file']['id'],
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic later replacement\n%%EOF').decode()))
        void = body | dict(request_id=monthly.rid(), id=saved['id'], revision=1, status='void', correction_reason='Faktenbild fachlich zurückgenommen')
        archived = self.api.save(self.owner, void)
        self.assertEqual(archived['sources'], saved['sources']); self.assertEqual(archived['plan'], saved['plan'])
        self.assertEqual(self.api.save(self.owner, body), saved)
        self.problem(409, lambda: self.api.resolve_period_case(self.owner, self.employee['id'], facts.reference(saved)))
        self.assertEqual(self.api.get(self.owner, saved['id'], True)['items'], [saved, archived])
        self.assertTrue(facts.validate_integrity(self.office))

    def test_unknown_fields_wrong_identity_false_confirmation_are_atomic(self):
        body = self.body('employment_terms', self.terms_details())
        for change in (dict(confirmed=False), dict(kind='arbitrary'), dict(gross_minor=123), dict(employee_revision=True), dict(revision=True), dict(source_file_ids=[])):
            self.problem(400, lambda change=change: self.api.save(self.owner, body | change))
        self.problem(409, lambda: self.api.save(self.owner, body | dict(employee_revision=self.employee['revision'] + 1)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_fact_events').fetchone()[0], 0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_fact_requests').fetchone()[0], 0)

    def test_duplicate_identity_and_changed_nonce_payload_never_add_facts(self):
        saved, body = self.terms()
        self.problem(409, lambda: self.api.save(self.owner, body | dict(request_id=monthly.rid())))
        self.problem(409, lambda: self.api.save(self.owner, body | dict(details=body['details'] | dict(reason='Different request'))))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_fact_events').fetchone()[0], 1)
        self.assertEqual(self.api.save(self.owner, body), saved)

    def test_bound_preview_cannot_confirm_changed_sources_or_plan(self):
        terms, _ = self.terms(); details = self.period_details(terms)
        preview = self.api.preview(self.owner, self.preview_body(details))
        body = self.body('period_case', details, preview_hash=preview['preview_hash'])
        self.problem(409, lambda: self.api.save(self.owner, body | dict(details=details | dict(verification_note='Changed after preview'))))
        self.problem(409, lambda: self.api.save(self.owner, body | dict(preview_hash='0' * 64)))
        self.assertEqual(len(self.api.records(self.owner, dict(employee_id=self.employee['id'], kind='period_case'))['items']), 0)

    def test_sources_no_private_self_fallback_and_capabilities_are_separate(self):
        value = self.api.sources(self.owner, dict(employee_id=self.employee['id']))
        self.assertTrue(value['can_write']); self.assertTrue(value['can_approve']); self.assertTrue(value['writes_enabled'])
        self.assertEqual(value['identities'], [self.identity]); self.assertIn('absences', value)
        self.assertNotIn('original', value['files'][0])
        self.problem(403, lambda: self.api.sources(self.technician, dict(employee_id=self.employee['id'])))
        self.pause(); value = self.api.sources(self.owner, dict(employee_id=self.employee['id']))
        self.assertTrue(value['can_write']); self.assertFalse(value['writes_enabled'])

    def test_db_guards_and_exact_exportable_table_inventory(self):
        saved, _, _ = self.period()
        for table in facts.TABLES:
            row = self.office.db.execute('SELECT * FROM ' + table + ' LIMIT 1').fetchone()
            for sql, parameters in [('UPDATE ' + table + ' SET ' + row.keys()[0] + '=' + row.keys()[0], ()), ('DELETE FROM ' + table, ()),
                ('INSERT OR REPLACE INTO ' + table + '(' + ','.join(row.keys()) + ') VALUES(' + ','.join('?' for _ in row.keys()) + ')', tuple(row))]:
                with self.assertRaises(sqlite3.IntegrityError):
                    self.office.db.execute(sql, parameters)
        self.assertEqual(set(facts.runtime_privileges()), set(facts.TABLES)); self.assertTrue(facts.validate_integrity(self.office))

    def test_historical_rehashed_period_plan_is_rejected(self):
        saved, _, _ = self.period()
        self.office.db.execute('DROP TRIGGER business_payroll_fact_events_update_guard')
        row = dict(self.api._row(saved['id'])); payload = json.loads(row['payload_json']); payload['plan']['gross_minor'] += 1
        row['payload_json'] = canonical(payload)
        envelope = {key: value for key, value in row.items() if key not in ('payload_json', 'sources_json', 'content_hash')}
        envelope.update(payload=payload, sources=json.loads(row['sources_json']))
        self.office.db.execute('UPDATE business_payroll_fact_events SET payload_json=?,content_hash=? WHERE id=?', (row['payload_json'], _sha(envelope), saved['id']))
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)

    def test_technical_receipt_cannot_point_to_different_revision_or_fingerprint(self):
        saved, body = self.terms()
        self.office.db.execute('DROP TRIGGER business_payroll_fact_requests_update_guard')
        self.office.db.execute('UPDATE business_payroll_fact_requests SET request_hash=?', ('0' * 64,))
        with self.assertRaises(ValueError): facts.validate_integrity(self.office)
        self.problem(409, lambda: self.api.save(self.owner, body))


if __name__ == '__main__':
    unittest.main()
