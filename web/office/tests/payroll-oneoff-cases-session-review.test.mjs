import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {payrollOneOffCaseValidator} from '../payroll-oneoff-cases.js';
const fixture=JSON.parse(readFileSync(new URL('../../../docs/fixtures/payroll-oneoff-cases-2026.json',import.meta.url),'utf8'));
const clone=value=>structuredClone(value),id=fixture.saved.employee_id,path='/business/payroll/one-off-cases',key='payroll-oneoff-cases-'+id;
const body=()=>{const value=clone(fixture.command);delete value.request_id;return value;};
const response=value=>new Response(JSON.stringify(value));
const capabilities=()=>({features:['payroll_oneoff_cases'],capabilities:['business_payroll_oneoff_cases'],permissions:['personnel.read','personnel.approve'],readonly:false,organization:{modules:{personnel:{enabled:true}}}});
function harness({commandKey=key}={}){
 const posts=[],reads=[];let caps=capabilities(),sources=clone(fixture.sources),receipt=clone(fixture.saved);
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET'){reads.push(url);return response(url.endsWith('/capabilities')?caps:sources);}
  posts.push(JSON.parse(options.body));if(posts.length===1)throw new Error('Synthetic accepted response lost');return response(receipt);
 }});api.setToken('synthetic-oneoff-session-review');
 return {api,posts,reads,get caps(){return caps;},get sources(){return sources;},set receipt(value){receipt=value;},
  async lose(){const value=body();await assert.rejects(api.mutate(commandKey,path,value,{validate:payrollOneOffCaseValidator(value,null,fixture.preview)}));return value;}};
}

test('actual v6 OfficeApi retry requires current approval and exact source person/month, keeps original nonce through a pause',async()=>{
 const h=harness(),original=await h.lose();original.details.verification_note='Later editor draft';
 h.caps.permissions=['personnel.read'];await assert.rejects(h.api.retry(key),e=>e.status===403);
 h.caps.permissions.push('personnel.approve');h.sources.can_approve=false;await assert.rejects(h.api.retry(key),e=>e.status===403);
 h.sources.can_approve=true;h.sources.employee_id='f'.repeat(32);await assert.rejects(h.api.retry(key));h.sources.employee_id=id;
 h.sources.month='2026-11';await assert.rejects(h.api.retry(key));h.sources.month='2026-10';
 assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,1);
 h.caps.organization.modules.personnel.enabled=false;h.sources.writes_enabled=false;h.sources.employee.revision=99;
 assert.deepEqual(await h.api.retry(key),fixture.saved);assert.deepEqual(h.posts[1],h.posts[0]);assert.equal(h.api.pendingCount,0);
 assert.notEqual(h.posts[1].details.verification_note,original.details.verification_note);
});

test('actual v6 endpoint rejects unrelated pending keys before another POST',async()=>{
 const h=harness({commandKey:'unrelated-open-request'});await h.lose();
 await assert.rejects(h.api.retry('unrelated-open-request'),e=>[403,409].includes(e.status));
 assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,1);assert.equal(h.reads.length,0);
});

test('v6 keeps the original receipt validator when an unrelated valid saved record is returned',async()=>{
 const h=harness();await h.lose();h.receipt=clone(fixture.corrected);
 await assert.rejects(h.api.retry(key));assert.equal(h.api.pendingCount,1);
 h.receipt=clone(fixture.saved);assert.deepEqual(await h.api.retry(key),fixture.saved);
 assert.equal(h.posts.length,3);assert.deepEqual(h.posts[0],h.posts[1]);assert.deepEqual(h.posts[1],h.posts[2]);
});

test('replacing the session during fresh v6 authorization cannot send the old accepted request',async()=>{
 let release,entered,posts=0;const gate=new Promise(resolve=>release=resolve),started=new Promise(resolve=>entered=resolve);
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method!=='GET'){posts++;throw new Error('Synthetic accepted response lost');}
  entered();await gate;return response(url.endsWith('/capabilities')?capabilities():fixture.sources);
 }});api.setToken('synthetic-oneoff-old-session');const value=body();
 await assert.rejects(api.mutate(key,path,value,{validate:payrollOneOffCaseValidator(value,null,fixture.preview)}));
 const retry=api.retry(key);await started;api.setToken('synthetic-oneoff-new-session');release();
 await assert.rejects(retry);assert.equal(posts,1);assert.equal(api.pendingCount,0);
});
