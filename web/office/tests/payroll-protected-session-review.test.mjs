import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {payrollFactValidator} from '../payroll-facts.js';
import {payrollEntitlementValidator} from '../payroll-entitlements.js';
import {payrollTravelTaxPolicyValidator} from '../payroll-travel-tax-policies.js';
import {payrollCalculationCaseValidator} from '../payroll-calculation-cases.js';

const copy=value=>structuredClone(value),fixture=name=>JSON.parse(readFileSync(new URL('../../../app/test/fixtures/'+name+'.json',import.meta.url),'utf8'));
const facts=fixture('payroll_facts'),claims=fixture('payroll_entitlements'),policy=fixture('payroll_travel_tax_policies'),composite=fixture('payroll_calculation_cases');
const cases=[
 {name:'P2 employment terms',path:'facts',feature:'payroll_period_facts',capability:'business_payroll_facts',body:facts.terms_command,result:facts.terms,sources:facts.sources,validator:payrollFactValidator,write:true},
 {name:'P2 period case',path:'facts',feature:'payroll_period_facts',capability:'business_payroll_facts',body:facts.command,result:facts.period,sources:facts.sources,preview:facts.preview,validator:payrollFactValidator},
 ...['sickness','vacation','unpaid'].map(name=>({name:'P4 '+name,path:'entitlements',feature:'payroll_entitlements',capability:'business_payroll_entitlements',body:claims[name].command,result:claims[name].saved,sources:claims[name].sources,preview:claims[name].preview,previous:claims[name].history.items[0],validator:payrollEntitlementValidator})),
 {name:'global employer policy',path:'travel-tax-policies',feature:'payroll_calculation_cases',capability:'business_payroll_calculation_cases',body:policy.body,result:policy.saved,sources:policy.sources,preview:policy.preview,validator:payrollTravelTaxPolicyValidator,global:true},
 {name:'Source3 calculation case',path:'calculation-cases',feature:'payroll_calculation_cases',capability:'business_payroll_calculation_cases',body:composite.command,result:composite.saved,sources:composite.sources,preview:composite.preview,validator:payrollCalculationCaseValidator},
];
function setup(c){
 const state={posts:[],gets:[],allowed:true,active:true,sources:copy(c.sources)},path='/business/payroll/'+c.path,key='payroll-'+c.path+(c.global?'':'-'+c.body.employee_id),body=copy(c.body);delete body.request_id;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET'){
   state.gets.push(url);
   if(url.includes('/capabilities'))return new Response(JSON.stringify({readonly:false,features:[c.feature],capabilities:[c.capability],permissions:['personnel.read',...(state.allowed?[c.write?'personnel.write':'personnel.approve']:[])],organization:{modules:{personnel:{enabled:state.active}}}}));
   assert.ok(url.endsWith(path+'/sources'+(c.global?'':'?employee_id='+body.employee_id+(c.path==='calculation-cases'?'&month='+body.details.month:''))));return new Response(JSON.stringify(state.sources));
  }
  state.posts.push(JSON.parse(options.body));if(state.posts.length===1)throw new Error('Synthetic original accepted acknowledgement lost');return new Response(JSON.stringify(c.result));
 }});api.setToken('synthetic-independent-protected-session-review');return{api,state,path,key,body};
}
for(const c of cases){
 test('actual OfficeApi '+c.name+' rejects an unrelated replay key without another POST',async()=>{
  const {api,state,path,body}=setup(c),key='unrelated-private-command';await assert.rejects(api.mutate(key,path,body,{validate:c.validator(body,c.previous??null,c.preview)}));state.allowed=false;
  await assert.rejects(api.retry(key),error=>[403,409].includes(error.status));assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,path),body);
 });
 test('actual OfficeApi '+c.name+' accepts exact authorized original after rights restoration and module pause',async()=>{
  const {api,state,path,key,body}=setup(c);await assert.rejects(api.mutate(key,path,body,{validate:c.validator(body,c.previous??null,c.preview)}));state.allowed=false;
  await assert.rejects(api.retry(key),error=>error.status===403);assert.equal(state.posts.length,1);assert.equal(api.pendingCount,1);
  state.allowed=true;state.sources[c.write?'can_write':'can_approve']=false;await assert.rejects(api.retry(key),error=>error.status===403);assert.equal(state.posts.length,1);
  state.sources[c.write?'can_write':'can_approve']=true;if(state.sources.employee)state.sources.employee.revision++;state.active=false;state.sources.writes_enabled=false;
  assert.deepEqual(await api.retry(key),c.result);assert.equal(api.pendingCount,0);assert.equal(state.posts.length,2);assert.deepEqual(state.posts[1],state.posts[0]);assert.match(state.posts[1].request_id,/^[a-f0-9]{32}$/);assert.ok(state.gets.some(url=>url.includes('/sources')));
 });
}
