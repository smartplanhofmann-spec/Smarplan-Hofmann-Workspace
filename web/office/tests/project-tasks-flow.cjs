const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const path=require('node:path');
const fs=require('node:fs/promises');
const {selectProject}=require('./e2e.cjs');

async function projectTasksFlow({page,context,login,ready,navigate,fixture,screenshots}){
  let authorization;const sent=[];const project=fixture.project_id,base=`/projects/${project}/tasks`;
  const capture=request=>{if(new URL(request.url()).origin===fixture.base_url&&request.headers().authorization)authorization=request.headers().authorization;};
  page.on('request',capture);
  const api=async(suffix,data)=>{
    const response=await context.request.fetch(fixture.base_url+'/api/v1'+suffix,{method:data?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(data?{data}:{}),maxRedirects:0});
    assert.ok([200,201].includes(response.status()),suffix+': '+await response.text());return response.json();
  };
  const command=values=>({request_id:crypto.randomUUID().replaceAll('-',''),...values});
  const editor=target=>target.getByRole('dialog',{name:'Aufgabe bearbeiten',exact:true});
  const row=(target,title)=>target.locator('main .list-row').filter({has:target.getByRole('heading',{name:title,exact:true})});
  const save=async(target=page)=>{await target.getByRole('dialog').getByRole('button',{name:'Speichern',exact:true}).click();await target.getByRole('dialog').waitFor({state:'detached'});await ready(target);};
  const tasks=async(target=page)=>{await selectProject(target,project);await target.getByRole('tab',{name:'Aufgaben',exact:true}).click();await ready(target);};
  await tasks();const users=await api('/users'),tech=users.find(user=>user.email==='technician@browser.example.test');assert.ok(tech);
  let initial,created;let loseCreate=true;
  const createPattern='**/api/v1'+base;
  const createRoute=async route=>{
    if(route.request().method()!=='POST')return route.fallback();
    sent.push(JSON.parse(route.request().postData()));const response=await route.fetch();assert.equal(response.status(),201);created=await response.json();initial??=created;
    if(loseCreate){loseCreate=false;return route.abort('failed');}return route.fulfill({response});
  };
  await context.route(createPattern,createRoute);
  try{
    await page.getByRole('button',{name:'Aufgabe hinzufügen',exact:true}).click();const create=page.getByRole('dialog',{name:'Neue Aufgabe',exact:true});
    await create.getByLabel('Priorität',{exact:true}).waitFor();
    assert.deepEqual(await create.getByLabel('Priorität',{exact:true}).locator('option').allTextContents(),['Normal','Hoch']);
    await create.getByLabel('Aufgabe',{exact:true}).fill('Synthetische Originalaufgabe');
    await create.getByLabel('Beschreibung',{exact:true}).fill('Unveränderte erste Fassung');
    await create.getByLabel('Verantwortlich',{exact:true}).selectOption(tech.id);
    await create.getByLabel('Fällig am',{exact:true}).fill('2026-11-12');
    await create.getByRole('button',{name:'Speichern',exact:true}).click();await create.locator('[role=alert]').waitFor();
    assert.equal((await api(base)).filter(item=>item.id===created.id).length,1);assert.equal(created.revision,1);
    await create.getByLabel('Aufgabe',{exact:true}).fill('Veränderte unbestätigte Eingabe');await create.getByRole('button',{name:'Speichern',exact:true}).click();
    await create.getByText(/vorige Antwort ist noch unklar/).waitFor();assert.equal(sent.length,1);
    await create.getByLabel('Aufgabe',{exact:true}).fill('Synthetische Originalaufgabe');await save();assert.deepEqual(sent[0],sent[1]);
  }finally{await context.unroute(createPattern,createRoute);}
  const identifier=created.id,taskPath=base+'/'+identifier;let current=created;
  await row(page,current.title).getByRole('button',{name:'Bearbeiten',exact:true}).click();
  await editor(page).getByLabel('Aufgabe',{exact:true}).fill('Bearbeitete Projektaufgabe');await editor(page).getByLabel('Status',{exact:true}).selectOption('in_progress');
  await editor(page).getByLabel('Priorität',{exact:true}).selectOption('high');await editor(page).getByLabel('Verantwortlich',{exact:true}).selectOption('');
  await editor(page).getByLabel('Beschreibung',{exact:true}).fill('Zweite Fassung mit neuer Planung');await save();current=await api(taskPath);assert.equal(current.revision,2);assert.equal(current.assignee_id,null);
  await row(page,current.title).getByRole('button',{name:'Bearbeiten',exact:true}).click();await editor(page).getByLabel('Status',{exact:true}).selectOption('cancelled');await save();
  await row(page,current.title).getByRole('button',{name:'Wieder öffnen',exact:true}).click();assert.equal(await editor(page).getByLabel('Status',{exact:true}).inputValue(),'todo');await save();
  await row(page,current.title).getByRole('button',{name:'Erledigt',exact:true}).click();assert.equal(await editor(page).getByLabel('Status',{exact:true}).inputValue(),'done');await save();
  current=await api(taskPath);assert.equal(current.revision,5);
  await row(page,current.title).getByRole('button',{name:'Verlauf',exact:true}).click();const history=page.getByRole('dialog',{name:'Aufgabenverlauf',exact:true});
  await history.getByRole('heading',{name:'Version 5 · aktuell',exact:true}).waitFor();await history.getByRole('heading',{name:'Synthetische Originalaufgabe',exact:true}).waitFor();
  assert.equal(await history.locator('input,textarea,select').count(),0);assert.deepEqual((await api(taskPath+'/history')).items[0],initial);
  await history.getByRole('button',{name:'Dialog schließen',exact:true}).click();
  // A stale editor cannot overwrite a real concurrent revision.
  await row(page,current.title).getByRole('button',{name:'Bearbeiten',exact:true}).click();
  current=await api(taskPath,command({revision:5,title:'Parallel geänderte Aufgabe'}));
  await editor(page).getByLabel('Aufgabe',{exact:true}).fill('Überholter Browserentwurf');await editor(page).getByRole('button',{name:'Speichern',exact:true}).click();
  await editor(page).getByText(/inzwischen geändert/).waitFor();assert.deepEqual(await api(taskPath),current);await editor(page).getByRole('button',{name:'Dialog schließen',exact:true}).click();
  await navigate(page,'Projekte');await tasks();
  // A real GET arriving after navigation must not reopen the old task.
  let enter,release,done;const entered=new Promise(resolve=>enter=resolve),gate=new Promise(resolve=>release=resolve),finished=new Promise(resolve=>done=resolve);
  const getPattern='**/api/v1'+taskPath;
  const delayed=async route=>{const response=await route.fetch();enter();await gate;await route.fulfill({response});done();};
  await context.route(getPattern,delayed);try{
    await row(page,current.title).getByRole('button',{name:'Bearbeiten',exact:true}).click();await entered;await navigate(page,'Übersicht');release();await finished;await page.evaluate(()=>new Promise(requestAnimationFrame));assert.equal(await page.getByRole('dialog').count(),0);
  }finally{release();await context.unroute(getPattern,delayed);}
  // The technician receives the real accepted result only after project access
  // is restored; neither access loss nor replay creates a duplicate revision.
  const technician=await context.newPage();let techAuth;const techCapture=request=>{if(request.headers().authorization)techAuth=request.headers().authorization;};technician.on('request',techCapture);
  await technician.goto(fixture.base_url+'/office/');await login(technician,tech.email);await tasks(technician);
  let lost=true;const updateSent=[];const updateRoute=async route=>{
    if(route.request().method()!=='POST'||route.request().headers().authorization!==techAuth)return route.fallback();
    updateSent.push(JSON.parse(route.request().postData()));const response=await route.fetch();assert.equal(response.status(),200);if(lost){lost=false;return route.abort('failed');}return route.fulfill({response});
  };
  await context.route(getPattern,updateRoute);
  try{
    await row(technician,current.title).getByRole('button',{name:'Bearbeiten',exact:true}).click();await editor(technician).getByLabel('Status',{exact:true}).selectOption('in_progress');
    await editor(technician).getByRole('button',{name:'Speichern',exact:true}).click();await editor(technician).locator('[role=alert]').waitFor();assert.equal(updateSent.length,1);
    await api('/assignments',{project_id:project,user_id:tech.id,remove:true});
    await editor(technician).getByRole('button',{name:'Speichern',exact:true}).click();await editor(technician).getByText(/nicht mehr verfügbar/).waitFor();assert.equal(await editor(technician).locator('input,textarea,select').count(),0);assert.equal(updateSent.length,1);
    await api('/assignments',{project_id:project,user_id:tech.id});await editor(technician).getByRole('button',{name:'Dialog schließen',exact:true}).click();
    // Pending indicator updates on refresh without discarding the frozen body.
    await navigate(technician,'Projekte');await tasks(technician);await technician.locator('[data-pending-indicator]').click();
    await technician.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await technician.getByRole('dialog').waitFor({state:'detached'});await ready(technician);
    assert.deepEqual(updateSent[0],updateSent[1]);current=await api(taskPath);assert.equal(current.revision,7);
    await technician.setViewportSize({width:390,height:844});await tasks(technician);await row(technician,current.title).getByRole('button',{name:'Verlauf',exact:true}).click();
    await technician.getByRole('dialog',{name:'Aufgabenverlauf',exact:true}).getByRole('heading',{name:'Version 7 · aktuell',exact:true}).waitFor();
    assert.equal(await technician.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await technician.screenshot({path:path.join(screenshots,'project-tasks-mobile.png'),fullPage:false});
    const revisions=(await api(taskPath+'/history')).items;assert.equal(revisions.length,7);assert.deepEqual(revisions[0],initial);
    await fs.writeFile(path.join(screenshots,'project-tasks-evidence.json'),JSON.stringify({initial,current,revisions,create_commands:sent,update_commands:updateSent},null,2));
  }finally{await api('/assignments',{project_id:project,user_id:tech.id});await context.unroute(getPattern,updateRoute);await technician.close();page.off('request',capture);}
  console.log('project tasks: real MFA/HTTP create/edit/assignment/cancel/reopen/history, exact lost acknowledgements, concurrent change, revoked access, late response and390px passed');
}
module.exports={projectTasksFlow};
