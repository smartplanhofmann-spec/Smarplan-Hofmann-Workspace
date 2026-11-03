import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,componentPendingKey,componentPendingOperation,componentPendingAuthorize,capacityAccess,capacityState,capacityPortion,capacityPreviewData,capacityPreview,capacityConfirmData} from '../office.js';

const id=x=>x.repeat(32);
const hash=x=>x.repeat(64);
const money=(net,tax,gross)=>({net,tax,gross}),zero=()=>money('0.00','0.00','0.00');
const caps=()=>({permissions:['accounting.read','accounting.prepare','finance.read','finance.write'],features:['accounting_prejournal','accounting_payment_allocation','accounting_document_components','accounting_refund_origins','accounting_document_component_reuse'],capabilities:['business_accounting','business_accounting_allocations','business_accounting_components','business_accounting_refunds','business_accounting_capacity'],readonly:false});
const source=()=>({event_id:id('a'),source_hash:hash('a'),revision:0,state_hash:hash('b'),source_kind:'customer_receipt',amount:'13.22',currency:'EUR',cash_date:'2026-11-03',documented_amount:'0.00',undocumented_amount:'13.22',unallocated_amount:'0.00',eligible:true,blocked_reason:null,writes_allowed:true,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});
const group=()=>({group_id:hash('c'),rate:'19',category:'S',reason:'',archive:money('100.00','19.00','119.00'),current_capacity:{segment_id:null,...zero(),not_before_date:null},pending_returns:{...money('33.33','6.34','39.67'),not_before_date:'2026-11-02'},offered_capacity:{segment_id:hash('d'),...money('33.33','6.34','39.67'),not_before_date:'2026-11-02'},transition:'takeover',group_state_hash:hash('e')});
const portion=()=>({portion_id:hash('f'),kind:'original_allocation',event_id:id('a'),document_id:id('b'),customer_id:id('c'),project_id:id('d'),number:'SYN-CAPACITY-INVOICE',party_name:'Synthetic customer',amount:'13.22',currency:'EUR',payload_sha256:hash('a'),pdf_sha256:hash('b'),ownership_id:null,writer:'c2',action:'takeover_and_document',refund_status:'clear',pending_blocked_reason:null,portion_state_hash:hash('e'),eligible:true,blocked_reason:null,groups:[group()]});
const body=()=>capacityPreviewData(source(),portion(),[{group_id:hash('c'),amount:'13,22'}],'Synthetic exact frozen return');
const preview=()=>({event_id:id('a'),source_hash:hash('a'),expected_revision:0,state_hash:hash('b'),action:'takeover_and_document',portion:portion(),amount:'13.22',net:'11.11',tax:'2.11',lines:[{group_id:hash('c'),segment_id:hash('d'),amount:'13.22',net:'11.11',tax:'2.11',gross_before:'0.00',gross_after:'13.22',net_before:'0.00',net_after:'11.11',tax_before:'0.00',tax_after:'2.11',remaining_gross:'26.45',remaining_net:'22.22',remaining_tax:'4.23'}],capacity_changes:[{group_id:hash('c'),previous_segment_id:null,segment_id:hash('d'),carry:zero(),returned:money('33.33','6.34','39.67'),basis:money('33.33','6.34','39.67'),not_before_date:'2026-11-02'}],reason:'Synthetic exact frozen return',preview_hash:hash('f'),scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});

test('component confirmation keeps one logical event key across old and current writer paths',async()=>{
  const calls=[],eventId=id('a'),legacy=`/business/accounting/components/events/${eventId}/confirm`,current=`/business/accounting/components/v2/events/${eventId}/confirm`,key=componentPendingKey(eventId);
  let status=0;
  const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(!status)throw new Error('Lost response');return new Response(JSON.stringify(status===409?{error:'Writer changed; prepare anew',request_resolution:'not_accepted'}:{event_id:eventId}),{status});}});
  api.setToken('synthetic-memory-only');
  const body={portion_id:'b'.repeat(64),groups:[{group_id:'c'.repeat(64),amount:'39.67'}],confirmation:true};
  await assert.rejects(api.mutate(key,legacy,body));
  assert.equal(componentPendingOperation(api.pendingOperations(),eventId).path,legacy);
  assert.equal(componentPendingOperation(api.pendingOperations(),id('d')),null);
  await assert.rejects(api.mutate(key,current,body),/unveränderte Eingabe/);
  assert.equal(calls.length,1,'a writer change cannot send a new command while the old outcome is unknown');
  status=423;await assert.rejects(api.retry(key),error=>error.status===423);assert.equal(api.pendingCount,1);
  status=409;await assert.rejects(api.retry(key),error=>error.status===409);assert.equal(api.pendingCount,0);
  assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);
  status=201;await api.mutate(key,current,body);assert.notEqual(calls[3].body.request_id,calls[0].body.request_id);assert.equal(api.pendingCount,0);
});

