import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi} from '../office.js';

for (const kind of ['travel_tax_policy']) {
  test(`actual OfficeApi retains ${kind} nonce through rights drift and module pause`, async () => {
    const employee = null, key = 'payroll-travel-tax-policies';
    const posts = [];
    let rights = true, sourceRights = true, sourceEmployee = employee, active = true;
    const api = new OfficeApi({fetcher: async (url, options) => {
      if (options.method === 'GET') {
        const payload = url.includes('/capabilities') ? {
          readonly: false, features: ['payroll_calculation_cases'], capabilities: ['business_payroll_calculation_cases'],
          permissions: ['personnel.read', ...(rights ? ['personnel.write', 'personnel.approve'] : [])],
          organization: {modules: {personnel: {enabled: active}}},
        } : {
          employee_id: sourceEmployee, employee: {id: sourceEmployee, revision: 99},
          files: [], agreements: [], preparations: [], profiles: [], identities: [], facts: [], absences: [],
          policies: [], file_references: [],
          can_write: sourceRights, can_approve: sourceRights, writes_enabled: active,
        };
        return new Response(JSON.stringify(payload));
      }
      posts.push(JSON.parse(options.body));
      if (posts.length === 1) throw new Error('Synthetic lost accepted acknowledgement');
      return new Response(JSON.stringify({id: 'b'.repeat(32), revision: 1}));
    }});
    api.setToken('synthetic-payroll-entitlements-session');
    const body = {employee_id: employee, employee_revision: null, kind, rule_version:'de_2026_travel_tax_policy_v1', source_contract_version:1, details: {reason: 'Original evidence'}};
    await assert.rejects(api.mutate(key, '/business/payroll/travel-tax-policies', body));
    assert.equal(api.pendingCount, 1);
    body.details.reason = 'Later editor change';
    rights = false;
    await assert.rejects(api.retry(key), error => error.status === 403);
    rights = true;
    sourceRights = false;
    await assert.rejects(api.retry(key), error => error.status === 403);
    sourceRights = true;
    sourceEmployee = 'c'.repeat(32);
    await assert.rejects(api.retry(key));
    assert.equal(posts.length, 1);
    assert.equal(api.pendingCount, 1);
    sourceEmployee = employee;
    active = false;
    await api.retry(key);
    assert.equal(posts.length, 2);
    assert.deepEqual(posts[1], posts[0]);
    assert.equal(posts[1].details.reason, 'Original evidence');
    assert.equal(api.pendingCount, 0);
  });
}
