const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const request=body=>({request_id:crypto.randomUUID().replaceAll('-',''),...body});

async function factorFlow({page,context,navigate,ready,fixture,screenshots}){
  let token,lose=true;const records=[];
  page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)token=r.headers().authorization;});
  const modal=name=>page.getByRole('dialog',{name,exact:true});
  const close=()=>page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
  const workspace=()=>modal('Lohnberechnung 2026 · Synthetic technician');
  async function api(suffix,body){const r=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:token,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(r.ok(),suffix+' '+await r.text());return r.json();}
  async function open(){await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();await workspace().waitFor();}
  async function calculate(correction=false){
    await workspace().getByRole('button',{name:correction?'Monatsberechnung korrigieren':'Belegte Monatsberechnung prüfen',exact:true}).click();
    const editor=modal(correction?'Monatsberechnung korrigieren':'Belegte Monatsberechnung prüfen');
    await editor.getByLabel('Geprüftes gültiges Lohnprofil',{exact:true}).selectOption({index:1});
    await editor.getByLabel('Abgeschlossene HR-Monatsquelle',{exact:true}).selectOption({index:1});
    await editor.getByLabel('Geprüftes Brutto aus Vereinbarung und Monatsquellen (€)',{exact:true}).fill('5000.00');
    await editor.getByRole('checkbox').check();
    if(correction)await editor.getByLabel('Nachvollziehbarer Korrekturgrund',{exact:true}).fill('Synthetische belegte Faktorkorrektur');
    await editor.getByRole('button',{name:'Berechnungsumfang unverbindlich prüfen',exact:true}).click();
    const confirm=modal('Geprüften Berechnungsumfang festhalten');await confirm.waitFor();return confirm;
  }
  const pattern='**/api/v1/business/payroll/**';
  await context.route(pattern,async route=>{const req=route.request(),response=await route.fetch({maxRedirects:0});if(!response.headers()['content-type']?.includes('application/json'))return route.fulfill({response});const value=await response.json(),body=req.method()==='POST'?req.postDataJSON():null,url=new URL(req.url());records.push({path:url.pathname,body,status:response.status(),value});if(response.ok()&&body&&url.pathname.endsWith('/runs')&&lose){lose=false;return route.abort('failed');}return route.fulfill({response});});
  try{
    await navigate(page,'Personal');await page.getByLabel('Mitarbeiter',{exact:true}).selectOption({label:'Synthetic technician'});await ready(page);
    const employees=await api('/employees'),employee=(Array.isArray(employees)?employees:employees.items).find(e=>e.name==='Synthetic technician');
    const file=await api('/personnel/files',request({employee_id:employee.id,purpose:'personnel',owner_visible:false,filename:'synthetic-factor-evidence.pdf',media_type:'application/pdf',content_base64:Buffer.from('%PDF-1.4\nSynthetic verified class-IV factor evidence\n%%EOF').toString('base64')}));
    await api('/personnel/agreements',request({employee_id:employee.id,revision:0,effective_from:'2026-01-01',employment_kind:'regular',pay_basis:'monthly',amount_minor:500000,currency:'EUR',reference_file_id:file.id,notes:'Synthetic verified full-month salary'}));
    const hr=await api(`/personnel/payroll-preparations/preview?employee_id=${employee.id}&month=2026-10`);
    await api('/personnel/payroll-preparations',request({employee_id:employee.id,revision:0,month:'2026-10',source_hash:hr.source_hash,completeness_confirmed:true}));
    await open();await workspace().getByRole('button',{name:'Neues Lohnprofil erfassen',exact:true}).click();
    let editor=modal('Neues Lohnprofil erfassen');
    assert.equal(await editor.getByLabel('Eingetragener ELStAM-Faktor (Steuerklasse IV)',{exact:true}).inputValue(),'');
    const texts={'Tatsächlicher Gültigkeitsbeginn':'2026-01-01','Geburtsdatum':'1990-01-01','Steuerklasse':'4','Kinderfreibeträge in halben Einheiten':'0','Krankenkasse / Versicherungsnachweis':'Synthetische nachgewiesene Kasse','Kassenindividueller Zusatzbeitrag (%)':'2.90','Berücksichtigungsfähige Kinder unter 25':'0','Tatsächlicher U1-Satz (%)':'2.10','Tatsächlicher U2-Satz (%)':'0.44','Regelmäßiges Jahresbrutto (€)':'60000','Prüfvermerk und Merkmalsnachweise':'Synthetischer gültiger ELStAM-Faktor geprüft','Monatlicher ELStAM-Freibetrag (€)':'0','Monatlicher ELStAM-Hinzurechnungsbetrag (€)':'0','Eingetragener ELStAM-Faktor (Steuerklasse IV)':'0.7539'};
    for(const [label,value]of Object.entries(texts))await editor.getByLabel(label,{exact:true}).fill(value);
    const choices={'Beschäftigungsart':'regular','Maßgebliches Bundesland':'HE','Kirchensteuermerkmal':'none','Krankenversicherungsart':'statutory_mandatory','Elterneigenschaft nachgewiesen':'false','U1-Teilnahme nachgewiesen':'true','Minijob: RV-Befreiung nachgewiesen':'false','Steuerverfahren':'individual','Weitere RV-Pflicht für Mindestbeitragsausnahme nachgewiesen':'false','Steuerberechnungsumfang ausdrücklich wählen':'factor','Übergangsbereich ausdrücklich beurteilen':'none','Geschütztes Personaloriginal der Merkmale':file.id};
    for(const [label,value]of Object.entries(choices))await editor.getByLabel(label,{exact:true}).selectOption(value);
    await editor.getByRole('checkbox').check();await editor.getByRole('button',{name:'Geprüfte Merkmale belegt speichern',exact:true}).click();
    await editor.getByRole('alert').waitFor();assert.match(await editor.innerText(),/genau drei Nachkommastellen/);
    assert.equal(records.filter(r=>r.body&&r.path.endsWith('/profiles')).length,0);
    await editor.getByLabel('Eingetragener ELStAM-Faktor (Steuerklasse IV)',{exact:true}).fill('0,753');
    await editor.getByRole('button',{name:'Geprüfte Merkmale belegt speichern',exact:true}).click();await workspace().waitFor();
    let confirmation=await calculate();assert.match(await confirmation.innerText(),/Steuerklasse IV mit Faktor/);assert.match(await confirmation.innerText(),/0\.753/);assert.match(await confirmation.innerText(),/589,08/);assert.match(await confirmation.innerText(),/3\.323,42/);
    await page.screenshot({path:path.join(screenshots,'payroll-factor-preview-desktop.png'),fullPage:false});
    await page.setViewportSize({width:390,height:844});await page.locator('.sidebar').evaluate(el=>Promise.all(el.getAnimations().map(a=>a.finished)));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    await page.screenshot({path:path.join(screenshots,'payroll-factor-preview-mobile.png'),fullPage:false});await page.setViewportSize({width:1440,height:1000});
    await confirmation.getByRole('checkbox').check();await confirmation.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await confirmation.getByRole('alert').waitFor();await close();
    await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);await open();
    const attempts=records.filter(r=>r.body&&r.path.endsWith('/runs'));assert.equal(attempts.length,2);assert.deepEqual(attempts[0].body,attempts[1].body);assert.deepEqual(attempts[0].value,attempts[1].value);
    const original=attempts[0].value;assert.equal(original.calculation.net_minor,332342);
    const download=page.waitForEvent('download');await workspace().getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();const pdf=await fs.readFile(await(await download).path());assert.equal(crypto.createHash('sha256').update(pdf).digest('hex'),original.pdf_sha256);
    await workspace().getByRole('button',{name:'Profil korrigieren',exact:true}).click();editor=modal('Lohnprofil korrigieren');assert.equal(await editor.getByLabel('Steuerberechnungsumfang ausdrücklich wählen',{exact:true}).inputValue(),'factor');assert.equal(await editor.getByLabel('Eingetragener ELStAM-Faktor (Steuerklasse IV)',{exact:true}).inputValue(),'0.753');
    await editor.getByLabel('Eingetragener ELStAM-Faktor (Steuerklasse IV)',{exact:true}).fill('0.900');await editor.getByLabel('Korrekturgrund',{exact:true}).fill('Synthetischer wirksamer geänderter Faktor');await editor.getByRole('checkbox').check();await editor.getByRole('button',{name:'Geprüfte Merkmale belegt speichern',exact:true}).click();await workspace().waitFor();
    confirmation=await calculate(true);assert.match(await confirmation.innerText(),/3\.208,34/);await confirmation.getByRole('checkbox').check();await confirmation.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await workspace().waitFor();
    const runs=(await api('/payroll/runs?employee_id='+employee.id)).items;assert.equal(runs.length,1);assert.equal(runs[0].revision,2);assert.equal(runs[0].delta.employee_tax_minor,11508);assert.equal(runs[0].delta.net_minor,-11508);
    await workspace().getByRole('button',{name:'Laufhistorie',exact:true}).click();const history=modal('Laufhistorie');await history.waitFor();const historicalDownload=page.waitForEvent('download');await history.getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();assert.deepEqual(await fs.readFile(await(await historicalDownload).path()),pdf);
    const ledger=await api(`/payroll/ledger?employee_id=${employee.id}&year=2026`);assert.equal(ledger.ledger.recorded_months,1);assert.equal(ledger.ledger.totals.net_minor,320834);
    const statement=await api('/payroll/employee-statements/'+runs[0].id);assert.equal(statement.statement.calculation.net_minor,320834);assert.equal(statement.statement.calculation.tax_parameters,undefined);
    console.log('factor payroll: explicit original-backed class-IV factor form, invalid precision blocked before POST, real preview, lost-ACK exact retry, new rule version, factor correction and tax delta, unchanged historical PDF, latest annual totals, reduced employee statement and 390px view passed');
  }finally{await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-factor-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={factorFlow};
