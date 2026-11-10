"""A diagnosis cannot mutate the frozen report or manufacture a receipt."""
import copy
import unittest
import uuid

import test_business_offline_reports as fixture
from offline_report_conflicts import diagnose


class ConflictDiagnosisTests(unittest.TestCase):
    setUp = fixture.OfflineServiceReportTests.setUp
    actor = fixture.OfflineServiceReportTests.actor
    body = fixture.OfflineServiceReportTests.body
    counts = fixture.OfflineServiceReportTests.counts
    error = fixture.OfflineServiceReportTests.error

    def diagnosis(self, body, actor=None):
        return diagnose(self.api, actor or self.tech, self.project, body)

    def rename(self, name='Neues Projekt', customer='Neuer Kunde'):
        self.office.db.execute('UPDATE projects SET name=?,customer=? WHERE id=?', (name, customer, self.project))
        self.office.db.commit()

    def test_ready_and_changed_context_are_read_only_and_original_bound(self):
        body = self.body()
        before = copy.deepcopy(body)
        changes = self.office.db.total_changes
        ready = self.diagnosis(body)
        self.assertEqual(ready['state'], 'ready')
        self.assertEqual(ready['current_context'], ready['captured_context'])
        self.assertIsNone(ready['server_record'])
        self.assertEqual(self.office.db.total_changes, changes)
        self.rename()
        changes = self.office.db.total_changes
        changed = self.diagnosis(body)
        self.assertEqual(changed['state'], 'context_changed')
        self.assertEqual(changed['captured_context'], ready['captured_context'])
        self.assertEqual(changed['current_context'], dict(project_name='Neues Projekt', customer='Neuer Kunde'))
        self.assertEqual(self.office.db.total_changes, changes)
        self.assertEqual(body, before)
        self.assertEqual(self.counts(), [0, 0, 0])

    def test_accepted_original_takes_precedence_over_current_names(self):
        body = self.body()
        accepted = self.api.capture_offline(self.tech, self.project, body)
        pdf = self.api.entry_pdf(self.tech, self.project, accepted['id'])
        self.rename()
        changes = self.office.db.total_changes
        result = self.diagnosis(body)
        self.assertEqual(result['state'], 'accepted')
        self.assertEqual(result['server_record'], accepted)
        self.assertEqual(self.office.db.total_changes, changes)
        self.assertEqual(self.api.entry_pdf(self.tech, self.project, accepted['id']), pdf)
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_identity_or_request_collision_is_not_a_copyable_context_conflict(self):
        body = self.body()
        self.api.capture_offline(self.tech, self.project, body)
        for key, value in [('request_id', uuid.uuid4().hex), ('signer', 'Andere Person')]:
            self.error(409, lambda: self.diagnosis({**body, key: value}))
        self.error(409, lambda: self.diagnosis(body, self.owner))
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_fresh_revocation_is_enforced_even_for_accepted_original(self):
        body = self.body()
        self.api.capture_offline(self.tech, self.project, body)
        self.office.assign(self.owner, self.project, self.tech['id'], remove=True)
        self.error(404, lambda: self.diagnosis(body))
        self.assertEqual(self.counts(), [1, 2, 1])

    def test_unknown_fields_and_changed_signed_content_do_not_get_a_diagnosis(self):
        body = self.body()
        self.error(400, lambda: self.diagnosis({**body, 'ignore_conflict': True}))
        body['content']['customer'] = 'Manipuliert'
        self.error(409, lambda: self.diagnosis(body))
        self.assertEqual(self.counts(), [0, 0, 0])

    def test_archive_corruption_is_never_reported_as_missing_or_ready(self):
        body = self.body()
        self.api.capture_offline(self.tech, self.project, body)
        # Synthetic SQLite fixture, matching the existing archive corruption test.
        self.office.db.execute("UPDATE business_operation_entries SET pdf_sha256=? WHERE id=?", ('0'*64, body['entry_id']))
        self.error(500, lambda: self.diagnosis(body))


if __name__ == '__main__':
    unittest.main()
