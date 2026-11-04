/* Real local HTTP and browser clock/approval/correction journey. Synthetic users only. */
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');
const request = values => ({request_id: crypto.randomUUID().replaceAll('-', ''), ...values});

async function timeTrackingFlow({page, context, navigate, ready, login, fixture, screenshots}) {
  let authorization;
  const receipts = [], errors = [];
  const capture = req => { if (new URL(req.url()).origin === fixture.base_url && req.headers().authorization) authorization = req.headers().authorization; };
  page.on('request', capture);
  const dialog = title => page.getByRole('dialog', {name: title, exact: true});
  async function api(suffix, body, status = 200, token = authorization) {
    const response = await context.request.fetch(fixture.base_url + '/api/v1' + suffix, {
      method: body ? 'POST' : 'GET', headers: {Authorization: token, Origin: fixture.base_url},
      ...(body ? {data: body} : {}), maxRedirects: 0,
    });
    assert.equal(response.status(), status, suffix + ' ' + await response.text());
    return response.json();
  }
  let loseAck = true;
  await context.route('**/api/v1/business/time/entries/*/correct', async route => {
    try {
      const response = await route.fetch({maxRedirects: 0}), value = await response.json();
      receipts.push({body: route.request().postDataJSON(), status: response.status(), value});
      if (loseAck) {
        assert.equal(response.status(), 201, JSON.stringify(value));
        loseAck = false;
        await route.abort('failed');
      } else await route.fulfill({response});
    } catch (error) { errors.push(error.message); await route.abort('failed').catch(() => {}); }
  });
  try {
    await navigate(page, 'Personal');
    const actor = await api('/me');
    const employees = (await api('/business/employees')).items;
    const owner = employees.find(employee => employee.user_id === actor.id);
    assert.ok(owner);
    const dates = await page.evaluate(() => {
      function input(date) { return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
      return {start: input(new Date(Date.now() - 3 * 3600000)), end: input(new Date(Date.now() - 3600000))};
    });
    await page.getByRole('button', {name: 'Zeit starten', exact: true}).click();
    await dialog('Zeiterfassung').getByLabel('Projekt', {exact: true}).selectOption(fixture.project_id);
    await dialog('Zeiterfassung').getByLabel('Zeitpunkt (Gerätezeit)', {exact: true}).fill(dates.start);
    await dialog('Zeiterfassung').getByRole('button', {name: 'Zeitereignis speichern', exact: true}).click();
    await dialog('Zeiterfassung').waitFor({state: 'detached'});
    await ready(page);
    await page.getByRole('button', {name: 'Laufende Zeit öffnen', exact: true}).click();
    await dialog('Zeiterfassung').getByLabel('Aktion', {exact: true}).selectOption('stop');
    await dialog('Zeiterfassung').getByLabel('Zeitpunkt (Gerätezeit)', {exact: true}).fill(dates.end);
    await dialog('Zeiterfassung').getByRole('button', {name: 'Zeitereignis speichern', exact: true}).click();
    await dialog('Zeiterfassung').waitFor({state: 'detached'});
    await ready(page);
    const original = (await api('/business/time/entries')).items[0];
    assert.equal(original.project_id, fixture.project_id);
    assert.equal(original.worked_seconds, 7200);
    assert.equal(original.events.length, 2);
    assert.deepEqual(original.corrections, []);
    for (const day of original.work_dates) {
      const label = new Intl.DateTimeFormat('de-DE', {dateStyle: 'medium'}).format(new Date(day + 'T12:00:00Z'));
      const row = page.locator('main .list-row').filter({has: page.getByRole('heading', {name: label, exact: true})});
      await row.getByRole('button', {name: 'Tag freigeben', exact: true}).click();
      await dialog('Arbeitstag freigeben').getByRole('button', {name: 'Verbindlich bestätigen', exact: true}).click();
      await dialog('Arbeitstag freigeben').waitFor({state: 'detached'});
      await ready(page);
    }
    const approved = await api('/business/time/entries/' + original.id);
    const day = approved.approved_work_dates[0];
    const summaryPath = '/business/time/summary?employee_id=' + owner.id + '&from=' + day + '&to=' + day;
    const before = await api(summaryPath);
    await page.getByRole('button', {name: 'Zeiteintrag prüfen', exact: true}).click();
    await dialog('Zeiteintrag prüfen').getByRole('button', {name: 'Freigegebene Zeit korrigieren', exact: true}).click();
    const editor = dialog('Freigegebene Zeit korrigieren');
    assert.equal(await editor.getByLabel('Ich habe den Originaleintrag und die Zeitänderung geprüft.', {exact: true}).isChecked(), false);
    await editor.getByLabel('Freigegebener Arbeitstag', {exact: true}).selectOption(day);
    await editor.getByLabel('Änderung in Minuten', {exact: true}).fill('-30');
    await editor.getByLabel('Begründung der Zeitkorrektur', {exact: true}).fill('Synthetisch belegte Pause von 30 Minuten nachgetragen.');
    await editor.getByLabel('Ich habe den Originaleintrag und die Zeitänderung geprüft.', {exact: true}).check();
    await editor.getByRole('button', {name: 'Zeitkorrektur speichern', exact: true}).click();
    await editor.getByRole('alert').waitFor();
    assert.equal(await editor.getByLabel('Änderung in Minuten', {exact: true}).isDisabled(), true);
    await editor.getByRole('button', {name: 'Dieselbe Zeitkorrektur erneut senden', exact: true}).click();
    await editor.waitFor({state: 'detached'});
    await ready(page);
    assert.equal(receipts.length, 2);
    assert.deepEqual(receipts[0], receipts[1]);
    const corrected = await api('/business/time/entries/' + original.id);
    assert.deepEqual(corrected.events, original.events);
    assert.equal(corrected.corrections.length, 1);
    assert.equal(corrected.corrections[0].delta_seconds, -1800);
    assert.equal((await api(summaryPath)).net_seconds, before.net_seconds - 1800);
    const monthly = page.locator('main .panel').filter({has: page.getByRole('heading', {name: 'Nettoarbeitszeit im Monat', exact: true})});
    assert.equal(await monthly.locator('.metric').textContent(), '1:30 Std.');
    await page.getByRole('button', {name: 'Zeiteintrag prüfen', exact: true}).click();
    await dialog('Zeiteintrag prüfen').getByText('Synthetisch belegte Pause von 30 Minuten nachgetragen.', {exact: true}).waitFor();
    await page.screenshot({path: path.join(screenshots, 'time-correction-desktop.png')});
    await page.setViewportSize({width: 390, height: 844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path: path.join(screenshots, 'time-correction-mobile.png')});

    // A technician sees their own original and history but cannot append corrections.
    const users = await api('/users');
    const technicianUser = (Array.isArray(users) ? users : users.items).find(user => user.email === 'technician@browser.example.test');
    const technician = employees.find(employee => employee.user_id === technicianUser.id);
    const id = crypto.randomUUID().replaceAll('-', '');
    const start = original.events[0].occurred_at, end = original.events[1].occurred_at;
    await api('/business/time/events', request({entry_id: id, employee_id: technician.id, project_id: fixture.project_id, device_id: 'browser-time-fixture', sequence: 1, revision: 0, action: 'start', occurred_at: start}));
    await api('/business/time/events', request({entry_id: id, employee_id: technician.id, project_id: fixture.project_id, device_id: 'browser-time-fixture', sequence: 2, revision: 1, action: 'stop', occurred_at: end}));
    for (const date of original.work_dates) {
      const account = await api('/business/time/summary?employee_id=' + technician.id + '&from=' + date + '&to=' + date);
      await api('/business/time/days/' + date + '/approve', request({employee_id: technician.id, revision: account.days[0].revision}));
    }
    const restricted = await context.newPage();
    let technicianAuthorization;
    restricted.on('request', req => { if (new URL(req.url()).origin === fixture.base_url && req.headers().authorization) technicianAuthorization = req.headers().authorization; });
    await restricted.goto(fixture.base_url + '/office/');
    await login(restricted, 'technician@browser.example.test');
    await navigate(restricted, 'Personal');
    await restricted.getByRole('button', {name: 'Zeiteintrag prüfen', exact: true}).click();
    const detail = restricted.getByRole('dialog', {name: 'Zeiteintrag prüfen', exact: true});
    await detail.waitFor();
    assert.equal(await detail.getByRole('button', {name: 'Freigegebene Zeit korrigieren', exact: true}).count(), 0);
    await api('/business/time/entries/' + id + '/correct', request({work_date: day, delta_seconds: -60, reason: 'Synthetischer verbotener Versuch'}), 403, technicianAuthorization);
    await restricted.close();
    assert.deepEqual(errors, []);
    await fs.writeFile(path.join(screenshots, 'time-correction-result.json'), JSON.stringify({original, approved, corrected, before, after: await api(summaryPath), receipts}, null, 2));
    console.log('time-tracking: project-bound browser start/stop, day approval, append-only correction, lost ACK exact replay, unchanged originals, corrected day total, mobile layout and denied technician correction passed');
  } finally {
    page.off('request', capture);
    await context.unroute('**/api/v1/business/time/entries/*/correct');
  }
}
module.exports = {timeTrackingFlow};
