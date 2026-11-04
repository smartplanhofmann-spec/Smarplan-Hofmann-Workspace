#!/usr/bin/env python3
"""Only synthetic, actually accepted domain commands; no production access."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
from business_accounting_open_items import TABLES,public_source
from core import Problem
import test_business_accounting_open_items as fixture

def scenario(direction,prior=False,correction=False):
    f=fixture.OpeningItemWorkflow('runTest');f.setUp()
    try:
        previews=[];real_preview=f.api.preview
        def capture_preview(actor,body):
            value=real_preview(actor,body);previews.append(deepcopy(value));return value
        f.api.preview=capture_preview
        from business_api import dispatch
        accounts=dispatch(f.office,f.owner,'/business/accounting/accounts','GET',{})[0]
        key='synthetic-'+direction
        payload=f.item(key,direction,prior=prior);before=f.api.state(f.owner);entry,command=f.save('item',key,payload)
        values=dict(initial_state=before,item_command=command,item_preview=previews[-1],accounts=accounts,item=entry,state_after_item=f.api.state(f.owner),payments=[])
        amounts=['39.67','39.66'] if prior else ['59.50'] if correction else ['119.00']
        for index,amount in enumerate(amounts):
            payment,payment_command=f.payment(entry,amount,day='2026-02-'+str(15+index));source=public_source(f.office,payment['entity_key']);posted=f.classify(payment)
            values['payments'].append(dict(command=payment_command,preview=previews[-1],payment=payment,source=source,euer_entry=posted))
        if correction:
            f.euer.post('reverse',dict(entry_id=posted['id']))
            void,void_command=f.save('payment',payment['entity_key'],dict(payment['payload'],status='void'))
            void_preview=previews[-1]
            corrected,correct_command=f.save('payment',payment['entity_key'],dict(payment['payload'],amount='119.00'))
            corrected_post=f.classify(corrected)
            values['correction']=dict(void=void,void_preview=void_preview,void_command=void_command,command=correct_command,preview=previews[-1],payment=corrected,source=public_source(f.office,corrected['entity_key']),euer_entry=corrected_post)
        values.update(final_state=f.api.state(f.owner),sources=f.euer.api.sources(f.owner),report=f.euer.api.report(f.owner,2026),history=f.api.history(f.owner,key),
                      originals=[dict(entity_key=row['entity_key'],filename=row['filename'],media_type=row['media_type'],sha256=row['sha256'],original_id=row['id'],content_base64=base64.b64encode(bytes(row['original'])).decode()) for row in f.office.db.execute('SELECT * FROM '+TABLES[0]+' ORDER BY created_at,id')])
        assert f.api.confirm(f.owner,command)==entry
        return values
    finally:f.doCleanups()

result=dict(schema_version=1,synthetic=True,generated_by='scripts/generate-accounting-open-items-fixture.py',
            receivable_prior_parts=scenario('receivable',True),payable_old_input_vat=scenario('payable'),clerical_payment_correction=scenario('receivable',correction=True))
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs/fixtures/accounting_open_items_v1.json');args=parser.parse_args()
path=ROOT/args.output;path.parent.mkdir(exist_ok=True,parents=True)
path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),actual_scenarios=3)))
