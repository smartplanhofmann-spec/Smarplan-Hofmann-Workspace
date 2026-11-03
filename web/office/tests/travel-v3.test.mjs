import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {travelMixedAssessment,travelPreview,travelV3Calculation,travelReceipt,travelHash} from '../travel-allowances.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/travel_allowances_v3.json',import.meta.url))),copy=v=>structuredClone(v);
test('actual v3 mixed programme retains every original and explicit false review flags',()=>{
 const raw=f.trip_body.details.mixed_assessment;
 assert.deepEqual(travelMixedAssessment(raw,f.sources.files),raw);
 assert.equal(travelMixedAssessment({...raw,program_complete:false,cost_allocation_reviewed:false},f.sources.files).program_complete,false);
 for(const change of [v=>v.program_complete=null,v=>v.program_sessions.pop(),v=>v.program_sessions[1].id=v.program_sessions[0].id,v=>v.program_sessions[1].from=v.program_sessions[0].from,v=>v.program_sessions[0].source_file_ids=['f'.repeat(32)],v=>v.program_sessions[0].from='2026-10-26T08:00:00',v=>v.chosen_share=1]){const bad=copy(raw);change(bad);assert.throws(()=>travelMixedAssessment(bad,f.sources.files));}
});
test('actual v3 preview binds rational programme and ground calendar without changing exact expenses',()=>{
 assert.deepEqual(travelPreview(f.preview,f.employee.id,f.preview_body),f.preview);
 assert.equal(f.preview.days[0].base_minor,933);assert.deepEqual(f.preview.days[0].business_share,{numerator:2,denominator:3});assert.equal(f.preview.totals.expense_allowance_minor,600);assert.equal(f.preview.totals.tax_free_minor,1533);
 for(const change of [v=>delete v.totals.expense_allowance_minor,v=>v.totals.expense_already_paid_minor=-1,v=>delete v.days[0].business_share,v=>v.days[0].business_share.denominator=0,v=>v.days[0].business_share.numerator=true,v=>delete v.ground_calendar_sources,v=>v.ground_calendar_sources[0].trip.revision++,v=>v.mixed_program_sources[0].facts_hash='bad',v=>v.mixed_program_sources[0].source_file_ids.push(v.mixed_program_sources[0].source_file_ids[0])]){const bad=copy(f.preview);change(bad);assert.throws(()=>travelPreview(bad,f.employee.id,f.preview_body));}
});
test('missing programme remains an explicit domain blocker and cannot become approved',()=>{
 const value=copy(f.preview);value.can_approve=false;value.blockers=[{code:'mixed_travel_assessment',text:'Actual programme missing'}];value.days[0].business_share={numerator:0,denominator:1};value.days[0].base_minor=0;value.mixed_program_sources=[{trip:copy(value.trip_refs[0]),rule_version:'de_travel_mixed_program_2026_v1',can_calculate:false,blockers:copy(value.blockers)}];
 assert.equal(travelPreview(value,f.employee.id,f.preview_body).can_approve,false);
 value.can_approve=true;assert.throws(()=>travelV3Calculation(value,value.trip_refs));
});
test('actual v3 archived source arrays and original receipts survive correction unchanged',async()=>{
 for(const item of f.settlement_history.items)travelV3Calculation(item.calculation,item.details.trip_refs);
 assert.deepEqual(f.settlement_history.items[0].calculation,f.calculation);
 for(const [receiptKey,bodyKey]of [['trip_receipt','trip_body'],['approval_receipt','approval_body'],['correction_receipt','correction_body'],['payment_receipt','payment_body']]){
  const value=f[receiptKey],body=f[bodyKey];assert.equal(await travelHash([value.operation,value.target_kind,value.target_id,body]),value.request_hash);assert.deepEqual(await travelReceipt(value,value),value);
 }
});
