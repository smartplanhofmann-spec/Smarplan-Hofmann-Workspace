import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {webcrypto} from 'node:crypto';
import {factorClaimTravelPlan,factorClaimTravelBindings,factorClaimTravelInput,
 verifyFactorClaimTravelCase,verifyFactorClaimTravelRun} from '../payroll-factor-claim-travel.js';
globalThis.crypto??=webcrypto;
const fixture=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_factor_claim_travel.json',import.meta.url),'utf8'));
const clone=structuredClone;

for(const c of fixture.cases){
 test('actual complete13 component/source/preview/run proofs: '+c.kind,async()=>{
  assert.equal(factorClaimTravelPlan(c.case.plan),c.case.plan);
  factorClaimTravelBindings(c.case.sources,c.case.details,c.case.plan);
  assert.equal(await verifyFactorClaimTravelCase(c.case_preview),c.case_preview);
  assert.equal(await verifyFactorClaimTravelCase(c.case),c.case);
  assert.equal(await verifyFactorClaimTravelRun(c.run_preview),c.run_preview);
 });
 test('actual complete13 explicit original selection and unused upgrade: '+c.kind,()=>{
  const body=factorClaimTravelInput(c.employee.id,c.sources,c.values,c.previous);
  const expected={...c.case_command};delete expected.request_id;delete expected.preview_hash;
  assert.deepEqual(body,expected);
  assert.equal(body.details.travel_payment_refs.length,1);
  assert.equal(body.details.entitlement_case_refs.length,1);
 });
}

test('hourly original remains zero actual work; only the evidenced P4 wage satisfies its exact review',()=>{
 const c=fixture.cases.find(c=>c.kind==='hourly'),p=c.case.plan;
 assert.equal(c.period.plan.gross_minor,0);assert.equal(c.period.plan.can_calculate,false);
 assert.equal(p.gross_minor,320000);assert.equal(p.components.paid_travel.plan.can_calculate,false);
 assert.deepEqual(p.components.paid_travel.plan.blockers.map(v=>v.code),['zero_earnings_requires_review']);
 assert.deepEqual(p.satisfied_travel_component_wage_reviews,['zero_earnings_requires_review']);
 assert.equal(p.can_calculate,true);
 const changed=clone(p);changed.satisfied_travel_component_wage_reviews=[];
 assert.throws(()=>factorClaimTravelPlan(changed));
});

test('original payment and P4 omissions, duplicate choices and implicit upgrades never produce commands',()=>{
 const c=fixture.cases[0];
 for(const field of ['entitlement_case_ids','travel_settlement_ids','travel_payment_ids']){
  const v=clone(c.values);v[field]=[];assert.throws(()=>factorClaimTravelInput(c.employee.id,c.sources,v));
 }
 const duplicate=clone(c.values);duplicate.travel_payment_ids.push(duplicate.travel_payment_ids[0]);
 assert.throws(()=>factorClaimTravelInput(c.employee.id,c.sources,duplicate));
 const u=fixture.cases.find(c=>c.previous);
 assert.throws(()=>factorClaimTravelInput(u.employee.id,u.sources,{...u.values,confirm_unused_upgrade:false},u.previous));
 const changed=clone(u.previous);changed.sources.period_case.content_hash='0'.repeat(64);
 assert.throws(()=>factorClaimTravelInput(u.employee.id,u.sources,u.values,changed));
});

test('changed component gross, paid sum, projection, source and run cannot pass original hashes',async()=>{
 const c=fixture.cases[0];
 for(const change of [
  v=>v.plan.gross_minor++,v=>v.plan.travel_paid_minor++,
  v=>v.plan.components.paid_travel.projection='GUESS_AN_UNBOUND_PAYMENT',
  v=>v.plan.components.claims.source_snapshot_hash='0'.repeat(64),
  v=>v.sources.travel_sources[0].payment_proof.payments[0].amount_minor++,
 ]){const altered=clone(c.case);change(altered);await assert.rejects(verifyFactorClaimTravelCase(altered));}
 const altered=clone(c.run_preview);altered.calculation.payout_minor+=1400;
 await assert.rejects(verifyFactorClaimTravelRun(altered));
});
