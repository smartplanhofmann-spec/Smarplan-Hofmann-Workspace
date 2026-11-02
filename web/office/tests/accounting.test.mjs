import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,accountingAccess,accountingAmount,accountingAccountData,accountingPaymentData,accountingPayoutData,accountingStatus,accountingPage,organizationCommandArea} from '../office.js';
const id='a'.repeat(32),hash='b'.repeat(64);
const account=()=>({id,code:'MAIN',name:'Synthetic original account',currency:'EUR',active:true,revision:3});
const values=()=>({cash_date:'2026-11-02',evidence_reference:' SYN-CASH-1 ',confirmation:true,amount:'59,50',reference:' Synthetic actual payout '});
const payment=()=>({payment_id:'c'.repeat(32),source_hash:hash,currency:'EUR',kind:'receipt',direction:'in',amount:'119.00',booking_date:'2026-11-01',allocations:[],unallocated:'119.00',linked_event_id:null});
const receipt=()=>({receipt_id:'d'.repeat(32),source_hash:hash,original_sha256:'e'.repeat(64),review_sha256:'f'.repeat(64),review_revision:2,cash_revision:1,currency:'EUR',gross:'119.00',remaining_amount:'59.50',payable:true,blocked_reason:null});
const caps=(permissions=['accounting.read','finance.read','accounting.prepare','accounting.admin'])=>({permissions,features:['accounting_prejournal'],capabilities:['business_accounting'],readonly:false});

