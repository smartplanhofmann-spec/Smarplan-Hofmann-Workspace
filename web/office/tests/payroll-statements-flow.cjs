const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
async function payrollStatementsFlow(h){
 const {page,context,navigate,ready,login,fixture,screenshots}=h;
 const seeded=await require('./payroll-periods-flow.cjs').payrollPeriodsFlow(h);
 await page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
 await page.getByRole('button',{name:'Abmelden',exact:true}).click();await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();
 let token;const requests=[];page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization){token=r.headers().authorization;requests.push(new URL(r.url()).pathname);}});
 await login(page,'technician@browser.example.test');await navigate(page,'Personal');
 await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();
 requests.length=0;
 await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();
 const list=page.getByRole('dialog',{name:'Meine Lohnnachweise · Synthetic technician',exact:true});await list.waitFor();
 await list.getByRole('button',{name:'Lohnnachweis ansehen',exact:true}).click();
 const detail=page.getByRole('dialog',{name:'Mitarbeiter-Lohnnachweis · 2026-10',exact:true});await detail.waitFor();
 assert.match(await detail.innerText(),/1.726,86/);assert.match(await detail.innerText(),/Sozialversicherung/);
 assert.equal(requests.some(p=>/\/payroll\/(?:runs|profiles|facts)(?:\/|$)/.test(p)),false);
 const own=await context.request.get(fixture.base_url+'/api/v1/business/payroll/employee-statements/'+seeded.run.id,{headers:{Authorization:token,Origin:fixture.base_url}});
 assert.ok(own.ok());const statement=(await own.json()).statement;assert.equal(statement.calculation.net_minor,seeded.run.calculation.net_minor);
 for(const forbidden of ['period_case','employment_terms','work_schedule','source_file_ids','verification_note','tax_identifier'])assert.equal(JSON.stringify(statement).includes('"'+forbidden+'"'),false);
 const pdfPromise=page.waitForEvent('download');await detail.getByRole('button',{name:'Eigenen PDF-Lohnnachweis herunterladen',exact:true}).click();const pdf=await fs.readFile(await(await pdfPromise).path());assert.equal(crypto.createHash('sha256').update(pdf).digest('hex'),statement.pdf_sha256);assert.notEqual(statement.pdf_sha256,seeded.run.pdf_sha256);
 for(const suffix of ['/payroll/runs/'+seeded.run.id,'/payroll/runs/'+seeded.run.id+'/pdf?revision=1','/payroll/facts/sources?employee_id='+seeded.employee.id]){
  const denied=await context.request.get(fixture.base_url+'/api/v1/business'+suffix,{headers:{Authorization:token,Origin:fixture.base_url}});assert.equal(denied.status(),403);
 }
 await detail.getByRole('button',{name:'Beleghistorie öffnen',exact:true}).click();const history=page.getByRole('dialog',{name:'Mitarbeiter-Beleghistorie',exact:true});await history.getByRole('button',{name:'Diese Fassung ansehen',exact:true}).click();await detail.waitFor();
 await page.setViewportSize({width:390,height:844});await detail.getByText('Netto',{exact:true}).scrollIntoViewIfNeeded();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(await detail.locator('.table-scroll').evaluateAll(nodes=>nodes.every(node=>node.scrollWidth<=node.clientWidth+1)),true);await page.screenshot({path:path.join(screenshots,'payroll-statement-own-mobile.png'),fullPage:false});
 const adminContext=await context.browser().newContext();let adminToken;
 try{
  const adminPage=await adminContext.newPage();adminPage.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)adminToken=r.headers().authorization;});
  await adminPage.goto(fixture.base_url+'/office/');await login(adminPage,'owner@browser.example.test',h.recovery[0]);
  const revoked=await adminContext.request.post(fixture.base_url+'/api/v1/business/settings/permissions',{headers:{Authorization:adminToken,Origin:fixture.base_url},data:{request_id:crypto.randomUUID().replaceAll('-',''),user_id:seeded.employee.user_id,permission:'time.own',scope:'*',effect:'deny',revision:0}});assert.ok(revoked.ok(),await revoked.text());
 }finally{await adminContext.close();}
 await detail.getByRole('button',{name:'Eigenen PDF-Lohnnachweis herunterladen',exact:true}).click();await detail.getByRole('alert').waitFor();assert.equal(await detail.getByText('Netto',{exact:true}).count(),0);assert.match(await detail.innerText(),/nicht mehr freigegeben/);
 const denied=await context.request.get(fixture.base_url+'/api/v1/business/payroll/employee-statements/'+seeded.run.id,{headers:{Authorization:token,Origin:fixture.base_url}});assert.equal(denied.status(),403);
 console.log('payroll statements: actual own password/MFA, reduced v4 page, no raw payroll requests, private source denial, independent PDF bytes, history, mobile390 and fresh revocation clearing passed');
}
module.exports={payrollStatementsFlow};
