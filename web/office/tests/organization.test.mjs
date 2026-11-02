import test from 'node:test';
import assert from 'node:assert/strict';
import {
  OfficeApi, organizationMetadata, organizationSectionAllowed,
  organizationModuleEnabled, organizationCommandArea, organizationChange, organizationHiddenAreas,
} from '../office.js';

const areaNames=['personnel','material','planning','documents','finance'];
const needsNames=['has_employees','uses_inventory','project_work','uses_finance','works_with_tax_advisor'];
const config=()=>({revision:0,configured:false,modules:Object.fromEntries(areaNames.map(name=>[name,{visible:name!=='personnel',enabled:true}]))});
const capabilities=organization=>({features:['organization_modules'],organization});
const inputs=()=>Object.fromEntries([
  ...needsNames.map(name=>['needs_'+name,false]),
  ...areaNames.flatMap(name=>[['visibility_'+name,'auto'],['enabled_'+name,true]]),
]);

test('legacy servers keep their navigation without interpreting unnegotiated preferences',()=>{
  assert.equal(organizationMetadata({features:[],organization:{invalid:true}}),null);
  assert.equal(organizationSectionAllowed('personnel',true,null),true);
  assert.equal(organizationSectionAllowed('finance',false,null),false);
});

test('negotiated organization metadata must be complete and does not retain private fields',()=>{
  const original=config();original.active_employee_count=13;
  const actual=organizationMetadata(capabilities(original));
  assert.deepEqual(Object.keys(actual).sort(),['configured','modules','revision']);
  assert.equal(actual.modules.personnel.visible,false);
  original.modules.personnel.visible=true;
  assert.equal(actual.modules.personnel.visible,false);
  for(const invalid of [null,{...config(),revision:-1},{...config(),configured:'yes'},
    {...config(),modules:{personnel:{visible:false,enabled:true}}},
    {...config(),modules:{...config().modules,personnel:{visible:'false',enabled:true}}}]) {
    assert.throws(()=>organizationMetadata(capabilities(invalid)),error=>error.status===502);
  }
});

test('manual visibility, administrative history access and permission remain independent',()=>{
  const organization=organizationMetadata(capabilities(config()));
  assert.equal(organizationSectionAllowed('personnel',true,organization),false);
  assert.equal(organizationSectionAllowed('personnel',true,organization,true),true);
  assert.equal(organizationSectionAllowed('personnel',false,organization,true),false);
  assert.equal(organizationSectionAllowed('finance',false,organization),false);
  assert.equal(organizationSectionAllowed('settings',true,organization),true);
});

test('deactivation preserves the visible history and does not change other modules',()=>{
  const organization=config();organization.modules.personnel={visible:true,enabled:false};
  assert.equal(organizationSectionAllowed('personnel',true,organization),true);
  assert.equal(organizationModuleEnabled('personnel',organization),false);
  assert.equal(organizationModuleEnabled('planning',organization),true);
  assert.equal(organizationModuleEnabled(null,organization),true);
});

test('hidden history remains reachable without settings permission but never grants access',()=>{
  const organization=config();
  organization.modules.finance.visible=false;
  organization.modules.material.visible=false;
  organization.modules.personnel.enabled=false;
  const capabilities=['business_planning','business_finance','business_inventory'];
  assert.deepEqual(organizationHiddenAreas(organization,['time.own'],capabilities),['personnel']);
  assert.deepEqual(organizationHiddenAreas(organization,['finance.read'],capabilities),['material','finance']);
  assert.deepEqual(organizationHiddenAreas(organization,['settings.manage'],capabilities),[]);
  assert.deepEqual(organizationHiddenAreas(organization,['time.own'],['business_finance']),[]);
  assert.equal(organization.modules.personnel.visible,false);
  assert.equal(organization.modules.personnel.enabled,false);
});

test('form submission sends all needs and preserves automatic versus manual choices',()=>{
  const values=inputs();values.needs_has_employees=true;values.visibility_personnel='hide';values.visibility_material='show';values.enabled_finance=false;
  const result=organizationChange({revision:7,active_employee_count:9},values);
  assert.equal(result.revision,7);
  assert.deepEqual(Object.keys(result.needs).sort(),needsNames.toSorted());
  assert.equal(result.needs.has_employees,true);
  assert.deepEqual(result.modules.personnel,{visible:false,enabled:true});
  assert.deepEqual(result.modules.material,{visible:true,enabled:true});
  assert.deepEqual(result.modules.finance,{visible:null,enabled:false});
  assert.equal(result.active_employee_count,undefined);
  assert.equal(result.request_id,undefined);
  delete values.enabled_documents;
  assert.throws(()=>organizationChange({revision:7},values),/aller Module/);
  assert.throws(()=>organizationChange({revision:7},{...inputs(),needs_has_employees:'false'}),/vollständig/);
});

test('a lost organization save response resends the complete identical command',async()=>{
  const calls=[];const payload=organizationChange({revision:0},inputs());
  const api=new OfficeApi({fetcher:async(path,options)=>{
    calls.push({path,body:JSON.parse(options.body)});
    if(calls.length===1)throw new Error('Synthetic lost response after persistence');
    return new Response(JSON.stringify({...config(),revision:1,configured:true}),{headers:{'Content-Type':'application/json'}});
  }});
  api.setToken('synthetic-organization-session');
  await assert.rejects(api.mutate('organization-0','/business/organization',payload));
  assert.equal(api.pendingCount,1);
  await api.retry('organization-0');
  assert.deepEqual(calls[0],calls[1]);
  assert.match(calls[1].body.request_id,/^[a-f0-9]{32}$/);
  assert.equal(api.pendingCount,0);
});

test('temporary module deactivation preserves an uncertain command for exact retry after activation',async()=>{
  const calls=[];
  const api=new OfficeApi({fetcher:async(path,options)=>{
    calls.push({path,body:JSON.parse(options.body)});
    if(calls.length===1)throw new Error('Synthetic lost acknowledgement');
    if(calls.length===2)return new Response(JSON.stringify({error:'Bereich deaktiviert'}),{status:423});
    return new Response(JSON.stringify({id:'saved-once'}),{headers:{'Content-Type':'application/json'}});
  }});
  api.setToken('synthetic-activation-session');
  await assert.rejects(api.mutate('employee','/business/employees',{name:'Synthetic employee'}));
  await assert.rejects(api.retry('employee'),error=>error.status===423);
  assert.equal(api.pendingCount,1);
  assert.deepEqual(await api.retry('employee'),{id:'saved-once'});
  assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[0],calls[2]);
  assert.equal(api.pendingCount,0);
});

test('commands map to their real area while configuration remains reachable',()=>{
  for(const [path,expected] of [
    ['/employees','personnel'],['/employees/id','personnel'],['/absences/id/approve','personnel'],
    ['/shifts/id','personnel'],['/time/events','personnel'],['/resources','planning'],
    ['/appointments/id','planning'],['/planning/projects/id/dates','planning'],
    ['/inventory/orders','material'],['/budgets','material'],
    ['/projects/id/changes/change-id/approve','material'],['/documents/id/finalize','documents'],
    ['/articles','documents'],['/commercial/pricing/preview','documents'],
    ['/adapters/imports/import-id/apply','documents'],['/adapters/imports/import-id/offer','documents'],
    ['/adapters/imports/import-id',null],
    ['/finance/payments','finance'],['/commercial/settings',null],
    ['/settings/branding',null],['/organization',null],['/service-reports/id/sign',null],
    ['/employees-extra',null],
  ])assert.equal(organizationCommandArea(path),expected,path);
});
