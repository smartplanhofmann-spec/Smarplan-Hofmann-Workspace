"""A report replays joint journals once, without retaining stale source data."""
from contextlib import nullcontext
import unittest
from unittest.mock import patch

from business_accounting_euer import validate_integrity
from core import Problem, canonical
import test_business_accounting_euer as fixture


class EuerReadScope(unittest.TestCase):
    def setUp(self):
        self.f = fixture.EuerWorkflowTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.api, self.office, self.owner = self.f.api, self.f.office, self.f.owner

    def read_count(self, method, *args):
        statements = []
        self.office.db.set_trace_callback(statements.append)
        try:
            value = method(*args)
        finally:
            self.office.db.set_trace_callback(None)
        reconstructions = sum(sql == 'SELECT * FROM business_accounting_capacity_entries ORDER BY sequence,id'
                              for sql in statements)
        self.assertFalse(hasattr(self.api, '_joint_source_cache'))
        return value, reconstructions

    def test_exact_report_and_catalog_reconstruct_joint_history_once_per_call(self):
        for _ in range(3):
            event = self.f.sale()
            self.f.post('cash', self.f.cash_payload(event))
        report, report_count = self.read_count(self.api.report, self.owner, 2026)
        catalog, catalog_count = self.read_count(self.api.sources, self.owner)
        self.assertEqual((1, 1), (report_count, catalog_count))
        # Independent baseline path performs the former full reconstruction
        # for each source; all amounts, original references and hashes agree.
        with patch.object(self.api, '_source_read', nullcontext):
            original_report, original_count = self.read_count(self.api.report, self.owner, 2026)
            original_catalog, _ = self.read_count(self.api.sources, self.owner)
        self.assertGreater(original_count, report_count)
        self.assertEqual(canonical(original_report), canonical(report))
        self.assertEqual(canonical(original_catalog), canonical(catalog))
        self.assertTrue(validate_integrity(self.office))

    def test_same_service_observes_new_cash_and_changed_original_between_reads(self):
        first = self.f.sale()
        before, count = self.read_count(self.api.sources, self.owner)
        self.assertEqual(count, 1)
        second = self.f.sale(net='200.00', amount='238.00')
        after, count = self.read_count(self.api.sources, self.owner)
        self.assertEqual(count, 1)
        self.assertEqual({first['id']}, {item['id'] for item in before['items'] if item['kind'] == 'cash'})
        self.assertEqual({first['id'], second['id']}, {item['id'] for item in after['items'] if item['kind'] == 'cash'})
        # A real downstream source tamper is still revalidated after a previous
        # successful read; the joint cache must never mask it on this instance.
        with self.office.db:
            guards = self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name='business_payments' AND sql LIKE '%BEFORE UPDATE%'").fetchall()
            self.assertTrue(guards)
            for guard in guards:
                self.office.db.execute('DROP TRIGGER "' + guard['name'].replace('"', '""') + '"')
            self.office.db.execute("UPDATE business_payments SET amount='0.01' WHERE id=?",
                                   (first['source']['id'],))
        with self.assertRaises((Problem, ValueError)):
            self.api.sources(self.owner)
        self.assertFalse(hasattr(self.api, '_joint_source_cache'))

    def test_revoked_source_rights_and_failed_reads_leave_no_cache(self):
        self.f.sale()
        tech = self.f.fixture.tech
        for permission in ('accounting.read', 'finance.read'):
            self.f.fixture.grant(tech, permission)
        self.api.sources(tech)
        self.f.fixture.grant(tech, 'finance.read', effect='deny', revision=1)
        with self.assertRaises(Problem) as denied:
            self.api.sources(tech)
        self.assertEqual(denied.exception.status, 403)
        self.assertFalse(hasattr(self.api, '_joint_source_cache'))
        self.api.sources(self.owner)
        self.assertFalse(hasattr(self.api, '_joint_source_cache'))


if __name__ == '__main__':
    unittest.main()
