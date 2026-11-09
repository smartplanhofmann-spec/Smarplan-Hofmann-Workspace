import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollOneOffCaseRecord,payrollOneOffSource} from '../payroll-oneoff-cases.js';
import {payrollMultipleCaseRecord,payrollMultipleSource} from '../payroll-multiple-cases.js';
import {payrollMultiplePaymentPlan} from '../payroll-accounts.js';

const fixture=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/oneoff_provenance_workflow.json',import.meta.url)));
const cases=[['single','one_off_case',payrollOneOffCaseRecord,payrollOneOffSource],
  ['multiple','multiple_one_off_case',payrollMultipleCaseRecord,payrollMultipleSource]];

test('actual accepted CRLF v6/v7 originals retain their complete source and monetary contract',()=>{
  for(const [name,key,record,source]of cases){
    const f=fixture[name],v=structuredClone(f.preview),before=JSON.stringify(v),fact=v.source[key];
    assert.notDeepEqual(fact.plan,f.calculation_lf);
    assert.equal(fact.plan.net_minor,f.calculation_lf.net_minor);
    assert.deepEqual(record(fact,fact.employee_id),fact);
    assert.deepEqual(source(v,v.source.input),v);
    assert.equal(JSON.stringify(v),before);
  }
});

test('archived v6/v7 views still reject substituted sources and monetary amounts',()=>{
  for(const [name,key,,source]of cases){
    for(const change of [v=>v.calculation.net_minor++,v=>v.source[key].details.current_annual_basis_ref.revision++]){
      const value=structuredClone(fixture[name].preview);change(value);
      assert.throws(()=>source(value,value.source.input));
    }
  }
});

test('actual CRLF original v1 payment plan binds its accepted run and unchanged prior payment',async()=>{
  const paid=fixture.multiple_payment,run={...paid.run_metadata,...fixture.multiple.preview};
  assert.deepEqual(await payrollMultiplePaymentPlan(paid.details,run,paid.prior_payment),paid.plan);
  const bad=structuredClone(paid.details);bad.payments[1].amount_minor++;
  await assert.rejects(payrollMultiplePaymentPlan(bad,run,paid.prior_payment));
});
