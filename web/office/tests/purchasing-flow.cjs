/* Real authenticated browser purchasing flow against the disposable fixture. */
const assert=require('node:assert/strict');
const path=require('node:path');
const SUPPLIER='Synthetic browser supplier';
const ORDER_REFERENCE='SYN-BROWSER-ORDER';
const RECEIPT_REFERENCE='SYN-BROWSER-PARTIAL';
const REST_REFERENCE='SYN-BROWSER-REST';
const detail=page=>page.getByRole('dialog',{name:'Bestellung · '+SUPPLIER,exact:true});
const purchaseResponse=(page,suffix,method='POST')=>page.waitForResponse(response=>
  new URL(response.url()).pathname.endsWith(suffix)&&response.request().method()===method).then(async response=>{
    // Read before the successful form refresh can discard the CDP resource.
    const value=await response.json(),status=response.status(),request=response.request();
    return {status:()=>status,json:async()=>value,request:()=>request};
  });
async function orderReady(page,status){await detail(page).waitFor();await detail(page).getByText(status,{exact:true}).waitFor();}
async function close(page){await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();}

async function purchasingFlow({page,context,navigate,ready,fixture,screenshots}){
  await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);await navigate(page,'Material');
  const stock=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Lagerbestand',exact:true})});
  assert.match(await stock.locator('tbody').innerText(),/10,0000 m/);
  await page.getByRole('button',{name:'Bestellvorschlag anlegen',exact:true}).click();
  let modal=page.getByRole('dialog',{name:'Bestellvorschlag anlegen',exact:true});
  await modal.getByLabel('Lieferant',{exact:true}).fill(SUPPLIER);
  await modal.getByLabel('Bestellartikel',{exact:true}).selectOption({label:'SYN-CABLE · Synthetic cable (m)'});
  await modal.getByLabel('Bestellmenge',{exact:true}).fill('6,0000');
  let response=purchaseResponse(page,'/business/inventory/orders');
  await modal.getByRole('button',{name:'Vorschlag speichern',exact:true}).click();
  const created=await response;assert.equal(created.status(),201);const initial=await created.json();
  assert.equal(initial.status,'draft');assert.equal(initial.revision,1);assert.equal(initial.project_id,fixture.project_id);
  await orderReady(page,'Bestellvorschlag');assert.equal(await detail(page).getByRole('button',{name:'Lieferung erfassen',exact:true}).count(),0);
  await detail(page).getByRole('button',{name:'Bestellvorschlag bearbeiten',exact:true}).click();
  modal=page.getByRole('dialog',{name:'Bestellvorschlag bearbeiten',exact:true});
  assert.equal(await modal.getByLabel('Lieferant',{exact:true}).inputValue(),SUPPLIER);
  assert.equal(await modal.getByLabel('Bestellmenge',{exact:true}).inputValue(),'6.0000');
  await modal.getByLabel('Bestellmenge',{exact:true}).fill('5,0000');
  response=purchaseResponse(page,'/business/inventory/orders/'+initial.id);
  await modal.getByRole('button',{name:'Vorschlag speichern',exact:true}).click();
  const edited=await response;assert.equal(edited.status(),200);const changed=await edited.json();
  assert.equal(changed.id,initial.id);assert.equal(changed.revision,2);assert.equal(changed.items[0].quantity,'5.0000');
  assert.equal(edited.request().postDataJSON().revision,1);
  await orderReady(page,'Bestellvorschlag');
  await detail(page).getByRole('button',{name:'Vorschlag freigeben',exact:true}).click();
  modal=page.getByRole('dialog',{name:'Bestellvorschlag freigeben',exact:true});
  response=purchaseResponse(page,'/business/inventory/orders/'+initial.id);
  await modal.getByRole('button',{name:'Vorschlag verbindlich freigeben',exact:true}).click();
  const approved=await response;assert.equal(approved.status(),200);assert.equal((await approved.json()).revision,3);
  await orderReady(page,'Freigegeben');assert.equal(await detail(page).getByRole('button',{name:'Bestellvorschlag bearbeiten',exact:true}).count(),0);
  await detail(page).getByRole('button',{name:'Extern erteilte Bestellung dokumentieren',exact:true}).click();
  modal=page.getByRole('dialog',{name:'Extern erteilte Bestellung dokumentieren',exact:true});
  await modal.getByLabel('Bestellreferenz',{exact:true}).fill(ORDER_REFERENCE);
  const orderedOn=await modal.getByLabel('Tatsächliches Bestelldatum',{exact:true}).inputValue();
  await modal.getByLabel('Ich bestätige, dass diese Bestellung bereits extern erteilt wurde.',{exact:true}).check();
  response=purchaseResponse(page,'/purchasing/orders/'+initial.id+'/confirm');
  await modal.getByRole('button',{name:'Bestellung dokumentieren',exact:true}).click();
  const confirmed=await response;assert.equal(confirmed.status(),200);const ordered=await confirmed.json();
  assert.equal(ordered.status,'ordered');assert.equal(ordered.delivery_status,'not_sent');assert.equal(ordered.receipt_revision,0);
  const {request_id:confirmationId,...confirmation}=confirmed.request().postDataJSON();assert.match(confirmationId,/^[a-f0-9]{32}$/);
  assert.deepEqual(confirmation,{source_revision:3,expected_receipt_revision:0,order_reference:ORDER_REFERENCE,ordered_on:orderedOn,confirmation:true});
  await orderReady(page,'Bestellung dokumentiert');
  await detail(page).getByRole('button',{name:'Lieferung erfassen',exact:true}).click();
  modal=page.getByRole('dialog',{name:'Lieferung erfassen',exact:true});
  await modal.getByLabel('Lieferschein / Belegreferenz',{exact:true}).fill(RECEIPT_REFERENCE);
  await modal.getByLabel('Ziellager',{exact:true}).selectOption({label:'Synthetic main store'});
  await modal.getByLabel('Pos. 1 · Synthetic cable – Liefermenge (m)',{exact:true}).fill('2,0000');
  await modal.getByRole('button',{name:'Wareneingang verbindlich buchen',exact:true}).click();
  await modal.getByRole('alert').filter({hasText:'Einstandspreis'}).waitFor();
  await modal.getByLabel('Pos. 1 · Einstand netto EUR / m',{exact:true}).fill('2,0000');
  const calls=[],receiptReplies=[],receiptRoute='**/api/v1/business/purchasing/orders/'+initial.id+'/receipts';
  await context.route(receiptRoute,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    calls.push(route.request().postDataJSON());
    const result=await route.fetch();assert.equal(result.status(),201);receiptReplies.push(await result.json());
    if(calls.length===1)await route.abort('failed');else await route.fulfill({response:result});
  });
  try{
    await modal.getByRole('button',{name:'Wareneingang verbindlich buchen',exact:true}).click();
    await modal.getByRole('alert').waitFor();
    assert.equal(await modal.getByLabel('Pos. 1 · Synthetic cable – Liefermenge (m)',{exact:true}).inputValue(),'2,0000');
    // For fulfilled intercepted requests Chromium may evict the CDP body;
    // the real server JSON is captured from route.fetch above instead.
    response=page.waitForResponse(result=>new URL(result.url()).pathname.endsWith('/purchasing/orders/'+initial.id+'/receipts')&&result.request().method()==='POST');
    await modal.getByRole('button',{name:'Wareneingang verbindlich buchen',exact:true}).click();
    const receipt=await response;assert.equal(receipt.status(),201);assert.equal(receiptReplies.at(-1).receipt_revision,1);
  }finally{await context.unroute(receiptRoute);}
  assert.equal(calls.length,2);assert.deepEqual(calls[0],calls[1]);
  assert.deepEqual(receiptReplies[0],receiptReplies[1]);
  assert.equal(calls[0].source_revision,3);assert.equal(calls[0].expected_receipt_revision,0);
  assert.deepEqual(calls[0].lines,[{line_index:0,quantity:'2.0000',unit_cost_net:'2.0000'}]);
  await orderReady(page,'Teillieferung');
  assert.equal(await detail(page).getByRole('heading',{name:RECEIPT_REFERENCE,exact:true}).count(),1);
  assert.match(await detail(page).locator('table').first().innerText(),/5,0000 m\s+2,0000 m\s+3,0000 m/);
  await close(page);await ready(page);assert.match(await stock.locator('tbody').innerText(),/12,0000 m/);
  await page.locator('.list-row').filter({has:page.getByRole('heading',{name:SUPPLIER,exact:true})}).getByRole('button',{name:'Bestellung ansehen',exact:true}).click();
  await orderReady(page,'Teillieferung');
  await page.setViewportSize({width:390,height:844});
  await detail(page).getByRole('button',{name:'Lieferung erfassen',exact:true}).click();
  modal=page.getByRole('dialog',{name:'Lieferung erfassen',exact:true});
  await modal.getByLabel('Lieferschein / Belegreferenz',{exact:true}).fill(REST_REFERENCE);
  await modal.getByLabel('Ziellager',{exact:true}).selectOption({label:'Synthetic main store'});
  await modal.getByRole('button',{name:'Restmengen übernehmen',exact:true}).click();
  assert.equal(await modal.getByLabel('Pos. 1 · Synthetic cable – Liefermenge (m)',{exact:true}).inputValue(),'3.0000');
  assert.equal(await modal.getByLabel('Pos. 1 · Einstand netto EUR / m',{exact:true}).inputValue(),'');
  await modal.getByLabel('Pos. 1 · Einstand netto EUR / m',{exact:true}).fill('2');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'mobile purchasing form overflow');
  if(screenshots)await page.screenshot({path:path.join(screenshots,'purchasing-mobile.png'),fullPage:false});
  response=purchaseResponse(page,'/purchasing/orders/'+initial.id+'/receipts');
  await modal.getByRole('button',{name:'Wareneingang verbindlich buchen',exact:true}).click();
  const finalReceipt=await response;assert.equal(finalReceipt.status(),201);
  const finalBody=finalReceipt.request().postDataJSON();assert.equal(finalBody.expected_receipt_revision,1);
  assert.equal((await finalReceipt.json()).receipt_revision,2);assert.notEqual(finalBody.request_id,calls[0].request_id);
  await orderReady(page,'Vollständig geliefert');
  assert.match(await detail(page).locator('table').first().innerText(),/5,0000 m\s+5,0000 m\s+0,0000 m/);
  assert.equal(await detail(page).getByRole('button',{name:'Lieferung erfassen',exact:true}).count(),0);
  assert.equal(await detail(page).getByRole('heading',{name:RECEIPT_REFERENCE,exact:true}).count(),1);
  assert.equal(await detail(page).getByRole('heading',{name:REST_REFERENCE,exact:true}).count(),1);
  assert.equal(await detail(page).getByRole('columnheader',{name:'Einstand je Einheit',exact:true}).count(),2);
  if(screenshots){await detail(page).getByRole('heading',{name:'Lieferhistorie',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(screenshots,'purchasing-mobile-history.png'),fullPage:false});}
  await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>!document.querySelector('.sidebar').inert);
  if(screenshots){await detail(page).evaluate(node=>{node.scrollTop=0;});await page.screenshot({path:path.join(screenshots,'purchasing-desktop-history.png'),fullPage:false});}
  await close(page);await ready(page);assert.match(await stock.locator('tbody').innerText(),/15,0000 m/);
  console.log('browser: editable proposal, approval, explicit external order and partial/rest receipts persisted; lost acknowledgement retried one stock booking and mobile form passed');
  return initial.id;
}

