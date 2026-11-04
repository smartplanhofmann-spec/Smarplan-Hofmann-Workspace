import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollSicknessStructure,payrollEntitlementSources,payrollEntitlementRecord,payrollEntitlementInput,payrollEntitlementPreview,payrollEntitlementValidator} from '../payroll-entitlements.js';
const copy=v=>JSON.parse(JSON.stringify(v));
const samples=['phases_v3','start_v4'].map(name=>JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_sickness_'+name+'.json',import.meta.url))).sickness);
function assemble(v){
 const original=v.command.details.input,base=copy(original),cases=original.prevention_cases;
 delete base.prevention_cases;delete base.employment_commencement;
 const choices=base.episodes.map((e,i)=>{const c=cases.find(c=>c.episode_ids.includes(e.id)),first=base.episodes.findIndex(e=>c.episode_ids.includes(e.id));return first===i?'new':'same:'+first;});
 const ids=base.episodes.map(e=>cases.find(c=>c.episode_ids.includes(e.id)).id);
 return payrollSicknessStructure(base,original.employment_commencement?'preemployment':'combined',choices,ids,cases[0].evidence_refs,original.employment_commencement||null);
}
function values(v,input){const d=v.command.details;return {case_key:d.case_key,employment_terms_id:d.employment_terms_ref.id,agreement_ids:d.agreement_refs.map(v=>v.id),work_schedule_ids:[],preparation_ids:[],source_file_ids:v.command.source_file_ids,verification_note:d.verification_note,input};}
for(const [i,v]of samples.entries())test('actual '+(i?'preemployment v4':'overlap v3')+' typed grouping preserves exact original command and preview',()=>{
 const id=v.command.employee_id,input=assemble(v);assert.deepEqual(input,v.command.details.input);
 payrollEntitlementSources(v.sources,id);payrollEntitlementRecord(v.saved,id);
 const body=payrollEntitlementInput(id,v.sources,'sickness_history',values(v,input));
 const original=copy(v.command);delete original.request_id;
 assert.deepEqual({...body,preview_hash:v.preview.preview_hash},original);
 payrollEntitlementPreview(v.preview,body);payrollEntitlementValidator(original,null,v.preview)(v.saved);
});
test('cause grouping requires genuine existing AU and never invents a shift or recovery',()=>{
 const source=copy(samples[0].command.details.input),cases=source.prevention_cases;delete source.prevention_cases;
 const refs=cases[0].evidence_refs,ids=source.episodes.map(()=>cases[0].id);
 assert.throws(()=>payrollSicknessStructure(source,'combined',['new','new'],ids,refs));
 assert.throws(()=>payrollSicknessStructure(source,'combined',['same:0','same:0'],ids,refs));
 const bad=copy(source);bad.episodes[1].recovery_before=true;assert.throws(()=>payrollSicknessStructure(bad,'combined',['new','same:0'],ids,refs));
 bad.episodes[1].recovery_before=false;bad.episodes[1].first_scheduled_day='2026-11-20';assert.throws(()=>payrollSicknessStructure(bad,'combined',['new','same:0'],ids,refs));
 assert.throws(()=>payrollSicknessStructure(source,'separate'));
});
test('preemployment needs explicit contract original and preserves earlier actual AU',()=>{
 const source=copy(samples[1].command.details.input),cases=source.prevention_cases;delete source.prevention_cases;delete source.employment_commencement;
 assert.throws(()=>payrollSicknessStructure(source,'preemployment',['new'],[cases[0].id],cases[0].evidence_refs));
 assert.throws(()=>payrollSicknessStructure(source,'combined',['new'],[cases[0].id],cases[0].evidence_refs));
 const result=assemble(samples[1]);assert.equal(result.episodes[0].from,'2026-10-10');assert.equal(result.episodes[0].first_scheduled_day,null);
});
test('new phase versions reject unknown rules, overlapping phases and changed cause identity',()=>{
 for(const alter of[x=>x.plan.rule_version='de_2026_sickness_future',x=>x.plan.phases[1].from_date=x.plan.phases[0].to_date,x=>x.plan.phases[0].responsible_episode_id='f'.repeat(32),x=>x.plan.phases=[null],x=>x.plan.phases[0].entitled='true']){
  const v=copy(samples[0].saved);alter(v);assert.throws(()=>payrollEntitlementRecord(v,v.employee_id));
 }
 const v=copy(samples[1].saved);v.plan.preemployment_periods[0].employment_wage_entitlement=true;assert.throws(()=>payrollEntitlementRecord(v,v.employee_id));
});
test('new case and contract evidence remain canonical private file references',()=>{
 for(const v of samples){const input=assemble(v);input.prevention_cases[0].evidence_refs[0].content_hash='f'.repeat(64);assert.throws(()=>payrollEntitlementInput(v.command.employee_id,v.sources,'sickness_history',values(v,input)));}
 const v=samples[1],input=assemble(v);input.employment_commencement.evidence_refs[0].id='f'.repeat(32);assert.throws(()=>payrollEntitlementInput(v.command.employee_id,v.sources,'sickness_history',values(v,input)));
});
