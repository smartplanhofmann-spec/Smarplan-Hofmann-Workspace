import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {accountingOpenItemsUi} from '../accounting-open-items.js';
import {createAccountingEuer, EUER_PATH} from '../accounting-euer.js';
import {OI_PATH,oiReceipt,oiUploadReceipt} from '../accounting-open-items-contract.js';
import {bankMatchInput,bankMatchPreview,bankReceipt} from '../bank-reconciliation.js';

// Domain facts are unmodified results from the real backend generator.
// Only transport timing and DOM connection state are controlled here.
const fixture=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_open_items_ui_v1.json',import.meta.url)));
const copy=v=>structuredClone(v),receivable=fixture.receivable_prior_parts,payable=fixture.payable_old_input_vat;
const capabilities=()=>({readonly:false,features:['accounting_open_items','accounting_euer'],capabilities:['business_accounting_open_items','business_accounting_euer'],permissions:['accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}});
function gate(){let release,enter;return{wait:new Promise(r=>release=r),entered:new Promise(r=>enter=r),release,enter};}
function harness(s=receivable){
 let body=null,title='',view=0,render=0,hook,workspace,euer,state=copy(s.state_after_item);
 const errors=[],downloads=[],requests=[],refreshes=[],serverCaps=capabilities(),localCaps=capabilities();
 const el=(tag,attrs={},...children)=>({tag,attrs,dataset:{},classList:{add(){}},children:children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false),isConnected:false,append(...more){this.children.push(...more.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false));}});
 function connect(n,value){if(!n||typeof n!=='object')return;n.isConnected=value;for(const c of n.children||[])connect(c,value);}
 function close(){view++;connect(body,false);workspace?.clear();body=null;title='';}
 const api=new OfficeApi({fetcher:async(url,options)=>{
  const r={path:url.replace('/api/v1',''),method:options.method,body:options.body?JSON.parse(options.body):null};requests.push(r);
  const special=await hook?.(r);if(special)return special;
  if(r.path==='/business/capabilities')return Response.json(serverCaps);
  if(r.path==='/business'+OI_PATH)return Response.json(state);
  if(r.path==='/business/accounting/accounts')return Response.json(s.accounts);
  if(r.path==='/business'+EUER_PATH)return Response.json({revision:0,state_hash:'0'.repeat(64),writes_allowed:true,profile_ready:true,periods:[]});
  if(r.path==='/business'+EUER_PATH+'/sources')return Response.json({...s.sources,items:s.sources.items.map(v=>({...v,current:null}))});
  if(r.path.startsWith('/business'+EUER_PATH+'/journal'))return Response.json({items:[],total:0,next_offset:null});
  if(r.path.startsWith('/business'+EUER_PATH+'/report'))return Response.json(s.report);
  throw new Error('Unexpected route '+r.path);
 }});api.setToken('independent-synthetic-session');
 const button=(label,run)=>Object.assign(el('button',{},label),{label,run});
 const ui={api,biz:p=>'/business'+p,el,button,field:(name,label,type,value,options)=>({name,label,type,value,...options}),
  form:(_,fields,save,options={})=>Object.assign(el('form',{},options.extra),{fields,save,options,async submit(values){try{const result=await save(values);if(result!==undefined){close();if(options.after)await options.after(result);else refreshes.push('default');}}catch(error){errors.push(error);}},controls:new Map(fields.map(spec=>[spec.name,{spec,input:{value:spec.value??'',checked:!!spec.value,addEventListener(){}}}]))}),
  panel:(label,...children)=>el('panel',{label},...children),table:(heads,rows)=>el('table',{},heads,rows),notice:label=>el('notice',{},label),
  row:(...children)=>el('row',{},...children),rows:(values,fn)=>el('rows',{},values.map(fn)),formatDate:String,formatMoney:String,
  available:()=>true,caps:()=>localCaps,stamp:()=>api.generation+'/'+view,context:()=>render,privateContext:()=>api.generation+'/'+render+'/'+view,organization:()=>localCaps.organization,
  updatePending(){},saveBlob:(blob,name)=>downloads.push({blob,name}),action:async fn=>{try{return await fn();}catch(e){errors.push(e);}},
  dialog:(nextTitle,next)=>{view++;connect(body,false);body=next;title=nextTitle;connect(body,true);},closeModal:close,refresh:async()=>{refreshes.push('refresh');},
  mutation:(key,path,values,options)=>api.mutate(key,'/business'+path,values,options),onDenied:close,
  openItemsAvailable:()=>true,openOpenItems:async()=>{},download:async()=>{},textDownload(){},jsonDownload(){},openCash(){},openEvent(){},openProfile(){},
 };
 workspace=accountingOpenItemsUi(ui);euer=createAccountingEuer(ui);
 const find=(fn,n=body)=>{if(!n||typeof n!=='object')return null;if(fn(n))return n;for(const c of n.children||[]){const r=find(fn,c);if(r)return r;}return null;};
 return{api,workspace,euer,errors,downloads,requests,refreshes,serverCaps,localCaps,close,find,
  button(label,n=body){const b=find(v=>v.label===label,n);assert.ok(b,label);return b;},
  other(){close();body=el('other',{},'Unrelated private dialog');title='Other';connect(body,true);},
  session(){close();api.setToken('independent-replacement-session');render++;},
  hook(fn){hook=fn;},get body(){return body;},get title(){return title;},set state(v){state=copy(v);},
 };
}

test('rendered historical and remaining cents are exact and old VAT is not offered again',async()=>{
 const h=harness();await h.workspace.detail(receivable.item.entity_key);
 const text=JSON.stringify(h.body);for(const amount of ['33.34','6.33','39.67','66.66','12.67','79.33'])assert.ok(text.includes(amount),amount);
 const p=harness(payable);await p.workspace.detail(payable.item.entity_key);
 assert.match(JSON.stringify(p.body),/Neue Lieferantenzahlungen erzeugen keinen zweiten Vorsteuerabzug/);
 assert.equal(p.find(v=>v.label?.includes('Vorsteuerabzug buchen')),null);
});

for(const transition of ['other','session','background'])for(const failure of [false,true])test('held original byte read '+(failure?'failure':'success')+' cannot cross '+transition,async()=>{
 const h=harness(),g=gate(),o=receivable.originals.find(v=>v.original_id===receivable.item.payload.invoice_proof.original_id),m=receivable.state_after_item.originals.find(v=>v.id===o.original_id);
 await h.workspace.detail(receivable.item.entity_key);
 h.hook(async r=>{if(r.path==='/business'+m.path){g.enter();await g.wait;return failure?Response.json({error:'Private old filename'},{status:409}):new Response(Buffer.from(o.content_base64,'base64'));}});
 const request=h.button(m.filename+' · '+m.sha256.slice(0,12)+' · Original ansehen').run();await g.entered;
 if(transition==='background'){h.workspace.clear();h.close();}else h[transition]();const next=h.body;
 g.release();await request;assert.equal(h.body,next);assert.equal(h.downloads.length,0);assert.equal(h.errors.length,0);
});

for(const transition of ['other','session','background'])test('held local original file before upload cannot cross '+transition,async()=>{
 const h=harness(),g=gate();await h.workspace.detail(receivable.item.entity_key);await h.button('Originalnachweis hochladen').run();
 const input=h.find(v=>v.tag==='input'),bytes=Buffer.from(receivable.originals[0].content_base64,'base64');
 input.files=[{name:'synthetic-private.pdf',type:'application/pdf',size:bytes.length,arrayBuffer:async()=>{g.enter();await g.wait;return bytes;}}];
 const pending=h.button('Ausgewähltes Original unverändert speichern').run();await g.entered;
 if(transition==='background')h.close();else h[transition]();const next=h.body;g.release();await pending;
 assert.equal(h.body,next);assert.equal(h.requests.filter(r=>r.method==='POST').length,0);assert.equal(h.errors.length,0);
});

test('download rejects altered original bytes and checks live read rights after correct bytes',async()=>{
 for(const corrupt of [true,false]){
  const h=harness(),o=receivable.originals.find(v=>v.original_id===receivable.item.payload.invoice_proof.original_id),m=receivable.state_after_item.originals.find(v=>v.id===o.original_id);
  await h.workspace.detail(receivable.item.entity_key);
  h.hook(async r=>{if(r.path==='/business'+m.path){if(!corrupt)h.serverCaps.permissions=h.serverCaps.permissions.filter(p=>p!=='finance.read');return new Response(corrupt?Buffer.from('different original'):Buffer.from(o.content_base64,'base64'));}});
  await h.button(m.filename+' · '+m.sha256.slice(0,12)+' · Original ansehen').run();assert.equal(h.downloads.length,0);assert.equal(h.errors.length,1);
  if(!corrupt){assert.equal(h.title,'Finanzzugriff nicht freigegeben');assert.ok(!JSON.stringify(h.body).includes(receivable.item.payload.invoice_number));}
 }
});

test('three pending original/item/payment intents survive advancement and exact independent replays',async()=>{
 const h=harness(),o=receivable.originals.find(v=>v.original_id===receivable.item.payload.invoice_proof.original_id),meta=receivable.state_after_item.originals.find(v=>v.id===o.original_id),bytes=Buffer.from(o.content_base64,'base64');
 const original={entity_key:o.entity_key,filename:o.filename,media_type:o.media_type,content_base64:o.content_base64};
 const item=copy(receivable.item_command),payment=copy(receivable.payments[0].command);delete item.request_id;delete payment.request_id;
 const entries=[
  {key:'accounting-open-item-original-'+o.entity_key,path:'/originals',body:original,result:meta,validate:oiUploadReceipt(original,{size:bytes.length,sha256:o.sha256})},
  {key:'accounting-open-item-confirm-'+item.entity_key,path:'/confirm',body:item,result:receivable.item,validate:oiReceipt(item,receivable.item_preview,receivable.initial_state)},
  {key:'accounting-open-item-confirm-'+payment.entity_key,path:'/confirm',body:payment,result:receivable.payments[0].payment,validate:oiReceipt(payment,receivable.payments[0].preview,receivable.state_after_item)},
 ];
 const attempts=new Map();h.hook(async r=>{if(r.method!=='POST')return;const count=(attempts.get(r.body.entity_key+r.path)||0)+1;attempts.set(r.body.entity_key+r.path,count);if(count===1)throw new Error('Synthetic accepted reply lost');return Response.json(entries.find(v=>v.path===r.path.slice(('/business'+OI_PATH).length)&&v.body.entity_key===r.body.entity_key).result);});
 for(const e of entries)await assert.rejects(h.api.mutate(e.key,'/business'+OI_PATH+e.path,e.body,{validate:e.validate}));
 assert.equal(h.api.pendingCount,3);h.state=receivable.final_state;
 for(const e of [...entries].reverse()){const originalSent=h.requests.find(r=>r.method==='POST'&&r.body.entity_key===e.body.entity_key&&r.path.endsWith(e.path)).body;await h.api.retry(e.key);const all=h.requests.filter(r=>r.method==='POST'&&r.body.entity_key===e.body.entity_key&&r.path.endsWith(e.path));assert.deepEqual(all.at(-1).body,originalSent);}
 assert.equal(h.api.pendingCount,0);
});

async function openEuer(h){
 if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
 const view=await h.euer.render();await h.button('Belegte Altpostenzahlung einordnen',view).run();assert.ok(h.body?.save);return h.body;
}
for(const transition of ['other','close'])test('EÜR held opening-item preview cannot restore a dismissed private editor after '+transition,async()=>{
 const h=harness(payable),editor=await openEuer(h),g=gate(),e=payable.payments[0].euer_entry;
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/preview'){g.enter();await g.wait;return Response.json({...e,...r.body});}});
 const pending=editor.save({net_account:'5400',tax_account:'1406',reason:'Original old tax already deducted',evidence_reference:'Actual original proof'});await g.entered;
 h[transition]();const next=h.body;g.release();await pending.catch(error=>h.errors.push(error));
 assert.ok(h.body===next,'A detached opening-item EÜR preview must not replace or reopen a private dialog; visible title: '+h.title);
});

for(const transition of ['other','session','background'])for(const failure of [false,true])test('late original upload '+(failure?'failure':'accepted receipt')+' cannot change '+transition,async()=>{
 const h=harness(),g=gate(),o=receivable.originals.find(v=>v.original_id===receivable.item.payload.invoice_proof.original_id),meta=receivable.state_after_item.originals.find(v=>v.id===o.original_id),bytes=Buffer.from(o.content_base64,'base64');
 await h.workspace.detail(receivable.item.entity_key);await h.button('Originalnachweis hochladen').run();h.find(v=>v.tag==='input').files=[{name:o.filename,type:o.media_type,size:bytes.length,arrayBuffer:async()=>bytes}];
 h.hook(async r=>{if(r.method==='POST'&&r.path.endsWith('/originals')){g.enter();await g.wait;return failure?Response.json({error:'Private original filename denied'},{status:409}):Response.json(meta);}});
 const pending=h.button('Ausgewähltes Original unverändert speichern').run();await g.entered;if(transition==='background')h.close();else h[transition]();const next=h.body;g.release();await pending;
 assert.ok(h.body===next);assert.equal(h.errors.length,0);assert.equal(h.requests.filter(r=>r.method==='POST').length,1);
});

for(const transition of ['other','close'])test('EÜR initial held source cannot open after '+transition,async()=>{
 const h=harness(payable);if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});const view=await h.euer.render(),g=gate();
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/sources'){g.enter();await g.wait;return Response.json({...payable.sources,items:payable.sources.items.map(v=>({...v,current:null}))});}});
 const pending=h.button('Belegte Altpostenzahlung einordnen',view).run();await g.entered;h[transition]();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Initial private EÜR source must not replace the changed dialog; visible title: '+h.title);
});

