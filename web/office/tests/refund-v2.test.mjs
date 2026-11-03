import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,refundAuthorize,refundV2Access,refundV2State,refundV2Portion,refundV2Origin,refundV2LotKey,refundV2OriginLabel,refundV2PreviewData,refundV2Preview,refundV2ConfirmData,refundV2Authorize,refundPendingKey,refundPendingOperation,refundPendingAuthorize} from '../office.js';
const id=x=>x.repeat(32),hash=x=>x.repeat(64);
const caps=()=>({permissions:['accounting.read','accounting.prepare','finance.read','finance.write'],features:['accounting_prejournal','accounting_payment_allocation','accounting_document_components','accounting_refund_origins','accounting_document_component_reuse','accounting_refund_origins_v2'],capabilities:['business_accounting','business_accounting_allocations','business_accounting_components','business_accounting_refunds','business_accounting_capacity','business_accounting_refunds_v2'],readonly:false});
const source=()=>({event_id:id('a'),source_hash:hash('a'),revision:0,state_hash:hash('b'),source_kind:'customer_refund',amount:'26.44',currency:'EUR',cash_date:'2026-11-03',evidence_reference:'Refund evidence',reference:'Synthetic mixed refund',origin_documented_amount:'0.00',origin_unresolved_amount:'26.44',unallocated_amount:'0.00',eligible:true,blocked_reason:null,writes_allowed:true,capacity_released:false,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});
const portion=()=>({portion_id:hash('c'),kind:'original_refund_allocation',event_id:id('a'),document_id:id('b'),customer_id:id('c'),project_id:id('d'),number:'SYN-R2-INVOICE',party_name:'Synthetic customer',amount:'26.44',currency:'EUR',payload_sha256:hash('d'),pdf_sha256:hash('e'),capacity_ownership_id:id('b'),ownership_id:null,writer:'r2',action:'takeover_and_bind',portion_state_hash:hash('f'),eligible:true,blocked_reason:null});
const origin=(version='c1')=>({origin_version:version,entry_id:id(version==='c1'?'d':'e'),group_id:hash('a'),origin_event_id:id(version==='c1'?'b':'f'),component_sequence:1,rate:'19',category:'S',tax_reason:'',document_id:id('b'),customer_id:id('c'),project_id:id('d'),number:'SYN-R2-INVOICE',party_name:'Synthetic customer',cash_date:version==='c1'?'2026-11-01':'2026-11-03',evidence_reference:version==='c1'?'Original evidence':'Reused evidence',reference:version==='c1'?'Original middle lot':'First reuse',currency:'EUR',amount:version==='c1'?'39.67':'13.22',net:version==='c1'?'33.33':'11.11',tax:version==='c1'?'6.34':'2.11',returned_amount:version==='c1'?'13.22':'0.00',returned_net:version==='c1'?'11.11':'0.00',returned_tax:version==='c1'?'2.11':'0.00',remaining_amount:version==='c1'?'26.45':'13.22',remaining_net:version==='c1'?'22.22':'11.11',remaining_tax:version==='c1'?'4.23':'2.11',lot_state_hash:hash(version==='c1'?'a':'b')});
const choices=()=>[{origin:origin('c2'),amount:'13,22'},{origin:origin(),amount:'13.22'}];
const body=()=>refundV2PreviewData(source(),portion(),choices(),'Synthetic mixed actual lots');
const line=(o)=>({origin_version:o.origin_version,entry_id:o.entry_id,group_id:o.group_id,origin_event_id:o.origin_event_id,component_sequence:o.component_sequence,rate:o.rate,category:o.category,tax_reason:o.tax_reason,origin_cash_date:o.cash_date,origin_evidence_reference:o.evidence_reference,origin_reference:o.reference,lot_state_hash:o.lot_state_hash,amount:'13.22',net:o.origin_version==='c1'?'11.10':'11.11',tax:o.origin_version==='c1'?'2.12':'2.11',gross_before:o.returned_amount,gross_after:o.origin_version==='c1'?'26.44':'13.22',net_before:o.returned_net,net_after:o.origin_version==='c1'?'22.21':'11.11',tax_before:o.returned_tax,tax_after:o.origin_version==='c1'?'4.23':'2.11',remaining_gross:o.origin_version==='c1'?'13.23':'0.00',remaining_net:o.origin_version==='c1'?'11.12':'0.00',remaining_tax:o.origin_version==='c1'?'2.11':'0.00'});
const preview=()=>({event_id:id('a'),source_hash:hash('a'),expected_revision:0,state_hash:hash('b'),action:'takeover_and_bind',cash_date:'2026-11-03',evidence_reference:'Refund evidence',reference:'Synthetic mixed refund',portion:portion(),amount:'26.44',net:'22.21',tax:'4.23',lines:[line(origin()),line(origin('c2'))],reason:'Synthetic mixed actual lots',preview_hash:hash('f'),capacity_released:false,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});
const positive=(eventId)=>({event_id:eventId,source_hash:hash('a'),revision:1,state_hash:hash('b'),source_kind:'customer_receipt',amount:'13.22',currency:'EUR',cash_date:'2026-11-03',documented_amount:'13.22',undocumented_amount:'0.00',unallocated_amount:'0.00',eligible:false,blocked_reason:'fully_documented',writes_allowed:true,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});

