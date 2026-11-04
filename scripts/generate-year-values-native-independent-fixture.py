#!/usr/bin/env python3
"""Independent actual domain evidence; does not modify the frozen 441f fixture."""
from pathlib import Path
import hashlib
import json
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from core import Problem
from business_accounting_year_openings import YearValues
from test_accounting_year_openings import YearOpeningWorkflow
from test_business_accounting_open_items import OpeningItemWorkflow

result={'schema_version':1,'synthetic_only':True,'generated_by':'scripts/generate-year-values-native-independent-fixture.py'}
f=YearOpeningWorkflow('runTest');f.setUp()
try:
    entry,command=f.save();posted=f.classify(entry)
    void=dict(f.payload,status='void')
    try:f.api.preview(f.owner,f.body(void))
    except Problem as error:assert error.status==409;blocked=dict(status=error.status,message=error.message)
    else:raise AssertionError('Active EÜR must block void')
    reverse=f.f.euer.post('reverse',{'entry_id':posted['id']})
    f.f.euer.configure(bookkeeping_start=None)
    state=f.api.state(f.owner);assert state['profile'] is None and state['can_prepare'] is False
    body=f.body(void);body['profile_ref']=entry['profile_ref']
    preview=f.api.preview(f.owner,body)
    request=dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
    accepted=f.api.confirm(f.owner,request)
    result['void_after_missing_start']=dict(initial_state=state,preview=preview,command=request,entry=accepted,
        original_entry=entry,original_command=command,old_item=f.old,euer_posted=posted,blocked_before_reverse=blocked,
        euer_reverse=reverse,state_after_acceptance=f.api.state(f.owner),history=f.api.history(f.owner,'2026'))
finally:f.doCleanups()

fresh=OpeningItemWorkflow('runTest');fresh.setUp()
try:
    fresh.euer.configure(vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01')
    helper=YearOpeningWorkflow('runTest');helper.f=fresh;helper.office=fresh.office;helper.owner=fresh.owner
    helper.api=YearValues(fresh.office,clock=lambda:fresh.f.now)
    helper.payload=dict(status='active',coverage={'from':'2026-01-01','through':'2026-10-31'},sources=[],controls=[],
        ledger_proof=helper.original('Explicit independent complete zero journal with reviewed zero controls'),
        attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))
    state=helper.api.state(helper.owner);body=helper.body();preview=helper.api.preview(helper.owner,body);entry,command=helper.save()
    result['actual_evidenced_zero']=dict(initial_state=state,preview=preview,command=command,entry=entry,
        state_after_acceptance=helper.api.state(helper.owner),history=helper.api.history(helper.owner,'2026'))
finally:fresh.doCleanups()

raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
for relative in ('docs/fixtures/accounting_year_values_native_independent_v1.json','app/test/fixtures/accounting_year_values_native_independent_v1.json'):
    (ROOT/relative).write_bytes(raw)
print(json.dumps({'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}))
