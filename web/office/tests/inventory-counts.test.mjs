import test from 'node:test';
import assert from 'node:assert/strict';
import {inventoryQuantity,inventoryCountValues,inventoryCountRights,inventoryCountRecord,inventoryCountPendingAuthorize} from '../inventory-counts.js';
import {OfficeApi} from '../office.js';

const id='a'.repeat(32),article='b'.repeat(32),location='c'.repeat(32);
const caps=()=>({readonly:false,features:['inventory_counts'],capabilities:['business_inventory_counts'],permissions:['inventory.read','inventory.write','finance.read','finance.write','finance.approve'],organization:{modules:{material:{enabled:true}}}});
const record=()=>({id,revision:2,status:'counted',history_sha256:'d'.repeat(64),items:[{article:{id:article},on_hand:'10.0000'}]});

test('physical quantities preserve exact four decimal text and require difference explanation',()=>{
  assert.equal(inventoryQuantity('00012,3456'),'12.3456');
  assert.equal(inventoryQuantity('999999999999.9999'),'999999999999.9999');
  for(const value of ['-1','1e3','NaN','','1.00001'])assert.throws(()=>inventoryQuantity(value));
  assert.throws(()=>inventoryCountValues(record(),{['quantity_'+article]:'9',['reason_'+article]:''}));
  assert.deepEqual(inventoryCountValues(record(),{['quantity_'+article]:'9',['reason_'+article]:'Bruch'}),{revision:2,lines:[{article_id:article,quantity:'9.0000',reason:'Bruch'}]});
});
test('financial approval is separate from counting and paused material stays readable',()=>{
  assert.deepEqual(inventoryCountRights(caps()),{read:true,write:true,approve:true});
  assert.equal(inventoryCountRights({...caps(),permissions:['inventory.read','inventory.write']}).approve,false);
  assert.deepEqual(inventoryCountRights({...caps(),organization:{modules:{material:{enabled:false}}}}),{read:true,write:false,approve:false});
  for(const field of ['features','capabilities','permissions'])assert.equal(inventoryCountRights({...caps(),[field]:[]}).read,false);
});
test('archive response validates object, exact revision and status',()=>{
  assert.equal(inventoryCountRecord(record(),{id,revision:2,status:'counted'}).id,id);
  for(const change of [{id:location},{revision:3},{status:'approved'},{history_sha256:''}])assert.throws(()=>inventoryCountRecord({...record(),...change},{id,revision:2,status:'counted'}));
});
test('pending fresh helper checks approval rights but accepts committed newer revision for original receipt',async()=>{
  const operation={key:'inventory-count-approve-'+id,path:'/business/inventory/counts/'+id+'/approve'},gets=[];
  let rights=caps();
  const api={pendingCommandValues:()=>({revision:2,confirmed:true,zero_stock_unit_costs:{}}),get:async path=>{gets.push(path);return path.endsWith('capabilities')?rights:{...record(),revision:3,status:'approved'};}};
  await inventoryCountPendingAuthorize(api,operation);assert.equal(gets.length,2);
  rights={...caps(),permissions:['inventory.read','inventory.write','finance.read','finance.write']};
  await assert.rejects(()=>inventoryCountPendingAuthorize(api,operation),error=>error.status===403);
});
test('open pending checks original location identity',async()=>{
  const operation={key:'inventory-count-open-'+location,path:'/business/inventory/counts'};
  await assert.rejects(()=>inventoryCountPendingAuthorize({pendingCommandValues:()=>({location_id:location}),get:async path=>path.endsWith('capabilities')?caps():{location:{id}}},operation),/Lagerort/);
});
test('lost approval acknowledgement retries exact original bytes after fresh authorization',async()=>{
  let lost=true,allowed=true;const sent=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.includes('capabilities')?{...caps(),permissions:allowed?caps().permissions:['inventory.read','inventory.write']}:{...record(),revision:3,status:'approved'}),{status:200});
    sent.push(options.body);if(lost){lost=false;throw Error('lost acknowledgement');}
    return new Response(JSON.stringify({...record(),revision:3,status:'approved'}),{status:200});
  }});
  api.setToken('synthetic-count-session');
  const key='inventory-count-approve-'+id,path='/business/inventory/counts/'+id+'/approve',body={revision:2,confirmed:true,zero_stock_unit_costs:{}};
  await assert.rejects(()=>api.mutate(key,path,body));
  allowed=false;await assert.rejects(()=>api.retry(key));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  allowed=true;await api.retry(key);assert.deepEqual(sent,[sent[0],sent[0]]);assert.equal(api.pendingCount,0);
});
