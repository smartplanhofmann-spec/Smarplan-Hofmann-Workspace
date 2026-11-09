import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,copy} from './source5-positive-fixture.mjs';
import {payrollUi} from '../payroll.js';

class Node{constructor(tag,children=[]){this.tag=tag;this.children=children.flat(Infinity).filter(v=>v!==null&&v!==undefined);this.isConnected=true;}setAttribute(){}}
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of node.children||[]){const result=find(child,predicate);if(result)return result;}return null;}

test('positive correction asks for explicit complete external payments, remittances and a real private original before preview',async()=>{
  const s=fixture.correction,posts=[],mutations=[];let view=null,title='';
  const caps={features:['german_payroll_2026','payroll_multiple_cases','payroll_wage_account','payroll_source5_positive_corrections'],capabilities:['business_payroll','business_payroll_multiple_cases','business_payroll_accounts'],permissions:['personnel.read','personnel.approve','personnel.write'],readonly:false};
  const api={pendingCommandValues:()=>null,get:async path=>{
    if(path.endsWith('/capabilities'))return copy(caps);
    if(path.includes('/payroll/runs?'))return{employee_id:s.employee.id,items:[copy(s.prior_run)]};
    if(path.includes('/payroll/profiles?'))return{employee_id:s.employee.id,items:copy(s.sources.profiles)};
    if(path.includes('/personnel/payroll-preparations?'))return{employee_id:s.employee.id,items:copy(s.sources.preparations)};
    if(path.includes('/payroll/multiple-one-off-cases/sources?'))return copy(s.sources);
    if(path.includes('/payroll/account-records?'))return{employee_id:s.employee.id,items:[copy(s.prior_payment),...copy(s.sources.identities)]};
    if(path.includes('/personnel/files?'))return{employee_id:s.employee.id,items:copy(s.files)};
    throw new Error('Unexpected read '+path);
  },post:async(path,body)=>{assert.equal(path,'/business/payroll/preview');posts.push(copy(body));return copy(s.run_preview);}};
  const h={api,available:()=>true,caps:()=>caps,stamp:()=>0,userId:()=>s.employee.user_id,organization:()=>({modules:{personnel:{enabled:true}}}),
    biz:path=>'/business'+path,query:(path,params)=>path+'?'+new URLSearchParams(params),formatMoney:value=>value,formatDate:value=>value,
    el:(tag,attrs,...children)=>new Node(tag,children),panel:(label,...children)=>new Node('panel',[label,...children]),table:(head,rows)=>new Node('table',[head,rows]),
    rows:(values,render)=>new Node('rows',values.map(render)),row:(...children)=>new Node('row',children),notice:text=>new Node('notice',[text]),
    button:(label,fn)=>Object.assign(new Node('button',[label]),{label,fn}),field:(name,label,type,value,options)=>({name,label,type,value,...options}),
    form:(label,fields,save,options)=>Object.assign(new Node('form'),{fields,save,options}),
    dialog:(label,body)=>{if(view)view.isConnected=false;view=body;title=label;},action:async fn=>fn(),refresh:async()=>{},mutation:async(...args)=>mutations.push(args),
  };
  const ui=payrollUi(h);await ui.open(s.employee);
  await find(view,n=>n.label==='Monatsberechnung korrigieren').fn();
  let form=find(view,n=>n.tag==='form');
  await form.save({fact_id:s.case.id,correction_reason:s.run_command.correction_reason});
  assert.equal(title,'Zahlungen und Abführungen vollständig prüfen');form=find(view,n=>n.tag==='form');
  assert.equal(form.fields.find(f=>f.name==='payments_complete').value,false);
  assert.equal(form.fields.find(f=>f.name==='remittances_complete').value,false);
  assert.equal(form.fields.find(f=>f.name==='evidence_id').value,'');
  assert.match(JSON.stringify(view),/externe/);assert.match(JSON.stringify(view),/keine Abführungen erfolgt/);
  const evidence=s.run_input.settlement_review.evidence_ref.id;
  await assert.rejects(form.save({payments_complete:true,remittances_complete:false,evidence_id:evidence}));
  await assert.rejects(form.save({payments_complete:true,remittances_complete:true,evidence_id:''}));
  assert.equal(posts.length,0);
  await form.save({payments_complete:true,remittances_complete:true,evidence_id:evidence});
  assert.equal(title,'Geprüften Berechnungsumfang festhalten');
  assert.deepEqual(posts,[s.run_input]);assert.equal(mutations.length,0);
  assert.match(JSON.stringify(view),/Zusätzliche Nettoverpflichtung/);
});
