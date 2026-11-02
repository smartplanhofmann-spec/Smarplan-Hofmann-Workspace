import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,organizationCommandArea,purchaseActions,purchaseConfirmationData,purchaseReceiptData} from '../office.js';

const order=()=>({id:'a'.repeat(32),project_id:'b'.repeat(32),source_revision:3,receipt_revision:1,
  status:'partially_received',confirmation:{order_reference:'SYN-ORDER',ordered_on:'2026-11-01'},items:[
    {line_index:0,article_id:'c'.repeat(32),remaining_quantity:'0.0000'},
    {line_index:1,article_id:'d'.repeat(32),remaining_quantity:'2.1250'},
    {line_index:2,article_id:'d'.repeat(32),remaining_quantity:'7.0000'},
  ]});
const values=()=>({receipt_reference:' SYN-DELIVERY-2 ',received_on:'2026-11-02',location_id:'e'.repeat(32),
  quantity_1:'1,1250',cost_1:'3,5000'});

test('partial receipt keeps stable position indices, revisions and explicit decimal costs',()=>{
  const data=purchaseReceiptData(order(),values());
  assert.deepEqual(data,{source_revision:3,expected_receipt_revision:1,receipt_reference:'SYN-DELIVERY-2',
    received_on:'2026-11-02',location_id:'e'.repeat(32),lines:[{line_index:1,quantity:'1.1250',unit_cost_net:'3.5000'}]});
  const reordered={...order(),items:[...order().items].reverse()};
  assert.deepEqual(purchaseReceiptData(reordered,values()),data);
});

test('repeated articles remain separate order positions and zero cost requires explicit input',()=>{
  const data=purchaseReceiptData(order(),{...values(),quantity_1:'2.1250',cost_1:'0',quantity_2:'7',cost_2:'1.25'});
  assert.deepEqual(data.lines,[{line_index:1,quantity:'2.1250',unit_cost_net:'0'},
    {line_index:2,quantity:'7',unit_cost_net:'1.25'}]);
  for(const cost_1 of ['',undefined,null])assert.throws(()=>purchaseReceiptData(order(),{...values(),cost_1}),/Einstandspreis/);
});

test('remaining quantity comparison is decimal exact beyond Number safe integer precision',()=>{
  const large={...order(),items:[{line_index:0,remaining_quantity:'9007199254740992.0001'}]};
  const input={receipt_reference:'SYN-LARGE',received_on:'2026-11-02',location_id:'e'.repeat(32),cost_0:'0.0001'};
  assert.equal(purchaseReceiptData(large,{...input,quantity_0:'9007199254740992.0001'}).lines[0].quantity,'9007199254740992.0001');
  assert.throws(()=>purchaseReceiptData(large,{...input,quantity_0:'9007199254740992.0002'}),/offenen Menge/);
});

test('empty, overdelivered, negative and invalid receipt values cannot create a stock command',()=>{
  for(const change of [{quantity_1:'0'},{quantity_1:'2.1251'},{quantity_1:'-1'},{quantity_1:'NaN'},
    {quantity_1:'1e5'},{cost_1:'-0.0001'},{quantity_0:'1',cost_0:'1'},
    {receipt_reference:' '},{location_id:''},{received_on:'2026-02-30'},{received_on:'2026-10-31'},
    {quantity_1:'',cost_1:'2'}]) {
    assert.throws(()=>purchaseReceiptData(order(),{...values(),...change}),undefined,JSON.stringify(change));
  }
});

test('invalid or unconfirmed order metadata is never silently repaired by the client',()=>{
  for(const changed of [{source_revision:0},{receipt_revision:-1},{source_revision:'3'},
    {items:[]},{items:[order().items[1],order().items[1]]},{items:[{line_index:'1',remaining_quantity:'2'}]},
    {status:'proposal'},{status:'received'},{confirmation:null}]) {
    assert.throws(()=>purchaseReceiptData({...order(),...changed},values()));
  }
});

test('confirmation records an explicit external order and never auto-approves a proposal',()=>{
  const approved={...order(),status:'approved',confirmation:null,receipt_revision:0};
  const input={order_reference:' SYN-ORDER ',ordered_on:'2026-11-01',confirmation:true};
  assert.deepEqual(purchaseConfirmationData(approved,input),{source_revision:3,expected_receipt_revision:0,
    order_reference:'SYN-ORDER',ordered_on:'2026-11-01',confirmation:true});
  for(const confirmation of [false,undefined,'true',1])assert.throws(()=>purchaseConfirmationData(approved,{...input,confirmation}));
  assert.throws(()=>purchaseConfirmationData({...approved,status:'proposal'},input),/freigeben/);
  assert.throws(()=>purchaseConfirmationData(order(),input));
  assert.throws(()=>purchaseConfirmationData(approved,{...input,ordered_on:'2026-02-30'}));
  assert.throws(()=>purchaseConfirmationData(approved,{...input,order_reference:' '}));
});

