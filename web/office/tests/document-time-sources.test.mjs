import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError,OfficeApi,StaleSession} from '../office.js';
import {
  documentTimeSources,documentTimeRights,documentTimeContext,
  documentTimeCommand,documentTimePendingAuthorize,documentTimeUnchanged,
  documentTimeReceipt,documentTimesChanged,documentTimePicker,
} from '../document-time-sources.js';

// Synthetic shapes of the existing approved_billable/_time_values contract.
// The independent end-to-end test supplies actual backend-generated originals.
const project='a'.repeat(32),otherProject='b'.repeat(32),entry='c'.repeat(32),otherEntry='d'.repeat(32),documentId='e'.repeat(32);
const copy=value=>structuredClone(value);
const source=(change={})=>({entry_id:entry,revision:2,source_hash:'1'.repeat(64),net_seconds:3607,
  segments:[{work_date:'2026-11-08',net_seconds:7},{work_date:'2026-11-09',net_seconds:3600}],
  label:'Freigegebene Projektzeit',date:'2026-11-08',...change});
const caps=(change={})=>({project_id:project,capabilities:['business_documents','business_time'],permissions:['finance.read','finance.write','documents.read'],
  features:['organization_modules'],organization:{modules:{documents:{enabled:true}}},readonly:false,...change});
const position=(value=source(),change={})=>({id:'f'.repeat(32),index:1,description:value.label+' · '+value.date,
  quantity:String(value.net_seconds),unit:'SEC',unit_price_net:'100.0000',price_base_quantity:'3600',tax_rate:'19',kind:'labor',
  source_type:'time',source_id:value.entry_id,source_revision:value.revision,source_hash:value.source_hash,source_seconds:value.net_seconds,...change});
const receipt=(change={})=>({id:documentId,project_id:project,status:'draft',revision:1,positions:[position()],...change});
const expected=(change={})=>({project,selected:[source()],existing:[],rate:'100',tax:'19.00',...change});
const command=()=>({project_id:project,kind:'invoice',title:'Synthetic time invoice',issue_date:'2026-11-09',due_date:'2026-11-09',positions:[],time_entry_ids:[entry],hourly_rate_net:'100',time_tax_rate:'19'});

test('whole approved entries retain both midnight segments and exact original hashes without sharing mutable input',()=>{
  const input={items:[source()]},parsed=documentTimeSources(input);
  assert.deepEqual(parsed,input.items);
  input.items[0].segments[0].net_seconds=999;
  assert.equal(parsed[0].segments[0].net_seconds,7);
  assert.equal(parsed[0].net_seconds,3607);
  assert.equal(parsed[0].source_hash,'1'.repeat(64));
});

test('source parser rejects duplicate or partial originals and inconsistent day totals',()=>{
  for(const input of [
    {},{items:[source(),source()]},
    {items:[source({entry_id:otherProject+'x'})]},
    {items:[source({revision:0})]},
    {items:[source({source_hash:'1'.repeat(63)})]},
    {items:[source({net_seconds:-1})]},
    {items:[source({net_seconds:3607.5})]},
    {items:[source({net_seconds:3608})]},
    {items:[source({date:'2026-02-30'})]},
    {items:[source({date:'2026-11-09'})]},
    {items:[source({segments:[{work_date:'2026-11-08',net_seconds:7},{work_date:'2026-11-08',net_seconds:3600}]})]},
    {items:[source({segments:[{work_date:'2026-11-08',net_seconds:3607.5}]})]},
  ])assert.throws(()=>documentTimeSources(input),ApiError);
  // A fully corrected zero-duration original is valid transport data. It is
  // excluded by the picker, because a billed line must have positive quantity.
  assert.equal(documentTimeSources({items:[source({net_seconds:0,segments:[{work_date:'2026-11-08',net_seconds:0}]})]})[0].net_seconds,0);
});

test('time import needs project-scoped document and finance reads plus a writable document module',()=>{
  assert.deepEqual(documentTimeRights(caps(),project),{read:true,write:true});
  assert.deepEqual(documentTimeRights(caps(),otherProject),{read:false,write:false});
  for(const permission of ['documents.read','finance.read'])assert.deepEqual(documentTimeRights(caps({permissions:caps().permissions.filter(value=>value!==permission)}),project),{read:false,write:false});
  for(const change of [
    {permissions:['documents.read','finance.read']},{readonly:true},
    {organization:{modules:{documents:{enabled:false}}}},
  ])assert.deepEqual(documentTimeRights(caps(change),project),{read:true,write:false});
  assert.deepEqual(documentTimeRights(caps({capabilities:['business_documents']}),project),{read:false,write:false});
  assert.deepEqual(documentTimeRights(caps({permissions:[],global_permissions:caps().permissions}),project),{read:false,write:false});
});

