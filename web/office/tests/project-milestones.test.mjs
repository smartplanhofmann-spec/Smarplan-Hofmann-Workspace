import test from 'node:test';
import assert from 'node:assert/strict';
import {milestoneValues,milestoneRights,milestoneContext,milestoneCommandPath,projectMilestonesUi} from '../project-milestones.js';
import {ApiError} from '../office.js';

const project='a'.repeat(32),other='b'.repeat(32),actor='c'.repeat(32),member='d'.repeat(32);
const caps=()=>({project_id:project,features:['project_milestones'],capabilities:['business_project_milestones'],permissions:['planning.read','projects.manage'],readonly:false,organization:{modules:{planning:{enabled:true}}}});
const team=()=>[{id:actor,email:'owner@example.test',role:'owner'},{id:member,email:'tech@example.test',role:'technician'}];
const values=()=>({title:'  Unverändertes Ziel  ',details:'Beschreibung\n',due_date:'2028-02-29',assignee_id:member,status:'planned'});

test('milestone fields retain original whitespace and allow the same Unicode codepoint limits as the backend',()=>{
  assert.deepEqual(milestoneValues(values(),team()),values());
  assert.equal(milestoneValues({...values(),title:'🎯'.repeat(200),details:'🎯'.repeat(10000)},team()).title.length,400);
  for(const change of [{title:'🎯'.repeat(201)},{details:'🎯'.repeat(10001)},{title:'\u0085 '},{title:'invalid \ud800'},{details:'invalid \udfff'},{status:'todo'},{due_date:'2026-02-29'},{due_date:'2201-01-01'},{assignee_id:other}])assert.throws(()=>milestoneValues({...values(),...change},team()));
  assert.equal(milestoneValues(values(),[],values()).assignee_id,member,'unchanged historical member is retained');
  assert.equal(milestoneValues({...values(),due_date:'',assignee_id:''},[]).assignee_id,null);
});
test('milestone rights are project-scoped and require project management rather than planning write',()=>{
  assert.deepEqual(milestoneRights(caps(),project),{read:true,write:true});
  assert.deepEqual(milestoneRights({...caps(),permissions:['planning.read','planning.write']},project),{read:true,write:false});
  assert.deepEqual(milestoneRights({...caps(),permissions:[],global_permissions:['planning.read','projects.manage']},project),{read:false,write:false});
  for(const change of [{project_id:other},{features:[]},{capabilities:[]}])assert.deepEqual(milestoneRights({...caps(),...change},project),{read:false,write:false});
  for(const change of [{readonly:true},{organization:{modules:{planning:{enabled:false}}}}])assert.deepEqual(milestoneRights({...caps(),...change},project),{read:true,write:false});
});
test('fresh milestone context reads the scoped capability and exact team source before accepting current user',async()=>{
  const reads=[];let result=caps();const api={get:async path=>{reads.push(path);return path.startsWith('/business/capabilities')?result:path==='/me'?{id:actor}:{project:{id:project},team:team()};}};
  assert.equal((await milestoneContext(api,project,{write:true})).user.id,actor);
  assert.equal(reads[0],'/business/capabilities?project_id='+project);assert.ok(reads.includes('/projects/'+project+'/workspace'));
  reads.length=0;result={...caps(),permissions:[]};await assert.rejects(milestoneContext(api,project));assert.equal(reads.length,1,'no team data after scoped denial');
});
test('only exact project milestone command paths receive the pending contract',()=>{
  assert.equal(milestoneCommandPath('/business/projects/'+project+'/milestones')[1],project);
  assert.equal(milestoneCommandPath('/business/projects/'+project+'/milestones/'+other)[2],other);
  for(const path of ['/projects/'+project+'/milestones','/business/projects/'+project+'/milestones/'+other+'/history','/business/projects/'+project+'/milestones?project_id='+other,'/business/projects/unknown/milestones'])assert.equal(milestoneCommandPath(path),null);
});

class Node{constructor(tag,children=[]){this.tag=tag;this.children=children.flat(Infinity).filter(value=>value!=null);this.isConnected=true;}setAttribute(){}replaceChildren(...children){this.children=children;}}
const find=(node,predicate)=>node&&typeof node==='object'?(predicate(node)?node:node.children?.map(child=>find(child,predicate)).find(Boolean)):undefined;
function harness(){
  let version=0,view,writes=0,hold=null;
  const api={get:async path=>path.startsWith('/business/capabilities')?caps():path==='/me'?{id:actor}:{project:{id:project},team:team()},pendingCommandValues:()=>null,mutate:async()=>{writes++;if(hold)await hold;return {};}};
  const ui=projectMilestonesUi({api,el:(tag,attrs,...children)=>new Node(tag,children),button:(label,fn)=>Object.assign(new Node('button',[label]),{label,fn}),panel:(title,...children)=>new Node('panel',[title,...children]),row:(...children)=>new Node('row',children),rows:(items,render)=>new Node('rows',items.map(render)),notice:message=>new Node('notice',[message]),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),form:(title,fields,save,options)=>Object.assign(new Node('form'),{fields,save,options}),dialog:(title,node)=>{if(view)view.isConnected=false;view=node;},formatDate:value=>value,action:fn=>fn(),refresh:async()=>{},stamp:()=>version});
  return {ui,api,get view(){return view;},get writes(){return writes;},invalidate:()=>version++,hold:value=>hold=value};
}
test('milestone DOM limits accommodate codepoints without permitting longer values in the contract',async()=>{
  const h=harness();await h.ui.edit(project);const form=find(h.view,node=>node.tag==='form');
  assert.equal(form.fields.find(field=>field.name==='title').maxLength,400);
  assert.equal(form.fields.find(field=>field.name==='details').maxLength,20000);
  assert.equal(form.fields.find(field=>field.name==='status').value,'planned');
});
test('late milestone save does not finish a replaced dialog and navigation before preflight prevents writing',async()=>{
  const previous=globalThis.document;globalThis.document={visibilityState:'visible'};
  try{
    const h=harness();await h.ui.edit(project);h.invalidate();assert.equal(await h.view.save(values(),'milestone-save-new-'+project),undefined);assert.equal(h.writes,0);
    await h.ui.edit(project);let release;h.hold(new Promise(resolve=>release=resolve));const pending=h.view.save(values(),'milestone-save-new-'+project);
    while(h.writes===0)await new Promise(resolve=>setImmediate(resolve));h.invalidate();release();assert.equal(await pending,undefined);
  }finally{globalThis.document=previous;}
});
test('late denied milestone load after navigation cannot display an error in the next workspace',async()=>{
  const h=harness();let reject;h.api.get=()=>new Promise((resolve,fail)=>reject=fail);
  const loading=h.ui.edit(project);h.invalidate();reject(new ApiError('Project access withdrawn',403));
  assert.equal(await loading,undefined);assert.equal(h.view,undefined);assert.equal(h.writes,0);
});
