import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,copy,ref} from './source5-positive-fixture.mjs';
import {payrollAnnualRecord,payrollAnnualSources} from '../payroll-annual-basis.js';

test('actual annual basis after both positive corrections binds only the effective run and cumulative V2 payment',()=>{
  const evidence=fixture.annual_after_corrections,record=evidence.record,id=record.employee_id;
  const frozen=JSON.stringify(record);
  assert.equal(payrollAnnualRecord(record,id,'annual_basis'),record);
  assert.equal(payrollAnnualSources(evidence.sources,id),evidence.sources);
  assert.deepEqual(record.details.payroll_run_refs,[evidence.run_ref]);
  assert.deepEqual(record.details.payroll_payment_refs,[evidence.payment_ref]);
  assert.deepEqual(record.sources.payroll_runs.map(ref),[evidence.run_ref]);
  assert.deepEqual(record.sources.payroll_payments.map(ref),[evidence.payment_ref]);
  assert.deepEqual(evidence.run_ref,ref(fixture.second_correction.run));
  assert.deepEqual(evidence.payment_ref,ref(fixture.second_correction.payment));
  assert.equal(record.plan.earlier_other_taxable_minor,fixture.second_correction.run.calculation.multiple_one_off_details.amount_minor);
  assert.equal(record.plan.projection.prior_one_offs.length,1);
  assert.deepEqual(record.sources.payroll_payments[0].details.payments,fixture.second_correction.payment.details.payments);
  assert.equal(JSON.stringify(record),frozen);
});

test('annual consumer still rejects replaced effective run or foreign cumulative payment references',()=>{
  const record=fixture.annual_after_corrections.record;
  for(const change of [
    value=>value.sources.payroll_runs[0].revision--,
    value=>value.sources.payroll_payments[0].employee_id='f'.repeat(32),
    value=>value.details.payroll_payment_refs[0].content_hash='0'.repeat(64),
  ]){
    const value=copy(record);change(value);
    assert.throws(()=>payrollAnnualRecord(value,record.employee_id,'annual_basis'));
  }
});
