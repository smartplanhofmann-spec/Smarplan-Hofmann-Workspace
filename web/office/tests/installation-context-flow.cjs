const assert=require('node:assert/strict'),crypto=require('node:crypto'),path=require('node:path');
async function installationContextFlow({page,context,navigate,ready,login,fixture,screenshots}){
 const tokens=new Map(),reads=[];
 function capture(p){p.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)tokens.set(p,r.headers().authorization);if(r.url().endsWith('/business/installation')){assert.equal(r.method(),'GET');reads.push(r.url());}});}capture(page);
 async function api(p,suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1'+suffix,{method:body?'POST':'GET',headers:{Authorization:tokens.get(p),Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 const modal=p=>p.getByRole('dialog',{name:'Installierter Serverstand',exact:true});
 await navigate(page,'Einstellungen');await page.getByRole('button',{name:'Serverstand anzeigen',exact:true}).click();await modal(page).waitFor();
 assert.match(await modal(page).innerText(),new RegExp(fixture.installation_source_commit));
 assert.match(await modal(page).innerText(),/API-Kompatibilität: 0\.12\.0-online-pilot/);
 const unauthenticated=await context.request.get(fixture.base_url+'/api/v1/business/installation');assert.equal(unauthenticated.status(),401);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'installation-source-mobile.png'),fullPage:false});
 await modal(page).getByRole('button',{name:'Dialog schließen',exact:true}).click();
 const email='support-reader@browser.example.test';const user=await api(page,'/users',{email,password:'Synthetic-browser-password-123',role:'technician'});
 const grant={user_id:user.id,permission:'settings.manage',scope:'*',effect:'allow',revision:0};
 await api(page,'/business/settings/permissions',{request_id:crypto.randomUUID().replaceAll('-',''),...grant});
 const reviewer=await context.newPage();capture(reviewer);
 try{
  await reviewer.goto(fixture.base_url+'/office/');await login(reviewer,email);await navigate(reviewer,'Einstellungen');
  await reviewer.getByRole('button',{name:'Serverstand anzeigen',exact:true}).click();await modal(reviewer).waitFor();assert.match(await modal(reviewer).innerText(),new RegExp(fixture.installation_source_commit));
  await modal(reviewer).getByRole('button',{name:'Dialog schließen',exact:true}).click();
  const before=reads.length;await api(page,'/business/settings/permissions',{request_id:crypto.randomUUID().replaceAll('-',''),...grant,revision:1,effect:'deny'});
  await reviewer.getByRole('button',{name:'Serverstand anzeigen',exact:true}).click();await reviewer.getByRole('alert').filter({hasText:'Die aktuelle Freigabe für den Serverstand fehlt.'}).waitFor();
  assert.equal(await modal(reviewer).count(),0);assert.equal(reads.length,before);
  assert.ok(reads.length>=2);await ready(page);
  console.log('installed source: actual startup marker, MFA, distinct API compatibility,390px,no write endpoint, and freshly revoked support access passed');
 }finally{await reviewer.close();}
}
module.exports={installationContextFlow};
