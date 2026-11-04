import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi,StaleSession} from '../office.js';
import {accountingOpeningsUi,OPENING_PATH,openingReceiptValidator,openingUploadValidator,openingSources} from '../accounting-openings.js';

const f=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_openings_2026.json',import.meta.url)));
const copy=v=>structuredClone(v),accountId=f.saved.account_id,rootPath='/business'+OPENING_PATH;
const noNonce=v=>{const result=copy(v);delete result.request_id;return result;};
const capabilities=()=>({readonly:false,features:['accounting_opening_balances'],capabilities:['business_accounting_openings'],permissions:['accounting.read','finance.read','bank.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}});
const gate=()=>{let release,enter;return{released:new Promise(r=>release=r),entered:new Promise(r=>enter=r),release:()=>release(),enter:()=>enter()};};
const raw=Buffer.from(f.original_upload.content_base64,'base64');

// The real UI module receives a small deterministic DOM host. Closing a dialog
// invokes its real clear() hook exactly as Office's closeModal does. This is a
// controlled async test, not a claim of executing a browser or real HTTP server.
function harness({accepted=false}={}){
 let body=null,title='',view=0,hook=null,ui;const seen=[],errors=[],downloads=[];
 const serverCaps=capabilities(),localCaps=capabilities();let state=copy(accepted?f.state_after:f.state_before);
 function node(tag,attrs={},...children){return{tag,attrs,dataset:{},children:children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false),isConnected:false,append(...items){this.children.push(...items.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false));},replaceChildren(...items){this.children=[];this.append(...items);connect(this,true);}};}
 function connect(n,yes){if(!n||typeof n!=='object')return;n.isConnected=yes;for(const c of n.children||[])connect(c,yes);}
 function close(){if(body){connect(body,false);ui.clear();body=null;title='';}}
 const api=new OfficeApi({fetcher:async(url,options)=>{const path=url.replace('/api/v1',''),command=options.body?JSON.parse(options.body):null;seen.push({path,method:options.method,body:command});const overridden=await hook?.({path,method:options.method,body:command});if(overridden)return overridden;
   if(path==='/business/capabilities')return Response.json(serverCaps);
   if(path===rootPath)return Response.json(state);
   if(path===rootPath+'/sources?account_id='+accountId)return Response.json(f.sources);
   if(path===rootPath+'/accounts/'+accountId+'/history')return Response.json(f.history);
   if(path===rootPath+'/preview')return Response.json(f.preview);
   if(path===rootPath+'/confirm')return Response.json(f.saved);
   if(path===rootPath+'/originals')return Response.json(f.original);
   if(path===rootPath+'/originals/'+f.original.id)return new Response(raw,{headers:{'Content-Type':f.original.media_type}});
   throw new Error('Unexpected review route '+path);
 }});api.setToken('synthetic-independent-opening-context-session');
 ui=accountingOpeningsUi({api,biz:p=>'/business'+p,el:node,button:(label,run)=>Object.assign(node('button',{},label),{label,run}),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),form:(_title,fields,save,options)=>Object.assign(node('form',{},options.extra),{fields,save,options}),panel:(label,...items)=>node('panel',{label},...items),table:(heads,rows)=>node('table',{},heads,rows),notice:message=>node('notice',{},message),available:()=>true,caps:()=>localCaps,stamp:()=>api.generation+'/'+view,
   action:async fn=>{try{return await fn();}catch(error){errors.push(error);}},dialog:(name,next)=>{close();title=name;body=next;connect(body,true);},formatDate:String,formatMoney:String,updatePending:()=>{},saveBlob:(blob,name)=>downloads.push({blob,name})});
 function find(predicate,n=body){if(!n||typeof n!=='object')return null;if(predicate(n))return n;for(const c of n.children||[]){const found=find(predicate,c);if(found)return found;}return null;}
 return{api,ui,seen,errors,downloads,serverCaps,get body(){return body;},get title(){return title;},set state(v){state=copy(v);},hook:v=>{hook=v;},find,button:label=>{const v=find(n=>n.tag==='button'&&n.label===label);assert.ok(v,'Button '+label);return v;},close,other:()=>{close();body=node('other',{},'Unrelated private view');connect(body,true);title='Other';view++;},session:()=>{close();api.setToken('synthetic-independent-replacement-session');view++;}};
}
async function uploadForm(h){await h.ui.account(accountId);await h.button('Anfangsbestandsoriginal hochladen').run();return h.find(n=>n.tag==='input');}
async function editor(h){await h.ui.account(accountId);await h.button('Anfangsbestand aus Original vorbereiten').run();return h.find(n=>n.tag==='form');}
const values=()=>({source_choice:'original:'+f.original.id,amount:'1000.00',at_start_of_day:true,reason:f.preview_request.reason});
function file(read=async()=>raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)){return{name:f.original.filename,type:f.original.media_type,size:raw.length,arrayBuffer:read};}
async function withDigestHold(select,fn){const original=globalThis.crypto,hold=gate();let used=false;
 const wrapped={subtle:{digest:async(algorithm,bytes)=>{if(!used&&select(bytes)){used=true;hold.enter();await hold.released;}return original.subtle.digest(algorithm,bytes);}},getRandomValues:original.getRandomValues.bind(original),randomUUID:original.randomUUID.bind(original)};
 const descriptor=Object.getOwnPropertyDescriptor(globalThis,'crypto');Object.defineProperty(globalThis,'crypto',{configurable:true,value:wrapped});
 try{await fn(hold);}finally{hold.release();Object.defineProperty(globalThis,'crypto',descriptor);}
}

