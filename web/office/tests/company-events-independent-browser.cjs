/* Independent actual Chromium/MFA check using the existing disposable host. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');

async function companyEventsFlow({page,navigate,ready,fixture,screenshots}){
  const results=[];
  for(const mode of ['dialog-success','dialog-error','project-error']){
    await navigate(page,'Assistent');
    let release,enter,completed,held=false;
    const entered=new Promise(r=>enter=r),delivered=new Promise(r=>completed=r);
    const message='PRIVATE INDEPENDENT OLD PLAN '+('d'.repeat(32));
    await page.route('**/api/v1/business/company-events/plans',async route=>{
      if(held){await route.continue();return;}
      held=true;const actual=await route.fetch();
      await new Promise(r=>{release=r;enter();});
      if(mode.endsWith('error'))await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:message})});
      else await route.fulfill({response:actual});
      completed();
    });
    try{
      await page.getByRole('button',{name:'Unternehmensereignisse öffnen',exact:true}).click();
      await entered;
      if(mode.startsWith('dialog')){
        // The first opening has not created a dialog. A second explicit opening
        // creates another real dialog and then a separate unsent scan editor.
        await page.getByRole('button',{name:'Unternehmensereignisse öffnen',exact:true}).click();
        await page.getByRole('dialog',{name:'Unternehmensereignisse',exact:true}).waitFor();
        await page.getByRole('button',{name:'Ereignislauf prüfen und starten',exact:true}).click();
        await page.getByRole('dialog',{name:'Ereignislauf starten',exact:true}).waitFor();
      }else{
        await page.getByLabel('Aktuelles Projekt',{exact:true}).selectOption(fixture.project_id);
        await ready(page);
      }
      release();await delivered;
      await page.waitForLoadState('networkidle');
      const visible=await page.locator('body').innerText();
      const current=mode.startsWith('dialog')?await page.getByRole('dialog',{name:'Ereignislauf starten',exact:true}).count():await page.getByRole('dialog').count()===0;
      const evidence={mode,privateErrorVisible:visible.includes(message),currentContextPreserved:Boolean(current)};
      results.push(evidence);
      await page.screenshot({path:path.join(screenshots,'independent-'+mode+'.png'),fullPage:true});
      assert.equal(evidence.privateErrorVisible,false,'An earlier private error must not appear in the current browser context');
      assert.equal(evidence.currentContextPreserved,true);
      if(mode.startsWith('dialog'))await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
    }finally{
      release?.();await page.unroute('**/api/v1/business/company-events/plans');
      await fs.writeFile(path.join(screenshots,'independent-context-results.json'),JSON.stringify(results,null,2)+'\n');
    }
  }
  console.log('Independent company events: actual MFA/HTTP/Chromium held initial list success/error after a new unsent dialog and project replacement passed; no business mutation.');
}
module.exports={companyEventsFlow};
