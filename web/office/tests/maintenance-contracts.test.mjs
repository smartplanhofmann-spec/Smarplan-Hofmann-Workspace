import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi} from '../office.js';
import {maintenanceContractValues,maintenanceContractReceipt,maintenanceContractPendingAuthorize,maintenanceContractsUi} from '../maintenance-contracts.js';

const project='a'.repeat(32),id='b'.repeat(32),asset='c'.repeat(32),media='d'.repeat(32);
const path='/business/maintenance/contracts/'+id,key='maintenance-contract-'+id;
const original={id,project_id:project,asset_id:asset,title:'Originalvertrag',anchor_date:'2026-11-01',
  interval_unit:'months',interval_count:1,active:true,notes:'Original',media_ids:[media],revision:3};
const values={...original,title:'Pausierter Vertrag',notes:'Vertrag pausiert',active:false};
const body=()=>maintenanceContractValues(project,original,values);
function harness(){
  const state={allowed:true,readonly:false,wrong:false,lose:false,status:200,hook:null,returnedId:id,returnedProject:project};
  const posts=[],effects=new Map(),reads=[];
  const api=new OfficeApi({fetcher:async(url,request)=>{
    if(request.method==='POST'){
      const command=JSON.parse(request.body);posts.push(command);
      if(state.status!==200)return Response.json({error:'Synthetic rejected original'},{status:state.status});
      if(!effects.has(command.request_id))effects.set(command.request_id,{...original,...command,revision:command.revision+1});
      state.source=effects.get(command.request_id);
      await state.hook?.(url);
      if(state.lose){state.lose=false;throw new Error('Synthetic accepted response lost');}
      return Response.json({...effects.get(command.request_id),...(state.wrong?{project_id:'e'.repeat(32)}:{})});
    }
    reads.push(url);await state.hook?.(url);
    if(url.includes('/capabilities'))return Response.json({readonly:state.readonly,capabilities:['business_maintenance'],permissions:state.allowed?['documents.read','projects.manage']:[]});
    return Response.json({...state.source||original,id:state.returnedId,project_id:state.returnedProject});
  }});
  api.setToken('synthetic-maintenance-original-token');
  return {api,state,posts,effects,reads};
}
test('editing keeps canonical project, complete schedule and original files; dates and intervals are validated',()=>{
  assert.deepEqual(body(),{project_id:project,asset_id:asset,title:values.title,anchor_date:values.anchor_date,
    interval_unit:'months',interval_count:1,active:false,notes:values.notes,media_ids:[media],revision:3});
  assert.throws(()=>maintenanceContractValues('e'.repeat(32),original,values));
  assert.throws(()=>maintenanceContractValues(project,original,{...values,anchor_date:'2026-02-31'}));
  assert.throws(()=>maintenanceContractValues(project,original,{...values,interval_count:121}));
  assert.equal(maintenanceContractValues(project,null,{...values,interval_unit:'days',interval_count:3660}).revision,undefined);
});
test('receipt binds every edited value, original files, project, id and exact next revision',()=>{
  const sent=body(),receipt={...original,...sent,revision:4};
  assert.equal(maintenanceContractReceipt(path,sent,receipt),receipt);
  for(const change of [{id:'e'.repeat(32)},{revision:5},{project_id:asset},{active:true},{notes:'Other'},{interval_count:2},{media_ids:[]}])
    assert.throws(()=>maintenanceContractReceipt(path,sent,{...receipt,...change}));
});
test('lost accepted pause repeats same request only after fresh rights and canonical contract lookup',async()=>{
  const h=harness(),sent=body();h.state.lose=true;
  await assert.rejects(h.api.mutate(key,path,sent,{validate:value=>maintenanceContractReceipt(path,sent,value)}));
  h.state.allowed=false;
  await assert.rejects(h.api.retry(key),/Wartungsrechte/);
  assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,1);
  h.state.allowed=true;await h.api.retry(key);
  assert.deepEqual(h.posts[0],h.posts[1]);assert.equal(h.effects.size,1);assert.equal(h.api.pendingCount,0);
  assert.ok(h.reads.some(url=>url.endsWith('/'+id+'?project_id='+project)));
});
test('wrong receipt is retained, a confirmed stale revision permits loading a fresh contract',async()=>{
  const h=harness(),sent=body();h.state.wrong=true;
  await assert.rejects(h.api.mutate(key,path,sent,{validate:value=>maintenanceContractReceipt(path,sent,value)}),/ursprüngliche/);
  assert.equal(h.api.pendingCount,1);h.state.wrong=false;await h.api.retry(key);assert.equal(h.effects.size,1);
  h.state.status=409;await assert.rejects(h.api.mutate(key,path,sent));assert.equal(h.api.pendingCount,0);
});
test('server denial retains unresolved original; a login change during retry never sends it as the new actor',async()=>{
  for(const status of [403,404]){
    const h=harness();h.state.status=status;await assert.rejects(h.api.mutate(key,path,body()));
    assert.equal(h.api.pendingCount,1);
    h.state.hook=async url=>{if(url.includes('/capabilities'))h.api.setToken('synthetic-different-maintenance-user');};
    await assert.rejects(h.api.retry(key));assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,0);
  }
});
test('readonly and foreign canonical contract are rejected before retry',async()=>{
  const h=harness();h.state.lose=true;await assert.rejects(h.api.mutate(key,path,body()));
  h.state.readonly=true;await assert.rejects(maintenanceContractPendingAuthorize(h.api,{key,path}),/Wartungsrechte/);
  h.state.readonly=false;h.state.returnedId=asset;
  await assert.rejects(maintenanceContractPendingAuthorize(h.api,{key,path}),/anderen Wartungsvertrag/);
  h.state.returnedId=id;h.state.returnedProject=asset;
  await assert.rejects(maintenanceContractPendingAuthorize(h.api,{key,path}),/richtigen Projekt/);
  assert.equal(h.posts.length,1);
});
test('closed retry context after its internal source read sends no second POST',async()=>{
  const h=harness();h.state.lose=true;await assert.rejects(h.api.mutate(key,path,body()));
  let active=true;
  h.state.hook=async url=>{if(url.includes('/contracts/'))active=false;};
  await assert.rejects(h.api.retry(key,{stillCurrent:()=>active}),/Ansicht wurde geschlossen/);
  assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,1);
});
test('a mode conflict during retry cannot erase an earlier accepted original',async()=>{
  const h=harness(),sent=body();h.state.lose=true;
  await assert.rejects(h.api.mutate(key,path,sent,{validate:value=>maintenanceContractReceipt(path,sent,value)}));
  const accepted=structuredClone(h.posts[0]);h.state.status=409;
  await assert.rejects(h.api.retry(key));assert.equal(h.api.pendingCount,1);
  h.state.status=200;await h.api.retry(key);
  assert.deepEqual(h.posts,[accepted,accepted,accepted]);assert.equal(h.effects.size,1);
});

