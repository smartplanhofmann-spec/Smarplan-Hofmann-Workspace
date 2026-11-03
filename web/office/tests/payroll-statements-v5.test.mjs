import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollStatement} from '../payroll-statements.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_statements_v5.json',import.meta.url))),copy=v=>JSON.parse(JSON.stringify(v));
test('actual v5 employee projection includes own travel and claim values with deducted payout',async()=>{await payrollStatement(f,f.employee_id);assert.equal(f.schema_version,2);assert.equal(f.calculation.net_deductions_minor,109);assert.equal(f.calculation.payout_minor,172977);assert.equal(f.travel_summary.tax_free_external_minor,1400);});
test('narrow v5 projection rejects raw sources, unknown claim kinds and missing net deductions',async()=>{for(const change of[v=>v.earnings_summary[0].source_refs=[],v=>v.travel_summary.policy={},v=>v.earnings_summary[0].kind='private_claim',v=>v.calculation.payout_minor+=109,v=>v.calculation.net_deductions_minor=0,v=>v.schema_version=1]){const bad=copy(f);change(bad);await assert.rejects(payrollStatement(bad,f.employee_id));}});
