/* Independent real MFA/HTTP source-right check. Only synthetic permissions mutate. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
module.exports.accountingYearPackageFlow=async({page,context,navigate,ready,login,fixture,screenshots})=>{
 let ownerToken,readerToken,release;const requests=[],downloads=[];
 page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)ownerToken=r.headers().authorization;});
 const modal=p=>p.getByRole('dialog');
 async function overview(p){await navigate(p,'Finanzen');await p.getByRole('button',{name:'EÜR-Vorbereitung',exact:true}).click();await ready(p);await p.getByRole('button',{name:'Eigene EÜR',exact:true}).click();await ready(p);}
 async function ownerApi(suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:ownerToken,Origin:fixture.base_url},...(body?{data:{request_id:crypto.randomUUID().replaceAll('-',''),...body}}:{})});assert.ok(response.ok(),suffix+' '+response.status());return response.json();}
 async function grant(permission,scope,effect){const value=await ownerApi('/settings/permissions'),rows=Array.isArray(value)?value:value.items;await ownerApi('/settings/permissions',{user_id:fixture.reader_id,permission,scope,effect,revision:rows.find(v=>v.user_id===fixture.reader_id&&v.permission===permission&&v.scope===scope)?.revision||0});}
 await overview(page);const exported=await ownerApi('/accounting/euer/exports/'+fixture.exports[0].id),receiptRef=exported.report.sources.find(v=>v.kind==='receipt');assert.ok(receiptRef);
 const receipt=await ownerApi(receiptRef.source_path);assert.match(receipt.project_id,/^[a-f0-9]{32}$/);
 for(const permission of ['finance.read','accounting.read'])await grant(permission,'*','allow');
 const reader=await context.newPage();reader.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)readerToken=r.headers().authorization;});reader.on('download',value=>downloads.push(value));
 const pattern='**/api/v1/business/accounting/euer/exports/**';let enter;const entered=new Promise(r=>enter=r);
 await reader.route(pattern,async route=>{const actual=await route.fetch({maxRedirects:0});requests.push({path:new URL(route.request().url()).pathname,status:actual.status(),method:route.request().method()});if(route.request().url().endsWith('/archive'))await new Promise(r=>{release=r;enter();});await route.fulfill({response:actual});});
 try{
  await login(reader,fixture.reader_email);await overview(reader);const journal=reader.locator('section.panel').filter({has:reader.getByRole('heading',{name:'Unveränderliches Buchungsjournal',exact:true})});await journal.locator('.list-row').filter({hasText:`Nr. ${fixture.exports[0].sequence} ·`}).getByRole('button',{name:'Prüfpaket öffnen',exact:true}).click();await reader.getByRole('dialog',{name:'Gespeichertes Jahresprüfpaket',exact:true}).waitFor();await modal(reader).getByRole('button',{name:'Jahresnachweis mit Originalen öffnen',exact:true}).click();await reader.getByRole('dialog',{name:'Jahresnachweis mit Originalen',exact:true}).waitFor();
  await reader.setViewportSize({width:390,height:844});assert.equal(await reader.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);await reader.screenshot({path:path.join(screenshots,'independent-year-source-before-390.png')});
  await modal(reader).getByRole('button',{name:'Gebundenes Belegpaket herunterladen',exact:true}).click();await entered;
  await grant('finance.read',receipt.project_id,'deny');
  const capsResponse=await context.request.get(fixture.base_url+'/api/v1/business/capabilities',{headers:{Authorization:readerToken,Origin:fixture.base_url}});assert.ok(capsResponse.ok());const caps=await capsResponse.json();assert.ok(caps.permissions.includes('finance.read'));assert.ok(caps.permissions.includes('accounting.read'));
  release();await reader.getByRole('dialog',{name:'Jahresnachweis nicht freigegeben',exact:true}).waitFor();assert.equal(downloads.length,0);assert.doesNotMatch(await modal(reader).innerText(),new RegExp(fixture.exports[0].id));assert.ok(requests.some(r=>r.path.endsWith('/evidence')&&[403,404].includes(r.status)));assert.ok(requests.every(r=>r.method==='GET'));
  await reader.screenshot({path:path.join(screenshots,'independent-year-source-denied-390.png')});
  const result={case:'real project-only source revocation after original archive was fetched',globalFinanceReadRetained:true,globalAccountingReadRetained:true,downloads:downloads.length,requests};await fs.writeFile(path.join(screenshots,'independent-year-source-results.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
 }finally{release?.();await reader.unroute(pattern);await reader.close();}
};
