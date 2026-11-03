import test from 'node:test';
import assert from 'node:assert/strict';
import {TravelCommand, travelMinor, travelLocalTime, travelCanonical,
  travelHash, travelReceipt, travelOriginal, travelTimeOptions, travelReference,
  travelPreview} from '../travel-allowances.js';

const employee = 'a'.repeat(32), actor = 'b'.repeat(32), trip = 'c'.repeat(32);
const hash = 'd'.repeat(64), root = '/business/personnel/travel';
const clone = value => JSON.parse(JSON.stringify(value));
function fixture() {
  const state = {stamp: 1, actor, read: true, write: true, active: true,
    lose: false, accepted: true, posts: [], receipts: new Map(), foreign: null};
  state.api = {
    get: async path => {
      if (path === '/me') return {id: state.actor};
      if (path.endsWith('/capabilities')) return {features: ['travel_allowances'],
        capabilities: ['business_travel_allowances'], readonly: false};
      if (path.includes('/sources?')) return {employee: {id: employee, user_id: actor},
        rights: {read: state.read, write: state.write, approve: state.write, payments: state.write},
        active: state.active, readonly: false};
      if (path.includes('/requests/')) {
        const receipt = state.receipts.get(path.split('/').at(-1));
        if (!receipt) throw Object.assign(new Error('Not found'), {status: 404});
        return {...clone(receipt), ...(state.foreign || {})};
      }
      throw new Error('Unexpected read');
    },
    post: async (path, body) => {
      state.posts.push({path, body: clone(body)});
      if (state.accepted && !state.receipts.has(body.request_id)) {
        const result = {id: trip, employee_id: employee, revision: 1, status: 'draft',
          details: {purpose: body.details.purpose}};
        state.receipts.set(body.request_id, {request_id: body.request_id, actor_id: actor,
          employee_id: employee, operation: 'trip.save', target_kind: 'trip', target_id: trip,
          revision: 1, request_hash: await travelHash(['trip.save', 'trip', trip, body]),
          result_hash: await travelHash(result), confirmed: true, result});
      }
      if (state.lose) {state.lose = false; throw Object.assign(new Error('Lost reply'), {status: 0});}
      return {};
    },
  };
  state.command = new TravelCommand(state.api, {employeeId: employee, stamp: () => state.stamp});
  state.submit = body => state.command.submit(root + '/trips', body || {
    employee_id: employee, id: trip, revision: 0, details: {purpose: 'PRIVATE Reise'}},
  {operation: 'trip.save', targetKind: 'trip', targetId: trip});
  return state;
}

test('travel money is exact; missing values differ from explicit zero; local time keeps its civil zone', () => {
  assert.equal(travelMinor('14,05'), 1405);
  assert.equal(travelMinor('0', {zero: true}), 0);
  for (const value of ['', null, '-1', '1.234', '1e2', '1,002']) assert.throws(() => travelMinor(value, {zero: true}));
  assert.equal(travelLocalTime('2026-10-25T02:30'), '2026-10-25T02:30');
  for (const value of ['2026-02-29T12:00', '2026-11-03T24:00', '', '2026-11-03']) assert.throws(() => travelLocalTime(value));
  assert.equal(travelCanonical({z: ['ä', 1, false], a: null}), '{"a":null,"z":["ä",1,false]}');
  assert.throws(() => travelCanonical({amount: 1.1}));
});

test('ambiguous local clock needs the actual offset, impossible clock does not silently normalize', () => {
  const local = '2026-10-25T02:30', timezone = 'Europe/Berlin';
  const options = ['+02:00', '+01:00'].map(offset => ({instant: local + ':00' + offset, offset, label: offset}));
  assert.equal(travelTimeOptions({local, timezone, options, valid: true}, local, timezone).length, 2);
  assert.throws(() => travelTimeOptions({local, timezone, options: [], valid: false}, local, timezone), /existiert/);
  assert.throws(() => travelTimeOptions({local, timezone: 'UTC', options, valid: true}, local, timezone), /Zeitauflösung/);
});

