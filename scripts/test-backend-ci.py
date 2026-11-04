"""Run backend tests for the supported host; keep readable CI annotations.

Windows hosts the portable local SQLite service. The shared online service and
its protected POSIX storage are tested by the complete Linux backend job.
"""
import argparse
from pathlib import Path
import sys
import unittest


PORTABLE_LOCAL_PATTERNS = (
    'test_office.py', 'test_admin_api.py', 'test_backup.py',
    'test_windows_office.py', 'test_report_integrity.py', 'test_customers.py',
    'test_plans.py', 'test_plan_access.py', 'test_workspace_access.py',
    'test_project_workspace.py',
)


def escape(value):
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=('all', 'portable-local'),
                        default='portable-local' if sys.platform == 'win32' else 'all')
    args = parser.parse_args()
    backend = Path(__file__).resolve().parent.parent / "backend"
    if args.scope == 'portable-local':
        print('Portable local backend scope: ' + ', '.join(PORTABLE_LOCAL_PATTERNS), flush=True)
        print('Complete online/POSIX backend coverage remains in the Linux backend job.', flush=True)
        suite = unittest.TestSuite()
        for pattern in PORTABLE_LOCAL_PATTERNS:
            selected = unittest.defaultTestLoader.discover(str(backend), pattern=pattern)
            if not selected.countTestCases():
                raise RuntimeError('Required portable backend tests missing: ' + pattern)
            suite.addTests(selected)
    else:
        suite = unittest.defaultTestLoader.discover(str(backend))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    for test, traceback in result.errors + result.failures:
        print("::error title=" + escape(test.id()) + "::" + escape(traceback), flush=True)
    if not result.testsRun:
        print("::error::No backend tests were discovered", flush=True)
    sys.exit(0 if result.testsRun and result.wasSuccessful() else 1)
