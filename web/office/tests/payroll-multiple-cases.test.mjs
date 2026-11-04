import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {PAYROLL_MULTIPLE_PATH,payrollMultipleCalculation,payrollMultipleCaseSources,payrollMultipleCaseRecord,payrollMultipleCaseInput,payrollMultipleCasePreview,payrollMultipleCaseValidator,payrollMultipleCaseHistory,payrollMultipleCaseRunInput,payrollMultipleSource,payrollMultipleCasesPendingAuthorize,payrollMultipleMoney} from '../payroll-multiple-cases.js';
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_multiple_runs.json',import.meta.url))),copy=v=>structuredClone(v),employee=f.saved.employee_id;
const clean=v=>{const b=copy(v);delete b.request_id;return b;};
const values=d=>({month:d.month,running_calculation_case_id:d.running_calculation_case_ref.id,current_annual_basis_id:d.current_annual_basis_ref.id,previous_annual_basis_id:d.previous_annual_basis_ref?.id||'',source_file_ids:f.saved.source_file_ids,completeness_file_id:d.completeness.evidence_ref.id,month_events_complete:true,verification_note:d.verification_note,components:d.components.map(p=>({earning_id:p.earning_ref.id,receipts:p.planned_receipts.map(e=>({event_key:e.event_key,receipt_date:e.receipt_date,gross_minor:e.gross_minor,document_ids:e.document_refs.map(r=>r.id)}))})),annual_tax_forecasts:d.annual_tax_forecasts.map(t=>({event_key:t.event_key,forecast_id:t.annual_tax_forecast_ref.id}))});
test('actual Source5 case originals, canonical typed input and exact accepted preview survive unchanged',()=>{
 payrollMultipleCaseSources(f.sources,employee,'2026-10');payrollMultipleCaseRecord(f.saved,employee);payrollMultipleCaseHistory(f.history,employee,f.saved.id);
 const body=payrollMultipleCaseInput(employee,f.sources,values(f.saved.details));const command=clean(f.command);delete command.preview_hash;assert.deepEqual(body,command);payrollMultipleCasePreview(f.preview,body);payrollMultipleCaseValidator(clean(f.command),null,f.preview)(f.saved);
});
test('actual one-full-claim run and paid v5 upgrade bind unchanged original calculations',()=>{
 for(const c of [f,f.paid_v5_upgrade]){payrollMultipleSource(c.run_preview,c.run_input);payrollMultipleSource({...c.run,can_finalize:true},c.run_input);assert.deepEqual(payrollMultipleCaseRunInput(c.run.source.multiple_one_off_case),c.run_input);const p=payrollMultipleCalculation(c.run.calculation);assert.equal(p.multiple_one_off_details.receipt_events[0].receipt_date,'2026-10-31');assert.equal(p.net_minor,p.multiple_one_off_details.single_original_calculation.net_minor);}
});
test('actual multiple-claim plan remains visibly incomplete with unknown net and cannot form run input',()=>{
 const b=f.blocked_multiple;payrollMultipleCaseRecord(b.saved,b.saved.employee_id);payrollMultipleCasePreview(b.preview,b.preview_request);payrollMultipleSource(b.run_preview,b.run_input);assert.equal(b.run_preview.can_finalize,false);assert.equal(b.saved.plan.net_minor,null);assert.equal(b.saved.plan.multiple_one_off_details.tax_groups,null);assert.throws(()=>payrollMultipleCaseRunInput(b.saved));
 const fake=copy(b.saved.plan);fake.net_minor=0;assert.throws(()=>payrollMultipleCalculation(fake));
});
test('claim/event/annual and original-file substitutions fail source binding',()=>{
 for(const mutate of [v=>v.details.components[0].planned_receipts[0].event_key='f'.repeat(32),v=>v.details.components[0].planned_receipts[0].document_refs[0].content_hash='f'.repeat(64),v=>v.sources.calculation_source.components[0].earning.details.amount_minor++,v=>v.details.annual_tax_forecasts[0].annual_tax_forecast_ref.revision++,v=>v.plan.multiple_one_off_details.components[0].claim_minor++,v=>v.plan.multiple_one_off_details.receipt_events[0].receipt_date='2026-10-30',v=>v.plan.net_minor++,v=>v.plan.multiple_one_off_details.social_month_group.component_allocations=[]]){const bad=copy(f.saved);mutate(bad);assert.throws(()=>payrollMultipleCaseRecord(bad,employee));}
});
test('frozen accepted receipt cannot replace original metadata, plan or previous linkage',()=>{
 const body=clean(f.command),p=copy(f.preview),validator=payrollMultipleCaseValidator(body,null,p);body.details.verification_note='Changed later';p.plan.net_minor=0;validator(f.saved);
 for(const mutate of [v=>v.previous_hash='f'.repeat(64),v=>v.revision++,v=>v.correction_reason='Other reason',v=>v.source_file_ids=[],v=>v.sources.source_files[0].filename='Replaced original name']){const bad=copy(f.saved);mutate(bad);assert.throws(()=>validator(bad));}
});
test('unknown source metadata does not turn a planned claim into an actual payment',()=>{
 const p=copy(f.saved.plan);p.multiple_one_off_details.actual_payment_created=true;assert.throws(()=>payrollMultipleCalculation(p));p.multiple_one_off_details.actual_payment_created=false;p.multiple_one_off_details.claim_consumption_created=true;assert.throws(()=>payrollMultipleCalculation(p));
 for(const value of ['',null,'1.001','1e3','-1','0'])assert.throws(()=>payrollMultipleMoney(value));assert.equal(payrollMultipleMoney('500,00'),50000);
});
test('unchanged case retry rechecks current global employee rights but may replay accepted history during module pause',async()=>{
 const caps={features:['payroll_multiple_cases'],capabilities:['business_payroll_multiple_cases'],permissions:['personnel.read','personnel.approve'],readonly:false},s=copy(f.sources);s.writes_enabled=false;const path='/business'+PAYROLL_MULTIPLE_PATH,key='payroll-multiple-'+employee,body=clean(f.command),api={pendingCommandValues:(k,p)=>k===key&&p===path?body:null,get:async path=>path.endsWith('/capabilities')?caps:s};assert.equal(await payrollMultipleCasesPendingAuthorize(api,{key,path}),true);caps.permissions.pop();await assert.rejects(payrollMultipleCasesPendingAuthorize(api,{key,path}),e=>e.status===403);await assert.rejects(payrollMultipleCasesPendingAuthorize(api,{key:'wrong',path}),e=>e.status===409);
});
