/* Actual MFA/HTTP, explicit RV originals, lost answer and profile binding. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const sample=require('../../../app/test/fixtures/payroll_rv_lifecycle.json').cases.at(-1);
const request=value=>({request_id:crypto.randomUUID().replaceAll('-',''),...value});
async function payrollRvLifecycleFlow({page,context,navigate,ready,login,fixture,screenshots}){
 let authorization,technicianContext,lose=true;const records=[];
 page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)authorization=r.headers().authorization;});
 const modal=name=>page.getByRole('dialog',{name,exact:true});
 const close=async()=>{if(await page.getByRole('dialog').count())await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();};
 async function api(suffix,body){const response=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:authorization,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(response.ok(),suffix+' '+await response.text());return response.json();}
 async function payroll(){await close();await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();await modal('Lohnberechnung 2026 · Synthetic technician').waitFor();}
 const pattern='**/api/v1/business/payroll/rv-lifecycle';
 await context.route(pattern,async route=>{const req=route.request(),response=await route.fetch({maxRedirects:0});if(req.method()==='POST'){records.push({body:req.postDataJSON(),status:response.status(),value:await response.json()});if(response.ok()&&lose){lose=false;return route.abort('failed');}}return route.fulfill({response});});
 try{
  await navigate(page,'Personal');await page.getByLabel('Mitarbeiter',{exact:true}).selectOption({label:'Synthetic technician'});await ready(page);
  const employees=await api('/employees');let employee=(employees.items||employees).find(e=>e.name==='Synthetic technician');
  employee=await api('/employees',request({id:employee.id,revision:employee.revision,employment_from:'2026-01-01',employment_to:null}));
  const file=await api('/personnel/files',request({employee_id:employee.id,purpose:'personnel',owner_visible:false,filename:'synthetic-actual-rv-originals.pdf',media_type:'application/pdf',content_base64:Buffer.from('%PDF-1.4\nSynthetic established RV exemption, actual request and reviewed non-objection\n%%EOF').toString('base64')}));
  await api('/personnel/agreements',request({employee_id:employee.id,revision:0,effective_from:'2026-01-01',employment_kind:'minijob',pay_basis:'monthly',amount_minor:60300,currency:'EUR',reference_file_id:file.id}));
  const original=await api('/payroll/profiles',request({employee_id:employee.id,revision:0,profile:sample.record.sources.original_profile.profile,source_file_id:file.id,confirmed:true}));
  const preparationPreview=await api('/personnel/payroll-preparations/preview?employee_id='+employee.id+'&month=2026-10');
  const preparation=await api('/personnel/payroll-preparations',request({employee_id:employee.id,month:'2026-10',revision:0,source_hash:preparationPreview.source_hash,completeness_confirmed:true}));
  await payroll();await page.getByRole('button',{name:'Minijob-RV und Aufhebungsantrag prüfen',exact:true}).click();
  await modal('Minijob-RV · Synthetic technician').getByRole('button',{name:'RV-Verlauf anhand der Originale aufnehmen',exact:true}).click();
  const form=modal('Minijob-RV anhand der Originale prüfen');
  for(const [label,value]of Object.entries({'Tatsächlicher Abrechnungsmonat (JJJJ-MM)':'2026-10','Tatsächlicher Prüfstand bis':'2026-10-31','Bereits bestehende Befreiung ab':'2026-01-01','Antrag beim Arbeitgeber eingegangen am':'2026-07-17','Meldung bei der Minijob-Zentrale eingegangen am':'2026-07-21','Tatsächlich geprüfte Widerspruchsfrist bis':'2026-08-21','Belegter Abschluss-/Widerspruchsstand vom':'2026-08-22','Prüfvermerk zum tatsächlichen Verfahren':'Synthetic original received application and reviewed non-objection','Prüfvermerk zum vollständigen RV-Verlauf':'Synthetic actual sole continuous commercial employment reviewed'}))await form.getByLabel(label,{exact:true}).fill(value);
  for(const label of ['Einziger durchgehender gewerblicher Minijob nach 2012 geprüft','Keine Altersrenten- oder sonstigen Ausschlussfälle geprüft','Bereits bestehende Befreiung anhand der Originale bestätigt','Anwendbare Frist einschließlich Feiertagen fachlich geprüft'])await form.getByLabel(label,{exact:true}).check();
  for(const [label,value]of Object.entries({'Ursprüngliches befreites Minijobprofil':original.id+'/'+original.revision+'/'+original.content_hash,'Original zur bereits bestehenden Befreiung':file.id,'Aufhebungsantrag tatsächlich eingegangen':'received','Tatsächliche Antragsform':'electronic','Original des eingegangenen Antrags':file.id,'Original zum Eingang der Meldung':file.id,'Tatsächlicher Widerspruchsstand':'non_objection_verified','Original der tatsächlichen Fristprüfung':file.id,'Original zum tatsächlichen Verfahrensstand':file.id}))await form.getByLabel(label,{exact:true}).selectOption(value);
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await form.getByRole('button',{name:'RV-Wirkung unverbindlich prüfen',exact:true}).click();
  const confirm=modal('RV-Prüfstand bestätigen');await confirm.getByText('RV-Pflicht nach belegter Aufhebung',{exact:true}).waitFor();
  await confirm.getByLabel('Genau diesen Prüfstand und seine Originale ausdrücklich bestätigen',{exact:true}).check();await confirm.getByRole('button',{name:'Geprüften RV-Verlauf festhalten',exact:true}).click();
  await confirm.getByRole('alert').waitFor();assert.equal(records.length,1);await close();
  await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
  assert.equal(records.length,2);assert.deepEqual(records[0].body,records[1].body);assert.deepEqual(records[0].value,records[1].value);
  const record=records[1].value;assert.equal(record.plan.minijob_rv_exempt,false);
  const {payrollProfileFields}=await import('../payroll.js');
  const profile={...original.profile,effective_from:'2026-08-01',minijob_rv_exempt:false};
  async function profileEditor(evidence){
    await payroll();await page.getByRole('button',{name:'Neues Lohnprofil erfassen',exact:true}).click();
    const form=modal('Neues Lohnprofil erfassen');await form.waitFor();
    for(const field of payrollProfileFields([file],{profile,source_file:file})){
      const control=form.getByLabel(field.label,{exact:true});if(await control.count()===0)continue;
      if(field.type==='multi')continue;
      if(field.type==='checkbox'){await control.check();continue;}
      if(field.type==='select')await control.selectOption(String(field.value??''));else await control.fill(String(field.value??''));
    }
    await form.getByLabel('Aktueller RV-Nachweis für den Minijob',{exact:true}).selectOption(evidence.id+'/'+evidence.revision+'/'+evidence.content_hash);
    assert.deepEqual(await form.locator('form').evaluate(form=>[...form.elements].filter(v=>v.willValidate&&!v.validity.valid).map(v=>({name:v.name,value:v.value,message:v.validationMessage}))),[]);
    return form;
  }
  const staleProfileForm=await profileEditor(record);
  const details=structuredClone(record.details);details.prior_assessment_refs=[{id:record.id,revision:record.revision,content_hash:record.content_hash}];details.assessment.review_note='Synthetic later unchanged RV review explicitly selected';
  const proposal={employee_id:employee.id,employee_revision:employee.revision,kind:record.kind,rule_version:record.rule_version,source_contract_version:1,details,source_file_ids:record.source_file_ids};
  const nextPreview=await api('/payroll/rv-lifecycle/preview',proposal);
  const currentEvidence=await api('/payroll/rv-lifecycle',request({...proposal,id:record.id,revision:record.revision,status:'active',confirmed:true,preview_hash:nextPreview.preview_hash,correction_reason:'Synthetic current original review while profile editor was already open'}));
  await staleProfileForm.getByRole('button',{name:'Geprüfte Merkmale belegt speichern',exact:true}).click();await staleProfileForm.getByRole('alert').waitFor();
  assert.match(await staleProfileForm.getByRole('alert').innerText(),/geändert|genaue Fassung/);
  assert.equal((await api('/payroll/profiles?employee_id='+employee.id)).items.length,1);
  const profileForm=await profileEditor(currentEvidence);
  await profileForm.getByRole('button',{name:'Geprüfte Merkmale belegt speichern',exact:true}).click();await modal('Lohnberechnung 2026 · Synthetic technician').waitFor();
  const profiles=await api('/payroll/profiles?employee_id='+employee.id),bound=profiles.items.find(p=>p.profile.effective_from==='2026-08-01');
  assert.deepEqual(bound.rv_lifecycle_ref,{id:currentEvidence.id,revision:currentEvidence.revision,content_hash:currentEvidence.content_hash});
  const input={employee_id:employee.id,profile_id:bound.id,profile_revision:bound.revision,preparation_id:preparation.id,preparation_revision:preparation.revision,gross_minor:60300,full_month_confirmed:true};
  const preview=await api('/payroll/preview',input);assert.equal(preview.calculation.net_minor,58129);
  const run=await api('/payroll/runs',request({...input,revision:0,confirmed:true,preview_hash:preview.preview_hash,accepted_scope:preview.calculation.scope}));
  assert.equal(run.calculation.employee_social_total_minor,2171);
  await payroll();await page.getByRole('button',{name:'Minijob-RV und Aufhebungsantrag prüfen',exact:true}).click();
  const detail=modal('Minijob-RV · Synthetic technician');await detail.getByText('RV-Pflicht nach belegter Aufhebung',{exact:true}).waitFor();
  await page.screenshot({path:path.join(screenshots,'payroll-rv-mobile.png'),fullPage:false});
  await detail.getByRole('button',{name:'Aktuellen RV-Nachweis öffnen',exact:true}).click();
  await modal('RV-Nachweis · Synthetic technician').getByRole('button',{name:'Vollständige RV-Historie öffnen',exact:true}).click();
  await modal('RV-Nachweishistorie').getByText('Fassung 2',{exact:true}).waitFor();
  for(const permission of ['personnel.read','personnel.approve'])await api('/settings/permissions',request({user_id:employee.user_id,permission,scope:'*',effect:'allow',revision:0}));
  technicianContext=await context.browser().newContext({viewport:{width:390,height:844},locale:'de-DE',timezoneId:'Europe/Berlin'});
  const tech=await technicianContext.newPage();await tech.goto(fixture.base_url+'/office/');await login(tech,'technician@browser.example.test');await navigate(tech,'Personal');
  await tech.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();await tech.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();
  await tech.getByRole('button',{name:'Minijob-RV und Aufhebungsantrag prüfen',exact:true}).click();await tech.getByRole('button',{name:'Aktuellen RV-Nachweis öffnen',exact:true}).click();
  const privateDetail=tech.getByRole('dialog',{name:'RV-Nachweis · Synthetic technician',exact:true});await privateDetail.getByText('Synthetic later unchanged RV review explicitly selected',{exact:true}).waitFor();
  await api('/settings/permissions',request({user_id:employee.user_id,permission:'personnel.read',scope:'*',effect:'deny',revision:1}));
  await privateDetail.getByRole('button',{name:'Vollständige RV-Historie öffnen',exact:true}).click();await privateDetail.getByRole('alert').first().waitFor();
  assert.equal(await privateDetail.getByText('Synthetic later unchanged RV review explicitly selected',{exact:true}).count(),0);
  assert.equal(await privateDetail.getByRole('button',{name:'Geschütztes Original: '+file.filename,exact:true}).count(),0);
  console.log('RV: actual MFA/HTTP, explicit mobile originals and reviewed deadline, exact lost-answer replay, real profile editor binding, actual 581.29 EUR net and original history passed');
 }finally{await technicianContext?.close();await context.unroute(pattern);await fs.writeFile(path.join(screenshots,'payroll-rv-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={payrollRvLifecycleFlow};
