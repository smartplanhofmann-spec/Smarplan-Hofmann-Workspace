/* Real Chromium + disposable loopback Flask/auth/SQLite. No providers or token injection. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const PASSWORD='Synthetic-browser-password-123';
const delay=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
function compactFailure(error){
  const lines=String(error?.stack||error).replace(/\r\n?/g,'\n').split('\n');
  const selected=lines.length<=50?lines:[...lines.slice(0,35),`[${lines.length-50} middle diagnostic lines omitted]`,...lines.slice(-15)];
  return selected.map(line=>line.length>400?line.slice(0,400)+' [line truncated]':line).join('\n');
}
function namespaceSandboxArguments(value){
  if(value===undefined||value==='0')return [];
  assert.equal(value,'1','SMARTPLAN_BROWSER_NAMESPACE_SANDBOX accepts only 1, 0 or unset');
  // Explicit test-environment alternative to an unavailable root-owned SUID
  // helper. Namespace and seccomp isolation must still pass the live probe.
  return ['--disable-setuid-sandbox'];
}
function assertNamespaceSandbox(status){
  for(const expression of [/Layer 1 Sandbox\s+Namespace/,/PID namespaces\s+Yes/,
    /Network namespaces\s+Yes/,/Seccomp-BPF sandbox\s+Yes/])assert.match(status,expression);
}
async function launchDiagnostics(executable){
  const values={browser:executable||'Playwright managed Chromium',uid:process.getuid?.()};
  for(const [name,filename]of Object.entries({apparmor_enabled:'/sys/module/apparmor/parameters/enabled',apparmor_profile:'/proc/self/attr/current',apparmor_restrict_unprivileged_userns:'/proc/sys/kernel/apparmor_restrict_unprivileged_userns',unprivileged_userns_clone:'/proc/sys/kernel/unprivileged_userns_clone',max_user_namespaces:'/proc/sys/user/max_user_namespaces'})){
    try{values[name]=(await fs.readFile(filename,'utf8')).trim().slice(0,160);}catch{values[name]='unavailable';}
  }
  return values;
}
function totp(secret){
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits='';for(const character of secret.replace(/=/g,''))bits+=alphabet.indexOf(character).toString(2).padStart(5,'0');
  const bytes=[];for(let offset=0;offset+8<=bits.length;offset+=8)bytes.push(parseInt(bits.slice(offset,offset+8),2));
  const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));const digest=crypto.createHmac('sha1',Buffer.from(bytes)).update(counter).digest(),offset=digest.at(-1)&15;
  return String((digest.readUInt32BE(offset)&0x7fffffff)%1000000).padStart(6,'0');
}
async function login(page,email,recovery){
  await page.getByLabel('E-Mail',{exact:true}).fill(email);await page.getByLabel('Passwort',{exact:true}).fill(PASSWORD);await page.getByRole('button',{name:'Weiter',exact:true}).click();
  await page.getByRole('heading',{name:'Anmeldung bestätigen',exact:true}).waitFor();
  let code=recovery;if(!code)code=totp((await page.locator('.secret').textContent()).trim());
  await page.getByLabel('Authentifizierungscode',{exact:true}).fill(code);await page.getByRole('button',{name:'Bestätigen',exact:true}).click();
  let codes=[];
  if(!recovery){await page.getByRole('heading',{name:'Wiederherstellungscodes sichern'}).waitFor();codes=await page.locator('.recovery-list span').allTextContents();await page.getByRole('button',{name:'Ich habe die Codes gesichert'}).click();}
  await page.getByRole('heading',{name:'Guten Tag.',exact:true}).waitFor();return codes;
}
async function ready(page){await page.locator('main .loading').waitFor({state:'detached'});const errors=await page.locator('main [role=alert]').allTextContents();assert.deepEqual(errors,[]);}
async function navigate(page,name){if(await page.locator('.sidebar').evaluate(sidebar=>sidebar.inert))await page.getByRole('button',{name:'Navigation öffnen',exact:true}).click();await page.locator('.navigation').getByRole('button',{name,exact:true}).click();await ready(page);}
async function main(){
  const workflow=process.env.SMARTPLAN_BROWSER_WORKFLOW;
  assert.ok(workflow===undefined||['time-tracking', 'accounting-open-items', 'company-events', 'catalog-prices', 'historical-assets', 'payroll-multiple-cases', 'catalog-imports', 'accounting-openings', 'payroll-oneoff-cases', 'payroll-zero-account', 'payroll-annual-basis', 'payroll-wage-interruptions', 'payroll-calculation-cases', 'travel-v3', 'payroll-travel-tax-policies', 'payroll-entitlements', 'travel-allowances', 'payroll-statements', 'payroll-periods', 'purchase-changes', 'payroll-transition', 'bank-reconciliation', 'resource-custody', 'accessibility', 'privacy-cases', 'service', 'custom-fields', 'migrations', 'payroll-cash', 'company-handover', 'speech', 'sales', 'company-overview', 'inventory-counts', 'invoice-chain', 'payroll', 'assistant', 'personnel-workflow', 'asset-provenance', 'project-economics', 'accounting-allocation', 'accounting-components', 'accounting-refunds', 'accounting-capacity', 'accounting-refunds-v2', 'accounting-profile', 'inventory-article-refs', 'project-customer'].includes(workflow),'Unsupported targeted browser workflow');
  const {chromium}=require('playwright');
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'smartplan-browser-e2e-')),readyFile=path.join(directory,'ready.json');
  const screenshots=process.env.SMARTPLAN_BROWSER_SCREENSHOT_DIR||directory;
  let browser,server,page,launchInfo;let output='';const pageErrors=[],consoleErrors=[];
  try{
    await fs.mkdir(screenshots,{recursive:true,mode:0o700});
    const python=process.env.SMARTPLAN_BROWSER_TEST_PYTHON||'python3';
    server=spawn(python,[path.join(__dirname,'serve_fixture.py'),'--ready-file',readyFile,...(workflow==='speech'?['--synthetic-speech']:[]),...(workflow==='company-events'?['--synthetic-company-events']:[]),...(['payroll-cash','travel-allowances','travel-v3'].includes(workflow)?['--synthetic-payroll-cash']:[]),...(['company-handover','payroll-cash','travel-allowances','travel-v3'].includes(workflow)?['--synthetic-handover']:[])],{env:{PATH:process.env.PATH,LANG:'C.UTF-8',TZ:'Europe/Berlin',PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
    for(const stream of [server.stdout,server.stderr])stream.on('data',chunk=>{output=(output+chunk.toString()).slice(-15000);});
    let fixture;
    for(let index=0;index<300;index++){try{fixture=JSON.parse(await fs.readFile(readyFile,'utf8'));break;}catch(error){if(error.code!=='ENOENT')throw error;if(server.exitCode!==null)throw new Error('Fixture exited: '+output);await delay(50);}}
    assert.ok(fixture,'fixture did not become ready');
    let executable=process.env.SMARTPLAN_CHROMIUM_BINARY;
    if(executable===undefined){try{await fs.access('/usr/bin/chromium');executable='/usr/bin/chromium';}catch{executable='';}}
    // Explicit empty override selects Playwright's pinned bundled browser in CI.
    launchInfo=await launchDiagnostics(executable);
    const namespaceArguments=namespaceSandboxArguments(process.env.SMARTPLAN_BROWSER_NAMESPACE_SANDBOX);
    browser=await chromium.launch({...executable?{executablePath:executable}:{},headless:true,chromiumSandbox:true,args:['--enable-automation',...namespaceArguments,...(workflow==='speech'?['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']:[])]});
    const debug=await browser.newBrowserCDPSession();
    const command=await debug.send('Browser.getBrowserCommandLine');
    assert.ok(!command.arguments.some(argument=>['--no-sandbox','--disable-web-security','--ignore-certificate-errors','--disable-seccomp-filter-sandbox','--disable-namespace-sandbox'].includes(argument)),'browser security must remain enabled');
    await debug.detach();
    if(namespaceArguments.length){
      const probe=await browser.newPage();
      try{
        await probe.goto('chrome://sandbox');
        const status=await probe.locator('body').innerText();
        assertNamespaceSandbox(status);
        console.log('browser: namespace, PID, network and seccomp sandboxes verified before application access');
      }finally{await probe.close();}
    }
    const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'de-DE',timezoneId:'Europe/Berlin',acceptDownloads:true});
    await context.route('**/*',route=>new URL(route.request().url()).origin===fixture.base_url?route.continue():route.abort());
    page=await context.newPage();page.on('pageerror',error=>pageErrors.push(error.message));page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});page.setDefaultTimeout(15000);
    await page.goto(fixture.base_url+'/office/');
    if(workflow==='accessibility')await require('./accessibility-flow.cjs').audit(page,'login');
    const recovery=await login(page,'owner@browser.example.test');
    if(workflow==='inventory-article-refs'){
      await require('./inventory-article-refs-flow.cjs').inventoryArticleRefsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();return;
    }
    if(workflow==='project-customer'){
      await require('./project-customer-flow.cjs').projectCustomerFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();return;
    }
    if(workflow==='accessibility'){
      await require('./accessibility-flow.cjs').accessibilityFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted accessibility workflow passed (real rendered WCAG scans, keyboard and mobile views)');return;
    }
    if(workflow==='privacy-cases'){
      await require('./privacy-cases-flow.cjs').privacyCasesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted privacy case workflow passed (real MFA/HTTP, private RAM commands and supervised export)');return;
    }
    if(workflow==='custom-fields'){
      await require('./custom-fields-flow.cjs').customFieldsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted custom fields workflow passed (real MFA/HTTP, typed revisions and original retry)');return;
    }
    if(workflow==='payroll-travel-tax-policies'){
      await require('./payroll-travel-tax-policies-flow.cjs').payrollTravelTaxPoliciesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll travel tax policies workflow passed');return;
    }
    if(workflow==='payroll-multiple-cases'){
      await require('./payroll-multiple-cases-flow.cjs').payrollMultipleCasesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted Source5 payroll workflow passed (actual MFA, original source chain, separately dated actual transfers, private and employee-safe exports)');return;
    }
    if(workflow==='payroll-oneoff-cases'){
      await require('./payroll-oneoff-cases-flow.cjs').payrollOneOffCasesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll oneoff cases workflow passed');return;
    }
    if(workflow==='payroll-annual-basis'){
      await require('./payroll-annual-basis-flow.cjs').payrollAnnualBasisFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll annual basis workflow passed');return;
    }
    if(workflow==='payroll-zero-account'){
      await require('./payroll-zero-account-flow.cjs').payrollZeroAccountFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll zero account workflow passed');return;
    }
    if(workflow==='payroll-wage-interruptions'){
      await require('./payroll-wage-interruptions-flow.cjs').payrollWageInterruptionsFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll wage interruptions workflow passed');return;
    }
    if(workflow==='accounting-open-items'){
      await require('./accounting-open-items-flow.cjs').openingItemsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);console.log('1 targeted accounting-open-items browser workflow passed');return;
    }
    if(workflow==='historical-assets'){
      await require('./accounting-historical-assets-flow.cjs').historicalAssetsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted historical assets workflow passed');return;
    }
    if(workflow==='accounting-openings'){
      await require('./accounting-openings-flow.cjs').accountingOpeningsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted accounting openings workflow passed');return;
    }
    if(workflow==='payroll-calculation-cases'){
      await require('./payroll-calculation-cases-flow.cjs').payrollCalculationCasesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll calculation cases workflow passed');return;
    }
    if(workflow==='company-events'){
      await require('./company-events-flow.cjs').companyEventsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);console.log('1 targeted company-events browser workflow passed');return;
    }
    if(workflow==='payroll-entitlements'){
      await require('./payroll-entitlements-flow.cjs').payrollEntitlementsFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted payroll entitlements workflow passed');return;
    }
    if(workflow==='travel-v3'){
      await require('./travel-v3-flow.cjs').travelV3Flow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted travel v3 workflow passed');return;
    }
    if(workflow==='travel-allowances'){
      await require('./travel-allowances-flow.cjs').travelAllowancesFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted travel allowances workflow passed (actual private journeys, foreign approval and public cash)');return;
    }
    if(workflow==='catalog-prices'){
      await require('./catalog-prices-flow.cjs').catalogPricesFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted dated catalog workflow passed');return;
    }
    if(workflow==='catalog-imports'){
      await require('./catalog-imports-flow.cjs').catalogImportsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted catalog imports workflow passed (real MFA/HTTP, original bytes, explicit acceptance and exact replay)');return;
    }
    if(workflow==='purchase-changes'){
      await require('./purchase-changes-flow.cjs').purchaseChangesFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted purchase changes workflow passed (actual MFA/HTTP, canonical purchase, stock, evidence and amendments)');return;
    }
    if(workflow==='resource-custody'){
      await require('./resource-custody-flow.cjs').resourceCustodyFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted resource custody workflow passed (real MFA/HTTP, native resource, inspection, custody and planning)');return;
    }
    if(workflow==='time-tracking'){
      await require('./time-tracking-flow.cjs').timeTrackingFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted time-tracking workflow passed (real MFA/HTTP, original time events, approved correction and exact retry)');return;
    }
    if(workflow==='service'){
      await require('./service-flow.cjs').serviceFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors');console.log('1 targeted service workflow passed (real MFA/HTTP and canonical source, planning, signed report, maintenance domains)');return;
    }
    if(workflow==='migrations'){
      await require('./migrations-flow.cjs').migrationsFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[],'browser runtime errors'); console.log('1 targeted migration workflow passed (real owner MFA/HTTP, synthetic files, no provider network)'); return;
    }
    if(workflow==='bank-reconciliation'){
      await require('./bank-reconciliation-flow.cjs').bankFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted bank reconciliation workflow passed (MFA/HTTP, original files and explicit existing-cash matches)');return;
    }
    if(workflow==='payroll-statements'){
      await require('./payroll-statements-flow.cjs').payrollStatementsFlow({page,context,navigate,ready,login,recovery,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted employee payroll statement workflow passed');return;
    }
    if(workflow==='payroll-periods'){
      await require('./payroll-periods-flow.cjs').payrollPeriodsFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted payroll periods workflow passed (MFA/HTTP, private facts, separate periods and unchanged original payroll)');return;
    }
    if(workflow==='payroll-transition'){
      await require('./payroll-transition-flow.cjs').transitionFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted transition payroll workflow passed (MFA/HTTP, explicit forecast, historical corrections and original retries)');return;
    }
    if(workflow==='payroll-cash'){
      await require('./payroll-cash-flow.cjs').payrollCashFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted actual payroll cash/EÜR workflow passed (private actual payments, public financial classification and original retries)');return;
    }
    if(workflow==='company-handover'){
      await require('./company-handover-flow.cjs').companyHandoverFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted company handover workflow passed (owner MFA, immutable ZIP proof, original retry and explicit exit review)');return;
    }
    if(workflow==='sales'){
      await require('./sales-flow.cjs').salesFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted sales workflow passed (real MFA/HTTP, canonical CRM adoptions and lost ACK)');return;
    }
    if(workflow==='company-overview'){
      await require('./company-overview-flow.cjs').companyOverviewFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted company overview workflow passed (real MFA, sources and mobile UI)');return;
    }
    if(workflow==='invoice-chain'){
      await require('./invoice-chain-flow.cjs').invoiceChainFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted invoice-chain workflow passed (real MFA/HTTP/draft conversions; synthetic archived invoices)');return;
    }
    if(workflow==='speech'){
      await require('./speech-flow.cjs').speechFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted speech workflow passed (real MediaRecorder on synthetic device, real MFA/HTTP, test-only speech transport; no provider network)');return;
    }
    if(workflow==='assistant'){
      await require('./assistant-flow.cjs').assistantFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted assistant workflow passed (real MFA/HTTP/rules/tasks/offers; no model provider or external action)');return;
    }
    if(workflow==='payroll'){
      await require('./payroll-flow.cjs').payrollFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted payroll workflow passed (real owner/employee MFA and payroll UI; synthetic HR sources)');return;
    }
    if(workflow==='inventory-counts'){
      await require('./inventory-counts-flow.cjs').inventoryCountsFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted inventory count workflow passed (real MFA/HTTP and synthetic physical inventory)');return;
    }
    if(workflow==='personnel-workflow'){
      await require('./personnel-workflow-flow.cjs').personnelWorkflowFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted personnel workflow passed (real owner/employee MFA, original expense and month UI; synthetic local sources)');return;
    }
    if(workflow==='asset-provenance'){
      await require('./asset-provenance-flow.cjs').assetProvenanceFlow({page,context,navigate,ready,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted asset provenance browser workflow passed (synthetic local purchasing setup; real original and device UI)');return;
    }
    if(workflow==='project-economics'){
      await require('./project-economics-flow.cjs').projectEconomicsFlow({page,context,navigate,ready,login,fixture,screenshots});
      assert.deepEqual(pageErrors,[]);await context.close();console.log('1 targeted project economics browser workflow passed (real original, review, classification and corrections; synthetic local fixture)');return;
    }
    if(workflow==='accounting-profile'){
      await require('./profile-flow.cjs').profileFlow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted preparation profile browser workflow passed (real explicit UI and unchanged cash sources; loopback transport, TLS/Origin acceptance separate)');return;
    }
    if(workflow==='accounting-refunds-v2'){
      await require('./refund-v2-flow.cjs').refundV2Flow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted versioned refund browser workflow passed (real UI and authenticated Finance setup per cycle; synthetic legacy invoice archives; TLS/Origin acceptance separate)');return;
    }
    if(workflow==='accounting-capacity'){
      await require('./capacity-flow.cjs').capacityFlow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted capacity browser workflow passed (real UI bootstrap; synthetic legacy invoice archives; production issuance accepted separately)');return;
    }
    if(workflow==='accounting-refunds'){
      await require('./refund-flow.cjs').refundFlow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted refund browser workflow passed (real UI bootstrap; synthetic legacy invoice archives; cancellation/production issuance accepted separately)');return;
    }
    if(workflow==='accounting-components'){
      await require('./component-flow.cjs').componentFlow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted component browser workflow passed (real UI bootstrap; synthetic legacy invoice archives; production issuance accepted separately)');return;
    }
    if(workflow==='accounting-allocation'){
      await require('./accounting-allocation-flow.cjs').accountingAllocationFlow({page,context,navigate,ready,login,fixture,screenshots,bootstrap:true});
      assert.deepEqual(pageErrors,[]);await context.close();
      console.log('1 targeted allocation browser workflow passed (real UI bootstrap; synthetic legacy invoice archives; production issuance accepted separately)');return;
    }

    const assistantAvailable=await page.locator('.navigation').getByRole('button',{name:'Assistent',exact:true}).count()===1;
    const serviceAvailable=await page.locator('.navigation').getByRole('button',{name:'Kundenservice',exact:true}).count()===1;
    assert.equal(await page.locator('.navigation button').count(),10+Number(assistantAvailable)+Number(serviceAvailable));
    assert.equal(await page.evaluate(()=>Object.keys(localStorage).length+Object.keys(sessionStorage).length),0);
    for(const section of ['Anfragen','Kontakte','Einsatzplanung','Dokumente','Finanzen','Material','Personal',...(assistantAvailable?['Assistent']:[]),...(serviceAvailable?['Kundenservice']:[]),'Einstellungen','Übersicht'])await navigate(page,section);
    console.log('browser: actual MFA login and all available areas loaded without API errors');
    await navigate(page,'Einstellungen');
    async function saveOrganization(){
      const current=page.locator('form[data-form^="organization-"]');
      const next=Number((await current.getAttribute('data-form')).split('-').at(-1))+1;
      await current.getByRole('button',{name:'Bedarf und Module speichern',exact:true}).click();
      await page.locator(`form[data-form="organization-${next}"]`).waitFor();await ready(page);
    }
    await page.getByLabel('Unser Unternehmen beschäftigt Mitarbeiter',{exact:true}).check();
    await page.getByLabel('Personal in der Navigation',{exact:true}).selectOption('hide');
    await saveOrganization();
    assert.equal(await page.locator('.navigation').getByRole('button',{name:'Personal',exact:true}).count(),0);
    assert.equal(await page.getByLabel('Personal in der Navigation',{exact:true}).inputValue(),'hide');
    await page.getByRole('button',{name:'Personal öffnen',exact:true}).click();await ready(page);
    await page.getByRole('heading',{name:'Personal & Zeiten',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Mitarbeiterprofil anlegen',exact:true}).count(),1);
    await navigate(page,'Einstellungen');
    await page.getByLabel('Personal in der Navigation',{exact:true}).selectOption('show');
    await page.getByLabel('Personal fachlich aktiv',{exact:true}).uncheck();await saveOrganization();
    await navigate(page,'Personal');
    assert.equal(await page.getByRole('button',{name:'Mitarbeiterprofil anlegen',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Zeit starten',exact:true}).count(),0);
    assert.ok(await page.locator('main').getByText('Dieser Bereich ist fachlich deaktiviert.',{exact:false}).count());
    assert.ok(await page.getByRole('heading',{name:'Synthetic owner',exact:true}).count());
    await navigate(page,'Einstellungen');
    await page.getByLabel('Unser Unternehmen beschäftigt Mitarbeiter',{exact:true}).uncheck();
    await page.getByLabel('Personal in der Navigation',{exact:true}).selectOption('auto');
    await page.getByLabel('Personal fachlich aktiv',{exact:true}).check();await saveOrganization();
    assert.equal(await page.locator('.navigation').getByRole('button',{name:'Personal',exact:true}).count(),1);
    console.log('browser: manual module visibility retained, hidden personnel opened by administrator, inactive history stayed readable and reactivation restored writes');
    await require('./portal-flow.cjs').portalFlow({page,context,navigate,ready,fixture,screenshots});
    await require('./accounting-flow.cjs').accountingFlow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./accounting-allocation-flow.cjs').accountingAllocationFlow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./component-flow.cjs').componentFlow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./refund-flow.cjs').refundFlow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./capacity-flow.cjs').capacityFlow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./refund-v2-flow.cjs').refundV2Flow({page,context,navigate,ready,login,fixture,screenshots});
    await require('./profile-flow.cjs').profileFlow({page,context,navigate,ready,login,fixture,screenshots});
    const {purchasingFlow,purchasingReadOnly,purchasingCatalogFlow}=require('./purchasing-flow.cjs');
    const purchaseOrderId=await purchasingFlow({page,context,navigate,ready,fixture,screenshots});
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);await navigate(page,'Einsatzplanung');
    await page.getByRole('button',{name:'Termin planen',exact:true}).click();let modal=page.getByRole('dialog',{name:'Termin planen',exact:true});
    const monday=await page.evaluate(()=>{const day=new Date();day.setDate(day.getDate()-((day.getDay()+6)%7));return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;});
    await modal.getByLabel('Termin',{exact:true}).fill('Synthetic browser schedule');await modal.getByLabel('Beginn (Gerätezeit)',{exact:true}).fill(monday+'T09:00');await modal.getByLabel('Ende (Gerätezeit)',{exact:true}).fill(monday+'T10:00');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const appointment=page.locator('.day').nth(0).locator('.appointment').filter({hasText:'Synthetic browser schedule'});
    const moved=page.waitForResponse(response=>response.url().includes('/business/appointments/')&&response.request().method()==='POST');
    await appointment.dragTo(page.locator('.day').nth(1));assert.equal((await moved).status(),200);await ready(page);await page.locator('.day').nth(1).locator('.appointment').filter({hasText:'Synthetic browser schedule'}).waitFor();
    console.log('browser: appointment form and drag-and-drop updated the same canonical calendar');
    await page.getByLabel('Aktuelles Projekt').selectOption('');await ready(page);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('month');await ready(page);
    await page.getByLabel('Monat auswählen',{exact:true}).fill('2030-12');await page.getByLabel('Monat auswählen',{exact:true}).press('Tab');await ready(page);
    assert.equal(await page.locator('.calendar-month .day').count(),31);
    assert.match(await page.locator('.calendar-month .day').first().getAttribute('aria-label'),/01\.12\.2030/);
    await page.getByRole('button',{name:'Weiter',exact:true}).click();await ready(page);
    assert.equal(await page.getByLabel('Monat auswählen',{exact:true}).inputValue(),'2031-01');
    assert.match(await page.locator('.calendar-month .day').first().getAttribute('aria-label'),/01\.01\.2031/);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('year');await ready(page);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2030');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    let timeline=page.locator('.timeline-row').filter({has:page.getByText('Synthetic Workshop',{exact:true})});
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2030-12-15');
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-end'),'2031-02-20');
    assert.equal(await timeline.locator('.timeline-project-bar.clipped-end').count(),1);
    const unplanned=page.locator('.timeline-row').filter({has:page.getByText('Private synthetic project',{exact:true})});
    assert.equal(await unplanned.locator('.timeline-project-bar').count(),0);assert.match(await unplanned.locator('.timeline-unplanned').textContent(),/Ungeplant/);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('multi');await ready(page);
    assert.equal(await page.locator('.timeline-tick').count(),36);
    assert.equal(await timeline.locator('.timeline-project-bar.clipped-end').count(),0);
    await timeline.getByRole('button',{name:'Projektzeitraum ändern: Synthetic Workshop',exact:true}).click();
    let datesModal=page.getByRole('dialog',{name:'Projektzeitraum: Synthetic Workshop',exact:true});
    await datesModal.getByLabel('Projektbeginn',{exact:true}).fill('2031-01-10');await datesModal.getByLabel('Projektende',{exact:true}).fill('2031-03-05');
    let releaseAck,arrived,failed;const held=new Promise(resolve=>releaseAck=resolve),received=new Promise((resolve,reject)=>{arrived=resolve;failed=reject;}),dateRoute='**/api/v1/business/planning/projects/*/dates';
    await context.route(dateRoute,async route=>{try{const response=await route.fetch({timeout:10000});assert.equal(response.status(),200);arrived();await held;await route.fulfill({response});}catch(error){failed(error);await route.abort('failed');}});
    try{await datesModal.getByRole('button',{name:'Zeitraum speichern',exact:true}).click();await received;assert.equal(await datesModal.isVisible(),true);assert.equal(await datesModal.getByRole('button',{name:'Zeitraum speichern',exact:true}).isDisabled(),true);}finally{releaseAck();}
    await datesModal.waitFor({state:'detached'});await ready(page);await context.unroute(dateRoute);
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2031-01-10');
    await page.reload();await login(page,'owner@browser.example.test',recovery[1]);await navigate(page,'Einsatzplanung');
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('year');await ready(page);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2031');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    timeline=page.locator('.timeline-row').filter({has:page.getByText('Synthetic Workshop',{exact:true})});
    assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-start'),'2031-01-10');assert.equal(await timeline.locator('.timeline-project-bar').getAttribute('data-end'),'2031-03-05');
    assert.ok((await timeline.locator('.timeline-project-bar').boundingBox()).width>0);
    await page.screenshot({path:path.join(screenshots,'timeline-year.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);assert.equal(await page.getByRole('region',{name:/Projektzeitleiste/}).getAttribute('tabindex'),'0');await page.screenshot({path:path.join(screenshots,'timeline-mobile.png'),fullPage:false});await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>!document.querySelector('.sidebar').inert);
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2200');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('multi');await page.getByRole('alert').waitFor();
    assert.equal(await page.getByLabel('Planungsansicht',{exact:true}).inputValue(),'year');
    await page.getByLabel('Planungsjahr',{exact:true}).fill('2031');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    // Exercise compatibility negotiation using the real response with only
    // the feature/readonly metadata reduced; authentication is never replaced.
    let compatibility='readonly';const capRoute='**/api/v1/business/capabilities';
    await context.route(capRoute,async route=>{const response=await route.fetch();const value=await response.json();await route.fulfill({response,json:compatibility==='readonly'?{...value,readonly:true}:{...value,features:[]}});});
    await navigate(page,'Einsatzplanung');assert.equal(await page.locator('.timeline-edit').count(),0);assert.ok(await page.locator('.timeline-project-bar').count());
    compatibility='legacy';await navigate(page,'Einsatzplanung');
    // Removing organization feature metadata rebuilds the shell before the
    // asynchronous legacy calendar is inserted. Wait for that actual view.
    await page.locator('.calendar .day').nth(6).waitFor({state:'visible'});await ready(page);
    assert.equal(await page.getByLabel('Planungsansicht',{exact:true}).count(),0);assert.equal(await page.locator('.timeline-row').count(),0);assert.equal(await page.locator('.calendar .day').count(),7);
    await context.unroute(capRoute);await navigate(page,'Einsatzplanung');
    await page.getByLabel('Planungsansicht',{exact:true}).selectOption('week');await ready(page);await page.getByRole('button',{name:'Heute',exact:true}).click();await ready(page);
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);
    console.log('browser: real month/year boundary, multi-year project bars, explicit unplanned rows and acknowledged dates persisted after new MFA login');
    await navigate(page,'Projekte');
    await page.getByRole('tab',{name:'Fotos & Doku',exact:true}).click();await ready(page);
    assert.equal(await page.locator('.photo-card').count(),12,'gallery must page originals and decoded previews');
    await page.getByRole('button',{name:'Weitere Fotos',exact:true}).click();await ready(page);assert.equal(await page.locator('.photo-card').count(),2);
    await page.getByRole('button',{name:'Tagesbericht hinzufügen',exact:true}).click();modal=page.getByRole('dialog',{name:'Bautagesbericht'});
    await modal.getByLabel('Titel',{exact:true}).fill('Synthetic browser diary');await modal.getByLabel('Ausgeführte Arbeiten',{exact:true}).fill('<img src=x onerror="window.__unsafe=true"> Synthetic work');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    await page.getByRole('heading',{name:'Synthetic browser diary',exact:true}).waitFor();assert.equal(await page.locator('img[src=x]').count(),0);assert.equal(await page.evaluate(()=>window.__unsafe),undefined);
    await page.getByRole('button',{name:'Foto aufnehmen / hochladen',exact:true}).click();modal=page.getByRole('dialog',{name:'Baustellenfoto',exact:true});
    await modal.getByLabel('Bildnotiz',{exact:true}).fill('Synthetic browser photo');await modal.getByLabel('Baustellenfoto auswählen',{exact:true}).setInputFiles(fixture.photo_path);await modal.getByRole('button',{name:'Original sicher hochladen',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const card=page.locator('.photo-card').filter({has:page.getByRole('heading',{name:'Synthetic browser photo',exact:true})});await card.waitFor();await card.scrollIntoViewIfNeeded();await card.locator('img').evaluate(image=>image.decode());assert.equal(await card.locator('img').evaluate(image=>image.naturalWidth),64);
    const downloadPromise=page.waitForEvent('download');await card.getByRole('button',{name:'Original',exact:true}).click();const download=await downloadPromise;
    assert.deepEqual(await fs.readFile(await download.path()),await fs.readFile(fixture.photo_path));
    console.log('browser: documentation created safely, original photo uploaded and downloaded byte-identically');
    await page.getByRole('button',{name:'Aufmaß erfassen',exact:true}).click();modal=page.getByRole('dialog',{name:'Metrisches Aufmaß',exact:true});
    await modal.getByLabel('Aufmaßbezeichnung',{exact:true}).fill('Synthetic browser measurement');await modal.getByLabel('Position / Bauteil',{exact:true}).fill('Floor');await modal.getByLabel('Länge in Metern',{exact:true}).fill('3,10');await modal.getByLabel('Breite in Metern',{exact:true}).fill('2,20');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    await page.getByRole('button',{name:'Prüfen & unterzeichnen',exact:true}).click();modal=page.getByRole('dialog',{name:'Fassung prüfen & unterzeichnen',exact:true});
    await modal.getByLabel('Name der unterzeichnenden Person',{exact:true}).fill('Synthetic browser signer');await modal.getByLabel('Ich bestätige die dargestellte Fassung',{exact:true}).check();
    const bounds=await modal.locator('canvas').boundingBox();await page.mouse.move(bounds.x+20,bounds.y+40);await page.mouse.down();await page.mouse.move(bounds.x+150,bounds.y+110,{steps:12});await page.mouse.up();await modal.getByRole('button',{name:'Fassung unterzeichnen',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const measured=page.locator('.list-row').filter({has:page.getByRole('heading',{name:'Synthetic browser measurement',exact:true})});await measured.getByText('Unterzeichnet',{exact:true}).waitFor();
    const pdfPromise=page.waitForEvent('download');await measured.getByRole('button',{name:'PDF',exact:true}).click();const pdf=await pdfPromise;assert.ok((await fs.readFile(await pdf.path())).subarray(0,5).equals(Buffer.from('%PDF-')));
    console.log('browser: decimal measurement and actual canvas signature produced a frozen PDF');
    await page.screenshot({path:path.join(screenshots,'desktop.png'),fullPage:true});
    await page.getByRole('button',{name:'Abmelden',exact:true}).click();await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();assert.equal(await page.getByText('Synthetic browser diary',{exact:true}).count(),0);
    await login(page,'technician@browser.example.test');assert.equal(await page.locator('.navigation').getByRole('button',{name:'Finanzen',exact:true}).count(),0);
    await purchasingReadOnly({page,navigate,ready,orderId:purchaseOrderId});
    assert.equal(await page.getByLabel('Aktuelles Projekt').locator('option').filter({hasText:'Private synthetic project'}).count(),0);
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);await navigate(page,'Projekte');await page.getByRole('tab',{name:'Fotos & Doku',exact:true}).click();await ready(page);assert.equal(await page.getByText('PRIVATE FINANCIAL RECEIPT',{exact:true}).count(),0);
    await navigate(page,'Einsatzplanung');await page.getByLabel('Planungsansicht',{exact:true}).selectOption('year');await ready(page);await page.getByLabel('Planungsjahr',{exact:true}).fill('2031');await page.getByLabel('Planungsjahr',{exact:true}).press('Tab');await ready(page);
    assert.equal(await page.locator('.timeline-edit').count(),0);assert.equal(await page.locator('.timeline-project-bar').count(),1);assert.equal(await page.getByText('Private synthetic project',{exact:true}).count(),0);
    await navigate(page,'Projekte');await page.getByRole('tab',{name:'Fotos & Doku',exact:true}).click();await ready(page);
    await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.equal(await page.locator('.sidebar').evaluate(sidebar=>sidebar.inert),true);
    await page.screenshot({path:path.join(screenshots,'mobile.png'),fullPage:false});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,'mobile page overflow');
    await page.getByRole('button',{name:'Navigation öffnen',exact:true}).click();await page.locator('.navigation').getByRole('button',{name:'Personal',exact:true}).click();await ready(page);
    assert.deepEqual(pageErrors,[]);
    console.log('browser: technician financial/project scope, logout clearing and 390px responsive view passed');
    await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>!document.querySelector('.sidebar').inert);
    await page.getByRole('button',{name:'Abmelden',exact:true}).click();await page.getByRole('heading',{name:'Willkommen im Büro.',exact:true}).waitFor();
    await login(page,'warehouse@browser.example.test');await purchasingCatalogFlow({page,context,navigate,ready,fixture,screenshots});
    await page.goto(fixture.base_url+'/office/contact.html');await page.getByRole('heading',{name:'Wie können wir helfen?',exact:true}).waitFor();
    let lost=true;const contactCalls=[];
    await context.route('**/api/v1/intake/contact',async route=>{
      if(new URL(route.request().url()).origin!==fixture.base_url){await route.abort();return;}
      contactCalls.push({body:route.request().postDataJSON(),headers:route.request().headers()});
      const response=await route.fetch();assert.equal(response.status(),201);
      if(lost){lost=false;await route.abort('failed');}else await route.fulfill({response});
    });
    await page.getByLabel('Ihr Name',{exact:true}).fill('Synthetic public sender');await page.getByLabel('Ihre E-Mail',{exact:true}).fill('public@browser.example.test');
    await page.getByLabel('Worum geht es?',{exact:true}).fill('Synthetic public website inquiry');await page.getByLabel('Ihre Nachricht',{exact:true}).fill('Synthetic callback, no confirmed order.');
    await page.getByLabel('Ich habe den Hinweis zur Verarbeitung meiner Anfrage gelesen.',{exact:true}).check();await page.getByRole('button',{name:'Anfrage übermitteln',exact:true}).click();
    await page.getByRole('alert').waitFor();await page.getByRole('button',{name:'Unverändert erneut übermitteln',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Ihre Anfrage ist eingegangen'}).waitFor();
    assert.match(await page.getByRole('status').textContent(),/Versand ist noch nicht bestätigt/);assert.equal(contactCalls.length,2);assert.equal(contactCalls[0].headers.authorization,undefined);assert.deepEqual(contactCalls[0].body,contactCalls[1].body);
    await page.goto(fixture.base_url+'/office/');await login(page,'owner@browser.example.test',recovery[0]);await navigate(page,'Anfragen');assert.equal(await page.getByRole('heading',{name:'Synthetic public website inquiry',exact:true}).count(),1);
    assert.deepEqual(pageErrors,[]);await context.close();
    console.log('browser: public form had no bearer, lost acknowledgement retried one inquiry and reply remained pending');
    console.log('17 real browser workflows passed (loopback transport fixture; TLS/Origin acceptance is separate)');
  }catch(error){
    console.error('SMARTPLAN_BROWSER_FAILURE_BEGIN');
    console.error(compactFailure(error));
    if(launchInfo)console.error('Browser launch context:',JSON.stringify(launchInfo));
    if(page){try{console.error('Visible alerts:',await page.locator('[role=alert]').allTextContents());}catch{console.error('Visible alerts: unavailable after browser failure');}console.error('Page errors:',pageErrors);console.error('Browser console errors:',consoleErrors);}
    if(output)console.error('Fixture log tail:\n'+output.slice(-1500));
    console.error('SMARTPLAN_BROWSER_FAILURE_END');
    process.exitCode=1;
  }
  finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill('SIGTERM');await Promise.race([new Promise(resolve=>server.once('exit',resolve)),delay(5000)]);if(server.exitCode===null)server.kill('SIGKILL');}await fs.rm(directory,{recursive:true,force:true});}
}
module.exports={compactFailure,namespaceSandboxArguments,assertNamespaceSandbox};
if(require.main===module)main();