for(const transition of ['other','close'])test('EÜR late accepted opening-item confirmation cannot close newer dialog or refresh after '+transition,async()=>{
 const h=harness(payable),editor=await openEuer(h),g=gate(),e=payable.payments[0].euer_entry;let confirmedBody;
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/preview')return Response.json({...e,...r.body});if(r.path==='/business'+EUER_PATH+'/confirm'){confirmedBody=r.body;g.enter();await g.wait;return Response.json({...e,...Object.fromEntries(['reason','evidence_reference','operation','payload','preview_hash'].map(k=>[k,r.body[k]])),sequence:r.body.expected_revision+1,previous_hash:r.body.state_hash});}});
 await editor.save({net_account:'5400',tax_account:'1406',reason:'Actual historical VAT treatment',evidence_reference:'Original checked'});assert.equal(h.title,'EÜR-Buchung bestätigen');
 const confirm=h.body,pending=confirm.submit({accepted:true});await g.entered;h[transition]();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Late accepted command must not close another private dialog');assert.deepEqual(h.refreshes,[]);assert.ok(confirmedBody.request_id);assert.equal(h.api.pendingCount,0,'Actual original accepted receipt can resolve independently from visibility');
});

for(const stage of ['initial','preview','confirm'])test('EÜR late authorization denial at '+stage+' cannot close a newer private dialog',async()=>{
 const h=harness(payable),g=gate(),e=payable.payments[0].euer_entry;let editor,view;
 if(stage==='initial'){if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});view=await h.euer.render();}
 else{editor=await openEuer(h);if(stage==='confirm'){h.hook(async r=>r.path==='/business'+EUER_PATH+'/preview'?Response.json({...e,...r.body}):null);await editor.save({net_account:'5400',tax_account:'1406',reason:'Actual proof',evidence_reference:'Source'});editor=h.body;}}
 h.hook(async r=>{if(r.path==='/business/capabilities'){g.enter();await g.wait;return Response.json({error:'Private original old-item rights changed'},{status:403});}});
 const pending=stage==='initial'?h.button('Belegte Altpostenzahlung einordnen',view).run():editor.submit(stage==='confirm'?{accepted:true}:{net_account:'5400',tax_account:'1406',reason:'Proof',evidence_reference:'Source'});
 await g.entered;h.other();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Stale authorization denial must not invoke onDenied for a newer private dialog');assert.equal(h.errors.length,0);assert.deepEqual(h.refreshes,[]);
});

