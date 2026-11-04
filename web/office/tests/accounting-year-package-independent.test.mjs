import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi,StaleSession} from '../office.js';
import {createAccountingEuer} from '../accounting-euer.js';
import {accountingYearPackageUi} from '../accounting-year-package.js';
import {yearPackageArchive,yearPackageMetadata} from '../accounting-year-package-contract.js';

const fixture=JSON.parse(readFileSync(new URL('./fixtures/accounting-year-package-independent.json',import.meta.url)));
const original=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_year_package_v1.json',import.meta.url)));
const copy=structuredClone,first=fixture.first,second=fixture.second;
const base='/business/accounting/euer/exports/';
const gate=()=>{let enter,release;return{entered:new Promise(r=>enter=r),wait:new Promise(r=>release=r),enter,release};};
const caps=()=>({features:['accounting_euer','accounting_year_evidence_v1'],capabilities:['business_accounting_euer'],permissions:['accounting.read','finance.read'],readonly:true});
function host(){
 let body=null,title='',render=0,dialog=0,hook,packages;
 const downloads=[],errors=[],requests=[],permissions=caps(),sources=[first,second,...Object.values(original.scenarios)];
 const el=(tag,attrs={},...children)=>({tag,attrs,isConnected:false,children:children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false),append(...values){this.children.push(...values.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false));}});
 const connect=(n,value)=>{if(!n||typeof n!=='object')return;n.isConnected=value;for(const c of n.children||[])connect(c,value);};
 function close(){dialog++;if(body?.attrs['data-year-package'])packages.clear();connect(body,false);body=null;title='';}
 const api=new OfficeApi({fetcher:async(url,options)=>{const path=url.replace('/api/v1','');requests.push({path,method:options.method});const custom=await hook?.(path);if(custom)return custom;
  if(path==='/business/capabilities')return Response.json(permissions);
  if(path==='/business/accounting/euer')return Response.json(fixture.state);
  for(const s of sources){if(path===base+s.export.entry_id)return Response.json(s.export);if(path==='/business'+s.metadata.archive_path)return new Response(Buffer.from(s.archive_base64,'base64'),{headers:{'Content-Type':'application/zip'}});if(path==='/business'+s.metadata.archive_path.replace('/archive',''))return Response.json(s.metadata);}
  throw new Error('Unexpected year-package route '+path);
 }});api.setToken('synthetic-independent-year-session');
 const ui={api,biz:p=>'/business'+p,el,button:(label,run)=>Object.assign(el('button',{},label),{label,run}),notice:text=>el('notice',{},text),table:(heads,rows)=>el('table',{},heads,rows),panel:(label,...children)=>el('panel',{},label,...children),row:(...children)=>el('row',{},...children),rows:(values,fn)=>el('rows',{},values.map(fn)),
  available:()=>true,caps:()=>permissions,stamp:()=>api.generation+'/'+render+'/'+dialog,context:()=>render,privateContext:()=>api.generation+'/'+render+'/'+dialog,organization:()=>null,
  dialog:(name,next)=>{close();body=next;title=name;connect(body,true);},closeModal:close,formatMoney:String,formatDate:String,
  saveBlob:(blob,name)=>downloads.push({kind:'zip',blob,name}),jsonDownload:(value,name)=>downloads.push({kind:'json',value,name}),textDownload:(value,name)=>downloads.push({kind:'csv',value,name}),
  action:async fn=>{try{return await fn();}catch(error){if(!(error instanceof StaleSession)&&error.name!=='StaleSession')errors.push(error);}},onDenied:close,
  yearPackageAvailable:()=>true,openYearPackage:value=>packages.open(value),refresh:async()=>{},updatePending(){},form(){throw new Error('No mutation form in read-only review');},
 };
 if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{configurable:true,value:{onLine:true}});
 packages=accountingYearPackageUi(ui);const euer=createAccountingEuer(ui);
 const find=(fn,n=body)=>{if(!n||typeof n!=='object')return null;if(fn(n))return n;for(const c of n.children||[]){const found=find(fn,c);if(found)return found;}return null;};
 return{api,euer,packages,permissions,downloads,errors,requests,close,hook:fn=>hook=fn,get body(){return body;},get title(){return title;},
  button(label){const value=find(n=>n.label===label);assert.ok(value,label);return value;},text:()=>JSON.stringify(body),
  other(){close();body=el('other',{},'Unrelated private dialog');title='Other';connect(body,true);},session(){this.other();api.setToken('synthetic-independent-new-year-session');render++;packages.clear();},
  background(){globalThis.document={hidden:true};packages.clear();euer.invalidateExport?.();if(body?.attrs['data-year-package']||body?.attrs['data-year-export'])close();},foreground(){globalThis.document={hidden:false};},
  async export(s=first){return ui.action(()=>euer.exported(s.export.entry_id));},
 };
}
test.afterEach(()=>{delete globalThis.document;});

test('real readonly export entry opens exactly its package and incomplete original remains incomplete',async()=>{
 const h=host();await h.export();assert.equal(h.title,'Gespeichertes Jahresprüfpaket');await h.button('Jahresnachweis mit Originalen öffnen').run();assert.equal(h.title,'Jahresnachweis mit Originalen');await h.button('Gebundenes Belegpaket herunterladen').run();assert.equal(h.downloads.length,1);assert.equal(h.downloads[0].name,first.metadata.filename);
 await h.export(second);await h.button('Jahresnachweis mit Originalen öffnen').run();assert.match(h.text(),/damalige Jahresstand enthält offene Quellen/);assert.ok(h.requests.every(v=>v.method==='GET'));assert.equal(h.errors.length,0);
});

