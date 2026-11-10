/* Actual rendered WCAG checks; no external scripts or customer data. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const AxeBuilder=require('@axe-core/playwright').default;
const reports=[];

async function audit(page,name){
  const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
  reports.push({name,engine:result.testEngine,violations:result.violations.map(v=>({id:v.id,impact:v.impact,help:v.help,helpUrl:v.helpUrl,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),
    manual_review:result.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),passed_rules:result.passes.length});
  return reports.at(-1);
}
exports.audit=audit;
exports.accessibilityFlow=async function({page,navigate,ready,screenshots}){
  const sections=await page.locator('.navigation button').allTextContents();
  const labels=await page.locator('.navigation button').evaluateAll(nodes=>nodes.map(n=>n.textContent.replace(n.querySelector('.nav-glyph')?.textContent||'','').trim()));
  assert.ok(sections.length>=10);
  for(const label of labels){await navigate(page,label);await audit(page,'desktop:'+label);}
  await navigate(page,'Kontakte');
  const opener=page.getByRole('button',{name:'Kontakt anlegen',exact:true});
  await opener.focus();await page.keyboard.press('Enter');
  const dialog=page.getByRole('dialog',{name:'Neuer Kontakt'});await dialog.waitFor();
  await audit(page,'desktop:Kontaktformular');
  const keyboard=[];
  for(const key of ['Shift+Tab','Tab','Tab','Shift+Tab']){
    await page.keyboard.press(key);
    keyboard.push(await dialog.evaluate(node=>node.contains(document.activeElement)));
  }
  await page.keyboard.press('Escape');await dialog.waitFor({state:'detached'});
  const restored=await opener.evaluate(node=>node===document.activeElement);
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
  for(const label of ['Übersicht','Kontakte','Finanzen','Einstellungen']){
    await navigate(page,label);await audit(page,'mobile:'+label);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'horizontal overflow '+label);
  }
  await fs.mkdir(screenshots,{recursive:true});
  await fs.writeFile(path.join(screenshots,'accessibility-report.json'),JSON.stringify({reports,keyboard_trapped:keyboard,focus_restored:restored,limits:'Rendered sampled views only; no native-device or complete human accessibility approval'},null,2)+'\n');
  const violations=reports.flatMap(r=>r.violations.map(v=>({view:r.name,...v})));
  if(violations.length)console.log(JSON.stringify(violations,null,2));
  assert.deepEqual(keyboard,[true,true,true,true],'dialog keyboard focus remains inside');
  assert.equal(restored,true,'Escape restores focus to opening button');
  assert.equal(violations.length,0,'rendered WCAG violations; details in accessibility-report.json');
  console.log(reports.length+' rendered accessibility views checked; manual-review findings retained in report');
};
