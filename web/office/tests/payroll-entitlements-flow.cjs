const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const request=value=>({request_id:crypto.randomUUID().replaceAll('-',''),...value});
async function payrollEntitlementsFlow(h){
 const {page,context,navigate,ready,fixture,screenshots}=h;
 let token,employee,file,terms,agreement,lose=true;const records=[];
 page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)token=r.headers().authorization;});
 const modal=name=>page.getByRole('dialog',{name,exact:true});
 const close=async()=>{if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();};
 const label='Unbezahlte Unterbrechung und SV-Fortbestand';
 async function api(suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:token,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 async function open(){await close();await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();await page.getByRole('button',{name:'Private Anspruchsnachweise öffnen',exact:true}).click();await modal('Private Anspruchsnachweise · Synthetic technician').waitFor();}
 const pattern='**/api/v1/business/payroll/entitlements**';
 await context.route(pattern,async route=>{const req=route.request(),response=await route.fetch({maxRedirects:0}),value=await response.json(),body=req.method()==='POST'?req.postDataJSON():null,url=new URL(req.url());records.push({path:url.pathname,body,status:response.status(),value});if(response.ok()&&body&&url.pathname.endsWith('/entitlements')&&lose){lose=false;return route.abort('failed');}return route.fulfill({response});});
 try{
  await navigate(page,'Personal');await page.getByLabel('Mitarbeiter',{exact:true}).selectOption({label:'Synthetic technician'});await ready(page);
  const employees=await api('/employees');employee=(Array.isArray(employees)?employees:employees.items).find(v=>v.name==='Synthetic technician');employee=await api('/employees',request({id:employee.id,revision:employee.revision,employment_from:'2026-01-01',employment_to:null}));
  file=await api('/personnel/files',request({employee_id:employee.id,purpose:'personnel',owner_visible:false,filename:'synthetic-unpaid-original.pdf',media_type:'application/pdf',content_base64:Buffer.from('%PDF-1.4\nSynthetic actual employment and unpaid continuation source\n%%EOF').toString('base64')}));
  agreement=await api('/personnel/agreements',request({employee_id:employee.id,revision:0,effective_from:'2026-01-01',employment_kind:'regular',pay_basis:'monthly',amount_minor:300000,currency:'EUR',reference_file_id:file.id,notes:'Synthetic actual calendar-day contract'}));
  terms=await api('/payroll/facts',request({employee_id:employee.id,employee_revision:employee.revision,kind:'employment_terms',revision:0,status:'active',confirmed:true,source_file_ids:[file.id],details:{employment_from:'2026-01-01',employment_to:null,proration_method:'calendar_days_actual',agreement_refs:[{id:agreement.id,revision:agreement.revision,content_hash:agreement.content_hash}],reason:'Synthetic canonical contract for explicit unpaid source'}}));
  await open();await modal('Private Anspruchsnachweise · Synthetic technician').getByRole('button',{name:label+' erfassen',exact:true}).click();
  const editor=modal('Erfassen: '+label);
  assert.equal(await editor.getByLabel('Tatsächlicher Beginn ohne Entgeltanspruch',{exact:true}).inputValue(),'');
  await editor.getByLabel('Belegte Beschäftigungsfassung',{exact:true}).selectOption(terms.id);
  await editor.getByLabel('Alle einschlägigen Entgeltvereinbarungen',{exact:true}).selectOption(agreement.id);
  await editor.getByLabel('Geschützte Originale für diesen Anspruch',{exact:true}).selectOption(file.id);
  await editor.getByLabel('Nachvollziehbarer Anspruchsprüfvermerk',{exact:true}).fill('Synthetic complete evidenced unpaid period without diagnosis');
  await editor.getByLabel('Tatsächlicher Beginn ohne Entgeltanspruch',{exact:true}).fill('2026-10-20');
  await editor.getByLabel('Tatsächliches Ende des zu prüfenden Zeitraums',{exact:true}).fill('2026-12-15');
  await editor.getByLabel('Anzahl belegter Ausnahmetatbestände, auch bekannte 0',{exact:true}).fill('0');
  for(const text of ['Das Beschäftigungsverhältnis besteht nach Beleg fort.','Für diesen Zeitraum besteht nach Beleg kein Entgeltanspruch.','Es gibt keine dazwischenliegenden entgeltberechtigten Tage.'])await editor.getByLabel(text,{exact:true}).check();
  await editor.getByRole('button',{name:'Konkrete Anspruchsangaben belegen',exact:true}).click();
  const details=modal('Konkrete Angaben: '+label);await details.getByLabel('Originale für die unbezahlte Unterbrechung',{exact:true}).selectOption(file.id);await details.getByLabel('Ich bestätige diese konkreten Anspruchsangaben und Originale.',{exact:true}).check();await details.getByRole('button',{name:'Anspruch unverbindlich prüfen',exact:true}).click();
  const preview=modal('Anspruchsbaustein prüfen');await preview.waitFor();assert.match(await preview.innerText(),/19\.11\.2026/);assert.match(await preview.innerText(),/20\.11\.2026/);
  await preview.getByLabel('Ich bestätige genau diesen geprüften Anspruchsbaustein und seine Originale.',{exact:true}).check();await preview.getByRole('button',{name:'Geprüften Anspruchsbaustein festhalten',exact:true}).click();await preview.getByRole('alert').waitFor();
  await close();await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);await open();await modal('Private Anspruchsnachweise · Synthetic technician').getByRole('button',{name:'Anspruchsnachweis öffnen',exact:true}).click();
  const saved=modal(label);await saved.waitFor();const commands=records.filter(v=>v.body&&v.path.endsWith('/entitlements'));assert.equal(commands.length,2);assert.deepEqual(commands[0].body,commands[1].body);assert.deepEqual(commands[0].value,commands[1].value);
  const record=commands[0].value;assert.equal(record.revision,1);assert.equal(record.plan.intervals[0].to,'2026-11-19');assert.equal(record.plan.intervals[1].employment_for_contributions_continues,false);
  const download=page.waitForEvent('download');await saved.getByRole('button',{name:'Personaloriginal: '+file.filename,exact:true}).click();assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await download).path())).digest('hex'),file.sha256);
  await page.setViewportSize({width:390,height:844});await page.locator('.sidebar').evaluate(el=>Promise.all(el.getAnimations().map(a=>a.finished)));assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(await saved.locator('.table-scroll').evaluateAll(nodes=>nodes.every(n=>n.scrollWidth<=n.clientWidth+1)),true);await page.screenshot({path:path.join(screenshots,'payroll-entitlements-mobile.png'),fullPage:false});
  await saved.getByRole('button',{name:'Fälschlichen Anspruch aufheben',exact:true}).click();const cancel=modal('Fälschlichen Anspruch aufheben');await cancel.getByLabel('Belegter Aufhebungsgrund',{exact:true}).fill('Synthetic original unpaid request was canceled');await cancel.getByLabel('Ich bestätige die Aufhebung; frühere Abrechnungen bleiben unverändert.',{exact:true}).check();await cancel.getByRole('button',{name:'Anspruch belegt aufheben',exact:true}).click();await modal(label).waitFor();assert.match(await modal(label).innerText(),/Aufgehoben/);await modal(label).getByRole('button',{name:'Anspruchshistorie öffnen',exact:true}).click();await modal('Anspruchshistorie').waitFor();assert.equal(await modal('Anspruchshistorie').getByRole('button',{name:'Diese Anspruchsfassung öffnen',exact:true}).count(),2);await modal('Anspruchshistorie').getByRole('button',{name:'Diese Anspruchsfassung öffnen',exact:true}).first().click();await modal('Historische Anspruchsfassung · '+label).waitFor();assert.equal(await modal('Historische Anspruchsfassung · '+label).getByRole('button',{name:'Anspruch korrigieren',exact:true}).count(),0);
  const history=await api('/payroll/entitlements/'+record.id+'/history');assert.deepEqual(history.items[0],record);assert.equal(history.items[1].status,'void');assert.deepEqual(history.items[1].plan,record.plan);
  const sicknessLabel='Krankheitsverlauf und Vorzeiten';
  for(const preemployment of [false,true]){
   await open();await modal('Private Anspruchsnachweise · Synthetic technician').getByRole('button',{name:sicknessLabel+' erfassen',exact:true}).click();
   const editor=modal('Erfassen: '+sicknessLabel);
   await editor.getByLabel('Belegte Beschäftigungsfassung',{exact:true}).selectOption(terms.id);
   await editor.getByLabel('Alle einschlägigen Entgeltvereinbarungen',{exact:true}).selectOption(agreement.id);
   await editor.getByLabel('Geschützte Originale für diesen Anspruch',{exact:true}).selectOption(file.id);
   await editor.getByLabel('Nachvollziehbarer Anspruchsprüfvermerk',{exact:true}).fill('Synthetic evidenced '+(preemployment?'preemployment sickness and prior contract':'joined causes and continuous work incapacity'));
   await editor.getByLabel('Belegte Form des Krankheitsverlaufs',{exact:true}).selectOption(preemployment?'preemployment':'combined');
   await editor.getByLabel('Belegte vollständige Vorzeiten ab',{exact:true}).fill('2026-01-01');
   await editor.getByLabel('Belegte vollständige Vorzeiten bis',{exact:true}).fill('2026-12-31');
   await editor.getByLabel('Anzahl vollständig belegter Krankheitsfälle, auch bekannte 0',{exact:true}).fill(preemployment?'1':'2');
   await editor.getByRole('button',{name:'Konkrete Anspruchsangaben belegen',exact:true}).click();
   const details=modal('Konkrete Angaben: '+sicknessLabel);
   await details.getByLabel('Originale für die Vollständigkeit der Vorzeiten',{exact:true}).selectOption(file.id);
   await details.getByLabel('Originale für die zusammenhängenden Verhinderungsfälle und ihre Zuordnung',{exact:true}).selectOption(file.id);
   if(preemployment){
    await details.getByLabel('Tatsächliches Datum des Vertragsabschlusses vor der Erkrankung',{exact:true}).fill('2025-12-01');
    await details.getByLabel('Vertragsoriginal für den vereinbarten Beschäftigungsbeginn',{exact:true}).selectOption(file.id);
   }
   const episodes=preemployment?[{from:'2025-12-20',to:'2026-03-31',onset:'before_employment',relation:'new',recovery:'yes'}]:[{from:'2026-04-01',to:'2026-04-20',onset:'before_work',relation:'new',recovery:'yes'},{from:'2026-04-10',to:'2026-05-31',onset:'during_existing_au',relation:'same:0',recovery:'no'}];
   for(const [index,e]of episodes.entries()){
    const p='Vorzeitenfall '+(index+1)+': ';
    await details.getByLabel(p+'Beginn',{exact:true}).fill(e.from);await details.getByLabel(p+'Ende',{exact:true}).fill(e.to);
    await details.getByLabel(p+'tatsächlicher Beginn zur Arbeit',{exact:true}).selectOption(e.onset);
    await details.getByLabel(p+'belegter Fortsetzungszusammenhang',{exact:true}).selectOption('new');
    await details.getByLabel(p+'belegter Verhinderungsfall',{exact:true}).selectOption(e.relation);
    const recovery=details.getByLabel(p+'vorherige Arbeitsfähigkeit belegt (Nein bei fortbestehender AU)',{exact:true});assert.equal(await recovery.inputValue(),'');await recovery.selectOption(e.recovery);
    assert.equal(await details.getByLabel(p+'erster ausgefallener Solltag nur bei Stundenlohn-AU am freien Tag',{exact:true}).inputValue(),'');
    await details.getByLabel(p+'Unverschuldete Arbeitsverhinderung ist belegt.',{exact:true}).check();
    await details.getByLabel(p+'konkrete Originale',{exact:true}).selectOption(file.id);
   }
   await details.getByLabel('Ich bestätige diese konkreten Anspruchsangaben und Originale.',{exact:true}).check();await details.getByRole('button',{name:'Anspruch unverbindlich prüfen',exact:true}).click();
   const preview=modal('Anspruchsbaustein prüfen');await preview.waitFor();assert.match(await preview.innerText(),/Zusammenhängender Verhinderungsfall 1/);assert.match(await preview.innerText(),/Geprüfte Phasen ohne doppelte Tageszählung/);
   const checked=records.filter(v=>v.path.endsWith('/preview')).at(-1);assert.equal(checked.status,200);assert.equal(checked.value.plan.rule_version,preemployment?'de_2026_sickness_start_v4':'de_2026_sickness_phases_v3');
   assert.equal(checked.value.plan.prevention_cases[0].statutory_deadline,preemployment?'2026-03-11':'2026-05-12');
   assert.equal(checked.body.details.input.episodes[0].from,episodes[0].from);assert.ok(checked.body.details.input.episodes.every(e=>e.first_scheduled_day===null));
   if(preemployment){assert.equal(checked.value.plan.preemployment_periods[0].employment_wage_entitlement,false);assert.match(await preview.innerText(),/20\.12\.2025/);}
   await preview.getByLabel('Ich bestätige genau diesen geprüften Anspruchsbaustein und seine Originale.',{exact:true}).check();await preview.getByRole('button',{name:'Geprüften Anspruchsbaustein festhalten',exact:true}).click();await modal(sicknessLabel).waitFor();
   const accepted=records.filter(v=>v.body&&v.path.endsWith('/entitlements')).at(-1);assert.equal(accepted.status,200);assert.deepEqual(accepted.value.plan,checked.value.plan);assert.deepEqual(accepted.value.details.input,checked.body.details.input);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,preemployment?'payroll-sickness-start-v4-mobile.png':'payroll-sickness-phases-v3-mobile.png'),fullPage:false});
  }
  console.log('payroll entitlements: actual MFA/HTTP, empty typed fields, exact personnel sources, explicit unpaid facts, checked statutory deadline, original download, exact lost-ACK replay, historical void and mobile390 passed');
  console.log('payroll sickness: actual v3 overlapping causes and v4 preemployment onset created through typed forms, explicit evidence/recovery, exact checked phases accepted and mobile390 passed');
 }finally{await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-entitlements-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollEntitlementsFlow};
