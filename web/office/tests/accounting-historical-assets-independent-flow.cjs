/* Independent targeted real-browser review; replaces only the test entry via explicit preload. */
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs/promises');
async function historicalAssetsFlow(h){
 const {page,context,navigate,ready,screenshots}=h;let entered,release;const begun=new Promise(r=>entered=r),hold=new Promise(r=>release=r),pattern='**/api/v1/business/accounting/historical-assets';
 await navigate(page,'Finanzen');await page.getByRole('button',{name:'EÜR-Vorbereitung',exact:true}).click();await ready(page);
 await context.route(pattern,async route=>{const response=await route.fetch();assert.equal(response.status(),200);const state=await response.json();assert.equal(state.schema_version,1);entered();await hold;await route.fulfill({response});});
 try{
  await page.getByRole('button',{name:'Historische Anlagen',exact:true}).click();await begun;
  await page.getByRole('button',{name:'Vorbereitungsprofil',exact:true}).click();await page.getByRole('dialog',{name:'Vorbereitungsprofil',exact:true}).waitFor();
  const finalRead=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/business/capabilities'));release();await finalRead;await page.waitForTimeout(250);
  const title=await page.getByRole('dialog').getAttribute('aria-label');await fs.writeFile(path.join(screenshots,'independent-initial-state-dialog-result.json'),JSON.stringify({scenario:'actual initial asset-state response after unrelated profile dialog',expected:'Vorbereitungsprofil',actual:title},null,2));await page.screenshot({path:path.join(screenshots,'independent-initial-state-dialog.png')});assert.equal(title,'Vorbereitungsprofil');
  console.log('INDEPENDENT targeted actual browser review passed: delayed initial historical-asset state does not replace subsequently opened bookkeeping-profile dialog; real local MFA/HTTP; no product writes');
 }finally{release?.();await context.unroute(pattern);}
}
module.exports={historicalAssetsFlow};
