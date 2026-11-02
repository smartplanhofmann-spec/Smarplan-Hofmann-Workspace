import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,componentAccess,componentState,componentPortion,componentPreviewData,componentPreview,componentConfirmData,componentGroupLabel} from '../office.js';
const id=letter=>letter.repeat(32),hash=letter=>letter.repeat(64);
const capabilities=(permissions=['accounting.read','accounting.prepare','finance.read','finance.write'])=>({permissions,features:['accounting_prejournal','accounting_payment_allocation','accounting_document_components'],capabilities:['business_accounting','business_accounting_allocations','business_accounting_components'],readonly:false});
const state=()=>({event_id:id('a'),source_hash:hash('a'),revision:0,state_hash:hash('b'),source_kind:'customer_receipt',amount:'39.67',currency:'EUR',documented_amount:'0.00',undocumented_amount:'39.67',unallocated_amount:'0.00',eligible:true,blocked_reason:null,writes_allowed:true,scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});
const group=()=>({group_id:hash('c'),rate:'19',category:'S',reason:'',net:'100.00',tax:'19.00',gross:'119.00',documented_net:'0.00',documented_tax:'0.00',documented_gross:'0.00',remaining_net:'100.00',remaining_tax:'19.00',remaining_gross:'119.00'});
const portion=()=>({portion_id:hash('d'),kind:'original_allocation',event_id:id('a'),document_id:id('b'),receipt_id:null,project_id:id('c'),number:'SYN-COMPONENT-1',party_name:'Synthetic customer',amount:'39.67',currency:'EUR',payload_sha256:hash('e'),pdf_sha256:hash('f'),original_sha256:null,review_revision:null,review_sha256:null,portion_state_hash:hash('a'),eligible:true,blocked_reason:null,groups:[group()]});
const body=()=>componentPreviewData(state(),portion(),[{group_id:hash('c'),amount:'39,67'}],'Synthetic documentary evidence');
const preview=()=>({event_id:id('a'),source_hash:hash('a'),expected_revision:0,state_hash:hash('b'),portion:portion(),amount:'39.67',net:'33.34',tax:'6.33',lines:[{group_id:hash('c'),amount:'39.67',net:'33.34',tax:'6.33',gross_before:'0.00',gross_after:'39.67',net_before:'0.00',net_after:'33.34',tax_before:'0.00',tax_after:'6.33',remaining_gross:'79.33'}],reason:'Synthetic documentary evidence',preview_hash:hash('e'),scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false});

