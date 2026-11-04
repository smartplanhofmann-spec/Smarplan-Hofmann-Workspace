import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {createAccountingEuer,EUER_PATH} from '../accounting-euer.js';

const f=JSON.parse(readFileSync(new URL('./fixtures/accounting-euer-legacy-context.json',import.meta.url)));
const clone=v=>structuredClone(v);
const input={euer_date:f.payload.euer_date,year_kind:'cash',reason:f.body.reason,evidence_reference:f.body.evidence_reference};
f.payload.lines.forEach((line,i)=>{for(const [key,value] of Object.entries(line))if(key!=='unit_id')input['u'+i+'_'+key]=value;});
function gate(){let enter,release;return{entered:new Promise(r=>enter=r),wait:new Promise(r=>release=r),enter,release};}
function host(data=f){
 let body=null,title='',dialogGeneration=0,render=0,hook;
 const errors=[],refreshes=[],requests=[],caps={readonly:false,features:['accounting_euer'],capabilities:['business_accounting_euer'],permissions:['accounting.read','finance.read','accounting.prepare','accounting.admin','finance.write'],organization:{modules:{finance:{enabled:true}}}};
 const node=(tag,attrs={},...children)=>({tag,attrs,dataset:{},isConnected:false,children:children.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false),append(...values){this.children.push(...values.flat(Infinity).filter(v=>v!==null&&v!==undefined&&v!==false));}});
 function connect(n,value){if(!n||typeof n!=='object')return;n.isConnected=value;for(const c of n.children||[])connect(c,value);}
 function close(){dialogGeneration++;connect(body,false);body=null;title='';}
 const api=new OfficeApi({fetcher:async(url,options)=>{const r={path:url.replace('/api/v1',''),method:options.method,body:options.body?JSON.parse(options.body):null};requests.push(r);const handled=await hook?.(r);if(handled)return handled;
  if(r.path==='/business/capabilities')return Response.json(caps);
  if(r.path==='/business'+EUER_PATH)return Response.json(data.state);
  if(r.path==='/business'+EUER_PATH+'/sources')return Response.json(data.sources);
  if(r.path==='/business'+EUER_PATH+'/preview'){assert.deepEqual(r.body,data.body);return Response.json(data.preview);}
  if(r.path==='/business'+EUER_PATH+'/confirm'){const {request_id,...sent}=r.body,{request_id:unused,...expected}=data.command;assert.ok(request_id);assert.deepEqual(sent,expected);return Response.json(data.accepted);}
  if(r.path.startsWith('/business'+EUER_PATH+'/journal'))return Response.json(data.journal);
  if(r.path.startsWith('/business'+EUER_PATH+'/report'))return Response.json(data.report);
  if(r.path==='/business/accounting/accounts')return Response.json(data.accounts);
  throw new Error('Unexpected legacy-only route '+r.path);
 }});api.setToken('synthetic-legacy-only-session');
 const ui={api,biz:p=>'/business'+p,el:node,button:(label,run)=>Object.assign(node('button',{},label),{label,run}),panel:(label,...children)=>node('panel',{label},...children),notice:label=>node('notice',{},label),table:(heads,rows)=>node('table',{},heads,rows),row:(...children)=>node('row',{},...children),rows:(values,fn)=>node('rows',{},values.map(fn)),
  form:(_,fields,save,options={})=>Object.assign(node('form',{},options.extra),{fields,save,options,controls:new Map(fields.map(spec=>[spec.name,{spec,input:{value:spec.value??'',checked:!!spec.value,addEventListener(){}}}])),async submit(values){try{const result=await save(values);if(result!==undefined){close();if(options.after)await options.after(result);else refreshes.push('default');}}catch(error){errors.push(error);}}}),
  dialog:(name,next)=>{dialogGeneration++;connect(body,false);body=next;title=name;connect(body,true);},closeModal:close,formatMoney:String,formatDate:String,refresh:async()=>{refreshes.push('refresh');},updatePending(){},
  action:async fn=>{try{return await fn();}catch(error){errors.push(error);}},mutation:(key,path,values,options)=>api.mutate(key,'/business'+path,values,options),organization:()=>caps.organization,
  context:()=>render,privateContext:()=>api.generation+'/'+render+'/'+dialogGeneration,onDenied:close,openItemsAvailable:()=>false,openCash(){},openEvent(){},openProfile(){},download(){},textDownload(){},jsonDownload(){},
 };
 if(!globalThis.navigator)Object.defineProperty(globalThis,'navigator',{value:{onLine:true},configurable:true});
 const euer=createAccountingEuer(ui),find=(fn,n=body)=>{if(!n||typeof n!=='object')return null;if(fn(n))return n;for(const c of n.children||[]){const value=find(fn,c);if(value)return value;}return null;};
 return{api,euer,caps,errors,refreshes,requests,close,hook(fn){hook=fn;},get body(){return body;},get title(){return title;},other(){close();body=node('other',{},'Unrelated new dialog');title='Other';connect(body,true);},session(){this.other();render++;api.setToken('synthetic-new-session');},button(label,n=body){const value=find(v=>v.label===label,n);assert.ok(value,label);return value;}};
}
async function open(h){const view=await h.euer.render();await h.button('Geldfluss fachlich buchen',view).run();assert.ok(h.body?.save,'Existing cash editor must open');return h.body;}