test('EÜR exact pending old-item replay ACK cannot close a newer dialog',async()=>{
 const h=harness(payable),editor=await openEuer(h),g=gate(),e=payable.payments[0].euer_entry;let attempts=0;
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/preview')return Response.json({...e,...r.body});if(r.path==='/business'+EUER_PATH+'/confirm'){if(++attempts===1)throw new Error('Server accepted original reply lost');g.enter();await g.wait;return Response.json({...e,...Object.fromEntries(['reason','evidence_reference','operation','payload','preview_hash'].map(k=>[k,r.body[k]])),sequence:r.body.expected_revision+1,previous_hash:r.body.state_hash});}});
 await editor.save({net_account:'5400',tax_account:'1406',reason:'Original historical tax',evidence_reference:'Bound original'});await h.body.submit({accepted:true});assert.equal(h.api.pendingCount,1);h.errors.length=0;h.close();await h.euer.openPending();
 const pending=h.button('Unveränderte Buchung erneut senden').run();await g.entered;h.other();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Accepted documentary replay must not close a newer dialog');assert.deepEqual(h.refreshes,[]);assert.equal(h.api.pendingCount,0);
 const posts=h.requests.filter(r=>r.path.endsWith('/euer/confirm'));assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);
});

const bank=JSON.parse(readFileSync(new URL('./fixtures/accounting-open-items-independent-bank.json',import.meta.url)));
test('EÜR opening-item source held across live read revocation cannot fill a private editor',async()=>{
 const h=harness(payable);if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});const view=await h.euer.render(),g=gate();
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/sources'){g.enter();await g.wait;return Response.json({...payable.sources,items:payable.sources.items.map(v=>({...v,current:null}))});}});
 const pending=h.button('Belegte Altpostenzahlung einordnen',view).run();await g.entered;h.serverCaps.permissions=h.serverCaps.permissions.filter(v=>v!=='finance.read');g.release();await pending;
 assert.equal(h.body,null,'A fresh read authorization after held source retrieval must prevent private editor display');
});
test('real SQLite old-item bank match binds one existing money source and original payment',()=>{
 const c=bank.candidates,p=bank.preview_match,s=c.items[0].source;
 assert.equal(s.source_kind,'opening_item_cash');assert.equal(s.source_id,bank.payment_source.id);assert.equal(s.origin_hash,bank.payment_source.source_hash);
 assert.equal(s.amount,'119.00');assert.equal(s.account.id,bank.payment_source.cash_movements[0].account.id);
 assert.deepEqual(bankMatchInput(c,{amount_0:'119,00',date_reason_0:'',reason:bank.preview_match_command.reason},[c.items[0]]),bank.preview_match_command);
 bankMatchPreview(p,bank.preview_match_command,c.transaction.id);bankReceipt('match',bank.save_match_command,p)(bank.save_match);
 for(const change of [s=>s.source_hash='f'.repeat(64),s=>s.account.id='e'.repeat(32),s=>s.source_id='d'.repeat(32)]){
  const selected=copy(c.items);change(selected[0].source);assert.throws(()=>bankMatchInput(c,{amount_0:'119.00',reason:'Source changed'},selected));
 }
 const changed=copy(p);changed.links[0].source.source_hash='f'.repeat(64);assert.throws(()=>bankMatchPreview(changed,bank.preview_match_command,c.transaction.id));
});
