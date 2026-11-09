import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {PAYROLL_FACTOR_TRAVEL_RULE,PAYROLL_FACTOR_TRAVEL_FEATURE,payrollCalculationCaseInput,payrollCalculationCaseSources,payrollCalculationCasePreview,payrollCalculationCaseValidator,payrollCalculationCaseRunInput,payrollCompositeCalculation,payrollCompositeSource} from '../payroll-calculation-cases.js';
import {payrollCalculation,payrollPreview,payrollRunValidator,payrollLedger} from '../payroll.js';

const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_factor_travel.json',import.meta.url),'utf8'));
const copy=v=>structuredClone(v),id=f.employee_id,month=f.command.details.month;
const clean=v=>{const value=copy(v);delete value.request_id;return value;};
const values=()=>{const d=f.command.details;return{rule_version:PAYROLL_FACTOR_TRAVEL_RULE,month,period_case_id:d.period_case_ref.id,employment_terms_ids:d.employment_terms_refs.map(v=>v.id),profile_ids:d.profile_refs.map(v=>v.id),identity_ids:d.identity_refs.map(v=>v.id),entitlement_case_ids:[],travel_settlement_ids:d.travel_settlement_refs.map(v=>v.id),travel_payment_ids:d.travel_payment_refs.map(v=>v.id),segment_events:[],thirty_day_rule:null,policy_id:null,source_file_ids:copy(f.command.source_file_ids),verification_note:d.verification_note};};

test('actual factor travel source3 command, immutable record and run preserve the v9 net',async()=>{
 payrollCalculationCaseSources(f.sources,id,month);
 const body=payrollCalculationCaseInput(id,f.sources,values());
 assert.deepEqual({...body,preview_hash:f.preview.preview_hash},clean(f.command));
 payrollCalculationCasePreview(f.preview,body);
 payrollCalculationCaseValidator(clean(f.command),null,f.preview)(f.saved);
 assert.deepEqual(payrollCalculationCaseRunInput(f.saved),f.run_input);
 payrollCompositeSource(f.run_preview,f.run_input);payrollCompositeCalculation(f.run.calculation);
 payrollCalculation(f.run.calculation);payrollPreview(f.run_preview,f.run_input);
 payrollRunValidator(clean(f.run_command),f.run_preview)(f.run);
 await payrollLedger(f.ledger,id,2026);
 for(const field of ['gross_minor','net_minor','payout_minor','employee_social_total_minor','employer_social_total_minor','individual_wage_tax_minor','solidarity_minor','church_tax_minor'])assert.deepEqual(f.run.calculation[field],f.v9_base_calculation[field],field);
 assert.equal(f.run.calculation.travel_expenses_included_in_net,false);
 assert.equal(f.run.calculation.net_deductions_minor,0);
 assert.equal(f.run.calculation.period_details.travel_paid_minor,1400);
});

test('new source selection rejects incomplete payment lists, old rule substitution and extra claims',()=>{
 for(const change of [v=>v.travel_payment_ids=[],v=>v.period_case_id=f.command.details.employment_terms_refs[0].id,v=>v.entitlement_case_ids=[f.command.details.employment_terms_refs[0].id],v=>v.policy_id='a'.repeat(32),v=>v.thirty_day_rule='actual_days_capped_per_claim']){
  const v=values();change(v);assert.throws(()=>payrollCalculationCaseInput(id,f.sources,v));
 }
 const partial=copy(f.sources);partial.factor_period_facts[0].plan.social_periods[0].full_month=false;
 assert.throws(()=>payrollCalculationCaseInput(id,partial,values()));
 const excessive=copy(f.sources);excessive.travel_payment_proofs[0].account_id='a'.repeat(32);
 assert.throws(()=>payrollCalculationCaseSources(excessive,id,month));
});

test('actual factor correction retains original travel payment references and both historical payroll versions',()=>{
 const command=f.correction_case_command,d=command.details;
 const v={...values(),period_case_id:d.period_case_ref.id,employment_terms_ids:d.employment_terms_refs.map(ref=>ref.id),profile_ids:d.profile_refs.map(ref=>ref.id),identity_ids:d.identity_refs.map(ref=>ref.id),travel_payment_ids:d.travel_payment_refs.map(ref=>ref.id),verification_note:d.verification_note,correction_reason:command.correction_reason};
 const body=payrollCalculationCaseInput(id,f.correction_sources,v,f.saved);
 assert.deepEqual({...body,preview_hash:f.correction_case_preview.preview_hash},clean(command));
 payrollCalculationCasePreview(f.correction_case_preview,body);
 payrollCalculationCaseValidator(clean(command),f.saved,f.correction_case_preview)(f.correction_case);
 payrollCompositeCalculation(f.correction_run.calculation);
 assert.deepEqual(f.correction_case.details.travel_payment_refs,f.saved.details.travel_payment_refs);
 assert.equal(f.saved.plan.factor_parameters.tax_factor,'0.753');
 assert.equal(f.correction_case.plan.factor_parameters.tax_factor,'0.900');
 assert.equal(f.correction_run.calculation.period_details.travel_paid_minor,1400);
 assert.equal(f.correction_run.calculation.net_deductions_minor,0);
 assert.equal(f.correction_run.previous_hash,f.run.content_hash);
});

