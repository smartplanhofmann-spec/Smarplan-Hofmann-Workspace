"""Reproduce the three old/new SQLite source and hash comparisons.

Run with the repository's backend test environment. This reads the pinned
old source from local Git history and creates only disposable synthetic data.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

root = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(root / 'backend'), str(root / 'backend/business_tests')]
from test_time_billing import TimeBillingTests
from business_time import TimeTracking

old_source = subprocess.check_output(['git', 'show', 'd4df2f5:backend/business_time.py'], cwd=root)
with tempfile.TemporaryDirectory(prefix='smartplan-time-original-') as directory:
    source = Path(directory) / 'before.py'
    source.write_bytes(old_source)
    spec = importlib.util.spec_from_file_location('time_before', source)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    fixture = TimeBillingTests('runTest')
    fixture.setUp()
    result = []
    try:
        fixture.approve()
        before = old.TimeTracking(fixture.office, clock=fixture.time.clock)
        after = TimeTracking(fixture.office, clock=fixture.time.clock)
        for delta in (None, -2, 3):
            if delta is not None:
                after.correct_entry(fixture.owner, fixture.entry, dict(request_id=uuid.uuid4().hex, work_date='2030-01-09', delta_seconds=delta, reason='Synthetic before/after comparison'))
            original = before.approved_billable(fixture.owner, fixture.project, [fixture.entry])
            current = after.approved_billable(fixture.owner, fixture.project, [fixture.entry])
            assert original == current
            query = dict(employee_id=fixture.employee['id'], **{'from': '2030-01-09', 'to': '2030-01-09'})
            assert before.summary(fixture.owner, query) == after.summary(fixture.owner, query)
            result.append(dict(delta=delta, same_source=True, same_summary=True, source=original))
        print(json.dumps(result, indent=2))
    finally:
        fixture.doCleanups()