test('prejournal access requires explicit global accounting and finance rights; project grants cannot substitute',()=>{
  assert.deepEqual(accountingAccess(caps(),null,{writes_allowed:true}),{available:true,read:true,prepare:true,admin:true});
  for(const permissions of [[],['finance.read'],['accounting.read'],['accounting.prepare','finance.read']])assert.equal(accountingAccess(caps(permissions),null,{writes_allowed:true}).read,false);
  const global=caps(['finance.read']);global.project_permissions=['accounting.read','accounting.admin','accounting.prepare'];
  assert.equal(accountingAccess(global,null,{writes_allowed:true}).read,false);
  assert.equal(accountingAccess({...caps(),features:[]},null,{writes_allowed:true}).available,false);
  assert.equal(accountingAccess({...caps(),capabilities:[]},null,{writes_allowed:true}).read,false);
});
test('accounting read survives module pause and restore gates but all new commands wait',()=>{
  for(const [value,organization,status] of [[caps(),null,null],[caps(),null,{writes_allowed:false}],[{...caps(),readonly:true},null,{writes_allowed:true}],[caps(),{modules:{finance:{enabled:false}}},{writes_allowed:true}]])assert.deepEqual(accountingAccess(value,organization,status),{available:true,read:true,prepare:false,admin:false});
  const readOnly=accountingAccess(caps(['accounting.read','finance.read']),null,{writes_allowed:true});assert.equal(readOnly.prepare,false);assert.equal(readOnly.admin,false);
  for(const path of ['/accounting/accounts','/accounting/accounts/'+id,'/accounting/events/import-payment','/accounting/events/payout'])assert.equal(organizationCommandArea(path),'finance');
});
test('EUR inputs canonicalize exact cents without rounding or numeric coercion',()=>{
  for(const [input,expected]of [['1','1.00'],['0001,2','1.20'],[' 0.01 ','0.01'],['999999999.99','999999999.99']])assert.equal(accountingAmount(input),expected);
  assert.equal(accountingAmount('0',{zero:true}),'0.00');
  for(const value of ['0','-1','1.001','1.230','1e2','1.000,50','1000000000.00','Infinity','',null,undefined])assert.throws(()=>accountingAmount(value));
});
test('account create and revision update use only the explicit account fields',()=>{
  assert.deepEqual(accountingAccountData(null,{code:' SYN-01 ',name:' Synthetic cash ',kind:'cash',confirmation:true,iban:'ignored'}),{code:'SYN-01',name:'Synthetic cash',kind:'cash',confirmation:true});
  assert.deepEqual(accountingAccountData(account(),{name:'Renamed',active:false,confirmation:true,kind:'cash',code:'CHANGED'}),{revision:3,name:'Renamed',active:false,confirmation:true});
  for(const change of [{code:'space bad'},{kind:'crypto'},{name:' '},{confirmation:'true'}])assert.throws(()=>accountingAccountData(null,{code:'MAIN',name:'Main',kind:'bank',confirmation:true,...change}));
});
test('payment import binds source hash and account version without editable amount or old payment fields',()=>{
  const body=accountingPaymentData(payment(),account(),values());
  assert.deepEqual(body,{payment_id:'c'.repeat(32),source_hash:hash,account_id:id,account_revision:3,cash_date:'2026-11-02',evidence_reference:'SYN-CASH-1',confirmation:true});
  assert.deepEqual(accountingPaymentData({...payment(),kind:'refund',direction:'out'},account(),values()),body);
  for(const source of [{...payment(),linked_event_id:id},{...payment(),kind:'refund'},{...payment(),source_hash:'not-a-hash'},{...payment(),currency:'USD'}])assert.throws(()=>accountingPaymentData(source,account(),values()));
});
test('manual partial payout binds exact original, review, cash and account revisions',()=>{
  const body=accountingPayoutData(receipt(),account(),values());
  assert.deepEqual(body,{receipt_id:'d'.repeat(32),source_hash:hash,review_revision:2,review_sha256:'f'.repeat(64),original_sha256:'e'.repeat(64),account_id:id,account_revision:3,cash_date:'2026-11-02',evidence_reference:'SYN-CASH-1',confirmation:true,expected_cash_revision:1,amount:'59.50',reference:'Synthetic actual payout'});
  for(const change of [{remaining_amount:'59.49'},{payable:false},{blocked_reason:'review_changed'},{blocked_reason:'duplicate_original'},{cash_revision:-1},{review_revision:'2'},{original_sha256:'x'}])assert.throws(()=>accountingPayoutData({...receipt(),...change},account(),values()));
  for(const change of [{amount:'59.501'},{cash_date:'2026-02-30'},{cash_date:'0000-01-01'},{evidence_reference:''},{reference:'Two\nlines'},{evidence_reference:'Control\tcharacter'},{confirmation:false}])assert.throws(()=>accountingPayoutData(receipt(),account(),{...values(),...change}));
  assert.throws(()=>accountingPayoutData(receipt(),{...account(),active:false},values()));
  assert.equal(accountingPayoutData(receipt(),account(),{...values(),cash_date:'2400-02-29'}).cash_date,'2400-02-29');
});
test('status and bounded page errors cannot masquerade as empty journal data',()=>{
  const status={profile_status:'unconfigured',tax_status:'unconfigured',tax_result_available:false,scope:'authorized_sources',writes_allowed:false};assert.equal(accountingStatus(status),status);
  for(const change of [{scope:'company'},{tax_result_available:true},{writes_allowed:'false'},{profile_status:'configured'}])assert.throws(()=>accountingStatus({...status,...change}));
  const page={items:[],total:0,next_offset:null,scope:'authorized_sources',tax_result_available:false};assert.equal(accountingPage(page,0,true),page);
  for(const change of [{items:null},{scope:'all'},{total:-1},{next_offset:0},{next_offset:100001},{tax_result_available:true}])assert.throws(()=>accountingPage({...page,...change},0,true));
  assert.equal(accountingPage({...page,items:[{}],total:30,next_offset:25},0).next_offset,25);
});
test('lost cash reply retries the original complete body through temporary 423 after later account or review changes',async()=>{
  const calls=[];const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(calls.length===1)throw new Error('Synthetic lost ACK');if(calls.length===2)return new Response(JSON.stringify({error:'Finance inactive'}),{status:423});return new Response(JSON.stringify({id:'f'.repeat(32),account:account(),source:{snapshot:{review_revision:2}},amount:'59.50'}),{status:201});}});api.setToken('synthetic-memory-token-only');
  const body=accountingPayoutData(receipt(),account(),values());await assert.rejects(api.mutate('payout','/business/accounting/events/payout',body),error=>error.status===0);await assert.rejects(api.retry('payout'),error=>error.status===423);assert.equal(api.pendingCount,1);
  await assert.rejects(api.mutate('payout','/business/accounting/events/payout',{...body,review_revision:3,account_revision:4}),/unveränderte Eingabe/);
  const replay=await api.retry('payout');assert.equal(replay.account.revision,3);assert.equal(replay.source.snapshot.review_revision,2);assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);assert.equal(api.pendingCount,0);
});
test('definite stale source rejection requires a newly reviewed request and new request ID',async()=>{
  const calls=[];const api=new OfficeApi({fetcher:async(_,options)=>{calls.push(JSON.parse(options.body));return new Response(JSON.stringify(calls.length===1?{error:'Review changed'}:{id}),{status:calls.length===1?409:201});}});api.setToken('synthetic-memory-token-only');
  await assert.rejects(api.mutate('payout','/business/accounting/events/payout',accountingPayoutData(receipt(),account(),values())),error=>error.status===409);
  await api.mutate('payout','/business/accounting/events/payout',accountingPayoutData({...receipt(),cash_revision:2,review_revision:3},account(),values()));assert.notEqual(calls[0].request_id,calls[1].request_id);assert.equal(calls[0].review_revision,2);assert.equal(calls[1].review_revision,3);
});
