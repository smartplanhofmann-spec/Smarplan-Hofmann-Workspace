import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {OfficeApi} from '../office.js';
import {payrollAnnualValidator} from '../payroll-annual-basis.js';

const fixtures=JSON.parse(fs.readFileSync(new URL('../../../docs/fixtures/payroll-annual-basis-2026.json',import.meta.url))).cases,copy=v=>structuredClone(v);
const clean=v=>{const body=copy(v);delete body.request_id;return body;};
const path='/business/payroll/annual-facts';
function harness(f){
 const employee=f.command.employee_id,key='payroll-annual-basis-'+employee;
 const state={approve:true,active:true,sources:copy(f.sources),result:copy(f.saved),lose:true,posts:[],gets:[]};
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET'){
   state.gets.push(url);
   if(url.includes('/capabilities'))return new Response(JSON.stringify({readonly:false,features:['payroll_annual_basis'],capabilities:['business_payroll_annual_basis'],permissions:['personnel.read',...(state.approve?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:state.active}}}}));
   assert.ok(url.endsWith('/business/payroll/annual-facts/sources?employee_id='+employee));return new Response(JSON.stringify(state.sources));
  }
  state.posts.push(JSON.parse(options.body));if(state.lose){state.lose=false;throw new Error('Synthetic response lost after original annual command accepted');}
  return new Response(JSON.stringify(state.result));
 }});api.setToken('synthetic-annual-independent-session-review');return{api,state,key,employee};
}
async function begin(api,f,key){const body=clean(f.command);await assert.rejects(api.mutate(key,path,body,{validate:payrollAnnualValidator(body,null,f.preview)}));assert.equal(api.pendingCount,1);return body;}

for(const f of fixtures)test('actual OfficeApi '+f.command.kind+' guard requires current approval and preserves nonce after module pause',async()=>{
 const {api,state,key}=harness(f),body=await begin(api,f,key);body.details.verification_note='Later editor text';
 state.approve=false;await assert.rejects(api.retry(key),e=>e.status===403);assert.equal(state.posts.length,1);assert.ok(state.gets.some(v=>v.includes('/capabilities')));
 state.approve=true;state.sources.can_approve=false;await assert.rejects(api.retry(key),e=>e.status===403);assert.equal(state.posts.length,1);
 // These later sources are real generated annual facts; the employee revision may also advance.
 state.sources=copy(fixtures.at(-1).sources);state.sources.employee.revision++;state.sources.writes_enabled=false;state.active=false;
 assert.deepEqual(await api.retry(key),f.saved);assert.equal(api.pendingCount,0);assert.equal(state.posts.length,2);assert.deepEqual(state.posts[1],state.posts[0]);assert.equal(state.posts[1].details.verification_note,f.command.details.verification_note);
});
test('actual OfficeApi annual hook refuses other employee sources and an edited pending year without another POST',async()=>{
 const f=fixtures.find(v=>v.command.kind==='annual_basis'),{api,state,key}=harness(f);await begin(api,f,key);
 state.sources.employee_id='f'.repeat(32);await assert.rejects(api.retry(key));assert.equal(state.posts.length,1);
 state.sources=copy(f.sources);const changed=api.pendingCommandValues(key,path);changed.details.year=2025;
 await assert.rejects(api.mutate(key,path,changed));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
 await api.retry(key);assert.deepEqual(state.posts[1],state.posts[0]);
});
test('actual OfficeApi annual replay retains original result validator for wrong employee or year responses',async()=>{
 const f=fixtures.find(v=>v.command.kind==='annual_basis'),{api,state,key}=harness(f);await begin(api,f,key);
 state.result.employee_id='f'.repeat(32);await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);
 state.result=copy(f.saved);state.result.details.year=2025;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);
 state.result=copy(f.saved);await api.retry(key);assert.equal(new Set(state.posts.map(v=>v.request_id)).size,1);for(const p of state.posts)assert.deepEqual(p,state.posts[0]);assert.equal(api.pendingCount,0);
});
test('actual OfficeApi annual path cannot bypass its fresh guard through an unrelated command key',async()=>{
 const f=fixtures[0],{api,state}=harness(f),wrong='unrelated-annual-command';await begin(api,f,wrong);state.approve=false;
 await assert.rejects(api.retry(wrong));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
});
test('actual OfficeApi annual path rejects a valid-shaped key belonging to another person',async()=>{
 const f=fixtures[0],{api,state}=harness(f),wrong='payroll-annual-basis-'+'f'.repeat(32);await begin(api,f,wrong);
 await assert.rejects(api.retry(wrong));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
});
