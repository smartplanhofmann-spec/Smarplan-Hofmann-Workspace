const assert=require('node:assert/strict');
const path=require('node:path');
async function companyOverviewFlow({page,navigate,ready,fixture,screenshots}) {
  const reads=[];
  const capture=async response=>{
    if(new URL(response.url()).pathname==='/api/v1/business/overview/metrics'&&response.status()===200)reads.push(await response.json());
  };
  page.on('response',capture);
  try {
    await navigate(page,'Übersicht');await ready(page);
    const area=page.getByRole('region',{name:'Unternehmenskennzahlen'});await area.waitFor();
    assert.ok(reads.length);let value=reads.at(-1);
    assert.equal(value.scope,'authorized_projects');assert.equal(value.accounting.available,true);
    assert.match(await area.innerText(),/Anfangsbestände.*Kontostand/s);
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);
    value=reads.at(-1);assert.equal(value.scope,'selected_project');assert.equal(value.project_id,fixture.project_id);
    assert.equal(value.project_count,1);assert.equal(value.accounting.available,false);
    assert.equal(await page.getByRole('button',{name:'EÜR und Belege öffnen',exact:true}).count(),0);
    const sources=page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Grundlage der Projektkennzahlen',exact:true})});
    await sources.getByRole('button',{name:'Vorgang öffnen',exact:true}).click();await ready(page);
    await page.getByRole('tab',{name:'Wirtschaftlichkeit',exact:true}).waitFor();
    await navigate(page,'Übersicht');await page.setViewportSize({width:390,height:844});await ready(page);
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(screenshots,'company-overview-mobile.png'),fullPage:true});
  } finally {page.off('response',capture);}
}
module.exports={companyOverviewFlow};
