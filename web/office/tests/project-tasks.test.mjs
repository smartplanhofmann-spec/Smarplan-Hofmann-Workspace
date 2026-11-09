import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi} from '../office.js';
import {taskValues,taskRecord,taskReceipt,taskHistory,taskContext,taskPendingAuthorize,projectTasksUi} from '../project-tasks.js';
const project='a'.repeat(32),other='b'.repeat(32),identifier='c'.repeat(32),actor='d'.repeat(32),assignee='e'.repeat(32);
const values=()=>({title:'Original task',details:'Original detail',status:'todo',priority:'normal',due_date:'2026-11-10',assignee_id:assignee});
const record=(revision=1,change={})=>({...values(),id:identifier,project_id:project,revision,created_by:actor,created_at:'2026-11-09T12:00:00+00:00',updated_by:actor,updated_at:'2026-11-09T12:00:00+00:00',...change});
const context=()=>({project:{id:project},team:[{id:actor,email:'owner@example.test'},{id:assignee,email:'tech@example.test'}]});
const apiFor=(options={})=>({get:async path=>path.endsWith('/workspace')?context():path==='/me'?{id:actor,role:options.role||'owner'}:path.endsWith('/capabilities')?{readonly:options.readonly??false}:record()});

test('task values implement supported priorities, all statuses, exact dates and current assignment',()=>{
  for(const status of ['todo','in_progress','done','cancelled'])assert.equal(taskValues({...values(),status},context().team).status,status);
  for(const change of [{priority:'low'},{status:'open'},{due_date:'2026-02-30'},{due_date:'1800-01-01'},{title:''},{title:'x'.repeat(201)},{details:'x'.repeat(10001)},{assignee_id:other}])assert.throws(()=>taskValues({...values(),...change},context().team));
  assert.equal(taskValues(values(),[],record()).assignee_id,assignee,'removed existing assignee remains unchanged');
  assert.equal(taskValues({...values(),assignee_id:''},[],record()).assignee_id,null);
});
test('task history retains every original and rejects cross-project, gaps, substitutions and stale head',()=>{
  const first=record(),second=record(2,{title:'Changed task',status:'done'}),history={items:[first,second]};
  assert.equal(taskHistory(history,project,second),history.items);assert.equal(first.title,'Original task');
  for(const bad of [{items:[second]},{items:[first,{...second,project_id:other}]},{items:[first,{...second,created_at:'2026-11-08T12:00:00+00:00'}]},{items:[first,{...second,title:'substitution'}]}])assert.throws(()=>taskHistory(bad,project,second));
  assert.throws(()=>taskRecord({...first,id:other},project,identifier));
});
test('receipt verifies full original command, target and revision, including old accepted replay',()=>{
  const body={...values(),revision:2},saved=record(3);assert.equal(taskReceipt(saved,project,identifier,body),saved);
  for(const bad of [{...saved,project_id:other},{...saved,id:other},{...saved,revision:4},{...saved,status:'done'},{...saved,assignee_id:actor}])assert.throws(()=>taskReceipt(bad,project,identifier,body));
});
test('fresh task authorization honors server read-only mode, actual write role and project identity',async()=>{
  for(const role of ['owner','manager','technician'])await taskContext(apiFor({role}),project,{write:true});
  for(const options of [{role:'accountant'},{readonly:true}])await assert.rejects(taskContext(apiFor(options),project,{write:true}));
  await taskContext(apiFor({role:'accountant'}),project);
  const api=apiFor();api.get=async()=>({project:{id:other},team:[]});await assert.rejects(taskContext(api,project));
});
test('pending task preserves exact body after lost ACK, forbids retry after rights loss and then replays original',async()=>{
  let allowed=true,lose=true;const sent=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.endsWith('/workspace')?context():url.endsWith('/me')?{role:allowed?'technician':'accountant'}:url.endsWith('/capabilities')?{readonly:false}:record(5)));
    sent.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('Lost accepted response');}return new Response(JSON.stringify(record(3)));
  }});api.setToken('synthetic-task-owner-session');const key='project-task-'+identifier,path='/projects/'+project+'/tasks/'+identifier,body={...values(),revision:2};
  await assert.rejects(api.mutate(key,path,body,{validate:(result,original)=>taskReceipt(result,project,identifier,original)}));
  allowed=false;await assert.rejects(api.retry(key));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  allowed=true;assert.equal((await api.retry(key)).revision,3);assert.deepEqual(sent[0],sent[1]);assert.equal(api.pendingCount,0);
});
test('pending authorization rejects crossed task keys, malformed commands and inaccessible current task',async()=>{
  const api=apiFor();api.pendingCommandValues=()=>({...values(),revision:1});
  const operation={key:'project-task-'+identifier,path:'/projects/'+project+'/tasks/'+identifier};await taskPendingAuthorize(api,operation);
  await assert.rejects(taskPendingAuthorize(api,{...operation,key:'project-task-'+other}));
  api.pendingCommandValues=()=>({...values(),revision:1,foreign:true});await assert.rejects(taskPendingAuthorize(api,operation));
  api.pendingCommandValues=()=>({...values(),revision:1});const get=api.get;api.get=async path=>path===operation.path?{...record(),project_id:other}:get(path);await assert.rejects(taskPendingAuthorize(api,operation));
});
test('invalid successful receipt and inconsistent retry reads never discard an uncertain task request',async()=>{
  let badRead=false,badReceipt=true;const sent=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.endsWith('/workspace')?{...context(),project:{id:badRead?other:project}}:url.endsWith('/me')?{role:'owner'}:url.endsWith('/capabilities')?{readonly:false}:record()));
    sent.push(JSON.parse(options.body));return new Response(JSON.stringify(record(1,badReceipt?{title:'Unexpected accepted echo'}:{})));
  }});api.setToken('synthetic-task-owner-session');const key='project-task-new-'+project,path='/projects/'+project+'/tasks';
  await assert.rejects(api.mutate(key,path,values(),{validate:(result,body)=>taskReceipt(result,project,null,body)}));assert.equal(api.pendingCount,1);
  badRead=true;await assert.rejects(api.retry(key));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  badRead=false;badReceipt=false;await api.retry(key);assert.deepEqual(sent[0],sent[1]);assert.equal(api.pendingCount,0);
});

