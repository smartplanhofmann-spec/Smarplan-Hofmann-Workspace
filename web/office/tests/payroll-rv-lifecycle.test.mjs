import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {payrollRvSources,payrollRvAssessment,payrollRvInput,payrollRvPreviewInput,payrollRvPreview,
 payrollRvRecordHashes,payrollRvValidator,payrollRvAuthorize,payrollRvPendingAuthorize,payrollRvProfileBinding,payrollRvSelection,RV_PATH,RV_RULE} from '../payroll-rv-lifecycle.js';
import {payrollProfileValidator} from '../payroll.js';
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_rv_lifecycle.json',import.meta.url)));
const clone=v=>structuredClone(v),cases=fixture.cases;
const manyFiles=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_rv_lifecycle_many_files.json',import.meta.url)));
const caps=()=>({features:['payroll_rv_lifecycle'],capabilities:['business_payroll_rv_lifecycle'],permissions:['personnel.read','personnel.approve'],readonly:false,organization:{modules:{personnel:{enabled:true}}}});
function values(c){const a=c.input.details.assessment,r=a.revocation;return{...a,exempt_from:a.established_exemption.effective_from,original_profile_id:payrollRvSelection(a.established_exemption.profile_ref),exemption_file_id:a.established_exemption.evidence_ref.id,established_status_confirmed:true,request_state:r?'received':'none',received_on:r?.received_on||'',request_format:r?.request_format||'',request_file_id:r?.request_ref.id||'',notification_received_on:r?.notification_received_on||'',notification_file_id:r?.notification_ref?.id||'',authority_status:r?.authority_status||'',objection_deadline_on:r?.objection_deadline_on||'',deadline_file_id:r?.deadline_ref?.id||'',deadline_review_confirmed:r?.deadline_review_confirmed||false,authority_status_on:r?.authority_status_on||'',authority_file_id:r?.authority_evidence_ref?.id||'',procedure_note:r?.review_note||''};}

for(const c of cases)test('actual original '+c.name+' stays bound through input, preview and receipt',async()=>{
 const s=payrollRvSources(clone(c.sources_before),c.employee.id),body=payrollRvInput(s,values(c));
 assert.deepEqual(payrollRvPreviewInput(body),c.input);
 const preview=await payrollRvPreview(clone(c.preview),body);
 const command={...body,preview_hash:preview.preview_hash};
 assert.deepEqual(await payrollRvValidator(command,preview)(clone(c.record)),c.record);
 assert.deepEqual(await payrollRvRecordHashes(clone(c.record),c.employee.id),c.record);
 assert.equal(preview.plan.can_bind_payroll,c.name!=='pending');
});

test('changed private evidence, source, rule or decision hashes are rejected',async()=>{
 const c=cases.at(-1);
 for(const change of [v=>v.source_snapshot.source_files[0].sha256='f'.repeat(64),v=>v.plan.rules_sha256='f'.repeat(64),v=>v.preview_hash='f'.repeat(64),v=>v.plan.external_transmission=true,v=>v.plan.minijob_rv_exempt=true,v=>v.source_snapshot.prior_assessments.push({reference:c.record.details.assessment.established_exemption.profile_ref,assessment:c.input.details.assessment})]){
  const v=clone(c.preview);change(v);await assert.rejects(()=>payrollRvPreview(v,c.input));
 }
 const pending=clone(cases[1].preview);pending.plan.can_bind_payroll=pending.plan.can_determine=true;pending.plan.blockers=[];pending.plan.minijob_rv_exempt=false;pending.plan.status='compulsory_after_revocation';
 await assert.rejects(()=>payrollRvPreview(pending,cases[1].input));
});

test('wrong person, incomplete prefix and bool version cannot enter the client contract',()=>{
 const c=cases.at(-1);
 for(const edit of [s=>s.employee.id='f'.repeat(32),s=>s.prior_assessment_refs=[],s=>s.files[0].employee_id='f'.repeat(32),s=>s.history[0].source_contract_version=true]){
  const s=clone(c.sources);edit(s);assert.throws(()=>payrollRvSources(s,c.employee.id));
 }
 const a=clone(c.input.details.assessment);a.schema_version=true;assert.throws(()=>payrollRvAssessment(a));
});