test('independent: a deferred file read cannot upload or reopen after dialog replacement',async()=>{
 const h=harness(),hold=gate(),input=await uploadForm(h);input.files=[file(async()=>{hold.enter();await hold.released;return raw;})];
 const pending=h.button('Ausgewähltes Original geschützt speichern').run();await hold.entered;h.other();const replacement=h.body;hold.release();await pending;
 assert.equal(h.body,replacement);assert.equal(h.title,'Other');assert.equal(h.api.pendingCount,0);assert.equal(h.seen.filter(v=>v.method==='POST').length,0);
});

test('independent: upload digest completion after session replacement performs no POST',async()=>{
 const h=harness(),input=await uploadForm(h);input.files=[file()];
 await withDigestHold(bytes=>Buffer.from(bytes).equals(raw),async hold=>{const pending=h.button('Ausgewähltes Original geschützt speichern').run();await hold.entered;h.session();hold.release();await pending;});
 assert.equal(h.body,null);assert.equal(h.api.pendingCount,0);assert.equal(h.seen.filter(v=>v.method==='POST').length,0);
});

test('independent: a genuine accepted preview DTO delivered after close cannot replace another dialog',async()=>{
 const h=harness(),form=await editor(h),hold=gate();h.hook(async request=>{if(request.path===rootPath+'/preview'){hold.enter();await hold.released;return Response.json(f.preview);}});
 const pending=form.save(values());await hold.entered;h.other();const replacement=h.body;hold.release();await pending;
 assert.equal(h.body,replacement);assert.equal(h.title,'Other');assert.equal(h.seen.filter(v=>v.path===rootPath+'/confirm').length,0);
});

test('independent: read revocation during original download discards bytes and removes private content',async()=>{
 const h=harness({accepted:true}),hold=gate();await h.ui.account(accountId);h.hook(async request=>{if(request.path===rootPath+'/originals/'+f.original.id){hold.enter();await hold.released;return new Response(raw);}});
 const pending=h.button('Gebundenes Original ansehen').run();await hold.entered;h.serverCaps.permissions=h.serverCaps.permissions.filter(v=>v!=='bank.read');hold.release();await pending;
 assert.equal(h.downloads.length,0);assert.equal(h.find(n=>n.tag==='table'),null);assert.equal(h.find(n=>n.tag==='button'),null);
 assert.ok(h.find(n=>n.tag==='notice'&&n.children.includes('Diese Finanzoriginale sind aktuell nicht freigegeben.')));
 assert.equal(h.title.includes(f.saved.account.name),false,'The private account name must not remain in the dialog title after read revocation.');
});