class Node{constructor(tag,children=[]){this.tag=tag;this.children=children.flat(Infinity).filter(value=>value!=null);this.isConnected=true;}setAttribute(){}}
const find=(node,test)=>node&&typeof node==='object'?(test(node)?node:node.children?.map(child=>find(child,test)).find(Boolean)):undefined;
function harness(){let view,version=0,current=record(),writes=0,hold=null;const api=apiFor();const get=api.get;
  api.get=async path=>path.endsWith('/'+identifier)?current:get(path);api.pendingCommandValues=()=>null;api.mutate=async()=>{writes++;if(hold)await hold;return record(2);};
  const h={api,el:(tag,attrs,...children)=>new Node(tag,children),button:(label,fn)=>Object.assign(new Node('button',[label]),{label,fn}),panel:(title,...children)=>new Node('panel',[title,...children]),row:(...children)=>new Node('row',children),rows:(items,render)=>new Node('rows',items.map(render)),notice:message=>new Node('notice',[message]),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),form:(title,fields,save,options)=>Object.assign(new Node('form'),{fields,save,options}),dialog:(title,node)=>{if(view)view.isConnected=false;view=node;},formatDate:value=>value,action:fn=>fn(),refresh:async()=>{},stamp:()=>version,writable:()=>true};
  return {ui:projectTasksUi(h),api,get view(){return view;},get writes(){return writes;},change:value=>{current=value;},invalidate:()=>version++,hold:promise=>{hold=promise;}};
}
test('editor offers only supported priorities and all lifecycle states with explicit original revision',async()=>{
  const h=harness();await h.ui.edit(project,identifier);const editor=find(h.view,node=>node.tag==='form');
  assert.deepEqual(editor.fields.find(field=>field.name==='priority').options.map(([value])=>value),['normal','high']);
  assert.deepEqual(editor.fields.find(field=>field.name==='status').options.map(([value])=>value),['todo','in_progress','done','cancelled']);
  assert.match(editor.options.description,/Version 1/);
});
test('changed current revision blocks stale form without issuing a write',async()=>{
  const before=globalThis.document;globalThis.document={visibilityState:'visible'};try{
    const h=harness();await h.ui.edit(project,identifier);h.change(record(2,{title:'Concurrent change'}));
    await assert.rejects(h.view.save(values(),'project-task-'+identifier),/inzwischen geändert/);assert.equal(h.writes,0);
  }finally{globalThis.document=before;}
});
test('late accepted reply cannot close or refresh a replaced task dialog',async()=>{
  const before=globalThis.document;globalThis.document={visibilityState:'visible'};try{
    const h=harness();let release;h.hold(new Promise(resolve=>release=resolve));await h.ui.edit(project,identifier);
    const saved=h.view.save(values(),'project-task-'+identifier);while(h.writes===0)await new Promise(resolve=>setImmediate(resolve));h.invalidate();release();assert.equal(await saved,undefined);
  }finally{globalThis.document=before;}
});
