import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {PAYROLL_FACTOR_TRANSITION_RULE,verifyFactorTransitionCase,verifyFactorTransitionRun} from '../payroll-factor-transition.js';
import {payrollCalculationCaseSources,payrollCalculationCaseInput,payrollCalculationCasePreview,payrollCalculationCaseValidator,payrollCalculationCaseRunInput,payrollCompositeSource} from '../payroll-calculation-cases.js';
import {payrollPreview,payrollRunValidator} from '../payroll.js';
globalThis.crypto??=webcrypto;
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_factor_transition.json',import.meta.url),'utf8'));
const id=f.employee.id,copy=structuredClone,clean=v=>Object.fromEntries(Object.entries(copy(v)).filter(([k])=>k!=='request_id'));
const values=()=>{const d=f.case_input.details;return{month:d.month,rule_version:PAYROLL_FACTOR_TRANSITION_RULE,
 period_case_id:d.period_case_ref.id,employment_terms_ids:d.employment_terms_refs.map(v=>v.id),
 profile_ids:d.profile_refs.map(v=>v.id),identity_ids:d.identity_refs.map(v=>v.id),source_file_ids:f.case_input.source_file_ids,
 factor_transition_assessment:copy(d.factor_transition_assessment),verification_note:d.verification_note};};

test('actual API originals, command, case, financial projection and run stay independently bound',async()=>{
 payrollCalculationCaseSources(f.sources_before,id,'2026-10');
 const body=payrollCalculationCaseInput(id,f.sources_before,values());
 assert.deepEqual({...body,preview_hash:f.case_preview.preview_hash},clean(f.case_command));
 await payrollCalculationCasePreview(f.case_preview,body);
 await payrollCalculationCaseValidator(clean(f.case_command),null,f.case_preview)(f.case);
 assert.deepEqual(payrollCalculationCaseRunInput(f.case),f.run_input);
 payrollCompositeSource(f.run_preview,f.run_input);
 await payrollPreview(f.run_preview,f.run_input);
 await payrollRunValidator(clean(f.run_command),f.run_preview)(f.run);
 assert.equal(f.run.calculation.individual_wage_tax_minor,6633);
 assert.equal(f.run.calculation.employee_social_total_minor,43500);
 assert.equal(f.run.calculation.net_minor,149867);
 assert.equal(f.case.sources.profiles[0].profile.transition_assessment,undefined);
});

test('missing prognosis, other requested movements and partial period are rejected before submission',()=>{
 for(const mutate of [v=>v.source_file_ids=[],v=>v.profile_ids=[],v=>v.segment_events=[{}],
  v=>v.entitlement_case_ids=[id],v=>v.travel_settlement_ids=[id],v=>v.factor_transition_assessment.employee_id='f'.repeat(32),
  v=>v.factor_transition_assessment.transition_assessment.forecast_months=11,
  v=>v.factor_transition_assessment.forecast_evidence_ref.content_hash='f'.repeat(64)]){
  const v=values();mutate(v);assert.throws(()=>payrollCalculationCaseInput(id,f.sources_before,v));
 }
 const s=copy(f.sources_before);s.factor_period_facts[0].plan.social_periods[0].full_month=false;
 assert.throws(()=>payrollCalculationCaseInput(id,s,values()));
});

test('complete case hashes detect original factor, forecast, plan or contribution substitution',async()=>{
 for(const mutate of [v=>v.sources.factor_transition_assessment.transition_assessment.note+=' changed',
  v=>v.plan.gross_minor++,v=>v.plan.factor_parameters.tax_factor='0.900',
  v=>v.plan.factor_transition_component.factor_transition_components.contribution_profile.special_cases.push('other_special_case'),
  v=>v.plan.factor_transition_component.individual_wage_tax_minor++,v=>v.preview_hash='f'.repeat(64)]){
  const v=copy(f.case);mutate(v);await assert.rejects(verifyFactorTransitionCase(v));
 }
});

test('a run cannot substitute the actual original profile or confirmed financial component',async()=>{
 for(const mutate of [v=>v.calculation.net_minor++,v=>v.source.profile.profile.tax_factor='0.900',
  v=>v.calculation.factor_transition_components.contribution_financials.employee_social_total_minor++,
  v=>v.calculation.period_details.factor_transition_assessment.transition_assessment.forecast_months=11]){
  const v=copy(f.run);mutate(v);await assert.rejects(verifyFactorTransitionRun(v));
 }
});

for(const run of [false,true])test(`actual original ${run?'run':'case'} survives lost reply and refuses revoked feature or approval`,async()=>{
 const {OfficeApi}=await import('../office.js');let feature=true,approve=true,lost=true;const posts=[];
 const caps=()=>({readonly:false,features:['german_payroll_2026','payroll_calculation_cases',...(feature?['payroll_factor_transition']:[])],
  capabilities:['business_payroll','business_payroll_calculation_cases'],permissions:['personnel.read',...(approve?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:true}}}});
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted reply lost');}return Response.json(run?f.run:f.case);}
  return Response.json(url.includes('/capabilities')?caps():url.includes('/sources?')?{...f.sources_after,can_approve:approve}:{employee_id:id,items:[f.run]});
 }});
 api.setToken('synthetic-factor-midijob-browser-token');
 const body=clean(run?f.run_command:f.case_command),key=(run?'payroll-run-':'payroll-calculation-cases-')+id,path=run?'/business/payroll/runs':'/business/payroll/calculation-cases';
 await assert.rejects(api.mutate(key,path,body,{validate:run?payrollRunValidator(body,f.run_preview):payrollCalculationCaseValidator(body,null,f.case_preview)}));
 feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 feature=true;approve=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 approve=true;await api.retry(key);assert.deepEqual(posts[1],posts[0]);assert.equal(api.pendingCount,0);
});