async function purchasingReadOnly({page,navigate,ready,orderId}){
  await navigate(page,'Material');
  assert.equal(await page.getByRole('button',{name:'Bestellvorschlag anlegen',exact:true}).count(),0);
  const response=purchaseResponse(page,'/purchasing/orders/'+orderId+'/receipts','GET');
  await page.locator('.list-row').filter({has:page.getByRole('heading',{name:SUPPLIER,exact:true})}).getByRole('button',{name:'Bestellung ansehen',exact:true}).click();
  const receipts=await (await response).json();assert.equal(receipts.items.length,2);
  for(const receipt of receipts.items)for(const line of receipt.lines){assert.equal('unit_cost_net' in line,false);assert.equal('cost_net' in line,false);}
  await orderReady(page,'Vollständig geliefert');
  assert.equal(await detail(page).getByRole('columnheader',{name:'Einstand je Einheit',exact:true}).count(),0);
  assert.equal(await detail(page).getByRole('columnheader',{name:'Kosten netto',exact:true}).count(),0);
  assert.equal(await detail(page).getByRole('heading',{name:RECEIPT_REFERENCE,exact:true}).count(),1);
  await close(page);await ready(page);
  console.log('browser: technician reads delivery history without financial fields or purchasing write controls');
}
module.exports={purchasingFlow,purchasingReadOnly};
