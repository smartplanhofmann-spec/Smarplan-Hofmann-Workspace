import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {ContactClient,ContactError,contactPayload,receiptMessage,PRIVACY_NOTICE_VERSION} from '../contact.js';
const values={sender_name:'Synthetic person',sender_email:'person@example.test',sender_phone:'',subject:'Synthetic callback',message:'Please call back.\nNo order.',website:'',privacy:true};
const identifier='a'.repeat(32),response=()=>new Response(JSON.stringify({id:'b'.repeat(32),status:'received',reply_status:'pending',accepted_by_server:false,recipient_delivery_confirmed:false}),{status:201,headers:{'Content-Type':'application/json'}});
test('the public envelope matches the narrow server contract and captures notice version',()=>{
  const payload=contactPayload(values,identifier);
  assert.deepEqual(Object.keys(payload).sort(),['request_id','subject','message','sender_name','sender_email','sender_phone','website','privacy_notice_version'].sort());
  assert.equal(payload.request_id,identifier);assert.equal(payload.privacy_notice_version,PRIVACY_NOTICE_VERSION);
  assert.throws(()=>contactPayload({...values,privacy:false},identifier),ContactError);
  assert.throws(()=>contactPayload({...values,sender_email:'Display <person@example.test>'},identifier),ContactError);
  assert.throws(()=>contactPayload({...values,message:'x'.repeat(6001)},identifier),ContactError);
  assert.equal(contactPayload({...values,website:'  '},identifier).website,'  ','honeypot must not normalize a bot field to empty');
});
test('public requests have no bearer or cookies, cannot follow redirects and are bounded',async()=>{
  let options,url;const client=new ContactClient(async function(path,request){assert.equal(this,globalThis);url=path;options=request;return response();});
  const result=await client.submit(values);assert.equal(url,'/api/v1/intake/contact');assert.deepEqual(Object.keys(options.headers).sort(),['Accept','Content-Type']);
  assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');assert.equal(options.cache,'no-store');assert.ok(options.signal instanceof AbortSignal);
  assert.equal(result.receipt.status,'received');assert.match(result.message,/Anfrage ist eingegangen/);assert.match(result.message,/Versand ist noch nicht bestätigt/);assert.equal(client.pending,false);
});
test('a lost reply retries the identical request id and never changes pending content silently',async()=>{
  const calls=[];let first=true;const client=new ContactClient(async(_,options)=>{calls.push(JSON.parse(options.body));if(first){first=false;throw new Error('synthetic lost reply');}return response();});
  await assert.rejects(client.submit(values));assert.equal(client.pending,true);
  await assert.rejects(client.submit({...values,message:'Changed'}),/unveränderte Anfrage/);
  await client.submit(values);assert.deepEqual(calls[0],calls[1]);assert.equal(client.pending,false);
});
test('received is never confused with delivered email or a confirmed contract',()=>{
  const message=receiptMessage({id:identifier,status:'received',reply_status:'pending',accepted_by_server:false});
  assert.match(message,/Bearbeitung steht noch aus/);assert.match(message,/noch nicht bestätigt/);
  assert.throws(()=>receiptMessage({id:identifier,status:'sent'}));assert.throws(()=>receiptMessage({id:'invalid',status:'received'}));
});
test('disabled source and invalid input permit correction without an old unknown operation',async()=>{
  const client=new ContactClient(async()=>new Response(JSON.stringify({error:'private config detail'}),{status:409}));
  await assert.rejects(client.submit(values),error=>error.status===409&&!error.message.includes('private config'));assert.equal(client.pending,false);
});
test('proxy HTML and oversized responses do not leak or claim acceptance',async()=>{
  const client=new ContactClient(async()=>new Response('<b>Proxy detail</b>',{status:502}));
  await assert.rejects(client.submit(values),error=>!error.message.includes('Proxy detail'));assert.equal(client.pending,true);
  const large=new ContactClient(async()=>new Response('x'.repeat(65537)));await assert.rejects(large.submit(values),ContactError);assert.equal(large.pending,true);
});
test('standalone contact source never imports authenticated Office code or browser persistence',async()=>{
  const html=await readFile(new URL('../contact.html',import.meta.url),'utf8'),source=await readFile(new URL('../contact.js',import.meta.url),'utf8');
  assert.ok(!html.includes('office.js'));assert.ok(!/localStorage|sessionStorage|indexedDB|Authorization|SPIN_|SPLD_|innerHTML/.test(source));
  assert.match(html,/name="website"/);assert.match(html,/type="module" src="\.\/contact.js"/);
  assert.match(html,/<form[^>]*method="post"/);assert.match(html,/<button[^>]*id="contact-submit"[^>]*disabled/);
});
