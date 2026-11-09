import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {stockReturnKey,stockReturnReceipt} from '../stock-returns.js';
import {originalCanonical} from '../original-journal.js';

const fixture=JSON.parse(readFileSync(new URL('../../../app/test/fixtures/material_return.json',import.meta.url),'utf8')).main;
const copy=structuredClone,actor=fixture.first.returned.created_by,subject=fixture.project_id,key=stockReturnKey(subject),path='/business/inventory/movements';
class Store{
  rows=new Map();fail=false;
  async get(k){return copy(this.rows.get(k)??null);}
  async compareAndSwap(k,expected,next){
    if(this.fail)throw new Error('Synthetic storage failure');const old=this.rows.get(k);
    if(expected===null?old!==undefined:old?.revision!==expected)throw new Error('Synthetic original changed');
    if(next===null)this.rows.delete(k);else this.rows.set(k,copy(next));
  }
}
function model(){
  const store=new Store(),wrappingKey=Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString('base64');
  const m={store,wrappingKey,posts:[],accepted:new Map(),lose:true,failClear:false,instance:'a'.repeat(32),derivedInstance:'a'.repeat(32)};
  m.caps=()=>({readonly:false,permissions:['inventory.read','inventory.write','finance.read'],capabilities:['business_inventory'],features:['client_original_key'],
    project_creation_scope:{schema_version:1,account_id:actor,instance_id:m.instance},organization:{modules:{material:{enabled:true}}}});
  const reply=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
  m.fetcher=async(url,options)=>{
    const p=new URL(url,'https://office.example.test').pathname.replace('/api/v1','');
    if(p==='/me')return reply({id:actor});
    if(p==='/business/capabilities')return reply(m.caps());
    if(p==='/business/client-original-key')return reply({schema_version:1,binding:{schema_version:1,account_id:actor,instance_id:m.derivedInstance,
      kind:'material_return',subject_id:subject,host:'office.example.test',api_version:'v1'},wrapping_key:wrappingKey});
    if(p===path&&options.method==='POST'){
      const body=JSON.parse(options.body);m.posts.push(copy(body));const old=m.accepted.get(body.request_id);
      if(m.notAccepted)return new Response(JSON.stringify({error:'Synthetic proven rejection',request_resolution:'not_accepted'}),{status:409});
      if(old)assert.equal(originalCanonical(old),originalCanonical(body));else m.accepted.set(body.request_id,copy(body));
      if(m.lose){m.lose=false;throw new Error('Synthetic accepted response lost');}
      return reply(fixture.first.returned);
    }
    if(p===path+'/'+fixture.issue.id)return reply(fixture.issue);
    if(p===path+'/'+fixture.first.returned.id){if(m.readBackConflict)return new Response(JSON.stringify({error:'Synthetic failed later read',request_resolution:'not_accepted'}),{status:409});if(m.failClear)store.fail=true;return reply(fixture.first.returned);}
    throw new Error('Synthetic unexpected path '+p);
  };
  m.api=()=>{const api=new OfficeApi({fetcher:m.fetcher,originalStore:store,originalOrigin:'https://office.example.test'});api.setToken('synthetic-original-session-token');return api;};
  m.data=()=>{const body=copy(fixture.first.command);delete body.request_id;body.quantity='2.0000';return body;};
  m.send=api=>{const data=m.data(),verify=stockReturnReceipt(data,actor);return api.mutate(key,path,data,{validate:v=>verify(v,api)});};
  return m;
}
test('new OfficeApi after lost accepted return restores exact nonce and validates original without a second booking',async()=>{
  const m=model();let api=m.api();await api.restoreStockReturn(subject,m.caps());await assert.rejects(m.send(api),{status:0});
  const original=copy(m.posts[0]);assert.equal(m.accepted.size,1);assert.equal(api.pendingCount,1);api.clear();
  api=m.api();assert.equal(await api.restoreStockReturn(subject,m.caps()),true);
  await assert.rejects(api.mutate(key,path,{...m.data(),quantity:'1.0000'}));assert.equal(m.posts.length,1);
  await api.retry(key);assert.equal(m.posts.length,2);assert.deepEqual(m.posts[1],original);assert.equal(m.accepted.size,1);
  assert.equal(api.pendingCount,0);assert.equal(m.store.rows.size,0);
});
test('an older server cannot bypass retained original and a restored company cannot inspect another instance',async()=>{
  const m=model();let api=m.api();await api.restoreStockReturn(subject,m.caps());await assert.rejects(m.send(api));api.clear();
  const before=JSON.stringify([...m.store.rows]);api=m.api();
  await assert.rejects(api.restoreStockReturn(subject,{...m.caps(),features:[],project_creation_scope:undefined}),/noch geschützt gespeichert/);
  m.instance='e'.repeat(32);m.derivedInstance=m.instance;
  await assert.rejects(api.restoreStockReturn(subject,m.caps()),/ursprüngliche Firmenanmeldung/);
  assert.equal(api.pendingCount,0);assert.equal(m.posts.length,1);assert.equal(JSON.stringify([...m.store.rows]),before);
});
test('storage prepare refusal prevents POST; failed local clear retains the accepted original for another browser session',async()=>{
  const m=model();let api=m.api();await api.restoreStockReturn(subject,m.caps());m.store.fail=true;
  await assert.rejects(m.send(api));assert.equal(m.posts.length,0);assert.equal(api.pendingCount,0);
  m.store.fail=false;m.lose=false;m.failClear=true;await assert.rejects(m.send(api));assert.equal(m.accepted.size,1);assert.equal(api.pendingCount,1);
  const original=copy(m.posts[0]);api.clear();m.store.fail=false;m.failClear=false;api=m.api();await api.restoreStockReturn(subject,m.caps());
  await api.retry(key);assert.equal(m.accepted.size,1);assert.deepEqual(m.posts.at(-1),original);assert.equal(m.store.rows.size,0);
});
test('a live company switch during pending retry blocks POST while preserving ciphertext',async()=>{
  const m=model(),api=m.api();await api.restoreStockReturn(subject,m.caps());await assert.rejects(m.send(api));
  const before=JSON.stringify([...m.store.rows]);m.derivedInstance='f'.repeat(32);
  await assert.rejects(api.retry(key),/ursprüngliche Firmenanmeldung/);assert.equal(m.posts.length,1);assert.equal(JSON.stringify([...m.store.rows]),before);
});
test('only the original POST rejection can release ciphertext, never a failed later read',async()=>{
  const m=model();m.lose=false;m.readBackConflict=true;let api=m.api();await api.restoreStockReturn(subject,m.caps());
  await assert.rejects(m.send(api),{status:409});assert.equal(m.accepted.size,1);assert.equal(api.pendingCount,1);assert.equal(m.store.rows.size,1);
  const original=copy(m.posts[0]);m.readBackConflict=false;await api.retry(key);assert.deepEqual(m.posts[1],original);assert.equal(m.accepted.size,1);assert.equal(m.store.rows.size,0);
  const rejected=model();rejected.lose=false;rejected.notAccepted=true;api=rejected.api();await api.restoreStockReturn(subject,rejected.caps());
  await assert.rejects(rejected.send(api),{status:409});assert.equal(rejected.accepted.size,0);assert.equal(api.pendingCount,0);assert.equal(rejected.store.rows.size,0);
});
