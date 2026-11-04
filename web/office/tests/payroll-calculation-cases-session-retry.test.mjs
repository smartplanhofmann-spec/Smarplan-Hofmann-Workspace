import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_calculation_cases.json',import.meta.url),'utf8'));
test('actual OfficeApi source3 original remains exact through fresh rights and paused module',async()=>{
 const employee=fixture.command.employee_id,key='payroll-calculation-cases-'+employee,posts=[];
 let rights=true,sourceRights=true,sourceEmployee=employee,sourceMonth='2026-10',active=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?{
   readonly:false,features:['payroll_calculation_cases'],capabilities:['business_payroll_calculation_cases'],permissions:['personnel.read',...(rights?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:active}}},
  }:{...structuredClone(fixture.sources),employee_id:sourceEmployee,month:sourceMonth,can_approve:sourceRights,writes_enabled:active}));
  posts.push(JSON.parse(options.body));if(posts.length===1)throw new Error('Synthetic accepted response lost');return new Response(JSON.stringify(fixture.saved));
 }});api.setToken('synthetic-case-retry');
 const body=structuredClone(fixture.command);delete body.request_id;
 await assert.rejects(api.mutate(key,'/business/payroll/calculation-cases',body));
 body.details.verification_note='Later editor text';rights=false;
 await assert.rejects(api.retry(key),e=>e.status===403);rights=true;sourceRights=false;
 await assert.rejects(api.retry(key),e=>e.status===403);sourceRights=true;sourceEmployee='f'.repeat(32);
 await assert.rejects(api.retry(key));sourceEmployee=employee;sourceMonth='2026-11';
 await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 sourceMonth='2026-10';active=false;await api.retry(key);
 assert.equal(posts.length,2);assert.deepEqual(posts[0],posts[1]);assert.equal(api.pendingCount,0);
});
test('actual OfficeApi source3 endpoint cannot bypass its fresh guard with an unrelated pending key',async()=>{
 let posts=0;const api=new OfficeApi({fetcher:async()=>{posts++;throw new Error('Synthetic original response lost');}});api.setToken('synthetic-case-unknown-key');
 const body=structuredClone(fixture.command);delete body.request_id;
 await assert.rejects(api.mutate('unrelated-case-command','/business/payroll/calculation-cases',body));
 await assert.rejects(api.retry('unrelated-case-command'),error=>error.status===409);
 assert.equal(posts,1);assert.equal(api.pendingCount,1);
});
