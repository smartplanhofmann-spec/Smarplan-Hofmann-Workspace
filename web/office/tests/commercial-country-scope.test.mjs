import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {commercialCountryScopeView} from '../office.js';

const fixture=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/commercial-country-scope.json',import.meta.url),'utf8'));
const settings=country=>({country,revision:2,issuing_enabled:false});

test('actual German scope describes the boundary without changing issuing settings',()=>{
  const company=settings('DE'),before=structuredClone(company),view=commercialCountryScopeView(fixture.DE,company);
  assert.equal(view.unsupported,false);assert.match(view.message,/Deutschland/);
  assert.deepEqual(company,before);assert.equal(company.issuing_enabled,false);
});
test('unsupported issuer keeps the precise country and never chooses German rules',()=>{
  for(const country of ['AT','CH']){
    const view=commercialCountryScopeView(fixture[country],settings(country));
    assert.equal(view.unsupported,true);assert.match(view.message,new RegExp(country));assert.match(view.message,/nicht unterstützt/);
    assert.equal(fixture[country].selected,null);
  }
});
test('changed configuration and partial or substituted packages cannot produce a supported display',()=>{
  for(const value of [
    {...fixture.DE,settings_revision:1}, {...fixture.DE,issuer_country:'AT'},
    {...fixture.DE,supported_issuer:false}, {...fixture.DE,selected:{...fixture.DE.selected,currency:'CHF'}},
    {...fixture.DE,supported:[]}, {...fixture.DE,scope_note:''}, {...fixture.DE,schema_version:2},
  ])assert.throws(()=>commercialCountryScopeView(value,settings('DE')),/neu laden/);
});
