import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {INDIVIDUAL_MINIJOB_RULE,INDIVIDUAL_MINIJOB_FEATURE,payrollCalculationCaseInput,payrollCalculationCaseSources,payrollCalculationCasePreview,payrollCalculationCaseValidator,payrollCalculationCaseRunInput,payrollCompositeSource,payrollCompositeCalculation} from '../payroll-calculation-cases.js';
import {MINIJOB_CONFIRMATIONS,MINIJOB_EVIDENCE,minijobAssessment,minijobUpgradeEligible} from '../payroll-individual-minijob.js';
import {accountRecord,payrollAccountDetails,accountReceiptValidator} from '../payroll-accounts.js';
import {payrollCalculation,payrollPreview,payrollRunValidator} from '../payroll.js';
const fixtures=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/individual_minijob_v11.json',import.meta.url),'utf8'));
const copy=v=>structuredClone(v),clean=v=>{v=copy(v);delete v.request_id;return v;};
function values(f){const d=f.case_command.details,a=d.individual_minijob_assessment;return{rule_version:INDIVIDUAL_MINIJOB_RULE,month:d.month,period_case_id:d.period_case_ref.id,employment_terms_ids:d.employment_terms_refs.map(v=>v.id),profile_ids:d.profile_refs.map(v=>v.id),identity_ids:d.identity_refs.map(v=>v.id),source_file_ids:copy(f.case_command.source_file_ids),verification_note:d.verification_note,valid_from:a.valid_from,valid_to:a.valid_to,declaration_date:a.declaration_date,actual_health_insurance:a.actual_health_insurance,pension_status:a.pension_status,assessment_note:a.verification_note,...Object.fromEntries(Object.keys(MINIJOB_CONFIRMATIONS).map(k=>[k,a[k]])),...Object.fromEntries(Object.keys(MINIJOB_EVIDENCE).map(k=>[k+'_id',a[k].id])),...f.case_command.correction_reason?{correction_reason:f.case_command.correction_reason}:{}};}
for(const branch of ['compulsory','exempt','migrated'])test('actual '+branch+' private originals, complete command and payroll retain direct PAP and net',()=>{
 const f=fixtures[branch],id=f.employee.id,old=branch==='migrated'?f.legacy_case:null;
 payrollCalculationCaseSources(f.sources,id,f.case.details.month);
 const body=payrollCalculationCaseInput(id,f.sources,values(f),old);
 assert.deepEqual({...body,preview_hash:f.case_preview.preview_hash},{...clean(f.case_command),source_file_ids:[...f.case_command.source_file_ids].sort()});
 payrollCalculationCasePreview(f.case_preview,body);payrollCalculationCaseValidator(clean(f.case_command),old,f.case_preview)(f.case);
 assert.deepEqual(payrollCalculationCaseRunInput(f.case),f.run_input);
 payrollCompositeSource(f.run_preview,f.run_input);payrollCompositeCalculation(f.run.calculation);payrollCalculation(f.run.calculation);payrollPreview(f.run_preview,f.run_input);payrollRunValidator(clean(f.run_command),f.run_preview)(f.run);
 assert.equal(f.run.calculation.net_minor,f.run.calculation.gross_minor-f.run.calculation.employee_tax_minor-f.run.calculation.employee_social_total_minor);
 assert.equal(f.case.sources.profiles[0].profile.health_insurance,'statutory_other');assert.equal(f.run.calculation.tax_parameters.actual_health_insurance,'statutory_family');assert.equal(f.run.calculation.tax_parameters.technical_pap_parameters.PKV,1);
 assert.equal(f.run.calculation.employee_contributions.pension===0,branch==='exempt');
 accountRecord(f.identity,id,'identity');accountReceiptValidator(clean(f.identity_command),f.files.find(v=>v.id===f.identity_command.source_file_id),null,{profile:f.profile})(f.identity);
 const d=f.identity_command.details,identityValues={...d,identity_scope:'individual_minijob',profile_ref:f.profile.id+'@'+f.profile.revision,tax_allowance_yearly_minor:'0',tax_addition_yearly_minor:'0'};
 assert.deepEqual(payrollAccountDetails('identity',identityValues,{profiles:[f.profile]},0),d);
});

