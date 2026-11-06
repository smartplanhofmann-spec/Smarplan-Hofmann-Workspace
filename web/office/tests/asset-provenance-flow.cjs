const {selectProject}=require('./e2e.cjs');
/* Real C UI: immutable original, explicit device source, lost reply and source links. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const path=require('node:path');
const request=values=>({request_id:crypto.randomUUID().replaceAll('-',''),...values});

async function assetProvenanceFlow({page,context,navigate,ready,fixture,screenshots}){
  let authorization,loseCreate=true;const records=[],errors=[];
  const capture=req=>{if(new URL(req.url()).origin===fixture.base_url&&req.headers().authorization)authorization=req.headers().authorization;};
  page.on('request',capture);
  async function api(suffix,body,status=200){assert.ok(authorization?.startsWith('Bearer '));const result=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.equal(result.status(),status,(body?'POST ':'GET ')+suffix);return result.json();}
  const modal=title=>page.getByRole('dialog',{name:title,exact:true});
  const close=()=>page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
  async function sources(){await page.getByRole('button',{name:'Lieferungen und Geräte',exact:true}).click();await modal('Lieferungen und Geräte').waitFor();}
  async function origin(){await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Anlagen',exact:true})}).locator('.list-row').filter({hasText:'Synthetisches Herkunftsgerät'}).getByRole('button',{name:'Lieferherkunft',exact:true}).click();await modal('Geräteherkunft · Synthetisches Herkunftsgerät').waitFor();}
  const routePattern='**/api/v1/business/**';
  await context.route(routePattern,async route=>{
    const req=route.request(),url=new URL(req.url());
    if(!url.pathname.startsWith('/api/v1/business/assets')&&!/\/purchasing\/receipts\/[^/]+\/document$/.test(url.pathname))return route.fallback();
    try{assert.equal(url.origin,fixture.base_url);const reply=await route.fetch({maxRedirects:0}),value=await reply.json();records.push({path:url.pathname,method:req.method(),body:req.method()==='POST'?req.postDataJSON():null,status:reply.status(),value});
      if(loseCreate&&req.method()==='POST'&&url.pathname.endsWith('/assets/from-delivery')){assert.equal(reply.status(),201);loseCreate=false;await route.abort('failed');}else await route.fulfill({response:reply});
    }catch(error){errors.push(error.message);await route.abort('failed').catch(()=>{});}
  });
  try{
    await selectProject(page,fixture.project_id);await ready(page);await navigate(page,'Material');
    const article=await api('/articles',request({code:'SYN-ORIGIN-DEVICE',name:'Synthetisches Herkunftsgerät',kind:'material',unit:'Stk',unit_price_net:'75',cost_price_net:'40',tax_rate:'19',tax_category:'S',currency:'EUR',active:true}));
    const location=await api('/inventory/locations',request({name:'Synthetisches Herkunftslager'}),201);
    const order=await api('/inventory/orders',request({project_id:fixture.project_id,supplier_name:'Synthetischer Herkunftslieferant',status:'approved',items:[{article_id:article.id,quantity:'1'}]}),201);
    const current=await api('/purchasing/orders/'+order.id);
    await api('/purchasing/orders/'+order.id+'/confirm',request({source_revision:current.source_revision,expected_receipt_revision:0,order_reference:'SYN-ORIGIN-ORDER',ordered_on:'2026-11-01',confirmation:true}));
    const receipt=await api('/purchasing/orders/'+order.id+'/receipts',request({source_revision:current.source_revision,expected_receipt_revision:0,receipt_reference:'SYN-ORIGIN-DELIVERY',received_on:'2026-11-02',location_id:location.id,lines:[{line_index:0,quantity:'1',unit_cost_net:'40'}]}),201);
    const issue=await api('/inventory/movements',request({kind:'issue',article_id:article.id,from_location_id:location.id,project_id:fixture.project_id,quantity:'1'}),201);
    const before=await api('/projects/'+fixture.project_id+'/costs');
    await navigate(page,'Projekte');await page.getByRole('tab',{name:'Wartung',exact:true}).click();await ready(page);await sources();
    await modal('Lieferungen und Geräte').getByRole('button',{name:'Lieferschein zuordnen',exact:true}).click();
    let editor=modal('Lieferschein zuordnen');await editor.getByLabel('Original des Lieferscheins',{exact:true}).selectOption({label:'site-0.png'});
    await editor.getByLabel('Ich habe Original und Wareneingang geprüft und ordne diesen Lieferschein dauerhaft zu.',{exact:true}).check();await editor.getByRole('button',{name:'Original verbindlich zuordnen',exact:true}).click();
    await modal('Original-Lieferschein').waitFor();assert.match(await modal('Original-Lieferschein').innerText(),/SYN-ORIGIN-DELIVERY/);
    const download=page.waitForEvent('download');await modal('Original-Lieferschein').getByRole('button',{name:'Original herunterladen',exact:true}).click();assert.deepEqual(await fs.readFile(await(await download).path()),await fs.readFile(fixture.photo_path));await close();
    await sources();await modal('Lieferungen und Geräte').getByRole('button',{name:'Gerät aus Lieferung',exact:true}).click();editor=modal('Gerät aus Lieferung anlegen');
    await editor.getByLabel('Seriennummer',{exact:true}).fill('SYN-ORIGIN-SERIAL');await editor.getByLabel('Tatsächliche Materialentnahme',{exact:true}).selectOption(issue.id);await editor.getByLabel('Ich bestätige, dass dieses Gerät tatsächlich aus der genannten Lieferung und Entnahme stammt.',{exact:true}).check();
    await editor.getByRole('button',{name:'Gerät und Herkunft anlegen',exact:true}).click();await editor.getByRole('alert').waitFor();assert.match(await editor.innerText(),/Keine sichere Antwort/);await close();
    await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
    const attempts=records.filter(row=>row.method==='POST'&&row.path.endsWith('/assets/from-delivery'));assert.equal(attempts.length,2);assert.deepEqual(attempts[0].body,attempts[1].body);assert.deepEqual(attempts[0].value,attempts[1].value);
    const result=attempts[1].value;assert.equal(result.origin.receipt_id,receipt.id);assert.equal(result.origin.issue_movement_id,issue.id);assert.deepEqual(await api('/projects/'+fixture.project_id+'/costs'),before);
    const assets=await api('/assets?project_id='+fixture.project_id);assert.equal((Array.isArray(assets)?assets:assets.items).filter(row=>row.serial_number==='SYN-ORIGIN-SERIAL').length,1);
    const contract=await api('/maintenance/contracts',request({project_id:fixture.project_id,asset_id:result.id,title:'Synthetische Gerätewartung',anchor_date:'2026-11-03',interval_unit:'months',interval_count:12}),201);
    const scheduled=await api('/maintenance/schedule',request({project_id:fixture.project_id,as_of:'2026-11-03'}));const visit=scheduled.items.find(row=>row.contract_id===contract.id);assert.ok(visit);
    const report=await api('/service-reports',request({project_id:fixture.project_id,title:'Synthetischer Herkunftsservice',description:'Seriennummer und Funktion geprüft.'}),201);
    await api('/service-reports/'+report.id+'/sign',request({revision:report.revision,expected_hash:report.content_hash,signer:'Synthetischer Betreiber',strokes:[[[.1,.2],[.8,.5]]]}));
    const completed=await api('/maintenance/visits/'+visit.id+'/complete',request({revision:visit.revision,report_id:report.id}));
    await sources();assert.equal(await modal('Lieferungen und Geräte').getByRole('button',{name:'Gerät aus Lieferung',exact:true}).count(),0);await close();
    await origin();assert.match(await modal('Geräteherkunft · Synthetisches Herkunftsgerät').innerText(),/SYN-ORIGIN-SERIAL/);
    assert.match(await modal('Geräteherkunft · Synthetisches Herkunftsgerät').innerText(),/Synthetische Gerätewartung/);
    const serviceDownload=page.waitForEvent('download');await modal('Geräteherkunft · Synthetisches Herkunftsgerät').getByRole('button',{name:'Service-PDF',exact:true}).click();const serviceBytes=await fs.readFile(await(await serviceDownload).path());assert.equal(crypto.createHash('sha256').update(serviceBytes).digest('hex'),completed.report_pdf_sha256);
    await page.screenshot({path:path.join(screenshots,'asset-provenance-desktop.png'),fullPage:true});
    await modal('Geräteherkunft · Synthetisches Herkunftsgerät').getByRole('button',{name:'Materialentnahme öffnen',exact:true}).click();await modal('Materialentnahme').waitFor();assert.match(await modal('Materialentnahme').innerText(),/1,0000 Stk/);await close();
    await origin();await modal('Geräteherkunft · Synthetisches Herkunftsgerät').getByRole('button',{name:'Bestellung öffnen',exact:true}).click();await modal('Bestellung · Synthetischer Herkunftslieferant').waitFor();assert.match(await modal('Bestellung · Synthetischer Herkunftslieferant').innerText(),/SYN-ORIGIN-ORDER/);await close();
    await origin();await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'asset-provenance-mobile.png'),fullPage:true});await close();await page.setViewportSize({width:1440,height:1000});
    assert.deepEqual(errors,[]);console.log('asset provenance: original selection/download, explicit physical origin, lost reply and exact retry, one device, unchanged cost, order/issue links and signed maintenance PDF passed');
  }finally{page.off('request',capture);await context.unroute(routePattern);await fs.writeFile(path.join(screenshots,'asset-provenance-http-records.json'),JSON.stringify(records,null,2));}
}
module.exports={assetProvenanceFlow};
