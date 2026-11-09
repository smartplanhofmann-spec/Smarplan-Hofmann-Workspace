const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const path=require('node:path');
const {selectProject}=require('./e2e.cjs');

async function projectMilestonesFlow({page,context,login,ready,navigate,fixture,screenshots}){
  let authorization;const project=fixture.project_id,base=`/business/projects/${project}/milestones`,createCommands=[],updateCommands=[];
  const capture=request=>{if(new URL(request.url()).origin===fixture.base_url&&request.headers().authorization)authorization=request.headers().authorization;};page.on('request',capture);
  const request=values=>({request_id:crypto.randomUUID().replaceAll('-',''),...values});
  const api=async(url,data)=>{
    const response=await context.request.fetch(fixture.base_url+'/api/v1'+url,{method:data?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(data?{data}:{}),maxRedirects:0});
    assert.ok([200,201].includes(response.status()),url+': '+await response.text());return response.json();
  };
  const values=item=>Object.fromEntries(['title','details','due_date','assignee_id','status'].map(key=>[key,item[key]]));
  const open=async(target=page)=>{await selectProject(target,project);await target.getByRole('tab',{name:'Meilensteine',exact:true}).click();await ready(target);};
  const editor=target=>target.getByRole('dialog',{name:'Meilenstein bearbeiten',exact:true});
  const row=target=>target.locator('main .list-row').filter({has:target.getByRole('heading',{name:'Freigabe Süd 🚧',exact:true})});
  const save=async(target=page)=>{await target.getByRole('dialog').getByRole('button',{name:'Speichern',exact:true}).click();await target.getByRole('dialog').waitFor({state:'detached'});await ready(target);};
  await open();const users=await api('/users'),technician=users.find(user=>user.email==='technician@browser.example.test');assert.ok(technician);
  let initial,current,loseCreate=true;
  const createPattern='**/api/v1'+base;
  const createRoute=async route=>{
    if(route.request().method()!=='POST')return route.fallback();createCommands.push(route.request().postData());
    const response=await route.fetch();assert.equal(response.status(),201);current=await response.json();initial??=current;
    if(loseCreate){loseCreate=false;return route.abort('failed');}return route.fulfill({response});
  };
  await context.route(createPattern,createRoute);
  try{
    await page.getByRole('button',{name:'Meilenstein hinzufügen',exact:true}).click();const create=page.getByRole('dialog',{name:'Neuer Meilenstein',exact:true});
    await create.getByLabel('Meilenstein',{exact:true}).fill(' Freigabe Süd 🚧 ');await create.getByLabel('Beschreibung des Projektziels',{exact:true}).fill('Originalfassung mit echtem Zeilenumbruch\n');
    await create.getByRole('button',{name:'Speichern',exact:true}).click();await create.locator('[role=alert]').waitFor();assert.equal((await api(base)).items.length,1);
    await save();assert.equal(createCommands.length,2);assert.equal(createCommands[0],createCommands[1]);assert.equal(current.title,' Freigabe Süd 🚧 ');assert.ok(current.details.endsWith('\n'));
  }finally{await context.unroute(createPattern,createRoute);}
  const objectPath=base+'/'+current.id,objectPattern='**/api/v1'+objectPath;
  // A previously offered new assignee cannot be saved after leaving the team.
  await row(page).getByRole('button',{name:'Bearbeiten',exact:true}).click();await editor(page).getByLabel('Verantwortlich',{exact:true}).selectOption(technician.id);
  await api('/assignments',{project_id:project,user_id:technician.id,remove:true});
  await editor(page).getByRole('button',{name:'Speichern',exact:true}).click();await editor(page).getByText(/aktuelle.*Mitglied/).waitFor();assert.equal((await api(objectPath)).revision,1);
  await api('/assignments',{project_id:project,user_id:technician.id});await editor(page).getByLabel('Status',{exact:true}).selectOption('achieved');await editor(page).getByLabel('Fällig am',{exact:true}).fill('2026-11-30');await save();current=await api(objectPath);assert.equal(current.revision,2);
  // The unchanged old responsibility remains valid when the team later changes.
  await api('/assignments',{project_id:project,user_id:technician.id,remove:true});
  await row(page).getByRole('button',{name:'Bearbeiten',exact:true}).click();await editor(page).getByLabel('Verantwortlich',{exact:true}).locator('option').filter({hasText:'Nicht mehr im aktuellen Projektteam'}).waitFor();
  await editor(page).getByLabel('Status',{exact:true}).selectOption('cancelled');await save();current=await api(objectPath);assert.equal(current.revision,3);assert.equal(current.assignee_id,technician.id);
  await api('/assignments',{project_id:project,user_id:technician.id});await row(page).getByRole('button',{name:'Wieder planen',exact:true}).click();assert.equal(await editor(page).getByLabel('Status',{exact:true}).inputValue(),'planned');await save();current=await api(objectPath);assert.equal(current.revision,4);
  await row(page).getByRole('button',{name:'Verlauf',exact:true}).click();let history=page.getByRole('dialog',{name:'Meilensteinverlauf',exact:true});await history.getByRole('heading',{name:'Version 4 · aktuell',exact:true}).waitFor();
  assert.equal(await history.locator('input,textarea,select').count(),0);assert.deepEqual((await api(objectPath+'/history')).items[0],initial);await history.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  // A genuine concurrent write does not become the original of an old editor.
  await row(page).getByRole('button',{name:'Bearbeiten',exact:true}).click();current=await api(objectPath,request({schema_version:1,...values(current),revision:current.revision,details:'Parallel bestätigte Fassung'}));
  await editor(page).getByLabel('Beschreibung des Projektziels',{exact:true}).fill('Veralteter Entwurf');await editor(page).getByRole('button',{name:'Speichern',exact:true}).click();await editor(page).getByText(/inzwischen geändert/).waitFor();assert.deepEqual(await api(objectPath),current);await editor(page).getByRole('button',{name:'Dialog schließen',exact:true}).click();
  const grants=new Map();const grant=async(permission,effect)=>{const value=await api('/business/settings/permissions',request({user_id:technician.id,permission,scope:project,effect,revision:grants.get(permission)?.revision||0}));grants.set(permission,value);return value;};
  await grant('projects.manage','allow');await grant('planning.read','deny');
  const tech=await context.newPage();let techAuth;tech.on('request',request=>{if(request.headers().authorization)techAuth=request.headers().authorization;});
  await tech.goto(fixture.base_url+'/office/');await login(tech,technician.email);await selectProject(tech,project);
  assert.equal(await tech.getByRole('tab',{name:'Meilensteine',exact:true}).count(),0,'global read cannot override scoped denial');
  await grant('planning.read','allow');await navigate(tech,'Projekte');await open(tech);
  let lose=true,release,started,finished;const arrived=new Promise(resolve=>started=resolve),gate=new Promise(resolve=>release=resolve),settled=new Promise(resolve=>finished=resolve);
  const updateRoute=async route=>{
    if(route.request().method()!=='POST'||route.request().headers().authorization!==techAuth)return route.fallback();
    updateCommands.push(route.request().postData());const response=await route.fetch();assert.equal(response.status(),200);
    if(lose){lose=false;return route.abort('failed');}started();await gate;await route.fulfill({response});finished();
  };
  await context.route(objectPattern,updateRoute);
  try{
    await row(tech).getByRole('button',{name:'Bearbeiten',exact:true}).click();await editor(tech).getByLabel('Status',{exact:true}).selectOption('achieved');await editor(tech).getByRole('button',{name:'Speichern',exact:true}).click();await editor(tech).locator('[role=alert]').waitFor();assert.equal(updateCommands.length,1);
    await grant('projects.manage','deny');await editor(tech).getByRole('button',{name:'Speichern',exact:true}).click();await editor(tech).getByText(/nicht mehr verfügbar/).waitFor();assert.equal(await editor(tech).locator('input,textarea,select').count(),0);assert.equal(updateCommands.length,1);
    await grant('projects.manage','allow');await editor(tech).getByRole('button',{name:'Dialog schließen',exact:true}).click();await navigate(tech,'Projekte');await open(tech);
    await tech.locator('[data-pending-indicator]').click();await tech.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await arrived;
    await tech.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();await navigate(tech,'Übersicht');release();await settled;await tech.evaluate(()=>new Promise(requestAnimationFrame));
    assert.equal(await tech.getByRole('dialog').count(),0);await tech.getByRole('heading',{name:'Guten Tag.',exact:true}).waitFor();assert.equal(updateCommands[0],updateCommands[1]);
    current=await api(objectPath);assert.equal(current.revision,6);await open(tech);
    await tech.setViewportSize({width:390,height:844});await row(tech).getByRole('button',{name:'Verlauf',exact:true}).click();history=tech.getByRole('dialog',{name:'Meilensteinverlauf',exact:true});await history.getByRole('heading',{name:'Version 6 · aktuell',exact:true}).waitFor();
    assert.equal(await tech.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await tech.screenshot({path:path.join(screenshots,'project-milestones-mobile.png'),fullPage:false});
    const originals=(await api(objectPath+'/history')).items;assert.equal(originals.length,6);assert.deepEqual(originals[0],initial);
    await fs.writeFile(path.join(screenshots,'project-milestones-evidence.json'),JSON.stringify({initial,current,originals,createCommands,updateCommands},null,2));
  }finally{release();await context.unroute(objectPattern,updateRoute);await tech.close();page.off('request',capture);}
  console.log('project milestones: real MFA, exact create/update retries, scoped denial, current and historical team, concurrent revision, preserved six-version history, late reply and390px passed');
}
module.exports={projectMilestonesFlow};
