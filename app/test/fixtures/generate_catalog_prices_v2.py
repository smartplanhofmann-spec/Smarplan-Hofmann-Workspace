"""Regenerate native contract facts from the actual dated-price implementation."""
import base64
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/online')]
from test_business_catalog_prices import CatalogPricesTests, raw, row, request
from business_documents import Documents

def copy(value):return json.loads(json.dumps(value))
f=CatalogPricesTests('test_parser_requires_explicit_role_dates_unit_and_exact_price_basis');f.setUp()
try:
    original=raw(row(),row(price_id='dec',amount='12.00',start='2026-12-01',end=''),row(price_id='buy',role='purchase_net',amount='1.00',basis='3',end=''))
    staged=f.stage(original);detail=f.service.detail(f.owner,staged['id']);decisions=f.choices(staged);preview=f.service.preview(f.owner,staged['id'],decisions)
    accepted,command=f.accept(staged,decisions);article=Documents(f.office).catalog_item(f.owner,'business_articles',accepted['bindings'][0]['article_id'])
    selected={day:f.service.candidates(f.owner,dict(article_id=article['id'],price_role='sales_net',effective_on=day)) for day in ['2026-11-30','2026-12-01']}
    purchase=f.service.candidates(f.owner,dict(article_id=article['id'],price_role='purchase_net',effective_on='2026-11-30'))
    def selection(value):return {key:value[key] for key in ('price_id','price_revision','price_sha256','effective_on')}
    pricing_input=dict(components=[dict(article_id=article['id'],article_revision=article['revision'],quantity='3',price_selection=selection(purchase['items'][0]))])
    pricing=Documents(f.office).pricing_preview(f.owner,pricing_input)
    document=f.draft(positions=[dict(article_id=article['id'],article_revision=article['revision'],quantity='3',catalog_price_selection=selection(next(item for item in selected['2026-11-30']['items'] if item['status']=='eligible')))])
    twin_source=f.service.create_source(f.owner,request(name=f.source['name'],reference='SYNTHETIC-DISTINCT-REFERENCE'))
    twin_import=f.service.stage(f.owner,twin_source['id'],request(catalog_revision='TWIN',filename='twin.csv',content_base64=base64.b64encode(raw(row())).decode()))
    twin_decisions=dict(expected_source_version=0,bindings={'SYN-PRICE':dict(action='bind',article_id=article['id'],article_revision=article['revision'],expected_binding_revision=0,confirm_name_difference=False)},replacements={})
    twin_preview=f.service.preview(f.owner,twin_import['id'],twin_decisions)
    f.service.apply(f.owner,twin_import['id'],request(**twin_decisions,preview_sha256=twin_preview['preview_sha256'],confirmation=True))
    twin_candidates=f.service.candidates(f.owner,dict(article_id=article['id'],price_role='sales_net',effective_on='2026-11-30'))
    after=f.service.detail(f.owner,staged['id']);history=f.service.history(f.owner,f.source['id'],{})
    correction=f.stage(raw(row(amount='11.00')));correction_detail=f.service.detail(f.owner,correction['id']);correction_decisions=f.choices(correction);required=copy(f.service.preview(f.owner,correction['id'],correction_decisions))
    for value in required['required_replacements']:correction_decisions['replacements'][value['external_price_id']]={'revision':value['revision'],'sha256':value['sha256']}
    correction_preview=f.service.preview(f.owner,correction['id'],correction_decisions)
    price_id=accepted['prices'][0]['price_id'];price_history=f.service.price_history(f.owner,price_id);head=price_history['items'][-1]
    withdrawn=f.service.withdraw(f.owner,price_id,request(revision=head['revision'],sha256=head['sha256'],reason='Synthetic native withdrawal',confirmation=True))
    value=dict(twin_source=twin_source,twin_candidates=twin_candidates,source=f.source,original_base64=base64.b64encode(original).decode(),staged=staged,detail=detail,decisions=decisions,preview=preview,application=accepted,command=command,article=article,applied_detail=after,history=history,candidates=selected,purchase_candidates=purchase,pricing=pricing,document=document,correction_detail=correction_detail,correction_decisions=correction_decisions,correction_required=required,correction_preview=correction_preview,price_history=price_history,withdrawn=withdrawn,withdrawn_history=f.service.price_history(f.owner,price_id))
    (ROOT/'app/test/fixtures/catalog_prices_v2.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Actual native fixture:',len(original),'bytes,',len(preview['rows']),'prices,',len(required['required_replacements']),'explicit correction; article policy:',article.get('price_policy'))
finally:f.doCleanups()
