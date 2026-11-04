import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollCalculation,payrollPreview,payrollRunValidator,payrollLedger,payrollExportBytes} from '../payroll.js';
import {payrollOneOffCaseRunInput} from '../payroll-oneoff-cases.js';
import {accountRecord,accountReceiptValidator,payrollAccountNoPaymentDue} from '../payroll-accounts.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_oneoff_runs.json',import.meta.url)));
const copy=v=>JSON.parse(JSON.stringify(v)),id=f.run.employee_id;

test('actual Source4 accepted run uses the general payroll preview, receipt and archive readers',async()=>{
 assert.deepEqual(payrollOneOffCaseRunInput(f.saved),f.run_input);
 assert.equal(payrollCalculation(f.run.calculation).scope,'regular_standard_oneoff');
 payrollPreview(f.run_preview,f.run_input);
 payrollRunValidator(f.run_command,f.run_preview)(f.run);
 await payrollExportBytes(new Blob([JSON.stringify(f.run)]),'json',f.run);
 const c=f.run.calculation;
 assert.equal(c.period_details.travel.flat_taxable_payroll_minor,400);
 assert.equal(c.net_deductions_minor,109);
 assert.equal(c.payout_minor,c.net_minor-109);
});

test('general Source4 preview rejects swapped original running case, bonus and employee',()=>{
 for(const change of [v=>v.source.employee_id='f'.repeat(32),v=>v.source.calculation_case.id='f'.repeat(32),v=>v.source.one_off_case.details.one_off_earning_ref.id='f'.repeat(32),v=>v.source.input.source_schema_version=3,v=>v.calculation.net_deductions_minor=0,v=>v.calculation.running_calculation.net_minor++]){
  const bad=copy(f.run_preview);change(bad);assert.throws(()=>payrollPreview(bad,f.run_input));
 }
});

test('Source4 receipt binds frozen sources and original run hash after a lost response',()=>{
 const command=copy(f.run_command),preview=copy(f.run_preview),validate=payrollRunValidator(command,preview);
 command.employee_id='f'.repeat(32);preview.calculation.net_minor++;
 validate(f.run);
 for(const change of [v=>v.source.one_off_case.source_hash='f'.repeat(64),v=>v.accepted_scope='regular_standard_segments',v=>v.delta={},v=>v.pdf_sha256='bad',v=>v.calculation.net_minor++]){
  const bad=copy(f.run);change(bad);assert.throws(()=>validate(bad));
 }
});

test('actual Source4 account payment and year totals retain original net deductions and actual receipt date',async()=>{
 accountRecord(f.payment,id,'payment');
 assert.equal(payrollAccountNoPaymentDue(f.run),false);
 accountReceiptValidator(f.payment_command,f.payment.source_file,null,f.payment.sources)(f.payment);
 await payrollLedger(f.ledger,id,2026);
 const m=f.ledger.ledger.months.find(m=>m.run_id===f.run.id);
 assert.equal(m.wage_account.payable_minor,f.run.calculation.payout_minor);
 assert.equal(m.wage_account.payment_status,'payments_evidenced');
 for(const change of [v=>v.details.payments[0].paid_on='2026-11-01',v=>v.details.payments[0].amount_minor++,v=>v.details.payments=[],v=>v.sources.run.calculation.net_deductions_minor=0,v=>v.details.run_revision++]){
  const bad=copy(f.payment);change(bad);assert.throws(()=>accountRecord(bad,id,'payment'));
 }
});

for(const [name,section,previous]of [['Source4 bonus correction',f.correction,f.run],['already paid v5 upgrade',f.paid_v5_upgrade,f.paid_v5_upgrade.original_run]])test(name+' preserves original run identity, full delta and original paid part',()=>{
 payrollPreview(section.run_preview,section.run_input);
 payrollRunValidator(section.run_command,section.run_preview,previous)(section.run);
 assert.equal(section.run.id,previous.id);
 assert.equal(section.run.previous_hash,previous.content_hash);
 assert.equal(section.run.delta.payout_minor,section.run.calculation.payout_minor-previous.calculation.payout_minor);
 assert.equal(section.run.delta.net_deductions_minor,0);
 accountRecord(section.payment,section.run.employee_id,'payment');
 const original=name==='already paid v5 upgrade'?f.paid_v5_upgrade.original_payment:f.payment;
 assert.deepEqual(section.payment.details.payments[0],original.details.payments[0]);
 assert.equal(section.payment.details.payments[1].amount_minor,section.run.delta.payout_minor);
 const omitted=copy(section.run);delete omitted.delta.payout_minor;
 assert.throws(()=>payrollRunValidator(section.run_command,section.run_preview,previous)(omitted));
});
