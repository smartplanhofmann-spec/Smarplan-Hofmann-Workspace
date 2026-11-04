/* Called from an actual Source4 run browser workflow; no synthetic responses. */
const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');

async function payrollOneOffOwnFlow(h,employee,run){
  const {page,navigate,fixture,screenshots}=h;
  const close=async()=>{const dialog=page.getByRole('dialog');if(await dialog.count())await dialog.getByRole('button',{name:'Dialog schließen',exact:true}).click();};
  await close();await navigate(page,'Personal');
  await page.getByRole('button',{name:'Personalakte, Reisen und Lohnvorbereitung',exact:true}).click();
  await page.getByRole('button',{name:'Lohnberechnung 2026 öffnen',exact:true}).click();
  // click() finishes before the asynchronous staff loader. That loader must
  // finish (its dialog is shown only after all private staff reads) before
  // measuring the subsequent, separate employee-statement navigation.
  await page.getByRole('dialog',{name:'Lohnberechnung 2026 · '+employee.name,exact:true}).waitFor();
  const requests=[],capture=request=>{const url=new URL(request.url());if(url.origin===fixture.base_url)requests.push(url.pathname);};
  page.on('request',capture);
  try{
    await page.getByRole('dialog').getByRole('button',{name:'Mitarbeiter-Lohnnachweise ansehen',exact:true}).click();
    const list=page.getByRole('dialog',{name:'Meine Lohnnachweise · '+employee.name,exact:true});await list.waitFor();
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/payroll/employee-statements/'+run.id)&&r.request().method()==='GET');
    await list.getByRole('button',{name:'Lohnnachweis ansehen',exact:true}).click();
    const statement=(await(await response).json()).statement;
    assert.equal(statement.schema_version,3);assert.deepEqual(statement.run_ref,{id:run.id,revision:run.revision,content_hash:run.content_hash});
    assert.equal(statement.one_off_summary.amount_minor,run.calculation.one_off_details.amount_minor);
    assert.equal(statement.one_off_summary.employee_social_total_minor,run.calculation.one_off_details.social.employee_total_minor);
    assert.equal(statement.calculation.payout_minor,run.calculation.payout_minor);
    const detail=page.getByRole('dialog',{name:'Mitarbeiter-Lohnnachweis · '+run.source.month,exact:true});await detail.waitFor();
    assert.match(await detail.innerText(),/Einmalzahlung \/ sonstiger Bezug/);
    assert.match(await detail.innerText(),/Berechneter Zuflussstichtag/);
    const download=page.waitForEvent('download');await detail.getByRole('button',{name:'Eigenen PDF-Lohnnachweis herunterladen',exact:true}).click();
    const pdf=await fs.readFile(await(await download).path());assert.equal(crypto.createHash('sha256').update(pdf).digest('hex'),statement.pdf_sha256);
    assert.notEqual(statement.pdf_sha256,run.pdf_sha256);
    const source=run.source.one_off_case.sources.calculation_source;
    for(const original of [run.source.one_off_case.id,source.one_off_earning.id,source.current_annual_basis.id,source.annual_tax_forecast.id,...run.source.one_off_case.source_file_ids]){
      assert.equal(JSON.stringify(statement).includes(original),false);assert.equal(pdf.includes(Buffer.from(original)),false);
    }
    for(const forbidden of ['annual_pay_before_minor','annual_tax_before_minor','annual_tax_after_minor','source_file_ids','verification_note','tax_identifier','earning_ref','annual_basis_ref'])assert.equal(JSON.stringify(statement).includes('"'+forbidden+'"'),false);
    await page.setViewportSize({width:390,height:844});await detail.getByText('Einmalzahlung / sonstiger Bezug',{exact:true}).scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    assert.equal(await detail.locator('.table-scroll').evaluateAll(nodes=>nodes.every(node=>node.scrollWidth<=node.clientWidth+1)),true);
    await page.screenshot({path:path.join(screenshots,'payroll-oneoff-own-mobile.png'),fullPage:false});
    await detail.getByRole('button',{name:'Beleghistorie öffnen',exact:true}).click();
    const history=page.getByRole('dialog',{name:'Mitarbeiter-Beleghistorie',exact:true});await history.waitFor();
    assert.equal(await history.getByRole('button',{name:'Diese Fassung ansehen',exact:true}).count(),run.revision);
    await history.getByRole('button',{name:'Diese Fassung ansehen',exact:true}).first().click();await detail.waitFor();
    assert.match(await detail.innerText(),/Fassung 1/);
    const forbiddenRequests=requests.filter(p=>/\/payroll\/(?:runs|profiles|facts|annual-facts|one-off-cases)(?:\/|$)|\/personnel\/files/.test(p));
    assert.deepEqual(forbiddenRequests,[],'Employee-statement navigation requested private routes: '+JSON.stringify(forbiddenRequests));
    await close();
    console.log('payroll oneoff employee statement: actual Source4 reduced schema3, own bonus, independent PDF SHA256, no annual/source originals, exact history and mobile390 passed');
    return statement;
  }finally{page.off('request',capture);}
}
module.exports={payrollOneOffOwnFlow};
