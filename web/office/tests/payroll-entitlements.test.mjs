import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollEntitlementSources,payrollEntitlementRecord,payrollEntitlementInput,payrollEntitlementPreview,payrollEntitlementValidator,payrollEntitlementRights,payrollEntitlementsPendingAuthorize} from '../payroll-entitlements.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_entitlements.json',import.meta.url))),copy=v=>JSON.parse(JSON.stringify(v)),cases=[f.sickness,f.vacation,f.unpaid];
const clean=v=>{const r=copy(v);delete r.request_id;return r;};
function values(v){const d=v.command.details;return {case_key:d.case_key,employment_terms_id:d.employment_terms_ref.id,agreement_ids:d.agreement_refs.map(v=>v.id),work_schedule_ids:d.work_schedule_refs.map(v=>v.id),preparation_ids:d.preparation_refs.map(v=>v.id),sickness_history_id:d.sickness_history_ref?.id||'',source_file_ids:v.command.source_file_ids,input:d.input,verification_note:d.verification_note,correction_reason:v.command.correction_reason};}
const caps=()=>({readonly:false,features:['payroll_entitlements'],capabilities:['business_payroll_entitlements'],permissions:['personnel.read','personnel.approve'],organization:{modules:{personnel:{enabled:true}}}});
test('actual P4 kinds retain canonical originals and exact typed correction command',()=>{
 for(const v of cases){const id=v.command.employee_id;payrollEntitlementSources(v.sources,id);payrollEntitlementRecord(v.saved,id);const body=payrollEntitlementInput(id,v.sources,v.saved.kind,values(v),v.history.items[0]);assert.deepEqual({...body,preview_hash:v.preview.preview_hash},clean(v.command));payrollEntitlementPreview(v.preview,body);payrollEntitlementValidator(clean(v.command),v.history.items[0],v.preview)(v.saved);}
 assert.ok(f.sickness.sources.entitlements.some(v=>v.kind==='sickness_history'));
 assert.equal(f.vacation.command.details.input.reference_days.length,91);
});
test('private source pages reject foreign originals, wrong immutable file revisions and own-only permission',()=>{
 const v=f.sickness,id=v.command.employee_id;for(const alter of[x=>x.files[0].employee_id='f'.repeat(32),x=>x.file_references[0].revision=2,x=>x.entitlements[0].employee_id='f'.repeat(32)]){const page=copy(v.sources);alter(page);assert.throws(()=>payrollEntitlementSources(page,id));}
 assert.equal(payrollEntitlementRights({...caps(),permissions:['time.own']}).read,false);
 assert.equal(payrollEntitlementRights({...caps(),permissions:['personnel.read','personnel.write']}).approve,false);
 assert.equal(payrollEntitlementRights(caps()).approve,true);
});
test('claim preview and accepted receipt cannot replace person, selected sources, prior case or plan',()=>{
 const v=f.sickness,body=clean(v.command),prior=v.history.items[0];
 for(const alter of[x=>x.source_snapshot.employee.id='f'.repeat(32),x=>x.source_snapshot.work_schedules[0].revision++,x=>x.plan.source_hash='f'.repeat(64),x=>x.kind='vacation_reference']){const bad=copy(v.preview);alter(bad);assert.throws(()=>payrollEntitlementPreview(bad,body));}
 for(const alter of[x=>x.details.case_key='f'.repeat(32),x=>x.revision++,x=>x.plan.gross_minor++,x=>x.source_hash='f'.repeat(64)]){const bad=copy(v.saved);alter(bad);assert.throws(()=>payrollEntitlementValidator(body,prior,v.preview)(bad));}
 const invalid=values(v);invalid.input.days[0].evidence_refs[0].content_hash='f'.repeat(64);assert.throws(()=>payrollEntitlementInput(body.employee_id,v.sources,body.kind,invalid,prior));
});
test('uncertain accepted claim retries only unchanged command with fresh global approval despite module pause',async()=>{
 const v=f.unpaid,body=clean(v.command),id=body.employee_id;let metadata=caps(),sources=copy(v.sources);
 sources.employee.revision++;sources.writes_enabled=false;metadata.organization.modules.personnel.enabled=false;
 const api={pendingCommandValues:()=>copy(body),get:async path=>path==='/business/capabilities'?metadata:sources},operation={key:'payroll-entitlements-'+id,path:'/business/payroll/entitlements'};
 await payrollEntitlementsPendingAuthorize(api,operation);assert.deepEqual(api.pendingCommandValues(),body);
 metadata={...caps(),permissions:['personnel.read','personnel.write']};await assert.rejects(payrollEntitlementsPendingAuthorize(api,operation),e=>e.status===403);
 metadata=caps();sources.employee_id='f'.repeat(32);await assert.rejects(payrollEntitlementsPendingAuthorize(api,operation));
});

test('explicit sickness v2 is additive, historical v1 persists and unknown versions fail closed',()=>{
 const history=copy(f.sickness.sources.entitlements.find(v=>v.kind==='sickness_history')),id=history.employee_id;
 payrollEntitlementRecord(history,id);history.plan.rule_version='de_2026_sickness_v2';payrollEntitlementRecord(history,id);history.plan.rule_version='de_2026_sickness_future';assert.throws(()=>payrollEntitlementRecord(history,id));
 const wrong=copy(f.unpaid.saved);wrong.plan.rule_version='de_2026_sickness_v2';assert.throws(()=>payrollEntitlementRecord(wrong,wrong.employee_id));
});
