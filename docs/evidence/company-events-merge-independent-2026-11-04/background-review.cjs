const assert=require('node:assert/strict');
module.exports.companyEventsFlow=async({page,navigate})=>{
 await navigate(page,'Assistent');let enter,release,done;const entered=new Promise(r=>enter=r),completed=new Promise(r=>done=r);
 await page.route('**/api/v1/business/company-events/plans',async route=>{const actual=await route.fetch();await new Promise(r=>{release=r;enter();});await route.fulfill({response:actual});done();});
 await page.getByRole('button',{name:'Unternehmensereignisse öffnen',exact:true}).click();await entered;
 assert.equal(await page.getByRole('dialog').count(),0,'Initial read must still be before its first dialog');
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});
 release();await completed;await page.waitForLoadState('networkidle');
 const count=await page.getByRole('dialog').count();console.log(JSON.stringify({case:'held initial event list after actual DOM background handler',hidden:await page.evaluate(()=>document.hidden),dialogs:count,dialogTitles:await page.getByRole('dialog').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')))}));
 assert.equal(count,0,'Initial private event list must not appear after background before its first dialog');
};
