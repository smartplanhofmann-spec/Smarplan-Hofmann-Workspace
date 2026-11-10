/* Genuine MFA/HTTP, original factor/P4 month and genuinely paid tax-free travel. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const original=require('../../../app/test/fixtures/payroll_factor_claims.json');
const uid=()=>crypto.randomUUID().replaceAll('-',''),request=value=>({request_id:uid(),...value});
const ref=value=>({id:value.id,revision:value.revision,content_hash:value.content_hash});

async function payrollFactorClaimTravelFlow({page,context,navigate,ready,login,fixture,screenshots}){
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
  const payrollFile=await file('synthetic-factor-claims-paid-travel-employment.pdf'),tripFile=await file('synthetic-factor-claims-paid-travel-trip.pdf','expense_receipt'),paymentFile=await file('synthetic-factor-claims-paid-travel-bank.pdf');
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
  const bank=await api(page,'/accounting/accounts',request({confirmation:true,code:'1200',name:'Synthetic factor-travel actual bank',kind:'bank'}));
  const currentProfile=await api(page,'/accounting/profile'),accountingBody={expected_revision:currentProfile.revision,state_hash:currentProfile.state_hash,reason:'Synthetic actual paid-travel account',evidence_reference:'Synthetic owner verification',profile:{legal_form:'sole_proprietorship',accounting_method:'euer',vat_regime:'regular',vat_timing:'cash',vat_effective_from:'2026-01-01',bookkeeping_start:'2026-01-01'}};
  const accountingPreview=await api(page,'/accounting/profile/preview',accountingBody);await api(page,'/accounting/profile/confirm',request({...accountingBody,confirmation:true,preview_hash:accountingPreview.preview_hash}));
  technician=await context.newPage();capture(technician);await technician.goto(fixture.base_url+'/office/');await login(technician,'technician@browser.example.test');await navigate(technician,'Personal');
  const sites={};for(const kind of ['home','external_fixed'])sites[kind]=(await api(technician,'/personnel/travel/sites',request({employee_id:employee.id,id:uid(),revision:0,status:'active',correction_reason:'',details:{kind,name:'Synthetic factor-travel '+kind,address:'Synthetic actual site',rate_id:'de_2026',timezone:'Europe/Berlin',effective_from:'2026-01-01',effective_to:null,assignment_basis:'Synthetic complete site evidence',regular_days_per_week:2,history_complete_from:'2025-09-01',prior_visit_dates:[],source_file_ids:[tripFile.id]}}))).result;
  const start='2026-10-26T08:00:00+01:00',end='2026-10-26T18:00:00+01:00';
  const trip=(await api(technician,'/personnel/travel/trips',request({employee_id:employee.id,id:uid(),revision:0,correction_reason:'',details:{purpose:'Synthetic actual factor-month trip',project_id:fixture.project_id,departed_at:start,returned_at:end,timezone:'Europe/Berlin',source_file_ids:[tripFile.id],home_site_ref:ref(sites.home),first_workplace_ref:null,segments:[{id:uid(),from:start,to:end,site_ref:ref(sites.external_fixed),activity:'work',transport:'ground',necessary_stopover:false}],overnights:[],meals:[],expense_refs:[],requested_meal_minor:1400,requested_lodging_minor:0,tax_choice:'tax_free_only',private_intervals:[]}}))).result;
  const submitSource=await api(technician,'/personnel/travel/sources?employee_id='+employee.id);
  const submitted=(await api(technician,'/personnel/travel/trips/'+trip.id+'/submit',request({employee_id:employee.id,revision:trip.revision,source_hash:submitSource.source_hash,confirmed:true}))).result;
  const travelBody={employee_id:employee.id,trip_refs:[ref(submitted)],period_from:'2026-10-26',period_to:'2026-10-26',settlement_unit:'trip',tax_choice:'tax_free_only',requested_meal_minor:1400,requested_lodging_minor:0,correction_of:null,review_note:'Synthetic independent full travel-source review'};
  const travelPreview=await api(page,'/personnel/travel/settlements/preview',travelBody);
  const settlement=(await api(page,'/personnel/travel/settlements',request({...travelBody,id:uid(),revision:0,source_hash:travelPreview.source_hash,preview_hash:travelPreview.preview_hash,confirmed:true}))).result;
  const paymentSource=await api(page,'/personnel/travel/sources?employee_id='+employee.id);
  const payment=(await api(page,'/personnel/travel/payments',request({employee_id:employee.id,id:uid(),revision:0,action:'record',settlement_ref:ref(settlement),instance_id:paymentSource.instance_id,account_id:bank.id,account_revision:bank.revision,kind:'reimbursement',paid_on:'2026-10-27',amount_minor:1400,reference:'SYN-FACTOR-TRAVEL-PAID',reference_file_id:paymentFile.id,source_hash:paymentSource.source_hash,correction_reason:'',confirmed:true}))).result;
  const paymentBefore=JSON.stringify((await api(page,'/personnel/travel/payments/'+payment.id)).item);

  const beforeTimes=await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31');
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Faktor-Monat mit Ansprüchen und bezahlten Reisen',exact:true}).click();
  const edit=modal('Erfassen: Faktor-Monat mit Ansprüchen und bezahlten Reisen · 2026-10');await edit.waitFor();
  for(const [label,value]of [['Bestätigter Lohnmonat mit Faktor',period.id],['Sämtliche tatsächlichen Beschäftigungsepisoden',terms.id],['Sämtliche einschlägigen Lohnprofilfassungen',profile.id],['Identitäts- und Steuermerkmalsnachweise',identity.id],['Geschützte Originale für den Gesamtfall',payrollFile.id],['Alle aktiven Anspruchsnachweise im Monat',claim.id],['Tatsächliche bestätigte Reiseabrechnungen',settlement.id],['Sämtliche belegten Reisezahlungen einschließlich Korrekturen',payment.id]])await edit.getByLabel(label,{exact:true}).selectOption(value);
  assert.equal(await edit.getByLabel('Betriebliche Reise-Pauschalsteuerentscheidung',{exact:true}).count(),0);
  assert.equal(await edit.getByLabel('Sämtliche belegten Reisezahlungen einschließlich Korrekturen',{exact:true}).count(),1);
  await edit.getByLabel('Nachvollziehbarer Gesamtfallprüfvermerk',{exact:true}).fill('Synthetic original factor and all actual P4 claims verified');
  await edit.getByRole('button',{name:'Konkrete Ereignisse und Steuerbelege erfassen',exact:true}).click();
  const typed=modal('Konkrete Gesamtfallangaben · 2026-10');await typed.getByRole('checkbox').check();await typed.getByRole('button',{name:'Gesamtplan unverbindlich prüfen',exact:true}).click();
  const preview=modal('Gesamtplan prüfen · 2026-10');await preview.waitFor();assert.match(await preview.innerText(),/0,753|0\.753/);assert.match(await preview.innerText(),/4.193,55/);assert.match(await preview.innerText(),/14,00/);
  await preview.getByRole('checkbox').check();await preview.getByRole('button',{name:'Geprüften Gesamtfall festhalten',exact:true}).click();await preview.getByRole('alert').waitFor();await retry();
  await openCases();await modal('Abrechnungsfälle · Synthetic technician · 2026-10').getByRole('button',{name:'Gesamtfall öffnen',exact:true}).click();
  await modal('Gesamtfall · 2026-10').getByRole('button',{name:'Lohn aus diesem Gesamtfall berechnen',exact:true}).click();
  const confirm=modal('Geprüften Berechnungsumfang festhalten');await confirm.waitFor();assert.match(await confirm.innerText(),/Faktor-Monat mit Ansprüchen und bereits bezahlten Reisen/);
  await confirm.getByRole('checkbox').check();await confirm.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await confirm.getByRole('alert').waitFor();await retry();
  const cases=records.filter(r=>r.body&&r.path.endsWith('/calculation-cases')),runs=records.filter(r=>r.body&&r.path.endsWith('/runs'));
  assert.equal(cases.length,2);assert.deepEqual(cases[0].body,cases[1].body);assert.deepEqual(cases[0].value,cases[1].value);
  assert.equal(runs.length,2);assert.deepEqual(runs[0].body,runs[1].body);assert.deepEqual(runs[0].value,runs[1].value);
  const run=runs[0].value;assert.equal(run.calculation.scope,'regular_standard_factor_claims_paid_travel_month');assert.equal(run.source.source_schema_version,3);
  assert.equal(run.calculation.gross_minor,419355);assert.equal(run.calculation.individual_wage_tax_minor,43091);assert.equal(run.calculation.employee_contributions.care,10064);assert.equal(run.calculation.net_minor,285054);
  assert.equal(basePreview.calculation.gross_minor,500000);
  assert.equal(run.calculation.period_details.travel_paid_minor,1400);assert.equal(run.calculation.payout_minor,285054);
  assert.equal(JSON.stringify((await api(page,'/personnel/travel/payments/'+payment.id)).item),paymentBefore);
  assert.equal((await api(page,'/personnel/travel/payments?employee_id='+employee.id)).items.filter(p=>p.id===payment.id).length,1);
  assert.deepEqual(await api(page,'/time/summary?employee_id='+employee.id+'&from=2026-10-01&to=2026-10-31'),beforeTimes);
  await openPayroll();const pdf=page.waitForEvent('download');await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await pdf).path())).digest('hex'),run.pdf_sha256);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'payroll-factor-claims-paid-travel-mobile.png'),fullPage:false});
  const own=await api(page,'/payroll/employee-statements?employee_id='+employee.id);assert.equal(own.items[0].calculation.payout_minor,285054);assert.equal(own.items[0].sources,undefined);assert.equal(JSON.stringify(own).includes(claim.id),false);
  console.log('factor claims paid travel: actual MFA/HTTP original factor and unpaid claim, XML tax and separately rounded PV, explicit source choice, exact two lost-ACK retries, unchanged project times and genuine separate travel payment, private statement/PDF and390px passed');
 }finally{await technician?.close();await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-factor-claims-paid-travel-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollFactorClaimTravelFlow};
