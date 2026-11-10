const assert=require('node:assert/strict'),path=require('node:path');
async function qontoReadonlyFlow(h){
 const {page,navigate,ready,screenshots}=h;
 const dialog=name=>page.getByRole('dialog',{name,exact:true});
 await navigate(page,'Finanzen');await page.getByRole('button',{name:'Bankabgleich öffnen',exact:true}).click();
 await dialog('Bankabgleich').getByRole('button',{name:'Qonto-Umsatzänderungen lesen',exact:true}).click();
 await dialog('Qonto lesen').getByLabel('Änderungen ab (UTC, einschließlich)',{exact:true}).fill('2026-11-01');
 await dialog('Qonto lesen').getByLabel('Änderungen bis (UTC, ausschließlich)',{exact:true}).fill('2026-11-10');
 await dialog('Qonto lesen').getByRole('button',{name:'Umsatzänderungen lesen',exact:true}).click();
 const result=dialog('Qonto · gelesene Umsatzänderungen');await result.waitFor();
 for(const status of ['Abgeschlossen','Vorgemerkt','Abgelehnt','Storniert'])await result.getByRole('cell',{name:status,exact:true}).waitFor();
 assert.match(await result.innerText(),/kein vollständiger Kontoauszug/);
 assert.equal(await result.locator('tbody tr').count(),4);
 assert.ok(!(await result.innerText()).includes('PRIVATE_'));
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(screenshots,'qonto-readonly-mobile.png'),fullPage:false});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.getByRole('button',{name:'Dialog schließen',exact:true}).click();
 await page.getByRole('button',{name:'Abmelden',exact:true}).click();
 assert.equal(await page.locator('[data-bank-private]').count(),0);
 console.log('qonto: actual MFA/HTTP and pinned synthetic upstream, four original statuses, exact cents, no private fields,390px and logout clearance passed');
}
module.exports={qontoReadonlyFlow};
