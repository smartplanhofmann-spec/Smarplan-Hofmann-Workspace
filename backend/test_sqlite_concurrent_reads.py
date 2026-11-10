"""Real shared SQLite reads must never lose or merge immutable schema rows."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest

import business_schema
from core import Office


class SharedSQLiteReads(unittest.TestCase):
    def test_concurrent_schema_readers_retain_every_control_table_and_exact_row(self):
        with tempfile.TemporaryDirectory() as directory:
            office = Office(Path(directory)/'synthetic-shared-reads.sqlite')
            try:
                query = "SELECT name FROM sqlite_master WHERE type='table'"
                expected = sorted(row[0] for row in office.db.execute(query).fetchall())
                self.assertTrue(business_schema.CONTROL_TABLES <= set(expected))
                barrier = threading.Barrier(8)
                def read(worker):
                    failures = []; barrier.wait(timeout=10)
                    for index in range(300):
                        # Inventory/schema views and existing direct domain
                        # reads share the same actual Office connection.
                        if worker % 2:
                            with office.lock:
                                actual = [row[0] for row in office.db.execute(query).fetchall()]
                        else:
                            actual = [row[0] for row in office.db.execute(query).fetchall()]
                        if sorted(actual) != expected:
                            failures.append(dict(worker=worker, index=index,
                                expected_rows=len(expected), actual_rows=len(actual),
                                missing_controls=sorted(business_schema.CONTROL_TABLES-set(actual))))
                            break
                    return failures
                with ThreadPoolExecutor(max_workers=8) as pool:
                    failures = [failure for group in pool.map(read, range(8)) for failure in group]
                self.assertEqual(failures, [])
                self.assertEqual(sorted(row[0] for row in office.db.execute(query).fetchall()), expected)
                self.assertFalse(office.db.in_transaction)
            finally:
                office.db.close()


if __name__ == '__main__': unittest.main()
