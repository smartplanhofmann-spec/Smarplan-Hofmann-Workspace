"""Repeat the existing actual HTTP/ACL test at three UTC clock boundaries."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
from online import test_business_boundary_review as fixture

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
phase=sys.argv[1];assert phase in ('before','after')
method='test_project_planning_deny_also_filters_global_calendar_collection'
results=[];started=time.monotonic()
for hour in (12,22,23):
 frozen=datetime(2026,11,4,hour,30,tzinfo=timezone.utc)
 class BoundaryClock(datetime):
  @classmethod
  def now(cls,tz=None):
   return frozen.astimezone(tz) if tz else frozen.replace(tzinfo=None)
 with (OUT/(phase+'-'+str(hour)+'.txt')).open('w') as log,patch.object(fixture,'datetime',BoundaryClock):
  result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite([fixture.BusinessBoundaryReviewTests(method)]))
 results.append({'utc':frozen.isoformat(),'success':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors)})
paths=['backend/online/test_business_boundary_review.py','backend/business_planning.py']
metadata={'phase':phase,'source_commit':'bd8caef6ffcfa0cdf6bbd4314ddb393ad49dd806','duration_seconds':round(time.monotonic()-started,3),'results':results,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'real_HTTP_and_ACL':True,'clock_replaced_only_in_test_module':True}
(OUT/(phase+'-result.json')).write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata['results']))
expected=[True,True,False] if phase=='before' else [True,True,True]
raise SystemExit(0 if [r['success'] for r in results]==expected else 1)