test('lost accepted acknowledgement resolves by status only, including module pause', async () => {
  const f = fixture(); f.lose = true;
  const body = {employee_id: employee, id: trip, revision: 0, details: {purpose: 'PRIVATE Original'}};
  await assert.rejects(f.submit(body), /Lost reply/);
  body.details.purpose = 'changed after click';
  assert.equal(f.command.pending.target_id, trip);
  assert.equal(f.command.pending.body, undefined, 'private body is not publicly exposed');
  f.active = false; f.write = false;
  const result = await f.command.retry();
  assert.equal(result.result.details.purpose, 'PRIVATE Original');
  assert.equal(f.posts.length, 1, 'status recovery does not resend an accepted mutation');
  assert.equal(f.command.pending, null);
});

test('missing status retains original nonce and body for an explicit identical retry', async () => {
  const f = fixture(); f.accepted = false; f.lose = true;
  await assert.rejects(f.submit());
  await assert.rejects(f.command.status(), error => error.status === 404);
  assert.ok(f.command.pending);
  assert.equal(f.posts.length, 1);
  f.accepted = true;
  await f.command.retry();
  assert.deepEqual(f.posts[0], f.posts[1]);
  assert.equal(f.receipts.size, 1);
});

test('current employee rights or identity change discard private retry before another POST', async () => {
  for (const change of [f => {f.read = false;}, f => {f.actor = 'e'.repeat(32);}, f => {f.stamp++;}]) {
    const f = fixture(); f.lose = true;
    await assert.rejects(f.submit()); change(f);
    await assert.rejects(f.command.retry());
    assert.equal(f.command.pending, null);
    assert.equal(f.posts.length, 1);
  }
});

test('foreign target, employee, operation or altered result cannot resolve a pending command', async () => {
  for (const foreign of [{target_id: 'f'.repeat(32)}, {employee_id: 'f'.repeat(32)},
    {operation: 'payment.record'}, {request_hash: 'f'.repeat(64)},
    {result: {id: trip, employee_id: employee, revision: 1, details: {purpose: 'tampered'}}}]) {
    const f = fixture(); f.lose = true;
    await assert.rejects(f.submit()); f.foreign = foreign;
    await assert.rejects(f.command.status(), /Bestätigung/);
    assert.ok(f.command.pending);
    assert.equal(f.posts.length, 1);
  }
});

test('discarding the view while a write is in flight rejects the late response', async () => {
  const f = fixture(); let finish;
  const post = f.api.post;
  f.api.post = async (path, body) => {await post(path, body); await new Promise(resolve => {finish = resolve;});};
  const sending = f.submit();
  while (!finish) await new Promise(resolve => setImmediate(resolve));
  f.command.clear(); finish();
  await assert.rejects(sending, /verworfen/);
  assert.equal(f.command.pending, null);
  assert.equal(f.receipts.size, 1, 'discarding RAM does not undo the actual accepted source');
});

test('original download verifies bytes and previews reject missing amounts instead of claiming zero', async () => {
  const bytes = new TextEncoder().encode('%PDF-1.7 synthetic');
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('');
  await travelOriginal(new Blob([bytes]), {sha256: digest, size: bytes.length});
  await assert.rejects(travelOriginal(new Blob([bytes]), {sha256: hash, size: bytes.length}), /Prüfsumme/);
  assert.throws(() => travelReference({id: trip, revision: 0, content_hash: hash}));
  const reference = {id: trip, revision: 1, content_hash: hash};
  const body = {trip_refs: [reference]};
  const preview = {employee_id: employee, source_hash: hash, preview_hash: hash,
    rule_hash: hash, table_hash: hash, rule_version: 'test', days: [], blockers: [],
    can_approve: false, can_pay: false, trip_refs: [reference], totals: {
      meal_base_minor: 1400, meal_reduction_minor: 560, meal_allowance_minor: 840,
      lodging_allowance_minor: 0, requested_minor: 840, tax_free_minor: 840,
      flat_taxable_minor: 0, individual_taxable_minor: 0, benefit_in_kind_minor: 0,
      already_paid_minor: 0, remaining_minor: 840, overpaid_minor: 0}};
  travelPreview(preview, employee, body);
  const broken = clone(preview); delete broken.totals.tax_free_minor;
  assert.throws(() => travelPreview(broken, employee, body), /vorschau/i);
  assert.throws(() => travelPreview({...preview, can_approve: true, blockers: [{code: 'missing'}]}, employee, body), /vorschau/i);
});

