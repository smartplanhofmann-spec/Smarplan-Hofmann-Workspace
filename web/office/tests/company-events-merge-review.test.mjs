import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi,StaleSession} from '../office.js';
import {companyEventsUi,companyEventDataAuthorize} from '../company-events.js';
import {eventReceipt,eventHash,eventPlan,eventStates} from '../company-events-contract.js';

const fixture=JSON.parse(readFileSync(new URL('../../../docs/fixtures/company_events_2026.json',import.meta.url)));
const copy=value=>structuredClone(value);
const caps=()=>({features:['company_event_rules'],capabilities:['business_company_events'],readonly:false,permissions:['assistant.use','settings.manage','assistant.approve','documents.read','projects.manage','finance.read','finance.write','finance.approve']});
const defer=()=>{let release,enter;return {ready:new Promise(r=>enter=r),done:new Promise(r=>release=r),enter:()=>enter(),release:()=>release()};};
const scenarios=Object.values(fixture).filter(v=>v&&typeof v==='object'&&v.project_id);
const allPlans=scenarios.flatMap(v=>v.plans.items),allEvents=scenarios.flatMap(v=>v.events.items);
const withoutNonce=body=>{const next=copy(body);delete next.request_id;return next;};
async function accepted(path,body,value){const result=copy(value),suffix=path.slice('/business/company-events/'.length);const operation=suffix==='scan'?'scan':suffix==='rules'?'rule':suffix.split('/')[2]+':'+suffix.split('/')[1];result.acceptance={request_id:body.request_id,operation,request_hash:await eventHash([operation,body])};return result;}

