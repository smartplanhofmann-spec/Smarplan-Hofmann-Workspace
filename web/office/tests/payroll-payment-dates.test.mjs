import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {accountRecord,accountReceiptValidator,payrollAccountDetails,payrollMultiplePaymentPlan} from '../payroll-accounts.js';
import {positiveCorrectionPaymentDetails,verifyPositiveCorrectionPaymentRecord,positiveCorrectionHash} from '../payroll-positive-correction.js';

const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/source5_payment_dates.json',import.meta.url)));
const clone=value=>structuredClone(value),key=value=>value.id+'@'+value.revision;
const money=value=>(value/100).toFixed(2);
function inputs(s){
  const d=s.details;
  return {run_ref:key(s.run),identity_ref:d.identity_id+'@'+d.identity_revision,prior_payment_ref:key(s.prior_payment),standard_case_confirmed:true,
    tax_free_payments_minor:money(d.tax_free_payments_minor),tax_free_basis:d.tax_free_basis,
    ...Object.fromEntries(d.payments.flatMap((p,i)=>[['paid_on_'+i,p.paid_on],['amount_'+i,money(p.amount_minor)],
      ['reference_'+i,p.payment_reference],['running_'+i,money(d.settlement_allocations[i].running_minor)],
      ['bonus_'+i,money(d.settlement_allocations[i].one_off_allocations.reduce((n,v)=>n+v.net_minor,0))]]))};
}

test('both actual accepted later-date originals and their hashes match complete preserved prefixes',async()=>{
  const before=JSON.stringify(fixture);
  for(const s of fixture.cases){
    accountRecord(s.payment,s.payment.employee_id,'payment');
    assert.equal(await verifyPositiveCorrectionPaymentRecord(s.payment),s.payment);
    const plan=await payrollMultiplePaymentPlan(s.details,s.run,s.prior_payment);
    assert.deepEqual(plan,s.payment.sources.single_payment_plan);
    assert.equal(plan.schema_version,3);assert.equal(plan.bonus_receipt_date,'2026-10-31');
    assert.match(plan.payments.at(-1).paid_on,/^2026-11-/);
    assert.deepEqual(plan.payments.slice(0,s.prior_payment.details.payments.length),s.prior_payment.details.payments);
    const receipt=accountReceiptValidator(s.command,s.prior_payment.source_file,null,{single_payment_plan:plan});
    assert.equal(await receipt(s.payment),s.payment);
  }
  assert.equal(JSON.stringify(fixture),before);
});

test('the actual-date input builder is explicit while the previous same-day mode remains strict',()=>{
  for(const s of fixture.cases){
    const sources={runs:[s.run],identities:[s.payment.sources.identity],payments:[s.prior_payment]};
    assert.deepEqual(payrollAccountDetails('payment',inputs(s),{...sources,paymentDates:true},s.details.payments.length),s.details);
    assert.throws(()=>payrollAccountDetails('payment',inputs(s),sources,s.details.payments.length));
    for(const day of ['2026-10-30','2027-01-01']){
      const d=clone(s.details);d.payments.at(-1).paid_on=day;
      assert.throws(()=>positiveCorrectionPaymentDetails(d,s.run,s.prior_payment));
    }
  }
});

test('self-consistent date, basis or contract substitution cannot replace the original receipt',async()=>{
  const s=fixture.cases[1];
  for(const change of ['date','basis','version','prefix']){
    const value=clone(s.payment),plan=value.sources.single_payment_plan;
    if(change==='date'){value.details.payments.at(-1).paid_on='2026-10-31';plan.payments.at(-1).paid_on='2026-10-31';}
    if(change==='basis')plan.settlement_date_basis='new_gross_receipt';
    if(change==='version'){value.details.payment_source_schema_version=2;plan.schema_version=2;}
    if(change==='prefix')value.details.payments[0].amount_minor++;
    const {plan_hash,...data}=plan;plan.plan_hash=await positiveCorrectionHash(data);
    await assert.rejects(async()=>verifyPositiveCorrectionPaymentRecord(value));
  }
});