test('the explicit profile binding is part of the complete accepted profile',()=>{
 const c=cases.at(-1),s=clone(c.sources);
 assert.throws(()=>payrollRvProfileBinding(s,{}));
 const binding=payrollRvProfileBinding(s,{rv_lifecycle_id:payrollRvSelection(c.record)});
 assert.deepEqual(binding,{rv_lifecycle_source_contract_version:1,rv_lifecycle_ref:{id:c.record.id,revision:1,content_hash:c.record.content_hash}});
 const file=s.files.find(v=>v.id===c.profile_command.source_file_id),validate=payrollProfileValidator(c.profile_command,file);
 assert.deepEqual(validate(clone(c.profile)),c.profile);
 for(const change of [v=>delete v.rv_lifecycle_ref,v=>v.rv_lifecycle_source_contract_version=true,v=>v.rv_lifecycle_ref.content_hash='f'.repeat(64)]){
  const v=clone(c.profile);change(v);assert.throws(()=>validate(v));
 }
});

test('an ID alone or another revision cannot float to the newest original',()=>{
 const c=cases.at(-1),s=clone(c.sources);
 for(const selection of [c.record.id,payrollRvSelection({...c.record,revision:2}),payrollRvSelection({...c.record,content_hash:'f'.repeat(64)})])assert.throws(()=>payrollRvProfileBinding(s,{rv_lifecycle_id:selection}));
 const input=values(c);input.original_profile_id=c.input.details.assessment.established_exemption.profile_ref.id;
 assert.throws(()=>payrollRvInput(c.sources_before,input));
});

test('101 actual private file originals do not exceed the selected RV evidence limit',()=>{
 const page=payrollRvSources(clone(manyFiles.sources),manyFiles.sources.employee_id);
 assert.equal(page.files.length,101);assert.equal(page.history[0].source_file_ids.length,1);
});

test('a pending procedure may hold its actually reviewed future deadline without becoming settled',()=>{
 const a=clone(cases.at(-1).input.details.assessment);
 a.target_month='2026-08';a.reviewed_as_of='2026-08-01';
 a.revocation.authority_status='pending';a.revocation.authority_status_on=null;a.revocation.authority_evidence_ref=null;
 assert.equal(payrollRvAssessment(a).revocation.objection_deadline_on,'2026-08-21');
 a.revocation.notification_received_on='2026-08-02';assert.throws(()=>payrollRvAssessment(a));
});

test('current rights are checked before private sources and exact pending replay',async()=>{
 const c=cases.at(-1),calls=[];let rights=caps(),source=clone(c.sources);
 const api={get:async path=>{calls.push(path);return path==='/business/capabilities'?rights:source;},pendingCommandValues:()=>c.command};
 assert.equal((await payrollRvAuthorize(api,c.employee.id,{write:true})).sources.employee_id,c.employee.id);
 assert.equal(await payrollRvPendingAuthorize(api,{key:'payroll-rv-lifecycle-'+c.employee.id,path:RV_PATH}),true);
 rights.permissions=[];calls.length=0;
 await assert.rejects(()=>payrollRvAuthorize(api,c.employee.id));assert.deepEqual(calls,['/business/capabilities']);
 rights=caps();source.can_approve=false;await assert.rejects(()=>payrollRvPendingAuthorize(api,{key:'payroll-rv-lifecycle-'+c.employee.id,path:RV_PATH}));
 source.can_approve=true;source.writes_enabled=false;
 await assert.rejects(()=>payrollRvAuthorize(api,c.employee.id,{write:true}));
 assert.equal(await payrollRvPendingAuthorize(api,{key:'payroll-rv-lifecycle-'+c.employee.id,path:RV_PATH}),true);
 const original=clone(c.command);api.pendingCommandValues=()=>({...original,rule_version:RV_RULE+'-other'});
 await assert.rejects(()=>payrollRvPendingAuthorize(api,{key:'payroll-rv-lifecycle-'+c.employee.id,path:RV_PATH}));
 assert.deepEqual(original,c.command);
});
