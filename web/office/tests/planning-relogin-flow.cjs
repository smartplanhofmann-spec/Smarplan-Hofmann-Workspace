const assert=require('node:assert/strict'),path=require('node:path');
const {selectProject}=require('./e2e.cjs');
async function planningReloginFlow({page,context,navigate,ready,login,fixture,screenshots,recovery}) {
    await selectProject(page,fixture.project_id);await ready(page);await navigate(page,'Einsatzplanung');
    await page.getByRole('button',{name:'Termin planen',exact:true}).click();let modal=page.getByRole('dialog',{name:'Termin planen',exact:true});
    const monday=await page.evaluate(()=>{const day=new Date();day.setDate(day.getDate()-((day.getDay()+6)%7));return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;});
    await modal.getByLabel('Termin',{exact:true}).fill('Synthetic browser schedule');await modal.getByLabel('Beginn (Gerätezeit)',{exact:true}).fill(monday+'T09:00');await modal.getByLabel('Ende (Gerätezeit)',{exact:true}).fill(monday+'T10:00');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const appointment=page.locator('.day').nth(0).locator('.appointment').filter({hasText:'Synthetic browser schedule'});
    const moved=page.waitForResponse(response=>response.url().includes('/business/appointments/')&&response.request().method()==='POST');
    await appointment.dragTo(page.locator('.day').nth(1));assert.equal((await moved).status(),200);await ready(page);await page.locator('.day').nth(1).locator('.appointment').filter({hasText:'Synthetic browser schedule'}).waitFor();
    console.log('browser: appointment form and drag-and-drop updated the same canonical calendar');
    await selectProject(page,'');await ready(page);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('month');await ready(page);
    await page.getByLabel('Monat auswählen',{exact:true}).fill('2030-12');await page.getByLabel('Monat auswählen',{exact:true}).press('Tab');await ready(page);
    assert.equal(await page.locator('.calendar-month .day').count(),31);
    assert.match(await page.locator('.calendar-month .day').first().getAttribute('aria-label'),/01\.12\.2030/);
    await page.getByRole('button',{name:'Weiter',exact:true}).click();await ready(page);
    assert.equal(await page.getByLabel('Monat auswählen',{exact:true}).inputValue(),'2031-01');
    assert.match(await page.locator('.calendar-month .day').first().getAttribute('aria-label'),/01\.01\.2031/);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('year');await ready(page);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2030');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    let timeline=page.locator('.timeline-row').filter({has:page.getByText('Synthetic Workshop',{exact:true})});
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2030-12-15');
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-end'),'2031-02-20');
    assert.equal(await timeline.locator('.timeline-project-bar.clipped-end').count(),1);
    const unplanned=page.locator('.timeline-row').filter({has:page.getByText('Private synthetic project',{exact:true})});
    assert.equal(await unplanned.locator('.timeline-project-bar').count(),0);assert.match(await unplanned.locator('.timeline-unplanned').textContent(),/Ungeplant/);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('multi');await ready(page);
    assert.equal(await page.locator('.timeline-tick').count(),36);
    assert.equal(await timeline.locator('.timeline-project-bar.clipped-end').count(),0);
    await timeline.getByRole('button',{name:'Projektzeitraum ändern: Synthetic Workshop',exact:true}).click();
    let datesModal=page.getByRole('dialog',{name:'Projektzeitraum: Synthetic Workshop',exact:true});
    await datesModal.getByLabel('Projektbeginn',{exact:true}).fill('2031-01-10');await datesModal.getByLabel('Projektende',{exact:true}).fill('2031-03-05');
    let releaseAck,arrived,failed;const held=new Promise(resolve=>releaseAck=resolve),received=new Promise((resolve,reject)=>{arrived=resolve;failed=reject;}),dateRoute='**/api/v1/business/planning/projects/*/dates';
    await context.route(dateRoute,async route=>{try{const response=await route.fetch({timeout:10000});assert.equal(response.status(),200);arrived();await held;await route.fulfill({response});}catch(error){failed(error);await route.abort('failed');}});
    try{await datesModal.getByRole('button',{name:'Zeitraum speichern',exact:true}).click();await received;assert.equal(await datesModal.isVisible(),true);assert.equal(await datesModal.getByRole('button',{name:'Zeitraum speichern',exact:true}).isDisabled(),true);}finally{releaseAck();}
    await datesModal.waitFor({state:'detached'});await ready(page);await context.unroute(dateRoute);
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2031-01-10');
    await page.reload();await login(page,'owner@browser.example.test',recovery[1]);await navigate(page,'Einsatzplanung');
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('year');await ready(page);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2031');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    timeline=page.locator('.timeline-row').filter({has:page.getByText('Synthetic Workshop',{exact:true})});
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2031-01-10');assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-end'),'2031-03-05');
    assert.ok((await timeline.locator('.timeline-project-bar').boundingBox()).width>0);
    await page.screenshot({path:path.join(screenshots,'timeline-year.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.equal(await page.getByRole('region',{name:/Projektzeitleiste/}).getAttribute('tabindex'),'0');await page.screenshot({path:path.join(screenshots,'timeline-mobile.png'),fullPage:false});await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>!document.querySelector('.sidebar').inert);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2200');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('multi');await page.getByRole('alert').waitFor();
    assert.equal(await page.getByLabel('Planungsansicht',{exact:true}).inputValue(),'year');
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2031');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    // Exercise compatibility negotiation using the real response with only
    // the feature/readonly metadata reduced; authentication is never replaced.
    let compatibility='readonly';const capRoute='**/api/v1/business/capabilities';
    await context.route(capRoute,async route=>{const response=await route.fetch();const value=await response.json();await route.fulfill({response,json:compatibility==='readonly'?{...value,readonly:true}:{...value,features:[]}});});
    await navigate(page,'Einsatzplanung');assert.equal(await page.locator('.timeline-edit').count(),0);assert.ok(await page.locator('.timeline-project-bar').count());
    compatibility='legacy';await navigate(page,'Einsatzplanung');
    // Removing organization feature metadata rebuilds the shell before the
    // asynchronous legacy calendar is inserted. Wait for that actual view.
    await page.locator('.calendar .day').nth(6).waitFor({state:'visible'});await ready(page);
    assert.equal(await page.getByLabel('Planungsansicht',{exact:true}).count(),0);assert.equal(await page.locator('.timeline-row').count(),0);assert.equal(await page.locator('.calendar .day').count(),7);
    await context.unroute(capRoute);await navigate(page,'Einsatzplanung');
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('week');await ready(page);await page.getByRole('button',{name:'Heute',exact:true}).click();await ready(page);
    await selectProject(page,fixture.project_id);await ready(page);
    console.log('browser: real month/year boundary, multi-year project bars, explicit unplanned rows and acknowledged dates persisted after new MFA login');
}
module.exports={planningReloginFlow};