// Independent deterministic UI host. It follows Office dialogGeneration and
// clear(), but does not claim a real browser or independently reimplement DOM.
function harness(scenario='approval'){
 const f=fixture[scenario],globalCaps=caps(),projectCaps=new Map(),requests=[],errors=[];
 let modal=null,view=0,dialogGeneration=0,hook=null,ui;
 function node(tag,attrs={},...items){const n={tag,attrs:{...attrs},dataset:{},children:items.flat(Infinity).filter(v=>v!=null&&v!==false),isConnected:false,classList:{add(){}},setAttribute(k,v){this.attrs[k]=v;},append(...values){this.children.push(...values.flat(Infinity).filter(v=>v!=null&&v!==false));if(this.isConnected)connect(this,true);},replaceChildren(...values){for(const child of this.children)connect(child,false);this.children=[];this.append(...values);},querySelectorAll(selector){return walk(this).filter(child=>selector.split(',').includes(child.tag));}};return n;}
 function walk(n){return !n||typeof n!=='object'?[]:[n,...(n.children||[]).flatMap(walk)];}
 function connect(n,yes){for(const child of walk(n))child.isConnected=yes;}
 function close(keep=false){dialogGeneration++;if(modal){if(!keep&&walk(modal).some(n=>Object.hasOwn(n.dataset,'companyEvents')))ui.clear();connect(modal,false);modal=null;}}
 const api=new OfficeApi({fetcher:async(url,options)=>{
   const path=url.replace('/api/v1',''),body=options.body?JSON.parse(options.body):null,request={path,method:options.method,body};requests.push(request);const override=await hook?.(request);if(override)return override;
   if(path.split('?')[0]==='/business/capabilities'){const project=new URL('http://local'+path).searchParams.get('project_id');return Response.json(projectCaps.get(project)||globalCaps);}
   if(path==='/me')return Response.json({role:'owner'});
   if(path==='/business/company-events/status')return Response.json(f.status);
   if(path==='/business/company-events/rules')return Response.json(f.rules_after);
   for(const kind of ['plans','events','runs'])if(path==='/business/company-events/'+kind)return Response.json(f[kind]);
   if(path.startsWith('/business/company-events/events/'))return Response.json(allEvents.find(v=>path.endsWith(v.id)));
   if(path.startsWith('/business/company-events/plans/')){
     const [,id,operation]=path.match(/\/plans\/([a-f0-9]{32})(?:\/(\w+))?$/)||[];
     if(!body)return Response.json(allPlans.find(v=>v.id===id));
     const target=scenarios.find(v=>v.plans.items.some(p=>p.id===id));
     return Response.json(await accepted(path,body,operation==='execute'?target.executed:target.approved));
   }
   if(path==='/business/company-events/scan')return Response.json(await accepted(path,body,f.scan));
   if(path.startsWith('/business/company-events/runs/'))return Response.json(f.scan_replay);
   throw new Error('Unhandled independent route '+path);
 }});api.setToken('synthetic-independent-events-session');
 const action=async fn=>{try{return await fn();}catch(error){if(!(error instanceof StaleSession))errors.push(error);}};
 ui=companyEventsUi({api,biz:path=>'/business'+path,stamp:()=>`${api.generation}/${view}/${dialogGeneration}`,projects:()=>scenarios.map(v=>({id:v.project_id,name:'Project '+v.project_id})),userId:()=>f.actor.id,
   requestId:()=>crypto.randomUUID().replaceAll('-',''),el:node,button:(label,run)=>Object.assign(node('button',{},label),{label,run}),field:(name,label,type,value,extra)=>({name,label,type,value,...extra}),
   form:(_title,fields,save,options)=>Object.assign(node('form',{},options.extra,fields.map(v=>node('field',{},v.label,v.value))),{fields,save,options}),
   dialog:(title,content,description)=>{close(true);modal=node('dialog',{'aria-label':title},node('h2',{},title),description,content);connect(modal,true);return modal;},closeModal:close,
   panel:(title,...values)=>node('panel',{},title,...values),rows:(items,map,empty)=>items.length?node('rows',{},items.map(map)):node('empty',{},empty),row:(title,description,buttons)=>node('row',{},title,description,buttons),notice:message=>node('notice',{},message),table:(headers,rows)=>node('table',{},headers,rows),action,formatDate:String,updatePending(){},openTask(){throw new Error('not used');}});
 return {api,ui,f,globalCaps,projectCaps,requests,errors,action,get modal(){return modal;},hook:fn=>{hook=fn;},close,
   find:predicate=>walk(modal).find(predicate),button:label=>{const b=walk(modal).find(n=>n.tag==='button'&&n.label===label);assert.ok(b,'Missing button '+label);return b;},
   text:()=>{function text(n){if(typeof n==='string')return n;if(!n||typeof n!=='object')return '';return (n.children||[]).map(text).join('\n');}return text(modal);},
   other(){close();modal=node('dialog',{'aria-label':'OTHER PRIVATE DIALOG'},'OTHER PRIVATE DIALOG');connect(modal,true);},
   project(){close();view++;modal=node('dialog',{'aria-label':'OTHER PROJECT'},'OTHER PROJECT');connect(modal,true);},
   session(){close();api.setToken('synthetic-independent-new-events-session');view++;},
   async submit(form,values){try{return await form.save(values);}catch(error){if(form.isConnected&&!(error instanceof StaleSession))errors.push(error);}},
 };
}


test('merge review: original unconfirmed execution cannot be relabelled as succeeded in reader or UI',async()=>{
 const h=harness('external_unconfirmed'),bad=copy(h.f.plan_after);bad.status='succeeded';
 assert.deepEqual(bad.execution,h.f.plan_after.execution);assert.equal(bad.outcome,null);
 await assert.rejects(eventPlan(bad));
 h.hook(async r=>r.method==='GET'&&r.path==='/business/company-events/plans/'+bad.id?Response.json(bad):null);
 await h.action(()=>h.ui.planDetail(bad.id));assert.equal(h.text().includes(eventStates.succeeded),false);assert.equal(h.modal,null);
});
test('merge review: genuine unconfirmed and historical stale or suspended successes remain readable',async()=>{
 await eventPlan(copy(fixture.external_unconfirmed.plan_after));
 for(const status of ['stale','suspended_after_restore']){const value=copy(fixture.approval.plan_after);assert.equal(value.outcome.status,'succeeded');value.status=status;await eventPlan(value);}
});
