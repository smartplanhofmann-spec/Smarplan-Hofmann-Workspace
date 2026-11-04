#!/usr/bin/env python3
"""Actual synthetic accepted asset originals, carryover, AfA and corrections."""
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from business_accounting_asset_openings import INPUT
from test_business_accounting_asset_openings import HistoricalAssetWorkflow
from test_accounting_asset_opening_rules import asset


def scenario(under_year=False):
    f=HistoricalAssetWorkflow('runTest');f.setUp()
    try:
        if under_year:f.euer.configure(bookkeeping_start='2026-07-17')
        identity_request=dict(inventory_number=' ＭAẞE-01 ');identity=f.api.identity(f.owner,identity_request)
        initial=f.api.state(f.owner);original,upload,raw=f.original()
        fields=asset(depreciation_in_start_year='500.00',opening_book_value='700.00') if under_year else asset()
        before=f.api.state(f.owner);body=f.body(original=original,asset=fields)
        preview=f.api.preview(f.owner,body);command=f.command(body);saved=f.api.confirm(f.owner,command)
        result=dict(schema_version=1,identity_request=identity_request,identity=identity,state_before_upload=initial,original_upload=upload,original=original,
            state_before=before,preview_request=body,preview=preview,command=command,saved=saved,
            state_after=f.api.state(f.owner),history=f.api.history(f.owner,'m-001'),
            euer_state=f.euer.api.state(f.owner),euer_sources=f.euer.api.sources(f.owner),euer_report_before=f.euer.api.report(f.owner,2026))
        euer_body=f.euer.body('opening_depreciation',f.depreciation_payload(saved))
        euer_preview=f.euer.api.preview(f.owner,euer_body)
        euer_command=dict(euer_body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=euer_preview['preview_hash'])
        depreciation=f.euer.api.confirm(f.owner,euer_command)
        result.update(depreciation_preview_request=euer_body,depreciation_preview=euer_preview,
            depreciation_command=euer_command,depreciation=depreciation,euer_report_after=f.euer.api.report(f.owner,2026))
        reversal=f.euer.post('reverse',dict(entry_id=depreciation['id']))
        corrected_body=f.body(original=original,asset=fields|dict(description='Synthetic corrected original machine description'),reason='Synthetic original description corrected after explicit AfA reversal')
        corrected_preview=f.api.preview(f.owner,corrected_body);corrected_command=f.command(corrected_body)
        correction=f.api.confirm(f.owner,corrected_command)
        result.update(depreciation_reversal=reversal,correction_preview_request=corrected_body,correction_preview=corrected_preview,
            correction_command=corrected_command,correction=correction,state_after_correction=f.api.state(f.owner))
        state=f.api.state(f.owner);void_body={key:correction[key] for key in INPUT}
        void_body.update(expected_revision=state['revision'],state_hash=state['state_hash'],status='void',reason='Synthetic original expressly excluded after reviewed correction')
        void_preview=f.api.preview(f.owner,void_body);void_command=f.command(void_body);void=f.api.confirm(f.owner,void_command)
        result.update(void_preview_request=void_body,void_preview=void_preview,void_command=void_command,void=void,
            state_after_void=f.api.state(f.owner),history_after_void=f.api.history(f.owner,'m-001'),euer_report_void=f.euer.api.report(f.owner,2026))
        return result
    finally:f.doCleanups()


if __name__=='__main__':
    result=scenario();result['under_year']=scenario(True)
    payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    for relative in ('docs/fixtures/accounting_historical_assets_2026.json','app/test/fixtures/accounting_historical_assets_2026.json'):
        target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
    print(json.dumps(dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())))
