/* Real E1a browser forms, MFA and disposable HTTP/SQLite. No bank or token injection. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
async function accountingFlow({page,context,navigate,ready,login,fixture,screenshots}) {
  const waiting=new Set(),records=[],errors=[],pattern='**/api/v1/business/**';let losePayout=true;
  function wait(method,suffix) { const promise=new Promise((resolve,reject)=>{
    const item={method,suffix,resolve:value=>{clearTimeout(item.timer);waiting.delete(item);resolve(value);},reject:error=>{clearTimeout(item.timer);waiting.delete(item);reject(error);}};
    item.timer=setTimeout(()=>item.reject(new Error('Expected accounting HTTP response: '+method+' '+suffix)),15000);waiting.add(item);
  });promise.catch(()=>{});return promise; }
  await context.route(pattern,async route=>{
    const request=route.request(),url=new URL(request.url()),method=request.method();
    if(!url.pathname.startsWith('/api/v1/business/accounting/')){await route.fallback();return;}
    try {
      assert.equal(url.origin,fixture.base_url);assert.equal(url.searchParams.has('project_id'),false);
      for(const key of url.searchParams.keys())assert.ok(['limit','offset'].includes(key));
      const response=await route.fetch({maxRedirects:0}),value=await response.json(),record={method,path:url.pathname,body:request.postDataJSON(),status:response.status(),value};records.push(record);
      if(losePayout&&method==='POST'&&url.pathname.endsWith('/events/payout')){losePayout=false;await route.abort('failed');}else await route.fulfill({response});
      for(const item of [...waiting])if(item.method===method&&url.pathname.endsWith(item.suffix))item.resolve(record);
    } catch(error) { errors.push(error.message);for(const item of [...waiting])item.reject(error);await route.abort('failed').catch(()=>{}); }
  });
  async function tab(name,target=page){await target.getByRole('button',{name,exact:true}).click();await ready(target);}
  async function open(target=page){await navigate(target,'Finanzen');await target.getByRole('button',{name:'EÜR-Vorbereitung',exact:true}).click();await target.getByRole('heading',{name:'EÜR-Vorbereitung',exact:true}).waitFor();await target.getByRole('heading',{name:'Vorjournal',exact:true}).waitFor();await ready(target);}
  const receipt=fixture.accounting_receipts[0];
  const receiptRow=()=>page.locator('.list-row').filter({has:page.getByRole('heading',{name:receipt.vendor+' · '+receipt.invoice,exact:true})});
  async function accountEdit(name,active) {
    await tab('Geldkonten');await page.getByRole('button',{name:'Konto bearbeiten',exact:true}).click();const modal=page.getByRole('dialog',{name:'Geldkonto bearbeiten',exact:true});
    await modal.getByLabel('Kontoname',{exact:true}).fill(name);await modal.getByLabel('Konto für neue Geldflüsse aktiv',{exact:true}).setChecked(active);await modal.getByLabel('Ich bestätige diese Kontofassung.',{exact:true}).check();
    const reply=wait('POST','/accounts/'+account.id);await modal.getByRole('button',{name:'Kontofassung speichern',exact:true}).click();const result=await reply;assert.equal(result.status,200);await modal.waitFor({state:'detached'});await ready(page);return result.value;
  }
  async function financeEnabled(enabled) {
    await navigate(page,'Einstellungen');const current=page.locator('form[data-form^="organization-"]'),next=Number((await current.getAttribute('data-form')).split('-').at(-1))+1;
    await page.getByLabel('Finanzen fachlich aktiv',{exact:true}).setChecked(enabled);await current.getByRole('button',{name:'Bedarf und Module speichern',exact:true}).click();await page.locator(`form[data-form="organization-${next}"]`).waitFor();await ready(page);
  }
  async function fillCash(modal,evidence) {
    await modal.getByLabel('Geldkonto',{exact:true}).selectOption(account.id);await modal.getByLabel('Tatsächlicher Geldflusstag',{exact:true}).fill('2026-11-02');await modal.getByLabel('Geldfluss-Nachweisreferenz',{exact:true}).fill(evidence);
  }
  let account,bookkeeper;
  try {
    await page.getByLabel('Aktuelles Projekt').selectOption('');await ready(page);await open();
    assert.match(await page.locator('main').innerText(),/Nur freigegebene Quellen/);assert.match(await page.locator('main').innerText(),/keine steuerlichen Summen/);
    // The supported-feature fallback must not call a nonexistent endpoint.
    const capsPattern='**/api/v1/business/capabilities';let requests=records.length;
    await context.route(capsPattern,async route=>{assert.equal(new URL(route.request().url()).origin,fixture.base_url);const response=await route.fetch({maxRedirects:0}),value=await response.json();await route.fulfill({response,json:{...value,features:value.features.filter(feature=>feature!=='accounting_prejournal')}});});
    await navigate(page,'Finanzen');await page.getByText('Dieser Server bietet das EÜR-Vorjournal noch nicht an.',{exact:false}).waitFor();assert.equal(records.length,requests);await context.unroute(capsPattern);await navigate(page,'Finanzen');await page.getByRole('heading',{name:'Vorjournal',exact:true}).waitFor();
    await tab('Geldkonten');await page.getByRole('button',{name:'Geldkonto anlegen',exact:true}).click();let modal=page.getByRole('dialog',{name:'Geldkonto anlegen',exact:true});
    await modal.getByLabel('Stabiler Kontocode',{exact:true}).fill('SYN-MAIN');await modal.getByLabel('Kontoname',{exact:true}).fill('Synthetic original cash account');await modal.getByLabel('Kontoart',{exact:true}).selectOption('bank');await modal.getByLabel('Ich bestätige diese Kontofassung.',{exact:true}).check();
    let response=wait('POST','/accounting/accounts');await modal.getByRole('button',{name:'Geldkonto anlegen',exact:true}).click();let result=await response;assert.equal(result.status,201);account=result.value;await modal.waitFor({state:'detached'});await ready(page);
    await tab('Kundenzahlungen');
    for(const payment of fixture.accounting_payments) {
      const item=page.locator('.list-row').filter({hasText:'Synthetic accounting '+payment.kind});await item.getByRole('button',{name:'Bestehende Zahlung verknüpfen',exact:true}).click();modal=page.getByRole('dialog',{name:'Bestehende Zahlung verknüpfen',exact:true});await fillCash(modal,'SYN-IMPORT-'+payment.kind);
      assert.equal(await modal.getByLabel('Tatsächlich ausgezahlter Betrag EUR',{exact:true}).count(),0);await modal.getByLabel('Ich habe Quelle, Konto, Geldflusstag und Nachweis geprüft.',{exact:true}).check();response=wait('POST','/events/import-payment');await modal.getByRole('button',{name:'Geprüfte Zahlung verknüpfen',exact:true}).click();result=await response;assert.equal(result.status,201);
      assert.equal(result.value.direction,payment.kind==='refund'?'out':'in');assert.equal(result.value.source.snapshot.kind,payment.kind);assert.equal('amount' in result.body,false);assert.equal('direction' in result.body,false);
      if(payment.kind==='refund')assert.ok(result.value.unresolved_reasons.includes('refund_origin_unresolved'));
      await modal.waitFor({state:'detached'});await ready(page);await item.getByRole('button',{name:'Verknüpften Geldfluss ansehen',exact:true}).waitFor();
    }
    await tab('Auszahlungen');const original=page.waitForEvent('download');await receiptRow().getByRole('button',{name:'Original ansehen',exact:true}).click();assert.deepEqual(await fs.readFile(await(await original).path()),await fs.readFile(receipt.original_path));
    await receiptRow().getByRole('button',{name:'Auszahlung bestätigen',exact:true}).click();modal=page.getByRole('dialog',{name:'Auszahlung bestätigen',exact:true});await fillCash(modal,'SYN-PARTIAL-1');await modal.getByLabel('Tatsächlich ausgezahlter Betrag EUR',{exact:true}).fill('59,50');await modal.getByLabel('Verwendungszweck',{exact:true}).fill('Synthetic confirmed partial payout');await modal.getByLabel('Ich bestätige den tatsächlich geleisteten Geldabfluss mit diesem Beleg und Konto.',{exact:true}).check();
    response=wait('POST','/events/payout');await modal.getByRole('button',{name:'Tatsächliche Auszahlung bestätigen',exact:true}).click();const lost=await response;assert.equal(lost.status,201);assert.equal(lost.value.amount,'59.50');await modal.getByRole('alert').waitFor();await modal.getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await accountEdit('Synthetic renamed inactive account',false);await financeEnabled(false);await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();response=wait('POST','/events/payout');await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();const locked=await response;assert.equal(locked.status,423);assert.deepEqual(locked.body,lost.body);await page.locator('main [role=alert]').waitFor();await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await financeEnabled(true);await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();response=wait('POST','/events/payout');await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();const repeated=await response;assert.equal(repeated.status,201);assert.deepEqual(repeated.body,lost.body);assert.deepEqual(repeated.value,lost.value);assert.equal(repeated.value.account.revision,1);await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
    await navigate(page,'Finanzen');await page.getByRole('heading',{name:'Geldkonten',exact:true}).waitFor();await accountEdit('Synthetic active current account',true);await tab('Auszahlungen');assert.match(await receiptRow().innerText(),/Verbleibend 59,50/);
    await receiptRow().getByRole('button',{name:'Auszahlung bestätigen',exact:true}).click();modal=page.getByRole('dialog',{name:'Auszahlung bestätigen',exact:true});await fillCash(modal,'SYN-REST-2');await modal.getByLabel('Tatsächlich ausgezahlter Betrag EUR',{exact:true}).fill('59.50');await modal.getByLabel('Ich bestätige den tatsächlich geleisteten Geldabfluss mit diesem Beleg und Konto.',{exact:true}).check();response=wait('POST','/events/payout');await modal.getByRole('button',{name:'Tatsächliche Auszahlung bestätigen',exact:true}).click();result=await response;assert.equal(result.status,201);assert.equal(result.body.expected_cash_revision,1);assert.equal(result.body.account_revision,3);assert.equal(result.value.source.snapshot.review_revision,1);await modal.waitFor({state:'detached'});await ready(page);await receiptRow().getByText('Vollständig ausgezahlt',{exact:true}).waitFor();assert.equal(await receiptRow().getByRole('button',{name:'Auszahlung bestätigen',exact:true}).count(),0);
    await tab('Vorjournal');await page.getByRole('heading',{name:'Vorjournal',exact:true}).waitFor();assert.equal(await page.locator('main .list-row').count(),4);assert.match(await page.locator('main').innerText(),/Synthetic original cash account/);
    if(screenshots)await page.screenshot({path:path.join(screenshots,'accounting-desktop.png'),fullPage:true});
    assert.equal(await page.locator('.accounting').evaluate(node=>[...node.childNodes].some(child=>child.nodeType===3&&child.textContent.trim()==='null')),false,'optional notices must not render a null text node');
    await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.querySelector('.sidebar').inert&&document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
    const layout=await page.locator('.accounting .list-row').first().evaluate(node=>{const row=node.getBoundingClientRect(),body=node.querySelector('.body').getBoundingClientRect(),actions=node.querySelector('.actions').getBoundingClientRect();return {rowWidth:row.width,bodyWidth:body.width,bodyBottom:body.bottom,actionsTop:actions.top};});
    assert.ok(layout.bodyWidth>=layout.rowWidth*.9,'mobile text must use the row width');assert.ok(layout.actionsTop>=layout.bodyBottom-1,'mobile actions belong below the financial text');
    if(screenshots)await page.screenshot({path:path.join(screenshots,'accounting-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>!document.querySelector('.sidebar').inert);

    bookkeeper=await context.newPage();bookkeeper.on('pageerror',error=>errors.push(error.message));await bookkeeper.goto(fixture.base_url+'/office/');await login(bookkeeper,'bookkeeper@browser.example.test');await open(bookkeeper);
    await bookkeeper.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await bookkeeper.getByRole('heading',{name:'Vorjournal',exact:true}).waitFor();await ready(bookkeeper);assert.equal(await bookkeeper.locator('main .list-row').count(),2,'assigned project payouts only; owner unallocated imports hidden');
    await tab('Kundenzahlungen',bookkeeper);assert.equal(await bookkeeper.locator('main .list-row').count(),0);await tab('Auszahlungen',bookkeeper);assert.equal(await bookkeeper.getByText('Private accounting supplier',{exact:false}).count(),0);assert.equal(await bookkeeper.locator('main .list-row').count(),1);
    await tab('Vorjournal',bookkeeper);await bookkeeper.getByRole('button',{name:'Nachweis ansehen',exact:true}).first().click();await bookkeeper.getByRole('dialog').getByRole('heading',{name:'Bestätigte Quellfassung',exact:true}).waitFor();
    await navigate(page,'Einstellungen');await page.getByRole('button',{name:'Freigaben ansehen / ändern',exact:true}).click();modal=page.getByRole('dialog',{name:'Fachrechte',exact:true});
    await modal.getByLabel('Benutzer',{exact:true}).selectOption({label:'bookkeeper@browser.example.test'});await modal.getByLabel('Fachrecht',{exact:true}).selectOption('finance.read');await modal.getByLabel('Geltungsbereich',{exact:true}).selectOption(fixture.project_id);await modal.getByLabel('Entscheidung',{exact:true}).selectOption('deny');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    await bookkeeper.getByRole('dialog').getByRole('button',{name:'Original ansehen',exact:true}).click();await bookkeeper.getByRole('dialog').waitFor({state:'detached'});await bookkeeper.locator('main [role=alert]').waitFor();assert.equal(await bookkeeper.getByText(receipt.vendor+' · '+receipt.invoice,{exact:true}).count(),0,'recognized source denial removes stale financial detail');
    assert.deepEqual(errors,[]);assert.equal(records.filter(item=>item.method==='POST'&&item.path.endsWith('/events/payout')&&item.status===201).length,3,'first + identical replay + rest');
    console.log('browser: E1a global rights, legacy fallback, existing receipt/refund imports, exact original, partial/rest payout, lost ACK + module pause + frozen account replay and scoped 390px journal passed');
  } finally {await context.unroute(pattern);for(const item of waiting)clearTimeout(item.timer);waiting.clear();if(bookkeeper)await bookkeeper.close();}
}
module.exports={accountingFlow};