test('historical factor travel proofs reject altered payments, paid totals, factor and scope',()=>{
 for(const change of [
  v=>v.sources.travel_sources[0].payment_proof.paid_minor++,
  v=>v.sources.travel_sources[0].payment_proof.payments[0].content_hash='0'.repeat(64),
  v=>v.sources.travel_sources[0].payment_proof.payments[0].cash_source_hash='invalid',
  v=>v.sources.travel_sources[0].letter_m=true,
  v=>v.sources.travel_sources[0].individual_taxable_payroll_minor=1,
  v=>v.plan.factor_parameters.tax_factor='0.900',
  v=>v.source_contract_version=1,
 ]){const saved=copy(f.saved);change(saved);assert.throws(()=>payrollCalculationCaseValidator(clean(f.command),null,f.preview)(saved));}
 for(const change of [v=>v.net_minor+=1400,v=>v.payout_minor+=1400,v=>v.scope='regular_standard_segments',v=>v.period_details.travel_paid_minor++,v=>v.period_details.factor_parameters.tax_factor='0.900']){
  const calc=copy(f.run.calculation);change(calc);assert.throws(()=>payrollCompositeCalculation(calc));
 }
});

test('accepted factor travel case repeats the exact original after fresh authorization and lost response',async()=>{
 const body=clean(f.command),key='payroll-calculation-cases-'+id,path='/business/payroll/calculation-cases',posts=[];
 let lost=true,allowed=true,feature=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted answer lost');}return Response.json(f.saved);}
  return Response.json(url.includes('/capabilities')?{readonly:false,features:['payroll_calculation_cases',...(feature?[PAYROLL_FACTOR_TRAVEL_FEATURE]:[])],capabilities:['business_payroll_calculation_cases'],permissions:['personnel.read',...(allowed?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:true}}}}:f.sources);
 }});api.setToken('synthetic-factor-travel-browser-token');
 await assert.rejects(api.mutate(key,path,body,{validate:payrollCalculationCaseValidator(body,null,f.preview)}));
 allowed=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 allowed=true;feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 feature=true;await api.retry(key);assert.deepEqual(posts[1],posts[0]);assert.equal(api.pendingCount,0);
});

test('closing the factor-travel retry context during its inner source check sends no second command',async()=>{
 const key='payroll-calculation-cases-'+id,path='/business/payroll/calculation-cases',body=clean(f.command),posts=[];
 let closed=false,closeDuringRead=false;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));throw new Error('Synthetic accepted reply lost');}
  if(url.includes('/capabilities'))return Response.json({readonly:false,features:['payroll_calculation_cases',PAYROLL_FACTOR_TRAVEL_FEATURE],capabilities:['business_payroll_calculation_cases'],permissions:['personnel.read','personnel.approve'],organization:{modules:{personnel:{enabled:true}}}});
  if(closeDuringRead)closed=true;
  return Response.json(f.sources);
 }});api.setToken('synthetic-factor-travel-context-token');
 await assert.rejects(api.mutate(key,path,body));closeDuringRead=true;
 await assert.rejects(api.retry(key,{stillCurrent:()=>!closed}));
 assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 assert.deepEqual(api.pendingCommandValues(key,path),body);
});

test('the original final payroll also requires its feature before an unchanged retry',async()=>{
 const body=clean(f.run_command),path='/business/payroll/runs',key='payroll-run-'+id,posts=[];
 let lost=true,feature=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted payroll reply lost');}return Response.json(f.run);}
  return Response.json(url.includes('/capabilities')?{readonly:false,features:['german_payroll_2026',...(feature?[PAYROLL_FACTOR_TRAVEL_FEATURE]:[])],capabilities:['business_payroll'],permissions:['personnel.read','personnel.approve'],organization:{modules:{personnel:{enabled:true}}}}:{employee_id:id,items:[f.run]});
 }});api.setToken('synthetic-factor-travel-run-token');
 await assert.rejects(api.mutate(key,path,body,{validate:payrollRunValidator(body,f.run_preview)}));
 feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 feature=true;await api.retry(key);assert.deepEqual(posts[0],posts[1]);assert.equal(api.pendingCount,0);
});