test('component feature dependencies and global write permissions keep read history separate',()=>{
  assert.deepEqual(componentAccess(capabilities(),null,state()),{available:true,read:true,prepare:true});
  for(const permission of ['accounting.read','finance.read'])assert.equal(componentAccess(capabilities(capabilities().permissions.filter(item=>item!==permission)),null,state()).read,false);
  for(const permission of ['accounting.prepare','finance.write']){const result=componentAccess(capabilities(capabilities().permissions.filter(item=>item!==permission)),null,state());assert.equal(result.read,true);assert.equal(result.prepare,false);}
  for(const feature of capabilities().features)assert.equal(componentAccess({...capabilities(),features:capabilities().features.filter(item=>item!==feature)},null,state()).available,false);
  for(const module of capabilities().capabilities)assert.equal(componentAccess({...capabilities(),capabilities:capabilities().capabilities.filter(item=>item!==module)},null,state()).available,false);
  for(const [caps,organization,value,online] of [[capabilities(),null,state(),false],[{...capabilities(),readonly:true},null,state(),true],[capabilities(),{modules:{finance:{enabled:false}}},state(),true],[capabilities(),null,{...state(),eligible:false},true],[capabilities(),null,{...state(),writes_allowed:false},true]])assert.deepEqual(componentAccess(caps,organization,value,online),{available:true,read:true,prepare:false});
});
test('state is documentary and preserves unresolved refunds without pretending empty success',()=>{
  assert.equal(componentState(state()).amount,'39.67');const refund={...state(),source_kind:'customer_refund',eligible:false,blocked_reason:'refund_origin_unresolved'};assert.equal(componentState(refund),refund);
  for(const change of [{tax_result_available:true},{tax_status:'ready'},{scope:'company'},{amount:'39.670'},{documented_amount:'0.01'},{unallocated_amount:'40.00'},{revision:-1}])assert.throws(()=>componentState({...state(),...change}));
});
test('whole portion identity and exact group sum cannot be replaced by a smaller invented partial amount',()=>{
  assert.deepEqual(body(),{source_hash:hash('a'),expected_revision:0,state_hash:hash('b'),portion_id:hash('d'),portion_state_hash:hash('a'),groups:[{group_id:hash('c'),amount:'39.67'}],reason:'Synthetic documentary evidence'});
  assert.equal('request_id' in body(),false);assert.equal('amount' in body(),false);
  for(const groups of [[],[{group_id:hash('c'),amount:'39.66'}],[{group_id:hash('c'),amount:'39.68'}],[{group_id:hash('c'),amount:'0'}],[{group_id:hash('c'),amount:'-1'}],[{group_id:hash('c'),amount:'39.670'}],[{group_id:hash('e'),amount:'39.67'}],[{group_id:hash('c'),amount:'20'},{group_id:hash('c'),amount:'19.67'}]])assert.throws(()=>componentPreviewData(state(),portion(),groups,'Evidence'));
  assert.throws(()=>componentPreviewData(state(),portion(),body().groups,'Two\nlines'));
  assert.throws(()=>componentPreviewData(state(),{...portion(),eligible:false,blocked_reason:'review_changed'},body().groups,'Evidence'));
});
test('multiple groups are explicit and keep original command order despite sorted preview lines',()=>{
  const second={group_id:hash('b'),rate:'7',category:'S',reason:'',net:'50.00',tax:'3.50',gross:'53.50',documented_net:'0.00',documented_tax:'0.00',documented_gross:'0.00',remaining_net:'50.00',remaining_tax:'3.50',remaining_gross:'53.50'};
  const selected={...portion(),amount:'172.50',groups:[group(),second]},source={...state(),amount:'172.50',undocumented_amount:'172.50'};
  const data=componentPreviewData(source,selected,[{group_id:hash('c'),amount:'119'},{group_id:hash('b'),amount:'53,5'}],'Two explicit groups');
  const value={...preview(),portion:selected,amount:'172.50',net:'150.00',tax:'22.50',reason:data.reason,lines:[{group_id:hash('b'),amount:'53.50',net:'50.00',tax:'3.50',gross_before:'0.00',gross_after:'53.50',net_before:'0.00',net_after:'50.00',tax_before:'0.00',tax_after:'3.50',remaining_gross:'0.00'},{group_id:hash('c'),amount:'119.00',net:'100.00',tax:'19.00',gross_before:'0.00',gross_after:'119.00',net_before:'0.00',net_after:'100.00',tax_before:'0.00',tax_after:'19.00',remaining_gross:'0.00'}]};
  componentPreview(value,data,id('a'));assert.deepEqual(componentConfirmData(data,value,true).groups,data.groups);
  assert.throws(()=>componentPreviewData(source,selected,[{group_id:hash('c'),amount:'119.01'},{group_id:hash('b'),amount:'53.49'}],'Overflow'),/Bruttorest/);
});
test('supplier group uses fixed reviewed totals without inventing a tax rate',()=>{
  const value={...portion(),kind:'supplier_payout',document_id:null,payload_sha256:null,pdf_sha256:null,receipt_id:id('d'),original_sha256:hash('e'),review_revision:2,review_sha256:hash('f'),groups:[{...group(),rate:null,category:null,reason:null}]};
  assert.equal(componentPortion(value,id('a')),value);assert.equal(componentPreviewData({...state(),source_kind:'supplier_payout'},value,body().groups,'Reviewed source').portion_id,value.portion_id);
  assert.throws(()=>componentPortion({...value,review_revision:0},id('a')));
});
test('server cent differences preserve the cumulative middle rounding cent and require exact line totals',()=>{
  const basis={...group(),documented_gross:'39.67',documented_net:'33.34',documented_tax:'6.33',remaining_gross:'79.33',remaining_net:'66.66',remaining_tax:'12.67'};
  const middle={...preview(),portion:{...portion(),groups:[basis]},net:'33.33',tax:'6.34',lines:[{group_id:hash('c'),amount:'39.67',net:'33.33',tax:'6.34',gross_before:'39.67',gross_after:'79.34',net_before:'33.34',net_after:'66.67',tax_before:'6.33',tax_after:'12.67',remaining_gross:'39.66'}]};
  assert.equal(componentPreview(middle,body(),id('a')),middle);
  for(const change of [{net:'33.34'},{tax:'6.33'},{remaining_gross:'39.67'},{gross_before:'0.00'},{net_after:'66.68'},{group_id:hash('e')}])assert.throws(()=>componentPreview({...middle,lines:[{...middle.lines[0],...change}]},body(),id('a')));
  for(const change of [{event_id:id('e')},{source_hash:hash('e')},{state_hash:hash('e')},{expected_revision:2},{reason:'Other'},{tax_result_available:true},{amount:'39.66'}])assert.throws(()=>componentPreview({...middle,...change},body(),id('a')));
  assert.throws(()=>componentConfirmData(body(),middle,false));
});
test('side-effect-free preview has no pending request; lost confirm retries exact groups after later capacity change',async()=>{
  const calls=[];let mode='preview';const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(mode==='preview'||mode==='lost')throw new Error('Synthetic lost response');if(mode==='paused')return new Response(JSON.stringify({error:'Finance paused'}),{status:423});return new Response(JSON.stringify({id:id('e'),...preview()}),{status:201});}});api.setToken('synthetic-memory-bearer-only');
  const prefix='/business/accounting/components/events/'+id('a');await assert.rejects(api.post(prefix+'/preview',body()));assert.equal(api.pendingCount,0);assert.equal('request_id' in calls[0].body,false);
  mode='lost';await assert.rejects(api.mutate('components',prefix+'/confirm',componentConfirmData(body(),preview(),true)));assert.deepEqual(api.pendingOperations(),[{key:'components',path:prefix+'/confirm'}]);
  mode='paused';await assert.rejects(api.retry('components'),error=>error.status===423);await assert.rejects(api.mutate('components',prefix+'/confirm',{...componentConfirmData(body(),preview(),true),portion_state_hash:hash('f')}),/unveränderte Eingabe/);
  mode='accepted';await api.retry('components');assert.deepEqual(calls[1],calls[2]);assert.deepEqual(calls[2],calls[3]);assert.equal(api.pendingCount,0);
});

