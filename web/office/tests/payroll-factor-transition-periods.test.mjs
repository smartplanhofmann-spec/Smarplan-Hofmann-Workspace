import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash,webcrypto} from 'node:crypto';
import {
 factorTransitionPeriodAssessment,factorTransitionPeriodPlan,factorTransitionPeriodBindings,
 factorTransitionPeriodSelectable,factorTransitionPeriodInput,factorTransitionPeriodCalculation,
 verifyFactorTransitionPeriodCase,verifyFactorTransitionPeriodRun,
} from '../payroll-factor-transition-periods.js';
import {payrollCalculationCaseInput,payrollCalculationCasePreview,payrollCalculationCaseValidator} from '../payroll-calculation-cases.js';
import {payrollPreview,payrollRunValidator} from '../payroll.js';
import {payrollStatementPage,payrollStatementBytes} from '../payroll-statements.js';

globalThis.crypto ||= webcrypto;
const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_factor_transition_period.json',import.meta.url),'utf8'));
const rows=fixture.cases,copy=v=>structuredClone(v);
const order=v=>Array.isArray(v)?v.map(order):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,order(v[k])])):v;
const sha=v=>createHash('sha256').update(JSON.stringify(order(v))).digest('hex');
const values=r=>({month:'2026-10',period_case_id:r.input.details.period_case_ref.id,
 employment_terms_ids:r.input.details.employment_terms_refs.map(v=>v.id),profile_ids:r.input.details.profile_refs.map(v=>v.id),
 identity_ids:r.input.details.identity_refs.map(v=>v.id),factor_transition_period_assessment:copy(r.input.details.factor_transition_period_assessment),
 source_file_ids:r.input.source_file_ids,verification_note:r.input.details.verification_note});

test('two actual accepted API case/run graphs reproduce independent browser hashes and exact inputs',async()=>{
 assert.equal(rows.length,2);
 for(const r of rows){
  assert.equal(factorTransitionPeriodSelectable(r.case.sources.period_case,'2026-10'),true);
  assert.equal(factorTransitionPeriodPlan(r.case.plan),r.case.plan);
  factorTransitionPeriodBindings(r.case.sources,r.case.details,r.case.plan);
  await verifyFactorTransitionPeriodCase(r.case_preview);
  await verifyFactorTransitionPeriodCase(r.case);
  factorTransitionPeriodCalculation(r.run.calculation);
  await verifyFactorTransitionPeriodRun(r.run_preview);
  await verifyFactorTransitionPeriodRun(r.run);
  const expected=copy(r.case_command);delete expected.request_id;delete expected.preview_hash;
  assert.deepEqual(factorTransitionPeriodInput(r.employee.id,r.sources,values(r)),expected);
 }
 assert.equal(rows[0].run.calculation.net_minor,49565);
 assert.equal(rows[1].run.calculation.individual_wage_tax_minor,3740);
 assert.equal(rows[1].run.calculation.net_minor,84944);
});

test('a self-consistently rehashed changed tax cannot replace the separately accepted complete case component',async()=>{
 const v=copy(rows[1].run),c=v.calculation,t=c.factor_transition_period_components.factor_tax;
 t.component.LSTLZZ+=1;t.totals.LSTLZZ+=17;c.individual_wage_tax_minor+=17;c.employee_tax_minor+=17;c.net_minor-=17;c.payout_minor-=17;
 c.period_details.tax_calculations[0].calculation=copy(t);
 v.preview_hash=sha({source:v.source,calculation:c});
 factorTransitionPeriodCalculation(c);
 await assert.rejects(()=>verifyFactorTransitionPeriodRun(v));
});

test('actual generic preview, accepted-command and full run dispatchers use the v16 contract',async()=>{
 for(const r of rows){
  const body=payrollCalculationCaseInput(r.employee.id,r.sources,{...values(r),rule_version:r.input.rule_version});
  const expected=copy(r.case_command);delete expected.request_id;delete expected.preview_hash;
  assert.deepEqual(body,expected);
  await payrollCalculationCasePreview(r.case_preview,r.input);
  await payrollCalculationCaseValidator(r.case_command,null,r.case_preview)(r.case);
  await payrollPreview(r.run_preview,r.run_input);
  await payrollRunValidator(r.run_command,r.run_preview)(r.run);
 }
});

test('foreign private evidence is rejected even after recomputing all reported case and plan hashes',async()=>{
 const v=copy(rows[0].case),id=v.sources.factor_transition_period_assessment.forecast_evidence_ref.id;
 v.sources.source_files.find(f=>f.id===id).employee_id='f'.repeat(32);
 v.source_hash=sha(v.sources);v.plan.source_snapshot_hash=v.source_hash;
 const p=copy(v.plan);delete p.plan_hash;delete p.can_confirm;delete p.can_calculate;v.plan.plan_hash=sha(p);
 v.preview_hash=sha({source_snapshot:v.sources,plan:v.plan});
 await assert.rejects(()=>verifyFactorTransitionPeriodCase(v));
});

