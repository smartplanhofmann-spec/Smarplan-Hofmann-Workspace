/* Genuine MFA/HTTP, original full factor month and separate Midijob prognosis. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const original=require('../../../app/test/fixtures/payroll_factor_transition.json');
const uid=()=>crypto.randomUUID().replaceAll('-',''),request=value=>({request_id:uid(),...value});
const ref=value=>({id:value.id,revision:value.revision,content_hash:value.content_hash});

async function payrollFactorTransitionFlow({page,context,navigate,ready,login,fixture,screenshots}){
 const tokens=new Map(),records=[];let technician,technicianContext,loseCase=true,loseRun=true;
 const capture=p=>p.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)tokens.set(p,r.headers().authorization);});capture(page);
 const modal=name=>page.getByRole('dialog',{name,exact:true});
 const close=async()=>{if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();};
 async function api(p,suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:tokens.get(p),Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 async function openPayroll(){await close();await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();await modal('Lohnberechnung 2026 · Synthetic technician').waitFor();}
 async function openCases(){await openPayroll();await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'Abrechnungsfälle mit Ansprüchen und Reisen',exact:true}).click();await modal('Gesamtfallmonat wählen').getByLabel('Belegter Abrechnungsmonat (JJJJ-MM)',{exact:true}).fill('2026-10');await modal('Gesamtfallmonat wählen').getByRole('button',{name:'Gesamtfallquellen öffnen',exact:true}).click();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').waitFor();}
 async function retry(){await close();await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);}
 const pattern='**/api/v1/business/payroll/**';
 await context.route(pattern,async route=>{
  const req=route.request(),response=await route.fetch({maxRedirects:0});
  if(!response.headers()['content-type']?.includes('application/json'))return route.fulfill({response});
  const value=await response.json(),body=req.method()==='POST'?req.postDataJSON():null,url=new URL(req.url());records.push({path:url.pathname,body,status:response.status(),value});
  if(response.ok()&&body&&url.pathname.endsWith('/calculation-cases')&&loseCase){loseCase=false;return route.abort('failed');}
  if(response.ok()&&body&&url.pathname.endsWith('/runs')&&loseRun){loseRun=false;return route.abort('failed');}
  return route.fulfill({response});
 });
 try{
  await navigate(page,'Personal');await page.getByLabel('Mitarbeiter',{exact:true}).selectOption({label:'Synthetic technician'});await ready(page);
  const employees=await api(page,'/employees');let employee=(employees.items||employees).find(e=>e.name==='Synthetic technician');
  employee=await api(page,'/employees',request({id:employee.id,revision:employee.revision,employment_from:'2026-10-01',employment_to:null}));
  async function file(name,purpose='personnel'){return api(page,'/personnel/files',request({employee_id:employee.id,purpose,owner_visible:purpose==='expense_receipt',filename:name,media_type:'application/pdf',content_base64:Buffer.from('%PDF-1.4\nSynthetic verified '+name+'\n%%EOF').toString('base64')}));}
  const payrollFile=await file('synthetic-factor-midijob-employment.pdf');
  const agreement=await api(page,'/personnel/agreements',request({employee_id:employee.id,revision:0,effective_from:'2026-01-01',employment_kind:'regular',pay_basis:'monthly',amount_minor:200000,currency:'EUR',reference_file_id:payrollFile.id,notes:'Synthetic full-month factor employment'}));
  const profile=await api(page,'/payroll/profiles',request({employee_id:employee.id,revision:0,profile:original.case.sources.profiles[0].profile,source_file_id:payrollFile.id,confirmed:true}));
  const identity=await api(page,'/payroll/account-records',request({employee_id:employee.id,kind:'identity',revision:0,source_file_id:payrollFile.id,confirmed:true,details:{...original.case.sources.identities[0].details,profile_id:profile.id,profile_revision:profile.revision}}));
  const hr=await api(page,'/personnel/payroll-preparations/preview?employee_id='+employee.id+'&month=2026-10');
  const prep=await api(page,'/personnel/payroll-preparations',request({employee_id:employee.id,revision:0,month:'2026-10',source_hash:hr.source_hash,completeness_confirmed:true}));
  const terms=await api(page,'/payroll/facts',request({employee_id:employee.id,employee_revision:employee.revision,kind:'employment_terms',revision:0,status:'active',confirmed:true,source_file_ids:[payrollFile.id],details:{employment_from:'2026-10-01',employment_to:null,proration_method:'calendar_days_actual',agreement_refs:[ref(agreement)],reason:'Synthetic complete full-month contract'}}));
  const periodBody={employee_id:employee.id,employee_revision:employee.revision,kind:'period_case',source_file_ids:[payrollFile.id],details:{month:'2026-10',preparation_ref:ref(prep),employment_terms_ref:ref(terms),work_schedule_ref:null,profile_refs:[ref(profile)],identity_refs:[ref(identity)],tax_treatment:'domestic_running_wages',entitlement_decisions:[],verification_note:'Synthetic full-month factor sources verified'}};
  const periodPreview=await api(page,'/payroll/periods/preview',Object.fromEntries(Object.entries(periodBody).filter(([k])=>k!=='kind')));
  const period=await api(page,'/payroll/facts',request({...periodBody,revision:0,status:'active',confirmed:true,preview_hash:periodPreview.preview_hash}));
  assert.equal(period.plan.rule_version,'de_2026_standard_factor_period_v9');
  const basePreview=await api(page,'/payroll/preview',{source_schema_version:2,employee_id:employee.id,period_case_ref:ref(period)});

  assert.equal(basePreview.calculation.payroll_calculation_complete,false);
  const beforeTimes=await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31');
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Midijob mit belegtem ELStAM-Faktor',exact:true}).click();
  const edit=modal('Erfassen: Midijob mit ELStAM-Faktor · 2026-10');await edit.waitFor();
  for(const [label,value]of [['Bestätigter vollständiger Faktor-Monat',period.id],['Eine belegte Beschäftigung',terms.id],['Ein ursprüngliches ELStAM-Faktorprofil',profile.id],['Ein passender Identitäts- und ELStAM-Nachweis',identity.id],['Konkretes privates Prognoseoriginal',payrollFile.id],['Gebundene private Originale',payrollFile.id]])await edit.getByLabel(label,{exact:true}).selectOption(value);
  for(const [label,value]of [['Prognose gültig ab','2026-10-01'],['Prognose gültig bis','2026-10-31'],['Tatsächlicher Tag der Prüfung','2026-10-01'],['Tag der ursprünglichen Statusprognose','2026-01-01'],['Belegter fester regelmäßiger Monatslohn in EUR','2000.00'],['Belegter Prognosezeitraum in Monaten','12'],['Belegte Grundlage der Zwölfmonatsprognose','Synthetic original twelve-month fixed pay prognosis'],['Ergebnis der personenbezogenen Prüfung','Synthetic actual sole employment and fixed monthly pay verified'],['Prüfvermerk zum gesamten Abrechnungsfall','Synthetic unchanged factor profile and separate full prognosis']])await edit.getByLabel(label,{exact:true}).fill(value);
  for(const name of ['Alleinige Beschäftigung und tatsächlichen Übergangsbereich geprüft','Unveränderten festen Monatslohn für diesen vollständigen Monat geprüft','Keine vorhersehbaren Einmalbezüge in dieser Prognose'])await edit.getByLabel(name,{exact:true}).check();
  await edit.getByRole('button',{name:'Faktor-Midijob unverbindlich prüfen',exact:true}).click();
  const preview=modal('Gesamtplan prüfen · 2026-10');await preview.waitFor();assert.match(await preview.innerText(),/0,753|0\.753/);assert.match(await preview.innerText(),/1.498,67/);
  await preview.getByRole('checkbox').check();await preview.getByRole('button',{name:'Geprüften Gesamtfall festhalten',exact:true}).click();await preview.getByRole('alert').waitFor();await retry();
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Gesamtfall öffnen',exact:true}).click();
  await modal('Gesamtfall · 2026-10').getByRole('button',{name:'Lohn aus diesem Gesamtfall berechnen',exact:true}).click();
  const confirm=modal('Geprüften Berechnungsumfang festhalten');await confirm.waitFor();assert.match(await confirm.innerText(),/Belegter Midijob mit ELStAM-Faktor/);
  await confirm.getByRole('checkbox').check();await confirm.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await confirm.getByRole('alert').waitFor();await retry();
  const cases=records.filter(r=>r.body&&r.path.endsWith('/calculation-cases')),runs=records.filter(r=>r.body&&r.path.endsWith('/runs'));
  assert.equal(cases.length,2);assert.deepEqual(cases[0].body,cases[1].body);assert.deepEqual(cases[0].value,cases[1].value);
  assert.equal(runs.length,2);assert.deepEqual(runs[0].body,runs[1].body);assert.deepEqual(runs[0].value,runs[1].value);
  const run=runs[0].value;assert.equal(run.calculation.scope,'regular_transition_factor_month');assert.equal(run.source.source_schema_version,3);
  assert.equal(run.calculation.gross_minor,200000);assert.equal(run.calculation.individual_wage_tax_minor,6633);assert.equal(run.calculation.net_minor,149867);
  assert.deepEqual(run.source.profile,profile);assert.equal(run.source.profile.profile.transition_assessment,undefined);
  assert.deepEqual(await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31'),beforeTimes);
  await openPayroll();const pdf=page.waitForEvent('download');await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await pdf).path())).digest('hex'),run.pdf_sha256);

  technicianContext=await context.browser().newContext();technician=await technicianContext.newPage();capture(technician);
  const ownPaths=[];technician.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url)ownPaths.push(new URL(r.url()).pathname);});
  await technician.goto(fixture.base_url+'/office/');await login(technician,'technician@browser.example.test');await navigate(technician,'Personal');
  await technician.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();ownPaths.length=0;
  await technician.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();
  const ownList=technician.getByRole('dialog',{name:'Meine Lohnnachweise · Synthetic technician',exact:true});await ownList.getByRole('button',{name:'Lohnnachweis ansehen',exact:true}).click();
  const ownDetail=technician.getByRole('dialog',{name:'Mitarbeiter-Lohnnachweis · 2026-10',exact:true});await ownDetail.waitFor();assert.match(await ownDetail.innerText(),/1.498,67/);
  assert.equal(ownPaths.some(p=>/\/payroll\/(runs|profiles|facts)(\/|$)/.test(p)),false);
  const own=(await api(technician,'/payroll/employee-statements/'+run.id)).statement;assert.equal(own.calculation.net_minor,149867);
  for(const key of ['profile','tax_identifier','source_file_ids','verification_note','factor_transition_assessment'])assert.equal(JSON.stringify(own).includes('"'+key+'":'),false);
  assert.equal(JSON.stringify(own).includes(payrollFile.id),false);
  const ownPdf=technician.waitForEvent('download');await ownDetail.getByRole('button',{name:'Eigenen PDF-Lohnnachweis herunterladen',exact:true}).click();
  assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await ownPdf).path())).digest('hex'),own.pdf_sha256);
  const ownJson=technician.waitForEvent('download');await ownDetail.getByRole('button',{name:'Eigenen JSON-Lohnnachweis herunterladen',exact:true}).click();
  assert.deepEqual(JSON.parse(await fs.readFile(await(await ownJson).path(),'utf8')),own);
  for(const suffix of ['/payroll/runs/'+run.id,'/payroll/facts/sources?employee_id='+employee.id]){
    const denied=await technicianContext.request.get(fixture.base_url+'/api/v1/business'+suffix,{headers:{Authorization:tokens.get(technician),Origin:fixture.base_url}});assert.equal(denied.status(),403);
  }
  await technician.setViewportSize({width:390,height:844});assert.equal(await technician.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await technician.screenshot({path:path.join(screenshots,'payroll-factor-transition-own-mobile.png'),fullPage:false});
  await api(page,'/settings/permissions',request({user_id:employee.user_id,permission:'time.own',scope:'*',effect:'deny',revision:0}));
  await ownDetail.getByRole('button',{name:'Eigenen PDF-Lohnnachweis herunterladen',exact:true}).click();await ownDetail.getByRole('alert').waitFor();assert.equal(await ownDetail.getByText('Netto',{exact:true}).count(),0);
  console.log('factor Midijob: actual MFA/HTTP, unchanged original factor, separate full prognosis, two exact lost-ACK retries, unchanged project times, private PDF, real employee own DTO/PDF/JSON, no private routes, fresh revocation clearing and390px passed');
 }finally{await technicianContext?.close();await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-factor-transition-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollFactorTransitionFlow};
