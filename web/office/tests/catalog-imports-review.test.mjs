import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {catalogImportsUi} from '../catalog-imports.js';
import {OfficeApi} from '../office.js';

const adapterId='a'.repeat(32),runId='b'.repeat(32);
const caps={capabilities:['business_adapters','business_catalog_imports'],permissions:['settings.manage','finance.read','finance.write'],readonly:false,features:['organization_modules'],organization:{modules:{documents:{enabled:true,visible:true}}}};
const bytes=Buffer.from('code;name;unit;cost_price_net;unit_price_net;tax_rate\nSYN;Synthetic;ST;1;2;19\n');
const source={id:adapterId,name:'Independent synthetic source',profile:'catalog_csv_v1',enabled:true};
const run={id:runId,adapter_id:adapterId,profile:source.profile,status:'staged',source_sha256:createHash('sha256').update(bytes).digest('hex'),rows:[{code:'SYN',name:'Synthetic',unit:'ST',cost_price_net:'1',unit_price_net:'2',tax_rate:'19'}],result:{target_revisions:{}}};
const preview={run_id:runId,source_sha256:run.source_sha256,profile:source.profile,price_mapping:{},preview_sha256:'d'.repeat(64),rows:[{code:'SYN',action:'create',article_id:null,revision:null,before:null,after:{...run.rows[0],kind:'material',currency:'EUR',active:true,cost_known:true,tax_category:'S',tax_exemption_reason:'',components:[]}}]};
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};

// A small DOM model exercises the actual UI callbacks and OfficeApi request
// retention, without replacing either by the exported token helper alone.
class Element {
 constructor(tag,attrs={},...children){this.tag=tag;this.attrs=attrs;this.children=[];this.parent=null;this.listeners=new Map();Object.assign(this,attrs);this.append(...children);}
 get isConnected(){return this.root===true||Boolean(this.parent?.isConnected);}
 append(...values){for(const child of values.flat(Infinity)){if(child===null||child===undefined||child===false)continue;if(child instanceof Element)child.parent=this;this.children.push(child);}}
 replaceChildren(...children){for(const child of this.children)if(child instanceof Element)child.parent=null;this.children=[];this.append(...children);}
 prepend(...children){const old=this.children;this.children=[];this.append(...children,...old);}
 remove(){if(this.parent){this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}}
 get textContent(){return this.children.map(child=>child instanceof Element?child.textContent:String(child)).join(' ');}
 set textContent(value){this.replaceChildren(value);}
 addEventListener(name,callback){this.listeners.set(name,callback);}
 async emit(name){return this.listeners.get(name)?.();}
 walk(){return [this,...this.children.filter(child=>child instanceof Element).flatMap(child=>child.walk())];}
 querySelectorAll(selector){return this.walk().filter(node=>selector==='input,select'?['input','select'].includes(node.tag):selector==='button.primary'?node.tag==='button'&&node.attrs.class==='primary':selector==='[data-catalog-error]'?node.attrs['data-catalog-error']:false);}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
}

