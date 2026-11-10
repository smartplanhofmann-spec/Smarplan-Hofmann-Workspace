const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const request=values=>({request_id:crypto.randomUUID().replaceAll('-',''),...values});
async function employeeAccountSelectionFlow({page,context,navigate,ready,login,fixture,screenshots}){
 const tokens=new Map(),commands=[],errors=[];let lose=true,hr;
 const watch=p=>p.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)tokens.set(p,r.headers().authorization);});watch(page);
 async function api(p,suffix,body,status=200){const r=await context.request.fetch(fixture.base_url+'/api/v1'+suffix,{method:body?'POST':'GET',headers:{Authorization:tokens.get(p),Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.equal(r.status(),status,suffix+' '+await r.text());return r.json();}
 const modal=()=>hr.getByRole('dialog',{name:'Mitarbeiterprofil anlegen',exact:true});
 const grant=(id,effect,revision)=>api(page,'/business/settings/permissions',request({user_id:id,permission:'personnel.manage',scope:'*',effect,revision}));
 await navigate(page,'Personal');
 const hrAccount=await api(page,'/users',{email:'synthetic-hr-manager@example.test',password:'Synthetic-browser-password-123',role:'technician'},201);
 const hire=await api(page,'/users',{email:'synthetic-new-hire@example.test',password:'Synthetic-browser-password-123',role:'technician'},201);
 await api(page,'/business/settings/permissions',request({user_id:hrAccount.id,permission:'personnel.read',scope:'*',effect:'allow',revision:0}));
 await grant(hrAccount.id,'allow',0);
 const pattern='**/api/v1/business/employees';
 await context.route(pattern,async route=>{const req=route.request();if(req.method()!=='POST')return route.continue();const response=await route.fetch({maxRedirects:0}),value=await response.json();commands.push({body:req.postDataJSON(),status:response.status(),value});if(lose&&response.ok()){lose=false;return route.abort('failed');}return route.fulfill({response,json:value});});
 try{
  hr=await context.newPage();watch(hr);hr.on('pageerror',e=>errors.push(e.message));const requests=[];hr.on('request',r=>requests.push(new URL(r.url()).pathname));
  await hr.setViewportSize({width:390,height:844});await hr.goto(fixture.base_url+'/office/');await login(hr,'synthetic-hr-manager@example.test');await navigate(hr,'Personal');
  await api(hr,'/users',null,403);
  async function open(){await hr.getByRole('button',{name:'Mitarbeiterprofil anlegen',exact:true}).click();await modal().waitFor();}
  async function fill(){await modal().getByLabel('Benutzerkonto',{exact:true}).selectOption(hire.id);await modal().getByLabel('Anzeigename',{exact:true}).fill('Synthetic reviewed employee');await modal().getByLabel('Wöchentliche Sollminuten',{exact:true}).fill('1200');await modal().getByLabel('Historischer Kostensatz in Cent / Stunde',{exact:true}).fill('2500');}
  await open();assert.equal(await modal().getByLabel('Benutzerkonto',{exact:true}).inputValue(),'');await fill();
  await hr.screenshot({path:path.join(screenshots,'employee-create-mobile.png'),fullPage:false});
  await modal().getByRole('button',{name:'Speichern',exact:true}).click();await modal().getByRole('alert').waitFor();
  assert.equal(commands.length,1);await modal().getByRole('button',{name:'Speichern',exact:true}).click();await modal().waitFor({state:'detached'});await ready(hr);
  assert.equal(commands.length,2);assert.deepEqual(commands[0],commands[1]);
  const employees=(await api(page,'/business/employees')).items.filter(p=>p.user_id===hire.id);assert.equal(employees.length,1);assert.equal(employees[0].name,'Synthetic reviewed employee');
  const row=hr.locator('.list-row').filter({hasText:'Synthetic reviewed employee'});await row.getByRole('button',{name:'Bearbeiten',exact:true}).click();
  const edit=hr.getByRole('dialog',{name:'Mitarbeiterprofil ändern',exact:true});await edit.waitFor();assert.equal(await edit.getByLabel('Benutzerkonto',{exact:true}).isDisabled(),true);await edit.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await open();await fill();await grant(hrAccount.id,'deny',1);const before=commands.length;
  await modal().getByRole('button',{name:'Speichern',exact:true}).click();await modal().waitFor({state:'detached'});await ready(hr);assert.equal(commands.length,before);
  assert.equal(await hr.getByRole('button',{name:'Mitarbeiterprofil anlegen',exact:true}).count(),0);
  await hr.screenshot({path:path.join(screenshots,'employee-readonly-mobile.png'),fullPage:false});
  await grant(hrAccount.id,'allow',2);await navigate(hr,'Personal');
  let release,started;const gate=new Promise(r=>release=r),seen=new Promise(r=>started=r);
  await context.route('**/api/v1/business/employees/account-selection',async route=>{const response=await route.fetch({maxRedirects:0});started();await gate;return route.fulfill({response});});
  try{await hr.getByRole('button',{name:'Mitarbeiterprofil anlegen',exact:true}).click();await seen;await grant(hrAccount.id,'deny',3);release();await hr.waitForFunction(()=>![...document.querySelectorAll('button')].some(b=>b.textContent==='Mitarbeiterprofil anlegen'));assert.equal(await modal().count(),0);assert.equal(commands.length,before);}finally{release();await context.unroute('**/api/v1/business/employees/account-selection');}
  assert.equal(requests.filter(p=>p==='/api/v1/users').length,0);assert.deepEqual(errors,[]);assert.ok(await hr.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  console.log('Employee accounts: actual HR MFA without user administration, explicit selection, immutable binding, one original after lost reply, fresh revocation, held response and 390px passed');
 }finally{await context.unroute(pattern);if(hr)await hr.close();await fs.writeFile(path.join(screenshots,'employee-synthetic-commands.json'),JSON.stringify(commands,null,2));}
}
module.exports={employeeAccountSelectionFlow};
