import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollStatement, payrollStatementPage, payrollStatementBytes, payrollStatementHash} from '../payroll-statements.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_statements_v6.json',import.meta.url)));
const copy=value=>structuredClone(value), order=value=>Array.isArray(value)?value.map(order):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,order(value[k])])):value;
async function rehash(value){const {statement_hash,pdf_sha256,pdf_size,...base}=value;value.statement_hash=await payrollStatementHash(new TextEncoder().encode(JSON.stringify(order(base))));return value;}

test('actual v6 own statement, v5 original, March assignment and independent PDF remain bound',async()=>{
  for(const value of [f.statement,f.previous,f.march])await payrollStatement(value,value.employee_id);
  await payrollStatementPage(f.page,f.employee.id);await payrollStatementPage(f.history,f.employee.id);
  assert.equal(f.statement.schema_version,3);assert.equal(f.statement.one_off_summary.amount_minor,50000);
  assert.equal(f.statement.calculation.payout_minor-f.previous.calculation.payout_minor,39125);
  assert.equal(f.statement.calculation.net_deductions_minor,109);
  assert.equal(f.statement.travel_summary.tax_free_external_minor,1400);
  assert.equal(f.march.one_off_summary.social_year,2025);assert.equal(f.march.one_off_summary.tax_year,2026);
  for(const [statement,bytes] of [[f.statement,f.pdf_base64],[f.previous,f.previous_pdf_base64]])await payrollStatementBytes(new Blob([Buffer.from(bytes,'base64')]),statement);
});
test('rehashing cannot admit private annual material, invalid year split or inconsistent bonus money',async()=>{
  const changes=[v=>v.one_off_summary.annual_pay_before_minor=1,v=>v.one_off_summary.earning_ref={},
    v=>v.one_off_summary.employee_contributions.profile={},v=>v.one_off_summary.receipt_date='2026-11-01',
    v=>v.one_off_summary.tax_year=2025,v=>v.one_off_summary.social_year=2025,
    v=>{v.one_off_summary.social_year=2025;v.one_off_summary.march_clause=true;},
    v=>v.one_off_summary.employee_social_total_minor++,v=>v.one_off_summary.individual_wage_tax_minor=v.calculation.individual_wage_tax_minor+1,
    v=>v.one_off_summary.amount_minor++,v=>v.calculation.net_deductions_minor=0,
    v=>v.schema_version=2,v=>v.calculation.rule_version='de_2026_segments_entitlements_v5',
    v=>v.calculation.scope='regular_standard_segments',v=>v.one_off_summary.amount_minor=0,v=>v.calculation.individual_wage_tax_minor=null,v=>v.calculation.individual_wage_tax_minor++];
  for(const change of changes){const bad=copy(f.statement);change(bad);await rehash(bad);await assert.rejects(payrollStatement(bad,f.employee.id));}
});
test('employee PDF bytes and selected historical reference cannot be swapped',async()=>{
  await assert.rejects(payrollStatement(f.statement,f.employee.id,f.previous.run_ref));
  await assert.rejects(payrollStatementBytes(new Blob([Buffer.from(f.previous_pdf_base64,'base64')]),f.statement));
  await assert.rejects(payrollStatementPage({...f.page,items:[f.statement,f.statement]},f.employee.id));
});