function harness(){
 const previousDocument=globalThis.document,previousObserver=globalThis.MutationObserver;
 const root=new Element('body');root.root=true;const listeners=new Map();let stamp='session/1',title='',rights=structuredClone(caps),readHook=null,postHook=null;
 const calls=[];
 globalThis.document={body:root,visibilityState:'visible',addEventListener:(name,fn)=>listeners.set(name,fn)};
 globalThis.MutationObserver=class{observe(){}disconnect(){}};
 const api=new OfficeApi({fetcher:async(url,options)=>{
  const path=new URL(url,'https://synthetic.test').pathname.replace('/api/v1','');
  if(options.method==='POST'){const body=JSON.parse(options.body);if(path.endsWith('/catalog-preview')){await readHook?.(path);return Response.json(preview);}calls.push({path,body});await postHook?.(path,body);return Response.json(path.endsWith('/apply')?{...run,status:'applied',result:{article_ids:['c'.repeat(32)]}}:run);}
  await readHook?.(path);
  if(path.endsWith('/capabilities'))return Response.json(rights);
  if(path==='/business/adapters')return Response.json({items:[source]});
  if(path.endsWith('/imports'))return Response.json({items:[],offset:0,limit:20,total:0});
  if(path==='/business/articles')return Response.json({items:[]});
  throw new Error('Unexpected synthetic read '+path);
 }});api.setToken('synthetic-independent-catalog-session');
 const el=(tag,attrs,...children)=>new Element(tag,attrs,...children);
 const ui=catalogImportsUi({api,el,button:(caption,fn,className)=>{const node=el('button',{class:className},caption);node.listeners.set('click',fn);return node;},notice:(text,kind)=>el('p',{'data-notice':kind},text),panel:(heading,...children)=>el('section',{},heading,...children),table:(headers,rows)=>el('table',{},headers,rows),dialog:(next,body)=>{title=next;root.replaceChildren(body);},closeModal:()=>{title='';root.replaceChildren();},stamp:()=>stamp,caps:()=>rights,available:()=>true,formatDate:value=>String(value),saveBlob:()=>assert.fail('No download expected')});
 const button=caption=>{const node=root.walk().find(node=>node.tag==='button'&&node.textContent===caption);assert.ok(node,'Button missing: '+caption+' in '+root.textContent);return node;};
 return {api,ui,calls,root,title:()=>title,button,click:caption=>button(caption).emit('click'),picker:()=>root.walk().find(node=>node.tag==='input'&&node.type==='file'),rights:value=>rights=value,read:hook=>readHook=hook,post:hook=>postHook=hook,
  hidden(){document.visibilityState='hidden';listeners.get('visibilitychange')();},visible(){document.visibilityState='visible';listeners.get('visibilitychange')();},stamp(value){stamp=value;},
  cleanup(){ui.clear();globalThis.document=previousDocument;globalThis.MutationObserver=previousObserver;}};
}
async function upload(h){await h.ui.open();await h.click('Katalog öffnen');await h.click('Katalogdatei auswählen');const picker=h.picker();picker.files=[{name:'synthetic.csv',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}];await picker.emit('change');}
async function nextDialog(h){h.hidden();assert.equal(h.title(),'');h.visible();await h.ui.open();assert.equal(h.title(),'Lieferantenkataloge und Adapter');}
async function decisionReady(h){for(let i=0;i<25&&!h.root.textContent.includes('1 neu · 0 geändert · 0 unverändert');i++)await new Promise(resolve=>setImmediate(resolve));assert.match(h.root.textContent,/1 neu · 0 geändert · 0 unverändert/);}

for(const failure of [false,true])test(`late file ${failure?'failure':'bytes'} after background cannot alter a newly opened catalog dialog`,async()=>{
 const h=harness();try{await upload(h);const gate=deferred(),picker=h.picker();picker.files=[{name:'late-private.csv',size:bytes.length,arrayBuffer:()=>gate.promise}];const pending=picker.emit('change');await nextDialog(h);failure?gate.reject(new Error('LATE PRIVATE FILE ERROR')):gate.resolve(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));await pending;assert.equal(h.title(),'Lieferantenkataloge und Adapter');assert.doesNotMatch(h.root.textContent,/late-private|LATE PRIVATE/);assert.equal(h.calls.length,0);}finally{h.cleanup();}
});

for(const failure of [false,true])test(`late import ${failure?'error':'ACK'} after background cannot replace or contaminate the next dialog`,async()=>{
 const h=harness();try{await upload(h);const gate=deferred(),arrived=deferred();h.post(async()=>{arrived.resolve();await gate.promise;});const save=h.click('Datei prüfen und Vorschau laden');await arrived.promise;await nextDialog(h);failure?gate.reject(new Error('LATE PRIVATE SAVE ERROR')):gate.resolve();await save;assert.equal(h.title(),'Lieferantenkataloge und Adapter');assert.doesNotMatch(h.root.textContent,/LATE PRIVATE|SHA-256/);assert.equal(h.api.pendingCount,failure?1:0);}finally{h.cleanup();}
});

