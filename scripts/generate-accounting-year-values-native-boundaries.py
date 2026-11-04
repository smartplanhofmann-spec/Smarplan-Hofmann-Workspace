#!/usr/bin/env python3
"""Separate actual native read/replay boundaries; preserves frozen core fixture."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_accounting_year_openings import YearOpeningWorkflow
result={'schema_version':1,'synthetic_only':True,'generated_by':'scripts/generate-accounting-year-values-native-boundaries.py'}
for name,change in [('missing_start',dict(bookkeeping_start=None)),('missing_vat_timing',dict(vat_timing=None))]:
    f=YearOpeningWorkflow('runTest');f.setUp()
    try:
        before=f.api.state(f.owner);preview=f.api.preview(f.owner,f.body());entry,command=f.save()
        f.f.euer.configure(**change)
        state=f.api.state(f.owner);replay=f.api.confirm(f.owner,command)
        assert replay==entry
        result[name]=dict(before=before,preview=preview,entry=entry,command=command,state=state,replay=replay,history=f.api.history(f.owner,'2026'),old_item=f.old)
    finally:f.doCleanups()
raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
for p in ['docs/fixtures/accounting_year_values_native_boundaries_v1.json','app/test/fixtures/accounting_year_values_native_boundaries_v1.json']:(ROOT/p).write_bytes(raw)
print(json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))
