import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi,StaleSession} from '../office.js';
import {ASSET_PATH,assetIdentity,assetMoney,assetState,assetPreview,assetRecord,assetHistory,assetInput,assetReceiptValidator,assetUploadValidator,assetPendingAuthorize,historicalSource} from '../accounting-historical-assets-contract.js';
import {euerSources,euerReport,euerForm,euerValidator} from '../accounting-euer.js';
const f=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_historical_assets_2026.json',import.meta.url)));
const clone=structuredClone,withoutNonce=v=>{const b=clone(v);delete b.request_id;return b;};
const caps=()=>({readonly:false,features:['accounting_historical_assets'],capabilities:['business_accounting_asset_openings'],permissions:['accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}});

test('actual historical original, state, preview, correction and void keep original identity and profile',async()=>{
 for(const data of[f,f.under_year]){
  for(const key of ['state_before_upload','state_before','state_after','state_after_correction','state_after_void'])await assetState(data[key]);
  for(const key of ['saved','correction','void'])await assetRecord(data[key]);
  await assetPreview(data.preview,data.preview_request);await assetPreview(data.correction_preview,data.correction_preview_request);await assetHistory(data.history_after_void,data.saved.asset_key);
  await assetReceiptValidator(withoutNonce(data.command),data.preview,data.state_before)(data.saved);
  await assetReceiptValidator(withoutNonce(data.correction_command),data.correction_preview,data.state_after)(data.correction);
  await assetReceiptValidator(withoutNonce(data.void_command),data.void_preview,data.state_after_correction)(data.void);
  assetUploadValidator(withoutNonce(data.original_upload),data.original)(data.original);
 }
 assert.equal(f.under_year.preview.start_year.amount,'700.00');assert.equal(f.under_year.saved.asset.depreciation_in_start_year,'500.00');
});
test('server Unicode identity is exact and input uses original explicit values including documented zeros',()=>{
 assert.equal(assetIdentity(f.identity,f.identity_request).asset_key,'masse-01');
 assert.throws(()=>assetIdentity({...f.identity,inventory_number:'Other'},f.identity_request));
 const body=f.preview_request,identity={inventory_number:body.asset.inventory_number,asset_key:body.asset_key},values={...body.asset,...body.source,original_id:f.original.id,reason:body.reason};
 assert.deepEqual(assetInput(f.state_before,identity,values),body);
 assert.deepEqual(assetInput(f.state_after_correction,identity,{status:'void',reason:f.void_preview_request.reason},f.correction),f.void_preview_request);
 for(const value of ['',null,' ','1.001','-1.00','100000000000.00'])assert.throws(()=>assetMoney(value));
 assert.equal(assetMoney('0'),'0.00');assert.throws(()=>assetInput(f.state_before,identity,{...values,opening_book_value:''}));
 assert.throws(()=>assetInput(f.state_before,identity,{...values,unchanged_linear_history_confirmed:false}));
});
test('substituted original, cutoff, amount, historical profile and acquisition flags fail closed',async()=>{
 for(const mutate of [v=>v.asset_key='other',v=>v.source.sha256='f'.repeat(64),v=>v.source.position='Other position',v=>v.source.history_through='2025-12-30',v=>v.asset.opening_book_value='0.00',v=>v.profile.profile.bookkeeping_start='2026-02-01',v=>v.acquisition_created=true,v=>v.euer_postings_created=true,v=>v.preview_hash='f'.repeat(64)]){
  const bad=clone(f.preview);mutate(bad);await assert.rejects(assetPreview(bad,f.preview_request));
 }
 const invalid=clone(f.saved);invalid.asset.inventory_number='Forged inventory';await assert.rejects(assetRecord(invalid));
 await assert.rejects(assetReceiptValidator(withoutNonce(f.command),f.preview,f.state_before)(f.correction));
});
test('actual EÜR source and separate follow-up use immutable historical source and no new cash or input VAT',()=>{
 for(const data of[f,f.under_year]){
  euerSources(data.euer_sources);euerReport(data.euer_report_before,2026);euerReport(data.euer_report_after,2026);
  const source=historicalSource(data.euer_sources.items.find(i=>i.kind==='opening_asset').source),spec=euerForm('opening_depreciation',source);
  assert.deepEqual(spec.payload({year:2026,account:'6220'}),data.depreciation_preview_request.payload);
  euerValidator(withoutNonce(data.depreciation_command),data.depreciation_preview)(data.depreciation);
  assert.deepEqual(data.euer_report_before.cash_movements,data.euer_report_after.cash_movements);
  assert.equal(data.euer_report_after.totals.confirmed_input_vat,'0.00');
 }
});
test('accepted lost acknowledgment preserves exact bytes and checks freshly revoked rights or paused finance',async()=>{
 const permission=caps(),posts=[],key='accounting-historical-asset-confirm-'+f.saved.asset_key,path='/business'+ASSET_PATH+'/confirm';let lose=true,wrong=false;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return Response.json(url.includes('/capabilities')?permission:f.state_after);posts.push(JSON.parse(options.body));if(lose){lose=false;throw Error('Synthetic response lost');}return Response.json(wrong?f.correction:f.saved);}});api.setToken('synthetic-asset-session');
 await assert.rejects(api.mutate(key,path,withoutNonce(f.command),{validate:assetReceiptValidator(withoutNonce(f.command),f.preview,f.state_before)}));
 permission.permissions=permission.permissions.filter(p=>p!=='finance.read');await assert.rejects(api.retry(key),e=>e.status===403);assert.equal(posts.length,1);
 permission.permissions.push('finance.read');permission.organization.modules.finance.enabled=false;await assert.rejects(api.retry(key),e=>e.status===423);assert.equal(posts.length,1);
 permission.organization.modules.finance.enabled=true;wrong=true;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);wrong=false;await api.retry(key);assert.equal(api.pendingCount,0);
 for(const post of posts)assert.deepEqual(post,posts[0]);await assert.rejects(assetPendingAuthorize(api,{key:'wrong',path}),e=>e.status===409);
});
test('asynchronous original receipt validation cannot consume a new pending request after session replacement',async()=>{
 let enter,release;const begun=new Promise(r=>enter=r),held=new Promise(r=>release=r),key='accounting-historical-asset-confirm-'+f.saved.asset_key,path='/business'+ASSET_PATH+'/confirm';
 const api=new OfficeApi({fetcher:async()=>Response.json(f.saved)});api.setToken('synthetic-old-asset-session');
 const pending=api.mutate(key,path,withoutNonce(f.command),{validate:async raw=>{enter();await held;return assetReceiptValidator(withoutNonce(f.command),f.preview,f.state_before)(raw);}});await begun;api.setToken('synthetic-new-asset-session');
 await assert.rejects(api.mutate(key,path,withoutNonce(f.command),{validate:()=>{throw Error('Synthetic unresolved new receipt');}}));const replacement=api.pendingCommandValues(key,path);release();await assert.rejects(pending,StaleSession);assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,path),replacement);
});
