import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {payrollCalculationCaseSources,payrollCalculationCaseInput,payrollCalculationCasePreview,payrollCalculationCaseValidator,payrollCalculationCaseRunInput,payrollCompositeSource} from '../payroll-calculation-cases.js';
import {payrollPreview,payrollRunValidator} from '../payroll.js';
import {PAYROLL_FACTOR_CLAIMS_RULE,FACTOR_CLAIMS_CARE_METHOD,verifyFactorClaimsCase,verifyFactorClaimsRun} from '../payroll-factor-claims.js';
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_factor_claims.json',import.meta.url),'utf8'));
const id=f.employee.id,copy=v=>structuredClone(v),clean=v=>Object.fromEntries(Object.entries(copy(v)).filter(([k])=>k!=='request_id'));
const values=()=>{const d=f.case_command.details;return {rule_version:PAYROLL_FACTOR_CLAIMS_RULE,month:d.month,period_case_id:d.period_case_ref.id,employment_terms_ids:d.employment_terms_refs.map(r=>r.id),profile_ids:d.profile_refs.map(r=>r.id),identity_ids:d.identity_refs.map(r=>r.id),entitlement_case_ids:d.entitlement_case_refs.map(r=>r.id),source_file_ids:f.case_command.source_file_ids,segment_events:[],travel_settlement_ids:[],verification_note:d.verification_note};};
test('actual accepted factor/P4 sources, command, plan and run independently bind all original hashes',async()=>{
 payrollCalculationCaseSources(f.sources,id,'2026-10');
 const body=payrollCalculationCaseInput(id,f.sources,values());
 assert.deepEqual({...body,preview_hash:f.case_preview.preview_hash},clean(f.case_command));
 await payrollCalculationCasePreview(f.case_preview,body);
 await payrollCalculationCaseValidator(clean(f.case_command),null,f.case_preview)(f.case);
 assert.deepEqual(payrollCalculationCaseRunInput(f.case),f.run_input);
 payrollCompositeSource(f.run_preview,f.run_input);
 await payrollPreview(f.run_preview,f.run_input);
 await payrollRunValidator(clean(f.run_command),f.run_preview)(f.run);
 assert.equal(f.run.calculation.individual_wage_tax_minor,43091);
 assert.equal(f.run.calculation.employee_contributions.care,10064);
 assert.equal(f.run.calculation.net_minor,285054);
 assert.equal(f.case.plan.care_contribution_method,FACTOR_CLAIMS_CARE_METHOD);
});
test('source selection rejects omitted claims, duplicate originals, partial month and additional travel',()=>{
 for(const alter of [v=>v.entitlement_case_ids=[],v=>v.entitlement_case_ids.push(v.entitlement_case_ids[0]),v=>v.travel_settlement_ids=[f.claim.id],v=>v.thirty_day_rule='actual_days_capped_per_claim',v=>v.source_file_ids=[],v=>v.period_case_id=f.claim.id]){
  const v=values();alter(v);assert.throws(()=>payrollCalculationCaseInput(id,f.sources,v));
 }
 const s=copy(f.sources);s.factor_period_facts[0].plan.social_periods[0].full_month=false;
 assert.throws(()=>payrollCalculationCaseInput(id,s,values()));
});
test('independent hash verification rejects genuine-shaped altered sources, plans and receipts',async()=>{
 for(const alter of [v=>v.sources.entitlements[0].details.verification_note+=' changed',v=>v.plan.gross_minor++,v=>v.plan.factor_parameters.tax_factor='0.900',v=>v.plan.care_contribution_method='ONE_STEP',v=>v.plan.plan_hash='0'.repeat(64),v=>v.preview_hash='1'.repeat(64)]){
  const v=copy(f.case);alter(v);await assert.rejects(verifyFactorClaimsCase(v));
 }
 for(const alter of [v=>v.calculation.net_minor++,v=>v.source.profile.profile.tax_factor='0.900',v=>v.preview_hash='0'.repeat(64)]){
  const v=copy(f.run);alter(v);await assert.rejects(verifyFactorClaimsRun(v));
 }
});

for(const run of [false,true])test(`original ${run?'run':'case'} retains exact payload across lost ACK, feature and rights revocation`,async()=>{
 const {OfficeApi}=await import('../office.js');
 let feature=true,approve=true,lost=true;const posts=[];
 const caps=()=>({readonly:false,features:['german_payroll_2026','payroll_calculation_cases',...(feature?['payroll_factor_claims']:[])],capabilities:['business_payroll','business_payroll_calculation_cases'],permissions:['personnel.read',...(approve?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:true}}}});
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted reply lost');}return Response.json(run?f.run:f.case);}
  return Response.json(url.includes('/capabilities')?caps():url.includes('/sources?')?{...f.sources,calculation_cases:[f.case],can_approve:approve}:{employee_id:id,items:[f.run]});
 }});
 api.setToken('synthetic-factor-claims-browser-token');
 const body=clean(run?f.run_command:f.case_command),key=(run?'payroll-run-':'payroll-calculation-cases-')+id,path=run?'/business/payroll/runs':'/business/payroll/calculation-cases';
 await assert.rejects(api.mutate(key,path,body,{validate:run?payrollRunValidator(body,f.run_preview):payrollCalculationCaseValidator(body,null,f.case_preview)}));
 feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 feature=true;approve=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 approve=true;await api.retry(key);assert.deepEqual(posts[1],posts[0]);assert.equal(api.pendingCount,0);
});

test('actual original hourly holiday claim contributes paid absence, preserves zero recorded work and independent XML tax',async()=>{
 const h=f.hourly;
 payrollCalculationCaseSources(h.sources,h.employee.id,'2026-10');
 await payrollCalculationCasePreview(h.case_preview,h.case_input);
 await payrollCalculationCaseValidator(clean(h.case_command),null,h.case_preview)(h.case);
 payrollCompositeSource(h.run_preview,h.run_input);
 await payrollPreview(h.run_preview,h.run_input);
 await payrollRunValidator(clean(h.run_command),h.run_preview)(h.run);
 assert.equal(h.period.plan.gross_minor,0);
 assert.equal(h.run.calculation.gross_minor,320000);
 assert.equal(h.run.calculation.individual_wage_tax_minor,25391);
 assert.equal(h.case.sources.period_case.sources.preparation.snapshot.net_work_seconds,0);
 assert.ok(h.case.plan.earnings.some(e=>e.kind==='public_holiday'&&e.gross_minor===320000));
});
