import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollStatement,payrollStatementPage,payrollStatementBytes,payrollStatementJsonBytes,payrollStatementHash} from '../payroll-statements.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_statements_v7.json',import.meta.url)));
const order=v=>Array.isArray(v)?v.map(order):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,order(v[k])])):v;
async function rehash(v){const {statement_hash,pdf_sha256,pdf_size,...base}=v;v.statement_hash=await payrollStatementHash(new TextEncoder().encode(JSON.stringify(order(base))));return v;}

test('actual single Source5 own schema4 binds exact JSON/PDF and retained original v5 history',async()=>{
  for(const v of [f.statement,f.previous])await payrollStatement(v,f.employee.id);
  await payrollStatementPage(f.page,f.employee.id);await payrollStatementPage(f.history,f.employee.id);
  assert.equal(f.statement.schema_version,4);assert.equal(f.statement.one_off_summary.amount_minor,50000);
  assert.equal(f.statement.calculation.payout_minor-f.previous.calculation.payout_minor,39125);
  await payrollStatementBytes(new Blob([Buffer.from(f.pdf_base64,'base64')]),f.statement);
  await payrollStatementJsonBytes(new Blob([Buffer.from(f.json_base64,'base64')]),f.statement);
  await payrollStatementBytes(new Blob([Buffer.from(f.previous_pdf_base64,'base64')]),f.previous);
});
test('rehashing cannot introduce Source5 private IDs, alternate version, unproved net or tax amounts',async()=>{
  for(const change of [v=>v.event_key='a'.repeat(32),v=>v.one_off_summary.component_key='b'.repeat(32),v=>v.one_off_summary.source={},
    v=>v.one_off_summary.employee_contributions.earning_ref={},v=>v.one_off_summary.annual_pay_before_minor=1,
    v=>v.schema_version=3,v=>v.calculation.rule_version='de_2026_oneoff_composition_v6',v=>v.calculation.scope='regular_standard_oneoff',
    v=>v.calculation.payroll_calculation_complete=false,v=>v.one_off_summary.amount_minor++,v=>v.one_off_summary.receipt_date='2026-10-30',
    v=>v.one_off_summary.tax_year=2025,v=>v.one_off_summary.employee_social_total_minor++,v=>v.calculation.individual_wage_tax_minor++]){
    const bad=structuredClone(f.statement);change(bad);await rehash(bad);
    if(bad.one_off_summary.receipt_date==='2026-10-30')await assert.rejects(payrollStatementJsonBytes(new Blob([JSON.stringify(bad)]),f.statement));
    else await assert.rejects(payrollStatement(bad,f.employee.id));
  }
});
test('JSON download checks entire selected original and rejects UTF8 errors, unknown fields and older valid statements',async()=>{
  for(const bytes of [Buffer.from('{}'),Buffer.from([255,254]),Buffer.from(Buffer.from(f.json_base64,'base64').toString().replace('{','{\"employee_name\":\"PRIVATE-DUPLICATE-SHADOW\",')),Buffer.from(JSON.stringify(f.previous)),Buffer.from(JSON.stringify({...f.statement,source:{}}))])
    await assert.rejects(payrollStatementJsonBytes(new Blob([bytes]),f.statement));
  const old=structuredClone(f.statement);old.employee_name='Changed historical original';await rehash(old);
  await assert.rejects(payrollStatementJsonBytes(new Blob([JSON.stringify(old)]),f.statement));
  await assert.rejects(payrollStatementJsonBytes(new Blob([new Uint8Array(1024*1024+1)]),f.statement));
});