function uiHarness(api){
  let stamp=0,active=true,current=null;const forms=[];
  const h={api,available:()=>active,stamp:()=>stamp,today:()=> '2026-11-09',
    field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),
    el:()=>({}),notice:()=>({}),button:(name,run)=>({name,run}),
    form:(_title,fields,save,options)=>{
      const submit={textContent:options.submit},box={isConnected:false,fields,save,options,
        setAttribute(){},querySelectorAll(){return [];},querySelector(query){return query.includes('submit')?submit:null;},prepend(){}};
      forms.push(box);return box;
    },dialog:(_title,box)=>{if(current)current.isConnected=false;current=box;box.isConnected=true;stamp++;},
    closeModal:()=>{if(current)current.isConnected=false;stamp++;},refresh:async()=>{stamp++;},updatePending(){},action:fn=>fn()};
  return {h,forms,close:()=>{h.closeModal();active=false;},other:()=>h.dialog('Other',{isConnected:true})};
}
test('closing editor during fresh authorization prevents POST and leaves a later dialog untouched',async()=>{
  const network=harness(),ui=uiHarness(network.api),module=maintenanceContractsUi(ui.h);
  await module.edit(project,[{id:asset,name:'Anlage'}],id);
  const editor=ui.forms[0];let release,started;
  const held=new Promise(resolve=>started=resolve),wait=new Promise(resolve=>release=resolve);
  network.state.hook=async url=>{if(url.includes('/capabilities')){started();await wait;}};
  const saving=editor.save(values);await held;ui.close();ui.other();release();
  assert.equal(await saving,undefined);assert.equal(network.posts.length,0);
});
test('late accepted response after closing editor clears only confirmed original without reopening UI',async()=>{
  const network=harness(),ui=uiHarness(network.api),module=maintenanceContractsUi(ui.h);
  await module.edit(project,[{id:asset,name:'Anlage'}],id);
  let release,started;const held=new Promise(resolve=>started=resolve),wait=new Promise(resolve=>release=resolve);
  network.state.hook=async url=>{if(!url.includes('?')){started();await wait;}};
  const saving=ui.forms[0].save(values);await held;ui.close();ui.other();release();
  assert.equal(await saving,undefined);assert.equal(network.effects.size,1);assert.equal(network.api.pendingCount,0);
});
test('a replacement pending editor cannot turn an already confirmed original into a new revision',async()=>{
  const network=harness(),ui=uiHarness(network.api),module=maintenanceContractsUi(ui.h);
  await module.edit(project,[{id:asset,name:'Anlage'}],id);
  let release,started;const held=new Promise(resolve=>started=resolve),wait=new Promise(resolve=>release=resolve);
  network.state.hook=async url=>{if(!url.includes('?')){started();await wait;}};
  const first=ui.forms[0].save(values);await held;
  await module.edit(project,[{id:asset,name:'Anlage'}],id);
  assert.equal(ui.forms.length,2);release();await first;network.state.hook=null;
  assert.equal(network.api.pendingCount,0);
  await ui.forms[1].save(values);
  assert.equal(network.posts.length,1,'Only the original accepted pause may exist.');
  assert.equal(network.effects.size,1);
});