test('actual v2 flight and original expense snapshot preserves distinct approved, private and already-paid cents', async () => {
  const {readFile} = await import('node:fs/promises');
  const fixture = JSON.parse(await readFile(new URL('../../../app/test/fixtures/travel_allowances.json', import.meta.url), 'utf8'));
  const preview = travelPreview(fixture.preview, fixture.employee.id, fixture.preview_body);
  assert.equal(preview.rule_version, 'de_travel_2026_v2');
  assert.equal(preview.totals.tax_free_minor, 2000);
  assert.equal(preview.totals.expense_allowance_minor, 600);
  assert.equal(preview.expense_items[0].private_minor, 400);
  assert.equal(fixture.trip.details.transport_facts[0].kind, 'flight');
  for (const field of ['expense_allowance_minor', 'expense_already_paid_minor']) {
    const altered = clone(preview); delete altered.totals[field];
    assert.throws(() => travelPreview(altered, fixture.employee.id, fixture.preview_body));
  }
  const historical = {...clone(preview), rule_version: 'de_travel_2026_v1'};
  delete historical.totals.expense_allowance_minor; delete historical.totals.expense_already_paid_minor;
  assert.equal(travelPreview(historical, fixture.employee.id, fixture.preview_body), historical, 'historical v1 never requires invented v2 fields');
  for (const [receiptKey, bodyKey] of [['trip_receipt', 'trip_body'], ['approval_receipt', 'approval_body'], ['payment_receipt', 'payment_body']]) {
    const receipt = fixture[receiptKey], body = fixture[bodyKey];
    const original = {request_id: body.request_id, actor_id: receipt.actor_id, employee_id: body.employee_id,
      operation: receipt.operation, target_kind: receipt.target_kind, target_id: body.id,
      request_hash: await travelHash([receipt.operation, receipt.target_kind, body.id, body])};
    assert.equal(await travelReceipt(receipt, original), receipt);
  }
});

test('actual legacy adoption binds the original paid item without counting it a second time', async () => {
  const {readFile} = await import('node:fs/promises');
  const fixture = JSON.parse(await readFile(new URL('../../../app/test/fixtures/travel_allowances.json', import.meta.url), 'utf8'));
  const {expense, body, receipt, settlement, cash_source} = fixture.legacy;
  assert.equal(body.action, 'adopt_legacy');
  assert.equal(body.legacy_payment.payment_hash, await travelHash(expense.payments[body.legacy_payment.payment_index]));
  assert.equal(settlement.calculation.totals.already_paid_minor, 1000);
  assert.equal(settlement.calculation.totals.remaining_minor, 1400);
  assert.equal(cash_source.cash_movements[0].amount, '10.00');
  for (const key of ['kind', 'paid_on', 'amount_minor', 'reference']) assert.equal(body[key], expense.payments[0][key]);
  const expected = {...receipt, request_hash: await travelHash(['payment.record', 'payment', body.id, body])};
  assert.equal(await travelReceipt(receipt, expected), receipt);
  await assert.rejects(travelReceipt({...receipt, result: {...receipt.result, details: {...receipt.result.details, legacy_payment: null}}}, expected));
});