test('each of six confirmations and five own evidence references is necessary',()=>{
 const f=fixtures.compulsory;
 for(const k of Object.keys(MINIJOB_CONFIRMATIONS)){const v=values(f);v[k]=false;assert.throws(()=>payrollCalculationCaseInput(f.employee.id,f.sources,v),undefined,k);}
 for(const k of Object.keys(MINIJOB_EVIDENCE)){const v=values(f);v[k+'_id']='0'.repeat(32);assert.throws(()=>payrollCalculationCaseInput(f.employee.id,f.sources,v),undefined,k);}
 for(const change of [v=>v.actual_health_insurance='private',v=>v.valid_from='2026-10-02',v=>v.valid_to='2026-10-30',v=>v.period_case_id=f.preparation.id,v=>v.profile_ids=[],v=>v.travel_settlement_ids=['1'.repeat(32)],v=>v.segment_events=[{}],v=>v.entitlement_case_ids=['1'.repeat(32)],v=>v.thirty_day_rule='actual_days_capped_per_claim',v=>v.assessment_note='\ud800']){const v=values(f);change(v);assert.throws(()=>payrollCalculationCaseInput(f.employee.id,f.sources,v));}
 const a=copy(f.case.details.individual_minijob_assessment);a.extra=true;assert.throws(()=>minijobAssessment(a,f.employee.id,f.case.details.month));
});

test('old individually blocked case requires explicit source-contract correction',()=>{
 const f=fixtures.migrated;assert.equal(minijobUpgradeEligible(f.legacy_case),true);
 for(const change of [v=>v.rule_version=INDIVIDUAL_MINIJOB_RULE,v=>v.source_contract_version=2,v=>v.plan.can_calculate=true,v=>v.plan.blockers=[],v=>v.sources.profiles[0].profile.minijob_tax='flat']){const old=copy(f.legacy_case);change(old);assert.equal(minijobUpgradeEligible(old),false);}
 const original=JSON.stringify(f.legacy_case);const body=payrollCalculationCaseInput(f.employee.id,f.sources,values(f),f.legacy_case);assert.equal(body.id,f.legacy_case.id);assert.equal(body.revision,f.legacy_case.revision);assert.equal(body.source_contract_version,3);assert.equal(JSON.stringify(f.legacy_case),original);
 const noReason=values(f);delete noReason.correction_reason;assert.throws(()=>payrollCalculationCaseInput(f.employee.id,f.sources,noReason,f.legacy_case));
});

test('historical receipts reject substituted ELStAM, actual insurance, pension, periods, and net',()=>{
 const f=fixtures.compulsory,id=f.employee.id;
 for(const change of [v=>v.sources.individual_minijob_assessment.elstam_evidence_ref.id='1'.repeat(32),v=>v.sources.identities[0].details.identity_source_schema_version=1,v=>v.plan.technical_pap_parameters.KRV=1,v=>v.plan.actual_health_insurance='private',v=>v.plan.tax_periods[0].lzz=4,v=>v.plan.source_contract_version=2]){const item=copy(f.case);change(item);assert.throws(()=>payrollCalculationCaseValidator(clean(f.case_command),null,f.case_preview)(item));}
 for(const change of [v=>v.tax_parameters.actual_health_insurance='private',v=>v.tax_parameters.technical_pap_parameters.KRV=2,v=>v.period_details.tax_assessments[0].calculation.LSTLZZ++,v=>v.net_minor++,v=>v.period_details.travel.tax_free_external_minor=1,v=>v.period_details.social_periods[0].full_month=false]){const c=copy(f.run.calculation);change(c);assert.throws(()=>payrollCompositeCalculation(c));}
 const proof=copy(f.run_preview);proof.calculation.period_details.tax_periods[0].profile_ref.content_hash='0'.repeat(64);assert.throws(()=>payrollCompositeSource(proof,f.run_input));
});

