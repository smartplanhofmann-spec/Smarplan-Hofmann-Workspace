/* Real Chromium + disposable loopback Flask/auth/SQLite. No providers or token injection. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs/promises');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require('playwright');
const PASSWORD='Synthetic-browser-password-123';
const delay=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
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
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'smartplan-browser-e2e-')),readyFile=path.join(directory,'ready.json');
  const screenshots=process.env.SMARTPLAN_BROWSER_SCREENSHOT_DIR||directory;
  let browser,server,page;let output='';const pageErrors=[],consoleErrors=[];
  try{
    await fs.mkdir(screenshots,{recursive:true,mode:0o700});
    const python=process.env.SMARTPLAN_BROWSER_TEST_PYTHON||'python3';
    server=spawn(python,[path.join(__dirname,'serve_fixture.py'),'--ready-file',readyFile],{env:{PATH:process.env.PATH,LANG:'C.UTF-8',TZ:'Europe/Berlin',PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
    for(const stream of [server.stdout,server.stderr])stream.on('data',chunk=>{output=(output+chunk.toString()).slice(-15000);});
    let fixture;
    for(let index=0;index<300;index++){try{fixture=JSON.parse(await fs.readFile(readyFile,'utf8'));break;}catch(error){if(error.code!=='ENOENT')throw error;if(server.exitCode!==null)throw new Error('Fixture exited: '+output);await delay(50);}}
    assert.ok(fixture,'fixture did not become ready');
    let executable=process.env.SMARTPLAN_CHROMIUM_BINARY;
    if(executable===undefined){try{await fs.access('/usr/bin/chromium');executable='/usr/bin/chromium';}catch{executable='';}}
    // Explicit empty override selects Playwright's pinned bundled browser in CI.
    browser=await chromium.launch({...executable?{executablePath:executable}:{},headless:true,chromiumSandbox:true,args:['--enable-automation']});
    const debug=await browser.newBrowserCDPSession();
    const command=await debug.send('Browser.getBrowserCommandLine');
    assert.ok(!command.arguments.some(argument=>['--no-sandbox','--disable-web-security','--ignore-certificate-errors'].includes(argument)),'browser security must remain enabled');
    await debug.detach();
    const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'de-DE',timezoneId:'Europe/Berlin',acceptDownloads:true});
    await context.route('**/*',route=>new URL(route.request().url()).origin===fixture.base_url?route.continue():route.abort());
    page=await context.newPage();page.on('pageerror',error=>pageErrors.push(error.message));page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});page.setDefaultTimeout(15000);
    await page.goto(fixture.base_url+'/office/');
    const recovery=await login(page,'owner@browser.example.test');
    assert.equal(await page.locator('.navigation button').count(),10);
    assert.equal(await page.evaluate(()=>Object.keys(localStorage).length+Object.keys(sessionStorage).length),0);
    for(const section of ['Anfragen','Kontakte','Einsatzplanung','Dokumente','Finanzen','Material','Personal','Einstellungen','Übersicht'])await navigate(page,section);
    console.log('browser: actual MFA login and all ten areas loaded without API errors');
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);await navigate(page,'Einsatzplanung');
    await page.getByRole('button',{name:'Termin planen',exact:true}).click();let modal=page.getByRole('dialog',{name:'Termin planen',exact:true});
    const monday=await page.evaluate(()=>{const day=new Date();day.setDate(day.getDate()-((day.getDay()+6)%7));return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`;});
    await modal.getByLabel('Termin',{exact:true}).fill('Synthetic browser schedule');await modal.getByLabel('Beginn (Gerätezeit)',{exact:true}).fill(monday+'T09:00');await modal.getByLabel('Ende (Gerätezeit)',{exact:true}).fill(monday+'T10:00');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const appointment=page.locator('.day').nth(0).locator('.appointment').filter({hasText:'Synthetic browser schedule'});
    const moved=page.waitForResponse(response=>response.url().includes('/business/appointments/')&&response.request().method()==='POST');
    await appointment.dragTo(page.locator('.day').nth(1));assert.equal((await moved).status(),200);await ready(page);await page.locator('.day').nth(1).locator('.appointment').filter({hasText:'Synthetic browser schedule'}).waitFor();
    console.log('browser: appointment form and drag-and-drop updated the same canonical calendar');
    await navigate(page,'Projekte');
    await page.getByRole('tab',{name:'Fotos & Doku',exact:true}).click();await ready(page);
    assert.equal(await page.locator('.photo-card').count(),12,'gallery must page originals and decoded previews');
    await page.getByRole('button',{name:'Weitere Fotos',exact:true}).click();await ready(page);assert.equal(await page.locator('.photo-card').count(),2);
    await page.getByRole('button',{name:'Tagesbericht hinzufügen',exact:true}).click();modal=page.getByRole('dialog',{name:'Bautagesbericht'});
    await modal.getByLabel('Titel',{exact:true}).fill('Synthetic browser diary');await modal.getByLabel('Ausgeführte Arbeiten',{exact:true}).fill('<img src=x onerror="window.__unsafe=true"> Synthetic work');await modal.getByRole('button',{name:'Speichern',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    await page.getByRole('heading',{name:'Synthetic browser diary',exact:true}).waitFor();assert.equal(await page.locator('img[src=x]').count(),0);assert.equal(await page.evaluate(()=>window.__unsafe),undefined);
    await page.getByRole('button',{name:'Foto aufnehmen / hochladen',exact:true}).click();modal=page.getByRole('dialog',{name:'Baustellenfoto',exact:true});
    await modal.getByLabel('Bildnotiz',{exact:true}).fill('Synthetic browser photo');await modal.getByLabel('Baustellenfoto auswählen',{exact:true}).setInputFiles(fixture.photo_path);await modal.getByRole('button',{name:'Original sicher hochladen',exact:true}).click();await modal.waitFor({state:'detached'});await ready(page);
    const card=page.locator('.photo-card').filter({has:page.getByRole('heading',{name:'Synthetic browser photo',exact:true})});await card.waitFor();assert.equal(await card.locator('img').evaluate(image=>image.naturalWidth),64);
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
    assert.equal(await page.getByLabel('Aktuelles Projekt').locator('option').filter({hasText:'Private synthetic project'}).count(),0);
    await page.getByLabel('Aktuelles Projekt').selectOption(fixture.project_id);await ready(page);await navigate(page,'Projekte');await page.getByRole('tab',{name:'Fotos & Doku',exact:true}).click();await ready(page);assert.equal(await page.getByText('PRIVATE FINANCIAL RECEIPT',{exact:true}).count(),0);
    await page.setViewportSize({width:390,height:844});
    await page.waitForFunction(()=>document.querySelector('.sidebar').getBoundingClientRect().right<=1);
    assert.equal(await page.locator('.sidebar').evaluate(sidebar=>sidebar.inert),true);
    await page.screenshot({path:path.join(screenshots,'mobile.png'),fullPage:false});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert.equal(overflow,false,'mobile page overflow');
    await page.getByRole('button',{name:'Navigation öffnen',exact:true}).click();await page.locator('.navigation').getByRole('button',{name:'Personal',exact:true}).click();await ready(page);
    assert.deepEqual(pageErrors,[]);
    console.log('browser: technician financial/project scope, logout clearing and 390px responsive view passed');
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
    console.log('6 real browser workflows passed (loopback transport fixture; TLS/Origin acceptance is separate)');
  }catch(error){console.error(error.stack||error);if(page){console.error('Visible alerts:',await page.locator('[role=alert]').allTextContents());console.error('Page errors:',pageErrors);console.error('Browser console errors:',consoleErrors);}if(output)console.error('Fixture log tail:\n'+output.slice(-3500));process.exitCode=1;}
  finally{if(browser)await browser.close();if(server&&server.exitCode===null){server.kill('SIGTERM');await Promise.race([new Promise(resolve=>server.once('exit',resolve)),delay(5000)]);if(server.exitCode===null)server.kill('SIGKILL');}await fs.rm(directory,{recursive:true,force:true});}
}
main();
