import test from 'node:test';
import assert from 'node:assert/strict';
import {customValue,customSnapshot,customReceipt,customDisplay,customFieldsUi} from '../custom-fields.js';
import {OfficeApi} from '../office.js';
const id='a'.repeat(32),actor='b'.repeat(32),entity='c'.repeat(32),hash='d'.repeat(64);
const definition={id,revision:1,entity_type:'project',label:'Messwert',help_text:'',field_type:'number',required:true,active:true,options:[],reason:'',content_hash:hash,previous_hash:null,created_by:actor,created_at:'2026-11-03T10:00:00+00:00'};
const current={entity_type:'project',entity_id:entity,revision:0,previous_hash:null,content_hash:null,created_by:null,created_at:null,definitions_hash:null,values:{}};
const view={entity:{entity_type:'project',id:entity,label:'Synthetic',project_id:entity},definitions:[definition],definitions_hash:hash,current,missing_required:[id],complete:false,can_write:true};
const body={revision:0,definitions_hash:hash,values:{[id]:'0.123456'},reason:''};
const result={...current,revision:1,content_hash:hash,created_by:actor,created_at:definition.created_at,definitions_hash:hash,definitions:[definition],values:{[id]:{definition,value:'0.123456'}},reason:''};
const clone=v=>JSON.parse(JSON.stringify(v)),response=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
test('exact typed values preserve decimal precision and explicit false; invalid dates and coercions fail',()=>{
  assert.equal(customValue(definition,'999999999999,123456'),'999999999999.123456');
  assert.equal(customValue({...definition,field_type:'boolean'},'false'),false);
  assert.equal(customValue({...definition,required:false},''),null);
  for(const value of [0,true,'1e2','01','1.1234567','١'])assert.throws(()=>customValue(definition,value));
  assert.throws(()=>customValue({...definition,field_type:'date'},'2026-02-29'));
  assert.equal(customValue({...definition,field_type:'date'},'2028-02-29'),'2028-02-29');
  assert.throws(()=>customValue(definition,''));
});
test('archived option stays legible and unchanged but cannot be newly chosen',()=>{const d={...definition,field_type:'choice',options:[{id:'e'.repeat(32),label:'Alte Auswahl',active:false}]};assert.equal(customValue(d,d.options[0].id,d.options[0].id),d.options[0].id);assert.throws(()=>customValue(d,d.options[0].id));assert.equal(customDisplay({definition:d,value:d.options[0].id}),'Alte Auswahl');});
test('entity and original immutable definition/value bodies bind acknowledgments',()=>{customSnapshot(view,'project',entity);assert.throws(()=>customSnapshot(view,'contact',entity));const validate=customReceipt(body,current,view);validate(result);const bad=clone(result);bad.values[id].value='0';assert.throws(()=>validate(bad));assert.throws(()=>validate({...result,entity_id:actor}));assert.throws(()=>validate({...result,definitions:[]}));const definitionBody={revision:0,definition:Object.fromEntries(['entity_type','label','help_text','field_type','required','active','options'].map(k=>[k,definition[k]])),reason:''};customReceipt(definitionBody)(definition);assert.throws(()=>customReceipt(definitionBody)({...definition,required:false}));});
test('malformed reply retains original pending values without inventing success',async()=>{const api=new OfficeApi({fetcher:async()=>response({...result,values:{}})});api.setToken('synthetic-custom-fields-session');await assert.rejects(api.mutate('custom-fields-project-'+entity,'/business/custom-fields/entities/project/'+entity,body,{validate:customReceipt(body,current,view)}));assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues('custom-fields-project-'+entity,'/business/custom-fields/entities/project/'+entity),body);});
test('in-flight view cannot publish after authenticated session changes',async()=>{let stamp=1,deliver,published=false;const ui=customFieldsUi({api:{get:()=>new Promise(r=>deliver=r)},biz:p=>p,enabled:()=>true,stamp:()=>stamp,dialog:()=>published=true});const pending=ui.open('project',entity);stamp=2;deliver(view);await assert.rejects(pending,/Sitzung/);assert.equal(published,false);});
test('lost acknowledgment repeats original nonce only after fresh actual entity write permission',async()=>{let lose=true,write=true;const posts=[],api=new OfficeApi({fetcher:async(path,options)=>{if(options.method==='GET')return response(path.endsWith('/capabilities')?{readonly:false,features:['custom_fields'],capabilities:['business_custom_fields'],permissions:['documents.read','projects.manage']}:{...view,can_write:write});posts.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('Lost acknowledgment');}return response(result);}});api.setToken('synthetic-custom-field-session');const key='custom-fields-project-'+entity,path='/business/custom-fields/entities/project/'+entity;await assert.rejects(api.mutate(key,path,body,{validate:customReceipt(body,current,view)}));assert.equal(api.pendingCount,1);write=false;await assert.rejects(api.retry(key),/Schreibberechtigung/);assert.equal(posts.length,1);assert.equal(api.pendingCount,1);write=true;await api.retry(key);assert.equal(api.pendingCount,0);assert.deepEqual(posts[0],posts[1]);});

export {definition,current,view,body,result};