test('independent: original hash completion after close does not trigger a download',async()=>{
 const h=harness({accepted:true});await h.ui.account(accountId);
 await withDigestHold(bytes=>Buffer.from(bytes).equals(raw),async hold=>{const pending=h.button('Gebundenes Original ansehen').run();await hold.entered;h.close();hold.release();await pending;});
 assert.equal(h.downloads.length,0);assert.equal(h.body,null);
});

test('independent: upload lost ACK repeats exact original bytes and keeps hidden command payload private',async()=>{
 const h=harness(),input=await uploadForm(h);input.files=[file()];let lose=true;
 h.hook(async r=>{if(r.path===rootPath+'/originals'&&lose){lose=false;throw new Error('Synthetic accepted upload response lost');}});
 await h.button('Ausgewähltes Original geschützt speichern').run();assert.equal(h.api.pendingCount,1);
 const operations=h.api.pendingOperations();assert.deepEqual(operations,[{key:'accounting-opening-original-'+accountId,path:rootPath+'/originals'}]);
 assert.equal(JSON.stringify(operations).includes('content_base64'),false);h.close();await h.ui.account(accountId);await h.button('Ursprünglichen Originalauftrag erneut senden').run();
 const posts=h.seen.filter(v=>v.path===rootPath+'/originals'&&v.method==='POST');assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);assert.equal(posts[0].body.content_base64,f.original_upload.content_base64);assert.equal(h.api.pendingCount,0);
});

test('independent: an actual valid later receipt cannot acknowledge an earlier pending command',async()=>{
 const posts=[],body=noNonce(f.command),key='accounting-opening-confirm-'+accountId;let replacement=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return Response.json(url.includes('/capabilities')?capabilities():f.state_after_correction);posts.push(JSON.parse(options.body));return Response.json(replacement?f.correction:f.saved);}});api.setToken('synthetic-independent-validated-receipt-session');
 await assert.rejects(api.mutate(key,rootPath+'/confirm',body,{validate:openingReceiptValidator(body,f.preview,f.state_before)}));assert.equal(api.pendingCount,1);
 replacement=false;await api.retry(key);assert.equal(api.pendingCount,0);assert.deepEqual(posts[0],posts[1]);
});

test('independent: real cryptographic receipt validation after session change cannot consume a new pending request',async()=>{
 const body=noNonce(f.command),key='accounting-opening-confirm-'+accountId,api=new OfficeApi({fetcher:async()=>Response.json(f.saved)});api.setToken('synthetic-independent-old-receipt-session');
 await withDigestHold(()=>true,async hold=>{const pending=api.mutate(key,rootPath+'/confirm',body,{validate:openingReceiptValidator(body,f.preview,f.state_before)});await hold.entered;api.setToken('synthetic-independent-new-receipt-session');
   await assert.rejects(api.mutate(key,rootPath+'/confirm',body,{validate:()=>{throw new Error('Synthetic unresolved replacement');}}));const replacement=api.pendingCommandValues(key,rootPath+'/confirm');hold.release();await assert.rejects(pending,StaleSession);assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,rootPath+'/confirm'),replacement);
 });
});

test('independent: self-consistent actual account source from another fixture is not a current selection',async()=>{
 await assert.rejects(openingSources(f.bank.sources,f.bank.saved.account_id,f.state_before));
 const source=copy(f.sources);source.profile_ref={...source.profile_ref,revision:source.profile_ref.revision+1};await assert.rejects(openingSources(source,accountId,f.state_before));
 const validator=openingUploadValidator(noNonce(f.original_upload),{size:f.original.size,sha256:f.original.sha256});assert.throws(()=>validator({...f.original,size:f.original.size+1}));
});
