import test from 'node:test';import assert from 'node:assert/strict';
import {personnelMinor,personnelExpenseValues,personnelCloseValues} from '../personnel-workflow.js';
const employee={id:'a'.repeat(32)},preview={source_hash:'c'.repeat(64),snapshot:{employee:{id:employee.id},month:'2026-11'}};
test('money converts exact decimal cents without floating rounding',()=>{for(const [input,value]of [['0,01',1],['49.87',4987],['3500',350000],['10000000000',1000000000000]])assert.equal(personnelMinor(input),value);});
test('money rejects fractional cents, negative, exponent, zero and overflow',()=>{for(const input of ['1.001','1e2','-1','0','10000000000.01','2,001','Infinity',''])assert.throws(()=>personnelMinor(input));});
test('actual multi-receipt expenses whitelist sources and preserve originals',()=>{const items=[{date:'2026-10-28',description:'Vorgebuchte Bahn',amount:'49,87',receipt_file_id:'b'.repeat(32),project_id:'d'.repeat(32),tax_rate:'19'},{date:'2026-11-03',description:'Hotel',amount:'100',receipt_file_id:'e'.repeat(32)}],before=structuredClone(items),value=personnelExpenseValues(employee,{purpose:'Kundenreise',start_date:'2026-11-02',end_date:'2026-11-03'},items);assert.equal(value.revision,0);assert.equal(value.items[0].amount_minor,4987);assert.equal(value.items[1].amount_minor,10000);assert.equal(value.items[0].date,'2026-10-28');assert.ok(!('tax_rate' in value.items[0]));assert.ok(!('allowances' in value));assert.deepEqual(items,before);});
test('expense correction requires reason and retains actual revision',()=>{const values={purpose:'Reise',start_date:'2026-11-02',end_date:'2026-11-03'},items=[{amount:'1',receipt_file_id:'b'.repeat(32)}],old={id:'c'.repeat(32),revision:7};assert.throws(()=>personnelExpenseValues(employee,values,items,old));const result=personnelExpenseValues(employee,{...values,correction_reason:'Original erneut geprüft'},items,old);assert.equal(result.id,old.id);assert.equal(result.revision,7);});
test('monthly confirmation binds exact employee month and source hash',()=>{const result=personnelCloseValues(employee,preview,{completeness_confirmed:true});assert.deepEqual(result,{employee_id:employee.id,month:'2026-11',source_hash:preview.source_hash,revision:0,completeness_confirmed:true});assert.throws(()=>personnelCloseValues(employee,preview,{completeness_confirmed:false}));assert.throws(()=>personnelCloseValues({id:'z'},preview,{completeness_confirmed:true}));});
test('monthly correction cannot change employee or historical month',()=>{const values={completeness_confirmed:true,correction_reason:'Entgeltquelle korrigiert'},old={id:'d'.repeat(32),employee_id:employee.id,month:'2026-11',revision:3};assert.equal(personnelCloseValues(employee,preview,values,old).revision,3);assert.throws(()=>personnelCloseValues(employee,preview,values,{...old,month:'2026-10'}));assert.throws(()=>personnelCloseValues(employee,preview,{...values,correction_reason:''},old));});

