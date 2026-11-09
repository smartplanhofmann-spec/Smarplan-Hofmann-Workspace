"""Run every root payroll test once; PostgreSQL suites use separate DSN guards."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/business_tests'),str(ROOT/'backend/online')]
modules=[path.stem for path in sorted((ROOT/'backend').glob('test*payroll*.py'))]
suite=unittest.defaultTestLoader.loadTestsFromNames(modules)
seen=set();unique=[];duplicates=[]


def collect(group):
    for item in group:
        if isinstance(item,unittest.TestSuite):collect(item)
        elif item.id() in seen:duplicates.append(item.id())
        else:seen.add(item.id());unique.append(item)


collect(suite)
print(json.dumps(dict(modules=len(modules),unique_test_cases=len(unique),
    duplicate_discovery_entries_removed=len(duplicates))),flush=True)
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(unique))
raise SystemExit(0 if result.wasSuccessful() else 1)