test('actual unchanged legacy cash source/preview/receipt works without opening-item feature',async()=>{
 const h=host(),editor=await open(h);assert.equal(f.sources.items[0].kind,'cash');await editor.save(clone(input));assert.equal(h.title,'EÜR-Buchung bestätigen');await h.body.submit({accepted:true});assert.equal(h.api.pendingCount,0);assert.equal(h.body,null);assert.equal(h.errors.length,0);assert.equal(h.requests.filter(r=>r.method==='POST').length,2);
});

for(const stage of ['initial','preview','confirm'])test('legacy cash held '+stage+' success cannot replace or close a newer dialog',async()=>{
 const h=host(),g=gate();let editor,view;
 if(stage==='initial')view=await h.euer.render();else{editor=await open(h);if(stage==='confirm'){await editor.save(clone(input));editor=h.body;}}
 const route='/business'+EUER_PATH+({initial:'/sources',preview:'/preview',confirm:'/confirm'})[stage];
 h.hook(async r=>{if(r.path===route){g.enter();await g.wait;return Response.json(({initial:f.sources,preview:f.preview,confirm:f.accepted})[stage]);}});
 const pending=stage==='initial'?h.button('Geldfluss fachlich buchen',view).run():editor.submit(stage==='confirm'?{accepted:true}:clone(input));await g.entered;h.other();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Actual legacy cash '+stage+' crossed dialog context: '+h.title);assert.deepEqual(h.refreshes,[]);assert.equal(h.errors.length,0);
 if(stage==='confirm')assert.equal(h.api.pendingCount,0);
});

for(const stage of ['initial','preview','confirm'])test('legacy cash late authorization denial at '+stage+' cannot close a newer dialog',async()=>{
 const h=host(),g=gate();let editor,view;if(stage==='initial')view=await h.euer.render();else{editor=await open(h);if(stage==='confirm'){await editor.save(clone(input));editor=h.body;}}
 h.hook(async r=>{if(r.path==='/business/capabilities'){g.enter();await g.wait;return Response.json({error:'Synthetic old cash authorization denied'},{status:403});}});
 const pending=stage==='initial'?h.button('Geldfluss fachlich buchen',view).run():editor.submit(stage==='confirm'?{accepted:true}:clone(input));await g.entered;h.other();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Actual legacy cash late authorization denial crossed '+stage+' context');assert.equal(h.errors.length,0);assert.deepEqual(h.refreshes,[]);
});

