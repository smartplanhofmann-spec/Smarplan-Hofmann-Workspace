import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {communicationHistoryPage,historyStatus,createCommunicationHistory} from '../communication-history.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/communication_history.json',import.meta.url)));
test('actual six-source history binds canonical customer/project and preserves receipt meaning',()=>{
  const full=communicationHistoryPage(f.full,f.scope);
  assert.equal(full.items.length,11);
  assert.equal(new Set(full.items.map(v=>v.kind)).size,6);
  communicationHistoryPage(f.project,f.project_scope);
  assert.equal(full.items.filter(v=>v.accepted_by_server).length,1);
  assert.ok(full.items.every(v=>v.recipient_delivery_confirmed===false));
  assert.equal(historyStatus({kind:'inquiry',status:'accepted'}),'Zusage vermerkt');
  assert.equal(historyStatus({kind:'delivery',status:'accepted'}),'Vom Versandserver angenommen');
});
test('all pages share a snapshot, stable ordering and unique keys',()=>{
  const scope={...f.scope,limit:'2'},first=communicationHistoryPage(f.first,scope),second=communicationHistoryPage(f.second,scope,first);
  assert.equal(second.items.length,4);assert.equal(new Set(second.items.map(v=>v.key)).size,4);
  const reordered=structuredClone(f.second);reordered.scope=Object.fromEntries(Object.entries(reordered.scope).reverse());
  communicationHistoryPage(reordered,scope,first);
  const changed=structuredClone(f.second);changed.snapshot_sha256='f'.repeat(64);
  assert.throws(()=>communicationHistoryPage(changed,scope,first));
  assert.throws(()=>communicationHistoryPage(f.second,{...f.scope,limit:'50'},first));
});
test('foreign scope, forged receipt, invalid time, duplicate and private fields fail closed',()=>{
  const mutations=[v=>v.customer.id='f'.repeat(32),v=>v.scope.project_id='f'.repeat(32),v=>v.items[0].recipient_delivery_confirmed=true,
    v=>v.items[0].accepted_by_server=!v.items[0].accepted_by_server,v=>v.items[0].occurred_at='2026-02-30T00:00:00+00:00',
    v=>v.items[0].recorded_at='2026-11-03',v=>v.items[0].key='unbound',v=>v.items[0].credential='extra',
    v=>v.items.push(v.items[0]),v=>v.items.reverse(),v=>v.has_more=true];
  for(const mutate of mutations){const altered=structuredClone(f.full);mutate(altered);assert.throws(()=>communicationHistoryPage(altered,f.scope));}
});
test('manual corrected activity remains separate and HTML stays ordinary text',()=>{
  const value=communicationHistoryPage(f.full,f.scope),old=value.items.find(v=>v.superseded),correction=value.items.find(v=>v.supersedes_key===old.key);
  assert.equal(correction.provenance,'manual_activity');assert.equal(correction.precision,'day');assert.equal(correction.accepted_by_server,false);
  const altered=structuredClone(f.full);altered.items[0].text='<img src=x onerror=alert(1)>';
  assert.equal(communicationHistoryPage(altered,f.scope).items[0].text,'<img src=x onerror=alert(1)>');
  altered.items[0].text='😀'.repeat(40000);communicationHistoryPage(altered,f.scope);
});

class Node {
  constructor(tag,attrs={},...children){this.tag=tag;this.attrs=attrs;this.children=children.flat().filter(v=>v!==null&&v!==undefined);this.value=attrs.value??'';this.events={};this.isConnected=false;}
  addEventListener(name,fn){this.events[name]=fn;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
}
function content(node){return typeof node==='string'?node:node?.children?.map(content).join(' ')||'';}
function setup({change=false}={}){
  let reads=0,stamp=1,allowed=true;
  const nodes=[],el=(...args)=>{const node=new Node(...args);nodes.push(node);return node;},caps=()=>({generation:1,permissions:['contacts.read',...(change&&reads>0?[]:['finance.read'])],features:['communication_history'],capabilities:['business_sales']});
  const h={el,nodes,button:(name,fn)=>{const n=el('button',{},name);n.click=fn;return n;},notice:message=>el('p',{},message),formatDate:String,action:fn=>fn(),biz:p=>'/business'+p,stamp:()=>stamp,allowed:()=>allowed,dialog(){},openProject(){},api:{get:async path=>{if(path.includes('/capabilities'))return caps();reads++;return structuredClone(f.full);}}};
  return {ui:createCommunicationHistory(h),h,invalidate(){stamp++;},deny(){allowed=false;}};
}
test('fresh effective rights after response prevent display of a now-revoked source',async()=>{
  const a=setup({change:true}),node=await a.ui.view(f.scope);
  assert.match(content(node),/Leserechte.*geändert/);assert.doesNotMatch(content(node),/Synthetic corrected call/);
});
test('clear and context changes discard private results and late responses',async()=>{
  const a=setup(),node=await a.ui.view(f.scope);assert.match(content(node),/Synthetic corrected call/);
  a.ui.clear();assert.doesNotMatch(content(node),/Synthetic corrected call/);
  const b=setup();let release;b.h.api.get=async path=>path.includes('/capabilities')?{generation:1,permissions:['contacts.read'],features:['communication_history'],capabilities:['business_sales']}:new Promise(resolve=>{release=resolve;});
  const pending=b.ui.view(f.scope);while(!release)await new Promise(r=>setImmediate(r));b.invalidate();release(structuredClone(f.full));
  assert.doesNotMatch(content(await pending),/Synthetic corrected call/);
});
test('a newly submitted filter supersedes a pending read instead of silently dropping the search',async()=>{
  const a=setup();let release,reads=0;
  a.h.api.get=async path=>path.includes('/capabilities')?{generation:1,permissions:['contacts.read'],features:['communication_history'],capabilities:['business_sales']}:
    ++reads===1?new Promise(resolve=>{release=resolve;}):structuredClone(f.filtered);
  const pending=a.ui.view(f.scope);while(!release)await new Promise(resolve=>setImmediate(resolve));
  a.h.nodes.find(n=>n.attrs['aria-label']==='Kommunikationsverlauf durchsuchen').value='corrected';
  a.h.nodes.find(n=>n.attrs['aria-label']==='Verlaufsquelle').value='sales';
  a.h.nodes.find(n=>n.tag==='form').events.submit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  release(structuredClone(f.full));const node=await pending;
  assert.equal(reads,2);assert.match(content(node),/Synthetic corrected call/);assert.doesNotMatch(content(node),/Synthetic call original/);
});
test('a late first customer dialog cannot replace the most recently selected customer',async()=>{
  const a=setup(),id='f'.repeat(32),other=structuredClone(f.full),dialogs=[];
  other.scope.customer_id=id;other.customer={id,name:'Last explicitly selected customer'};other.items=[];
  let release;
  a.h.dialog=(_,node)=>dialogs.push(content(node));
  a.h.api.get=async path=>path.includes('/capabilities')?{generation:1,permissions:['contacts.read'],features:['communication_history'],capabilities:['business_sales']}:
    path.includes(id)?other:new Promise(resolve=>{release=resolve;});
  const first=a.ui.open(f.scope.customer_id);while(!release)await new Promise(resolve=>setImmediate(resolve));
  await a.ui.open(id);release(structuredClone(f.full));await first;
  assert.equal(dialogs.length,1);assert.match(dialogs[0],/Last explicitly selected customer/);
});
