import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,fx,base,block,edit,confirm,text} from './accounting-year-values-independent-harness.mjs';
import {yvReceipt,yvUploadReceipt} from '../accounting-year-values-contract.js';
function globals(t,h){for(const [name,value]of [['document',{get hidden(){return h.hidden;}}],['navigator',{onLine:true}]]){const old=Object.getOwnPropertyDescriptor(globalThis,name);Object.defineProperty(globalThis,name,{configurable:true,value});t.after(()=>old?Object.defineProperty(globalThis,name,old):delete globalThis[name]);}}
const denied=()=>Response.json({error:'Synthetic permission removed'},{status:403});
for(const error of [false,true])test('independent host: initial year response stays gone after background and return '+(error?'error':'success'),async t=>{
 const h=harness();globals(t,h);const b=block();h.hook(async r=>{if(r.path===base){b.entered.resolve();await b.release.promise;return error?denied():Response.json(fx.state);}});
 const task=h.yearUi.open();await b.entered.promise;h.visibility(true);h.visibility(false);b.release.resolve();await task;assert.equal(h.modal,null);assert.equal(h.title,'');
});
for(const loss of ['write','module'])test('independent preview: fresh '+loss+' withdrawal does not offer confirmation',async t=>{
 const h=harness();globals(t,h);const editor=await edit(h),b=block();h.hook(async r=>{if(r.path===base+'/preview'){b.entered.resolve();await b.release.promise;return Response.json(fx.preview);}});
 const task=editor.save(editor.values());await b.entered.promise;if(loss==='write')h.permission.permissions=h.permission.permissions.filter(v=>v!=='finance.write');else h.permission.organization.modules.finance.enabled=false;b.release.resolve();await task;
 assert.notEqual(h.title,'Jahresvortrag ausdrücklich bestätigen');assert.equal(h.requests.filter(v=>v.path===base+'/confirm').length,0);
});
for(const transition of ['other','session','background'])test('independent held preview error after '+transition+' never replaces current view',async t=>{
 const h=harness();globals(t,h);const editor=await edit(h),b=block();h.hook(async r=>{if(r.path===base+'/preview'){b.entered.resolve();await b.release.promise;return denied();}});
 const task=editor.save(editor.values());await b.entered.promise;if(transition==='background'){h.visibility(true);h.visibility(false);}else h[transition]();const body=h.modal,title=h.title;b.release.resolve();await task;
 assert.equal(h.modal,body);assert.equal(h.title,title);
});
for(const corruption of ['byte','length'])test('independent actual original '+corruption+' corruption cannot download',async t=>{
 const h=harness({accepted:true});globals(t,h);await h.yearUi.detail('2026');const o=fx.originals[0];h.hook(async r=>{if(r.path==='/business'+o.metadata.path){let b=Buffer.from(o.content_base64,'base64');if(corruption==='byte')b[0]^=1;else b=b.subarray(1);return new Response(b);}});
 await h.button(new RegExp('^'+o.metadata.filename)).run();assert.equal(h.downloads.length,0);assert.match(text(h.modal),/Originalbytes/);
});
test('independent actual opening-item original needs its own fresh source rights after bytes',async t=>{
 const h=harness({accepted:true});globals(t,h);await h.yearUi.detail('2026');const o=fx.opening_items_originals[0],b=block();h.hook(async r=>{if(r.path==='/business'+o.metadata.path){b.entered.resolve();await b.release.promise;return new Response(Buffer.from(o.content_base64,'base64'));}});
 const task=h.button(o.metadata.filename+' · '+o.metadata.sha256.slice(0,12)+' · Original ansehen').run();await b.entered.promise;h.permission.features=h.permission.features.filter(v=>v!=='accounting_open_items');b.release.resolve();await task;
 assert.equal(h.downloads.length,0);assert.equal(h.title,'Jahreswerte nicht freigegeben');assert.ok(h.permission.permissions.includes('finance.read'));assert.ok(h.permission.features.includes('accounting_year_values'));
});
test('independent upload lost ACK keeps actual file and exact nonce after closing',async t=>{
 const h=harness();globals(t,h);await h.yearUi.detail('2026');await h.button('Jahresoriginal unverändert hochladen').run();const o=fx.originals[0],bytes=Buffer.from(o.content_base64,'base64'),input=h.find(n=>n.tag==='input');
 input.files=[{name:o.metadata.filename,type:o.metadata.media_type,size:bytes.length,arrayBuffer:async()=>bytes}];let lost=true;
 h.hook(async r=>{if(r.path===base+'/originals'&&lost){lost=false;throw Error('Accepted upload response lost');}});
 await h.button('Ausgewähltes Jahresoriginal unverändert speichern').run();assert.equal(h.api.pendingCount,1);h.close();await h.yearUi.detail('2026');await h.button('Unverändert erneut senden').run();
 assert.equal(h.api.pendingCount,0);const calls=h.requests.filter(v=>v.path===base+'/originals');assert.equal(calls.length,2);assert.deepEqual(calls[0].body,calls[1].body);
});
test('independent second preview hash after dialog switch cannot reopen old confirmation',async t=>{
 const h=harness();globals(t,h);const editor=await edit(h),b=block(),subtle=crypto.subtle,original=subtle.digest;let count=0;
 subtle.digest=async function(algorithm,data){let decoded;try{decoded=JSON.parse(new TextDecoder().decode(data));}catch{}if(decoded?.operation==='year_values'&&decoded?.details&&decoded?.resolved_sources&&!decoded.preview_hash&&++count===2){b.entered.resolve();await b.release.promise;}return original.call(this,algorithm,data);};
 t.after(()=>subtle.digest=original);const task=editor.save(editor.values());await b.entered.promise;h.other();const body=h.modal;b.release.resolve();await task;assert.equal(h.modal,body);assert.equal(h.title,'Unbeteiligte Ansicht');
});
for(const error of [false,true])test('independent EÜR initial source after actual host background cycle '+(error?'error':'success')+' cannot reveal private year values',async t=>{
 const h=harness({accepted:true});globals(t,h);await h.renderEuer();const b=block();h.hook(async r=>{if(r.path==='/business/accounting/euer/sources'){b.entered.resolve();await b.release.promise;return error?denied():Response.json(fx.sources);}});
 const task=h.button('Frühere Jahreswerte ausdrücklich übernehmen').run();await b.entered.promise;h.visibility(true);h.visibility(false);b.release.resolve();await task;
 assert.equal(h.modal,null);assert.equal(h.title,'');assert.equal(h.errors.length,0);
});
test('independent EÜR displays actual historical VAT and cash dates without current cash',async t=>{
 const h=harness({accepted:true});globals(t,h);await h.renderEuer();await h.button('Frühere Jahreswerte ausdrücklich übernehmen').run();assert.match(text(h.modal),/keine neue Geldbewegung/);assert.match(text(h.modal),/-19.00/);assert.match(text(h.modal),/2026-08-20/);
 const editor=h.form();await editor.save({reason:fx.euer_body.reason,evidence_reference:fx.euer_body.evidence_reference});assert.equal(h.title,'EÜR-Buchung bestätigen');const sent=h.requests.find(v=>v.path==='/business/accounting/euer/preview');assert.deepEqual(sent.body,fx.euer_body);
});
