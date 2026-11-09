import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {stockReturnData,stockReturnRemaining,stockReturnReceipt,stockReturnAuthorize,stockReturnKey} from '../stock-returns.js';
const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/material_return.json',import.meta.url),'utf8')),f=fixture.main,copy=structuredClone,path='/business/inventory/movements';
const caps={readonly:false,capabilities:['business_inventory'],permissions:['inventory.read','inventory.write','finance.read'],organization:{modules:{material:{enabled:true}}}};
const clean=value=>{const x=copy(value);delete x.request_id;return x;};
const normalized=value=>({...clean(value),quantity:value.quantity.includes('.')?value.quantity.padEnd(value.quantity.indexOf('.')+5,'0'):value.quantity+'.0000'});

test('real partial and final returns keep original issue and historical price after article change',async()=>{
 let state=f.before;assert.equal(f.issue.unit_cost_net,'10.0000');assert.notEqual(f.updated_article.cost_price_net,f.issue.unit_cost_net);
 for(const item of [f.first,f.second,f.final]){
  const body=stockReturnData(f.issue,state.movements,{...item.command,confirmed:true});assert.deepEqual(body,normalized(item.command));assert.equal('unit_cost_net'in body,false);assert.equal('from_location_id'in body,false);
  await stockReturnReceipt(body,f.issue.created_by)(item.returned,{get:async()=>item.returned});state=item.after;
 }
 assert.equal(stockReturnRemaining(f.issue,f.before.movements),'6.0000');assert.equal(stockReturnRemaining(f.issue,f.first.after.movements),'4.0000');assert.equal(stockReturnRemaining(f.issue,f.final.after.movements),'0.0000');assert.equal(f.first.after.stock.on_hand,'6.0000');assert.equal(f.first.after.costs.material_actual_net,'40.00');assert.equal(f.final.after.costs.material_actual_net,'0.00');
});

test('real per-original rounding remainder is kept by the last return',async()=>{
 const r=fixture.rounding;assert.deepEqual(r.returns.map(v=>v.returned.cost_net),['0.3333','0.3333','0.3334']);for(const v of r.returns)await stockReturnReceipt(v.command,r.issue.created_by)(v.returned,{get:async()=>v.returned});assert.equal(r.after.costs.material_actual_net,'0.00');
});

test('zero, excess quantity, malformed decimal, missing confirmation, and foreign journal are rejected before POST',()=>{
 for(const change of [v=>v.quantity='0',v=>v.quantity='6.0001',v=>v.quantity='1e2',v=>v.quantity='-1',v=>v.confirmed=false,v=>v.to_location_id='']){const v={...f.first.command,confirmed:true};change(v);assert.throws(()=>stockReturnData(f.issue,f.before.movements,v));}
 const numeric=copy(f.before.movements);numeric.find(v=>v.kind==='issue').quantity=6;assert.throws(()=>stockReturnRemaining(f.issue,numeric));
 const foreign=copy(f.first.after.movements);foreign.find(v=>v.kind==='return').project_id='f'.repeat(32);assert.throws(()=>stockReturnRemaining(f.issue,foreign));
});

test('operational users validate an actual redacted return without private price fields',async()=>{
 const x=f.operational;assert.equal(x.issue.cost_net,undefined);assert.equal(x.returned.cost_net,undefined);assert.equal(x.returned.article_snapshot.cost_price_net,undefined);
 await stockReturnReceipt(x.command,x.returned.created_by)(x.returned,{get:async()=>x.returned});
});

test('return receipt rejects changed quantity, project, original, recipient or readback',async()=>{
 for(const change of [v=>v.quantity='3.0000',v=>v.project_id='e'.repeat(32),v=>v.reversal_of='e'.repeat(32),v=>v.to_location_id='e'.repeat(32),v=>v.created_by='e'.repeat(32)]){const v=copy(f.first.returned);change(v);await assert.rejects(stockReturnReceipt(f.first.command,f.issue.created_by)(v,{get:async()=>v}));}
 const v=copy(f.first.returned);v.note='Changed after response';await assert.rejects(stockReturnReceipt(f.first.command,f.issue.created_by)(f.first.returned,{get:async()=>v}));
});

test('accepted unknown return retains exact request through permission loss and zero remaining quantity',async()=>{
 const body=clean(f.final.command),key=stockReturnKey(f.project_id),posts=[];let lost=true,write=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted reply lost');}return Response.json(f.final.returned);}
  if(url.endsWith('/me'))return Response.json({id:f.issue.created_by});if(url.includes('/capabilities'))return Response.json({...caps,permissions:write?caps.permissions:['inventory.read']});
  if(url.endsWith('/'+f.issue.id))return Response.json(f.issue);if(url.endsWith('/'+f.final.returned.id))return Response.json(f.final.returned);return Response.json({items:f.final.after.movements});
 }});api.setToken('synthetic-stock-return');await assert.rejects(api.mutate(key,path,body,{validate:result=>stockReturnReceipt(body,f.issue.created_by)(result,api)}));
 write=false;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);assert.equal(posts.length,1);write=true;await api.retry(key);assert.deepEqual(posts[0],posts[1]);assert.equal(api.pendingCount,0);
});

test('fresh first write rejects changed remaining quantity but same original replay still authorizes',async()=>{
 const api={get:async url=>url.includes('/capabilities')?caps:url==='/me'?{id:f.issue.created_by}:url.endsWith('/'+f.issue.id)?f.issue:{items:f.final.after.movements}};
 await assert.rejects(stockReturnAuthorize(api,f.first.command));await stockReturnAuthorize(api,f.first.command,{replay:true});
});

test('closing retry during fresh read preserves original without a second POST',async()=>{
 const body=clean(f.first.command),key=stockReturnKey(f.project_id),posts=[];let close=false,closed=false;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='POST'){posts.push(JSON.parse(options.body));throw new Error('Synthetic lost response');}if(url.includes('/capabilities'))return Response.json(caps);if(url.endsWith('/me'))return Response.json({id:f.issue.created_by});if(close)closed=true;return Response.json(f.issue);}});api.setToken('synthetic-return-close');await assert.rejects(api.mutate(key,path,body));close=true;await assert.rejects(api.retry(key,{stillCurrent:()=>!closed}));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
});
