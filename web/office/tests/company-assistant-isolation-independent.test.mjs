import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {assistantAnswerValues,assistantReceipt} from '../assistant.js';
import {speechResult} from '../speech.js';

const fixture=JSON.parse(readFileSync(new URL('../../../docs/evidence/company-assistant-isolation-independent-2026-11-04/actual-two-company-responses.json',import.meta.url),'utf8'));
const [a,b]=fixture.companies;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const speechBinding=c=>({requestId:c.speech.id,projectId:c.project,contextId:c.context.id,contextSha256:c.context.sha256});
const selected=c=>({project_id:c.project,sources:c.context.sources.map(s=>s.descriptor)});

test('independent real two-company replies bind selected article/project originals despite identical speech nonce',()=>{
  assert.equal(a.speech.id,b.speech.id);
  assert.notEqual(a.context.instance_id,b.context.instance_id);
  for(const own of [a,b]){
    assert.deepEqual(assistantAnswerValues(own.context,own.chat).facts.map(fact=>fact.value),[own.marker+' project',own.marker+' original']);
    assert.equal(speechResult(own.speech,speechBinding(own)),own.speech.text);
    assert.equal(assistantReceipt('/assistant/contexts',own.project,selected(own),own.context),own.context);
  }
  assert.throws(()=>assistantAnswerValues(b.context,a.chat));
  assert.throws(()=>speechResult(a.speech,speechBinding(b)));
  assert.throws(()=>assistantReceipt('/assistant/contexts',b.project,selected(b),a.context));
});

const readPath=(kind,c)=>({
  search:'/business/assistant/sources?project_id='+c.project,
  context:'/business/assistant/contexts/'+c.context.id,
  chat:'/business/assistant/chat/'+c.chat.id,
  speech_status:'/business/assistant/speech/requests/'+c.speech.id,
})[kind];
for(const kind of ['search','context','chat','speech_status']){
  test(`independent old ${kind} response cannot cross a company session generation`,async()=>{
    let resolveOld,company=a;
    const reads=[];
    const api=new OfficeApi({fetcher:async(path,options)=>{
      reads.push({path,authorization:options.headers.Authorization});
      if(reads.length===1)return new Promise(resolve=>resolveOld=resolve);
      return Response.json(company[kind]);
    }});
    api.setToken('synthetic-native-review-company-a');
    const pending=api.get(readPath(kind,a));
    const rejected=assert.rejects(pending,error=>error.name==='StaleSession');
    await tick();
    company=b;api.setToken('synthetic-native-review-company-b');
    resolveOld(Response.json(a[kind]));
    await rejected;
    const actual=await api.get(readPath(kind,b));
    assert.deepEqual(actual,b[kind]);
    assert.doesNotMatch(JSON.stringify(actual),new RegExp(a.marker));
    assert.match(reads[0].authorization,/company-a$/);
    assert.match(reads[1].authorization,/company-b$/);
  });
}

test('independent old context ACK cannot clear a new company context using the same local operation key',async()=>{
  const pending=[];
  const api=new OfficeApi({fetcher:async(path,options)=>new Promise(resolve=>pending.push({path,options,resolve}))});
  const path='/business/assistant/contexts',key='same-local-context-choice';
  api.setToken('synthetic-review-original-company-a');
  const original=api.mutate(key,path,selected(a),{validate:v=>assistantReceipt('/assistant/contexts',a.project,selected(a),v)});
  const oldRejected=assert.rejects(original,error=>error.name==='StaleSession');
  await tick();
  api.setToken('synthetic-review-current-company-b');
  const current=api.mutate(key,path,selected(b),{validate:v=>assistantReceipt('/assistant/contexts',b.project,selected(b),v)});
  await tick();
  assert.equal(pending.length,2);
  pending[0].resolve(Response.json(a.context));
  await oldRejected;
  assert.equal(api.pendingCount,1);
  assert.deepEqual(api.pendingCommandValues(key,path),selected(b));
  pending[1].resolve(Response.json(b.context));
  assert.deepEqual(await current,b.context);
  assert.equal(api.pendingCount,0);
});
