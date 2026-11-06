const {selectProject}=require('./e2e.cjs');
/* Actual staff/customer browsers and real HTTP responses; no portal token injection. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
async function portalFlow({page,context,navigate,ready,fixture,screenshots}){
  const waiting=new Set(),customers=new Set(),records=[],errors=[];let loseGrant=true,loseSession=true,loseDecision=true;
  function wait(method,suffix){const promise=new Promise((resolve,reject)=>{
    const item={method,suffix,resolve:value=>{clearTimeout(item.timer);waiting.delete(item);resolve(value);},reject:error=>{clearTimeout(item.timer);waiting.delete(item);reject(error);}};
    item.timer=setTimeout(()=>item.reject(new Error('Expected real portal response was not observed: '+method+' '+suffix)),15000);waiting.add(item);
  });promise.catch(()=>{});return promise;}
  const pattern='**/api/v1/**';
  await context.route(pattern,async route=>{
    const request=route.request(),url=new URL(request.url()),method=request.method();
    if(!/^\/api\/v1\/(?:business\/)?portal\//.test(url.pathname)){await route.fallback();return;}
    try{
      assert.equal(url.origin,fixture.base_url);assert.equal(url.hash,'');
      const headers=request.headers(),body=request.postDataJSON(),isPublic=url.pathname.startsWith('/api/v1/portal/');
      if(isPublic){assert.equal(headers.cookie,undefined);if(url.pathname.endsWith('/sessions'))assert.equal(headers.authorization,undefined);else assert.match(headers.authorization||'',/^Bearer SPPT_/);}
      else assert.ok(headers.authorization&&!headers.authorization.startsWith('Bearer SPPT_'));
      const response=await route.fetch({maxRedirects:0}),status=response.status(),value=url.pathname.endsWith('/pdf')?Buffer.from(await response.body()):await response.json();
      const record={url,method,body,status,value};records.push(record);
      const drop=(loseGrant&&method==='POST'&&url.pathname==='/api/v1/business/portal/grants')||
        (loseSession&&method==='POST'&&url.pathname==='/api/v1/portal/sessions')||
        (loseDecision&&method==='POST'&&url.pathname==='/api/v1/portal/offer/decision');
      if(drop){if(url.pathname.endsWith('/grants'))loseGrant=false;else if(url.pathname.endsWith('/sessions'))loseSession=false;else loseDecision=false;await route.abort('failed');}
      else await route.fulfill({response});
      for(const item of [...waiting])if(item.method===method&&url.pathname.endsWith(item.suffix))item.resolve(record);
    }catch(error){for(const item of [...waiting])item.reject(error);await route.abort('failed').catch(()=>{});errors.push(error.message);}
  });
  async function openOffer(offer){
    if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await selectProject(page,'');await ready(page);await navigate(page,'Dokumente');
    await page.locator('.list-row').filter({has:page.getByRole('heading',{name:offer.title,exact:true})}).getByRole('button',{name:'Öffnen',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Kundenportal verwalten',exact:true}).click();
    const modal=page.getByRole('dialog',{name:'Kundenportal · '+offer.number,exact:true});await modal.waitFor();return modal;
  }
  async function fillGrant(){
    await page.getByRole('dialog').getByRole('button',{name:'Kundenzugang freigeben',exact:true}).click();
    const modal=page.getByRole('dialog',{name:'Kundenzugang freigeben',exact:true});
    await modal.getByLabel('Ich habe Angebotsfassung, Kundenbindung, Empfänger und Original-PDF geprüft und gebe diesen Zugang ausdrücklich frei.',{exact:true}).check();return modal;
  }
  async function revoke(buttonLabel='Zugang widerrufen'){
    await page.getByRole('dialog').getByRole('button',{name:buttonLabel,exact:true}).click();
    const modal=page.getByRole('dialog',{name:'Kundenzugang widerrufen',exact:true});
    await modal.getByLabel('Grund für den Widerruf',{exact:true}).fill('Synthetic browser review');
    await modal.getByLabel('Diesen Zugang und seine bestehenden Kundensitzungen ausdrücklich widerrufen.',{exact:true}).check();
    await modal.getByRole('button',{name:'Kundenzugang widerrufen',exact:true}).click();await modal.waitFor({state:'detached'});
    await page.getByRole('dialog',{name:/Kundenportal ·/}).waitFor();
  }
  async function issueLink(){const modal=await fillGrant(),response=wait('POST','/business/portal/grants');
    await modal.getByRole('button',{name:'Kundenzugang verbindlich freigeben',exact:true}).click();const result=await response;assert.equal(result.status,201);
    await page.getByRole('dialog',{name:'Kundenlink einmalig sichern',exact:true}).waitFor();
    const link=await page.getByLabel('Kundenlink',{exact:true}).inputValue();assert.equal(new URL(link).origin,'https://127.0.0.1');return {link,result};}
  async function openCustomer(link,expectRetry=false){
    const customer=await context.newPage();customers.add(customer);customer.on('pageerror',error=>errors.push(error.message));customer.setDefaultTimeout(15000);
    customer.on('request',request=>{const url=new URL(request.url());if(url.pathname.startsWith('/api/v1/'))assert.ok(url.pathname.startsWith('/api/v1/portal/'),'customer page must not load office APIs');});
    let session=wait('POST','/portal/sessions'),view;
    if(!expectRetry)view=wait('GET','/portal/offer');
    // The fixture explicitly maps its HTTP loopback transport to the canonical
    // HTTPS host. Keep the issued fragment byte-for-byte; authenticate normally.
    await customer.goto(fixture.base_url+'/office/portal.html'+new URL(link).hash);
    const first=await session;assert.equal(first.status,201);
    if(expectRetry){await customer.getByRole('button',{name:'Zugang erneut öffnen',exact:true}).waitFor();session=wait('POST','/portal/sessions');view=wait('GET','/portal/offer');
      await customer.getByRole('button',{name:'Zugang erneut öffnen',exact:true}).click();const second=await session;assert.equal(second.status,201);assert.deepEqual(first.body,second.body);}
    const loaded=await view;assert.equal(loaded.status,200);await customer.getByRole('heading',{name:loaded.value.offer.title,exact:true}).waitFor();
    assert.equal(new URL(customer.url()).hash,'');assert.equal(await customer.evaluate(()=>Object.keys(localStorage).length+Object.keys(sessionStorage).length),0);
    assert.equal(await customer.locator('img[src=x]').count(),0);assert.equal(await customer.evaluate(()=>window.__unsafe),undefined);
    function check(value){if(value&&typeof value==='object')for(const [key,child]of Object.entries(value)){assert.ok(!['cost_price_net','cost_price_base_quantity','pricing_snapshot','profit_net','components','source_article_id','hourly_cost_minor'].includes(key),'private field in public DTO: '+key);check(child);}}
    check(loaded.value);return {customer,view:loaded.value};
  }
  async function decide(customer,view,decision,retry=false){
    await customer.getByRole('button',{name:decision==='accepted'?'Angebot annehmen':'Angebot ablehnen',exact:true}).click();
    await customer.getByText(view.statements[decision],{exact:true}).waitFor();await customer.getByLabel('Ihr vollständiger Name',{exact:true}).fill('Synthetic customer representative');
    await customer.getByLabel('Ich bestätige diese Erklärung zum angezeigten Angebot.',{exact:true}).check();
    let response=wait('POST','/portal/offer/decision');await customer.getByRole('button',{name:decision==='accepted'?'Annahme verbindlich erklären':'Ablehnung verbindlich erklären',exact:true}).click();
    const first=await response;assert.equal(first.status,201);
    if(retry){await customer.getByRole('button',{name:'Unverändert erneut senden',exact:true}).waitFor();response=wait('POST','/portal/offer/decision');await customer.getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();
      const repeated=await response;assert.equal(repeated.status,201);assert.deepEqual(first.body,repeated.body);assert.deepEqual(first.value,repeated.value);}
    await customer.getByRole('heading',{name:decision==='accepted'?'Annahme dokumentiert':'Ablehnung dokumentiert',exact:true}).waitFor();return first.value;
  }
  async function documentsEnabled(enabled){
    if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await navigate(page,'Einstellungen');const current=page.locator('form[data-form^="organization-"]'),next=Number((await current.getAttribute('data-form')).split('-').at(-1))+1;
    await page.getByLabel('Belege fachlich aktiv',{exact:true}).setChecked(enabled);await current.getByRole('button',{name:'Bedarf und Module speichern',exact:true}).click();
    await page.locator(`form[data-form="organization-${next}"]`).waitFor();await ready(page);
  }
  try{
    const [acceptedOffer,declinedOffer]=fixture.portal_offers;await openOffer(acceptedOffer);let modal=await fillGrant(),response=wait('POST','/business/portal/grants');
    await modal.getByRole('button',{name:'Kundenzugang verbindlich freigeben',exact:true}).click();const lost=await response;assert.equal(lost.status,201);
    await modal.getByRole('alert').waitFor();response=wait('POST','/business/portal/grants');await modal.getByRole('button',{name:'Kundenzugang verbindlich freigeben',exact:true}).click();
    const replay=await response;assert.equal(replay.status,201);assert.deepEqual(lost.body,replay.body);assert.equal(replay.value.grant.id,lost.value.grant.id);assert.equal(replay.value.link_available,false);assert.equal('portal_url' in replay.value,false);
    await page.getByRole('dialog',{name:'Freigabe vorhanden – Link nicht erneut verfügbar',exact:true}).waitFor();assert.equal(await page.getByLabel('Kundenlink',{exact:true}).count(),0);
    await revoke('Diese Freigabe widerrufen');const firstLink=await issueLink();
    const first=await openCustomer(firstLink.link,true);assert.equal(first.view.offer.id,acceptedOffer.id);
    const pdfDownload=first.customer.waitForEvent('download');await first.customer.getByRole('button',{name:'Original-PDF herunterladen',exact:true}).click();
    assert.deepEqual(await fs.readFile(await (await pdfDownload).path()),await fs.readFile(acceptedOffer.pdf_path));
    if(screenshots)await first.customer.screenshot({path:path.join(screenshots,'portal-customer-desktop.png'),fullPage:true});
    const accepted=await decide(first.customer,first.view,'accepted',true);assert.equal(records.filter(record=>record.url.pathname.endsWith('/adopt')).length,0,'customer decision must not adopt automatically');
    modal=await openOffer(acceptedOffer);await modal.getByRole('heading',{name:'Angebot angenommen',exact:true}).waitFor();
    await modal.getByRole('button',{name:'Annahme in Auftragsentwurf übernehmen',exact:true}).click();
    modal=page.getByRole('dialog',{name:'Annahme in Auftragsentwurf übernehmen',exact:true});
    await modal.getByLabel('Ich habe die angenommene Angebotsfassung geprüft und übernehme sie ausdrücklich in einen Auftragsbestätigungsentwurf im bestehenden Projekt.',{exact:true}).check();
    response=wait('POST','/business/portal/offers/'+acceptedOffer.id+'/adopt');await modal.getByRole('button',{name:'Auftragsentwurf erstellen',exact:true}).click();
    const adopted=await response;assert.equal(adopted.status,201);assert.equal(adopted.value.decision_id,accepted.id);
    await page.getByRole('dialog').getByText('Entwurf',{exact:true}).waitFor();assert.equal(adopted.value.project_id,fixture.project_id);
    modal=await openOffer(acceptedOffer);assert.equal(await modal.getByRole('button',{name:'Annahme in Auftragsentwurf übernehmen',exact:true}).count(),0);
    await modal.getByRole('button',{name:'Auftragsentwurf öffnen',exact:true}).waitFor();
    await documentsEnabled(false);modal=await openOffer(acceptedOffer);assert.equal(await modal.getByRole('button',{name:'Kundenzugang freigeben',exact:true}).count(),0);
    await revoke();response=wait('GET','/portal/offer');await first.customer.getByRole('button',{name:'Ansicht aktualisieren',exact:true}).click();assert.ok([401,403,404,410].includes((await response).status));
    await first.customer.getByRole('heading',{name:'Kundenzugang',exact:true}).waitFor();assert.equal(await first.customer.getByText(acceptedOffer.title,{exact:true}).count(),0);
    await documentsEnabled(true);await openOffer(declinedOffer);const secondLink=await issueLink(),second=await openCustomer(secondLink.link);
    assert.equal(second.view.offer.id,declinedOffer.id);assert.notEqual(second.view.offer.id,first.view.offer.id);
    await second.customer.setViewportSize({width:390,height:844});assert.equal(await second.customer.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'customer portal mobile overflow');
    if(screenshots)await second.customer.screenshot({path:path.join(screenshots,'portal-customer-mobile.png'),fullPage:true});
    await decide(second.customer,second.view,'declined');modal=await openOffer(declinedOffer);await modal.getByRole('heading',{name:'Angebot abgelehnt',exact:true}).waitFor();
    assert.equal(await modal.getByRole('button',{name:'Annahme in Auftragsentwurf übernehmen',exact:true}).count(),0);
    await second.customer.getByRole('button',{name:'Zugang beenden',exact:true}).click();await second.customer.getByRole('heading',{name:'Kundenzugang',exact:true}).waitFor();
    assert.deepEqual(errors,[]);await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();await ready(page);
    console.log('browser: isolated customer portal, exact PDF, lost link/session/decision replies, accept/decline, explicit draft adoption and revoke during module pause passed');
  }finally{await context.unroute(pattern);for(const item of waiting)clearTimeout(item.timer);waiting.clear();for(const customer of customers)await customer.close();}
}
module.exports={portalFlow};
