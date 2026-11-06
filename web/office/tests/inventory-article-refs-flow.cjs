const {selectProject}=require('./e2e.cjs');
/* Real warehouse login, price-free item choice, reservation and material pick. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
async function inventoryArticleRefsFlow({page,context,navigate,ready,login,fixture,screenshots}) {
  await page.getByRole('button',{name:'Abmelden',exact:true}).click();
  await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();
  await login(page,'warehouse@browser.example.test');
  const requests=[],records=[];
  const capture=req=>requests.push(new URL(req.url()).pathname);
  page.on('request',capture);
  const pattern='**/api/v1/business/inventory/**';
  await context.route(pattern,async route=>{
    const request=route.request(),response=await route.fetch({maxRedirects:0});
    records.push({path:new URL(request.url()).pathname,method:request.method(),status:response.status(),body:request.method()==='POST'?request.postDataJSON():null,value:await response.json()});
    await route.fulfill({response});
  });
  const modal=()=>page.getByRole('dialog');
  try {
    await selectProject(page,fixture.project_id);await ready(page);
    await navigate(page,'Material');
    const catalogs=records.filter(r=>r.path.endsWith('/inventory/articles'));
    assert.ok(catalogs.length>0,'warehouse loads operative article identities');
    for(const catalog of catalogs)for(const item of catalog.value.items)assert.deepEqual(Object.keys(item).sort(),['active','code','id','name','revision','unit']);
    assert.equal(requests.includes('/api/v1/business/articles'),false,'no finance article endpoint for warehouse');
    await page.getByRole('button',{name:'Bewegung buchen',exact:true}).click();
    const options=await modal().getByLabel('Artikel',{exact:true}).locator('option').allTextContents();
    assert.ok(options.includes('Synthetic unstocked 000'),'unstocked item remains selectable');
    assert.equal(options.includes('Synthetic unstocked INACTIVE'),false);
    assert.equal(options.includes('Synthetic unstocked SERVICE'),false);
    await modal().getByRole('button',{name:'Dialog schließen',exact:true}).click();
    await page.getByRole('button',{name:'Material reservieren',exact:true}).click();
    await modal().getByLabel('Artikel',{exact:true}).selectOption({label:'Synthetic cable'});
    await modal().getByLabel('Lagerort',{exact:true}).selectOption({label:'Synthetic main store'});
    await modal().getByLabel('Menge',{exact:true}).fill('2');
    await modal().getByRole('button',{name:'Speichern',exact:true}).click();
    await modal().waitFor({state:'detached'});await ready(page);
    const reservation=records.find(r=>r.method==='POST'&&r.path.endsWith('/reservations'));
    assert.ok(reservation.status>=200&&reservation.status<300);assert.equal(reservation.body.project_id,fixture.project_id);
    await page.getByRole('button',{name:'Entnehmen',exact:true}).click();
    await modal().getByLabel('Entnahmemenge',{exact:true}).fill('1');
    await modal().getByRole('button',{name:'Entnahme verbindlich buchen',exact:true}).click();
    await modal().waitFor({state:'detached'});await ready(page);
    const pick=records.find(r=>r.method==='POST'&&r.path.endsWith('/pick'));
    assert.ok(pick.status>=200&&pick.status<300);assert.equal(pick.body.project_id,fixture.project_id);
    assert.equal(await page.getByRole('heading',{name:'Artikel & Leistungen',exact:true}).count(),0);
    await page.screenshot({path:path.join(screenshots,'warehouse-article-refs-desktop.png'),fullPage:true,animations:'disabled'});
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(screenshots,'warehouse-article-refs-mobile.png'),fullPage:true,animations:'disabled'});
    console.log('Warehouse without finance: price-free catalog including unstocked materials, real reservation and pick, no finance endpoint, desktop/mobile passed.');
  } finally {
    page.off('request',capture);await context.unroute(pattern);
    await fs.writeFile(path.join(screenshots,'warehouse-article-refs-http.json'),JSON.stringify(records,null,2));
  }
}
module.exports={inventoryArticleRefsFlow};
