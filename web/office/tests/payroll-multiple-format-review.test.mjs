import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {accountRecord} from '../payroll-accounts.js';
const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/payroll_multiple_runs.json',import.meta.url))),copy=v=>structuredClone(v);
test('independent browser format review preserves actual Source5 and earlier paid v5 payment originals',()=>{for(const payment of [f.payment,f.paid_v5_upgrade.payment,f.paid_v5_upgrade.original_payment])assert.deepEqual(accountRecord(payment,payment.employee_id,'payment'),payment);});
for(const indicator of ['settlement_allocations','prior_payment_ref','single_payment_plan','v7_calculation'])test('independent browser format review refuses missing Source5 dispatch markers with remaining '+indicator,()=>{
 const bad=copy(f.paid_v5_upgrade.payment);delete bad.sources.run.source.source_schema_version;for(const key of ['payment_source_schema_version','settlement_allocations','prior_payment_ref'])if(key!==indicator)delete bad.details[key];if(indicator!=='single_payment_plan')delete bad.sources.single_payment_plan;if(indicator!=='v7_calculation')bad.sources.run.calculation.rule_version='de_2026_segments_entitlements_v5';assert.throws(()=>accountRecord(bad,bad.employee_id,'payment'));
});
for(const source of ['run_missing','version3'])test('independent browser format review refuses new settlement fields when '+source,()=>{const bad=copy(f.payment);delete bad.details.payment_source_schema_version;if(source==='run_missing')delete bad.sources.run;else bad.sources.run.source.source_schema_version=3;assert.throws(()=>accountRecord(bad,bad.employee_id));});
