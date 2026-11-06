const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const path=require('node:path');
const {selectProject}=require('./e2e.cjs');

async function projectContextFlow({page,context,navigate,ready,login,fixture,screenshots}){
  const reads=[];
  let authorization;
  const capture=request=>{
    const url=new URL(request.url());
    if(url.origin!==fixture.base_url)return;
    if(request.headers().authorization)authorization=request.headers().authorization;
    if(request.method()==='GET')reads.push({path:url.pathname,project:url.searchParams.get('project_id')});
  };
  page.on('request',capture);
  const picker=()=>page.locator('.topbar .project-select');
  const noPicker=async()=>assert.equal(await picker().count(),0);
  const api=async(suffix,body)=>{
    const response=await context.request.fetch(fixture.base_url+'/api/v1'+suffix,{
      method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},
      ...(body?{data:body}:{}),maxRedirects:0,
    });
    assert.equal(response.status(),200,suffix+' '+await response.text());
    return response.json();
  };
  try{
    await navigate(page,'Übersicht');await noPicker();
    await navigate(page,'Projekte');
    assert.equal(await page.getByLabel('Projekt öffnen',{exact:true}).inputValue(),'');
    await selectProject(page,fixture.project_id);
    for(const name of ['Dokumente','Einsatzplanung','Material']){
      await navigate(page,name);
      assert.equal(await page.getByLabel('Projektfilter',{exact:true}).inputValue(),fixture.project_id);
    }
    await page.screenshot({path:path.join(screenshots,'project-filter-desktop.png'),fullPage:true});

    const before=reads.length;
    await navigate(page,'Übersicht');await noPicker();
    const overviewReads=reads.slice(before);
    assert.ok(overviewReads.some(value=>value.path.endsWith('/overview/metrics')&&value.project===null));
    assert.ok(overviewReads.some(value=>value.path.endsWith('/feed')&&value.project===null));
    for(const name of ['Anfragen','Kontakte','Personal','Einstellungen']){
      const start=reads.length;
      await navigate(page,name);await noPicker();
      assert.equal(reads.slice(start).some(value=>/\/projects\/[^/]+\/profile$/.test(value.path)),false,
                   'Company-wide page must not load a project permission profile: '+name);
    }
    await navigate(page,'Personal');
    await page.getByRole('button',{name:'Zeit starten',exact:true}).click();
    const clock=page.getByRole('dialog',{name:'Zeiterfassung',exact:true});
    assert.equal(await clock.getByLabel('Projekt',{exact:true}).inputValue(),'');
    await page.keyboard.press('Escape');await clock.waitFor({state:'detached'});
    await navigate(page,'Projekte');
    assert.equal(await page.getByLabel('Projekt öffnen',{exact:true}).inputValue(),'');
    await page.getByRole('heading',{name:'Projekte',exact:true}).waitFor();

    // A response for the previous project cannot reintroduce its context on
    // a company page after navigation while the response is in flight.
    let enter,release,finished;
    const entered=new Promise(resolve=>{enter=resolve;});
    const gate=new Promise(resolve=>{release=resolve;});
    const fulfilled=new Promise(resolve=>{finished=resolve;});
    const pattern='**/api/v1/business/projects/'+fixture.project_id+'/profile';
    const delayed=async route=>{
      const response=await route.fetch({maxRedirects:0});enter();await gate;
      await route.fulfill({response});finished();
    };
    await context.route(pattern,delayed);
    try{
      await page.getByLabel('Projekt öffnen',{exact:true}).selectOption(fixture.project_id);
      await entered;
      await navigate(page,'Personal');await noPicker();
      release();await fulfilled;
      await page.evaluate(()=>new Promise(requestAnimationFrame));
      await noPicker();
      await page.getByRole('heading',{name:'Personal & Zeiten',exact:true}).waitFor();
      await page.getByRole('button',{name:'Zeit starten',exact:true}).click();
      assert.equal(await page.getByRole('dialog').getByLabel('Projekt',{exact:true}).inputValue(),'');
      await page.keyboard.press('Escape');
    }finally{release();await context.unroute(pattern,delayed);}

    // Project denial must not hide the global personnel area, and leaving
    // that project must not bypass the server's scoped clock permission.
    const users=await api('/users');
    const technician=(Array.isArray(users)?users:users.items).find(value=>value.email==='technician@browser.example.test');
    assert.ok(technician);
    await api('/business/settings/permissions',{
      request_id:crypto.randomUUID().replaceAll('-',''),user_id:technician.id,
      permission:'time.own',scope:fixture.project_id,effect:'deny',revision:0,
    });
    const tech=await context.newPage();
    try{
      await tech.goto(fixture.base_url+'/office/');await login(tech,technician.email);
      await selectProject(tech,fixture.project_id);
      assert.equal(await tech.locator('.navigation').getByRole('button',{name:'Personal',exact:true}).count(),1);
      await navigate(tech,'Personal');
      assert.equal(await tech.locator('.topbar .project-select').count(),0);
      await tech.getByRole('button',{name:'Zeit starten',exact:true}).click();
      const editor=tech.getByRole('dialog',{name:'Zeiterfassung',exact:true});
      assert.equal(await editor.getByLabel('Projekt',{exact:true}).inputValue(),'');
      await editor.getByLabel('Projekt',{exact:true}).selectOption(fixture.project_id);
      const denied=tech.waitForResponse(value=>new URL(value.url()).pathname==='/api/v1/business/time/events'&&value.request().method()==='POST');
      await editor.getByRole('button',{name:'Zeitereignis speichern',exact:true}).click();
      assert.equal((await denied).status(),403);
      await editor.getByRole('alert').waitFor();
    }finally{await tech.close();}

    await page.setViewportSize({width:390,height:844});
    await navigate(page,'Personal');await noPicker();
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(screenshots,'personnel-company-mobile.png'),fullPage:true});
    await navigate(page,'Dokumente');
    assert.equal(await page.getByLabel('Projektfilter',{exact:true}).inputValue(),'');
    await page.getByLabel('Projektfilter',{exact:true}).selectOption(fixture.project_id);await ready(page);
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(screenshots,'project-filter-mobile.png'),fullPage:true});
    await fs.writeFile(path.join(screenshots,'project-context-acceptance.json'),JSON.stringify({
      company_pages_without_picker:true,project_and_filter_labels:true,scoped_selection_preserved:true,
      overview_requests_unfiltered:true,return_opens_project_list:true,clock_project_explicit:true,
      late_profile_cannot_restore_scope:true,global_personnel_survives_project_denial:true,
      server_still_rejects_denied_clock:403,mobile_width:390,mobile_overflow:false,
      fixture:'Disposable loopback SQLite, real HTTP and MFA, actual Chromium sandbox',
    },null,2)+'\n');
  }finally{page.off('request',capture);}
}
module.exports={projectContextFlow};
