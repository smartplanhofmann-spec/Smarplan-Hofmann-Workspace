import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {OfficeApi, ApiError, StaleSession, decimalText, formatMoney, formatQuantity, collection, duration, requestId} from '../office.js';
const token='synthetic-session-token-never-persisted';
const json=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});

test('money and quantities preserve server decimal strings in German display',()=>{
  assert.equal(formatMoney('12345.6700'),'12.345,6700 €');
  assert.equal(formatMoney('-0.25'),'-0,25 €');
  assert.equal(formatMoney(undefined),'—');
  assert.equal(decimalText('3,1250'),'3.1250');
  assert.equal(formatQuantity('6.8200','m2'),'6,8200 m²');
  assert.throws(()=>decimalText('1e12'));
  assert.throws(()=>decimalText('NaN'));
  assert.equal(duration(7200),'2:00 Std.');
  assert.deepEqual(collection({items:[{id:'a'}]}),[{id:'a'}]);
  assert.match(requestId(),/^[a-f0-9]{32}$/);
});
test('requests stay on same origin, omit cookies, refuse redirects and carry memory bearer',async()=>{
  let captured;const api=new OfficeApi({fetcher:async(path,options)=>{captured={path,options};return json({items:[]});}});api.setToken(token);
  await api.get('/business/media?project_id=synthetic');
  assert.equal(captured.path,'/api/v1/business/media?project_id=synthetic');
  assert.equal(captured.options.headers.Authorization,'Bearer '+token);
  assert.equal(captured.options.credentials,'omit');assert.equal(captured.options.redirect,'error');assert.equal(captured.options.cache,'no-store');
  await assert.rejects(api.get('//foreign.example.test/'),/Ungültiger API-Pfad/);
  assert.throws(()=>new OfficeApi({base:'https://foreign.example.test'}));
});
test('the browser native fetch receiver stays bound to the global object',async()=>{
  const api=new OfficeApi({fetcher:async function(){assert.equal(this,globalThis);return json({ready:true});}});api.setToken(token);
  assert.deepEqual(await api.get('/me'),{ready:true});
});
test('login has no stale bearer and logout erases memory authorization',async()=>{
  const headers=[];const api=new OfficeApi({fetcher:async(_,options)=>{headers.push(options.headers);return json({challenge:'synthetic'});}});api.setToken(token);
  await api.request('/login',{method:'POST',body:{email:'synthetic@example.test',password:'synthetic'},publicRequest:true});
  assert.equal(headers[0].Authorization,undefined);api.clear();
  await assert.rejects(api.get('/me'),error=>error.status===401);
});
test('clear aborts outstanding requests and refuses a response from the previous session',async()=>{
  let resolve,options;const api=new OfficeApi({fetcher:async(_,passed)=>{options=passed;return new Promise(done=>{resolve=done;});}});api.setToken(token);
  const pending=api.get('/me');api.clear();assert.equal(options.signal.aborted,true);resolve(json({id:'old-user'}));
  await assert.rejects(pending,StaleSession);
});
test('a lost mutation response retries the exact request id and body',async()=>{
  const calls=[];let fail=true;const api=new OfficeApi({fetcher:async(_,options)=>{calls.push(JSON.parse(options.body));if(fail){fail=false;throw new Error('synthetic lost response');}return json({id:'persisted'});}});api.setToken(token);
  await assert.rejects(api.mutate('new','/business/contacts',{name:'Synthetic contact'}),error=>error.status===0);assert.equal(api.pendingCount,1);
  assert.deepEqual(await api.mutate('new','/business/contacts',{name:'Synthetic contact'}),{id:'persisted'});
  assert.deepEqual(calls[0],calls[1]);assert.equal(api.pendingCount,0);
});
test('uncertain operation cannot silently change its target or payload',async()=>{
  const api=new OfficeApi({fetcher:async()=>{throw new Error('synthetic');}});api.setToken(token);
  await assert.rejects(api.mutate('one','/business/contacts',{name:'One'}));
  await assert.rejects(api.mutate('one','/business/contacts',{name:'Changed'}),/unveränderte Eingabe/);
  api.clear();assert.equal(api.pendingCount,0);
});
test('an uncertain saved form can be explicitly retried after its dialog closes',async()=>{
  let unavailable=true;const calls=[];
  const api=new OfficeApi({fetcher:async(_,options)=>{calls.push(JSON.parse(options.body));if(unavailable){unavailable=false;throw new Error('synthetic lost acknowledgement');}return json({id:'saved'});}});api.setToken(token);
  await assert.rejects(api.mutate('saved-form','/business/contacts',{name:'Synthetic'}));
  assert.deepEqual(api.pendingOperations(),[{key:'saved-form',path:'/business/contacts'}]);
  assert.deepEqual(await api.retry('saved-form'),{id:'saved'});assert.deepEqual(calls[0],calls[1]);assert.equal(api.pendingCount,0);
});
test('a definite validation failure allows a corrected fresh operation',async()=>{
  const calls=[];const api=new OfficeApi({fetcher:async(_,options)=>{calls.push(JSON.parse(options.body));return calls.length===1?json({error:'Check value'},400):json({id:'valid'});}});api.setToken(token);
  await assert.rejects(api.mutate('one','/business/contacts',{name:''}),error=>error.status===400);assert.equal(api.pendingCount,0);
  await api.mutate('one','/business/contacts',{name:'Corrected'});assert.notEqual(calls[0].request_id,calls[1].request_id);
});
test('streaming and advertised response bounds protect memory',async()=>{
  const api=new OfficeApi({fetcher:async()=>new Response(new Uint8Array(50),{headers:{'Content-Length':'50'}})});api.setToken(token);
  await assert.rejects(api.request('/large',{maxBytes:20}),error=>error.status===413);
  const stream=new OfficeApi({fetcher:async()=>new Response(new Uint8Array(50))});stream.setToken(token);
  await assert.rejects(stream.request('/large',{maxBytes:20}),error=>error.status===413);
});
test('HTML proxy errors never enter the user-facing error message',async()=>{
  const api=new OfficeApi({fetcher:async()=>new Response('<script>secret proxy page</script>',{status:502})});api.setToken(token);
  await assert.rejects(api.get('/me'),error=>error instanceof ApiError&&!error.message.includes('secret')&&!error.message.includes('<script>'));
});
test('binary downloads retain bytes and do not put bearer into a URL',async()=>{
  let path;const api=new OfficeApi({fetcher:async value=>{path=value;return new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':'image/png'}});}});api.setToken(token);
  const result=await api.binary('/business/media/synthetic/content');assert.deepEqual([...new Uint8Array(await result.arrayBuffer())],[1,2,3]);assert.equal(result.type,'image/png');assert.ok(!path.includes(token));
});
test('browser source has ten real navigation sections and no persistent credential or unsafe HTML writer',async()=>{
  const source=await readFile(new URL('../office.js',import.meta.url),'utf8');
  const nav=source.slice(source.indexOf('const NAV ='),source.indexOf('const LABELS'));
  assert.equal((nav.match(/\['[a-z]+','/g)||[]).length,10);
  assert.ok(!/localStorage|sessionStorage|indexedDB|innerHTML|insertAdjacentHTML|serviceWorker|document\.cookie/.test(source));
  const html=await readFile(new URL('../index.html',import.meta.url),'utf8');assert.ok(!/https?:\/\//.test(html));assert.match(html,/type="module" src="\.\/office\.js"/);
});