test('fresh context rejects withdrawn rights, removed project and a changed login during either read',async()=>{
  let permissions=caps(),projects=[{id:project}],generation=1,changeAt='';const reads=[];
  const api={get generation(){return generation;},get:async path=>{reads.push(path);if(path===changeAt)generation++;return path.startsWith('/business/capabilities')?copy(permissions):copy(projects);}};
  await documentTimeContext(api,project);
  assert.deepEqual(reads,['/business/capabilities?project_id='+project,'/projects']);
  reads.length=0;permissions=caps({permissions:[]});await assert.rejects(documentTimeContext(api,project),error=>error.status===403);assert.equal(reads.length,1);
  permissions=caps();projects=[];await assert.rejects(documentTimeContext(api,project),error=>error.status===403);
  projects=[{id:project}];changeAt='/business/capabilities?project_id='+project;await assert.rejects(documentTimeContext(api,project),StaleSession);
  changeAt='/projects';await assert.rejects(documentTimeContext(api,project),StaleSession);
});

test('only a chosen subset must stay unchanged; consumed, corrected and reapproved chosen originals are rejected',()=>{
  const chosen=source(),unselected=source({entry_id:otherEntry});
  documentTimeUnchanged([chosen],[chosen,{...unselected,source_hash:'2'.repeat(64)}]);
  for(const current of [[],[unselected],[{...chosen,source_hash:'2'.repeat(64)}],[{...chosen,revision:3}],[{...chosen,net_seconds:3606}]])assert.throws(()=>documentTimeUnchanged([chosen],current),error=>error.status===409);
});

test('receipt binds the selected source, exact decimal rate, tax, target and draft revision',()=>{
  assert.deepEqual(documentTimeReceipt(receipt(),expected()),[]);
  assert.equal(documentTimesChanged(receipt()),false);
  for(const changed of [
    {project_id:otherProject},{id:'not-a-document'},{status:'final'},{revision:2},
    {positions:[position(source(),{unit_price_net:'100.0001'})]},
    {positions:[position(source(),{tax_rate:'19.0001'})]},
    {positions:[position(source(),{price_base_quantity:'60'})]},
    {positions:[position(source(),{quantity:'3606'})]},
    {positions:[position(source(),{source_id:otherEntry})]},
    {positions:[position(),position()]},
  ])assert.throws(()=>documentTimeReceipt(receipt(changed),expected()),ApiError);
  // One unit in the fourth decimal place must remain distinguishable even at
  // large values where binary Number arithmetic would discard it.
  const large='9999999999.9999';
  assert.deepEqual(documentTimeReceipt(receipt({positions:[position(source(),{unit_price_net:large})]}),expected({rate:large})),[]);
  assert.throws(()=>documentTimeReceipt(receipt({positions:[position(source(),{unit_price_net:'9999999999.9998'})]}),expected({rate:large})),ApiError);
});

test('existing source positions remain exact and cannot be duplicated by a new selection',()=>{
  const old=position(source({entry_id:otherEntry}),{description:'Original\r\nZeitbeschreibung\n'});
  const saved=receipt({revision:3,positions:[old,position()]});
  assert.deepEqual(documentTimeReceipt(saved,expected({identifier:documentId,revision:2,existing:[old]})),[]);
  for(const changed of [{description:'Original Zeitbeschreibung'},{source_hash:'3'.repeat(64)},{unit_price_net:'100'},{source_seconds:3606}]){
    assert.throws(()=>documentTimeReceipt(receipt({revision:3,positions:[{...old,...changed},position()]}),expected({identifier:documentId,revision:2,existing:[old]})),ApiError);
  }
  assert.throws(()=>documentTimeReceipt(receipt(),expected({existing:[position()]})),ApiError);
});

test('a source changed only at server acceptance is marked on the actual response without mutating the DTO',()=>{
  const newer=source({revision:3,source_hash:'4'.repeat(64),net_seconds:3608,segments:[{work_date:'2026-11-08',net_seconds:8},{work_date:'2026-11-09',net_seconds:3600}]}),value=receipt({positions:[position(newer)]}),before=copy(value);
  assert.deepEqual(documentTimeReceipt(value,expected()),[entry]);
  assert.equal(documentTimesChanged(value),true);
  assert.deepEqual(value,before);
  assert.equal(documentTimesChanged(copy(value)),false,'unrelated JSON must not inherit a receipt observation');
});