test('legacy cash held original source cannot display after live read revocation',async()=>{
 const h=host(),view=await h.euer.render(),g=gate();h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/sources'){g.enter();await g.wait;return Response.json(f.sources);}});
 const pending=h.button('Geldfluss fachlich buchen',view).run();await g.entered;h.caps.permissions=h.caps.permissions.filter(v=>v!=='finance.read');g.release();await pending;assert.equal(h.body,null);
});

test('legacy cash exact pending receipt cannot close another dialog after replay',async()=>{
 const h=host(),editor=await open(h),g=gate();let attempts=0;
 h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/confirm'){if(++attempts===1)throw new Error('Synthetic accepted legacy response lost');g.enter();await g.wait;return Response.json(f.accepted);}});
 await editor.save(clone(input));await h.body.submit({accepted:true});assert.equal(h.api.pendingCount,1);h.errors.length=0;h.close();await h.euer.openPending();
 const pending=h.button('Unveränderte Buchung erneut senden').run();await g.entered;h.other();const next=h.body;g.release();await pending;
 assert.ok(h.body===next,'Legacy original replay must not close unrelated dialog');assert.deepEqual(h.refreshes,[]);assert.equal(h.api.pendingCount,0);const posts=h.requests.filter(r=>r.path.endsWith('/confirm'));assert.deepEqual(posts[0].body,posts[1].body);
});

const followups=JSON.parse(readFileSync(new URL('./fixtures/accounting-euer-legacy-followups.json',import.meta.url)));
async function openFollowup(h,kind){const view=await h.euer.render();await h.button(kind==='correction'?'Buchung berichtigen':'Gegenbuchen',view).run();assert.ok(h.body?.save);return h.body;}
for(const kind of ['correction','reversal']){
 test('actual legacy cash '+kind+' preview and original receipt remain valid',async()=>{
  const data=followups[kind],h=host(data),editor=await openFollowup(h,kind);await editor.save(clone(input));assert.equal(h.title,'EÜR-Buchung bestätigen');await h.body.submit({accepted:true});assert.equal(h.errors.length,0);assert.equal(h.api.pendingCount,0);assert.equal(h.body,null);
  if(kind==='reversal'){assert.equal(data.preview.effect,null);assert.deepEqual(Object.keys(data.body.payload),['entry_id']);}
 });
 test('actual legacy cash '+kind+' late preview cannot cross dialog replacement',async()=>{
  const data=followups[kind],h=host(data),editor=await openFollowup(h,kind),g=gate();h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/preview'){assert.deepEqual(r.body,data.body);g.enter();await g.wait;return Response.json(data.preview);}});
  const pending=editor.submit(clone(input));await g.entered;h.other();const next=h.body;g.release();await pending;assert.ok(h.body===next);assert.equal(h.errors.length,0);assert.deepEqual(h.refreshes,[]);
 });
 test('actual legacy cash '+kind+' keeps original pending scope after UI clear',async()=>{
  const data=followups[kind],h=host(data),editor=await openFollowup(h,kind),g=gate();let attempts=0;
  h.hook(async r=>{if(r.path==='/business'+EUER_PATH+'/confirm'){if(++attempts===1)throw new Error('Actual accepted reply lost');g.enter();await g.wait;return Response.json(data.accepted);}});
  await editor.save(clone(input));await h.body.submit({accepted:true});assert.equal(h.api.pendingCount,1);h.errors.length=0;h.close();h.euer.clear();await h.euer.openPending();
  const pending=h.button('Unveränderte Buchung erneut senden').run();await g.entered;h.other();const next=h.body;g.release();await pending;
  assert.ok(h.body===next,'Original '+kind+' source scope was lost after UI clear');assert.deepEqual(h.refreshes,[]);assert.equal(h.api.pendingCount,0);
  const posts=h.requests.filter(r=>r.path.endsWith('/confirm'));assert.equal(posts.length,2);assert.deepEqual(posts[0].body,posts[1].body);
 });
}
