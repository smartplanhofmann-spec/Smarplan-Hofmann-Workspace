"""Generate synthetic client fixtures from the actual accepted bank journal."""
import base64
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_bank_camt import CamtBankTests
f=CamtBankTests('runTest');f.setUp()
try:
 request=f.inspect_body();inspection=f.camt.inspect(f.owner,request)
 body=f.body();preview=f.camt.preview_import(f.owner,body)
 command=f.req(**body,preview_hash=preview['preview_hash'],confirmation=True)
 receipt=f.camt.import_statement(f.owner,command)
 value=dict(request=request,inspection=inspection,body=body,preview=preview,command=command,receipt=receipt,statement=f.bank.statement(f.owner,receipt['statement']['id']))
 path=ROOT/'app/test/fixtures/bank_camt.json';path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(path)
finally:f.doCleanups()
