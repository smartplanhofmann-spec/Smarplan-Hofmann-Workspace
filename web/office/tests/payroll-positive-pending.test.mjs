import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,copy} from './source5-positive-fixture.mjs';
import {OfficeApi} from '../office.js';
import {payrollRunValidator} from '../payroll.js';
import {accountReceiptValidator} from '../payroll-accounts.js';

const s=fixture.correction,response=value=>new Response(JSON.stringify(value));
function capabilities(){return{features:['german_payroll_2026','payroll_wage_account','payroll_source5_positive_corrections'],capabilities:['business_payroll','business_payroll_accounts'],permissions:['personnel.read','personnel.approve'],readonly:false};}
function host(kind){
  let caps=capabilities(),result=copy(kind==='run'?s.run:s.payment);const posts=[];
  const path=kind==='run'?'/business/payroll/runs':'/business/payroll/account-records';
  const key=(kind==='run'?'payroll-run-':'payroll-account-')+s.employee.id;
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET'){
      if(url.endsWith('/capabilities'))return response(caps);
      if(url.includes('/payroll/runs?'))return response({employee_id:s.employee.id,items:[s.run]});
      if(url.includes('/payroll/account-records?'))return response({employee_id:s.employee.id,items:[s.prior_payment]});
      throw new Error('Unexpected read '+url);
    }
    posts.push(JSON.parse(options.body));if(posts.length===1)throw new Error('Synthetic accepted response lost');
    return response(result);
  }});api.setToken('synthetic-positive-correction-private-session');
  return{api,posts,path,key,get caps(){return caps;},set caps(value){caps=value;},set result(value){result=value;}};
}

test('new run retry preserves its exact completeness review and transition proof through lost and invalid replies',async()=>{
  const h=host('run'),body=copy(s.run_command);delete body.request_id;
  await assert.rejects(h.api.mutate(h.key,h.path,body,{validate:payrollRunValidator(body,s.run_preview,s.prior_run)}));
  body.settlement_review.payments_complete=false;
  h.caps.permissions=['personnel.read'];await assert.rejects(h.api.retry(h.key));assert.equal(h.posts.length,1);
  h.caps=capabilities();h.caps.features=h.caps.features.filter(v=>v!=='payroll_source5_positive_corrections');
  await assert.rejects(h.api.retry(h.key));assert.equal(h.posts.length,1);
  h.caps=capabilities();const wrong=copy(s.run);wrong.settlement_transition.additional_net_minor++;h.result=wrong;
  await assert.rejects(h.api.retry(h.key));assert.equal(h.api.pendingCount,1);
  h.result=copy(s.run);assert.deepEqual(await h.api.retry(h.key),s.run);
  assert.deepEqual(h.posts[0],h.posts[1]);assert.deepEqual(h.posts[0],h.posts[2]);
  assert.equal(h.posts[0].settlement_review.payments_complete,true);assert.equal(h.api.pendingCount,0);
});

test('new payment retry preserves every old allocation and refuses changed receipt data or missing current feature',async()=>{
  const h=host('payment'),body=copy(s.payment_command);delete body.request_id;
  await assert.rejects(h.api.mutate(h.key,h.path,body,{validate:accountReceiptValidator(body,s.payment.source_file,null,s.payment.sources)}));
  body.details.settlement_allocations[1].one_off_allocations[0].net_minor=1;
  h.caps.features=h.caps.features.filter(v=>v!=='payroll_source5_positive_corrections');
  await assert.rejects(h.api.retry(h.key));assert.equal(h.posts.length,1);
  h.caps=capabilities();const wrong=copy(s.payment);wrong.sources.single_payment_plan.transition_hash='0'.repeat(64);h.result=wrong;
  await assert.rejects(h.api.retry(h.key));assert.equal(h.api.pendingCount,1);
  h.result=copy(s.payment);assert.deepEqual(await h.api.retry(h.key),s.payment);
  assert.deepEqual(h.posts[0],h.posts[1]);assert.deepEqual(h.posts[0],h.posts[2]);
  assert.deepEqual(h.posts[0].details,s.payment.details);assert.equal(h.api.pendingCount,0);
});
