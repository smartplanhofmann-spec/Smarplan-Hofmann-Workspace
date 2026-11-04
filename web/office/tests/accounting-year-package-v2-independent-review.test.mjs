import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {yearPackageExport, yearPackageMetadata, yearPackageArchive} from '../accounting-year-package-contract.js';

const fixtures = version => JSON.parse(readFileSync(new URL(`../../../docs/fixtures/accounting_year_package_v${version}.json`,import.meta.url)));
const old = fixtures(1), current = fixtures(2);
const blob = scenario => new Blob([Buffer.from(scenario.archive_base64,'base64')], {type:'application/zip'});

for (const [name, scenario] of Object.entries(current.scenarios)) {
  test(`independent actual V2 ${name} stays bound to retained export and separately read metadata`, async () => {
    assert.deepEqual(await yearPackageExport(scenario.export),scenario.export);
    assert.deepEqual(yearPackageMetadata(scenario.metadata,scenario.export),scenario.metadata);
    await yearPackageArchive(blob(scenario),scenario.metadata);
    assert.equal(scenario.metadata.original_year_complete,name==='complete_history');
    for (const prior of Object.values(old.scenarios)) {
      assert.throws(()=>yearPackageMetadata(prior.metadata,scenario.export));
      await assert.rejects(yearPackageArchive(blob(prior),scenario.metadata));
    }
  });
}

test('independent new reader preserves every actual V1 export/metadata/archive',async()=>{
  for(const scenario of Object.values(old.scenarios)) {
    await yearPackageExport(scenario.export);
    yearPackageMetadata(scenario.metadata,scenario.export);
    await yearPackageArchive(blob(scenario),scenario.metadata);
  }
});

test('independent historical partial V2 is unchanged after actual new complete correction',()=>{
  assert.deepEqual(current.scenarios.old_partial_after_correction,current.scenarios.partial_coverage);
  assert.notEqual(current.scenarios.partial_coverage.metadata.sha256,current.scenarios.complete_history.metadata.sha256);
  assert.throws(()=>yearPackageMetadata(current.scenarios.complete_history.metadata,current.scenarios.partial_coverage.export));
});

test('independent V2 metadata cannot switch versions or external archive anchor after initial read',()=>{
  const scenario=current.scenarios.complete_history;
  for(const patch of [{format:'smartplan-year-evidence-v1'},{format:'smartplan-year-evidence-v3'},{sha256:'a'.repeat(64)},{instance_id:'f'.repeat(32)}]) {
    assert.throws(()=>yearPackageMetadata({...scenario.metadata,...patch},scenario.export,scenario.metadata));
  }
});

test('independent altered V2 ZIP cannot use its own newly computed hash as the previous external anchor',async()=>{
  const scenario=current.scenarios.complete_history;
  const changed=Buffer.from(scenario.archive_base64,'base64');changed[Math.floor(changed.length/2)]^=1;
  await assert.rejects(yearPackageArchive(new Blob([changed],{type:'application/zip'}),scenario.metadata));
  assert.throws(()=>yearPackageMetadata({...scenario.metadata,original_year_complete:false},scenario.export));
  assert.throws(()=>yearPackageMetadata({...scenario.metadata,private_personnel_originals_included:true},scenario.export));
});
