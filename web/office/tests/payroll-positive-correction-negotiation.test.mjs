import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {payrollPreview,payrollRunValidator} from '../payroll.js';
import {accountRecord} from '../payroll-accounts.js';

const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_multiple_runs.json',import.meta.url)));
const original=fixture.paid_v5_upgrade;
const review=()=>({schema_version:1,payments_complete:true,remittances_complete:true,evidence_ref:{
  id:original.payment.source_file.id,revision:1,content_hash:original.payment.source_file.content_hash,
}});

test('a real v1 preview remains v1; adding review without its derived transition is refused',()=>{
  payrollPreview(original.run_preview,original.run_input);
  const input={...structuredClone(original.run_input),settlement_review:review()};
  const preview=structuredClone(original.run_preview);
  preview.source.input=input;
  assert.throws(()=>payrollPreview(preview,input));
});

test('a review-bearing request cannot use the old synchronous receipt path',()=>{
  payrollRunValidator(original.run_command,original.run_preview,original.original_run)(original.run);
  const command={...structuredClone(original.run_command),settlement_review:review()};
  const preview=structuredClone(original.run_preview);
  preview.source.input.settlement_review=review();
  assert.throws(()=>payrollRunValidator(command,preview,original.original_run));
});

test('an archived v1 payment cannot acquire an unbound completeness review',()=>{
  accountRecord(original.payment,original.run.employee_id,'payment');
  const payment=structuredClone(original.payment);
  payment.sources.run.source.input.settlement_review=review();
  assert.throws(()=>accountRecord(payment,original.run.employee_id,'payment'));
});
