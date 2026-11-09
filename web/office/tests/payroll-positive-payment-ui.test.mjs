import test from 'node:test';
import assert from 'node:assert/strict';
import {fixture,copy,values,ref} from './source5-positive-fixture.mjs';
import {payrollAccountsUi} from '../payroll-accounts.js';

class Node{
  constructor(tag,children=[]){this.tag=tag;this.children=children.flat(Infinity).filter(v=>v!==null&&v!==undefined);this.isConnected=true;}
  setAttribute(){}
}
function find(node,predicate){if(!node||typeof node!=='object')return null;if(predicate(node))return node;for(const child of node.children||[]){const result=find(child,predicate);if(result)return result;}return null;}
function host(section){
  let view=null,title='',generation=0,release=null;const posts=[];
  const caps={features:['payroll_wage_account','payroll_source5_positive_corrections'],capabilities:['business_payroll_accounts'],permissions:['personnel.read','personnel.approve'],readonly:false};
  const right=()=>({read:caps.permissions.includes('personnel.read'),run:caps.permissions.includes('personnel.approve'),profile:false});
  const api={pendingCommandValues:()=>null,get:async path=>{
    if(path.includes('/personnel/files'))return{employee_id:section.employee.id,items:copy(section.files)};
    if(path.includes('/payroll/profiles'))return{employee_id:section.employee.id,items:copy(section.sources.profiles)};
    if(path.includes('/payroll/runs'))return{employee_id:section.employee.id,items:[copy(section.run)]};
    if(path.includes('/payroll/account-records'))return{employee_id:section.employee.id,items:[...copy(section.sources.identities),copy(section.prior_payment)]};
    throw new Error('Unexpected read '+path);
  }};
  const h={api,caps:()=>caps,stamp:()=>generation,biz:path=>'/business'+path,query:(path,params)=>path+'?'+new URLSearchParams(params),rights:right,
    fresh:async(employee,purpose)=>{if(purpose==='run'&&!right().run)throw new Error('Current payroll approval denied');return{caps:copy(caps)};},el:(tag,attrs,...children)=>new Node(tag,children),panel:(label,...children)=>new Node('panel',[label,...children]),
    table:(head,rows)=>new Node('table',[head,rows]),notice:text=>new Node('notice',[text]),rows:(rows,render)=>rows.map(render),row:(...children)=>new Node('row',children),
    button:(label,fn)=>Object.assign(new Node('button',[label]),{label,fn}),field:(name,label,type,value,options)=>({name,label,type,value,...options}),
    form:(label,fields,save,options)=>Object.assign(new Node('form'),{label,fields,save,options}),
    show:(employee,label,body)=>{if(view)view.isConnected=false;view=body;title=label;},money:value=>(value/100).toFixed(2),
    action:async fn=>fn(),refresh:async()=>{},original:async()=>{},mutation:async(key,path,body,options)=>{
      posts.push(copy(body));const result=copy(section.payment);await options.validate(result);
      if(release)await release.promise;
      return result;
    }};
  const ui=payrollAccountsUi(h);
  return{ui,caps,posts,get title(){return title;},get view(){return view;},form:()=>find(view,n=>n.tag==='form'),
    close(){generation++;if(view)view.isConnected=false;view=null;title='';},
    hold(){let done;const promise=new Promise(resolve=>done=resolve);release={promise,done};return()=>{release.done();release=null;};},
    async editor(){
      await ui.edit(section.employee,'payment',null,null,section.run.id+'@'+section.run.revision,null);
      assert.equal(title,'Vorherige Monatsgruppen-Zahlung prüfen');
      await this.form().save({prior_payment_ref:section.prior_payment.id+'@'+section.prior_payment.revision});
      await this.form().save({count:section.payment.details.payments.length});
      assert.equal(title,'Erfassung · Tatsächliche Lohnzahlung');return this.form();
    }};
}
function input(section,form){return{...Object.fromEntries(form.fields.map(field=>[field.name,field.value])),...values(section),source_file_id:section.payment.source_file.id,confirmed:true};}

test('actual positive correction editors retain every old payment and bonus allocation as disabled original fields',async()=>{
  for(const key of ['correction','second_correction']){
    const s=fixture[key],h=host(s),form=await h.editor();
    const priorCount=s.prior_payment.details.payments.length;
    for(let i=0;i<priorCount;i++)for(const name of ['paid_on_','amount_','reference_','running_','bonus_'])assert.equal(form.fields.find(field=>field.name===name+i).disabled,true);
    assert.equal(form.fields.find(field=>field.name==='bonus_1').value,(s.prior_payment.details.settlement_allocations[1].one_off_allocations[0].net_minor/100).toFixed(2));
    const body=input(s,form);body.amount_0='0.01';body.bonus_1='0.00';body.running_1='999.00';
    assert.deepEqual(await form.save(body,'test-payment'),s.payment);
    assert.equal(h.posts.length,1);assert.deepEqual(h.posts[0].details,s.payment.details);
    assert.deepEqual(h.posts[0].details.prior_payment_ref,ref(s.prior_payment));
  }
});

test('withdrawn correction feature or current approval prevents a new V2 payment POST',async()=>{
  for(const change of [h=>h.caps.features=['payroll_wage_account'],h=>h.caps.permissions=['personnel.read']]){
    const s=fixture.correction,h=host(s),form=await h.editor();change(h);
    await assert.rejects(form.save(input(s,form),'test-payment'));
    assert.equal(h.posts.length,0);
  }
});

test('a completed receipt after closing the positive payment editor cannot reopen its private view',async()=>{
  const s=fixture.correction,h=host(s),form=await h.editor(),release=h.hold();
  const pending=form.save(input(s,form),'test-payment');
  while(!h.posts.length)await new Promise(resolve=>setImmediate(resolve));
  h.close();release();assert.equal(await pending,undefined);assert.equal(h.view,null);assert.equal(h.title,'');
});

test('the V2 origin chooser never offers a none or unrelated payment choice',async()=>{
  const s=fixture.second_correction,h=host(s);
  await h.ui.edit(s.employee,'payment',null,null,s.run.id+'@'+s.run.revision,null);
  const choices=h.form().fields.find(field=>field.name==='prior_payment_ref').options;
  assert.deepEqual(choices.map(option=>option[0]),['',s.prior_payment.id+'@'+s.prior_payment.revision]);
});