test('complete full-month or old-labelled cases cannot become new partial cases',()=>{
 const v=copy(rows[0].case),p=v.sources.period_case;
 p.plan.tax_periods[0].lzz=2;p.plan.tax_periods[0].tax_days=30;p.plan.social_periods[0].full_month=true;
 assert.equal(factorTransitionPeriodSelectable(p,'2026-10'),false);
 const plan=copy(v.plan);plan.rule_version='de_2026_factor_transition_month_v14';plan.source_contract_version=6;
 assert.throws(()=>factorTransitionPeriodPlan(plan));
});

test('no first-option selection or hidden extra wage sources are inferred',()=>{
 const r=rows[0],form=values(r);
 for(const key of ['period_case_id','profile_ids','identity_ids','employment_terms_ids']){
  const v=copy(form);delete v[key];assert.throws(()=>factorTransitionPeriodInput(r.employee.id,r.sources,v));
 }
 assert.throws(()=>factorTransitionPeriodInput(r.employee.id,r.sources,{...form,travel_settlement_ids:['a'.repeat(32)]}));
 assert.throws(()=>factorTransitionPeriodInput(r.employee.id,r.sources,{...form,thirty_day_rule:'unverified'}));
});

test('review shape rejects boolean counts, hidden fields and malformed Unicode while retaining meaningful multiline notes',()=>{
 const r=rows[0],review=copy(r.input.details.factor_transition_period_assessment);
 for(const change of [{schema_version:true},{contractual_30_days_confirmed:1},{unknown:true},{verification_note:'\ud800'}]){
  assert.throws(()=>factorTransitionPeriodAssessment({...review,...change},r.employee.id));
 }
 const valid={...review,verification_note:'Beleg geprüft\nZweite Zeile ✓'};
 assert.equal(factorTransitionPeriodAssessment(valid,r.employee.id),valid);
});

test('a blocked status cannot carry seemingly complete money or a changed daily gross remainder',()=>{
 const c=copy(rows[0].run.calculation);c.scope='unsupported';c.payroll_calculation_complete=false;c.social_contributions_available=false;c.blockers=[{code:'test',message:'blocked'}];
 assert.throws(()=>factorTransitionPeriodCalculation(c));
 const changed=copy(rows[1].run.calculation);changed.factor_transition_period_components.factor_tax.inputs.gross_remainder_minor++;
 assert.throws(()=>factorTransitionPeriodCalculation(changed));
});

for(const run of [false,true])test(`actual original ${run?'run':'case'} survives lost reply and refuses revoked feature or approval`,async()=>{
 const r=rows[1],id=r.employee.id; const clean=v=>Object.fromEntries(Object.entries(copy(v)).filter(([k])=>k!=='request_id')); const {OfficeApi}=await import('../office.js');let feature=true,approve=true,lost=true;const posts=[];
 const caps=()=>({readonly:false,features:['german_payroll_2026','payroll_calculation_cases',...(feature?['payroll_factor_transition_periods']:[])],
  capabilities:['business_payroll','business_payroll_calculation_cases'],permissions:['personnel.read',...(approve?['personnel.approve']:[])],organization:{modules:{personnel:{enabled:true}}}});
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted reply lost');}return Response.json(run?r.run:r.case);}
  return Response.json(url.includes('/capabilities')?caps():url.includes('/sources?')?{...{...r.sources,calculation_cases:[r.case]},can_approve:approve}:{employee_id:id,items:[r.run]});
 }});
 api.setToken('synthetic-factor-midijob-browser-token');
 const body=clean(run?r.run_command:r.case_command),key=(run?'payroll-run-':'payroll-calculation-cases-')+id,path=run?'/business/payroll/runs':'/business/payroll/calculation-cases';
 await assert.rejects(api.mutate(key,path,body,{validate:run?payrollRunValidator(body,r.run_preview):payrollCalculationCaseValidator(body,null,r.case_preview)}));
 feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 feature=true;approve=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 approve=true;await api.retry(key);assert.deepEqual(posts[1],posts[0]);assert.equal(api.pendingCount,0);
});

test('actual own partial-period statements retain their restricted DTO and exact PDF digest',async()=>{
 for(const r of rows){
  await payrollStatementPage(r.own,r.employee.id,{detail:true});
  const text=JSON.stringify(r.own.statement);
  assert.equal(text.includes(r.input.source_file_ids[0]),false);
  for(const key of ['factor_transition_period_assessment','tax_identifier','verification_note'])assert.equal(text.includes('"'+key+'":'),false);
  await payrollStatementBytes(new Blob([Buffer.from(r.own_pdf_base64,'base64')]),r.own.statement);
  const changed=copy(r.own);changed.statement.calculation.rule_version='de_2026_factor_transition_month_v14';
  await assert.rejects(()=>payrollStatementPage(changed,r.employee.id,{detail:true}));
 }
});
