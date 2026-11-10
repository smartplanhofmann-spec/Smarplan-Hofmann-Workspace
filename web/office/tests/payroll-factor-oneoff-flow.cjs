/* Real MFA/HTTP originals; only two successful responses are deliberately lost. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const original=require('../../../app/test/fixtures/payroll_factor_claims.json');
const uid=()=>crypto.randomUUID().replaceAll('-',''),request=value=>({request_id:uid(),...value});
const ref=value=>({id:value.id,revision:value.revision,content_hash:value.content_hash});
async function payrollFactorOneoffFlow({page,context,navigate,ready,login,fixture,screenshots}){
 const tokens=new Map(),records=[];let loseCase=true,loseRun=true;
 page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)tokens.set(page,r.headers().authorization);});
 const modal=name=>page.getByRole('dialog',{name,exact:true});
 const close=async()=>{if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();};
 async function api(p,suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:tokens.get(p),Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 async function openPayroll(){await close();await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();await modal('Lohnberechnung 2026 · Synthetic technician').waitFor();}
 async function openCases(){await openPayroll();await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'Faktor-Einmalbezugsfälle öffnen',exact:true}).click();const choose=modal('Einmalbezugsmonat auswählen');await choose.getByLabel('Tatsächlicher Zuflussmonat (JJJJ-MM)',{exact:true}).fill('2026-10');await choose.getByRole('button',{name:'Belegte Einmalbezugsquellen öffnen',exact:true}).click();await modal('Faktor-Einmalbezugsfälle · 2026-10 · Synthetic technician').waitFor();}
 async function retry(){await close();await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);}
 const pattern='**/api/v1/business/payroll/**';
 await context.route(pattern,async route=>{
  const req=route.request(),response=await route.fetch({maxRedirects:0});if(!response.headers()['content-type']?.includes('application/json'))return route.fulfill({response});
  const value=await response.json(),body=req.method()==='POST'?req.postDataJSON():null,url=new URL(req.url());
  records.push({path:url.pathname,body,status:response.status(),value});
  if(response.ok()&&body&&url.pathname.endsWith('/one-off-cases/factor-v15')&&loseCase){loseCase=false;return route.abort('failed');}
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

  const common={employee_id:employee.id,employee_revision:employee.revision,source_file_ids:[payrollFile.id]},originalRef={id:payrollFile.id,revision:1,content_hash:payrollFile.content_hash};
  const proposal={...common,kind:'calculation_case',rule_version:'de_2026_factor_claims_month_v12',source_contract_version:4,details:{month:'2026-10',period_case_ref:ref(period),employment_terms_refs:[ref(terms)],profile_refs:[ref(profile)],identity_refs:[ref(identity)],segment_events:[],thirty_day_rule:null,entitlement_case_refs:[ref(claim)],travel_settlement_refs:[],flat_tax_decision:null,verification_note:'Actual synthetic original factor and full P4 review'}};
  const cp=await api(page,'/payroll/calculation-cases/preview',proposal),running=await api(page,'/payroll/calculation-cases',request({...proposal,revision:0,status:'active',confirmed:true,preview_hash:cp.preview_hash}));
  const annual=async(kind,details,factorMode)=>{const base='/payroll/annual-facts'+(factorMode?'/factor-v2':''),body={...common,kind,details:{employer_identity_ref:ref(identity),verification_note:'Actual synthetic annual originals reviewed',...details}},p=await api(page,base+'/preview',body);return api(page,base,request({...body,revision:0,status:'active',confirmed:true,preview_hash:p.preview_hash}));};
  const basis=await annual('annual_basis',{year:2026,coverage_to:'2026-10-31',as_of_date:'2026-10-31',payroll_run_refs:[],payroll_payment_refs:[],imported_period_refs:[],imported_one_off_refs:[],current_calculation_case_ref:ref(running),gaps:[{start:'2026-01-01',end:'2026-09-30',reason:'not_employed',evidence_ref:originalRef}],completeness_confirmed:true},true);
  const earning=await annual('one_off_earning',{claim_key:originalRef,claim_reference:'Actual synthetic separate bonus position1',planned_receipt_date:'2026-10-31',amount_minor:50000,tax_classification:'other_payment',social_classification:'one_off_remuneration',section_key:'regular',employment_terms_refs:[ref(terms)],claim_periods:[{start:'2026-10-15',end:'2026-10-31',evidence_ref:originalRef}],document_refs:[originalRef]},false);
  const forecast=await annual('annual_tax_forecast',{annual_basis_ref:ref(basis),receipt_date:'2026-10-31',identity_ref:ref(identity),current_one_off_ref:ref(earning),previous_employers:[{employer_name:'Actual synthetic earlier employer',employer_tax_number:'111/222/33333',start:'2026-01-01',end:'2026-09-30',running_taxable_minor:12000000,other_paid_minor:0,evidence_ref:originalRef}],no_previous_employer_ref:null,other_tax_receipt_refs:[],remaining_periods:['2026-11','2026-12'].map(month=>({month,employment_terms_ref:ref(terms),agreement_refs:[ref(agreement)],work_schedule_ref:null}))},true);
  await openPayroll();await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'Faktor-Jahresbasis und Steuerprognose öffnen',exact:true}).click();
  await modal('Faktor-Jahresbasis und Steuerprognose · Synthetic technician').waitFor();assert.equal(await page.getByRole('button',{name:'Belegte externe Lohnperiode erfassen',exact:true}).count(),0);
  await openCases();await page.getByRole('button',{name:'Einmalbezugsfall aus Originalen erfassen',exact:true}).click();const edit=modal('Einmalbezugsfall erfassen · 2026-10');
  for(const [label,value]of [['Unveränderter laufender Gesamtfall dieses Monats',running.id],['Konkreter geplanter Einmalanspruch mit Zufluss in diesem Monat',earning.id],['Vollständige aktuelle Jahresbasis mit genau diesem laufenden Gesamtfall',basis.id],['Jahressteuergrundlage ohne den aktuellen Einmalanspruch',forecast.id],['Geschützte Originale für diesen Einmalbezugsfall',payrollFile.id]])await edit.getByLabel(label,{exact:true}).selectOption(value);
  await edit.getByLabel('Nachvollziehbarer Einmalbezugs-Prüfvermerk',{exact:true}).fill('Actual synthetic original factor, P4 and bonus annual evidence');await edit.getByRole('button',{name:'Einmalbezugsfall unverbindlich prüfen',exact:true}).click();
  const preview=modal('Einmalbezug prüfen · 2026-10');await preview.waitFor();await preview.getByRole('checkbox').check();await preview.getByRole('button',{name:'Geprüften Einmalbezugsfall festhalten',exact:true}).click();await preview.getByRole('alert').waitFor();await retry();
  await openCases();await page.getByRole('button',{name:'Einmalbezugsfall öffnen',exact:true}).click();await modal('Einmalbezugsfall · 2026-10').getByRole('button',{name:'Diesen Einmalbezugsfall im Lohnlauf verwenden',exact:true}).click();
  const confirm=modal('Geprüften Berechnungsumfang festhalten');await confirm.waitFor();assert.match(await confirm.innerText(),/Faktor-Monat mit belegtem Einmalbezug/);
  await confirm.getByRole('checkbox').check();await confirm.getByRole('button',{name:'Geprüften Berechnungsumfang festhalten',exact:true}).click();await confirm.getByRole('alert').waitFor();await retry();
  const cases=records.filter(r=>r.body&&r.path.endsWith('/one-off-cases/factor-v15')),runs=records.filter(r=>r.body&&r.path.endsWith('/runs'));
  assert.equal(cases.length,2);assert.deepEqual(cases[0].body,cases[1].body);assert.deepEqual(cases[0].value,cases[1].value);assert.equal(runs.length,2);assert.deepEqual(runs[0].body,runs[1].body);assert.deepEqual(runs[0].value,runs[1].value);
  const run=runs[0].value;assert.equal(run.calculation.scope,'regular_standard_factor_claims_oneoff');assert.ok(run.calculation.one_off_details.tax.STS>0);assert.ok(run.calculation.one_off_details.tax.SOLZS>0);assert.deepEqual(run.source.calculation_case,running);
  await openPayroll();const pending=page.waitForEvent('download');await modal('Lohnberechnung 2026 · Synthetic technician').getByRole('button',{name:'PDF · Fassung 1',exact:true}).click();assert.equal(crypto.createHash('sha256').update(await fs.readFile(await(await pending).path())).digest('hex'),run.pdf_sha256);
  await openCases();await page.getByRole('button',{name:'Einmalbezugsfall öffnen',exact:true}).click();await modal('Einmalbezugsfall · 2026-10').waitFor();assert.match(await modal('Einmalbezugsfall · 2026-10').innerText(),/Belegter ELStAM-Faktor: 0\.753/);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(screenshots,'payroll-factor-oneoff-mobile.png'),fullPage:false});
  const own=await api(page,'/payroll/employee-statements?employee_id='+employee.id);assert.equal(own.items[0].schema_version,5);for(const value of [cases[0].value.id,basis.id,forecast.id,earning.id,payrollFile.id])assert.equal(JSON.stringify(own).includes(value),false);
  await require('./payroll-oneoff-own-flow.cjs').payrollOneOffOwnFlow({page,context,navigate,ready,login,fixture,screenshots},employee,run);
  console.log('factor bonus: real MFA/HTTP factor/P4/V2 originals, explicit annual and oneoff UI, exact two lost-ACK receipts, positive STS/SOLZS, frozen monthly source, original PDF, narrow schema5 employee DTO and390px passed');
 }finally{await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-factor-oneoff-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollFactorOneoffFlow};