for(const failed of [false,true])test('initial original export '+(failed?'error':'success')+' cannot return after background and foreground',async()=>{
 const h=host(),held=gate();h.hook(async path=>{if(path===base+first.export.entry_id){held.enter();await held.wait;return failed?Response.json({error:'PRIVATE OLD YEAR EXPORT'},{status:409}):Response.json(first.export);}});
 const pending=h.export();await held.entered;assert.equal(h.body,null);h.background();h.foreground();held.release();await pending;
 assert.equal(h.body,null,'A first export response must remain invalid after the document returned to foreground');assert.equal(h.errors.length,0);assert.equal(h.downloads.length,0);
});

test('latest original export intent wins before either initial request created a dialog',async()=>{
 const h=host(),a=gate(),b=gate();h.hook(async path=>{if(path===base+first.export.entry_id){a.enter();await a.wait;return Response.json(first.export);}if(path===base+second.export.entry_id){b.enter();await b.wait;return Response.json(second.export);}});
 const old=h.export();await a.entered;const latest=h.export(second);await b.entered;a.release();await old;b.release();await latest;
 assert.equal(h.title,'Gespeichertes Jahresprüfpaket');assert.ok(h.text().includes(second.export.report_sha256),'The explicitly later original export must remain selected');assert.ok(!h.text().includes(first.export.report_sha256));
});

for(const phase of ['metadata','binary'])for(const change of ['session','export','background'])for(const failed of [false,true])test('held '+phase+' '+(failed?'error':'success')+' is discarded after '+change,async()=>{
 const h=host(),held=gate();if(phase==='binary')await h.packages.open(first.export);
 const path='/business'+first.metadata.archive_path+(phase==='metadata'?'':'');
 h.hook(async value=>{if(value===(phase==='metadata'?path.replace('/archive',''):path)){held.enter();await held.wait;if(failed)return Response.json({error:'PRIVATE PREVIOUS YEAR PACKAGE'},{status:409});}});
 const pending=phase==='metadata'?h.packages.open(first.export):h.button('Gebundenes Belegpaket herunterladen').run();await held.entered;
 if(change==='session')h.session();else if(change==='export')await h.packages.open(second.export);else{h.background();h.foreground();}
 const next=h.body;held.release();await pending;assert.ok(h.body===next);assert.equal(h.downloads.length,0);assert.equal(h.errors.length,0);
});

test('fresh individual-source denial after ZIP does not rely on unchanged global read rights',async()=>{
 const h=host();await h.packages.open(first.export);let metadataReads=0;
 h.hook(path=>{if(path==='/business'+first.metadata.archive_path.replace('/archive','')&&++metadataReads===2)return Response.json({error:'Synthetic original project access withdrawn'},{status:403});});
 await h.button('Gebundenes Belegpaket herunterladen').run();assert.deepEqual(h.permissions.permissions,['accounting.read','finance.read']);assert.equal(metadataReads,2);assert.equal(h.downloads.length,0);assert.equal(h.title,'Jahresnachweis nicht freigegeben');assert.ok(!h.text().includes(first.export.entry_id));
});

for(const kind of ['json','csv'])test('old '+kind+' original reread cannot leak after choosing a different export',async()=>{
 const h=host();await h.export();const held=gate();h.hook(async path=>{if(path===base+first.export.entry_id){held.enter();await held.wait;return Response.json(first.export);}});
 const pending=h.button(kind==='json'?'JSON-Prüfpaket herunterladen':'CSV-Buchungsnachweise herunterladen').run();await held.entered;await h.export(second);const next=h.body;held.release();await pending;assert.ok(h.body===next);assert.equal(h.downloads.length,0);assert.equal(h.errors.length,0);
});

test('archive corruption, truncation, unsupported type and authenticated metadata drift never output a file',async()=>{
 const raw=Buffer.from(first.archive_base64,'base64'),changed=Buffer.from(raw);changed[changed.length-1]^=1;for(const blob of [new Blob([raw.subarray(1)],{type:'application/zip'}),new Blob([raw],{type:'text/plain'}),new Blob([changed],{type:'application/zip'})])await assert.rejects(yearPackageArchive(blob,first.metadata));
 for(const [key,value]of [['export_hash','e'.repeat(64)],['year',2025],['instance_id','d'.repeat(32)],['original_year_complete',false],['original_count',first.metadata.original_count+1]]){
  const h=host();await h.packages.open(first.export);let count=0;h.hook(path=>path==='/business'+first.metadata.archive_path.replace('/archive','')&&++count===2?Response.json({...first.metadata,[key]:value}):null);
  await h.button('Gebundenes Belegpaket herunterladen').run();assert.equal(h.downloads.length,0,key);assert.equal(h.title,'Jahresnachweis nicht verfügbar',key);
 }
});

test('incomplete and public-only payroll/travel years retain their actual boundaries',async()=>{
 for(const key of ['incomplete_year','public_payroll','public_travel']){
  const s=original.scenarios[key],h=host();await h.packages.open(s.export);assert.equal(h.title,'Jahresnachweis mit Originalen');assert.match(h.text(),/Keine Steuererklärung/);
  if(!s.metadata.original_year_complete)assert.match(h.text(),/damalige Jahresstand enthält offene Quellen/);
  if(key!=='incomplete_year'){assert.match(h.text(),/Private Personaloriginale sind nicht enthalten/);assert.throws(()=>yearPackageMetadata({...copy(s.metadata),private_source_boundaries:[]},s.export));}
 }
});
