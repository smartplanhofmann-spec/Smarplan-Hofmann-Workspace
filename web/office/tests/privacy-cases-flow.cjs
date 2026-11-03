/* Real MFA/HTTP private case intake, supervised export and uncertain reply. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const path=require('node:path');
const request=value=>({request_id:crypto.randomUUID().replaceAll('-',''),...value});
async function privacyCasesFlow({page,context,navigate,fixture,screenshots}){
 let authorization,lose=true,created;const commands=[];
 const capture=req=>{if(new URL(req.url()).origin===fixture.base_url&&req.headers().authorization)authorization=req.headers().authorization;};page.on('request',capture);
 const dialog=title=>page.getByRole('dialog',{name:title,exact:true});
 async function api(suffix,body,status=200){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.equal(response.status(),status,suffix+' '+await response.text());return response.json();}
 await context.route('**/api/v1/business/privacy/cases',async route=>{if(route.request().method()!=='POST')return route.continue();const body=route.request().postDataJSON();commands.push(body);created=body.id;if(lose){lose=false;const response=await route.fetch();assert.equal(response.status(),200);return route.abort('failed');}return route.continue();});
 try{
  await navigate(page,'Einstellungen');const contact=await api('/contacts',request({name:'Synthetische Datenschutzperson',email:'private-browser@example.test',entity_type:'person'}),201);
  await page.getByRole('button',{name:'Datenschutzfälle öffnen',exact:true}).click();await dialog('Datenschutzfälle').getByRole('button',{name:'Datenschutzfall aufnehmen',exact:true}).click();
  const intake=dialog('Datenschutzfall aufnehmen');await intake.getByLabel('Betroffene Person',{exact:true}).selectOption('customer:'+contact.id);await intake.getByLabel('Anfragetyp',{exact:true}).selectOption('export');
  const due=new Date(Date.now()+20*86400000).toISOString().slice(0,10);await intake.getByLabel('Geprüfte Antwortfrist',{exact:true}).fill(due);await intake.getByLabel('Erbetener Umfang',{exact:true}).fill('Synthetische private Datenauskunft');await intake.getByLabel('Private Fallkopien aufbewahren bis',{exact:true}).fill(due);await intake.getByLabel('Zweck und Begründung dieser Aufbewahrung',{exact:true}).fill('Zeitlich begrenzte Bearbeitung dieser synthetischen Anfrage');
  await intake.getByRole('button',{name:'Speichern',exact:true}).click();await intake.getByRole('alert').waitFor();assert.equal(commands.length,1);assert.equal((await api('/privacy/cases/'+created)).status,'open');
  await intake.getByRole('button',{name:'Status des offenen Auftrags prüfen',exact:true}).click();await dialog('Datenschutzfall').waitFor();assert.equal(commands.length,1);
  await dialog('Datenschutzfall').getByRole('button',{name:'Identität prüfen',exact:true}).click();await dialog('Identität dokumentieren').getByLabel('Prüfnachweis ohne Ausweiskopie',{exact:true}).fill('Bestehender Kontaktweg unabhängig bestätigt');await dialog('Identität dokumentieren').getByLabel('Identität wurde tatsächlich geprüft.',{exact:true}).check();await dialog('Identität dokumentieren').getByRole('button',{name:'Speichern',exact:true}).click();
  await dialog('Datenschutzfall').getByRole('button',{name:'Quellen neu erfassen',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-privacy-cases]')?.textContent.includes('Strukturierte Quellen'));
  const sources=(await api('/privacy/cases/'+created)).inventory.sources;
  for(let index=0;index<sources.length;index++){
   await dialog('Datenschutzfall').getByRole('button',{name:'Quelle prüfen',exact:true}).nth(index).click();const review=dialog('Quelle prüfen');await review.getByLabel('Entscheidung',{exact:true}).selectOption('include');await review.getByLabel('Begründung und Aufbewahrung / Fremdpersonen',{exact:true}).fill('Nur synthetische betroffene Person; weitere Personen geprüft');await review.getByRole('button',{name:'Speichern',exact:true}).click();await dialog('Datenschutzfall').waitFor();
  }
  const areas=['Freitext und weitere Namensnennungen','Originaldateien und Daten anderer Personen','Historische Nachweise und Wiederholungsquittungen','Externe Systeme und lokale Dateien','Empfänger und weitergegebene Kopien','Sicherungen und Wiederherstellung','Aufbewahrungspflichten und Sperren'];
  for(const label of areas){await dialog('Datenschutzfall').locator('.list-row').filter({has:page.getByRole('heading',{name:label,exact:true})}).getByRole('button',{name:'Prüfung dokumentieren',exact:true}).click();const form=dialog(label);await form.getByLabel('Prüfergebnis',{exact:true}).selectOption('checked');await form.getByLabel('Konkreter Prüfnachweis und verbleibende Grenzen',{exact:true}).fill('Synthetischer Bestand konkret geprüft: '+label);await form.getByRole('button',{name:'Speichern',exact:true}).click();await dialog('Datenschutzfall').waitFor();}
  await dialog('Datenschutzfall').getByRole('button',{name:'Geprüften Personenexport erstellen',exact:true}).click();await dialog('Personenexport freigeben').getByLabel('Auswahl, fremde Personendaten und sichere Übergabe geprüft.',{exact:true}).check();await dialog('Personenexport freigeben').getByRole('button',{name:'Speichern',exact:true}).click();await dialog('Datenschutzfall').waitFor();
  const value=await api('/privacy/cases/'+created);assert.equal(value.exports.length,1);assert.equal(value.automatic_completeness,false);assert.equal(value.external_messages_sent,false);
  const download=page.waitForEvent('download');await dialog('Datenschutzfall').getByRole('button',{name:'ZIP herunterladen',exact:true}).click();const file=await download;const bytes=await fs.readFile(await file.path());assert.equal(bytes.length,value.exports[0].size);assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'),value.exports[0].sha256);
  await dialog('Datenschutzfall').evaluate(node=>node.scrollTop=0);await page.screenshot({path:path.join(screenshots,'privacy-case-desktop.png')});await page.setViewportSize({width:390,height:844});await dialog('Datenschutzfall').evaluate(node=>node.scrollTop=0);await dialog('Datenschutzfall').getByRole('heading',{name:'Datenschutzfall',exact:true}).scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'privacy-case-mobile.png')});
  const stored=await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}));assert.equal(stored.includes('private-browser@example.test'),false);assert.equal(stored.includes('Synthetische private Datenauskunft'),false);
  console.log('privacy cases: named subject selection, lost create reply/read-only status, identity, structured and manual review, bounded ZIP/hash, RAM-only drafts and mobile layout passed');
 }finally{page.off('request',capture);await context.unroute('**/api/v1/business/privacy/cases');}
}
module.exports={privacyCasesFlow};
