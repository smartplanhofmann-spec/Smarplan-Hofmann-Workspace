const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

async function invoiceChainFlow({page,context,navigate,ready,fixture,screenshots}){
  const chain=fixture.invoice_chain,records=[],errors=[];let lose=true;
  const pattern='**/api/v1/business/documents/**';
  await context.route(pattern,async route=>{
    const request=route.request(),url=new URL(request.url());
    if(request.method()!=='POST')return route.fallback();
    try{
      const response=await route.fetch({maxRedirects:0}),value=await response.json();
      records.push({path:url.pathname,body:request.postDataJSON(),status:response.status(),value});
      if(lose&&url.pathname.endsWith('/convert')){assert.equal(response.status(),200);lose=false;await route.abort('failed');}
      else await route.fulfill({response});
    }catch(error){errors.push(error.message);await route.abort('failed').catch(()=>{});}
  });
  const modal=()=>page.getByRole('dialog');
  async function open(item){await page.locator('.list-row').filter({hasText:item.title}).getByRole('button',{name:'Öffnen',exact:true}).click();await modal().getByRole('heading',{name:item.number,exact:true}).waitFor();}
  async function close(){await modal().getByRole('button',{name:'Dialog schließen',exact:true}).click();}
  try{
    await page.getByLabel('Aktuelles Projekt').selectOption(chain.project_id);await ready(page);await navigate(page,'Dokumente');
    await open(chain.independent);
    assert.equal(await modal().getByRole('button',{name:'→ Rechnung',exact:true}).count(),0);
    await modal().getByRole('button',{name:'→ Kumulierte Rechnung',exact:true}).click();
    await page.getByRole('button',{name:'1 Antwort offen',exact:true}).waitFor();
    await modal().getByRole('button',{name:'→ Kumulierte Rechnung',exact:true}).click();
    await modal().getByRole('heading',{name:'Kumulierte Rechnung',exact:true}).waitFor();
    const conversions=records.filter(value=>value.path.endsWith('/convert'));
    assert.equal(conversions.length,2);assert.deepEqual(conversions[0].body,conversions[1].body);
    assert.equal(conversions[0].value.id,conversions[1].value.id);
    assert.deepEqual(conversions[1].value.previous_document_ids,[chain.independent.id]);
    assert.equal(await modal().getByRole('button',{name:'→ Kumulierte Rechnung',exact:true}).count(),0,'a draft is not an issued chain source');
    await modal().getByRole('button',{name:'Bearbeiten',exact:true}).click();
    assert.equal(await modal().getByLabel('Belegart',{exact:true}).inputValue(),'cumulative_invoice');
    assert.match(await modal().innerText(),/1 Vorbeleg\(e\).*gesamte bisherige Vertragsleistung/s);
    await modal().getByLabel('Netto / Einheit',{exact:true}).fill('70,00');
    await modal().getByRole('button',{name:'Entwurf speichern',exact:true}).click();
    await modal().waitFor({state:'detached'});await ready(page);
    const saved=records.find(value=>value.path.endsWith('/'+conversions[1].value.id));
    assert.equal(saved.status,200);assert.equal(saved.body.kind,'cumulative_invoice');
    assert.deepEqual(saved.body.previous_document_ids,[chain.independent.id]);
    assert.equal(saved.value.positions[0].unit_price_net,'70.00');
    await open(chain.cumulative);
    assert.equal(await modal().getByRole('button',{name:'→ Kumulierte Rechnung',exact:true}).count(),1);
    assert.equal(await modal().getByRole('button',{name:'→ Schlussrechnung',exact:true}).count(),1);
    await close();await open(chain.final);
    const text=(await modal().innerText()).replace(/\s/g,' ');
    assert.match(text,/Gesamte Vertragsleistung brutto: 119,00/);
    assert.match(text,/Bereits berechnete Vertragsbasis brutto: 83,30/);
    assert.match(text,/Zusätzlich berechneter Rechnungsbetrag/);
    assert.match(text,/Brutto: 35,70/);
    assert.equal(await modal().getByRole('button',{name:/^→ /}).count(),0);
    await page.screenshot({path:path.join(screenshots,'invoice-chain-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(screenshots,'invoice-chain-mobile.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('invoice chain: exact lost-reply conversion, editable cumulative draft with preserved predecessor, final contract/increment distinction and mobile layout passed');
  }finally{
    await fs.writeFile(path.join(screenshots,'invoice-chain-http-records.json'),JSON.stringify(records,null,2));
    await context.unroute(pattern);
  }
}
module.exports={invoiceChainFlow};
