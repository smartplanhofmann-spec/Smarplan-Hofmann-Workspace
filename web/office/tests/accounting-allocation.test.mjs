import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,accountingAllocationAccess,accountingAllocationState,accountingAllocationPreviewData,accountingAllocationPreview,accountingAllocationAssignData} from '../office.js';
const id=letter=>letter.repeat(32),hash=letter=>letter.repeat(64);
const caps=(permissions=['accounting.read','accounting.prepare','finance.read','finance.write'])=>({permissions,features:['accounting_prejournal','accounting_payment_allocation'],capabilities:['business_accounting','business_accounting_allocations'],readonly:false});
const source=()=>({payment_id:id('a'),event_id:id('b'),source_hash:hash('c'),state_hash:hash('d'),revision:0,amount:'119.00',allocated_amount:'0.00',unallocated_amount:'119.00',currency:'EUR',customer_id:null,allocations:[],eligible:true,blocked_reason:null,writes_allowed:true,scope:'authorized_sources',tax_result_available:false});
const document=()=>({document_id:id('e'),customer_id:id('f'),project_id:id('a'),number:'SYN-INVOICE-1',buyer_name:'Synthetic buyer',gross:'119.00',paid:'0.00',credited:'0.00',open:'119.00',payload_sha256:hash('a'),pdf_sha256:hash('b'),document_state_hash:hash('e')});
const values=()=>({amount:'59,50',reason:' Synthetic confirmed customer relation ',customer_confirmation:true});
const body=()=>accountingAllocationPreviewData(source(),document(),values());
const preview=()=>({payment_id:source().payment_id,event_id:source().event_id,customer_id:document().customer_id,source_hash:source().source_hash,expected_revision:0,state_hash:source().state_hash,document:document(),amount:'59.50',reason:'Synthetic confirmed customer relation',unallocated_before:'119.00',unallocated_after:'59.50',open_before:'119.00',open_after:'59.50',preview_hash:hash('f'),scope:'authorized_sources',tax_result_available:false});