test('accepted old component confirmation replays its stored path, body and request id after a writer change',async()=>{
  const calls=[],eventId=id('a'),path=`/business/accounting/components/events/${eventId}/confirm`,body={reason:'Original checked cents'};let accepted=false;
  const receipt={event_id:eventId,net:'33.33',tax:'6.34',amount:'39.67'};
  const api=new OfficeApi({fetcher:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});if(!accepted){accepted=true;throw new Error('Accepted, acknowledgement lost');}return new Response(JSON.stringify(receipt),{status:201});}});
  api.setToken('synthetic-memory-only');await assert.rejects(api.mutate(componentPendingKey(eventId),path,body));
  assert.deepEqual(await api.retry(componentPendingKey(eventId)),receipt);assert.deepEqual(calls[0],calls[1]);assert.equal(api.pendingCount,0);
  accepted=false;await assert.rejects(api.mutate(componentPendingKey(eventId),path,body));assert.equal(api.pendingCount,1);api.clear();await assert.rejects(api.get('/business/accounting/events/'+eventId),error=>error.status===401);
  assert.equal(api.pendingCount,0,'logout clears memory-only commands');
});

test('capacity negotiation needs every dependency and separates readable history from new work',()=>{
  assert.deepEqual(capacityAccess(caps(),null,source()),{available:true,read:true,prepare:true});
  for(const name of caps().features)assert.equal(capacityAccess({...caps(),features:caps().features.filter(item=>item!==name)},null).read,false);
  for(const name of caps().capabilities)assert.equal(capacityAccess({...caps(),capabilities:caps().capabilities.filter(item=>item!==name)},null).read,false);
  for(const name of ['accounting.read','finance.read'])assert.equal(capacityAccess({...caps(),permissions:caps().permissions.filter(item=>item!==name)},null).read,false);
  for(const [cap,organization,value,online]of [[caps(),null,{...source(),eligible:false},true],[caps(),null,{...source(),writes_allowed:false},true],[caps(),null,source(),false],[{...caps(),readonly:true},null,source(),true],[caps(),{modules:{finance:{enabled:false}}},source(),true]])assert.deepEqual(capacityAccess(cap,organization,value,online),{available:true,read:true,prepare:false});
});

test('state keeps cumulative positive documented amounts and rejects invalid date or tax claims',()=>{
  assert.equal(capacityState(source()).amount,'13.22');
  for(const change of [{documented_amount:'0.01'},{tax_result_available:true},{tax_status:'configured'},{cash_date:'2026-02-30'}])assert.throws(()=>capacityState({...source(),...change}));
  assert.equal(capacityState({...source(),eligible:false,blocked_reason:'fully_documented'}).eligible,false);
});

test('archive, current rest, pending returns and offered cents retain separate meanings',()=>{
  const value=portion();assert.equal(capacityPortion(value,id('a')).groups[0].offered_capacity.tax,'6.34');
  for(const change of [{writer:'c1'},{ownership_id:id('b')},{eligible:false},{action:'document_legacy'}])assert.throws(()=>capacityPortion({...portion(),...change},id('a')));
  for(const change of [{archive:money('100.00','19.00','118.00')},{current_capacity:{...group().current_capacity,gross:'1.00'}},{offered_capacity:{...group().offered_capacity,tax:'6.33',net:'33.34'}},{transition:'none'},{offered_capacity:{...group().offered_capacity,segment_id:null}}])assert.throws(()=>capacityPortion({...portion(),groups:[{...group(),...change}]},id('a')));
  const pending={...group(),current_capacity:{segment_id:hash('d'),...money('22.22','4.23','26.45'),not_before_date:'2026-11-02'},offered_capacity:{segment_id:hash('d'),...money('22.22','4.23','26.45'),not_before_date:'2026-11-02'},transition:'none'};
  assert.equal(capacityPortion({...portion(),ownership_id:id('b'),action:'document_current',pending_blocked_reason:'refund_origin_unresolved',groups:[pending]},id('a')).groups[0].offered_capacity.gross,'26.45','unresolved new returns do not inflate confirmed current rest');
});

