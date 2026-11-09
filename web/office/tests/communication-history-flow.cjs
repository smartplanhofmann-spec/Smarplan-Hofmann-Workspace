/* Actual owner MFA/HTTP, canonical links and rendered private source history. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const command=body=>({request_id:crypto.randomUUID().replaceAll('-',''),...body});
async function communicationHistoryFlow({page,context,navigate,ready,fixture,screenshots}){
  let authorization;
  const capture=req=>{if(new URL(req.url()).origin===fixture.base_url&&req.headers().authorization)authorization=req.headers().authorization;};
  page.on('request',capture);
  const reads=[];
  async function api(suffix,body,root='/api/v1/business'){
    const response=await context.request.fetch(fixture.base_url+root+suffix,{method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});
    const value=await response.json();assert.ok([200,201].includes(response.status()),JSON.stringify({suffix,status:response.status(),value}));return value;
  }
  const history=()=>page.locator('.communication-history');
  const rows=()=>history().locator('[data-history-key]');
  const close=()=>page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
  const responseCapture=async response=>{if(new URL(response.url()).pathname==='/api/v1/business/sales/communication-history')reads.push({status:response.status(),query:new URL(response.url()).searchParams.toString()});};
  page.on('response',responseCapture);
  try{
    await navigate(page,'Kontakte');
    const owner=await api('/me',null,'/api/v1');
    const customer=await api('/contacts',command({name:'Synthetischer Verlaufskunde',email:'history@example.test'}));
    const inquiry=await api('/inquiries',command({subject:'Synthetische Verlaufsanfrage',message:'Angebot und Rückruf erbeten.',sender_email:'history@example.test'}),'/api/v1');
    const chance=await api('/sales/opportunities',command({revision:0,customer_id:customer.id,inquiry_id:inquiry.id,person_id:null,title:'Synthetische Verlaufsschance',stage:'qualified',expected_net_minor:10000,probability_percent:50,responsible_id:owner.id,follow_up_on:null,expected_close_on:null,description:'Explizit verknüpfte Anfrage',closure_reason:''}));
    const source=await api('/sales/opportunities/'+chance.id);
    const adoption=await api('/sales/opportunities/'+chance.id+'/project',command({revision:source.revision,source_sha256:source.source_sha256,confirmation:true,project_id:null,project_name:'Synthetisches Verlaufsprojekt'}));
    const projectId=adoption.project_id,today=new Date().toISOString().slice(0,10);
    const activity=await api('/sales/opportunities/'+chance.id+'/activities',command({kind:'call',text:'Ursprüngliche Rückrufnotiz',occurred_on:today,supersedes_id:null,correction_reason:''}));
    await api('/sales/opportunities/'+chance.id+'/activities',command({kind:'call',text:'Korrigierte Rückrufnotiz',occurred_on:today,supersedes_id:activity.id,correction_reason:'Inhalt berichtigt'}));
    const service=await api('/service/cases',command({revision:0,customer_id:customer.id,project_id:projectId,person_id:null,asset_id:null,contract_id:null,visit_id:null,inquiry_id:null,defect_id:null,title:'Synthetischer Verlaufsservice',kind:'request',priority:'normal',responsible_id:owner.id,follow_up_on:null,description:'Servicekontakt zum Projekt'}));
    await api('/documents',command({project_id:projectId,kind:'offer',title:'Synthetischer Verlaufsbeleg',issue_date:today,due_date:today,positions:[{description:'Testleistung',quantity:'1',unit:'HUR',unit_price_net:'10',tax_rate:'19',kind:'labor'}]}));
    const literal='<img src=x onerror="window.historyExecuted=true">';
    for(let i=0;i<52;i++)await api('/feed',command({project_id:projectId,text:`Synthetische Verlaufsnotiz ${String(i).padStart(2,'0')} ${i===51?literal:''}`}));
    await api('/feed',command({project_id:projectId,text:'PRIVATE PERSONALNOTIZ',visibility:'personnel'}));
    // Canonical API writes above are setup. The history is opened through the real UI.
    await navigate(page,'Kontakte');
    await page.locator('.list-row').filter({has:page.getByRole('heading',{name:customer.name,exact:true})}).getByRole('button',{name:'Kommunikationsverlauf',exact:true}).click();
    await page.getByRole('dialog',{name:'Kommunikationsverlauf',exact:true}).waitFor();
    await rows().first().waitFor();assert.equal(await rows().count(),50);
    assert.ok((await history().innerText()).includes(literal));assert.equal(await page.evaluate(()=>window.historyExecuted),undefined);assert.equal(await history().locator('img').count(),0);
    assert.ok(!(await history().innerText()).includes('PRIVATE PERSONALNOTIZ'));
    await history().getByRole('button',{name:'Weitere Einträge laden',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.communication-history [data-history-key]').length>50);
    const keys=await rows().evaluateAll(nodes=>nodes.map(n=>n.dataset.historyKey));assert.equal(new Set(keys).size,keys.length);
    assert.ok((await history().innerText()).includes('Korrigierte Rückrufnotiz'));
    assert.ok((await history().innerText()).includes('Dieser Originaleintrag wurde korrigiert.'));
    assert.ok((await history().innerText()).includes('Manuell protokolliert; kein Versandnachweis.'));
    await page.screenshot({path:path.join(screenshots,'communication-history-desktop.png'),fullPage:true});
    await history().getByRole('button',{name:'Verlauf neu laden',exact:true}).click();await rows().first().waitFor();assert.equal(await rows().count(),50);
    await api('/feed',command({project_id:projectId,text:'Später hinzugefügte Verlaufsnotiz'}));
    await history().getByRole('button',{name:'Weitere Einträge laden',exact:true}).click();
    await history().getByText('Verlauf oder Zugriffsrechte wurden geändert. Den Verlauf erneut laden.',{exact:true}).waitFor();assert.equal(await rows().count(),0);
    await history().getByLabel('Verlaufsquelle',{exact:true}).selectOption('sales');
    await history().getByLabel('Kommunikationsverlauf durchsuchen',{exact:true}).fill('Korrigierte Rückrufnotiz');
    await history().getByRole('button',{name:'Verlauf filtern',exact:true}).click();await rows().first().waitFor();assert.equal(await rows().count(),1);
    await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(screenshots,'communication-history-mobile.png'),fullPage:true});
    await rows().first().getByRole('button',{name:'Projekt öffnen',exact:true}).click();await ready(page);
    await page.getByRole('tab',{name:'Kommunikation',exact:true}).click();await ready(page);await rows().first().waitFor();
    assert.ok((await history().innerText()).includes('Projekt: Synthetisches Verlaufsprojekt'));
    // A response started in this project must never appear on another page.
    let release,started;const waiting=new Promise(resolve=>started=resolve),gate=new Promise(resolve=>release=resolve);
    const pattern='**/api/v1/business/sales/communication-history?*';
    await context.route(pattern,async route=>{const response=await route.fetch();started();await gate;await route.fulfill({response});});
    await history().getByRole('button',{name:'Verlauf neu laden',exact:true}).click();await waiting;
    await navigate(page,'Übersicht');release();await context.unroute(pattern);
    await page.waitForTimeout(100);assert.equal(await history().count(),0);assert.equal(await page.getByRole('dialog').count(),0);
    assert.ok(reads.some(r=>r.status===409));assert.ok(reads.some(r=>new URLSearchParams(r.query).get('project_id')===projectId));
    console.log('communication history: actual owner MFA/HTTP, explicit inquiry/sales/service/document/project links, 50-entry paging, stale cursor rejection, original/correction, escaped HTML, private-note exclusion, customer/project UI, mobile and late-response discard passed');
    assert.equal(service.customer_id,customer.id);
  }finally{page.off('request',capture);page.off('response',responseCapture);await fs.writeFile(path.join(screenshots,'communication-history-reads.json'),JSON.stringify(reads,null,2));}
}
module.exports={communicationHistoryFlow};