test('large immutable archive groups remain exact while new inputs keep the E1a limit',()=>{
  const large={...group(),net:'1000000000.00',tax:'190000000.00',gross:'1190000000.00',remaining_net:'1000000000.00',remaining_tax:'190000000.00',remaining_gross:'1190000000.00'};
  const selected={...portion(),amount:'1.00',groups:[large]},source={...state(),amount:'1.00',undocumented_amount:'1.00'};
  assert.equal(componentPortion(selected,id('a')),selected);
  const data=componentPreviewData(source,selected,[{group_id:large.group_id,amount:'1'}],'Small real portion of large archive');
  const value={...preview(),portion:selected,amount:'1.00',net:'0.84',tax:'0.16',reason:data.reason,lines:[{group_id:large.group_id,amount:'1.00',net:'0.84',tax:'0.16',gross_before:'0.00',gross_after:'1.00',net_before:'0.00',net_after:'0.84',tax_before:'0.00',tax_after:'0.16',remaining_gross:'1189999999.00'}]};
  assert.equal(componentPreview(value,data,id('a')),value);
  assert.throws(()=>componentPreviewData(source,selected,[{group_id:large.group_id,amount:'1000000000.00'}],'Too large input'));
});

test('zero-rate groups remain distinguishable by source category and exemption reason',()=>{
  const first=componentGroupLabel({rate:'0',category:'E',reason:'Synthetic exemption A'}),second=componentGroupLabel({rate:'0',category:'E',reason:'Synthetic exemption B'}),reverse=componentGroupLabel({rate:'0',category:'AE',reason:'Synthetic reverse-charge evidence'});
  assert.notEqual(first,second);assert.match(first,/Synthetic exemption A/);assert.match(second,/Synthetic exemption B/);assert.notEqual(first,reverse);
  assert.equal(componentGroupLabel({rate:null,category:null,reason:null}),'Geprüfte Gesamtsummen');
});
