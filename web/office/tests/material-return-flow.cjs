/* Actual HTTP stock returns; setup data and all identities are synthetic. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const request=body=>({request_id:crypto.randomUUID().replaceAll('-',''),...body});
async function materialReturnFlow({page,context,navigate,ready,login,fixture,screenshots,restart=false,recovery=[]}){
 let token,lost=false;const records=[];page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)token=r.headers().authorization;});
 const modal=name=>page.getByRole('dialog',{name,exact:true}),close=async()=>{if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();};
 async function api(suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:token,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 const pattern='**/api/v1/business/inventory/movements';await context.route(pattern,async route=>{const req=route.request();if(req.method()!=='POST')return route.continue();const body=req.postDataJSON();if(body.kind!=='return')return route.continue();const response=await route.fetch({maxRedirects:0}),value=await response.json();records.push({body,status:response.status(),value});if(response.ok()&&!lost){lost=true;return route.abort('failed');}return route.fulfill({response});});
 async function start(){await close();await navigate(page,'Material');await page.getByRole('button',{name:'Material zurückgeben',exact:true}).click();await page.getByRole('dialog',{name:/^(Projekt der Materialrückgabe|Material zurückgeben)$/}).waitFor();if(await modal('Projekt der Materialrückgabe').count()){await modal('Projekt der Materialrückgabe').getByLabel('Projekt der ursprünglichen Entnahme',{exact:true}).selectOption(fixture.project_id);await modal('Projekt der Materialrückgabe').getByRole('button',{name:'Originalentnahmen öffnen',exact:true}).click();}await modal('Material zurückgeben').waitFor();}
 async function selectIssue(issue){await start();await modal('Material zurückgeben').getByLabel('Ursprüngliche Materialentnahme',{exact:true}).selectOption(issue.id);await modal('Material zurückgeben').getByRole('button',{name:'Rückgabe zur Originalentnahme erfassen',exact:true}).click();await modal('Rückgabe zur Originalentnahme').waitFor();}
 async function enter(location,amount,note){const editor=modal('Rückgabe zur Originalentnahme');await editor.getByLabel('Ziellager für die Rückgabe',{exact:true}).selectOption(location.id);await editor.getByLabel('Tatsächlich zurückgegebene Menge',{exact:true}).fill(amount);await editor.getByLabel('Buchungsnotiz zur Rückgabe',{exact:true}).fill(note);await editor.getByRole('checkbox').check();await editor.getByRole('button',{name:'Materialrückgabe verbindlich buchen',exact:true}).click();}
 try{
  if(restart){await navigate(page,'Material');const caps=await api('/capabilities?project_id='+fixture.project_id);assert.ok(caps.features.includes('client_original_key'),'restart acceptance must use the actual bound key endpoint');}
  await navigate(page,'Material');const location=await api('/inventory/locations',request({name:'Synthetic returns shelf'}));
  const article=await api('/articles',request({code:'SYN-RET',name:'Synthetic original-price cable',kind:'material',unit:'m',currency:'EUR',unit_price_net:'12.00',cost_price_net:'10.00',tax_rate:'19',tax_category:'S',active:true}));
  const receive=await api('/inventory/movements',request({kind:'receive',article_id:article.id,to_location_id:location.id,quantity:'10',unit_cost_net:'10.00',note:'Synthetic receipt'}));
  const issue=await api('/inventory/movements',request({kind:'issue',article_id:article.id,from_location_id:location.id,project_id:fixture.project_id,quantity:'6',note:'Synthetic original issue'}));
  const before=await api('/projects/'+fixture.project_id+'/costs');assert.equal(issue.cost_net,'60.0000');
  await api('/articles/'+article.id,request({revision:article.revision,cost_price_net:'77.00'}));
  // Observe the client's real parsed result. A routed background response can
  // leave Playwright response.finished() pending after successful delivery.
  // This transparent probe preserves every request, byte, value and error.
  await page.evaluate(async expectedPath=>{
   const {OfficeApi}=await import('/office/office.js'),original=OfficeApi.prototype.get;
   window.__materialOriginalObserved={state:'waiting'};
   OfficeApi.prototype.get=async function(path){
    if(path!==expectedPath)return original.call(this,path);
    try{const value=await original.call(this,path);window.__materialOriginalObserved={state:'fulfilled',ids:value.items.map(item=>item.id).sort()};return value;}
    catch(error){window.__materialOriginalObserved={state:'rejected',name:error.name,status:error.status};throw error;}
   };
   window.__restoreMaterialOriginalObserver=()=>{OfficeApi.prototype.get=original;delete window.__materialOriginalObserved;delete window.__restoreMaterialOriginalObserver;};
  },'/business/inventory/movements?project_id='+fixture.project_id);
  let release,observed;const hold=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>observed=resolve),delayed=new RegExp('/api/v1/business/inventory/movements\\?project_id='+fixture.project_id+'$');
  const delayLoad=async route=>{const response=await route.fetch({maxRedirects:0});observed();await hold;await route.fulfill({response});};await context.route(delayed,delayLoad);
  try{
   await page.getByRole('button',{name:'Material zurückgeben',exact:true}).click();const chooser=modal('Projekt der Materialrückgabe');await chooser.waitFor();await chooser.getByLabel('Projekt der ursprünglichen Entnahme',{exact:true}).selectOption(fixture.project_id);await chooser.getByRole('button',{name:'Originalentnahmen öffnen',exact:true}).click();let timeout;try{await Promise.race([seen,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('Delayed material original GET was not observed')),15000);})]);}finally{clearTimeout(timeout);}await close();await page.getByRole('button',{name:'Lagerort anlegen',exact:true}).click();await modal('Lagerort').waitFor();
   const completed=page.waitForResponse(response=>delayed.test(response.url()),{timeout:15000});release();assert.equal((await completed).status(),200);
   await page.waitForFunction(()=>window.__materialOriginalObserved.state!=='waiting',null,{timeout:15000,polling:50});
   const parsed=await page.evaluate(()=>window.__materialOriginalObserved);assert.equal(parsed.state,'fulfilled');assert.ok(parsed.ids.includes(issue.id),'the actual client must parse the genuine original issue');
   await page.evaluate(()=>new Promise(resolve=>setTimeout(resolve,0)));assert.equal(await page.getByRole('dialog').getAttribute('aria-label'),'Lagerort','late return GET must not replace another dialog');
   console.log('material return: genuine original response parsed after closing its editor, replacement dialog preserved');
  }finally{release();await context.unroute(delayed,delayLoad);await page.evaluate(()=>window.__restoreMaterialOriginalObserver?.());await close();}
  await selectIssue(issue);const editor=modal('Rückgabe zur Originalentnahme');assert.match(await editor.innerText(),/10,00/);assert.equal(await editor.getByLabel('Artikel',{exact:true}).count(),0);assert.equal(await editor.getByLabel('Projekt für Entnahme',{exact:true}).count(),0);await enter(location,'6.0001','Synthetic over-return');await editor.getByRole('alert').waitFor();assert.equal(records.length,0);
  await enter(location,'2','Synthetic first return');await editor.getByRole('alert').waitFor();assert.equal(records.length,1);
  if(restart){
   const retained=await page.evaluate(()=>new Promise((resolve,reject)=>{const open=indexedDB.open('smartplan-originals-v1',1);open.onerror=()=>reject(new Error('Cannot inspect synthetic ciphertext'));open.onsuccess=()=>{const db=open.result,tx=db.transaction('originals','readonly'),request=tx.objectStore('originals').getAll();tx.oncomplete=()=>{db.close();resolve(request.result);};tx.onabort=()=>reject(new Error('Cannot read synthetic ciphertext'));};}));
   assert.equal(retained.length,1);const local=JSON.stringify(retained);assert.equal(local.includes(records[0].body.note),false);assert.equal(local.includes(token.replace('Bearer ','')),false);assert.equal(local.includes('wrapping_key'),false);
   await page.reload();assert.ok(recovery.length>0,'actual MFA recovery code required');await login(page,'owner@browser.example.test',recovery.shift());
   await start();assert.equal(await modal('Material zurückgeben').getByLabel('Ursprüngliche Materialentnahme',{exact:true}).count(),0);assert.equal(records.length,1);
   await modal('Material zurückgeben').getByRole('button',{name:'Ursprüngliche Rückgabe erneut prüfen',exact:true}).click();
  }else{await close();await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();}
  await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
  assert.equal(records.length,2);assert.deepEqual(records[0].body,records[1].body);assert.deepEqual(records[0].value,records[1].value);assert.equal('unit_cost_net'in records[0].body,false);assert.equal('from_location_id'in records[0].body,false);
  const stock=await api('/inventory/stock?location_id='+location.id+'&article_id='+article.id),after=await api('/projects/'+fixture.project_id+'/costs');assert.equal(stock.on_hand,'6.0000');assert.equal(Number(before.material_actual_net)-Number(after.material_actual_net),20);assert.deepEqual(await api('/inventory/movements/'+issue.id),issue);assert.deepEqual(await api('/inventory/movements/'+receive.id),receive);
  await selectIssue(issue);assert.match(await modal('Rückgabe zur Originalentnahme').innerText(),/4\.0000/);await enter(location,'1','Synthetic second return');await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
  await selectIssue(issue);await page.setViewportSize({width:390,height:844});await page.getByRole('dialog').evaluate(node=>node.scrollTop=0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'material-return-mobile.png'),fullPage:false});await enter(location,'3','Synthetic final return');await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
  const final=await api('/inventory/stock?location_id='+location.id+'&article_id='+article.id),costs=await api('/projects/'+fixture.project_id+'/costs');assert.equal(final.on_hand,'10.0000');assert.equal(Number(before.material_actual_net)-Number(costs.material_actual_net),60);
  await start();assert.equal(await modal('Material zurückgeben').getByLabel('Ursprüngliche Materialentnahme',{exact:true}).locator('option[value="'+issue.id+'"]').count(),0);
  await close();await page.setViewportSize({width:1440,height:1000});
  const warehouseIssue=await api('/inventory/movements',request({kind:'issue',article_id:article.id,from_location_id:location.id,project_id:fixture.project_id,quantity:'1',note:'Synthetic warehouse original'}));
  await page.getByRole('button',{name:'Abmelden',exact:true}).click();await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();await login(page,'warehouse@browser.example.test');
  const requests=[],capture=req=>requests.push(new URL(req.url()).pathname);page.on('request',capture);
  try{
   await selectIssue(warehouseIssue);const warehouse=modal('Rückgabe zur Originalentnahme');assert.equal((await warehouse.innerText()).includes('Historischer Einstand'),false);assert.equal(requests.includes('/api/v1/business/articles'),false);
   const original=await api('/inventory/movements/'+warehouseIssue.id);assert.equal(original.cost_net,undefined);assert.equal(original.unit_cost_net,undefined);assert.equal(original.article_snapshot.cost_price_net,undefined);
   await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'material-return-warehouse-mobile.png'),fullPage:false});
   await enter(location,'1','Synthetic warehouse price-free return');await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);const recorded=records.at(-1).value;assert.equal(recorded.cost_net,undefined);assert.equal(recorded.unit_cost_net,undefined);assert.equal(recorded.article_snapshot.cost_price_net,undefined);const balance=await api('/inventory/stock?location_id='+location.id+'&article_id='+article.id);assert.equal(balance.on_hand,'10.0000');assert.equal(balance.stock_value_net,undefined);
  }finally{page.off('request',capture);}
  if(restart)await require('./original-journal-browser.cjs').originalJournalBrowser({page,projectId:fixture.project_id,token});
  console.log('material return: actual MFA/HTTP issue selection, original price after catalogue change, no over-return POST, exact accepted lost-ACK retry, partial/final quantities, unchanged originals and project costs, price-free warehouse role and mobile view passed'+(restart?'; actual page reload and renewed MFA recovered ciphertext-only original without a second booking':''));
 }finally{await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'material-return-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={materialReturnFlow};
