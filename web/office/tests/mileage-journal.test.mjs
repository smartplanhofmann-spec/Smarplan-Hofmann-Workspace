import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {TravelCommand,travelHash} from '../travel-allowances.js';
import {MILEAGE_ROOT,MILEAGE_FEATURE,MILEAGE_READ_FEATURE,mileageResult} from '../private-car-mileage.js';

const f=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/private_car_mileage.json',import.meta.url),'utf8')),copy=structuredClone;
const calcFields=['rule_version','rule_hash','table_hash','days','expense_items','transport_sources','ground_calendar_sources','mixed_program_sources','mileage_items','totals','blockers','payroll_required','can_approve','can_pay'];
class Store{
  rows=new Map();fail=false;
  async get(key){return copy(this.rows.get(key)??null);}
  async compareAndSwap(key,expected,next){if(this.fail)throw new Error('Synthetic storage denied');const old=this.rows.get(key);if(expected===null?old!==undefined:old?.revision!==expected)throw new Error('Synthetic concurrent change');if(next===null)this.rows.delete(key);else this.rows.set(key,copy(next));}
}
function model(kind='trip'){
  const x=f.initial,source=kind==='trip'?'trip':kind==='submit'?'submit':kind,receiptName=kind==='trip'?'draft_receipt':kind==='submit'?'submit_receipt':kind+'_receipt';
  const receipt=copy(x[receiptName]),original=copy(x[source+'_command']),body=copy(original);delete body.request_id;
  const api={generation:1,originalStore:new Store(),originalOrigin:'https://office.example.test',posts:[],receipts:new Map(),accepted:true,lose:true,corrupt:false,feature:true,write:true,instance:'a'.repeat(32)};
  const key=Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64');
  const caps=()=>({readonly:!api.write,features:['travel_allowances',MILEAGE_READ_FEATURE,...api.write?[MILEAGE_FEATURE]:[],...api.feature?['client_original_key']:[]],
    capabilities:['business_travel_allowances'],project_creation_scope:{schema_version:1,account_id:receipt.actor_id,instance_id:api.instance}});
  api.get=async path=>{
    if(path==='/me')return{id:receipt.actor_id};if(path==='/business/capabilities')return caps();
    if(path.startsWith('/business/client-original-key'))return{schema_version:1,binding:{...caps().project_creation_scope,host:'office.example.test',api_version:'v1',kind:'private_car_mileage',subject_id:f.employee.id},wrapping_key:key};
    if(path===MILEAGE_ROOT+'/sources?employee_id='+f.employee.id)return{...copy(f.sources),active:api.write,readonly:!api.write,rights:{read:true,write:true,approve:true,payments:true}};
    if(path===MILEAGE_ROOT+'/requests/'+receipt.request_id){
      const stored=api.receipts.get(receipt.request_id);if(!stored)throw Object.assign(new Error('Synthetic status absent'),{status:404});
      const value=copy(stored);if(api.corrupt){value.result.previous_hash='f'.repeat(64);value.result_hash=await travelHash(value.result);}return value;
    }
    throw new Error('Unexpected private path '+path);
  };
  api.post=async(path,value)=>{api.posts.push({path,body:copy(value)});assert.deepEqual(value,original);if(api.accepted)api.receipts.set(value.request_id,copy(receipt));if(api.lose){api.lose=false;throw new Error('Synthetic accepted response lost');}return{};};
  const path=MILEAGE_ROOT+(kind==='trip'?'/trips':kind==='submit'?'/trips/'+receipt.target_id+'/submit':kind==='settlement'?'/settlements':'/payments');
  const expectation=kind==='trip'?{previous_hash:null,status:'draft',details:copy(body.details),correction_reason:body.correction_reason}:
    kind==='submit'?{previous_hash:x.draft.content_hash,status:'submitted',details:copy(x.draft.details),sources:copy(x.draft.sources)}:
    kind==='settlement'?{previous_hash:null,calculation:Object.fromEntries(calcFields.map(k=>[k,copy(x.preview[k])]))}:{previous_hash:null};
  const command=()=>new TravelCommand(api,{employeeId:f.employee.id,root:MILEAGE_ROOT,writeFeature:MILEAGE_FEATURE,validateResult:mileageResult});
  const submit=c=>c.submit(path,body,{operation:receipt.operation,targetKind:receipt.target_kind,targetId:receipt.target_id,
    right:kind==='settlement'?'approve':kind==='payment'?'payments':'write',expectation});
  return{api,body,expectation,original,receipt,command,submit};
}
async function withId(value,action){const before=crypto.randomUUID;Object.defineProperty(crypto,'randomUUID',{configurable:true,value:()=>value});try{return await action();}finally{Object.defineProperty(crypto,'randomUUID',{configurable:true,value:before});}}
for(const kind of ['trip','submit','settlement','payment'])test('private '+kind+' original survives new controller and status-only resolution under read-only access',async()=>{
  const m=model(kind);await withId(m.receipt.request_id,async()=>{
    let command=m.command();await assert.rejects(m.submit(command));assert.ok(command.pending);command.clear();m.api.write=false;
    command=m.command();await command.restorePending();assert.equal(command.pending.request_id,m.receipt.request_id);
    await command.retry();assert.equal(command.pending,null);assert.equal(m.api.posts.length,1);assert.equal(m.api.originalStore.rows.size,0);
  });
});
test('restored private expectation rejects a self-consistent altered previous hash without losing original',async()=>{
  const m=model('submit');await withId(m.receipt.request_id,async()=>{
    let command=m.command();await assert.rejects(m.submit(command));command.clear();command=m.command();await command.restorePending();
    m.api.corrupt=true;await assert.rejects(command.retry(),/gespeicherte Originalfassung/);assert.ok(command.pending);assert.equal(m.api.posts.length,1);
    m.api.corrupt=false;await command.retry();assert.equal(command.pending,null);assert.equal(m.api.posts.length,1);
  });
});
test('private original cannot be bypassed by missing feature or replacement instance',async()=>{
  const m=model('payment');await withId(m.receipt.request_id,async()=>{
    let command=m.command();await assert.rejects(m.submit(command));command.clear();const before=JSON.stringify([...m.api.originalStore.rows]);
    m.api.feature=false;command=m.command();await assert.rejects(command.restorePending(),/noch geschützt gespeichert/);assert.equal(command.pending,null);
    m.api.feature=true;m.api.instance='e'.repeat(32);await assert.rejects(command.restorePending(),/ursprüngliche Firmenanmeldung/);
    assert.equal(JSON.stringify([...m.api.originalStore.rows]),before);assert.equal(m.api.posts.length,1);
  });
});
test('private confirmed body and validation snapshot freeze before first awaited authorization',async()=>{
  const m=model('trip');await withId(m.receipt.request_id,async()=>{
    const command=m.command(),promise=m.submit(command);m.body.details.purpose='Mutated later';m.expectation.details.purpose='Mutated expected later';
    await assert.rejects(promise);assert.deepEqual(m.api.posts[0].body,m.original);
    command.clear();const fresh=m.command();await fresh.restorePending();await fresh.retry();assert.equal(m.api.posts.length,1);
  });
});
test('private storage refusal sends no POST and missing original status retries the exact nonce only',async()=>{
  const m=model('trip');await withId(m.receipt.request_id,async()=>{
    let command=m.command();m.api.originalStore.fail=true;await assert.rejects(m.submit(command));assert.equal(m.api.posts.length,0);assert.equal(command.pending,null);
    m.api.originalStore.fail=false;m.api.accepted=false;await assert.rejects(m.submit(command));assert.equal(m.api.posts.length,1);
    command.clear();m.api.accepted=true;command=m.command();await command.restorePending();await command.retry();
    assert.equal(m.api.posts.length,2);assert.deepEqual(m.api.posts[0],m.api.posts[1]);assert.equal(command.pending,null);
  });
});
