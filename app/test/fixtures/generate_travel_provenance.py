"""Controlled actual CRLF travel acceptance for independent package checking."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
from test_business_travel_provenance import TravelOriginalTransport

TravelOriginalTransport.setUpClass()
f=TravelOriginalTransport('runTest')
try:
    f.setUp();trip,command,receipt=f.original();record=receipt['result']
    source=record['sources'];d=record['details']
    payload=dict(trips=source['trips'],sites=source['sites'],parameters=dict(
        history_trips=source['history_trips'],settlement_unit=d['settlement_unit'],
        tax_choice=d['tax_choice'],requested_meal_minor=d['requested_meal_minor'],
        requested_lodging_minor=d['requested_lodging_minor'],already_paid_minor=0,
        rule_version=record['calculation']['rule_version']))
    result=dict(record=record,payload=payload,calculation_lf=f.recompute(record))
    Path(__file__).with_name('travel_provenance_workflow.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(dict(rule=record['calculation']['rule_version'],tax_free_minor=record['calculation']['totals']['tax_free_minor'],
        original_crlf_rule_hash=record['calculation']['rule_hash'],lf_rule_hash=result['calculation_lf']['rule_hash'])))
finally:
    f.doCleanups();TravelOriginalTransport.doClassCleanups()
