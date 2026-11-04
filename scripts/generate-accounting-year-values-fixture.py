#!/usr/bin/env python3
"""Actual synthetic original-bound year/cash/receipt workflows, no production access."""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
import test_accounting_year_openings as fixture
from business_accounting_year_openings import TABLES,public_source


def scenario(kind):
    f=fixture.YearOpeningWorkflow('runTest');f.setUp()
    try:
        previews=[];original=f.api.preview
        def capture(actor,body):
            result=original(actor,body);previews.append(deepcopy(result));return result
        f.api.preview=capture
        euer_previews=[];original_euer=f.f.euer.api.preview
        def capture_euer(actor,body):
            result=original_euer(actor,body);euer_previews.append(deepcopy(result));return result
        f.f.euer.api.preview=capture_euer
        payload=deepcopy(f.payload)
        if kind=='partial':payload.update(coverage={'from':'2026-08-01','through':'2026-10-31'},controls=payload['controls'][:2])
        if kind=='closed_trade':
            record=deepcopy(f.old['payload']);record.update(external_id='closed-original',counterparty_key='other-supplier',invoice_number='CLOSED-1')
            record['invoice_proof']=f.original('closed supplier original');record['cutover_proof']=f.original('closed actual original payment');record['prior_input_vat']['proof']=f.original('closed already deducted VAT')
            record['prior_payments'][0].update(gross='119.00',net='100.00',tax='19.00',proof=record['cutover_proof'])
            payload['sources'].append(dict(kind='closed_trade',record=record,accounts=f.rules.source['accounts'],cash_entry_keys=['CLOSED-CASH-1'],vat_entry_key='CLOSED-VAT-1'))
            for row,amount in zip(payload['controls'],('-150.00','-28.50','-38.00')):row['amount']=amount
        opening,_=f.f.f.save(amount='1000.00');initial=f.api.state(f.owner)
        entry,command=f.save(payload);preview=previews[-1];posted=f.classify(entry);posted_preview=euer_previews[-1]
        values=dict(initial_state=initial,old_item=f.old,opening_balance=opening,command=command,preview=preview,entry=entry,source=public_source(f.office,'2026'),state_after_acceptance=f.api.state(f.owner),euer_preview=posted_preview,euer_entry=posted)
        if kind=='complete':
            payment,payment_command=f.f.payment(f.old,'59.50',day='2026-11-01');cash=f.f.classify(payment)
            values['new_payment']=dict(command=payment_command,payment=payment,euer_entry=cash)
        values.update(report=f.f.euer.api.report(f.owner,2026),sources=f.f.euer.api.sources(f.owner),liquidity=f.f.f.api.liquidity(f.owner,'2026-11-04'))
        exported=f.f.euer.post('export',dict(year=2026));artifact=f.f.euer.api.exported(f.owner,exported['id'])
        values['export']=artifact
        if kind=='partial':
            f.f.euer.post('reverse',dict(entry_id=posted['id']));void,void_command=f.save(dict(payload,status='void'));void_preview=previews[-1]
            corrected,corrected_command=f.save(f.payload);corrected_preview=previews[-1];corrected_post=f.classify(corrected)
            values['correction']=dict(void=void,void_command=void_command,void_preview=void_preview,entry=corrected,command=corrected_command,preview=corrected_preview,euer_entry=corrected_post,source=public_source(f.office,'2026'),report=f.f.euer.api.report(f.owner,2026))
            assert f.f.euer.api.exported(f.owner,exported['id'])==artifact
        values.update(final_state=f.api.state(f.owner),history=f.api.history(f.owner,'2026'),originals=[dict(original_id=row['id'],entity_key=row['entity_key'],filename=row['filename'],media_type=row['media_type'],sha256=row['sha256'],content_base64=base64.b64encode(bytes(row['original'])).decode()) for row in f.office.db.execute('SELECT * FROM '+TABLES[0]+' ORDER BY created_at,id')])
        assert f.api.confirm(f.owner,command)==entry
        return values
    finally:f.doCleanups()

parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs/fixtures/accounting_year_values_v1.json');args=parser.parse_args()
result=dict(schema_version=1,synthetic=True,generated_by='scripts/generate-accounting-year-values-fixture.py',complete=scenario('complete'),partial_then_corrected=scenario('partial'),closed_trade=scenario('closed_trade'))
path=ROOT/args.output;path.parent.mkdir(exist_ok=True,parents=True);path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),actual_scenarios=3)))
