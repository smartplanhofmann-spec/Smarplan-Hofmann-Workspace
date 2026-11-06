import test from 'node:test';
import assert from 'node:assert/strict';
import {projectContext,organizationHiddenAreas} from '../office.js';

test('company-wide destinations clear a previously selected project',()=>{
  for(const section of ['overview','inquiries','contacts','personnel','settings','unknown']) {
    const scope=projectContext(section,'previous-project');
    assert.equal(scope.projectId,'');
    assert.equal(scope.label,null);
  }
});

test('project workspace and real project filters have distinct labels',()=>{
  assert.deepEqual(projectContext('projects','selected-project'),{
    projectId:'selected-project',label:'Projekt öffnen',all:'Projektübersicht',
  });
  for(const section of ['planning','documents','finance','material','assistant','service'])
    assert.deepEqual(projectContext(section,'selected-project'),{
      projectId:'selected-project',label:'Projektfilter',all:'Alle Projekte',
    });
});

test('leaving a project for a company page then returning opens the project list',()=>{
  const active=projectContext('projects','selected-project');
  const company=projectContext('personnel',active.projectId);
  const returned=projectContext('projects',company.projectId);
  assert.equal(returned.projectId,'');
  assert.equal(returned.all,'Projektübersicht');
});

test('hidden company areas use global rights while hidden project areas retain scoped grants',()=>{
  const organization={modules:{personnel:{visible:false},documents:{visible:false}}};
  const capabilities=new Set(['business_planning','business_documents']);
  const global=new Set(['time.own']);
  const scoped=new Set(['documents.read']);
  assert.deepEqual(organizationHiddenAreas(organization,scoped,capabilities,global),['personnel','documents']);
  assert.deepEqual(organizationHiddenAreas(organization,global,capabilities,global),['personnel']);
});
