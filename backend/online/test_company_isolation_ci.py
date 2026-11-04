"""The mandatory CI acceptance must select the same guarded disposable cluster."""
from pathlib import Path
import re
import unittest

from psycopg.conninfo import conninfo_to_dict

from online import provisioning
from online.test_provisioning import company


class CompanyIsolationCIContract(unittest.TestCase):
    def test_online_ci_database_is_accepted_by_real_provisioning_guard(self):
        source = (Path(__file__).resolve().parents[2] / '.github/workflows/checks.yml').read_text()
        job = source.split('\n  online-api:\n', 1)[1].split('\n  https-setup:', 1)[0]
        configured = re.search(r'^      SMARTPLAN_TEST_DSN: ([^\n]+)$', job, re.M)
        self.assertIsNotNone(configured, 'Explicit disposable online CI database configuration required')
        dsn = configured.group(1)
        # This is the real operator boundary, without connecting to any database.
        provisioning._operator_dsn(company('testcicontract'), dsn, test_mode=True)
        host_port = conninfo_to_dict(dsn)['port']
        self.assertRegex(job, r'(?m)^          - ' + re.escape(host_port) + r':5432$')


if __name__ == '__main__':
    unittest.main()
