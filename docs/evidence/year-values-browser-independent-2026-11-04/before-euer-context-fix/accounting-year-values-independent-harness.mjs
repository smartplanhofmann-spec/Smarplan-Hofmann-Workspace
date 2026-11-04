import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {accountingYearValuesUi} from '../accounting-year-values.js';
import {createAccountingEuer} from '../accounting-euer.js';
export const fx=JSON.parse(readFileSync(new URL('./fixtures/accounting-year-values-euer-ui.json',import.meta.url)));
export const originalFixture=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_year_values_v1.json',import.meta.url)));
export const base='/business/accounting/year-values';
export function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};}
export function block(){return{entered:deferred(),release:deferred()};}
export function text(node){if(node===undefined||node===null)return'';if(typeof node!=='object')return String(node);return(node.children||[]).map(text).join(' ');}
function element(tag,attrs={},...children){return{tag,attrs,dataset:{},isConnected:false,children:children.flat(Infinity).filter(v=>v!==undefined&&v!==null&&v!==false),classList:{add(){}},append(...values){this.children.push(...values.flat(Infinity).filter(v=>v!==undefined&&v!==null&&v!==false));},replaceChildren(...values){this.children=[];this.append(...values);},querySelector(selector){return find(this,n=>(selector.includes('year-values')&&(n.dataset.yearValues||n.attrs?.['data-year-values']))||(selector.includes('euer-detail')&&(n.dataset.euerDetail||n.attrs?.['data-euer-detail'])));}};}
function connected(node,on){if(typeof node==='object'&&node){node.isConnected=on;for(const child of node.children||[])connected(child,on);}}
export function find(node,filter){if(!node||typeof node!=='object')return null;if(filter(node))return node;for(const child of node.children||[]){const value=find(child,filter);if(value)return value;}return null;}
export function harness({accepted=false}={}){
 let modal=null,title='',view=0,page=null,hook=null,state=structuredClone(accepted?fx.state:fx.before.state),hidden=false;
 const downloads=[],requests=[],errors=[],counters={pending:0,close:0,refresh:0},permission={readonly:false,features:['accounting_year_values','accounting_open_items','accounting_euer'],capabilities:['business_accounting_year_openings','business_accounting_open_items','business_accounting_euer'],permissions:['accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}};
 const api=new OfficeApi({fetcher:async(url,options)=>{const path=url.replace('/api/v1',''),body=options.body?JSON.parse(options.body):null,request={path,method:options.method,body};requests.push(request);const result=await hook?.(request);if(result)return result;
  if(path==='/business/capabilities')return Response.json(permission);
  if(path===base)return Response.json(state);
  if(path==='/business/accounting/open-items')return Response.json(fx.before.open_items);
  if(path===base+'/preview')return Response.json(fx.preview);
  if(path===base+'/confirm'){state=structuredClone(fx.state);return Response.json(fx.entry);}
  if(path===base+'/history?entity_key=2026')return Response.json(fx.history);
  if(path===base+'/originals')return Response.json(fx.originals[0].metadata);
  const original=[...fx.originals,...(fx.opening_items_originals||[])].find(v=>'/business'+v.metadata.path===path);
  if(original)return new Response(Buffer.from(original.content_base64,'base64'),{headers:{'Content-Type':original.metadata.media_type}});
  if(path==='/business/accounting/euer')return Response.json(fx.before.euer);
  if(path==='/business/accounting/euer/sources')return Response.json(fx.sources);
  if(path==='/business/accounting/euer/journal?limit=25&offset=0')return Response.json(fx.before.journal);
  if(path==='/business/accounting/euer/report?year=2026')return Response.json(fx.before.report);
  if(path==='/business/accounting/accounts')return Response.json(fx.before.accounts);
  if(path==='/business/accounting/euer/preview')return Response.json(fx.euer_preview);
  if(path==='/business/accounting/euer/confirm')return Response.json(fx.euer_entry);
  throw Error('Unmapped actual-fixture route '+path);
 }});api.setToken('independent-year-values-session');
 const close=()=>{counters.close++;view++;yearUi.clear();connected(modal,false);modal=null;title='';};
 const dialog=(name,node)=>{view++;connected(modal,false);modal=node;title=name;connected(node,true);};
 const form=(_title,fields,save,options={})=>{const node=element('form',{},options.extra);node.fields=fields;node.save=save;node.options=options;node.controls=new Map(fields.map(spec=>[spec.name,{spec,input:{value:spec.value??options.initial?.[spec.name]??'',checked:spec.value===true,listeners:{},addEventListener(event,fn){this.listeners[event]=fn;}}}]));node.values=()=>Object.fromEntries([...node.controls].map(([key,{input,spec}])=>[key,spec.type==='checkbox'?input.checked:input.value]));return node;};
 const common={api,biz:p=>'/business'+p,el:element,button:(label,run)=>Object.assign(element('button',{},label),{label,run}),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),form,panel:(name,...values)=>element('panel',{name},...values),table:(heads,rows)=>element('table',{},heads,rows),notice:message=>element('notice',{},message),dialog,formatDate:String,formatMoney:String,updatePending:()=>counters.pending++,row:(...values)=>element('row',{},...values),rows:(items,render)=>element('rows',{},items.map(render))};
 const yearUi=accountingYearValuesUi({...common,available:()=>true,caps:()=>permission,stamp:()=>api.generation+'/'+view,saveBlob:(blob,name)=>downloads.push({blob,name})});
 const euer=createAccountingEuer({...common,closeModal:close,organization:()=>permission.organization,context:()=>0,privateContext:()=>api.generation+'/'+view,action:async fn=>{try{return await fn();}catch(error){errors.push(error);}},mutation:(key,path,body,options)=>api.mutate(key,'/business'+path,body,options),refresh:async()=>{counters.refresh++;},onDenied:()=>{close();},yearValuesAvailable:()=>true,openYearValues:year=>year?yearUi.detail(year):yearUi.open()});
 const hostLine=readFileSync(new URL('../office.js',import.meta.url),'utf8').split('\n').find(v=>v.includes("document.addEventListener('visibilitychange'")&&v.includes('yearValuesWorkspace'));
 function visibility(on){hidden=on;const callbacks=[];const document={hidden,addEventListener:(_name,callback)=>callbacks.push(callback)};
  new Function('document','yearValuesWorkspace','modal','closeModal','accountingEuer',hostLine)(document,yearUi,modal,close,euer);
  for(const callback of callbacks)callback();
 }
 return{api,yearUi,euer,permission,requests,downloads,errors,counters,get modal(){return modal;},get title(){return title;},get page(){return page;},get hidden(){return hidden;},set state(value){state=structuredClone(value);},hook:value=>hook=value,form:()=>find(modal,n=>n.tag==='form'),find:filter=>find(modal,filter),button:label=>{const value=find(modal||page,n=>n.tag==='button'&&(typeof label==='string'?n.label===label:label.test(n.label)));assert.ok(value,'Button '+label+' absent in '+title);return value;},set:(name,value)=>{const node=find(modal,n=>n.tag==='form'),control=node.controls.get(name);assert.ok(control,name);control.input[control.spec.type==='checkbox'?'checked':'value']=value;for(const event of ['input','change'])control.input.listeners[event]?.();},close,other:()=>{close();dialog('Unbeteiligte Ansicht',element('div',{},'Unverändert privatfrei'));},session:()=>{close();api.setToken('independent-next-session');},visibility,renderEuer:async()=>{page=await euer.render();connected(page,true);return page;}};
}
export async function edit(h){
 await h.yearUi.open();await h.button('Frühere Jahreswerte vorbereiten').run();await h.button('Kanonischen Altposten auswählen').run();await h.button('Diese ursprüngliche Fassung auswählen').run();
 const s=fx.command.payload.sources[0];await h.form().save({...s.accounts,cash_0:s.cash_entry_keys[0],vat_key:s.vat_entry_key});
 for(const c of fx.command.payload.controls){await h.button('Ursprüngliche Kontrollsumme hinzufügen').run();for(const spec of h.form().fields.filter(v=>v.name.startsWith('control_')).slice(-4))h.set(spec.name,c[spec.name.split('_').at(-1)]);}
 for(const [name,value]of Object.entries({from:fx.command.payload.coverage.from,through:fx.command.payload.coverage.through,journal_original:fx.command.payload.ledger_proof.original_id,reason:fx.command.reason,...fx.command.payload.attestations}))h.set(name,value);
 return h.form();
}
export async function confirm(h){const editor=await edit(h);await editor.save(editor.values());assert.equal(h.title,'Jahresvortrag ausdrücklich bestätigen');return h.form();}
