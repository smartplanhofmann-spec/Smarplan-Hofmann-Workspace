import test from 'node:test';
import assert from 'node:assert/strict';
import {timeEntry, timeCorrectionInput, timeCorrectionReceipt, timeCorrectionAllowed, timeCorrectionLabel, timeTrackingUi} from '../time-tracking.js';

const id = character => character.repeat(32);
const entry = () => ({id: id('a'), employee_id: id('b'), project_id: id('c'), status: 'partially_approved',
  worked_seconds: 7200, break_seconds: 0, events: [], corrections: [],
  work_dates: ['2026-11-03', '2026-11-04'], approved_work_dates: ['2026-11-03']});
const values = () => ({work_date: '2026-11-03', delta_minutes: -30, reason: '  Belegte Pause ergänzt.  ', confirmed: true});
const caps = () => ({readonly: false, permissions: ['time.approve'], capabilities: ['business_time']});

test('correction binds exact approved server day, signed integer minutes and reason', () => {
  const source = entry(), before = structuredClone(source);
  assert.deepEqual(timeCorrectionInput(source, values()), {work_date: '2026-11-03', delta_seconds: -1800, reason: 'Belegte Pause ergänzt.'});
  assert.deepEqual(source, before);
  for (const change of [{work_date: '2026-11-04'}, {work_date: '2026-11-02'}, {confirmed: false},
    {delta_minutes: 0}, {delta_minutes: .5}, {delta_minutes: 1441}, {delta_minutes: NaN}, {delta_minutes: '30'}, {reason: '  '}])
    assert.throws(() => timeCorrectionInput(source, {...values(), ...change}));
});

test('clock result and correction receipt must refer to actual selected originals and actor', () => {
  const source = entry(), body = timeCorrectionInput(source, values());
  assert.equal(timeEntry(source, source), source);
  for (const change of [{id: id('d')}, {employee_id: id('d')}, {project_id: id('d')},
    {approved_work_dates: ['2026-11-05']}, {work_dates: undefined}])
    assert.throws(() => timeEntry({...source, ...change}, source));
  const receipt = {id: id('e'), entry_id: source.id, ...body, created_by: id('f'), created_at: '2026-11-04T12:00:00+00:00'};
  assert.equal(timeCorrectionReceipt(receipt, source.id, body, id('f')), receipt);
  for (const change of [{entry_id: id('d')}, {work_date: '2026-11-04'}, {delta_seconds: 1800}, {reason: 'Other'}, {created_by: id('a')}])
    assert.throws(() => timeCorrectionReceipt({...receipt, ...change}, source.id, body, id('f')));
});

test('correction requires current permission, time capability and active write mode', () => {
  assert.equal(timeCorrectionAllowed(caps()), true);
  for (const change of [{readonly: true}, {readonly: undefined}, {permissions: ['time.own']}, {capabilities: []},
    {active_capabilities: []}, {organization: {modules: {personnel: {enabled: false}}}}])
    assert.equal(timeCorrectionAllowed({...caps(), ...change}), false);
});

test('history retains exact signed seconds for corrections smaller than a minute', () => {
  assert.equal(timeCorrectionLabel(-1), '−1 Sek.');
  assert.equal(timeCorrectionLabel(90), '+90 Sek.');
  assert.equal(timeCorrectionLabel(-1800), '−30 Min.');
});

test('late original read cannot reopen a dialog after the context changes', async () => {
  let release, stamp = 1, opened = 0;
  const pending = new Promise(resolve => { release = resolve; });
  const ui = timeTrackingUi({api: {get: () => pending}, biz: value => value,
    stamp: () => stamp, allowed: () => true, dialog: () => opened++});
  const opening = ui.open(entry());
  stamp++;
  release(entry());
  await opening;
  assert.equal(opened, 0);
});