test('new capacity command requires explicit positive whole-portion groups and an eligible cash date',()=>{
  assert.deepEqual(body().groups,[{group_id:hash('c'),amount:'13.22'}]);assert.equal('request_id'in body(),false);
  for(const groups of [[],[{group_id:hash('c'),amount:'0'}],[{group_id:hash('c'),amount:'13.21'}],[{group_id:hash('c'),amount:'13.220'}],[{group_id:hash('c'),amount:'40'}],[{group_id:hash('c'),amount:'6.61'},{group_id:hash('c'),amount:'6.61'}],[{group_id:hash('a'),amount:'13.22'}]])assert.throws(()=>capacityPreviewData(source(),portion(),groups,'Reason'));
  assert.throws(()=>capacityPreviewData({...source(),cash_date:'2026-11-01'},portion(),body().groups,'Reason'));
  assert.throws(()=>capacityPreviewData(source(),portion(),body().groups,'Two\nlines'));
  assert.throws(()=>capacityPreviewData(source(),{...portion(),writer:'c1',action:'document_legacy'},body().groups,'Reason'));
});

test('preview binds the exact command, every capacity transition and original middle-lot cents',()=>{
  assert.equal(capacityPreview(preview(),body(),source()).tax,'2.11');
  for(const change of [{action:'document_current'},{event_id:id('f')},{reason:'Changed'},{tax:'2.12'},{capacity_changes:[]}])assert.throws(()=>capacityPreview({...preview(),...change},body(),source()));
  for(const change of [{segment_id:hash('e')},{tax:'2.12',net:'11.10'},{gross_before:'0.01'},{remaining_tax:'4.22'}])assert.throws(()=>capacityPreview({...preview(),lines:[{...preview().lines[0],...change}]},body(),source()));
  for(const change of [{carry:money('0.01','0.00','0.01')},{returned:money('33.34','6.33','39.67')},{previous_segment_id:hash('d')},{not_before_date:'2026-11-01'}])assert.throws(()=>capacityPreview({...preview(),capacity_changes:[{...preview().capacity_changes[0],...change}]},body(),source()));
  assert.throws(()=>capacityConfirmData(body(),preview(),source(),false));assert.deepEqual(capacityConfirmData(body(),preview(),source(),true).groups,body().groups);
});

test('whole middle lot reuses 33.33/6.34 exactly and a later remainder never resets its ratio',()=>{
  const fullSource={...source(),amount:'39.67',undocumented_amount:'39.67'},fullPortion={...portion(),amount:'39.67'},fullBody=capacityPreviewData(fullSource,fullPortion,[{group_id:hash('c'),amount:'39.67'}],'Full original middle lot');
  const full={...preview(),portion:fullPortion,amount:'39.67',net:'33.33',tax:'6.34',reason:fullBody.reason,lines:[{...preview().lines[0],amount:'39.67',net:'33.33',tax:'6.34',gross_after:'39.67',net_after:'33.33',tax_after:'6.34',remaining_gross:'0.00',remaining_net:'0.00',remaining_tax:'0.00'}]};
  assert.equal(capacityPreview(full,fullBody,fullSource).tax,'6.34');
  const remainder={...group(),current_capacity:{segment_id:hash('d'),...money('22.22','4.23','26.45'),not_before_date:'2026-11-02'},pending_returns:{...zero(),not_before_date:null},offered_capacity:{segment_id:hash('d'),...money('22.22','4.23','26.45'),not_before_date:'2026-11-02'},transition:'none'};
  const nextSource={...source(),amount:'26.45',undocumented_amount:'26.45'},nextPortion={...portion(),ownership_id:id('b'),action:'document_current',amount:'26.45',groups:[remainder]},nextBody=capacityPreviewData(nextSource,nextPortion,[{group_id:hash('c'),amount:'26.45'}],'Continue same exact section');
  const next={...preview(),action:'document_current',portion:nextPortion,amount:'26.45',net:'22.22',tax:'4.23',reason:nextBody.reason,capacity_changes:[],lines:[{...full.lines[0],amount:'26.45',net:'22.22',tax:'4.23',gross_before:'13.22',net_before:'11.11',tax_before:'2.11'}]};
  assert.equal(capacityPreview(next,nextBody,nextSource).tax,'4.23');
  assert.throws(()=>capacityPreview({...next,lines:[{...next.lines[0],gross_before:'0.00',net_before:'0.00',tax_before:'0.00'}]},nextBody,nextSource));
});

