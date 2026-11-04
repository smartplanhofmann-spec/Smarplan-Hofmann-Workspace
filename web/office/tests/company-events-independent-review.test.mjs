import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi,StaleSession} from '../office.js';
import {companyEventsUi,companyEventDataAuthorize} from '../company-events.js';
import {eventReceipt,eventHash} from '../company-events-contract.js';

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

for(const change of ['other','project','session'])for(const fail of [false,true])test(`independent initial event list ${fail?'error':'success'} cannot cross ${change}`,async()=>{
 const h=harness(),held=defer();h.hook(async r=>{if(r.path==='/business/company-events/plans'){held.enter();await held.done;return fail?Response.json({error:'PRIVATE OLD PLAN FAILURE '+h.f.plans.items[0].id}, {status:409}):Response.json(h.f.plans);}});
 const pending=h.action(()=>h.ui.open());await held.ready;h[change]();const current=h.modal;held.release();await pending;
 assert.equal(h.modal,current,'late initial read must not replace current dialog');
 assert.deepEqual(h.errors,[],'late errors must not be inserted in the current page');
});

for(const scenario of ['approval','external_unknown'])test('independent held original loses project source permission: '+scenario,async()=>{
 const h=harness(scenario),held=defer(),event=h.f.events.items[0];await h.ui.open('events');
 h.hook(async r=>{if(r.path.endsWith('/events/'+event.id)){held.enter();await held.done;return Response.json(event);}});
 const pending=h.action(()=>h.ui.eventDetail(event.id));await held.ready;
 const revoked=caps();revoked.permissions=revoked.permissions.filter(p=>p!==(scenario==='approval'?'documents.read':'finance.read'));h.projectCaps.set(h.f.project_id,revoked);held.release();await pending;
 assert.ok(h.text().includes('Kontext oder die Zugriffsrechte'));
 assert.equal(h.text().includes(event.source.descriptor.id),false,'old source identifier must disappear');
 assert.equal(h.text().includes(event.source.sha256),false);
 assert.equal(h.text().includes(event.source.data.title||event.source.data.number),false);
 assert.equal(h.requests.some(r=>r.method==='POST'),false);
});

test('independent global source access does not substitute for revoked project rights',async()=>{
 const h=harness(),project=caps();project.permissions=['assistant.use'];h.projectCaps.set(h.f.project_id,project);
 await assert.rejects(companyEventDataAuthorize(h.api,h.f.plans.items[0]),/Originalquelle/);
 assert.ok(h.globalCaps.permissions.includes('documents.read'));
 assert.ok(h.requests.some(r=>r.path.endsWith('?project_id='+h.f.project_id)));
});

test('independent accepted decision after dialog replacement consumes exact receipt but cannot reopen plan',async()=>{
 const h=harness(),held=defer(),plan=h.f.plans.items[0];await h.ui.planDetail(plan.id);await h.button('Diesen Ereignisplan freigeben').run();const form=h.find(n=>n.tag==='form');
 h.hook(async r=>{if(r.path.endsWith('/approve')){held.enter();await held.done;return Response.json(await accepted(r.path,r.body,h.f.approved));}});
 const pending=h.submit(form,{reason:h.f.approve_command.reason,confirmation:true});await held.ready;h.other();const next=h.modal;held.release();await pending;
 assert.equal(h.modal,next);assert.equal(h.api.pendingCount,0);assert.deepEqual(h.errors,[]);
 assert.equal(h.requests.filter(r=>r.method==='POST').length,1);
});

test('independent two lost decisions resolve only their own original operation and cannot reveal body in pending list',async()=>{
 const h=harness(),pairs=['approval','project_approval'].map(name=>{const f=fixture[name];return {f,key:'company-event-decision-'+f.plans.items[0].id+'-true',path:'/business/company-events/plans/'+f.plans.items[0].id+'/approve'};});
 let lose=true;h.hook(async r=>{if(r.method==='POST'&&lose)throw new Error('Synthetic accepted response loss');});
 for(const {f,key,path}of pairs)await assert.rejects(h.api.mutate(key,path,withoutNonce(f.approve_command),{validate:(result,body)=>eventReceipt(path.slice('/business'.length),body,result)}));
 const original=h.requests.filter(r=>r.method==='POST').map(r=>copy(r.body));assert.equal(h.api.pendingCount,2);
 const list=h.api.pendingOperations();assert.equal(JSON.stringify(list).includes('plan_sha256'),false);assert.equal(JSON.stringify(list).includes(pairs[0].f.approve_command.reason),false);
 lose=false;await h.api.retry(pairs[1].key);assert.equal(h.api.pendingCount,1);assert.ok(h.api.pendingCommandValues(pairs[0].key,pairs[0].path));assert.deepEqual(h.requests.filter(r=>r.method==='POST').at(-1).body,original[1]);
 await h.api.retry(pairs[0].key);assert.equal(h.api.pendingCount,0);assert.deepEqual(h.requests.filter(r=>r.method==='POST').at(-1).body,original[0]);assert.notEqual(original[0].request_id,original[1].request_id);
});

test('independent correctly hashed foreign plan receipt cannot acknowledge original operation',async()=>{
 const h=harness(),f=h.f,plan=f.plans.items[0],path='/business/company-events/plans/'+plan.id+'/approve',key='independent-foreign-plan';let foreign=true;
 h.hook(async r=>{if(r.method==='POST')return Response.json(await accepted(r.path,r.body,foreign?fixture.project_approval.approved:f.approved));});
 await assert.rejects(h.api.mutate(key,path,withoutNonce(f.approve_command),{validate:(result,body)=>eventReceipt(path.slice('/business'.length),body,result)}));
 assert.equal(h.api.pendingCount,1);foreign=false;await h.api.retry(key);assert.equal(h.api.pendingCount,0);const posts=h.requests.filter(r=>r.method==='POST');assert.deepEqual(posts[0].body,posts[1].body);
});

// Separate post-handoff addendum: an actual persisted claim without an outcome.
test('independent actual accepted external claim shows no success and cannot execute twice',async()=>{
 const h=harness('external_unconfirmed'),f=h.f,plan=f.plan_after;
 assert.equal(plan.status,'unconfirmed');assert.equal(plan.can_execute,false);assert.equal(plan.outcome,null);assert.ok(plan.execution);
 await eventReceipt('/company-events/plans/'+plan.id+'/execute',f.execute_command,f.execute_replay);
 h.hook(async r=>r.path==='/business/company-events/plans/'+plan.id?Response.json(plan):undefined);
 await h.ui.planDetail(plan.id);
 assert.ok(h.text().includes('Ausgang noch nicht bestätigt'));
 assert.ok(h.text().includes('Ausführung noch ungeklärt'));
 assert.ok(h.text().includes('die Aktion wird nicht erneut gestartet'));
 assert.equal(h.find(n=>n.tag==='button'&&n.label==='Freigegebenen Ereignisplan ausführen'),undefined);
 assert.equal(h.text().includes('Erfolgreich ausgeführt'),false);
 assert.equal(h.requests.filter(r=>r.method==='POST').length,0);
 assert.deepEqual(h.errors,[]);
});
