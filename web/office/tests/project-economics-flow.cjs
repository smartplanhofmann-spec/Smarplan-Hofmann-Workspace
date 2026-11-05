const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

async function projectEconomicsFlow({page,context,navigate,ready,fixture,screenshots}){
  const records=[],errors=[];let loseConfirmation=true;
  const routePattern='**/api/v1/business/**';
  await context.route(routePattern,async route=>{
    const request=route.request(),url=new URL(request.url());
    if(!url.pathname.startsWith('/api/v1/business/project-economics'))return route.fallback();
    try{
      assert.equal(url.origin,fixture.base_url);const response=await route.fetch({maxRedirects:0}),value=await response.json();
      records.push({method:request.method(),path:url.pathname,query:url.search,body:request.method()==='POST'?request.postDataJSON():null,status:response.status(),value});
      if(loseConfirmation&&request.method()==='POST'&&url.pathname.endsWith('/confirm')){assert.equal(response.status(),201);loseConfirmation=false;await route.abort('failed');}
      else await route.fulfill({response});
    }catch(error){errors.push(error.message);await route.abort('failed').catch(()=>{});}
  });
  const metric=title=>page.locator('section.panel').filter({has:page.getByRole('heading',{name:title,exact:true})}).locator('.metric');
  const sourceRow=()=>page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Eingangsbelege und Kosten',exact:true})}).locator('.list-row').filter({hasText:'Synthetische Fremdleistung · SYN-ECO-1'});
  const modal=title=>page.getByRole('dialog',{name:title,exact:true});
  async function waitValue(locator,expected){await locator.filter({hasText:expected}).waitFor();assert.equal((await locator.innerText()).replace(/\s/g,' '),expected.replace(/\s/g,' '));}
  async function previewAndConfirm(reason,{lost=false}={}){
    const input=page.getByRole('dialog');await input.getByLabel('Begründung der Einordnung',{exact:true}).fill(reason);
    await input.getByRole('button',{name:'Einordnung prüfen',exact:true}).click();
    const confirmation=modal('Einordnung bestätigen');await confirmation.waitFor();
    await confirmation.getByLabel('Ich bestätige diese vollständige Belegeinordnung für das Projekt.',{exact:true}).check();
    await confirmation.getByRole('button',{name:'Einordnung verbindlich festhalten',exact:true}).click();
    if(lost){await confirmation.getByRole('alert').waitFor();assert.match(await confirmation.innerText(),/Keine sichere Antwort/);assert.equal(await page.getByRole('button',{name:'1 Antwort offen',exact:true}).count(),1);await confirmation.getByRole('button',{name:'Einordnung verbindlich festhalten',exact:true}).click();}
    await confirmation.waitFor({state:'detached'});await ready(page);
  }
  try{
    await page.getByLabel('Aktuelles Projekt').selectOption('');await ready(page);await navigate(page,'Projekte');
    await page.getByRole('button',{name:'Neues Projekt',exact:true}).click();
    await page.getByLabel('Projektname',{exact:true}).fill('Synthetische Projektwirtschaftlichkeit');
    assert.equal(await page.getByRole('dialog').getByLabel('Kunde auswählen',{exact:true}).inputValue(),'');
    await page.getByRole('dialog').getByLabel('Neuer Kunde / Auftraggeber',{exact:true}).fill('Synthetischer Wirtschaftlichkeitskunde');
    await page.getByRole('button',{name:'Projekt anlegen',exact:true}).click();await ready(page);
    await page.getByRole('tab',{name:'Wirtschaftlichkeit',exact:true}).click();await ready(page);
    await page.getByRole('button',{name:'Projektbeleg erfassen',exact:true}).click();
    await modal('Projektbeleg erfassen').getByLabel('Belegoriginal auswählen',{exact:true}).setInputFiles(fixture.photo_path);
    await modal('Projektbeleg erfassen').getByLabel('Notiz zum Beleg',{exact:true}).fill('Synthetischer Originalbeleg zur erbrachten Fremdleistung.');
    await modal('Projektbeleg erfassen').getByRole('button',{name:'Original speichern und prüfen',exact:true}).click();
    const review=modal('Eingangsbeleg prüfen');await review.waitFor();
    const originalDownload=page.waitForEvent('download');await review.getByRole('button',{name:'Original ansehen',exact:true}).click();const downloaded=await originalDownload;assert.deepEqual(await fs.readFile(await downloaded.path()),await fs.readFile(fixture.photo_path));
    for(const [label,value]of [['Lieferant','Synthetische Fremdleistung'],['Belegnummer','SYN-ECO-1'],['Belegdatum','2026-11-03'],['Netto laut Beleg EUR','100'],['Ausgewiesene Steuer EUR','19'],['Brutto laut Beleg EUR','119']])await review.getByLabel(label,{exact:true}).fill(value);
    await review.getByLabel('Ich habe das Original geöffnet und die Angaben damit abgeglichen.',{exact:true}).check();await review.getByRole('button',{name:'Belegprüfung speichern',exact:true}).click();await review.waitFor({state:'detached'});await ready(page);
    await waitValue(metric('Belegter Beitrag netto'),'—');
    await sourceRow().getByRole('button',{name:'Kosten einordnen',exact:true}).click();
    await modal('Belegkosten einordnen').getByLabel('Fremdleistungen netto EUR',{exact:true}).fill('100');
    await previewAndConfirm('Vollständige Fremdleistung laut Original.',{lost:true});
    const confirmations=records.filter(item=>item.method==='POST'&&item.path.endsWith('/confirm'));
    assert.equal(confirmations.length,2);assert.deepEqual(confirmations[0].body,confirmations[1].body);assert.equal(confirmations[0].value.id,confirmations[1].value.id);assert.equal(confirmations[1].value.revision,1);
    await waitValue(metric('Erfasste Projektkosten netto'),'100,00 €');await waitValue(metric('Belegter Beitrag netto'),'-100,00 €');await waitValue(metric('Zahlungszufluss nach Erstattungen'),'0,00 €');
    await sourceRow().getByRole('button',{name:'Einordnung korrigieren',exact:true}).click();
    await modal('Einordnung korrigieren').getByLabel('Fremdleistungen netto EUR',{exact:true}).fill('60');await modal('Einordnung korrigieren').getByLabel('Sonstige Kosten netto EUR',{exact:true}).fill('40');
    await previewAndConfirm('Getrennte belegte Leistungs- und Auslagenanteile.');await waitValue(metric('Erfasste Projektkosten netto'),'100,00 €');
    await sourceRow().getByRole('button',{name:'Historie',exact:true}).click();await modal('Einordnungshistorie').getByRole('heading',{name:'Fassung 2',exact:true}).waitFor();assert.equal(await modal('Einordnungshistorie').getByRole('heading',{name:'Fassung 1',exact:true}).count(),1);await modal('Einordnungshistorie').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await sourceRow().getByRole('button',{name:'Belegdaten prüfen',exact:true}).click();const changed=modal('Eingangsbeleg prüfen');await changed.getByLabel('Netto laut Beleg EUR',{exact:true}).fill('110');await changed.getByLabel('Ausgewiesene Steuer EUR',{exact:true}).fill('20,90');await changed.getByLabel('Brutto laut Beleg EUR',{exact:true}).fill('130,90');await changed.getByLabel('Ich habe das Original geöffnet und die Angaben damit abgeglichen.',{exact:true}).check();await changed.getByRole('button',{name:'Belegprüfung speichern',exact:true}).click();await changed.waitFor({state:'detached'});await ready(page);
    await waitValue(metric('Belegter Beitrag netto'),'—');assert.match(await sourceRow().innerText(),/Belegprüfung geändert/);
    await sourceRow().getByRole('button',{name:'Einordnung korrigieren',exact:true}).click();await modal('Einordnung korrigieren').getByLabel('Fremdleistungen netto EUR',{exact:true}).fill('70');await previewAndConfirm('Geänderte Belegprüfung ausdrücklich übernommen.');await waitValue(metric('Erfasste Projektkosten netto'),'110,00 €');
    const budget=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Budget festlegen',exact:true})});for(const [label,value]of [['Material netto EUR','50'],['Lohn netto EUR','50'],['Maschinen netto EUR','0'],['Sonstige Kosten netto EUR','100']])await budget.getByLabel(label,{exact:true}).fill(value);await budget.getByRole('button',{name:'Neue Budgetfassung speichern',exact:true}).click();await ready(page);await waitValue(metric('Rest zum Budget'),'90,00 €');
    const allocations=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Belegeinordnungen mit Herkunft',exact:true})});await allocations.getByRole('button',{name:'Quelle öffnen',exact:true}).first().click();await modal('Quellnachweis').waitFor();assert.match(await modal('Quellnachweis').innerText(),/SYN-ECO-1/);await modal('Quellnachweis').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(screenshots,'project-economics-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=0);await page.evaluate(()=>window.scrollTo(0,0));assert.ok((await sourceRow().locator('.body').boundingBox()).width>=250,'receipt title must retain a readable mobile column');assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'project-economics-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});
    const snapshots=records.filter(item=>item.method==='GET'&&item.path==='/api/v1/business/project-economics');const last=snapshots.at(-1).value;assert.equal(last.costs.total_net,'110.00');assert.equal(last.revenue.revenue_net,'0.00');assert.equal(last.payments.net_inflow_gross,'0.00');assert.equal(last.result.document_net_contribution,'-110.00');
    assert.deepEqual(errors,[]);console.log('project economics: original upload/review, full classification, lost real acknowledgement, correction/history, changed-source suppression, budget and source drilldown passed');
  }finally{await fs.writeFile(path.join(screenshots,'project-economics-http-records.json'),JSON.stringify(records,null,2));await context.unroute(routePattern);}
}
module.exports={projectEconomicsFlow};
