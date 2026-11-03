import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {travelCashPublic, travelCashCategories, travelBankSource} from '../travel-cash.js';

const fixture = JSON.parse(readFileSync(new URL('../../../app/test/fixtures/travel_cash.json', import.meta.url)));
const clone = value => structuredClone(value);

test('actual backend public cash and bank sources preserve exact values without private sources', () => {
  assert.equal(travelCashPublic(fixture.active), fixture.active);
  assert.equal(travelBankSource(fixture.bank), fixture.bank);
  assert.deepEqual(travelCashCategories(fixture.active), ['travel_allowance']);
  assert.equal(fixture.active.cash_movements[0].amount, '14.00');
  assert.equal(travelCashPublic(fixture.void), fixture.void);
  assert.deepEqual(travelCashCategories(fixture.void), []);
  assert.deepEqual(fixture.void.cash_movements, []);
});

test('private additions at every public level fail closed', () => {
  const changes = [s => {s.employee_id = 'a'.repeat(32);},
    s => {s.cash_movements[0].employee_name = 'Private';},
    s => {s.cash_movements[0].account.personnel_file = 'secret';},
    s => {s.cash_movements[0].categories.taxable_wages = '0.00';}];
  for (const change of changes) {const s = clone(fixture.active); change(s); assert.throws(() => travelCashPublic(s));}
  for (const field of ['employee_id', 'settlement_id', 'sources', 'file_id']) {
    assert.throws(() => travelBankSource({...fixture.bank, [field]: 'private'}));
  }
});

test('revision identity, amount, explicit void and dated movement cannot drift', () => {
  const changes = [s => {s.revision = true;}, s => {s.revision = 2;},
    s => {s.source_hash = 'invalid';}, s => {s.proof_hash = null;},
    s => {s.status = 'void';}, s => {s.cash_movements = [];},
    s => {s.cash_movements[0].date = '2026-10-28';},
    s => {s.cash_movements[0].amount = '14.01';},
    s => {s.cash_movements[0].account.currency = 'USD';},
    s => {s.cash_movements[0].account.revision = 0;}];
  for (const change of changes) {const s = clone(fixture.active); change(s); assert.throws(() => travelCashPublic(s));}
  for (const value of ['0.00', '-14.00', '1e2', '14', 14, '014.00', '14.001', null]) {
    const s = clone(fixture.active); s.cash_movements[0].amount = value;
    s.cash_movements[0].categories.travel_allowance = value;
    assert.throws(() => travelCashPublic(s));
    assert.throws(() => travelBankSource({...fixture.bank, amount: value}));
  }
});

test('impossible calendar dates cannot become travel cash dates', () => {
  for (const value of ['2026-02-29', '2026-04-31', '2026-00-01', '2026-13-01', '2026-10-00']) {
    const s = clone(fixture.active); s.date = value; s.cash_movements[0].date = value;
    assert.throws(() => travelCashPublic(s), value);
    assert.throws(() => travelBankSource({...fixture.bank, date: value}), value);
  }
});

test('bank source must retain a complete original revision and matching public shape', () => {
  for (const change of [{source_path: fixture.bank.source_path + '&employee=private'},
    {source_path: fixture.bank.source_path.replace(/revision=\d+$/, 'revision=0')},
    {origin_hash: 'bad'}, {source_hash: null}, {direction: 'refund'}, {source_kind: 'payroll_cash'}]) {
    assert.throws(() => travelBankSource({...fixture.bank, ...change}));
  }
});
