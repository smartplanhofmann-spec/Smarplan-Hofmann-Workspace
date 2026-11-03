import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,refundAccess,refundState,refundPortion,refundOrigin,refundPreviewData,refundPreview,refundConfirmData,refundAuthorize,refundOriginLabel} from '../office.js';
const id=x=>x.repeat(32),hash=x=>x.repeat(64);
const caps=()=>({permissions:['accounting.read','accounting.prepare','finance.read','finance.write'],features:['accounting_prejournal','accounting_payment_allocation','accounting_document_components','accounting_refund_origins'],capabilities:['business_accounting','business_accounting_allocations','business_accounting_components','business_accounting_refunds'],readonly:false});
const source=()=>({event_id:id('a'),source_hash:hash('a'),revision:0,state_hash:hash('b'),source_kind:'customer_refund',amount:'26.44',currency:'EUR',cash_date:'2026-11-02',evidence_reference:'Refund evidence',reference:'Synthetic refund',origin_documented_amount:'0.00',origin_unresolved_amount:'26.44',unallocated_amount:'0.00',eligible:true,blocked_reason:null,writes_allowed:true,capacity_released:false,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});
const portion=()=>({portion_id:hash('c'),kind:'original_refund_allocation',event_id:id('a'),document_id:id('b'),customer_id:id('c'),project_id:id('d'),number:'SYN-REFUND-INVOICE',party_name:'Synthetic customer',amount:'26.44',currency:'EUR',payload_sha256:hash('d'),pdf_sha256:hash('e'),portion_state_hash:hash('f'),eligible:true,blocked_reason:null});
const origin=(second=false)=>({entry_id:id(second?'e':'d'),group_id:hash('a'),origin_event_id:id(second?'f':'b'),component_sequence:second?2:1,rate:'19',category:'S',tax_reason:'',document_id:id('b'),customer_id:id('c'),project_id:id('d'),number:'SYN-REFUND-INVOICE',party_name:'Synthetic customer',cash_date:second?'2026-11-02':'2026-11-01',evidence_reference:second?'Original evidence B':'Original evidence A',reference:second?'Original B':'Original A',currency:'EUR',amount:'39.67',net:second?'33.33':'33.34',tax:second?'6.34':'6.33',returned_amount:'0.00',returned_net:'0.00',returned_tax:'0.00',remaining_amount:'39.67',remaining_net:second?'33.33':'33.34',remaining_tax:second?'6.34':'6.33',lot_state_hash:hash(second?'b':'a')});
const choices=()=>[{origin:origin(true),amount:'13,22'},{origin:origin(),amount:'13.22'}];
const body=()=>refundPreviewData(source(),portion(),choices(),'Synthetic origin evidence');
const line=o=>({entry_id:o.entry_id,group_id:o.group_id,origin_event_id:o.origin_event_id,component_sequence:o.component_sequence,rate:o.rate,category:o.category,tax_reason:o.tax_reason,origin_cash_date:o.cash_date,origin_evidence_reference:o.evidence_reference,origin_reference:o.reference,lot_state_hash:o.lot_state_hash,amount:'13.22',net:'11.11',tax:'2.11',gross_before:'0.00',gross_after:'13.22',net_before:'0.00',net_after:'11.11',tax_before:'0.00',tax_after:'2.11',remaining_gross:'26.45',remaining_net:o.entry_id===id('d')?'22.23':'22.22',remaining_tax:o.entry_id===id('d')?'4.22':'4.23'});
const preview=()=>({event_id:id('a'),source_hash:hash('a'),expected_revision:0,state_hash:hash('b'),cash_date:'2026-11-02',evidence_reference:'Refund evidence',reference:'Synthetic refund',portion:portion(),amount:'26.44',net:'22.22',tax:'4.22',lines:[line(origin()),line(origin(true))],reason:'Synthetic origin evidence',preview_hash:hash('f'),capacity_released:false,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});

