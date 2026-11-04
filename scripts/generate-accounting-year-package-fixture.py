#!/usr/bin/env python3
"""Actual accepted synthetic years and exact bytes, never handwritten DTOs."""
import base64
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'backend/online')]
import test_accounting_year_package as fixtures
import test_business_accounting_open_items as old_fixtures
import test_business_accounting_asset_openings as asset_fixtures
import test_business_payroll_cash as payroll_fixtures
import test_business_travel_finance as travel_fixtures
from business_accounting_euer import EuerAccounting,dispatch
from business_accounting_asset_openings import HistoricalAssets
from accounting_year_package_v1 import sha


def capture(office,actor,entry):
    path='/accounting/euer/exports/'+entry['id']
    export,status,kind=dispatch(office,actor,path,'GET',{})
    assert status==200 and kind=='application/json'
    metadata,status,kind=dispatch(office,actor,path+'/evidence','GET',{})
    assert status==200 and kind=='application/json'
    raw,status,kind=dispatch(office,actor,path+'/evidence/archive','GET',{})
    assert status==200 and kind=='application/zip' and sha(bytes(raw))==metadata['sha256']
    return dict(export=export,metadata=metadata,archive_base64=base64.b64encode(raw).decode())


def main():
    result=dict(schema_version=1,format='smartplan-year-evidence-v1',synthetic_only=True,scenarios={})
    f=fixtures.YearPackageTests('runTest');f.setUp()
    try:
        export,unused,unused2=f.year();result['scenarios']['ordinary_correction']=capture(f.office,f.owner,export)
        f.f.configure(bookkeeping_start='2026-07-01');incomplete=f.f.post('export',dict(year=2026))
        result['scenarios']['incomplete_year']=capture(f.office,f.owner,incomplete)
        result['scenarios']['old_after_profile_change']=capture(f.office,f.owner,export)
        assert result['scenarios']['ordinary_correction']==result['scenarios']['old_after_profile_change']
        old=old_fixtures.OpeningItemWorkflow('runTest');old.setUp()
        try:
            f.bind_other(old.office)
            asset=asset_fixtures.HistoricalAssetWorkflow('runTest');asset.f=old.f;asset.office=old.office;asset.owner=old.owner;asset.euer=old.euer
            asset.api=HistoricalAssets(old.office,clock=lambda:old.f.now)
            item,_=old.save('item','supplier-a',old.item('supplier-a','payable',prior=True));payment,_=old.payment(item,'79.33');old.classify(payment)
            historical,_=asset.save();old.euer.post('opening_depreciation',asset.depreciation_payload(historical))
            export=old.euer.post('export',dict(year=2026));result['scenarios']['historical_assets_old_supplier']=capture(old.office,old.owner,export)
        finally:old.doCleanups()
        payroll=payroll_fixtures.PayrollCashTests('runTest');payroll.setUp()
        try:
            data,run,identity,paid=payroll.case();batch=payroll.import_cash(payroll.body(paid));payroll.post('payroll_cash',payroll.payload(batch))
            export=payroll.post('export',dict(year=2026));result['scenarios']['public_payroll']=capture(payroll.office,payroll.owner,export)
        finally:payroll.doCleanups()
        travel=travel_fixtures.TravelFinanceTests('runTest');travel.setUp()
        try:
            payment,unused=travel.paid();travel.post('travel_cash',travel.payload(payment))
            export=travel.post('export',dict(year=2026));result['scenarios']['public_travel']=capture(travel.office,travel.owner,export)
        finally:travel.doCleanups()
    finally:f.doCleanups()
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    for relative in ('docs/fixtures/accounting_year_package_v1.json','app/test/fixtures/accounting_year_package_v1.json'):
        path=ROOT/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    print(json.dumps(dict(bytes=len(raw),sha256=sha(raw),scenarios=list(result['scenarios']))))


if __name__=='__main__':main()
