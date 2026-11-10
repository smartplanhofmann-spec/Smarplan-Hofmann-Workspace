/* Real, read-only rendered dialogs; all application data is synthetic. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {audit}=require('./accessibility-flow.cjs');

const forms=[
 ['Anfragen','Anfrage erfassen'],
 ['Projekte','Neues Projekt'],
 ['Kontakte','Kontakt anlegen'],
 ['Einsatzplanung','Termin planen'],
 ['Dokumente','Belegentwurf erstellen'],
 ['Material','Artikel / Leistung anlegen'],
 ['Material','Lagerort anlegen'],
 ['Material','Bewegung buchen'],
 ['Personal','Mitarbeiterprofil anlegen'],
 ['Personal','Personalakte, Reisen und Lohnvorbereitung'],
 ['Einstellungen','Status hinzufügen'],
 ['Einstellungen','Freigaben ansehen / ändern'],
 ['Einstellungen','Zusatzfelder verwalten'],
 ['Einstellungen','Lieferantenkataloge und Adapter'],
 ['Einstellungen','Datierte Katalogpreise'],
 ['Einstellungen','Dateiimport öffnen'],
 ['Einstellungen','Unternehmensübergabe öffnen'],
 ['Einstellungen','Datenschutzfälle öffnen'],
 ['Einstellungen','Jahresvorträge öffnen'],
];

exports.accessibilityFormsFlow=async function({page,navigate,screenshots}){
 const reports=[],keyboard=[],scrolling=[],writes=[];
 const record=request=>{const url=new URL(request.url());if(url.pathname.startsWith('/api/')&&!['GET','HEAD','OPTIONS'].includes(request.method()))writes.push({method:request.method(),path:url.pathname});};
 const output=path.join(screenshots,'accessibility-forms-report.json');
 async function save(){await fs.mkdir(screenshots,{recursive:true});await fs.writeFile(output,JSON.stringify({reports,keyboard,scrolling,writes,limits:'Actual synthetic read-only forms; automatic rules and keyboard checks only. Human screenreader, full browser zoom and real Windows/iPhone assistive technology approval remain separate.'},null,2)+'\n');}
 async function checkKeyboard(dialog,opener,name){
  await opener.evaluate(node=>node.focus());
  const backgroundBlocked=await dialog.evaluate(node=>node.contains(document.activeElement));
  const values=[];
  // Reach both boundaries by real Tab/Shift+Tab, from the actual dialog
  // container and from its close button. No form submission is invoked.
  await dialog.focus();
  for(const key of ['Shift+Tab','Tab','Tab','Shift+Tab','Shift+Tab','Tab']){
   await page.keyboard.press(key);values.push(await dialog.evaluate(node=>node.contains(document.activeElement)));
  }
  await page.keyboard.press('Escape');
  const closed=await dialog.count()===0;
  const restored=closed&&await opener.evaluate(node=>node===document.activeElement);
  keyboard.push({name,background_blocked:backgroundBlocked,contained:values,escape_closed:closed,focus_restored:restored});
  if(!closed)await dialog.getByRole('button',{name:'Dialog schließen',exact:true}).click();
 }
 page.on('request',record);
 try{
  for(const mode of ['desktop','mobile','large-text','forced-colors']){
   await page.setViewportSize(mode==='mobile'?{width:390,height:844}:{width:1440,height:1000});
   await page.emulateMedia({forcedColors:mode==='forced-colors'?'active':'none',reducedMotion:'reduce'});
   await page.evaluate(large=>document.documentElement.style.fontSize=large?'200%':'',mode==='large-text');
   const navigation=await page.locator('.navigation button').evaluateAll(nodes=>nodes.map(n=>n.textContent.replace(n.querySelector('.nav-glyph')?.textContent||'','').trim()));
   for(const area of navigation){
    await navigate(page,area);const result=await audit(page,mode+':main:'+area);
    result.document_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);result.dialog_overflow=false;
    reports.push(result);
    const regions=page.locator('main .table-scroll');
    for(let i=0;i<await regions.count();i++){
     const region=regions.nth(i);if(!await region.evaluate(node=>node.scrollWidth>node.clientWidth+1))continue;
     await region.evaluate(node=>node.scrollLeft=0);await region.focus();await page.keyboard.press('ArrowRight');
     let moved=true;try{await page.waitForFunction(node=>node.scrollLeft>0,await region.elementHandle(),{timeout:1500});}catch{moved=false;}
     scrolling.push({name:mode+':main:'+area,region:i,keyboard_moved:moved});
     await region.evaluate(node=>node.scrollLeft=0);
    }
    await save();
   }
   for(const [area,label] of forms){
    await navigate(page,area);
    const opener=page.locator('main').getByRole('button',{name:label,exact:true});
    assert.equal(await opener.count(),1,'Required form must exist: '+area+' / '+label);
    await opener.focus();await page.keyboard.press('Enter');
    const dialog=page.getByRole('dialog');await dialog.waitFor();
    const name=mode+':'+area+':'+label;
    const result=await audit(page,name);
    result.document_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
    result.dialog_overflow=await dialog.evaluate(node=>node.scrollWidth>node.clientWidth+1);
    reports.push(result);await checkKeyboard(dialog,opener,name);await save();
    console.log('accessibility form checked: '+name);
   }
  }
  const violations=reports.flatMap(r=>r.violations.map(v=>({view:r.name,...v})));
  if(violations.length)console.log(JSON.stringify(violations,null,2));
  assert.ok(scrolling.length>0&&scrolling.every(r=>r.keyboard_moved),'Actually overflowing tables must scroll by keyboard');
  assert.deepEqual(writes,[],'Opening and inspecting these forms must not write business data');
  assert.ok(keyboard.every(r=>r.background_blocked&&r.contained.every(Boolean)&&r.escape_closed&&r.focus_restored),'Full focus/keyboard evidence in report');
  assert.ok(reports.every(r=>!r.document_overflow&&!r.dialog_overflow),'Actual rendered form overflow evidence in report');
  assert.equal(violations.length,0,'Actual rendered form WCAG violations in report');
  console.log(reports.length+' real form states checked with keyboard, mobile,200% text and forced colors; human review findings retained');
 }finally{
  page.off('request',record);await save();
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.emulateMedia({forcedColors:'none',reducedMotion:'no-preference'});
 }
};
