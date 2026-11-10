import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {repaymentPaymentPlan,verifyRepaymentPaymentRecord,verifyRepaymentTransition,verifyRepaymentPreview,repaymentPaymentDetails} from '../payroll-repayment.js';
import {accountRecord,accountReceiptValidator,payrollAccountDetails} from '../payroll-accounts.js';
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/source5_repayment.json',import.meta.url)));
test('productive account reader, explicit input builder and sealed receipt retain negative originals',async()=>{
  accountRecord(f.payment,f.employee.id,'payment');
  const ref=v=>v.id+'@'+v.revision, money=v=>(v/100).toFixed(2),d=f.details;
  const values={run_ref:ref(f.run),identity_ref:d.identity_id+'@'+d.identity_revision,prior_payment_ref:ref(f.prior_payment),standard_case_confirmed:true,tax_free_payments_minor:'0.00',tax_free_basis:'',...Object.fromEntries(d.payments.flatMap((p,i)=>[['paid_on_'+i,p.paid_on],['amount_'+i,money(p.amount_minor)],['reference_'+i,p.payment_reference],['running_'+i,money(d.settlement_allocations[i].running_minor)],['bonus_'+i,money(d.settlement_allocations[i].one_off_allocations.reduce((n,a)=>n+a.net_minor,0))]]))};
  const sources={runs:[f.run],identities:[f.payment.sources.identity],payments:[f.prior_payment]};
  assert.throws(()=>payrollAccountDetails('payment',values,sources,d.payments.length));
  assert.deepEqual(payrollAccountDetails('payment',values,{...sources,repayments:true},d.payments.length),d);
  const receipt=accountReceiptValidator(f.payment_command,f.payment.source_file,null,{single_payment_plan:f.payment.sources.single_payment_plan});
  assert.equal(await receipt(f.payment),f.payment);
});
test('actual accepted repayment binds negative difference, unchanged original prefix and independently reproduced browser hashes',async()=>{
  await verifyRepaymentPreview(f.run_preview,f.run_input,{previous:f.prior_run});
  await verifyRepaymentTransition(f.run.settlement_transition,f.run,{previous:f.prior_run});
  assert.deepEqual(await repaymentPaymentPlan(f.details,f.run,f.prior_payment),f.payment.sources.single_payment_plan);
  assert.equal(await verifyRepaymentPaymentRecord(f.payment),f.payment);
});
test('repayment proof rejects a changed old transfer, positive new part, wrong original date and unknown version',()=>{
  for(const change of ['prefix','positive','early','version']){
    const details=structuredClone(f.details);
    if(change==='prefix')details.payments[0].amount_minor++;
    if(change==='positive')details.payments.at(-1).amount_minor=3900;
    if(change==='early')details.payments.at(-1).paid_on='2026-10-30';
    if(change==='version')details.payment_source_schema_version=3;
    assert.throws(()=>repaymentPaymentDetails(details,f.run,f.prior_payment));
  }
});
