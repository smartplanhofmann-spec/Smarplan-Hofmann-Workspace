import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollStatement,payrollStatementBytes,payrollStatementJsonBytes,payrollStatementHash} from '../payroll-statements.js';

const fixture=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_statement_composites.json',import.meta.url)));
const copy=v=>JSON.parse(JSON.stringify(v));
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
async function rehash(v){const{statement_hash,pdf_sha256,pdf_size,...base}=v;v.statement_hash=await payrollStatementHash(new TextEncoder().encode(JSON.stringify(ordered(base))));return v;}

for(const original of fixture.cases)test(`actual own employee statement/PDF: ${original.source_fixture} ${original.kind}`,async()=>{
 const v=original.statement;
 assert.equal(v.schema_version,2);await payrollStatement(v,original.employee_id);
 await payrollStatementBytes(new Blob([Buffer.from(original.pdf_base64,'base64')]),v);
 await payrollStatementJsonBytes(new Blob([JSON.stringify(ordered(v))]),v);
 const text=JSON.stringify(v);
 for(const privateKey of ['profile','tax_id','social_insurance_number','source_file_ids','verification_note','factor_transition_assessment'])
  assert.equal(text.includes(`"${privateKey}":`),false,privateKey);
});

test('known composite rules cannot borrow another scope even with a recomputed narrow hash',async()=>{
 const examples=[...new Map(fixture.cases.map(x=>[x.statement.calculation.rule_version,x])).values()];
 for(const original of examples){
  const own=original.statement;
  for(const other of examples.filter(x=>x.statement.calculation.rule_version!==own.calculation.rule_version)){
   const bad=copy(own);bad.calculation.scope=other.statement.calculation.scope;await rehash(bad);
   await assert.rejects(payrollStatement(bad,original.employee_id),/Belegversion/);
  }
  const unknown=copy(own);unknown.calculation.rule_version='de_2026_unreviewed_future';await rehash(unknown);
  await assert.rejects(payrollStatement(unknown,original.employee_id),/Belegversion/);
 }
});

test('new narrow statements still refuse private additions, foreign employee and edited original PDF',async()=>{
 for(const original of fixture.cases){
  const bad=copy(original.statement);bad.calculation.profile={tax_factor:.753};await rehash(bad);
  await assert.rejects(payrollStatement(bad,original.employee_id));
  await assert.rejects(payrollStatement(original.statement,'f'.repeat(32)));
  const pdf=Buffer.from(original.pdf_base64,'base64');pdf[pdf.length-50]^=1;
  await assert.rejects(payrollStatementBytes(new Blob([pdf]),original.statement));
 }
});
