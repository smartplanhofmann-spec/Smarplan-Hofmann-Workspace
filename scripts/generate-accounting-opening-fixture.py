#!/usr/bin/env python3
"""Regenerate accepted synthetic opening-balance DTOs through real commands."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from business_accounting_openings import INPUT
from test_business_accounting_openings import OpeningWorkflow


def scenario():
    f = OpeningWorkflow('runTest'); f.setUp()
    try:
        euer = f.fixture
        incoming = euer.sale(); euer.post('cash', euer.cash_payload(incoming))
        receipt = euer.incoming(); euer.post('input_vat', euer.vat_payload(receipt))
        payout = euer.payout(receipt); euer.post('cash', euer.cash_payload(payout, 'materials'))
        sources_before_original_upload = f.api.sources(f.owner, f.account['id'])
        liquidity_before = f.api.liquidity(f.owner, '2026-11-02')
        original, upload, raw = f.original()
        state = f.api.state(f.owner); sources = f.api.sources(f.owner, f.account['id'])
        body = f.body(); preview = f.api.preview(f.owner, body); command = f.command(body)
        saved = f.api.confirm(f.owner, command)
        result = dict(schema_version=1, original_upload=upload, original=original, state_before=state,
            sources_before_original_upload=sources_before_original_upload, liquidity_before=liquidity_before,
            sources=sources, preview_request=body, preview=preview, command=command, saved=saved,
            state_after=f.api.state(f.owner), history=f.api.history(f.owner, f.account['id']),
            liquidity=f.api.liquidity(f.owner, '2026-11-02'),
            euer_state=euer.api.state(f.owner), euer_sources=euer.api.sources(f.owner),
            euer_report=euer.api.report(f.owner, 2026))
        correction_body=f.body(amount='1001.00'); correction_command=f.command(correction_body)
        correction=f.api.confirm(f.owner,correction_command)
        result.update(correction_preview_request=correction_body, correction_command=correction_command,
            correction=correction, state_after_correction=f.api.state(f.owner), corrected_liquidity=f.api.liquidity(f.owner,'2026-11-02'))
        void_body={key:correction[key] for key in INPUT}; current=f.api.state(f.owner)
        void_body.update(expected_revision=current['revision'],state_hash=current['state_hash'],status='void',reason='Synthetic original reviewed; opening explicitly voided')
        void_command=f.command(void_body); void=f.api.confirm(f.owner,void_command)
        result.update(void_preview_request=void_body,void_command=void_command,void=void,
            state_after_void=f.api.state(f.owner),
            void_liquidity=f.api.liquidity(f.owner,'2026-11-02'),history_after_void=f.api.history(f.owner,f.account['id']))
        return result
    finally:
        f.doCleanups()


def bank_scenario():
    f=OpeningWorkflow('runTest');f.setUp()
    try:
        statement=f.bank_statement(opening='-100.00')
        state=f.api.state(f.owner);sources=f.api.sources(f.owner,f.account['id'])
        body=f.body(amount='-100.00',source=sources['bank_statements'][0]['source'])
        preview=f.api.preview(f.owner,body);command=f.command(body);saved=f.api.confirm(f.owner,command)
        return dict(statement=statement,state_before=state,sources=sources,preview_request=body,preview=preview,
            command=command,saved=saved,state_after=f.api.state(f.owner),liquidity=f.api.liquidity(f.owner,'2026-01-31'))
    finally:
        f.doCleanups()


result=scenario();result['bank']=bank_scenario()
payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
for relative in ('docs/fixtures/accounting_openings_2026.json','app/test/fixtures/accounting_openings_2026.json'):
    target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(payload)
print('Generated actual accepted opening-balance fixtures:',len(payload.encode()),'bytes each')