test('purchase writes belong to the material module regardless of order action',()=>{
  for(const suffix of ['', '/confirm','/receipts'])assert.equal(organizationCommandArea('/purchasing/orders/'+order().id+suffix),'material');
});

test('order project capabilities independently control approval, receipts and price visibility',()=>{
  const approved={...order(),status:'approved'},caps=permissions=>({permissions,readonly:false});
  const approver=caps(['inventory.read','inventory.write','finance.approve']);
  assert.equal(purchaseActions(approved,approver,null).confirm,true,'project approver needs no finance.write');
  assert.equal(purchaseActions(order(),approver,null).receive,false);
  assert.equal(purchaseActions(order(),approver,null).costs,false);
  const receiver=caps(['inventory.read','inventory.write','finance.write']);
  assert.equal(purchaseActions(order(),receiver,null).receive,true);
  assert.equal(purchaseActions(approved,receiver,null).confirm,false);
  assert.deepEqual(purchaseActions(order(),caps(['inventory.read']),null),
    {edit:false,approve:false,confirm:false,receive:false,costs:false},'a project deny hides actions and costs despite global grants');
  assert.equal(purchaseActions(order(),caps(['finance.write']),null).receive,false,'receipt also requires inventory.write');
});

test('paused and readonly purchasing retains financial history but hides every mutation',()=>{
  const caps={permissions:['inventory.write','finance.read','finance.write','finance.approve'],readonly:false};
  for(const status of ['proposal','approved','ordered','partially_received','received']){
    for(const [access,organization] of [[{...caps,readonly:true},null],[caps,{modules:{material:{enabled:false}}}]])
      assert.deepEqual(purchaseActions({status},access,organization),{edit:false,approve:false,confirm:false,receive:false,costs:true});
  }
  assert.equal(purchaseActions({status:'received'},caps,null).receive,false);
  assert.equal(purchaseActions({status:'approved'},caps,null).edit,false);
});

test('lost receipt acknowledgement and temporary module lock retry the exact original body',async()=>{
  const calls=[];
  const api=new OfficeApi({fetcher:async(path,options)=>{
    calls.push({path,body:JSON.parse(options.body)});
    if(calls.length===1)throw new Error('Synthetic lost acknowledgement');
    if(calls.length===2)return new Response(JSON.stringify({error:'Material deaktiviert'}),{status:423});
    return new Response(JSON.stringify({id:'f'.repeat(32),receipt_revision:2}),{status:201});
  }});
  api.setToken('synthetic-memory-token-only');
  const body=purchaseReceiptData(order(),values()),path='/business/purchasing/orders/'+order().id+'/receipts';
  await assert.rejects(api.mutate('receipt',path,body),error=>error.status===0);
  await assert.rejects(api.retry('receipt'),error=>error.status===423);
  assert.equal(api.pendingCount,1);
  await assert.rejects(api.mutate('receipt',path,{...body,receipt_reference:'Changed'}),/unveränderte Eingabe/);
  assert.equal((await api.retry('receipt')).receipt_revision,2);
  assert.equal(api.pendingCount,0);
  assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);
});

test('a definite stale delivery revision releases the failed command for a freshly reviewed receipt',async()=>{
  const calls=[];
  const api=new OfficeApi({fetcher:async(_,options)=>{
    calls.push(JSON.parse(options.body));
    return new Response(JSON.stringify(calls.length===1?{error:'Lieferstand inzwischen geändert'}:{id:'new-receipt'}),{status:calls.length===1?409:201});
  }});
  api.setToken('synthetic-memory-token-only');
  const path='/business/purchasing/orders/'+order().id+'/receipts';
  await assert.rejects(api.mutate('receipt',path,purchaseReceiptData(order(),values())),error=>error.status===409);
  assert.equal(api.pendingCount,0);
  const refreshed={...order(),receipt_revision:2};
  await api.mutate('receipt',path,purchaseReceiptData(refreshed,values()));
  assert.notEqual(calls[0].request_id,calls[1].request_id);
  assert.equal(calls[1].expected_receipt_revision,2);
});
