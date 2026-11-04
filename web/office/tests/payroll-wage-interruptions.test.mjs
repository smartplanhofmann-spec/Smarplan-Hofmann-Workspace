import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {PAYROLL_WAGE_INTERRUPTION_EXCEPTIONS,payrollWageInterruptionDetails,payrollWageInterruptionInput,payrollWageInterruptionSources,payrollWageInterruptionRecord,payrollWageInterruptionPreview,payrollWageInterruptionPlan,payrollWageInterruptionValidator,payrollWageInterruptionsAuthorize,payrollWageInterruptionsPendingAuthorize} from '../payroll-wage-interruptions.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_wage_interruptions.json',import.meta.url))),copy=v=>structuredClone(v),employee=f.saved.employee_id;
const clean=body=>{const v=copy(body);delete v.request_id;return v;};
function values(){const d=f.command.details;return{year:2026,assessment_through:d.assessment_through,employment_terms_ids:d.employment_terms_refs.map(r=>r.id),run_ids:d.run_refs.map(r=>r.id),work_schedule_ids:d.work_schedule_refs.map(r=>r.id),entitlement_case_ids:d.entitlement_case_refs.map(r=>r.id),exception_review_file_ids:d.exception_review_file_refs.map(r=>r.id),source_file_ids:f.command.source_file_ids,excluded_reviews:Object.fromEntries(Object.keys(PAYROLL_WAGE_INTERRUPTION_EXCEPTIONS).map(k=>[k,d.excluded_payments.some(p=>p.kind===k)?'present':'none'])),excluded_payments:d.excluded_payments.map(p=>({from:p.from,to:p.to,kind:p.kind,evidence_file_ids:p.evidence_refs.map(r=>r.id)})),verification_note:d.verification_note};}
test('real U fixture binds actual runs schedules employment and all eight reviewed payment kinds',()=>{
 const body=payrollWageInterruptionInput(employee,f.sources,values());assert.deepEqual({...body,preview_hash:f.command.preview_hash},clean(f.command));
 assert.deepEqual(payrollWageInterruptionSources(f.sources,employee),f.sources);assert.deepEqual(payrollWageInterruptionRecord(f.saved,employee),f.saved);assert.deepEqual(payrollWageInterruptionPreview(f.preview,f.preview_request),f.preview);assert.equal(f.preview.plan.number_u,1);assert.equal(f.preview.plan.periods[0].workday_count,5);
 assert.equal(Object.hasOwn(body.details,'number_u'),false);assert.equal(Object.hasOwn(body.details,'days'),false);
});
test('absence of an exception requires eight actual explicit decisions not an unchecked empty list',()=>{
 for(const patch of [{year:''},{assessment_through:''},{excluded_reviews:{}},{exception_review_file_ids:[]},{run_ids:['f'.repeat(32)]},{employment_terms_ids:[]}])assert.throws(()=>payrollWageInterruptionInput(employee,f.sources,{...values(),...patch}));
 for(const kind of Object.keys(PAYROLL_WAGE_INTERRUPTION_EXCEPTIONS)){const v=values();v.excluded_reviews[kind]='';assert.throws(()=>payrollWageInterruptionInput(employee,f.sources,v));v.excluded_reviews[kind]='present';assert.throws(()=>payrollWageInterruptionInput(employee,f.sources,v));}
});
test('actual excluded-payment periods need exact originals and coherent explicit review',()=>{
 const v=values(),kind='short_time_work_benefit';v.excluded_reviews[kind]='present';v.excluded_payments=[{from:'2026-10-20',to:'2026-10-26',kind,evidence_file_ids:v.exception_review_file_ids}];const body=payrollWageInterruptionInput(employee,f.sources,v);assert.equal(body.details.excluded_payments[0].kind,kind);
 for(const mutate of [v=>v.excluded_reviews[kind]='none',v=>v.excluded_payments[0].to='2026-02-30',v=>v.excluded_payments[0].to='2026-12-31',v=>v.excluded_payments[0].evidence_file_ids=['f'.repeat(32)],v=>v.excluded_payments.push(copy(v.excluded_payments[0]))]){const bad=copy(v);mutate(bad);assert.throws(()=>payrollWageInterruptionInput(employee,f.sources,bad));}
 assert.throws(()=>payrollWageInterruptionDetails({...body.details,number_u:0}));
});
test('preview freezes daily source references and cannot turn unknown U into confirmed zero',()=>{
 for(const mutate of [v=>v.source_snapshot.runs[0].revision++,v=>v.plan.input.days[0].claim_evidence_refs[0].content_hash='f'.repeat(64),v=>v.plan.input.days[0].schedule_evidence_refs[0].id='f'.repeat(32),v=>v.plan.input.days[0].exception_evidence_refs[0].revision++,v=>v.plan.input.days.push(copy(v.plan.input.days[0])),v=>v.plan.number_u=0,v=>v.plan.source_snapshot_hash='f'.repeat(64)]){const bad=copy(f.preview);mutate(bad);assert.throws(()=>payrollWageInterruptionPreview(bad,f.preview_request));}
 const unknown=copy(f.preview.plan);unknown.blockers=[{code:'unresolved_actual_claim',message:'Actual unresolved entitlement'}];unknown.can_determine=false;unknown.number_u=null;assert.equal(payrollWageInterruptionPlan(unknown).number_u,null);unknown.number_u=0;assert.throws(()=>payrollWageInterruptionPlan(unknown));
});
test('accepted record must retain original preview and an immutable private predecessor',()=>{
 const body=clean(f.command),proof=copy(f.preview),validate=payrollWageInterruptionValidator(body,null,proof);body.details.verification_note='later editor';proof.plan.number_u=0;assert.deepEqual(validate(f.saved),f.saved);
 for(const mutate of [v=>v.employee_id='f'.repeat(32),v=>v.effective_to='2026-12-31',v=>v.source_contract_version=true,v=>v.previous_hash='f'.repeat(64),v=>v.sources.source_files.push(copy(v.sources.source_files[0]))]){const bad=copy(f.saved);mutate(bad);assert.throws(()=>validate(bad));}
});
test('actual correction and documentary void keep the exact original historical source',()=>{
 payrollWageInterruptionValidator(clean(f.correction_body),f.saved,f.correction_preview)(f.corrected);
 payrollWageInterruptionValidator(clean(f.void_body),f.corrected)(f.void);
 assert.deepEqual(f.history.items,[f.saved,f.corrected,f.void]);
 const bad=copy(f.void);bad.previous_hash=f.saved.content_hash;
 assert.throws(()=>payrollWageInterruptionValidator(clean(f.void_body),f.corrected)(bad));
 assert.deepEqual(f.void.plan,f.corrected.plan);assert.deepEqual(f.void.sources,f.corrected.sources);
});
test('fresh global rights gate every new write while unchanged accepted replay survives pause',async()=>{
 const caps={readonly:false,features:['payroll_wage_interruptions'],capabilities:['business_payroll_wage_interruptions'],permissions:['personnel.read','personnel.approve'],organization:{modules:{personnel:{enabled:true}}}},state={caps,sources:copy(f.sources)};
 const api={get:async path=>copy(path==='/business/capabilities'?state.caps:state.sources),pendingCommandValues:()=>clean(f.command)};
 assert.equal((await payrollWageInterruptionsAuthorize(api,employee,{write:true})).rights.approve,true);
 state.caps.permissions=['personnel.read'];await assert.rejects(payrollWageInterruptionsAuthorize(api,employee,{write:true}),e=>e.status===403);
 state.caps.permissions.push('personnel.approve');state.sources.can_approve=false;await assert.rejects(payrollWageInterruptionsAuthorize(api,employee,{write:true}),e=>e.status===403);
 state.sources.can_approve=true;state.sources.writes_enabled=false;state.caps.organization.modules.personnel.enabled=false;await assert.rejects(payrollWageInterruptionsAuthorize(api,employee,{write:true}),e=>e.status===423);
 assert.equal(await payrollWageInterruptionsPendingAuthorize(api,{key:'payroll-wage-interruptions-'+employee,path:'/business/payroll/wage-interruptions'}),true);
 state.sources.employee_id='f'.repeat(32);await assert.rejects(payrollWageInterruptionsPendingAuthorize(api,{key:'payroll-wage-interruptions-'+employee,path:'/business/payroll/wage-interruptions'}));
});
