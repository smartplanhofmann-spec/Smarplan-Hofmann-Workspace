import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {historicalAssetsUi} from '../accounting-historical-assets.js';
const f=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_historical_assets_2026.json',import.meta.url))),clone=structuredClone;
const base='/business/accounting/historical-assets',identity={asset_key:f.saved.asset_key,inventory_number:f.saved.asset.inventory_number};
const caps=()=>({readonly:false,features:['accounting_historical_assets'],capabilities:['business_accounting_asset_openings'],permissions:['accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}});
const gate=()=>{let release,enter;return{released:new Promise(r=>release=r),entered:new Promise(r=>enter=r),release:()=>release(),enter:()=>enter()};};
const raw=Buffer.from(f.original_upload.content_base64,'base64');

// Actual UI and OfficeApi, controlled asynchronous transport and minimal DOM;
// the separate Chromium workflow proves actual browser rendering and HTTP.
function harness(accepted=false){
 let body=null,title='',version=0,ui,hook=null;const seen=[],errors=[],downloads=[],permissions=caps();
 function node(tag,attrs={},...children){return{tag,attrs,dataset:{},children:children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false),isConnected:false,append(...v){this.children.push(...v.flat(Infinity));}};}
 function connect(n,on){if(!n||typeof n!=='object')return;n.isConnected=on;for(const c of n.children||[])connect(c,on);}
 function close(){if(body){connect(body,false);ui.clear();body=null;title='';}}
 const api=new OfficeApi({fetcher:async(url,options)=>{const path=url.replace('/api/v1',''),command=options.body?JSON.parse(options.body):null;seen.push({path,method:options.method,body:command});const result=await hook?.({path,method:options.method,body:command});if(result)return result;
  if(path==='/business/capabilities')return Response.json(permissions);
  if(path===base)return Response.json(accepted?f.state_after:f.state_before);
  if(path===base+'/preview')return Response.json(f.preview);
  if(path===base+'/confirm')return Response.json(f.saved);
  if(path===base+'/originals')return Response.json(f.original);
  if(path===base+'/originals/'+f.original.id)return new Response(raw);
  if(path===base+'/history?asset_key='+identity.asset_key)return Response.json(f.history);
  throw Error('Unexpected synthetic route '+path);
 }});api.setToken('synthetic-assets-context');
 ui=historicalAssetsUi({api,biz:p=>'/business'+p,el:node,button:(label,run)=>Object.assign(node('button',{},label),{label,run}),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),form:(_title,fields,save,options)=>Object.assign(node('form',{},options.extra),{fields,save,options}),panel:(name,...children)=>node('panel',{name},...children),table:(heads,rows)=>node('table',{},heads,rows),notice:text=>node('notice',{},text),available:()=>true,caps,stamp:()=>api.generation+'/'+version,action:async fn=>{try{return await fn();}catch(e){errors.push(e);}},dialog:(name,next)=>{close();title=name;body=next;connect(body,true);},formatDate:String,formatMoney:String,updatePending:()=>{},saveBlob:(blob,name)=>downloads.push({blob,name})});
 function find(predicate,n=body){if(!n||typeof n!=='object')return null;if(predicate(n))return n;for(const c of n.children||[]){const v=find(predicate,c);if(v)return v;}return null;}
 return{api,ui,seen,errors,downloads,permissions,find,close,get body(){return body;},get title(){return title;},hook:fn=>{hook=fn;},button:label=>{const found=find(v=>v.tag==='button'&&v.label===label);assert.ok(found,label);return found;},other:()=>{close();body=node('other',{},'Other view');title='Other';connect(body,true);version++;},session:()=>{close();api.setToken('synthetic-new-assets-context');version++;}};
}
async function upload(h){await h.ui.detail(identity);await h.button('Historisches Anlagenoriginal hochladen').run();return h.find(n=>n.tag==='input');}
async function editor(h){await h.ui.detail(identity);await h.button('Anlagenwerte aus Original vorbereiten').run();return h.find(n=>n.tag==='form');}
const values=()=>({...clone(f.preview_request.asset),...clone(f.preview_request.source),original_id:f.original.id,reason:f.preview_request.reason});

test('deferred file bytes after view replacement never create an original or reopen private UI',async()=>{
 const h=harness(),held=gate(),input=await upload(h);input.files=[{name:f.original.filename,type:f.original.media_type,size:raw.length,arrayBuffer:async()=>{held.enter();await held.released;return raw;}}];
 const pending=h.button('Ausgewähltes Anlagenoriginal speichern').run();await held.entered;h.other();const replacement=h.body;held.release();await pending;assert.equal(h.body,replacement);assert.equal(h.seen.filter(v=>v.method==='POST').length,0);assert.equal(h.api.pendingCount,0);
});
test('genuine delayed preview after dialog close cannot reopen confirmation or post acceptance',async()=>{
 const h=harness(),form=await editor(h),held=gate();h.hook(async r=>{if(r.path===base+'/preview'){held.enter();await held.released;return Response.json(f.preview);}});
 const pending=form.save(values());await held.entered;h.other();const replacement=h.body;held.release();await pending;assert.equal(h.body,replacement);assert.equal(h.seen.filter(v=>v.path===base+'/confirm').length,0);
});
test('fresh financial read revocation during download hides original title and prevents use of bytes',async()=>{
 const h=harness(true),held=gate();await h.ui.detail(identity);h.hook(async r=>{if(r.path===base+'/originals/'+f.original.id){held.enter();await held.released;return new Response(raw);}});
 const pending=h.button('Gebundenes Anlagenoriginal ansehen').run();await held.entered;h.permissions.permissions=h.permissions.permissions.filter(p=>p!=='finance.read');held.release();await pending;
 assert.equal(h.downloads.length,0);assert.equal(h.title,'Finanzzugriff nicht freigegeben');assert.equal(h.find(n=>n.tag==='table'),null);assert.equal(JSON.stringify(h.body).includes(identity.inventory_number),false);
});
test('deferred original hash after background close never triggers a download',async()=>{
 const h=harness(true);await h.ui.detail(identity);const original=globalThis.crypto,held=gate(),descriptor=Object.getOwnPropertyDescriptor(globalThis,'crypto');
 Object.defineProperty(globalThis,'crypto',{configurable:true,value:{subtle:{digest:async(algorithm,bytes)=>{if(Buffer.from(bytes).equals(raw)){held.enter();await held.released;}return original.subtle.digest(algorithm,bytes);}},getRandomValues:original.getRandomValues.bind(original),randomUUID:original.randomUUID.bind(original)}});
 try{const pending=h.button('Gebundenes Anlagenoriginal ansehen').run();await held.entered;h.close();held.release();await pending;assert.equal(h.downloads.length,0);assert.equal(h.body,null);}finally{held.release();Object.defineProperty(globalThis,'crypto',descriptor);}
});
test('revoked editor rights remove private inputs before any preview request',async()=>{
 const h=harness(),form=await editor(h);h.permissions.permissions=h.permissions.permissions.filter(p=>p!=='accounting.read');await assert.rejects(form.save(values()),e=>e.status===403);assert.equal(h.title,'Finanzzugriff nicht freigegeben');assert.equal(h.find(n=>n.tag==='form'),null);assert.equal(h.seen.filter(v=>v.path===base+'/preview').length,0);
});
