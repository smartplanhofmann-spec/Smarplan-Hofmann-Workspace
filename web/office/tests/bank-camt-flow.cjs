const assert=require('node:assert/strict'),crypto=require('node:crypto'),fs=require('node:fs/promises'),path=require('node:path');
const request=value=>({request_id:crypto.randomUUID().replaceAll('-',''),confirmation:true,...value});

async function bankCamtFlow(h){
 const {page,context,navigate,ready,login,fixture,screenshots}=h;
 const records=[];let token,lose=true,withdraw=false;
 const modal=name=>page.getByRole('dialog',{name,exact:true});
 const close=()=>page.getByRole('dialog').getByRole('button',{name:'Dialog schließen',exact:true}).click();
 page.on('request',r=>{if(new URL(r.url()).origin===fixture.base_url&&r.headers().authorization)token=r.headers().authorization;});
 async function api(suffix,body){const r=await context.request.fetch(fixture.base_url+'/api/v1/business'+suffix,{method:body?'POST':'GET',headers:{Authorization:token,Origin:fixture.base_url},...(body?{data:body}:{}),maxRedirects:0});assert.ok(r.ok(),suffix+' '+await r.text());return r.json();}
 await navigate(page,'Finanzen');
 const account=await api('/accounting/accounts',request({code:'CAMT-SYN',name:'Synthetic XML bank',kind:'bank'}));
 const source=(await api('/accounting/sources/payments')).items.find(v=>v.payment_id===fixture.accounting_payments.find(v=>v.kind==='receipt').id);
 const cash=await api('/accounting/events/import-payment',request({payment_id:source.payment_id,source_hash:source.source_hash,account_id:account.id,account_revision:1,cash_date:'2026-11-02',evidence_reference:'Synthetic existing bank receipt'}));
 const binding=await api('/bank/accounts',{request_id:crypto.randomUUID().replaceAll('-',''),account_id:account.id,account_revision:1,revision:0,iban:'DE89370400440532013000',label:'Synthetic CAMT bank',active:true,coverage_from:'2026-11-01',coverage_to:null,reason:''});
 const bytes=await fs.readFile(path.join(__dirname,'fixtures/bank_camt_119.xml'));
 const digest=crypto.createHash('sha256').update(bytes).digest('hex');
 await context.route('**/api/v1/business/capabilities*',async route=>{
  const response=await route.fetch({maxRedirects:0});const value=await response.json();
  if(withdraw)value.features=value.features.filter(v=>v!=='bank_camt_v1');
  return route.fulfill({response,json:value});
 });
 const pattern='**/api/v1/business/bank/**';
 await context.route(pattern,async route=>{
  const req=route.request(),response=await route.fetch({maxRedirects:0});
  if(!response.headers()['content-type']?.includes('application/json'))return route.fulfill({response});
  const value=await response.json(),body=req.method()==='POST'?req.postDataJSON():null,url=new URL(req.url());
  records.push({path:url.pathname,method:req.method(),body,status:response.status(),value});
  if(lose&&body&&response.ok()&&url.pathname.endsWith('/bank/camt/statements')){lose=false;return route.abort('failed');}
  return route.fulfill({response});
 });
 async function open(){await navigate(page,'Finanzen');await page.getByRole('button',{name:'Bankabgleich öffnen',exact:true}).click();await modal('Bankabgleich').getByRole('button',{name:'Kontoauszüge und Abgleich öffnen',exact:true}).click();await modal('Bankkonto · Synthetic CAMT bank').waitFor();}
 async function propose(){
  await modal('Bankkonto · Synthetic CAMT bank').getByRole('button',{name:'Originalen XML-Auszug prüfen',exact:true}).click();
  const picker=modal('Originalen XML-Auszug auswählen');await picker.getByLabel('Originalen XML-Kontoauszug auswählen',{exact:true}).setInputFiles({name:'synthetic-bank.xml',mimeType:'application/xml',buffer:bytes});
  await picker.getByRole('button',{name:'XML-Auszug lesen',exact:true}).click();
  const review=modal('XML-Kontoauszug prüfen');await review.waitFor();
  assert.equal(await review.getByRole('checkbox').isChecked(),false);
  assert.match(await review.innerText(),/119,00/);
  await review.getByRole('checkbox').check();await review.getByRole('button',{name:'Auszug unverbindlich prüfen',exact:true}).click();
  const final=modal('Banknachweis bestätigen');await final.waitFor();
  assert.equal(await final.getByRole('checkbox').isChecked(),false);
  await final.getByRole('checkbox').check();return final;
 }
 try{
  await open();const confirm=await propose();
  await page.screenshot({path:path.join(screenshots,'camt-preview-desktop.png'),fullPage:false});
  await confirm.getByRole('button',{name:'Geprüften Banknachweis speichern',exact:true}).click();
  await confirm.getByRole('alert').waitFor();await close();
  const before=records.filter(v=>v.method==='POST'&&v.path.endsWith('/bank/camt/statements'));
  assert.equal(before.length,1);assert.equal(before[0].value.statement.payload.file_sha256,digest);
  withdraw=true;
  await page.getByRole('button',{name:'1 Antwort offen',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Die aktuelle XML-Bankfreigabe fehlt.'}).waitFor();
  assert.equal(records.filter(v=>v.method==='POST'&&v.path.endsWith('/bank/camt/statements')).length,1);
  withdraw=false;await page.getByRole('dialog').getByRole('button',{name:'Unverändert erneut senden',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'detached'});await ready(page);
  const imports=records.filter(v=>v.method==='POST'&&v.path.endsWith('/bank/camt/statements'));
  assert.equal(imports.length,2);assert.deepEqual(imports[0].body,imports[1].body);assert.deepEqual(imports[0].value,imports[1].value);
  const saved=imports[0].value;assert.equal(saved.lines.length,1);assert.equal(saved.lines[0].transaction.payload.amount,'119.00');
  await open();await modal('Bankkonto · Synthetic CAMT bank').getByRole('button',{name:new RegExp(saved.statement.reference_key)}).click();
  const statement=modal('Originaler Kontoauszug');await statement.waitFor();
  const downloadPromise=page.waitForEvent('download');await statement.getByRole('button',{name:'Unverändertes XML-Original herunterladen',exact:true}).click();
  const download=await downloadPromise;assert.equal(download.suggestedFilename(),'synthetic-bank.xml');
  assert.deepEqual(await fs.readFile(await download.path()),bytes);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(screenshots,'camt-original-mobile.png'),fullPage:false});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await close();
  const unchanged=await api('/accounting/events/'+cash.id);assert.deepEqual(unchanged,cash);
  const candidates=await api('/bank/transactions/'+saved.lines[0].transaction_id+'/candidates');
  const matchSource=candidates.items.find(v=>v.source.source_id===cash.id)?.source;assert.ok(matchSource,'Existing cash source must remain available');
  const body={revision:candidates.current.revision,links:[{source_kind:matchSource.source_kind,source_id:matchSource.source_id,source_hash:matchSource.source_hash,amount:'119.00',date_difference_reason:''}],reason:'Synthetic XML original and existing cash checked'};
  const proof=await api('/bank/transactions/'+saved.lines[0].transaction_id+'/preview',body);
  await api('/bank/transactions/'+saved.lines[0].transaction_id+'/matches',request({...body,preview_hash:proof.preview_hash}));
  const reportBody={account_id:account.id,period:'2026-11',statement_ids:[saved.statement.id],reason:'Synthetic complete XML statement scope'};
  const report=await api('/bank/reconciliations/preview',reportBody);assert.equal(report.complete,true);
  assert.equal(report.bank_movement_net,'119.00');assert.equal(report.cash_movement_net,'119.00');
  const worker=await context.newPage();let workerToken;
  worker.on('request',r=>{if(r.headers().authorization)workerToken=r.headers().authorization;});
  try{await worker.goto(fixture.base_url+'/office/');await login(worker,'technician@browser.example.test');const denied=await context.request.get(fixture.base_url+'/api/v1/business/bank/statements/'+saved.statement.id+'/original',{headers:{Authorization:workerToken,Origin:fixture.base_url}});assert.equal(denied.status(),403);}finally{await worker.close();}
  console.log('CAMT: real MFA, XML file, explicit two-stage review, lost ACK and withdrawn feature, identical retry, exact original download, existing cash match, complete report, private rights and 390px passed');
 }finally{await context.unroute(pattern);await context.unroute('**/api/v1/business/capabilities*');await fs.writeFile(path.join(screenshots,'camt-synthetic-commands.json'),JSON.stringify(records,null,2));}
}
module.exports={bankCamtFlow};
