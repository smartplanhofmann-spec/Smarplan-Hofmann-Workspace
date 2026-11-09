/* Real browser editing and exact retry of an existing synthetic maintenance contract. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const {selectProject} = require('./e2e.cjs');

const command = values => ({request_id: crypto.randomUUID().replaceAll('-', ''), ...values});

async function maintenanceContractFlow({page, context, navigate, ready, fixture, screenshots}) {
  let authorization;
  const capture = request => {
    if (new URL(request.url()).origin === fixture.base_url && request.headers().authorization) {
      authorization = request.headers().authorization;
    }
  };
  page.on('request', capture);
  const attempts = [], routeErrors = [];
  let routePattern;
  const title = 'Synthetischer Browserwartungsvertrag';
  const editor = () => page.getByRole('dialog', {name: 'Wartungsvertrag bearbeiten', exact: true});
  const contractRow = () => page.locator('main .list-row').filter({
    has: page.getByRole('heading', {name: title, exact: true}),
  });

  async function api(suffix, body, status = 200) {
    assert.ok(authorization, 'The fixture uses the browser’s actual authenticated session.');
    const response = await context.request.fetch(fixture.base_url + '/api/v1/business' + suffix, {
      method: body ? 'POST' : 'GET',
      headers: {Authorization: authorization, Origin: fixture.base_url},
      ...(body ? {data: body} : {}),
      maxRedirects: 0,
    });
    const text = await response.text();
    assert.equal(response.status(), status, suffix + ': ' + text);
    return JSON.parse(text);
  }
  async function openEditor() {
    await contractRow().getByRole('button', {name: 'Wartungsvertrag bearbeiten', exact: true}).click();
    await editor().waitFor();
    return editor();
  }
  async function submit() {
    await editor().getByRole('button', {name: 'Änderungen speichern', exact: true}).click();
  }
  async function saved() {
    await editor().waitFor({state: 'detached'});
    await ready(page);
    await contractRow().waitFor();
  }

  try {
    await navigate(page, 'Projekte');
    await selectProject(page, fixture.project_id);
    const asset = await api('/assets', command({
      project_id: fixture.project_id,
      name: 'Synthetische Anlage für Vertragsbearbeitung',
      serial_number: 'SYN-MAINTENANCE-EDIT-001',
    }), 201);
    const created = await api('/maintenance/contracts', command({
      project_id: fixture.project_id,
      asset_id: asset.id,
      title,
      anchor_date: '2026-11-01',
      interval_unit: 'months',
      interval_count: 1,
      notes: 'Synthetischer ursprünglicher Wartungsumfang.',
      active: true,
    }), 201);
    const firstSchedule = await api('/maintenance/schedule', command({
      project_id: fixture.project_id, as_of: '2026-11-01',
    }));
    assert.equal(firstSchedule.items.filter(item => item.contract_id === created.id).length, 1);
    const originalVisit = firstSchedule.items.find(item => item.contract_id === created.id);
    const originalVisitJson = JSON.stringify(originalVisit);
    assert.equal(originalVisit.contract_snapshot.active, true);
    assert.equal(originalVisit.contract_snapshot.revision, 1);

    await page.getByRole('tab', {name: 'Wartung', exact: true}).click();
    await ready(page);
    const initial = await openEditor();
    assert.equal(await initial.getByLabel('Anlage', {exact: true}).inputValue(), asset.id);
    assert.equal(await initial.getByLabel('Vertragsbezeichnung', {exact: true}).inputValue(), title);
    assert.equal(await initial.getByLabel('Erste Fälligkeit', {exact: true}).inputValue(), '2026-11-01');
    assert.equal(await initial.getByLabel('Intervalltyp', {exact: true}).inputValue(), 'months');
    assert.equal(await initial.getByLabel('Intervall', {exact: true}).inputValue(), '1');
    assert.equal(await initial.getByLabel('Vertragshinweise', {exact: true}).inputValue(), created.notes);
    assert.equal(await initial.getByLabel('Aktiv', {exact: true}).isChecked(), true);

    let losePauseResponse = true;
    routePattern = '**/api/v1/business/maintenance/contracts/' + created.id;
    await context.route(routePattern, async route => {
      try {
        const request = route.request();
        const response = await route.fetch({maxRedirects: 0});
        if (request.method() === 'POST') {
          const attempt = {body: request.postDataJSON(), status: response.status(), value: await response.json()};
          attempts.push(attempt);
          if (losePauseResponse) {
            losePauseResponse = false;
            assert.equal(attempt.status, 200, 'The lost pause response was actually accepted.');
            assert.equal(attempt.value.active, false);
            await route.abort('failed');
            return;
          }
        }
        await route.fulfill({response});
      } catch (error) {
        routeErrors.push(error.message);
        await route.abort('failed').catch(() => {});
      }
    });

    await initial.getByLabel('Aktiv', {exact: true}).uncheck();
    await submit();
    await editor().getByRole('alert').waitFor();
    assert.equal(attempts.length, 1);
    assert.equal(attempts[0].body.revision, 1);
    assert.equal(attempts[0].body.active, false);
    const acceptedPause = await api('/maintenance/contracts/' + created.id);
    assert.equal(acceptedPause.active, false);
    assert.equal(acceptedPause.revision, 2);
    await editor().getByRole('button', {name: 'Ursprüngliche Antwort erneut prüfen', exact: true}).click();
    await saved();
    assert.equal(attempts.length, 2);
    assert.deepEqual(attempts[1], attempts[0], 'Retry preserves the original body, request ID and receipt.');
    assert.equal((await api('/maintenance/contracts/' + created.id)).revision, 2);
    assert.match(await contractRow().innerText(), /Pausiert/);
    const whilePaused = await api('/maintenance/schedule', command({
      project_id: fixture.project_id, as_of: '2026-12-01',
    }));
    assert.equal(whilePaused.items.filter(item => item.contract_id === created.id).length, 0);

    await openEditor();
    assert.equal(await editor().getByLabel('Aktiv', {exact: true}).isChecked(), false);
    await editor().getByLabel('Aktiv', {exact: true}).check();
    await submit();
    await saved();
    assert.match(await contractRow().innerText(), /Aktiv/);
    const reactivated = await api('/maintenance/contracts/' + created.id);
    assert.equal(reactivated.revision, 3);
    assert.equal(reactivated.active, true);
    const afterReactivation = await api('/maintenance/schedule', command({
      project_id: fixture.project_id, as_of: '2026-12-01',
    }));
    const newVisits = afterReactivation.items.filter(item => item.contract_id === created.id);
    assert.equal(newVisits.length, 1);
    assert.equal(newVisits[0].occurrence_index, 1);
    assert.equal(newVisits[0].due_date, '2026-12-01');
    const scheduleAgain = await api('/maintenance/schedule', command({
      project_id: fixture.project_id, as_of: '2026-12-01',
    }));
    assert.equal(scheduleAgain.items.filter(item => item.contract_id === created.id).length, 0);

    // A second real writer advances the contract after this browser loaded its revision.
    await openEditor();
    const concurrent = await api('/maintenance/contracts/' + created.id, command({
      project_id: fixture.project_id,
      revision: reactivated.revision,
      notes: 'Synthetische parallele Vertragsänderung.',
    }));
    await editor().getByLabel('Vertragshinweise', {exact: true}).fill('Veraltete Browseränderung.');
    await submit();
    await editor().getByRole('alert').waitFor();
    assert.equal(attempts.at(-1).status, 409);
    assert.equal(attempts.at(-1).body.revision, reactivated.revision);
    const current = await api('/maintenance/contracts/' + created.id);
    assert.deepEqual(current, concurrent, 'The stale browser did not overwrite the concurrent change.');
    const beforeReloadAttempts = attempts.length;
    await editor().getByRole('button', {name: 'Aktuellen Stand laden', exact: true}).click();
    await page.waitForFunction(notes => document.querySelector('[name="notes"]')?.value === notes, concurrent.notes);
    assert.equal(await editor().getByLabel('Vertragshinweise', {exact: true}).inputValue(), concurrent.notes);
    assert.equal(attempts.length, beforeReloadAttempts, 'Reloading the conflicted contract performs no new write.');
    await editor().getByRole('button', {name: 'Dialog schließen', exact: true}).click();

    const allContracts = await api('/maintenance/contracts?project_id=' + fixture.project_id);
    assert.equal(allContracts.items.filter(item => item.id === created.id).length, 1);
    const history = await api('/maintenance/history?project_id=' + fixture.project_id);
    const visits = history.items.filter(item => item.contract_id === created.id);
    assert.equal(visits.length, 2);
    assert.equal(JSON.stringify(visits.find(item => item.id === originalVisit.id)), originalVisitJson,
      'Pausing, exact retry, reactivation and a rejected stale write preserve the original visit bytes.');
    assert.deepEqual(routeErrors, []);
    await page.setViewportSize({width: 390, height: 844});
    await openEditor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(screenshots, 'maintenance-contract-mobile.png'), fullPage: false});
    await editor().getByRole('button', {name: 'Dialog schließen', exact: true}).click();
    console.log('maintenance contracts: real browser prefill, pause, accepted lost reply and exact retry, reactivation, unchanged original visit, one resumed occurrence, stale revision and mobile editor passed');
  } finally {
    page.off('request', capture);
    if (routePattern) await context.unroute(routePattern);
    await fs.writeFile(path.join(screenshots, 'maintenance-contract-receipts.json'), JSON.stringify(attempts, null, 2));
  }
}

module.exports = {maintenanceContractFlow};
