import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {OfficeApi} from '../office.js';
import {payrollWageInterruptionValidator} from '../payroll-wage-interruptions.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_wage_interruptions.json',import.meta.url))),copy=v=>structuredClone(v);
const clean=v=>{const body=copy(v);delete body.request_id;return body;};
const employee=f.command.employee_id,commandKey='payroll-wage-interruptions-'+employee,path='/business/payroll/wage-interruptions';
function harness(){
 const state={approve:true,active:true,sources:copy(f.sources),result:copy(f.saved),lose:true,posts:[],gets:[]};
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET'){
   state.gets.push(url);
   if(url.includes('/capabilities'))return new Response(JSON.stringify({readonly:false,features:['payroll_wage_interruptions'],capabilities:['business_payroll_wage_interruptions'],permissions:['personnel.read',...(state.approve?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:state.active}}}}));
   assert.ok(url.endsWith('/business/payroll/wage-interruptions/sources?employee_id='+employee+'&year=2026'));return new Response(JSON.stringify(state.sources));
  }
  state.posts.push(JSON.parse(options.body));
  if(state.lose){state.lose=false;throw new Error('Synthetic response lost after original U command accepted');}
  return new Response(JSON.stringify(state.result));
 }});api.setToken('synthetic-u-independent-session-review');return {api,state};
}
async function begin(api,key=commandKey){const body=clean(f.command);await assert.rejects(api.mutate(key,path,body,{validate:payrollWageInterruptionValidator(body,null,f.preview)}));assert.equal(api.pendingCount,1);return body;}

test('actual OfficeApi U hook preserves exact original across fresh approve withdrawal and later source revisions',async()=>{
 const {api,state}=harness(),body=await begin(api);body.details.verification_note='Later editor contents must never replace accepted original';
 state.approve=false;await assert.rejects(api.retry(commandKey),e=>e.status===403);assert.equal(state.posts.length,1);assert.ok(state.gets.some(v=>v.includes('/capabilities')));
 state.approve=true;state.sources.can_approve=false;await assert.rejects(api.retry(commandKey),e=>e.status===403);assert.equal(state.posts.length,1);
 state.sources.can_approve=true;state.sources.employee.revision++;state.sources.assessments=[copy(f.corrected)];state.active=false;state.sources.writes_enabled=false;
 assert.deepEqual(await api.retry(commandKey),f.saved);assert.equal(api.pendingCount,0);assert.equal(state.posts.length,2);assert.deepEqual(state.posts[1],state.posts[0]);assert.equal(state.posts[1].details.verification_note,f.command.details.verification_note);assert.match(state.posts[1].request_id,/^[a-f0-9]{32}$/);
});
test('actual OfficeApi U hook refuses wrong source person or year and edited pending year without a second POST',async()=>{
 const {api,state}=harness();await begin(api);
 state.sources.employee_id='f'.repeat(32);await assert.rejects(api.retry(commandKey));assert.equal(state.posts.length,1);
 state.sources=copy(f.sources);state.sources.year=2025;await assert.rejects(api.retry(commandKey));assert.equal(state.posts.length,1);
 state.sources=copy(f.sources);const changed=api.pendingCommandValues(commandKey,path);changed.details.year=2025;
 await assert.rejects(api.mutate(commandKey,path,changed));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
 await api.retry(commandKey);assert.deepEqual(state.posts[0],state.posts[1]);
});
test('actual OfficeApi U replay keeps receipt validator and pending nonce when response changes person or year',async()=>{
 const {api,state}=harness();await begin(api);
 state.result.employee_id='f'.repeat(32);await assert.rejects(api.retry(commandKey));assert.equal(api.pendingCount,1);
 state.result=copy(f.saved);state.result.details.year=2025;await assert.rejects(api.retry(commandKey));assert.equal(api.pendingCount,1);
 state.result=copy(f.saved);await api.retry(commandKey);assert.equal(api.pendingCount,0);assert.equal(new Set(state.posts.map(p=>p.request_id)).size,1);for(const p of state.posts)assert.deepEqual(p,state.posts[0]);
});
test('actual OfficeApi U path cannot bypass fresh scope guard through a malformed command key',async()=>{
 const {api,state}=harness(),wrong='unrelated-private-command';await begin(api,wrong);state.approve=false;
 await assert.rejects(api.retry(wrong));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
});
test('actual OfficeApi U path refuses a valid-shaped command key for another employee',async()=>{
 const {api,state}=harness(),wrong='payroll-wage-interruptions-'+'f'.repeat(32);await begin(api,wrong);
 await assert.rejects(api.retry(wrong));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
});
