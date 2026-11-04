import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {YV_INPUT,yvHash,yvPreview,yvVerifiedSource} from '../accounting-year-values-contract.js';
const fixture=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_year_values_v1.json',import.meta.url)));
const clone=structuredClone;
const input=command=>Object.fromEntries(YV_INPUT.map(k=>[k,command[k]]));
async function rehash(value,key){const {[key]:unused,...original}=value;value[key]=await yvHash(original);return value;}

test('independent original: unchanged real 59.50 cash history and 19.00 exercised VAT remain readable',async()=>{
 const s=fixture.complete;
 await yvPreview(s.preview,input(s.command),{openingItems:[s.old_item]});
 await yvVerifiedSource(s.source);
 assert.equal(s.preview.resolved_sources[0].record.prior_payments[0].gross,'59.50');
 assert.equal(s.preview.resolved_sources[0].record.prior_input_vat.amount,'19.00');
 assert.deepEqual(s.source.cash_movements,[]);
});

test('independent original: rehashed preview cannot move actual old payment from August to September',async()=>{
 const s=fixture.complete,p=clone(s.preview);
 const old=p.details.copied_rows.find(v=>v.kind==='cash_history');
 old.date='2026-09-20';
 for(const row of p.details.historical_postings.filter(v=>v.economic_key===old.economic_key))row.date=old.date;
 await rehash(p,'preview_hash');
 assert.equal(p.resolved_sources[0].record.prior_payments[0].date,'2026-08-20');
 assert.deepEqual(input(p),input(s.command));
 await assert.rejects(yvPreview(p,input(s.command),{openingItems:[s.old_item]}),'Derived date must match actual original payment');
});

test('independent original: rehashed preview cannot change old cash cents while leaving actual source unchanged',async()=>{
 const s=fixture.complete,p=clone(s.preview),old=p.details.copied_rows.find(v=>v.kind==='cash_history');
 old.net='50.01';old.gross='59.51';
 await rehash(p,'preview_hash');
 assert.equal(p.resolved_sources[0].record.prior_payments[0].gross,'59.50');
 await assert.rejects(yvPreview(p,input(s.command),{openingItems:[s.old_item]}),'Copied cents must match actual original payment and postings');
});

test('independent original: source hash alone cannot legitimize contradictory historical posting amount',async()=>{
 const s=clone(fixture.complete.source);
 s.details.historical_postings.find(v=>v.category==='materials').amount='-49.00';
 s.details.controls.find(v=>v.category==='materials').amount='-49.00';
 await rehash(s,'source_hash');
 assert.equal(s.details.copied_rows.find(v=>v.kind==='cash_history').net,'50.00');
 await assert.rejects(yvVerifiedSource(s),'Posting must match copied original cents, not merely controls');
});
