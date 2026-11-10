"""Generate both clients' sample from actual MFA/HTTP and pinned provider parser."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
from online.test_bank_feeds_service import BankFeedTests

fixture=BankFeedTests('runTest')
try:
    fixture.setUp()
    fixture.body=dict(updated_from='2026-11-01T00:00:00.000Z',updated_to='2026-11-10T00:00:00.000Z')
    value=dict(
        status=fixture.call('GET','/bank-feeds/qonto/status').json,
        body=fixture.body,
        result=fixture.read().json,
        accounts=fixture.call('GET','/business/bank/accounts').json,
        capabilities=fixture.call('GET','/business/capabilities').json,
    )
    target=Path(__file__).with_name('qonto_readonly.json')
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(path=str(target.relative_to(ROOT)),bytes=target.stat().st_size,source='actual MFA/HTTP and bounded Qonto parser',real_bank_access=False)))
finally:
    fixture.doCleanups()