test('only the exact existing document mutation contract receives time retry authorization',async()=>{
  const body=command(),operation={key:'document-new',path:'/business/documents'},reads=[];
  assert.equal(documentTimeCommand(operation.key,operation.path,body),true);
  assert.equal(documentTimeCommand('document-'+documentId,operation.path+'/'+documentId,{project_id:project,positions:[position()]}),true);
  for(const data of [null,{}, {positions:{}}, {positions:[null]}])assert.equal(documentTimeCommand(operation.key,operation.path,data),false);
  for(const [key,path,data]of [['other',operation.path,body],['document-new','/business/documents/x',body],['document-new',operation.path,{positions:[]}],['document-new','/business/documents?project_id='+project,body]])assert.equal(documentTimeCommand(key,path,data),false);
  const api={generation:1,pendingCommandValues:()=>body,get:async path=>{reads.push(path);return path.startsWith('/business/capabilities')?caps():[{id:project}];}};
  await documentTimePendingAuthorize(api,operation);
  assert.deepEqual(reads,['/business/capabilities?project_id='+project,'/projects']);
  assert.ok(reads.every(path=>!path.includes('time-sources')),'an accepted and later billed original still has an idempotent receipt');
});

test('lost acceptance keeps the frozen request through rights withdrawal and replays it without a source-availability lookup',async()=>{
  let allowed=true,lose=true;const posts=[],reads=[],accepted=receipt();
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET'){
      reads.push(url);
      if(url.includes('time-sources'))throw new Error('Replay must not depend on an unbilled source');
      return new Response(JSON.stringify(url.includes('/capabilities')?caps({permissions:allowed?caps().permissions:[]}):[{id:project}]));
    }
    posts.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('Accepted response lost');}
    return new Response(JSON.stringify(accepted));
  }});
  api.setToken('synthetic-document-time-session');const body=command();
  await assert.rejects(api.mutate('document-new','/business/documents',body,{validate:value=>documentTimeReceipt(value,expected())}));
  body.title='Changed after transmission';body.time_entry_ids.push(otherEntry);
  allowed=false;await assert.rejects(api.retry('document-new'),error=>error.status===403);
  assert.equal(api.pendingCount,1);assert.equal(posts.length,1);
  await assert.rejects(api.mutate('document-new','/business/documents',body),/vorige Antwort/);
  allowed=true;assert.equal((await api.retry('document-new')).id,documentId);
  assert.deepEqual(posts[0],posts[1]);assert.equal(posts[1].title,'Synthetic time invoice');assert.deepEqual(posts[1].time_entry_ids,[entry]);
  assert.equal(api.pendingCount,0);assert.ok(reads.every(path=>!path.includes('time-sources')));
});

test('HTTP403 and invalid successful receipts preserve a time command until an exact valid receipt is obtained',async()=>{
  let mode='denied';const posts=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?caps():[{id:project}]));
    posts.push(JSON.parse(options.body));
    if(mode==='denied')return new Response(JSON.stringify({error:'Permission withdrawn'}),{status:403});
    return new Response(JSON.stringify(receipt(mode==='invalid'?{positions:[position(source(),{tax_rate:'7'})]}:{})));
  }});
  api.setToken('synthetic-document-time-session');
  await assert.rejects(api.mutate('document-new','/business/documents',command(),{validate:value=>documentTimeReceipt(value,expected())}),error=>error.status===403);
  assert.equal(api.pendingCount,1);mode='invalid';await assert.rejects(api.retry('document-new'),ApiError);assert.equal(api.pendingCount,1);
  mode='valid';await api.retry('document-new');assert.equal(api.pendingCount,0);
  assert.deepEqual(posts[0],posts[1]);assert.deepEqual(posts[1],posts[2]);
});