test('lost import ACK survives closing, background and reopening with the same request_id and original file',async()=>{
 const h=harness();try{await upload(h);let lose=true;h.post(()=>{if(lose){lose=false;throw new Error('Synthetic accepted response lost');}});await h.click('Datei prüfen und Vorschau laden');assert.equal(h.api.pendingCount,1);await nextDialog(h);await h.click('Katalog öffnen');await h.click('Ursprüngliche Antwort erneut prüfen');assert.equal(h.title(),'Import prüfen · '+source.name);assert.deepEqual(h.calls[0],h.calls[1]);assert.equal(h.api.pendingCount,0);}finally{h.cleanup();}
});

test('lost apply ACK retains confirmed command through close and the original OfficeApi retry',async()=>{
 const h=harness();try{await upload(h);await h.click('Datei prüfen und Vorschau laden');await decisionReady(h);const confirmation=h.root.walk().find(node=>node.tag==='input'&&node.type==='checkbox');confirmation.checked=true;let lose=true;h.post(path=>{if(path.endsWith('/apply')&&lose){lose=false;throw new Error('Accepted, ACK lost');}});await h.click('Artikel ausdrücklich übernehmen');assert.equal(h.api.pendingCount,1);await nextDialog(h);await h.api.retry('catalog-apply-'+runId);assert.deepEqual(h.calls[1],h.calls[2]);assert.equal(h.title(),'Lieferantenkataloge und Adapter');assert.equal(h.api.pendingCount,0);}finally{h.cleanup();}
});

test('write withdrawal closes the actual confirmation editor before any acceptance POST',async()=>{
 const h=harness();try{await upload(h);await h.click('Datei prüfen und Vorschau laden');await decisionReady(h);h.root.walk().find(node=>node.tag==='input'&&node.type==='checkbox').checked=true;h.rights({...caps,permissions:caps.permissions.filter(value=>value!=='finance.write')});await h.click('Artikel ausdrücklich übernehmen');assert.equal(h.title(),'');assert.equal(h.calls.filter(call=>call.path.endsWith('/apply')).length,0);}finally{h.cleanup();}
});

test('delayed readonly decision cannot refill a backgrounded preview after another dialog opens',async()=>{
 const h=harness();try{await upload(h);const gate=deferred(),arrived=deferred();h.read(async path=>{if(path.endsWith('/catalog-preview')){arrived.resolve();await gate.promise;}});const save=h.click('Datei prüfen und Vorschau laden');await arrived.promise;await nextDialog(h);gate.resolve();await save;await new Promise(resolve=>setImmediate(resolve));assert.equal(h.title(),'Lieferantenkataloge und Adapter');assert.doesNotMatch(h.root.textContent,/Artikel ausdrücklich übernehmen|USt./);}finally{h.cleanup();}
});

for(const withdrawal of ['write','module'])test(`delayed readonly decision closes its existing editor after ${withdrawal} withdrawal while read access remains`,async()=>{
 const h=harness();try{
  await upload(h);const gate=deferred(),arrived=deferred();
  h.read(async path=>{if(path.endsWith('/catalog-preview')){arrived.resolve();await gate.promise;}});
  const save=h.click('Datei prüfen und Vorschau laden');await arrived.promise;
  assert.match(h.title(),/^Import prüfen/);
  h.rights(withdrawal==='write'?{...caps,permissions:caps.permissions.filter(value=>value!=='finance.write')}:{...caps,organization:{modules:{documents:{enabled:false,visible:true}}}});
  gate.resolve();await save;
  for(let i=0;i<10&&h.title();i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(h.title(),'','the stale editor must close despite retained read authority');
  assert.equal(h.root.walk().some(node=>node.tag==='button'&&node.textContent==='Artikel ausdrücklich übernehmen'),false);
  assert.equal(h.calls.filter(call=>call.path.endsWith('/apply')).length,0);
 }finally{h.cleanup();}
});