test('withdrawal binds reviewed revision, current server feature and independent reviewer',async()=>{
  const {personnelWorkflowUi}=await import('../personnel-workflow.js');
  let root,modern=true,approve=true,viewer='reviewer';const commands=[];
  const person={...employee,user_id:'employee',name:'Synthetic employee'},expense={id:'e'.repeat(32),revision:3,status:'approved',submitted_by:'employee',purpose:'Whole ticket',total_minor:4987,items:[]};
  const node=(type,attrs={},...children)=>({type,attrs,children,setAttribute(name,value){this.attrs[name]=value;}}),button=(label,run)=>({label,run,children:[]});
  const ui=personnelWorkflowUi({el:node,button,field:(name,label)=>({name,label}),form:(_title,fields,submit)=>Object.assign(node('form'),{fields,submit}),dialog:(_title,body)=>{root=body;},panel:(title,...children)=>node('panel',{title},...children),rows:(items,render)=>node('rows',{},...items.map(render)),row:(title,description,actions=[])=>node('row',{title,description},...actions),notice:()=>node('notice'),table:()=>node('table'),
    api:{get:async route=>({items:route.endsWith('/expenses')?[expense]:[]})},biz:value=>value,query:value=>value,mutation:(key,path,body)=>{commands.push({key,path,body});},action:fn=>fn(),refresh:()=>{},formatDate:String,formatMoney:String,duration:String,
    available:()=>true,feature:()=>modern,permission:value=>value!=='personnel.approve'||approve,enabled:()=>true,userId:()=>viewer,stamp:()=>1,projects:()=>[]});
  function find(value){if(!value)return null;if(value.label==='Freigabe zurücknehmen')return value;for(const child of value.children||[]){const match=find(child);if(match)return match;}return null;}
  await ui.open(person);find(root).run();const form=root;
  modern=false;assert.throws(()=>form.submit({reason:'Independent duplicate review'},'same-request'),/Server/);assert.equal(commands.length,0);
  modern=true;approve=false;assert.throws(()=>form.submit({reason:'Independent duplicate review'},'same-request'),/Personalberechtigung/);assert.equal(commands.length,0);
  approve=true;form.submit({reason:'Independent duplicate review'},'same-request');assert.deepEqual(commands,[{key:'same-request',path:`/personnel/expenses/${expense.id}/withdraw-approval`,body:{revision:3,reason:'Independent duplicate review'}}]);
  for(const mode of ['own','old-server','revoked']){viewer=mode==='own'?'employee':'reviewer';modern=mode!=='old-server';approve=mode!=='revoked';await ui.open(person);assert.equal(find(root),null,mode);}
});

test('a private original in flight is withheld when global read is revoked but own time remains',async()=>{
  const {personnelWorkflowUi}=await import('../personnel-workflow.js'),bytes=new TextEncoder().encode('synthetic private original');
  const sha=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');
  let read=true,deliver,saved=false,root;
  const person={id:employee.id,user_id:'self',name:'Synthetic employee'},file={id:'d'.repeat(32),employee_id:employee.id,purpose:'personnel',owner_visible:0,filename:'private.pdf',media_type:'application/pdf',size:bytes.length,sha256:sha};
  const node=(type,attrs={},...children)=>({type,attrs,children,setAttribute(name,value){this.attrs[name]=value;}}),button=(label,run)=>({label,run,children:[]});
  const ui=personnelWorkflowUi({el:node,button,field:()=>{},form:()=>{},dialog:(_title,body)=>{root=body;},panel:(title,...children)=>node('panel',{title},...children),rows:(items,render)=>node('rows',{},...items.map(render)),row:(title,description,actions=[])=>node('row',{title,description},...actions),notice:()=>node('notice'),table:()=>node('table'),
    api:{get:async route=>({items:route.endsWith('/files')?[file]:[]}),binary:()=>new Promise(resolve=>{deliver=resolve;})},biz:value=>value,query:value=>value,mutation:()=>{},action:fn=>fn(),refresh:()=>{},formatDate:String,formatMoney:String,duration:String,
    available:()=>true,permission:value=>value==='personnel.read'?read:value==='time.own',enabled:()=>true,userId:()=>person.user_id,stamp:()=>1,projects:()=>[],saveBlob:()=>{saved=true;}});
  await ui.open(person);function find(value){if(!value)return null;if(value.label==='Original öffnen')return value;for(const child of value.children||[]){const match=find(child);if(match)return match;}return null;}
  const pending=find(root).run();read=false;deliver(new Blob([bytes]));await assert.rejects(pending,/private Personaloriginal/);assert.equal(saved,false);
});