class Element {
  constructor(tag,attrs={},children=[]){this.tag=tag;Object.assign(this,attrs);this.children=children.flat(Infinity).filter(value=>value!==null&&value!==undefined);this.isConnected=true;}
  append(...children){this.children.push(...children.flat(Infinity).filter(value=>value!==null&&value!==undefined));}
  replaceChildren(...children){this.children=[];this.append(...children);}
  querySelectorAll(selectors){const tags=selectors.split(',');return walk(this).filter(node=>tags.includes(node.tag));}
}
function walk(node){return node instanceof Element?[node,...node.children.flatMap(walk)]:[];}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function until(check){for(let index=0;index<30;index++){if(check())return;await tick();}assert.ok(check(),'asynchronous picker state did not settle');}
function pickerHarness({sources=[source()],existing=[]}={}){
  let currentProject=project,version=1,capability=caps(),sourceResult=copy(sources),selected=0;
  const reads=[],api={generation:1,get:async path=>{reads.push(path);return path.startsWith('/business/capabilities')?copy({...capability,project_id:currentProject}):path==='/projects'?[{id:currentProject}]:{items:copy(sourceResult)};}};
  const picker=documentTimePicker({api,el:(tag,attrs,...children)=>new Element(tag,attrs,children),button:(label,onClick)=>new Element('button',{onClick},[label]),notice:message=>new Element('notice',{},[message]),formatDate:value=>value,stamp:()=>version,project:()=>currentProject,positions:()=>copy(existing),onSelect:()=>selected++});
  return {picker,api,reads,get selected(){return selected;},set sources(value){sourceResult=copy(value);},set rights(value){capability=value;},switchProject(){currentProject=otherProject;},invalidate(){version++;}};
}

test('picker omits zero and already bound entries and imports only the explicit remaining subset',async()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:'visible'};
  try{
    const available=source({entry_id:otherEntry}),zero=source({entry_id:'0'.repeat(32),net_seconds:0,segments:[{work_date:'2026-11-08',net_seconds:0}]}),h=pickerHarness({sources:[source(),available,zero],existing:[position()]});
    h.picker.start();await until(()=>walk(h.picker.element).some(node=>node['data-time-entry']===otherEntry));
    const boxes=walk(h.picker.element).filter(node=>node.type==='checkbox');assert.deepEqual(boxes.map(node=>node['data-time-entry']),[otherEntry]);
    boxes[0].onChange({target:{checked:true}});
    walk(h.picker.element).find(node=>node['aria-label']==='Abrechnungssatz netto je Stunde (€)').value='100,25';
    const result=await h.picker.prepare();
    assert.deepEqual(result.data,{time_entry_ids:[otherEntry],hourly_rate_net:'100.25',time_tax_rate:'19'});assert.deepEqual(result.selected,[available]);assert.equal(h.selected,1);
    h.sources=[{...available,source_hash:'9'.repeat(64)}];await assert.rejects(h.picker.prepare(),error=>error.status===409);
  }finally{globalThis.document=previous;}
});

test('a late old-project source response or permissions withdrawn during load cannot display choices',async()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:'visible'};
  try{
    const h=pickerHarness();let release,sourceReads=0;const get=h.api.get;
    h.api.get=async path=>{if(path.startsWith('/business/documents/time-sources')&&sourceReads++===0)return new Promise(resolve=>release=resolve);return get(path);};
    h.picker.start();await until(()=>typeof release==='function');
    h.switchProject();h.sources=[source({entry_id:otherEntry})];await h.picker.load();
    release({items:[source()]});await tick();
    assert.deepEqual(walk(h.picker.element).filter(node=>node.type==='checkbox').map(node=>node['data-time-entry']),[otherEntry]);
    h.rights=caps({permissions:[]});await h.picker.load();assert.equal(walk(h.picker.element).filter(node=>node.type==='checkbox').length,0);
    h.picker.element.isConnected=false;await assert.rejects(h.picker.prepare(),StaleSession);
  }finally{globalThis.document=previous;}
});

test('a source load finishing during submission keeps newly rendered choices and rate controls locked',async()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:'visible'};
  try{
    const h=pickerHarness();let release;const get=h.api.get;
    h.api.get=async path=>path.startsWith('/business/documents/time-sources')?new Promise(resolve=>release=resolve):get(path);
    h.picker.start();await until(()=>typeof release==='function');
    // Save begins before the initial source response has arrived. Locking the
    // current DOM alone would miss all checkbox controls created afterwards.
    h.picker.busy(true);
    release({items:[source()]});
    await until(()=>walk(h.picker.element).some(node=>node.type==='checkbox'));
    assert.ok(h.picker.element.querySelectorAll('input,button').every(node=>node.disabled===true));
    h.picker.busy(false);
    assert.ok(h.picker.element.querySelectorAll('input,button').every(node=>node.disabled===false),'a rejected preflight can return to editing');
    h.picker.freeze();
    const reloading=h.picker.load();await tick();release({items:[source()]});await reloading;
    assert.ok(h.picker.element.querySelectorAll('input,button').every(node=>node.disabled===true),'an unresolved original remains frozen through another completed load');
  }finally{globalThis.document=previous;}
});