for(const kind of ['case','identity','run'])test('accepted '+kind+' keeps exact original after lost reply and feature or rights loss',async()=>{
 const f=fixtures.compulsory,id=f.employee.id,path=kind==='case'?'/business/payroll/calculation-cases':kind==='identity'?'/business/payroll/account-records':'/business/payroll/runs',key=(kind==='case'?'payroll-calculation-cases-':kind==='identity'?'payroll-account-':'payroll-run-')+id;
 const body=clean(kind==='case'?f.case_command:kind==='identity'?f.identity_command:f.run_command),record=kind==='case'?f.case:kind==='identity'?f.identity:f.run,validate=kind==='case'?payrollCalculationCaseValidator(body,null,f.case_preview):kind==='identity'?accountReceiptValidator(body,f.files.find(v=>v.id===body.source_file_id),null,{profile:f.profile}):payrollRunValidator(body,f.run_preview),posts=[];
 let lost=true,feature=true,allowed=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lost){lost=false;throw new Error('Synthetic accepted reply lost');}return Response.json(record);}if(url.includes('/capabilities'))return Response.json({readonly:false,features:['payroll_calculation_cases','german_payroll_2026','payroll_wage_account',...(feature?[INDIVIDUAL_MINIJOB_FEATURE]:[])],capabilities:['business_payroll_calculation_cases','business_payroll','business_payroll_accounts'],permissions:['personnel.read',...(allowed?['personnel.approve','personnel.write']:[])],organization:{modules:{personnel:{enabled:true}}}});return Response.json(kind==='case'?f.sources:{employee_id:id,items:url.includes('/profiles?')?[f.profile]:[record]});}});api.setToken('public-synthetic-v11-test-token');
 await assert.rejects(api.mutate(key,path,body,{validate}));assert.equal(api.pendingCount,1);
 feature=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 feature=true;allowed=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 allowed=true;await api.retry(key);assert.deepEqual(posts[0],posts[1]);assert.equal(api.pendingCount,0);
});

const boundaries=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/individual_minijob_client_boundaries.json',import.meta.url),'utf8'));
for(const kind of ['covered','blocked'])test('actual '+kind+' wider evidence interval, Unicode original and blocked calculation remain readable',()=>{
 const f=boundaries[kind],body=clean(f.command);payrollCalculationCasePreview(f.preview,body);payrollCalculationCaseValidator(body,null,f.preview)(f.record);payrollCompositeSource(f.run_preview,f.run_input);payrollCompositeCalculation(f.run_preview.calculation);
 assert.equal(f.record.plan.can_calculate,kind==='covered');assert.equal(f.record.details.individual_minijob_assessment.valid_from,'2026-01-01');assert.ok(f.record.details.individual_minijob_assessment.verification_note.includes('\n\t'));
 if(kind==='blocked'){assert.equal(f.run_preview.can_finalize,false);assert.equal(f.run_preview.calculation.net_minor,null);}
});

test('closing a minijob retry during the fresh original-source check sends no second POST',async()=>{
 const f=fixtures.compulsory,id=f.employee.id,key='payroll-calculation-cases-'+id,path='/business/payroll/calculation-cases',body=clean(f.case_command),posts=[];let closeOnRead=false,closed=false;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='POST'){posts.push(JSON.parse(options.body));throw new Error('Synthetic accepted response lost');}if(url.includes('/capabilities'))return Response.json({readonly:false,features:['payroll_calculation_cases',INDIVIDUAL_MINIJOB_FEATURE],capabilities:['business_payroll_calculation_cases'],permissions:['personnel.read','personnel.approve'],organization:{modules:{personnel:{enabled:true}}}});if(closeOnRead)closed=true;return Response.json(f.sources);}});api.setToken('synthetic-minijob-context');
 await assert.rejects(api.mutate(key,path,body));closeOnRead=true;await assert.rejects(api.retry(key,{stillCurrent:()=>!closed}));assert.equal(posts.length,1);assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,path),body);
});

test('a mismatching accepted minijob receipt preserves the exact unresolved original command',async()=>{
 const f=fixtures.compulsory,id=f.employee.id,key='payroll-calculation-cases-'+id,path='/business/payroll/calculation-cases',body=clean(f.case_command),wrong=copy(f.case);wrong.plan.actual_health_insurance='private';
 const api=new OfficeApi({fetcher:async()=>Response.json(wrong)});api.setToken('synthetic-minijob-bad-receipt');await assert.rejects(api.mutate(key,path,body,{validate:payrollCalculationCaseValidator(body,null,f.case_preview)}));assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,path),body);
});
