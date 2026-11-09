import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {travelV3Calculation} from '../travel-allowances.js';

const fixture=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/travel_provenance_workflow.json',import.meta.url)));

test('actual archived CRLF travel values remain readable with original hashes',()=>{
  const old=structuredClone(fixture.record.calculation),frozen=JSON.stringify(old),refs=fixture.record.details.trip_refs;
  assert.notEqual(old.rule_hash,fixture.calculation_lf.rule_hash);
  assert.equal(old.totals.tax_free_minor,933);
  assert.deepEqual(travelV3Calculation(old,refs),old);
  assert.equal(JSON.stringify(old),frozen);
  assert.deepEqual(travelV3Calculation(fixture.calculation_lf,refs),fixture.calculation_lf);
});

test('archived CRLF travel still needs linked originals and complete metadata',()=>{
  for(const change of [
    value=>value.ground_calendar_sources[0].trip.revision++,
    value=>value.mixed_program_sources[0].facts_hash='invalid',
    value=>value.mixed_program_sources[0].source_file_ids=[],
  ]){
    const old=structuredClone(fixture.record.calculation);change(old);
    assert.throws(()=>travelV3Calculation(old,fixture.record.details.trip_refs));
  }
});
