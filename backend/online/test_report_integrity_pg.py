"""Legacy archive and retry contracts on disposable PostgreSQL, never live data."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict

import test_report_integrity as legacy
from online import test_online as fixture
from online.store import PostgresOffice


if fixture.DSN:
    parameters = conninfo_to_dict(fixture.DSN)
    if (parameters.get('dbname') != 'smartplan_check' or
            parameters.get('host') not in ('127.0.0.1', 'localhost')):
        raise RuntimeError('Report integrity tests require disposable loopback smartplan_check.')


@unittest.skipUnless(fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ReportIntegrityPostgres(legacy.ReportIntegrityTests):
    def setUp(self):
        fixture.reset()
        # Keep the replacement alive through restart cases: a temporary SQLite
        # path must not silently switch those cases back to a different store.
        replacement = patch.object(legacy, 'Office', side_effect=lambda path: PostgresOffice(fixture.DSN))
        replacement.start()
        self.addCleanup(replacement.stop)
        super().setUp()

    def test_identical_sign_retries_from_separate_workers_share_original_archive(self):
        ready = threading.Barrier(2)

        def sign_in_worker(_):
            worker = PostgresOffice(fixture.DSN)
            try:
                ready.wait(timeout=5)
                return worker.sign(self.tech, self.report['id'],
                                   self.report['content_hash'], 'Synthetischer Kunde', legacy.STROKES)
            finally:
                worker.db.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            first, repeated = list(workers.map(sign_in_worker, range(2)))
        self.assertEqual(first, repeated)
        self.assertEqual(self.office.report(self.tech, self.report['id']), first)
        self.assertEqual(self.office.db.execute(
            'SELECT COUNT(*) FROM audit WHERE action=? AND object_id=?',
            ('report.signed', self.report['id'])).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
