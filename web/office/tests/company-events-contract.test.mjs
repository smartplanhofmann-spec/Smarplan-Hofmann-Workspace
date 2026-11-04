import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {eventStatus,eventRule,eventRuleHistory,eventObservation,eventPlan,eventRun,eventPage,eventReceipt,eventHash,eventConditions,eventMoney} from '../company-events-contract.js';
const fixture=JSON.parse(await readFile(new URL('../../../docs/fixtures/company_events_2026.json',import.meta.url)));
const copy=value=>JSON.parse(JSON.stringify(value));
for(const scenario of ['auto','approval','deny','project_approval','external_unknown','external_unconfirmed'])test('actual dispatcher company-event fixture: '+scenario,async()=>{
  const f=fixture[scenario];eventStatus(f.status);eventRule(f.rule);await eventRuleHistory(f.rule_history,f.rule.id);
  await eventReceipt('/company-events/rules',f.rule_command,f.rule);
  await eventReceipt('/company-events/scan',f.scan_command,f.scan);await eventRun(f.scan_replay);
  for(const kind of ['events','plans','runs'])await eventPage(f[kind],kind);
  for(const p of f.plans.items)await eventPlan(p,f.events.items.find(e=>e.id===p.event_id));
  if(f.approved)await eventReceipt('/company-events/plans/'+f.approved.id+'/approve',f.approve_command,f.approved);
  if(f.executed)await eventReceipt('/company-events/plans/'+f.executed.id+'/execute',f.execute_command,f.executed);
});
test('foreign fully valid run receipt cannot confirm original scan',async()=>{
  await assert.rejects(eventReceipt('/company-events/scan',fixture.approval.scan_command,fixture.auto.scan),/ursprünglichen/);
});
test('changed original event, plan or source cannot pass preserved source hash',async()=>{
  const event=copy(fixture.approval.events.items[0]);event.source.data.details='Foreign original';await assert.rejects(eventObservation(event),/Originalhash/);
  const plan=copy(fixture.approval.plans.items[0]);plan.parameters.title='Foreign task';await assert.rejects(eventPlan(plan),/Planhash/);
  await assert.rejects(eventPlan(fixture.approval.plans.items[0],fixture.auto.events.items[0]),/Ereignis/);
});
test('project-policy text and visible projection both bind unchanged historical original',async()=>{
  const plan=copy(fixture.project_approval.plans.items[0]);plan.policy.project_policies[0].policy.mode='auto';await assert.rejects(eventPlan(plan),/Projektregelprojektion/);
});
test('large monetary conditions keep exact cents; money is never rounded',()=>{
  const conditions=eventConditions('payment.overdue',[{field:'open_minor',operator:'gte',value:'90071992547409,93'}],fixture.approval.status);
  assert.equal(conditions[0].value,'9007199254740993');assert.equal(eventMoney(conditions[0].value),'90.071.992.547.409,93 €');
  assert.throws(()=>eventConditions('payment.overdue',[{field:'open_minor',operator:'gte',value:'1.001'}],fixture.approval.status));
});
test('recomputed acceptance hash alone cannot replace the selected plan',async()=>{
  const f=fixture.approval,raw=copy(f.executed);raw.id='f'.repeat(32);raw.acceptance.request_hash=await eventHash(['execute:'+f.executed.id,f.execute_command]);
  await assert.rejects(eventReceipt('/company-events/plans/'+f.executed.id+'/execute',f.execute_command,raw));
});

test('accepted external claim without result remains unconfirmed and cannot authorize new action',async()=>{const f=fixture.external_unconfirmed;assert.equal(f.synthetic_transport_calls,1);for(const result of [f.executed,f.execute_replay]){await eventReceipt('/company-events/plans/'+result.id+'/execute',f.execute_command,result);assert.equal(result.status,'unconfirmed');assert.equal(result.outcome,null);assert.equal(result.can_execute,false);}const forged=copy(f.executed);forged.status='succeeded';await assert.rejects(eventReceipt('/company-events/plans/'+forged.id+'/execute',f.execute_command,forged));});
