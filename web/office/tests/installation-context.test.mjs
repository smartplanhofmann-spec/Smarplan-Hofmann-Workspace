import test from 'node:test';
import assert from 'node:assert/strict';
import {installationContextView,readInstallationContext} from '../installation-context.js';

const recorded=()=>({schema_version:1,status:'recorded',source_commit:'a'.repeat(40),api_compatibility_version:'0.12.0-online-pilot'});
test('server source is explicit and separate from API compatibility; unknown never guesses a checkout',()=>{
 assert.deepEqual(installationContextView(recorded()),{recorded:true,source:'a'.repeat(40),compatibility:'0.12.0-online-pilot'});
 assert.deepEqual(installationContextView({...recorded(),status:'unrecorded',source_commit:null}),{recorded:false,source:null,compatibility:'0.12.0-online-pilot'});
 for(const changed of [{...recorded(),source_commit:null},{...recorded(),status:'unrecorded'},
  {...recorded(),schema_version:true},{...recorded(),private_path:'/private/data'},
  {...recorded(),source_commit:'a'.repeat(40)+'\n'},{...recorded(),api_compatibility_version:'<script>'}])assert.throws(()=>installationContextView(changed));
});
test('rights and context are checked before and after the actual source read; no mutation',async()=>{
 for(const change of ['none','rights','feature','generation','context']){
  let permitted=true,feature=true,current=true;const calls=[];
  const api={generation:1,get:async path=>{
   calls.push(path);
   if(path==='/business/installation'){
    if(change==='rights')permitted=false;if(change==='feature')feature=false;
    if(change==='generation')api.generation++;if(change==='context')current=false;
    return recorded();
   }
   return {permissions:permitted?['settings.manage']:[],features:feature?['installation_context']:[]};
  }};
  if(change==='none')assert.equal((await readInstallationContext(api,{current:()=>current})).source,'a'.repeat(40));
  else await assert.rejects(readInstallationContext(api,{current:()=>current}),e=>e.status===403);
  assert.deepEqual(calls,['/business/capabilities','/business/installation','/business/capabilities']);
 }
 const calls=[],api={generation:1,get:async p=>{calls.push(p);return {permissions:[],features:['installation_context']};}};
 await assert.rejects(readInstallationContext(api),e=>e.status===403);
 assert.deepEqual(calls,['/business/capabilities']);
});
