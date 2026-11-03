import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  payrollTravelTaxPolicyDetails, payrollTravelTaxPolicyInput,
  payrollTravelTaxPolicyRecord, payrollTravelTaxPolicySources,
  payrollTravelTaxPolicyPreview, payrollTravelTaxPolicyValidator,
  payrollTravelTaxPoliciesAuthorize, payrollTravelTaxPolicyRights,
} from '../payroll-travel-tax-policies.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_travel_tax_policies.json',import.meta.url)));
const copy=value=>structuredClone(value), clean=body=>{const value=copy(body);delete value.request_id;return value;};

test('real employer policy fixture binds exact original files and null person without inventing dates',()=>{
  const body=payrollTravelTaxPolicyInput(f.sources_before,{details:f.body.details,source_file_ids:f.body.source_file_ids});
  const expected=clean(f.body);delete expected.preview_hash;
  assert.deepEqual(body,expected);assert.equal(body.employee_id,null);assert.equal(body.employee_revision,null);
  assert.deepEqual(payrollTravelTaxPolicySources(f.sources),f.sources);
  assert.deepEqual(payrollTravelTaxPolicyRecord(f.saved),f.saved);
});

test('filing windows require actual complete month quarter or year and real calendar dates',()=>{
  for(const [from,to]of [['2026-02-01','2026-02-28'],['2026-07-01','2026-09-30'],['2026-01-01','2026-12-31']]){
    assert.equal(payrollTravelTaxPolicyDetails({...f.body.details,filing_period_from:from,filing_period_to:to}).filing_period_to,to);
  }
  for(const [from,to]of [['',''],['2026-02-01','2026-02-29'],['2026-02-01','2026-04-30'],['2026-10-02','2026-12-31'],['2025-10-01','2025-12-31']]){
    assert.throws(()=>payrollTravelTaxPolicyDetails({...f.body.details,filing_period_from:from,filing_period_to:to}));
  }
});

test('method region and actual economic cost choice remain explicit and coherent',()=>{
  for(const change of [{church_method:''},{employer_bears_tax:null},{employer_bears_tax:1},{church_method_applies_to_all:false},
      {church_rate_region:'ni_ev_westfalen',federal_state:'BW'},{church_rate_region:'bw_bad_wimpfen_mainz',federal_state:'NI'},{chosen_tax_minor:0}]){
    assert.throws(()=>payrollTravelTaxPolicyDetails({...f.body.details,...change}));
  }
  assert.equal(payrollTravelTaxPolicyDetails({...f.body.details,employer_bears_tax:false}).employer_bears_tax,false);
});

test('source and accepted policy cannot substitute employee scope original reference or version',()=>{
  for(const mutate of [v=>v.employee_id='a'.repeat(32),v=>v.file_references[0].content_hash='0'.repeat(64),v=>v.files.push(copy(v.files[0])),v=>v.policies.push(copy(v.policies[0]))]){
    const value=copy(f.sources);mutate(value);assert.throws(()=>payrollTravelTaxPolicySources(value));
  }
  for(const mutate of [v=>v.employee_id='a'.repeat(32),v=>v.source_contract_version=true,v=>v.sources.schema_version=true,v=>v.sources.policy.employer_bears_tax=false,
      v=>v.source_file_ids.push(v.source_file_ids[0]),v=>v.sources.source_files.push(copy(v.sources.source_files[0]))]){
    const value=copy(f.saved);mutate(value);assert.throws(()=>payrollTravelTaxPolicyRecord(value));
  }
});

test('preview and accepted response bind original policy body and immutable source snapshot',()=>{
  const body=clean(f.body),proof=copy(f.preview);
  assert.deepEqual(payrollTravelTaxPolicyPreview(proof,body),proof);
  const validate=payrollTravelTaxPolicyValidator(body,null,proof);
  body.details.verification_note='Later changed editor';proof.source_snapshot.policy.verification_note='Later changed preview';
  assert.deepEqual(validate(f.saved),f.saved);
  const changed=copy(f.saved);changed.details.verification_note='Changed result';changed.sources.policy.verification_note='Changed result';
  assert.throws(()=>validate(changed));
  const extra=copy(f.preview);extra.source_snapshot.source_files.push(copy(extra.source_snapshot.source_files[0]));
  assert.throws(()=>payrollTravelTaxPolicyPreview(extra,clean(f.body)));
});

test('correction and void retain exact predecessor and original policy source',()=>{
  payrollTravelTaxPolicyValidator(clean(f.correction_body),f.saved,f.correction_preview)(f.corrected);
  payrollTravelTaxPolicyValidator(clean(f.void_body),f.corrected)(f.void);
  const wrong=copy(f.void);wrong.previous_hash=f.saved.content_hash;
  assert.throws(()=>payrollTravelTaxPolicyValidator(clean(f.void_body),f.corrected)(wrong));
  assert.throws(()=>payrollTravelTaxPolicyInput(f.sources,{details:{...f.saved.details,filing_period_from:'2026-11-01',filing_period_to:'2026-11-30'},source_file_ids:f.saved.source_file_ids,correction_reason:'Changed scope'},f.saved));
});

test('fresh global authority and explicit paused replay remain separate from new writes',async()=>{
  const state={caps:copy(f.capabilities),sources:copy(f.sources)};
  const api={get:async path=>copy(path==='/business/capabilities'?state.caps:state.sources)};
  assert.equal((await payrollTravelTaxPoliciesAuthorize(api,{write:true})).rights.approve,true);
  state.caps.permissions=['personnel.read'];
  await assert.rejects(payrollTravelTaxPoliciesAuthorize(api,{write:true}),error=>error.status===403);
  assert.equal((await payrollTravelTaxPoliciesAuthorize(api)).rights.read,true);
  state.caps=copy(f.capabilities);state.sources.can_approve=false;
  await assert.rejects(payrollTravelTaxPoliciesAuthorize(api,{write:true}),error=>error.status===403);
  state.sources.can_approve=true;state.sources.writes_enabled=false;state.caps.organization.modules.personnel.enabled=false;
  await assert.rejects(payrollTravelTaxPoliciesAuthorize(api,{write:true}),error=>error.status===423);
  assert.equal((await payrollTravelTaxPoliciesAuthorize(api,{write:true,replay:true})).sources.writes_enabled,false);
  assert.equal(payrollTravelTaxPolicyRights({...f.capabilities,permissions:[]}).read,false);
});
