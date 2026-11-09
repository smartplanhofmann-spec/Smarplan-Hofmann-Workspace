import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,copy,values} from './source5-positive-fixture.mjs';
import {payrollPreview,payrollRunValidator,payrollExportBytes} from '../payroll.js';
import {accountRecord,accountReceiptValidator,payrollAccountDetails,payrollMultiplePaymentPlan} from '../payroll-accounts.js';
import {positiveCorrectionHash,positiveCorrectionReview,verifyPositiveCorrectionPreview,verifyPositiveCorrectionTransition,verifyPositiveCorrectionPaymentRecord} from '../payroll-positive-correction.js';

const sections=['correction','second_correction'];
const sources=s=>({runs:[s.run],identities:s.sources.identities,payments:[s.prior_payment]});
async function rehash(value){
  const t=value.settlement_transition,{source_hash,...observation}=t.remittance_observation;
  t.remittance_observation.source_hash=await positiveCorrectionHash(observation);
  const {transition_hash,...body}=t;t.transition_hash=await positiveCorrectionHash(body);
  value.preview_hash=await positiveCorrectionHash({source:value.source,calculation:value.calculation,settlement_transition:t});
  return value;
}

test('actual initial v1 remains unchanged and both positive corrected originals bind their complete previews and receipts',async()=>{
  const first=fixture.initial;
  assert.equal(payrollPreview(first.run_preview,first.run_input),first.run_preview);
  assert.equal(payrollRunValidator(first.run_command,first.run_preview)(first.run),first.run);
  assert.equal(Object.hasOwn(first.run,'settlement_transition'),false);
  for(const name of sections){
    const s=fixture[name],frozen=JSON.stringify(s);
    assert.equal(await payrollPreview(s.run_preview,s.run_input),s.run_preview);
    assert.equal(await verifyPositiveCorrectionPreview(s.run_preview,s.run_input,{previous:s.prior_run}),s.run_preview);
    assert.equal(await payrollRunValidator(s.run_command,s.run_preview,s.prior_run)(s.run),s.run);
    assert.equal(await payrollExportBytes(new Blob([JSON.stringify(s.run)]),'json',s.run) instanceof Uint8Array,true);
    assert.equal(JSON.stringify(s),frozen);
  }
});

test('actual v1-to-v2 and v2-to-v2 payment plans preserve every old part and exact original allocation',async()=>{
  for(const name of sections){
    const s=fixture[name],frozen=JSON.stringify(s),details=payrollAccountDetails('payment',values(s),sources(s),s.payment.details.payments.length);
    assert.deepEqual(details,s.payment.details);
    const plan=await payrollMultiplePaymentPlan(details,s.run,s.prior_payment);
    assert.deepEqual(plan,s.payment.sources.single_payment_plan);
    assert.deepEqual(plan.payments.slice(0,s.prior_payment.details.payments.length),s.prior_payment.details.payments);
    assert.deepEqual(plan.allocations.slice(0,s.prior_payment.details.payments.length),s.prior_payment.details.settlement_allocations);
    accountRecord(s.payment,s.employee.id,'payment');
    assert.equal(await verifyPositiveCorrectionPaymentRecord(s.payment),s.payment);
    assert.equal(await accountReceiptValidator(s.payment_command,s.payment.source_file,null,s.payment.sources)(s.payment),s.payment);
    assert.equal(JSON.stringify(s),frozen);
  }
});

test('missing, downgraded or unrelated review and transition bindings cannot become original run receipts',async()=>{
  const s=fixture.correction;
  for(const change of [v=>delete v.settlement_transition,v=>v.settlement_transition=null]){
    const bad=copy(s.run_preview);change(bad);
    await assert.rejects(async()=>payrollPreview(bad,s.run_input));
  }
  const body=copy(s.run_command);delete body.settlement_review;
  assert.throws(()=>payrollRunValidator(body,s.run_preview,s.prior_run));
  const wrong=copy(s.run_command);wrong.settlement_review.remittances_complete=false;
  await assert.rejects(payrollRunValidator(wrong,s.run_preview,s.prior_run)(s.run));
  for(const change of [v=>v.settlement_transition.previous_run_ref.content_hash='0'.repeat(64),v=>delete v.settlement_transition]){
    const bad=copy(s.run);change(bad);
    await assert.rejects(payrollRunValidator(s.run_command,s.run_preview,s.prior_run)(bad));
  }
});

test('rehashed changes still cannot replace old money, original event, assignment or remittance bounds',async()=>{
  const s=fixture.correction;
  for(const change of [
    v=>{v.settlement_transition.prior_total_net_minor--;v.settlement_transition.additional_net_minor++;},
    v=>v.settlement_transition.old_composition_hash='0'.repeat(64),
    v=>v.settlement_transition.event_key='0'.repeat(32),
    v=>v.settlement_transition.prior_payment_ref.revision=2,
    v=>v.settlement_transition.remittance_observation.amounts.employee_tax=v.calculation.employee_tax_minor+1,
    v=>v.settlement_transition.remittance_observation.entries=[{id:'a'.repeat(32),revision:2,sequence:1,private_hash:'b'.repeat(64)}],
  ]){
    const bad=copy(s.run_preview);change(bad);await rehash(bad);
    await assert.rejects(verifyPositiveCorrectionPreview(bad,s.run_input,{previous:s.prior_run}));
  }
  for(const field of ['payments_complete','remittances_complete']){
    const review=copy(s.run_input.settlement_review);review[field]=false;
    assert.throws(()=>positiveCorrectionReview(review));
  }
});

test('payment changes cannot erase or relabel original prefixes, change the original day or invent extra net',async()=>{
  for(const s of sections.map(name=>fixture[name])){
    for(const change of [
      d=>d.payments.shift(),
      d=>d.payments.reverse(),
      d=>d.payments[1].payment_reference='Changed old actual transfer',
      d=>{d.settlement_allocations[1].running_minor=d.payments[1].amount_minor;d.settlement_allocations[1].one_off_allocations=[];},
      d=>d.payments.at(-1).paid_on='2026-11-01',
      d=>d.payments.at(-1).amount_minor++,
      d=>d.payments.at(-1).amount_minor=-1,
      d=>d.prior_payment_ref.content_hash='0'.repeat(64),
    ]){
      const d=copy(s.payment.details);change(d);
      await assert.rejects(payrollMultiplePaymentPlan(d,s.run,s.prior_payment));
    }
    const prior=copy(s.prior_payment);prior.details.payments[1].payment_reference='Changed prior evidence';
    await assert.rejects(payrollMultiplePaymentPlan(s.payment.details,s.run,prior));
  }
});

test('archived corrected payments require exact plan hashes, transition hashes and false side-effect flags',async()=>{
  const s=fixture.second_correction;
  for(const change of [
    p=>p.sources.single_payment_plan.plan_hash='0'.repeat(64),
    p=>p.sources.single_payment_plan.transition_hash='0'.repeat(64),
    p=>p.sources.single_payment_plan.composition_hash='0'.repeat(64),
    p=>p.sources.single_payment_plan.actual_payment_created=true,
    p=>p.sources.single_payment_plan.new_payment_indexes=[0,3],
    p=>p.sources.single_payment_plan.preserved_prior_payment_indexes=[0,1],
    p=>p.details.payment_source_schema_version=1,
  ]){
    const bad=copy(s.payment);change(bad);
    await assert.rejects(verifyPositiveCorrectionPaymentRecord(bad));
  }
  const run=copy(s.run);run.preview_hash='0'.repeat(64);
  await assert.rejects(verifyPositiveCorrectionTransition(run.settlement_transition,run));
});
