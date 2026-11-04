import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {harness,base,block} from './accounting-year-values-independent-harness.mjs';
import {YV_INPUT,yvState,yvPreview,yvReceipt} from '../accounting-year-values-contract.js';
const all=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_year_values_native_independent_v1.json',import.meta.url))),scenario=all.void_after_missing_start;
function setup(){const h=harness({accepted:true});let accepted=false,override=null;h.fixtureHook=fn=>override=fn;h.state=scenario.initial_state;h.hook(async r=>{const custom=await override?.(r);if(custom)return custom;
 if(r.path===base)return Response.json(accepted?scenario.state_after_acceptance:scenario.initial_state);
 if(r.path===base+'/preview')return Response.json(scenario.preview);
 if(r.path===base+'/confirm'){accepted=true;return Response.json(scenario.entry);}
 if(r.path===base+'/history?entity_key=2026')return Response.json(scenario.history);
});return h;}
test('profile-void: actual backend evidence has prior block, original EÜR reversal and genuinely accepted void with no current start',async()=>{
 assert.equal(scenario.blocked_before_reverse.status,409);assert.equal(scenario.euer_reverse.reverses,scenario.euer_posted.id);assert.equal(scenario.initial_state.profile,null);assert.equal(scenario.initial_state.can_prepare,false);
 await yvState(scenario.initial_state);await yvPreview(scenario.preview,Object.fromEntries(YV_INPUT.map(k=>[k,scenario.command[k]])));await yvReceipt(scenario.command,scenario.preview,scenario.initial_state)(scenario.entry);
 assert.deepEqual(scenario.command.profile_ref,scenario.original_entry.profile_ref);assert.deepEqual(scenario.command.payload,{...scenario.original_entry.payload,status:'void'});
});
test('profile-void: existing original can be explicitly voided through browser despite missing current profile, with exact old facts',async()=>{
 const h=setup();await h.yearUi.detail('2026');assert.equal(h.title,'Belegter Jahresvortrag 2026');assert.equal(h.find(n=>n.tag==='button'&&n.label==='Belegte Jahresfassung berichtigen'),null);
 await h.button('Fälschlichen Jahresvortrag aufheben').run();assert.equal(h.title,'Fälschlichen Jahresvortrag ausdrücklich aufheben');await h.form().save({reason:scenario.command.reason});assert.equal(h.title,'Jahresvortrag ausdrücklich bestätigen');await h.form().save({accepted:true});
 assert.equal(h.title,'Belegter Jahresvortrag 2026');assert.equal(h.api.pendingCount,0);const calls=h.requests.filter(r=>r.path===base+'/confirm');assert.equal(calls.length,1);const actual={...calls[0].body},expected={...scenario.command};delete actual.request_id;delete expected.request_id;assert.deepEqual(actual,expected);
 await h.button('Unveränderliche Jahresfassungen öffnen').run();assert.equal(h.title,'Unveränderliche Jahresfassungen');assert.equal(h.requests.filter(r=>r.path.includes('/euer/confirm')).length,0);
});
for(const loss of ['write','module'])test('profile-void: missing-current-profile exception cannot bypass current '+loss+' restriction',async()=>{
 const h=setup();if(loss==='write')h.permission.permissions=h.permission.permissions.filter(p=>p!=='finance.write');else h.permission.organization.modules.finance.enabled=false;
 await h.yearUi.detail('2026');assert.equal(h.find(n=>n.tag==='button'&&n.label==='Fälschlichen Jahresvortrag aufheben'),null);assert.equal(h.find(n=>n.tag==='button'&&n.label==='Belegte Jahresfassung berichtigen'),null);assert.equal(h.requests.filter(r=>r.method==='POST').length,0);
});

test('profile-void: original accepted void after lost ACK retries exact nonce despite still missing current profile',async()=>{
 const h=setup();await h.yearUi.detail('2026');await h.button('Fälschlichen Jahresvortrag aufheben').run();await h.form().save({reason:scenario.command.reason});h.fixtureHook(async r=>{if(r.path===base+'/confirm')throw Error('Accepted void ACK lost');});await h.form().save({accepted:true});assert.equal(h.api.pendingCount,1);
 h.close();h.fixtureHook(async r=>r.path===base?Response.json(scenario.state_after_acceptance):null);await h.yearUi.detail('2026');await h.button('Unverändert erneut senden').run();assert.equal(h.api.pendingCount,0);const calls=h.requests.filter(r=>r.path===base+'/confirm');assert.equal(calls.length,2);assert.deepEqual(calls[0].body,calls[1].body);
});
test('profile-void: write rights lost after opening original void dialog block even a preview POST',async()=>{
 const h=setup();await h.yearUi.detail('2026');await h.button('Fälschlichen Jahresvortrag aufheben').run();const editor=h.form();h.permission.permissions=h.permission.permissions.filter(p=>p!=='finance.write');await editor.save({reason:scenario.command.reason});assert.equal(h.requests.filter(r=>r.method==='POST').length,0);assert.equal(h.title,'Jahreswerte nicht freigegeben');
});
test('profile-void: genuinely superseded original after opening dialog cannot be used for a stale second void',async()=>{
 const h=setup();await h.yearUi.detail('2026');await h.button('Fälschlichen Jahresvortrag aufheben').run();const editor=h.form();h.fixtureHook(async r=>r.path===base?Response.json(scenario.state_after_acceptance):null);await editor.save({reason:scenario.command.reason});assert.equal(h.requests.filter(r=>r.method==='POST').length,0);assert.notEqual(h.title,'Jahresvortrag ausdrücklich bestätigen');
});
