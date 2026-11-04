#!/usr/bin/env python3
"""Accepted synthetic opening records and genuine derived 12-digit balances."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_accounting_openings import OpeningWorkflow


def scenario(negative):
    f=OpeningWorkflow('runTest');f.setUp()
    try:
        if negative:
            receipt=f.fixture.incoming();f.fixture.post('input_vat',f.fixture.vat_payload(receipt))
            expense=f.fixture.payout(receipt);f.fixture.post('cash',f.fixture.cash_payload(expense,'materials'))
        else:
            income=f.fixture.sale();f.fixture.post('cash',f.fixture.cash_payload(income))
        original,upload,_=f.original()
        body=f.body(amount='-99999999999.99' if negative else '99999999999.99')
        command=f.command(body);saved=f.api.confirm(f.owner,command)
        return dict(original=original,original_upload=upload,preview_request=body,command=command,saved=saved,
                    state=f.api.state(f.owner),liquidity=f.api.liquidity(f.owner,'2026-11-02'))
    finally:f.doCleanups()


payload=json.dumps(dict(schema_version=1,positive=scenario(False),negative=scenario(True)),ensure_ascii=False,indent=2)+'\n'
for relative in ('docs/fixtures/accounting_openings_large_balances_2026.json','app/test/fixtures/accounting_openings_large_balances_2026.json'):
    target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(payload)
print('Generated actual accepted large-balance fixtures:',len(payload.encode()),'bytes each')