test('refund access negotiates all dependencies and separates historical read from new commands',()=>{
  assert.deepEqual(refundAccess(caps(),null,source()),{available:true,read:true,prepare:true});
  for(const feature of caps().features)assert.equal(refundAccess({...caps(),features:caps().features.filter(x=>x!==feature)},null).read,false);
  for(const capability of caps().capabilities)assert.equal(refundAccess({...caps(),capabilities:caps().capabilities.filter(x=>x!==capability)},null).read,false);
  for(const permission of ['accounting.read','finance.read'])assert.equal(refundAccess({...caps(),permissions:caps().permissions.filter(x=>x!==permission)},null).read,false);
  for(const permission of ['accounting.prepare','finance.write'])assert.deepEqual(refundAccess({...caps(),permissions:caps().permissions.filter(x=>x!==permission)},null,source()),{available:true,read:true,prepare:false});
  for(const [cap,organization,value,online]of [[{...caps(),readonly:true},null,source(),true],[caps(),{modules:{finance:{enabled:false}}},source(),true],[caps(),null,{...source(),writes_allowed:false},true],[caps(),null,{...source(),eligible:false},true],[caps(),null,source(),false]])assert.deepEqual(refundAccess(cap,organization,value,online),{available:true,read:true,prepare:false});
});
test('refund state preserves unresolved original rest and never claims capacity or a tax result',()=>{
  assert.equal(refundState(source()).origin_unresolved_amount,'26.44');
  for(const change of [{capacity_released:true},{tax_result_available:true},{tax_status:'configured'},{origin_documented_amount:'0.01'},{unallocated_amount:'26.45'},{cash_date:'2026-02-30'},{source_kind:'refund'}])assert.throws(()=>refundState({...source(),...change}));
  assert.equal(refundState({...source(),eligible:false,blocked_reason:'not_customer_refund',source_kind:'customer_receipt'}).eligible,false);
});
test('origin identity binds exact invoice, archived customer and cash date, not similar amount',()=>{
  assert.equal(refundPortion(portion(),id('a')).amount,'26.44');assert.equal(refundOrigin(origin(true),portion(),source().cash_date).cash_date,source().cash_date);
  for(const change of [{document_id:id('e')},{customer_id:id('e')},{cash_date:'2026-11-03'},{currency:'USD'},{remaining_tax:'4.00'},{component_sequence:0}])assert.throws(()=>refundOrigin({...origin(),...change},portion(),source().cash_date));
  assert.throws(()=>refundPortion({...portion(),kind:'original_allocation'},id('a')));
});
test('same group across two entries stays distinct and original input order survives sorted response',()=>{
  const data=body(),value=preview();assert.equal(data.origins.length,2);assert.equal(data.origins[0].entry_id,id('e'));assert.equal(data.origins[0].group_id,data.origins[1].group_id);
  assert.equal('request_id' in data,false);assert.equal('amount' in data,false);assert.equal(refundPreview(value,data,source(),choices()),value);
  assert.deepEqual(refundConfirmData(data,value,source(),choices(),true).origins,data.origins);assert.throws(()=>refundConfirmData(data,value,source(),choices(),false));
});
test('whole refund portion needs explicit positive exact cents and each lot pair only once',()=>{
  for(const list of [[],[{origin:origin(),amount:'26.43'}],[{origin:origin(),amount:'26.45'}],[{origin:origin(),amount:'0'}],[{origin:origin(),amount:'-1'}],[{origin:origin(),amount:'26.440'}],[{origin:origin(),amount:'40'}],[{origin:origin(),amount:'13.22'},{origin:origin(),amount:'13.22'}]])assert.throws(()=>refundPreviewData(source(),portion(),list,'Reason'));
  assert.throws(()=>refundPreviewData(source(),portion(),choices(),'Two\nlines'));
  assert.throws(()=>refundPreviewData(source(),{...portion(),eligible:false},choices(),'Reason'));
});
test('server preview must preserve immutable origin labels, selected cents and original lot tax basis',()=>{
  for(const change of [{net:'22.23'},{capacity_released:true},{reference:'Different refund'},{cash_date:'2026-11-01'},{reason:'Other'}])assert.throws(()=>refundPreview({...preview(),...change},body(),source(),choices()));
  for(const change of [{net:'11.10'},{tax:'2.12'},{gross_before:'0.01'},{remaining_tax:'4.23'},{origin_event_id:id('c')},{component_sequence:9},{category:'E'},{tax_reason:'Other'},{origin_reference:'Other'},{lot_state_hash:hash('f')}])assert.throws(()=>refundPreview({...preview(),lines:[{...preview().lines[0],...change},preview().lines[1]]},body(),source(),choices()));
});
test('subsequent partial return preserves differing frozen lot cents and final exact residual',()=>{
  const origins=[origin(),origin(true)].map((o,i)=>({...o,returned_amount:'13.22',returned_net:'11.11',returned_tax:'2.11',remaining_amount:'26.45',remaining_net:i?'22.22':'22.23',remaining_tax:i?'4.23':'4.22'}));
  const selected=origins.map(o=>({origin:o,amount:'13.22'})),data=refundPreviewData(source(),portion(),selected,'Second partial return');
  const value={...preview(),reason:data.reason,net:'22.21',tax:'4.23',lines:origins.map((o,i)=>({...line(o),net:i?'11.10':'11.11',tax:i?'2.12':'2.11',gross_before:'13.22',gross_after:'26.44',net_before:'11.11',net_after:i?'22.21':'22.22',tax_before:'2.11',tax_after:i?'4.23':'4.22',remaining_gross:'13.23',remaining_net:'11.12',remaining_tax:'2.11'}))};
  assert.equal(refundPreview(value,data,source(),selected).tax,'4.23');
  assert.throws(()=>refundPreview({...value,tax:'4.22'},data,source(),selected));
});
test('origin labels distinguish component sequences and archived zero-rate reasons without internal IDs',()=>{
  assert.notEqual(refundOriginLabel(origin()),refundOriginLabel(origin(true)));
  assert.match(refundOriginLabel({...origin(),rate:'0',category:'E',tax_reason:'Synthetic exemption'}),/Synthetic exemption/);
  assert.equal(refundOriginLabel(origin()).includes(origin().entry_id),false);
});
test('fresh authorization checks full protected refund and all distinct origin events before details',async()=>{
  const paths=[],api={get:async path=>{paths.push(path);if(path.includes('/refunds/'))return source();if(path.endsWith(id('f')))throw Object.assign(new Error('Denied later project B'),{status:403});return {id:path.split('/').at(-1)};}};
  await assert.rejects(refundAuthorize(api,id('a'),[origin(),origin(),origin(true)]),error=>error.status===403);
  assert.deepEqual(paths,['/business/accounting/refunds/events/'+id('a'),...[id('a'),id('b'),id('f')].map(x=>'/business/accounting/events/'+x)]);
});
test('lost confirmation keeps original ordered payload; denied preflight and 423 do not discard it',async()=>{
  const calls=[];let mode='lost';const api=new OfficeApi({fetcher:async(path,options)=>{if(options.method==='GET'){if(mode==='denied')return new Response(JSON.stringify({error:'Denied'}),{status:403});return new Response(JSON.stringify(path.includes('/refunds/')?source():{id:path.split('/').at(-1)}));}calls.push({path,body:JSON.parse(options.body)});if(mode==='lost')throw new Error('Synthetic loss before or after acceptance');if(mode==='paused')return new Response(JSON.stringify({error:'Paused'}),{status:423});return new Response(JSON.stringify(preview()),{status:201});}});api.setToken('synthetic-memory-only');
  const prefix='/business/accounting/refunds/events/'+id('a'),data=refundConfirmData(body(),preview(),source(),choices(),true);
  await assert.rejects(api.post(prefix+'/preview',body()));assert.equal(api.pendingCount,0);assert.equal('request_id' in calls[0].body,false);
  await assert.rejects(api.mutate('refund',prefix+'/confirm',data));assert.deepEqual(api.pendingOperations(),[{key:'refund',path:prefix+'/confirm'}]);
  mode='denied';await assert.rejects(refundAuthorize(api,id('a'),[origin(),origin(true)]));assert.equal(api.pendingCount,1);
  mode='paused';await assert.rejects(api.retry('refund'),error=>error.status===423);await assert.rejects(api.mutate('refund',prefix+'/confirm',{...data,origins:[...data.origins].reverse()}),/unveränderte Eingabe/);
  mode='ok';await refundAuthorize(api,id('a'),[origin(),origin(true)]);await api.retry('refund');assert.deepEqual(calls[1],calls[2]);assert.deepEqual(calls[2],calls[3]);assert.equal(api.pendingCount,0);
});

test('a newly denied earlier bound origin stops pending preflight before any selected-origin detail or POST',async()=>{
  const paths=[];const api={get:async path=>{paths.push(path);throw Object.assign(new Error('Earlier origin acquired restricted project B'),{status:403});}};
  await assert.rejects(refundAuthorize(api,id('a'),[origin(true)]),error=>error.status===403);
  assert.deepEqual(paths,['/business/accounting/refunds/events/'+id('a')]);
});
