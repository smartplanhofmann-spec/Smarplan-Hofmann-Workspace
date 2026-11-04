import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {OfficeApi, StaleSession} from '../office.js';

const path='/business/company-events/scan';
const caps={readonly:false,features:['company_event_rules'],capabilities:['business_company_events'],permissions:['assistant.use','settings.manage']};
const canonical=value=>JSON.stringify(Array.isArray(value)?value.map(ordered):ordered(value));
function ordered(value){return Array.isArray(value)?value.map(ordered):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,ordered(value[k])])):value;}
const receipt=body=>({acceptance:{request_id:body.request_id,operation:'scan',request_hash:createHash('sha256').update(canonical(['scan',body])).digest('hex')}});
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};
const response=value=>new Response(JSON.stringify(value),{status:200,headers:{'content-type':'application/json'}});

test('original generated request id reaches async receipt validation; foreign valid acceptance preserves pending',async()=>{
  const posts=[];let foreign=true;
  const api=new OfficeApi({fetcher:async(_url,options)=>{if(!options.body)return response(caps);const body=JSON.parse(options.body);posts.push(body);return response(receipt(foreign?{...body,request_id:'a'.repeat(32)}:body));}});
  api.setToken('independent-company-session-token');
  const validate=async(value,original)=>{await Promise.resolve();assert.equal(original.request_id,posts[0].request_id);assert.deepEqual(value,receipt(original),'foreign receipt must not confirm original request');};
  await assert.rejects(api.mutate('company-event-scan',path,{after:null,limit:100},{validate}),/foreign receipt/);
  assert.equal(api.pendingCount,1);
  foreign=false;
  await api.retry('company-event-scan');
  assert.deepEqual(posts[1],posts[0]);
  assert.equal(api.pendingCount,0);
});

test('validator gets isolated original-body copy; validator mutation cannot change later exact replay',async()=>{
  const posts=[];let first=true;
  const api=new OfficeApi({fetcher:async(_url,options)=>{if(!options.body)return response(caps);const body=JSON.parse(options.body);posts.push(body);return response(receipt(body));}});
  api.setToken('independent-company-isolated-body-token');
  const validate=async(value,original)=>{assert.deepEqual(value,receipt(original));if(first){first=false;original.limit=1;original.request_id='b'.repeat(32);throw new Error('local verification not complete');}};
  await assert.rejects(api.mutate('company-event-scan',path,{after:null,limit:100},{validate}),/not complete/);
  await api.retry('company-event-scan');
  assert.equal(posts[1].limit,100);assert.deepEqual(posts[1],posts[0]);assert.equal(api.pendingCount,0);
});

test('late async validator cannot clear new-session operation with same key or receive its body',async()=>{
  const first=deferred(),second=deferred(),enteredFirst=deferred(),enteredSecond=deferred(),bodies=[];
  const api=new OfficeApi({fetcher:async(_url,options)=>response(options.body?receipt(JSON.parse(options.body)):caps)});
  api.setToken('independent-old-company-session');
  const old=api.mutate('company-event-scan',path,{after:null,limit:1},{validate:async(value,body)=>{bodies.push(body);enteredFirst.resolve();await first.promise;assert.deepEqual(value,receipt(body));}});
  const oldFailure=assert.rejects(old,StaleSession);
  await enteredFirst.promise;
  api.setToken('independent-new-company-session');
  const current=api.mutate('company-event-scan',path,{after:null,limit:2},{validate:async(value,body)=>{bodies.push(body);enteredSecond.resolve();await second.promise;assert.deepEqual(value,receipt(body));}});
  await enteredSecond.promise;
  first.resolve();await oldFailure;
  assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues('company-event-scan',path),{after:null,limit:2});
  assert.equal(bodies[0].limit,1);assert.equal(bodies[1].limit,2);assert.notEqual(bodies[0].request_id,bodies[1].request_id);
  second.resolve();await current;assert.equal(api.pendingCount,0);
});

test('existing synchronous result-only validator still accepts and rejects without clearing failed operation',async()=>{
  let good=false;
  const api=new OfficeApi({fetcher:async()=>response({accepted:good})});api.setToken('independent-company-sync-validator');
  await assert.rejects(api.mutate('legacy-sync','/business/legacy-unit-test',{value:1},{validate:value=>{if(!value.accepted)throw new Error('unconfirmed legacy result');}}),/unconfirmed/);
  assert.equal(api.pendingCount,1);good=true;await api.retry('legacy-sync');assert.equal(api.pendingCount,0);
});