test('negotiated R2 reauthorizes retained R1 origins through their full capacity closure without candidate eligibility',async()=>{
  const paths=[],api={get:async path=>{paths.push(path);return path.includes('/refunds/')?{...source(),eligible:false}:positive(id('b'));}};
  await refundAuthorize(api,id('a'),[origin(),origin()],{versioned:true,selection:true});
  assert.deepEqual(paths,['/business/accounting/refunds/events/'+id('a'),'/business/accounting/components/v2/events/'+id('b')]);
  for(const status of [403,404])await assert.rejects(refundAuthorize({get:async path=>{if(path.includes('/refunds/'))return source();throw Object.assign(new Error('Entire origin closure denied'),{status});}},id('a'),[origin()],{versioned:true,selection:true}),error=>error.status===status);
  const readOnly={get:async path=>path.includes('/refunds/')?source():{...positive(id('b')),writes_allowed:false}};
  await assert.rejects(refundAuthorize(readOnly,id('a'),[origin()],{versioned:true,selection:true}),error=>error.status===423);
  await refundAuthorize(readOnly,id('a'),[origin()],{versioned:true});
});

test('new refund negotiation requires all prior modules and keeps authorized history readable',()=>{
  assert.deepEqual(refundV2Access(caps(),null,source()),{available:true,read:true,prepare:true});
  for(const feature of caps().features)assert.equal(refundV2Access({...caps(),features:caps().features.filter(item=>item!==feature)},null).read,false);
  for(const capability of caps().capabilities)assert.equal(refundV2Access({...caps(),capabilities:caps().capabilities.filter(item=>item!==capability)},null).read,false);
  for(const permission of ['accounting.read','finance.read'])assert.equal(refundV2Access({...caps(),permissions:caps().permissions.filter(item=>item!==permission)},null).read,false);
  for(const [cap,organization,value,online]of [[caps(),null,{...source(),eligible:false},true],[caps(),null,{...source(),writes_allowed:false},true],[caps(),null,source(),false],[{...caps(),readonly:true},null,source(),true],[caps(),{modules:{finance:{enabled:false}}},source(),true]])assert.deepEqual(refundV2Access(cap,organization,value,online),{available:true,read:true,prepare:false});
});
test('consolidated refund state keeps the fixed whole amount, unresolved rest and documentary flags',()=>{
  assert.equal(refundV2State({...source(),origin_documented_amount:'13.22',origin_unresolved_amount:'13.22'}).amount,'26.44');
  for(const change of [{origin_documented_amount:'0.01'},{capacity_released:true},{tax_result_available:true},{tax_status:'configured'}])assert.throws(()=>refundV2State({...source(),...change}));
});
test('each invoice portion binds its own writer and irreversible ownership boundaries',()=>{
  assert.equal(refundV2Portion(portion(),id('a')).action,'takeover_and_bind');
  assert.equal(refundV2Portion({...portion(),ownership_id:id('b'),action:'bind_current'},id('a')).writer,'r2');
  assert.equal(refundV2Portion({...portion(),capacity_ownership_id:null,writer:'r1',action:'bind_legacy'},id('a')).writer,'r1');
  assert.equal(refundV2Portion({...portion(),eligible:false,action:null,blocked_reason:'unsupported_document'},id('a')).eligible,false);
  for(const change of [{ownership_id:id('e')},{capacity_ownership_id:id('e')},{writer:'r1'},{action:'bind_current'},{capacity_ownership_id:null,ownership_id:id('b')},{eligible:false}])assert.throws(()=>refundV2Portion({...portion(),...change},id('a')));
});
test('version belongs to lot identity even if module sequence, entry id and group id collide',()=>{
  const old=origin(),reused={...origin('c2'),entry_id:old.entry_id};assert.notEqual(refundV2LotKey(old),refundV2LotKey(reused));
  assert.notEqual(refundV2OriginLabel(old),refundV2OriginLabel(reused));assert.match(refundV2OriginLabel(old),/Ursprüngliche/);assert.match(refundV2OriginLabel(reused),/wiederverwendeten/);
  assert.equal(refundV2OriginLabel(reused).includes(reused.entry_id),false);
  assert.equal(refundV2PreviewData(source(),portion(),[{origin:old,amount:'13.22'},{origin:reused,amount:'13.22'}],'Explicit distinct versions').origins.length,2);
  assert.throws(()=>refundV2LotKey({...old,origin_version:'c3'}));
});
test('mixed origins still require exact archived invoice, customer, date and positive chosen amounts',()=>{
  assert.equal(refundV2Origin(origin('c2'),portion(),source().cash_date).cash_date,source().cash_date);
  for(const change of [{document_id:id('e')},{customer_id:id('e')},{cash_date:'2026-11-04'},{remaining_tax:'2.12'},{currency:'USD'},{origin_version:'r1'}])assert.throws(()=>refundV2Origin({...origin('c2'),...change},portion(),source().cash_date));
  for(const selected of [[],[{origin:origin(),amount:'26.43'}],[{origin:origin(),amount:'26.45'}],[{origin:origin(),amount:'0'}],[{origin:origin(),amount:'-1'}],[{origin:origin(),amount:'26.440'}],[{origin:origin(),amount:'26.46'}],[{origin:origin(),amount:'13.22'},{origin:origin(),amount:'13.22'}]])assert.throws(()=>refundV2PreviewData(source(),portion(),selected,'Reason'));
  assert.throws(()=>refundV2PreviewData(source(),{...portion(),capacity_ownership_id:null,writer:'r1',action:'bind_legacy'},choices(),'Reason'));
  assert.throws(()=>refundV2PreviewData(source(),portion(),choices(),'Two\nlines'));
});
test('mixed partial return preserves prior R1 cents and gives 22.21 net plus 4.23 tax',()=>{
  const data=body(),value=preview();assert.equal(data.origins[0].origin_version,'c2');assert.equal('request_id'in data,false);assert.equal('amount'in data,false);
  assert.equal(refundV2Preview(value,data,source(),choices()),value);assert.equal(value.lines[0].tax,'2.12');assert.equal(value.lines[1].tax,'2.11');
  assert.deepEqual(refundV2ConfirmData(data,value,source(),choices(),true).origins,data.origins);assert.throws(()=>refundV2ConfirmData(data,value,source(),choices(),false));
});
test('preview cannot reset the old lot to its remaining basis or swap versioned sources',()=>{
  for(const change of [{action:'bind_current'},{net:'22.22',tax:'4.22'},{cash_date:'2026-11-02'},{reference:'Changed'},{capacity_released:true},{reason:'Changed'}])assert.throws(()=>refundV2Preview({...preview(),...change},body(),source(),choices()));
  for(const change of [{origin_version:'c2'},{net:'11.11',tax:'2.11'},{gross_before:'0.00'},{remaining_tax:'2.12'},{origin_event_id:id('e')},{component_sequence:2},{lot_state_hash:hash('f')},{origin_reference:'Changed'}])assert.throws(()=>refundV2Preview({...preview(),lines:[{...preview().lines[0],...change},preview().lines[1]]},body(),source(),choices()));
});
test('second mixed cycle reaches the complete original middle-lot 33.33/6.34 without losing cents',()=>{
  const old={...origin(),returned_amount:'26.44',returned_net:'22.21',returned_tax:'4.23',remaining_amount:'13.23',remaining_net:'11.12',remaining_tax:'2.11'},newLot={...origin('c2'),entry_id:id('f'),amount:'26.44',net:'22.21',tax:'4.23',remaining_amount:'26.44',remaining_net:'22.21',remaining_tax:'4.23'};
  const nextSource={...source(),amount:'39.67',origin_unresolved_amount:'39.67'},nextPortion={...portion(),ownership_id:id('b'),action:'bind_current',amount:'39.67'},selected=[{origin:old,amount:'13.23'},{origin:newLot,amount:'26.44'}],data=refundV2PreviewData(nextSource,nextPortion,selected,'Second whole cycle');
  const next={...preview(),action:'bind_current',portion:nextPortion,amount:'39.67',net:'33.33',tax:'6.34',reason:data.reason,lines:[{...line(old),amount:'13.23',net:'11.12',tax:'2.11',gross_after:'39.67',net_after:'33.33',tax_after:'6.34',remaining_gross:'0.00',remaining_net:'0.00',remaining_tax:'0.00'},{...line(newLot),amount:'26.44',net:'22.21',tax:'4.23',gross_after:'26.44',net_after:'22.21',tax_after:'4.23'}]};
  assert.equal(refundV2Preview(next,data,nextSource,selected).tax,'6.34');assert.equal(next.lines[0].gross_before,'26.44');assert.equal(next.lines[0].remaining_gross,'0.00');
});
test('cached selections reauthorize full origin events once without requiring positive candidate eligibility',async()=>{
  const paths=[],api={get:async path=>{paths.push(path);return path.includes('/refunds/')?source():positive(path.split('/').at(-1));}};
  await refundV2Authorize(api,id('a'),[origin(),origin(),origin('c2')],{selection:true});
  assert.deepEqual(paths,['/business/accounting/refunds/v2/events/'+id('a'),'/business/accounting/components/v2/events/'+id('b'),'/business/accounting/components/v2/events/'+id('f')]);
  for(const status of [403,404])await assert.rejects(refundV2Authorize({get:async path=>{if(path.includes('/refunds/'))return source();throw Object.assign(new Error('Full origin closure denied'),{status});}},id('a'),[origin()],{selection:true}),error=>error.status===status);
  await assert.rejects(refundV2Authorize({get:async path=>path.includes('/refunds/')?source():{...positive(id('b')),writes_allowed:false}},id('a'),[origin()],{selection:true}),error=>error.status===423);
});
test('refund pending preflight reads the original writer and ignores current new-command eligibility',async()=>{
  for(const version of ['', 'v2/']) {
    const paths=[],path=`/business/accounting/refunds/${version}events/${id('a')}/confirm`;
    assert.equal((await refundPendingAuthorize({get:async value=>{paths.push(value);return {...source(),eligible:false,blocked_reason:'fully_documented'};}},{path})).eligible,false);assert.deepEqual(paths,[path.slice(0,-8)]);
    await assert.rejects(refundPendingAuthorize({get:async()=>({...source(),writes_allowed:false})},{path}),error=>error.status===423);
  }
  await assert.rejects(refundPendingAuthorize({get:async()=>source()},{path:'/business/accounting/components/events/'+id('a')+'/confirm'}));
});
test('lost R1 acknowledgement keeps its original path and body across a later writer transition',async()=>{
  const calls=[],path=`/business/accounting/refunds/events/${id('a')}/confirm`,newPath=`/business/accounting/refunds/v2/events/${id('a')}/confirm`,key=refundPendingKey(id('a'));let mode='lost';
  const api=new OfficeApi({fetcher:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});if(mode==='lost')throw new Error('Accepted, acknowledgement lost');return new Response(JSON.stringify({id:id('f'),event_id:id('a'),capacity_released:false}),{status:201});}});
  api.setToken('synthetic-memory-only');await assert.rejects(api.mutate(key,path,{reason:'Original whole R1 command'}));assert.equal(refundPendingOperation(api.pendingOperations(),id('a')).path,path);assert.equal(refundPendingOperation(api.pendingOperations(),id('b')),null);
  await assert.rejects(api.mutate(key,newPath,body()),/unveränderte Eingabe/);assert.equal(calls.length,1);mode='accepted';await api.retry(key);assert.deepEqual(calls[0],calls[1]);assert.equal(api.pendingCount,0);
});
test('unmarked conflicts, permission changes and uncertain transport keep both refund paths pending',async()=>{
  for(const version of ['', 'v2/']) {
    const path=`/business/accounting/refunds/${version}events/${id('a')}/confirm`,key=refundPendingKey(id('a')),calls=[];let status=0,resolution;
    const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return new Response(JSON.stringify({...source(),eligible:false,blocked_reason:'fully_documented'}));calls.push({url,body:JSON.parse(options.body)});if(!status)throw new Error('Unknown acknowledgement');return new Response(JSON.stringify(status===201?{event_id:id('a')}:{error:'Current gate or conflict',...(resolution?{request_resolution:resolution}:{})}),{status});}});
    api.setToken('synthetic-memory-only');await assert.rejects(api.mutate(key,path,{reason:'Exact original',origins:body().origins}));
    for(const denied of [403,404,409,423,503]){await refundPendingAuthorize(api,api.pendingOperations()[0]);status=denied;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);}
    resolution='unknown';status=409;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);
    await assert.rejects(api.mutate(key,path,{reason:'Changed'}),/unveränderte Eingabe/);
    resolution='not_accepted';await assert.rejects(api.retry(key),error=>error.status===409&&error.requestResolution==='not_accepted');assert.equal(api.pendingCount,0);for(const call of calls)assert.deepEqual(call,calls[0]);
    status=201;await api.mutate(key,path,{reason:'New separately reviewed command'});assert.notEqual(calls.at(-1).body.request_id,calls[0].body.request_id);
  }
});
test('refund preview never becomes pending and logout clears an uncertain versioned command',async()=>{
  const calls=[],api=new OfficeApi({fetcher:async(path,options)=>{calls.push(JSON.parse(options.body));throw new Error('Synthetic network loss');}});api.setToken('synthetic-memory-only');
  await assert.rejects(api.post('/business/accounting/refunds/v2/events/'+id('a')+'/preview',body()));assert.equal(api.pendingCount,0);assert.equal('request_id'in calls[0],false);
  await assert.rejects(api.mutate(refundPendingKey(id('a')),'/business/accounting/refunds/v2/events/'+id('a')+'/confirm',refundV2ConfirmData(body(),preview(),source(),choices(),true)));assert.deepEqual(api.pendingOperations(),[{key:refundPendingKey(id('a')),path:'/business/accounting/refunds/v2/events/'+id('a')+'/confirm'}]);api.clear();assert.equal(api.pendingCount,0);
});
