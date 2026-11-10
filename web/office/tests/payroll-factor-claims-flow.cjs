/* Genuine MFA/HTTP, original full factor month and independently evidenced unpaid claim. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const original=require('../../../app/test/fixtures/payroll_factor_claims.json');
const uid=()=>crypto.randomUUID().replaceAll('-',''),request=value=>({request_id:uid(),...value});
const ref=value=>({id:value.id,revision:value.revision,content_hash:value.content_hash});

async function payrollFactorClaimsFlow({page,context,navigate,ready,login,fixture,screenshots}){
 const tokens=new Map(),records=[];let technician,loseCase=true,loseRun=true;
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
  const payrollFile=await file('synthetic-factor-claims-employment.pdf');
  const agreement=await api(page,'/personnel/agreements',request({employee_id:employee.id,revision:0,effective_from:'2026-01-01',employment_kind:'regular',pay_basis:'monthly',amount_minor:500000,currency:'EUR',reference_file_id:payrollFile.id,notes:'Synthetic full-month factor employment'}));
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

  const claimBody={employee_id:employee.id,employee_revision:employee.revision,kind:'unpaid_continuation',source_file_ids:[payrollFile.id],details:{case_key:uid(),employment_terms_ref:ref(terms),work_schedule_refs:[],preparation_refs:[],agreement_refs:[ref(agreement)],sickness_history_ref:null,input:{from:'2026-10-20',to:'2026-10-24',employment_to:null,employment_continues:true,no_wage_claim:true,intervening_paid_days:[],evidence_refs:[{id:payrollFile.id,revision:1,content_hash:payrollFile.content_hash}],exceptions:[]},verification_note:'Synthetic separately evidenced five unpaid days'}};
  const claimPreview=await api(page,'/payroll/entitlements/preview',claimBody);
  const claim=await api(page,'/payroll/entitlements',request({...claimBody,revision:0,status:'active',confirmed:true,preview_hash:claimPreview.preview_hash}));
  const beforeTimes=await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31');
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Faktor-Monat mit belegten Lohnansprüchen',exact:true}).click();
  const edit=modal('Erfassen: Faktor-Monat mit belegten Lohnansprüchen · 2026-10');await edit.waitFor();
  for(const [label,value]of [['Bestätigter Lohnmonat mit Faktor',period.id],['Sämtliche tatsächlichen Beschäftigungsepisoden',terms.id],['Sämtliche einschlägigen Lohnprofilfassungen',profile.id],['Identitäts- und Steuermerkmalsnachweise',identity.id],['Geschützte Originale für den Gesamtfall',payrollFile.id],['Alle aktiven Anspruchsnachweise im Monat',claim.id]])await edit.getByLabel(label,{exact:true}).selectOption(value);
  assert.equal(await edit.getByLabel('Betriebliche Reise-Pauschalsteuerentscheidung',{exact:true}).count(),0);
  assert.equal(await edit.getByLabel('Tatsächliche bestätigte Reiseabrechnungen',{exact:true}).count(),0);
  await edit.getByLabel('Nachvollziehbarer Gesamtfallprüfvermerk',{exact:true}).fill('Synthetic original factor and all actual P4 claims verified');
  await edit.getByRole('button',{name:'Konkrete Ereignisse und Steuerbelege erfassen',exact:true}).click();
  const typed=modal('Konkrete Gesamtfallangaben · 2026-10');await typed.getByRole('checkbox').check();await typed.getByRole('button',{name:'Gesamtplan unverbindlich prüfen',exact:true}).click();
  const preview=modal('Gesamtplan prüfen · 2026-10');await preview.waitFor();assert.match(await preview.innerText(),/0,753|0\.753/);assert.match(await preview.innerText(),/4.193,55/);
  await preview.getByRole('checkbox').check();await preview.getByRole('button',{name:'Geprüften Gesamtfall festhalten',exact:true}).click();await preview.getByRole('alert').waitFor();await retry();
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Gesamtfall öffnen',exact:true}).click();
  await modal('Gesamtfall · 2026-10').getByRole('button',{name:'Lohn aus diesem Gesamtfall berechnen',exact:true}).click();
  const confirm=modal('Geprüften Berechnungsumfang festhalten');await confirm.waitFor();assert.match(await confirm.innerText(),/Faktor-Monat mit belegten Lohnansprüchen/);
  await confirm.getByRole('checkbox').check();await confirm.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await confirm.getByRole('alert').waitFor();await retry();
  const cases=records.filter(r=>r.body&&r.path.endsWith('/calculation-cases')),runs=records.filter(r=>r.body&&r.path.endsWith('/runs'));
  assert.equal(cases.length,2);assert.deepEqual(cases[0].body,cases[1].body);assert.deepEqual(cases[0].value,cases[1].value);
  assert.equal(runs.length,2);assert.deepEqual(runs[0].body,runs[1].body);assert.deepEqual(runs[0].value,runs[1].value);
  const run=runs[0].value;assert.equal(run.calculation.scope,'regular_standard_factor_claims_month');assert.equal(run.source.source_schema_version,3);
  assert.equal(run.calculation.gross_minor,419355);assert.equal(run.calculation.individual_wage_tax_minor,43091);assert.equal(run.calculation.employee_contributions.care,10064);assert.equal(run.calculation.net_minor,285054);
  assert.equal(basePreview.calculation.gross_minor,500000);
  assert.deepEqual(await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31'),beforeTimes);
  await openPayroll();const pdf=page.waitForEvent('download');await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await pdf).path())).digest('hex'),run.pdf_sha256);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'payroll-factor-claims-mobile.png'),fullPage:false});
  const own=await api(page,'/payroll/employee-statements?employee_id='+employee.id);assert.equal(own.items[0].calculation.payout_minor,285054);assert.equal(own.items[0].sources,undefined);assert.equal(JSON.stringify(own).includes(claim.id),false);
  console.log('factor claims: actual MFA/HTTP original factor and unpaid claim, XML tax and separately rounded PV, explicit source choice, exact two lost-ACK retries, unchanged project times, private statement/PDF and390px passed');
 }finally{await technician?.close();await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-factor-claims-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollFactorClaimsFlow};