test('allocation read and prepare negotiate features and explicit global finance write independently',()=>{
  assert.deepEqual(accountingAllocationAccess(caps(),null,source()),{available:true,read:true,prepare:true});
  for(const permission of ['finance.write','accounting.prepare']){const access=accountingAllocationAccess(caps(caps().permissions.filter(item=>item!==permission)),null,source());assert.equal(access.read,true);assert.equal(access.prepare,false);}
  for(const permission of ['finance.read','accounting.read'])assert.equal(accountingAllocationAccess(caps(caps().permissions.filter(item=>item!==permission)),null,source()).read,false);
  const scoped=caps(['finance.read','accounting.read']);scoped.project_permissions=['finance.write','accounting.prepare'];assert.equal(accountingAllocationAccess(scoped,null,source()).prepare,false);
  assert.equal(accountingAllocationAccess({...caps(),features:['accounting_prejournal']},null,source()).available,false);
  assert.equal(accountingAllocationAccess({...caps(),capabilities:['business_accounting']},null,source()).read,false);
});
test('offline, readonly, paused finance, source gates and unsupported states retain history without new commands',()=>{
  for(const [capabilities,organization,state,online]of [[caps(),null,source(),false],[{...caps(),readonly:true},null,source(),true],[caps(),{modules:{finance:{enabled:false}}},source(),true],[caps(),null,{...source(),writes_allowed:false},true],[caps(),null,{...source(),eligible:false},true]])assert.deepEqual(accountingAllocationAccess(capabilities,organization,state,online),{available:true,read:true,prepare:false});
  const overallocated={...source(),allocated_amount:'120.00',unallocated_amount:'-1.00',eligible:false,blocked_reason:'overallocated'};assert.equal(accountingAllocationState(overallocated),overallocated,'historical overallocations stay readable');
  assert.throws(()=>accountingAllocationPreviewData(overallocated,document(),values()));
});
test('preview binds customer, immutable E1a source, effective revision and exact target state without request id',()=>{
  assert.deepEqual(body(),{source_hash:hash('c'),expected_revision:0,state_hash:hash('d'),customer_id:id('f'),document_id:id('e'),document_state_hash:hash('e'),amount:'59.50',reason:'Synthetic confirmed customer relation'});
  assert.equal('request_id' in body(),false);assert.equal('confirmation' in body(),false);
  for(const change of [{customer_confirmation:false},{customer_confirmation:'true'},{amount:'119.01'},{amount:'1.001'},{amount:'-1'},{reason:''},{reason:'Two\nlines'}])assert.throws(()=>accountingAllocationPreviewData(source(),document(),{...values(),...change}));
  assert.throws(()=>accountingAllocationPreviewData({...source(),customer_id:id('a')},document(),values()),/Kundenbindung/);
  assert.throws(()=>accountingAllocationPreviewData(source(),{...document(),customer_id:null},values()));
  assert.throws(()=>accountingAllocationPreviewData(source(),{...document(),open:'59.49'},values()),/offenen Rechnungsbetrag/);
});
test('mismatched or inconsistent preview cannot become an assign confirmation',()=>{
  const result=preview();assert.equal(accountingAllocationPreview(result,body(),id('a'),id('b')),result);
  for(const change of [{payment_id:id('c')},{event_id:id('d')},{customer_id:id('a')},{source_hash:hash('f')},{state_hash:hash('a')},{expected_revision:1},{amount:'59.49'},{reason:'Different'},{open_after:'59.51'},{unallocated_after:'59.49'},{scope:'company'},{tax_result_available:true},{preview_hash:'bad'},{document:{...document(),document_state_hash:hash('c')}}])assert.throws(()=>accountingAllocationPreview({...result,...change},body(),id('a'),id('b')));
  assert.throws(()=>accountingAllocationAssignData(body(),result,false));assert.deepEqual(accountingAllocationAssignData(body(),result,true),{...body(),preview_hash:hash('f'),confirmation:true});
});
test('preview HTTP POST has no mutation receipt or pending queue even after a lost response',async()=>{
  const calls=[];const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(calls.length===1)throw new Error('Synthetic lost preview');return new Response(JSON.stringify(preview()),{status:200});}});api.setToken('synthetic-memory-bearer-only');
  const path='/business/accounting/allocations/payments/'+id('a')+'/preview';await assert.rejects(api.post(path,body()));assert.equal(api.pendingCount,0);await api.post(path,body());assert.deepEqual(calls[0],calls[1]);assert.equal('request_id' in calls[0].body,false);
});
test('lost assign ACK and temporary finance pause replay exact preview and request despite later target balances',async()=>{
  const calls=[];const original={id:id('f'),revision:1,document:document(),amount:'59.50',open_after:'59.50'};
  const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(calls.length===1)throw new Error('Synthetic saved ACK lost');if(calls.length===2)return new Response(JSON.stringify({error:'Finance paused'}),{status:423});return new Response(JSON.stringify(original),{status:201});}});api.setToken('synthetic-memory-bearer-only');
  const path='/business/accounting/allocations/payments/'+id('a')+'/assign',data=accountingAllocationAssignData(body(),preview(),true);
  await assert.rejects(api.mutate('assign',path,data));await assert.rejects(api.retry('assign'),error=>error.status===423);
  await assert.rejects(api.mutate('assign',path,{...data,document_state_hash:hash('a'),preview_hash:hash('b')}),/unveränderte Eingabe/);
  assert.deepEqual(await api.retry('assign'),original);assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);assert.equal(api.pendingCount,0);
});
test('changed open balance rejects old preview and a freshly checked preview gets a new request id',async()=>{
  const calls=[];const api=new OfficeApi({fetcher:async(_,options)=>{calls.push(JSON.parse(options.body));return new Response(JSON.stringify(calls.length===1?{error:'Target changed after preview'}:{id:id('f')}),{status:calls.length===1?409:201});}});api.setToken('synthetic-memory-bearer-only');
  const path='/business/accounting/allocations/payments/'+id('a')+'/assign';await assert.rejects(api.mutate('assign',path,accountingAllocationAssignData(body(),preview(),true)),error=>error.status===409);assert.equal(api.pendingCount,0);
  const target={...document(),paid:'10.00',open:'109.00',document_state_hash:hash('b')},fresh=accountingAllocationPreviewData(source(),target,values()),checked={...preview(),document:target,open_before:'109.00',open_after:'49.50',preview_hash:hash('a')};
  await api.mutate('assign',path,accountingAllocationAssignData(fresh,checked,true));assert.notEqual(calls[0].request_id,calls[1].request_id);assert.equal(calls[1].document_state_hash,hash('b'));assert.equal(calls[1].preview_hash,hash('a'));
});
test('pending reopening exposes no frozen target details before fresh authorization',async()=>{
  const api=new OfficeApi({fetcher:async()=>{throw new Error('Synthetic request lost before acceptance');}});api.setToken('synthetic-memory-bearer-only');
  const path='/business/accounting/allocations/payments/'+id('a')+'/assign';await assert.rejects(api.mutate('assign',path,accountingAllocationAssignData(body(),preview(),true)));
  assert.deepEqual(api.pendingOperations(),[{key:'assign',path}]);
  const text=JSON.stringify(api.pendingOperations());assert.equal(text.includes(document().number),false);assert.equal(text.includes(document().customer_id),false);assert.equal(text.includes(body().amount),false);assert.equal(text.includes(body().reason),false);
});
