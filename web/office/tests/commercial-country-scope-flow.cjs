/* Genuine owner MFA, browser rendering and standard API; no mocked scope. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

async function commercialCountryScopeFlow({page,context,navigate,ready,fixture,screenshots}) {
  const request=page.waitForRequest(value=>value.method()==='GET'&&new URL(value.url()).pathname.endsWith('/business/settings/branding'));
  await navigate(page,'Einstellungen');
  const headers=await (await request).allHeaders();
  assert.ok(headers.authorization?.startsWith('Bearer '),'use the actual browser MFA session');
  const apiHeaders={Authorization:headers.authorization,Origin:fixture.base_url};
  const results=[];
  async function get(suffix) {
    const response=await context.request.get(fixture.base_url+'/api/v1/business'+suffix,{headers:apiHeaders,maxRedirects:0});
    assert.equal(response.status(),200);return response.json();
  }
  async function check(country,supported) {
    await ready(page);
    await page.getByRole('heading',{name:'Länderumfang der Rechnungsstellung',exact:true}).waitFor();
    await page.getByText(new RegExp('Ausstellerland: '+country+'\\.')).waitFor();
    if(!supported)await page.getByText(/Dieses Ausstellerland wird für neue eigene Rechnungen derzeit nicht unterstützt/).waitFor();
    const scope=await get('/commercial/rule-scope'),settings=await get('/commercial/settings');
    assert.equal(scope.issuer_country,country);assert.equal(scope.supported_issuer,supported);
    assert.equal(scope.settings_revision,settings.revision);
    assert.equal(scope.selected?.country??null,supported?'DE':null);
    if(country==='AT')assert.equal(settings.issuing_enabled,false);
    results.push({country,supported,scope,settings_revision:settings.revision,issuing_enabled:settings.issuing_enabled});
    await page.screenshot({path:path.join(screenshots,'commercial-country-'+country+'.png'),fullPage:true});
  }
  async function change(country) {
    const settings=await get('/commercial/settings');
    const response=await context.request.post(fixture.base_url+'/api/v1/business/commercial/settings',{
      headers:apiHeaders,data:{request_id:require('node:crypto').randomUUID().replaceAll('-',''),
        revision:settings.revision,country,issuing_enabled:false},maxRedirects:0});
    assert.equal(response.status(),200,await response.text());
    await navigate(page,'Übersicht');await navigate(page,'Einstellungen');
  }
  await check('DE',true);
  await change('AT');await check('AT',false);
  await change('DE');await check('DE',true);
  await fs.writeFile(path.join(screenshots,'commercial-country-synthetic-results.json'),JSON.stringify(results,null,2));
  console.log('1 actual MFA/browser country-scope workflow passed (DE, unsupported AT, explicit DE return; no issuing permission inferred)');
}
module.exports={commercialCountryScopeFlow};
