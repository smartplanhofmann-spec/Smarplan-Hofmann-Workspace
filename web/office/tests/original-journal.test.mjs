import test from 'node:test';
import assert from 'node:assert/strict';
import {BrowserOriginalJournal,OriginalIndexedStore,browserOriginalJournal} from '../original-journal.js';

const scope={schema_version:1,instance_id:'a'.repeat(32),account_id:'b'.repeat(32)};
const subject='c'.repeat(32),kind='material_return',locator='synthetic browser actor/slot';
const body=()=>({request_id:'d'.repeat(32),body:{quantity:'2.0000',note:'Original Müller e\u0301 🛠',amount_minor:3000,nullable:null}});
class Store{
  rows=new Map();writes=0;fail=false;
  async get(key){return structuredClone(this.rows.get(key)??null);}
  async compareAndSwap(key,expected,next){
    if(this.fail)throw new Error('Synthetic storage refused');
    const old=this.rows.get(key);
    if(expected===null?old!==undefined:old?.revision!==expected)throw new Error('Synthetic concurrent original');
    this.writes++;if(next===null)this.rows.delete(key);else this.rows.set(key,structuredClone(next));
  }
}
function fixture(){
  const store=new Store(),key=Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64');
  let calls=0,denied=false,current=true;
  function open(options={}){
    const bound=options.scope??scope;
    return new BrowserOriginalJournal({locator:options.locator??locator,scope:bound,kind,
      subjectId:subject,store,guard:()=>{if(!current)throw Object.assign(new Error('Synthetic logout'),{status:403});},
      access:async()=>{
        calls++;if(denied)throw Object.assign(new Error('Synthetic scope denied'),{status:403});
        return {schema_version:1,binding:{...bound,host:'office.example.test',api_version:'v1',kind,subject_id:subject},wrapping_key:options.key??key};
      },...options});
  }
  return {store,key,open,calls:()=>calls,deny:()=>{denied=true;},logout:()=>{current=false;}};
}
test('new browser controller recovers exact original from ciphertext only and gets fresh online key',async()=>{
  const f=fixture(),value=body();await f.open().prepare(value);value.body.note='Caller changed';
  const disk=JSON.stringify([...f.store.rows]);
  assert(!disk.includes('Müller'));assert(!disk.includes('amount_minor'));assert(!disk.includes(f.key));assert(!disk.includes('wrapping_key'));
  assert.deepEqual(await f.open().pending(),body());assert(f.calls()>=2);
  const changed=await f.open().pending();changed.body.quantity='9';assert.deepEqual(await f.open().pending(),body());
});
test('same pending preparation is idempotent; replacement and wrong clear preserve original',async()=>{
  const f=fixture(),j=f.open();await j.prepare(body());const before=JSON.stringify([...f.store.rows]);
  await j.prepare(body());assert.equal(f.store.writes,1);
  await assert.rejects(j.prepare({...body(),request_id:'e'.repeat(32)}),{status:409});
  await assert.rejects(j.clear({...body(),body:{...body().body,quantity:'3.0000'}}));
  assert.equal(JSON.stringify([...f.store.rows]),before);await j.clear(body());assert.equal(f.store.rows.size,0);
});
test('a replacement company with the same user and locator cannot inspect or overwrite the old original',async()=>{
  const f=fixture();await f.open().prepare(body());const before=JSON.stringify([...f.store.rows]),calls=f.calls();
  const other=f.open({scope:{...scope,instance_id:'e'.repeat(32)}});
  await assert.rejects(other.pending(),/ursprüngliche Firmenanmeldung/);
  await assert.rejects(other.prepare(body()),/ursprüngliche Firmenanmeldung/);
  assert.equal(f.calls(),calls);assert.equal(JSON.stringify([...f.store.rows]),before);
});
test('separate origin/account/resource locators do not assign a previous original',async()=>{
  const f=fixture();await f.open().prepare(body());
  assert.equal(await f.open({locator:'different authorized namespace'}).pending(),null);
  assert.deepEqual(await f.open().pending(),body());
});
test('a wrong server key and corrupted authenticated ciphertext stay preserved without fallback',async()=>{
  const f=fixture();await f.open().prepare(body());const before=JSON.stringify([...f.store.rows]);
  await assert.rejects(f.open({key:Buffer.alloc(32,1).toString('base64')}).pending(),/entschlüsselt/);
  assert.equal(JSON.stringify([...f.store.rows]),before);
  const row=f.store.rows.get(locator);row.revision='e'.repeat(32);
  const corrupt=JSON.stringify([...f.store.rows]);await assert.rejects(f.open().pending(),/entschlüsselt/);
  assert.equal(JSON.stringify([...f.store.rows]),corrupt);
});
test('fresh scope revocation and logout block reads without deleting retained ciphertext',async()=>{
  const f=fixture();await f.open().prepare(body());const before=JSON.stringify([...f.store.rows]);f.deny();
  await assert.rejects(f.open().pending(),{status:403});assert.equal(JSON.stringify([...f.store.rows]),before);
  f.logout();await assert.rejects(f.open().clear(body()),{status:403});assert.equal(JSON.stringify([...f.store.rows]),before);
});
test('storage refusal and unavailable IndexedDB do not become a prepared original',async()=>{
  const f=fixture();f.store.fail=true;await assert.rejects(f.open().prepare(body()));assert.equal(f.store.rows.size,0);
  const unavailable=new OriginalIndexedStore(null);await assert.rejects(unavailable.get(locator),/nicht verfügbar/);
});
test('two independently prepared windows cannot replace each other under asynchronous encryption',async()=>{
  const f=fixture(),a=body(),b={...body(),request_id:'e'.repeat(32)};
  const outcomes=await Promise.allSettled([f.open().prepare(a),f.open().prepare(b)]);
  assert.equal(outcomes.filter(x=>x.status==='fulfilled').length,1);
  const original=await f.open().pending();assert([a.request_id,b.request_id].includes(original.request_id));assert.equal(f.store.rows.size,1);
});
test('wrong local original cannot authorize retry and an already resolved original is absent',async()=>{
  const f=fixture();await f.open().prepare(body());await f.open().requireOriginal(body());
  await assert.rejects(f.open().requireOriginal({...body(),request_id:'e'.repeat(32)}));
  await f.open().clear(body());assert.equal(await f.open().pending(),null);await f.open().clear(body());
});
test('invalid identity whitespace JSON numbers Unicode and oversize payload never write',async()=>{
  const f=fixture();
  assert.throws(()=>f.open({scope:{...scope,account_id:scope.account_id+'\n'}}));
  for(const value of [{bad:NaN},{bad:1.5},{bad:String.fromCharCode(0xd800)},{bad:'🛠'.repeat(300000)}])await assert.rejects(f.open().prepare(value));
  assert.equal(f.store.writes,0);
});
test('optional old server checks for retained originals without creating a key; missing binding fails closed',async()=>{
  const store=new Store(),origin='https://office.example.test',actorId=scope.account_id;
  assert.equal(await browserOriginalJournal({}, {caps:{features:[]},kind,subjectId:subject,actorId,origin,store}),null);
  await assert.rejects(browserOriginalJournal({}, {caps:{features:['client_original_key']},kind,subjectId:subject,origin,actorId,store}));
});
test('a server downgrade cannot bypass ciphertext retained in the same authenticated browser namespace',async()=>{
  const f=fixture(),origin='https://office.example.test',actorId=scope.account_id;
  const api={get:async()=>({schema_version:1,binding:{...scope,host:'office.example.test',api_version:'v1',kind,subject_id:subject},wrapping_key:f.key})};
  const j=await browserOriginalJournal(api,{caps:{features:['client_original_key'],project_creation_scope:scope},kind,subjectId:subject,actorId,origin,store:f.store});
  await j.prepare(body());const before=JSON.stringify([...f.store.rows]);
  await assert.rejects(browserOriginalJournal(api,{caps:{features:[]},kind,subjectId:subject,actorId,origin,store:f.store}),/noch geschützt gespeichert/);
  assert.equal(JSON.stringify([...f.store.rows]),before);
});