test('all invoice groups including zero capacity are visible in an atomic takeover preview',()=>{
  const extra={...group(),group_id:hash('f'),current_capacity:{segment_id:null,...zero(),not_before_date:null},pending_returns:{...zero(),not_before_date:null},offered_capacity:{segment_id:hash('e'),...zero(),not_before_date:null}};
  const value={...preview(),portion:{...portion(),groups:[group(),extra]},capacity_changes:[...preview().capacity_changes,{group_id:hash('f'),previous_segment_id:null,segment_id:hash('e'),carry:zero(),returned:zero(),basis:zero(),not_before_date:null}]};
  assert.equal(capacityPreview(value,body(),source()).capacity_changes.length,2);
  assert.throws(()=>capacityPreview({...value,capacity_changes:preview().capacity_changes},body(),source()));
});

test('pending preflight uses the stored writer and permits historical replay despite current ineligibility',async()=>{
  const paths=[],api={get:async path=>{paths.push(path);return {...source(),eligible:false,blocked_reason:'fully_documented'};}};
  for(const version of ['', 'v2/']) {
    const path=`/business/accounting/components/${version}events/${id('a')}/confirm`;
    assert.equal((await componentPendingAuthorize(api,{path})).eligible,false);assert.equal(paths.at(-1),path.slice(0,-8));
  }
  await assert.rejects(componentPendingAuthorize({get:async()=>({...source(),writes_allowed:false})},{path:`/business/accounting/components/v2/events/${id('a')}/confirm`}),error=>error.status===423);
  await assert.rejects(componentPendingAuthorize({get:async()=>{throw Object.assign(new Error('Full historical source denied'),{status:403});}},{path:`/business/accounting/components/v2/events/${id('a')}/confirm`}),error=>error.status===403);
  await assert.rejects(componentPendingAuthorize(api,{path:'/business/accounting/refunds/events/'+id('a')+'/confirm'}));
});

test('rights lost between preflight and retry retain the exact component command on both paths',async()=>{
  for(const version of ['', 'v2/']) {
    const calls=[],path=`/business/accounting/components/${version}events/${id('a')}/confirm`,key=componentPendingKey(id('a'));let status=0;
    const api=new OfficeApi({fetcher:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});if(!status)throw new Error('Unknown result');return new Response(JSON.stringify(status===201?{accepted:true}:{error:'Source access denied'}),{status});}});
    api.setToken('synthetic-memory-only');await assert.rejects(api.mutate(key,path,{reason:'Immutable original'}));
    for(const denied of [403,404,409,423,503]){status=denied;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);}
    await assert.rejects(api.mutate(key,path,{reason:'Changed'}),/unveränderte Eingabe/);
    status=201;assert.deepEqual(await api.retry(key),{accepted:true});for(const call of calls)assert.deepEqual(call,calls[0]);assert.equal(api.pendingCount,0);
  }
});

test('accepted lost acknowledgement survives a positive preflight then unmarked restore conflict and replays exactly',async()=>{
  for(const version of ['', 'v2/']) {
    const eventId=id('a'),path=`/business/accounting/components/${version}events/${eventId}/confirm`,key=componentPendingKey(eventId),calls=[],receipt={id:id('f'),event_id:eventId,net:'33.33',tax:'6.34',amount:'39.67'};let mode='lost';
    const api=new OfficeApi({fetcher:async(url,options)=>{
      if(options.method==='GET')return new Response(JSON.stringify({...source(),eligible:false,blocked_reason:'fully_documented'}));
      calls.push({url,body:JSON.parse(options.body)});
      if(mode==='lost')throw new Error('Accepted but acknowledgement lost');
      if(mode==='restoring')return new Response(JSON.stringify({error:'Restore gate active before receipt lookup'}),{status:409});
      if(mode==='unknown-marker')return new Response(JSON.stringify({error:'Conflict',request_resolution:'something_else'}),{status:409});
      return new Response(JSON.stringify(receipt),{status:201});
    }});
    api.setToken('synthetic-memory-only');await assert.rejects(api.mutate(key,path,{reason:'Exact original accepted command'}));
    for(const blocked of ['restoring','unknown-marker']){await componentPendingAuthorize(api,api.pendingOperations()[0]);mode=blocked;await assert.rejects(api.retry(key),error=>error.status===409&&error.requestResolution===null);assert.equal(api.pendingCount,1);}
    await assert.rejects(api.mutate(key,path,{reason:'Changed command'}),/unveränderte Eingabe/);
    mode='ready';await componentPendingAuthorize(api,api.pendingOperations()[0]);assert.deepEqual(await api.retry(key),receipt);for(const call of calls)assert.deepEqual(call,calls[0]);assert.equal(api.pendingCount,0);
  }
});
