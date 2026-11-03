/* Real MFA/HTTP physical count UI; only synthetic local stock is changed. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const request=values=>({request_id:crypto.randomUUID().replaceAll('-',''),...values});

async function inventoryCountsFlow({page,context,navigate,ready,fixture,screenshots}){
  let authorization,lost=true;const posts=[];
  const capture=req=>{if(new URL(req.url()).origin===fixture.base_url&&req.headers().authorization)authorization=req.headers().authorization;};
  page.on('request',capture);
  async function api(suffix,body,status=200){
    assert.ok(authorization?.startsWith('Bearer '));
    const result=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});
    assert.equal(result.status(),status,suffix+' '+await result.text());return result.json();
  }
  const dialog=title=>page.getByRole('dialog',{name:title,exact:true});
  const close=()=>page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await context.route('**/api/v1/business/inventory/counts/*/approve',async route=>{
    const req=route.request(),response=await route.fetch({maxRedirects:0});posts.push({body:req.postDataJSON(),status:response.status(),value:await response.json()});
    if(lost){lost=false;assert.equal(response.status(),200);await route.abort('failed');}else await route.fulfill({response});
  });
  try{
    await navigate(page,'Material');
    const article=await api('/articles',request({code:'SYN-COUNT-ARTICLE',name:'Synthetischer Zählartikel',kind:'material',unit:'Stk',unit_price_net:'7',cost_price_net:'2',tax_rate:'19',tax_category:'S',currency:'EUR',active:true}));
    const location=await api('/inventory/locations',request({name:'Synthetisches Zähllager'}),201);
    await api('/inventory/movements',request({kind:'receive',article_id:article.id,to_location_id:location.id,quantity:'10',unit_cost_net:'2'}),201);
    await navigate(page,'Material');await page.getByRole('button',{name:'Inventur öffnen',exact:true}).click();
    await dialog('Inventur').getByRole('button',{name:'Neue Inventur',exact:true}).click();
    await dialog('Lagerort auswählen').getByLabel('Lagerort',{exact:true}).selectOption(location.id);
    await dialog('Lagerort auswählen').getByRole('button',{name:'Artikel auswählen',exact:true}).click();
    const open=dialog('Inventur beginnen');await open.getByLabel('Inventurtitel',{exact:true}).fill('Synthetische Browserinventur');
    await open.getByLabel('Tatsächlicher Zähltag',{exact:true}).fill('2026-11-03');
    await open.getByLabel('Anlass / Korrekturgrund',{exact:true}).fill('Physisch gezählt');
    await open.getByLabel('Zu zählende Artikel',{exact:true}).selectOption([article.id]);
    await open.getByRole('button',{name:'Zählumfang festhalten',exact:true}).click();
    await dialog('Synthetische Browserinventur').getByRole('button',{name:'Mengen zählen',exact:true}).click();
    const count=dialog('Mengen zählen');await count.getByLabel('Gezählte Menge · Synthetischer Zählartikel',{exact:true}).fill('8');
    await count.getByLabel('Differenzgrund · Synthetischer Zählartikel',{exact:true}).fill('Zwei beschädigte Einheiten');
    await count.getByRole('button',{name:'Zählung dokumentieren',exact:true}).click();
    await dialog('Synthetische Browserinventur').getByRole('button',{name:'Differenzen prüfen und freigeben',exact:true}).click();
    await dialog('Inventurdifferenzen prüfen').getByRole('button',{name:'Bewertung berechnen',exact:true}).click();
    const approval=dialog('Bestandsdifferenzen freigeben');assert.match(await approval.innerText(),/-4,0000/);
    await approval.getByLabel('Ich bestätige die gezählten Mengen, Differenzgründe und Lagerbewertung.',{exact:true}).check();
    await approval.getByRole('button',{name:'Differenzen verbindlich buchen',exact:true}).click();await approval.getByRole('alert').waitFor();
    await close();await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();
    await page.getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();
    await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
    assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);assert.deepEqual(posts[0].value,posts[1].value);
    const stock=await api('/inventory/stock?location_id='+location.id+'&article_id='+article.id);assert.equal(stock.on_hand,'8.0000');assert.equal(stock.stock_value_net,'16.00');
    const counts=await api('/inventory/counts');const saved=counts.items.find(item=>item.title==='Synthetische Browserinventur');assert.equal(saved.revision,3);assert.equal(saved.status,'approved');
    await page.getByRole('button',{name:'Inventur öffnen',exact:true}).click();await dialog('Inventur').getByRole('button',{name:'Inventur öffnen',exact:true}).click();
    await dialog('Synthetische Browserinventur').getByRole('button',{name:'Fassungen anzeigen',exact:true}).click();
    await dialog('Inventurhistorie').waitFor();
    assert.equal(await dialog('Inventurhistorie').getByRole('button',{name:'Fassung öffnen',exact:true}).count(),3);
    await dialog('Inventurhistorie').getByRole('button',{name:'Fassung öffnen',exact:true}).nth(1).click();
    assert.match(await dialog('Synthetische Browserinventur').innerText(),/Fassung 2/);
    assert.equal(await dialog('Synthetische Browserinventur').getByRole('button',{name:'Differenzen prüfen und freigeben',exact:true}).count(),0);
    await page.screenshot({path:path.join(screenshots,'inventory-counts-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(screenshots,'inventory-counts-mobile.png'),fullPage:true});
    console.log('inventory count: selection, exact counted quantities, explicit valuation approval, lost reply/original retry, one adjustment, historical read-only view and mobile layout passed');
  }finally{page.off('request',capture);await context.unroute('**/api/v1/business/inventory/counts/*/approve');}
}
module.exports={inventoryCountsFlow};
