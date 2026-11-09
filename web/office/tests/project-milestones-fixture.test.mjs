import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,ApiError} from '../office.js';
import {milestoneRecord,milestoneReceipt,milestoneHistory,milestoneList,milestoneHash,milestonePendingAuthorize} from '../project-milestones.js';
import {milestoneFixture as fixture,copy,commandBody} from './project-milestones-fixture.mjs';

const project=fixture.project_id,identifier=fixture.created.id,key='milestone-save-'+identifier,path='/business/projects/'+project+'/milestones/'+identifier;
const caps=()=>({project_id:project,features:['project_milestones'],capabilities:['business_project_milestones'],permissions:['planning.read','projects.manage'],readonly:false,organization:{modules:{planning:{enabled:true}}}});
async function rehash(value){const {content_hash,...raw}=value;return {...raw,content_hash:await milestoneHash(raw)};}

test('real backend milestone fixtures preserve Unicode, exact original text and every revision',async()=>{
  const original=JSON.stringify(fixture);
  for(let index=0;index<fixture.records.length;index++){
    const record=fixture.records[index],command=fixture.commands[index];
    assert.equal(await milestoneRecord(record,project,identifier),record);
    assert.equal(await milestoneReceipt(record,project,index?identifier:null,command,{original:index?fixture.records[index-1]:null,actorId:fixture.user_id}),record);
  }
  assert.equal(await milestoneHistory(fixture.history,project,fixture.reopened),fixture.history.items);
  assert.equal(await milestoneList(fixture.listing,project),fixture.listing.items);
  await milestoneReceipt(fixture.empty_created,project,null,fixture.empty_command,{actorId:fixture.user_id});
  assert.equal(fixture.empty_created.due_date,null);assert.equal(fixture.empty_created.assignee_id,null);
  assert.match(fixture.created.title,/^ .*🚧.* $/);assert.ok(fixture.created.details.endsWith('\n'));assert.equal(JSON.stringify(fixture),original);
});
test('real original history rejects a missing, crossed or rewritten source even with a fresh hash',async()=>{
  const wrong=copy(fixture.history);wrong.items[1]=await rehash({...wrong.items[1],created_by:fixture.team.find(member=>member.id!==fixture.user_id).id});
  await assert.rejects(milestoneHistory(wrong,project,fixture.reopened));
  for(const change of [{schema_version:2},{project_id:fixture.other_project_id},{milestone_id:fixture.empty_created.id},{items:fixture.history.items.slice(1)}])await assert.rejects(milestoneHistory({...copy(fixture.history),...change},project,fixture.reopened));
  await assert.rejects(milestoneList({...copy(fixture.listing),items:[fixture.reopened,fixture.reopened]},project));
  await assert.rejects(milestoneRecord({...fixture.created,title:'Substitution'},project));
});
test('update acknowledgement binds the real original creation and authenticated actor',async()=>{
  const original=fixture.created,body=fixture.update_command,actorId=fixture.user_id;
  for(const change of [{created_by:fixture.team.find(member=>member.id!==actorId).id},{created_at:'2026-11-08T12:00:00+00:00'},{updated_by:fixture.team.find(member=>member.id!==actorId).id},{project_id:fixture.other_project_id},{id:fixture.empty_created.id},{revision:3},{details:'Rewritten'}]){
    const wrong=await rehash({...fixture.updated,...change});await assert.rejects(milestoneReceipt(wrong,project,identifier,body,{original,actorId}));
  }
});
test('lost real update receipt survives rights loss, reads newer revision and replays exactly the original body',async()=>{
  let permitted=true,lose=true;const sent=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?{...caps(),permissions:permitted?caps().permissions:['planning.read']}:url.endsWith('/me')?fixture.actor:url.endsWith('/workspace')?fixture.workspace_after_assignee_removed:fixture.reopened));
    sent.push(options.body);if(lose){lose=false;throw new Error('Lost accepted backend result');}return new Response(JSON.stringify(fixture.updated));
  }});api.setToken('synthetic-milestone-session');const body=commandBody(fixture.update_command);
  await assert.rejects(api.mutate(key,path,body,{validate:(record,command)=>milestoneReceipt(record,project,identifier,command,{original:fixture.created,actorId:fixture.user_id})}));
  permitted=false;await assert.rejects(api.retry(key));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  permitted=true;assert.deepEqual(await api.retry(key),fixture.updated);assert.equal(sent[0],sent[1]);assert.equal(api.pendingCount,0);
});
test('invalid accepted echoes and inconsistent preflight sources retain the original request for later proof',async()=>{
  let badReply=true,badRead=false;const sent=[];
  const api=new OfficeApi({fetcher:async(url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?caps():url.endsWith('/me')?fixture.actor:url.endsWith('/workspace')?{...fixture.workspace,project:{...fixture.workspace.project,id:badRead?fixture.other_project_id:project}}:fixture.reopened));
    sent.push(options.body);return new Response(JSON.stringify(badReply?{...fixture.updated,content_hash:'0'.repeat(64)}:fixture.updated));
  }});api.setToken('synthetic-milestone-session');const body=commandBody(fixture.update_command);
  await assert.rejects(api.mutate(key,path,body,{validate:(record,command)=>milestoneReceipt(record,project,identifier,command,{original:fixture.created,actorId:fixture.user_id})}));assert.equal(api.pendingCount,1);
  badRead=true;await assert.rejects(api.retry(key));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  badRead=false;badReply=false;await api.retry(key);assert.equal(sent[0],sent[1]);assert.equal(api.pendingCount,0);
});
test('only explicitly proven rejection clears a milestone request; ambiguous conflict retains it',async()=>{
  for(const proven of [false,true]){
    const api=new OfficeApi({fetcher:async()=>new Response(JSON.stringify({error:'Conflict',...(proven?{request_resolution:'not_accepted'}:{})}),{status:409})});api.setToken('synthetic-milestone-session');
    await assert.rejects(api.mutate(key,path,commandBody(fixture.update_command)),ApiError);assert.equal(api.pendingCount,proven?0:1);
  }
});
test('pending milestone source validation checks exact v1 body and current project identity',async()=>{
  const api={pendingCommandValues:()=>commandBody(fixture.update_command),get:async url=>url.includes('/capabilities')?caps():url==='/me'?fixture.actor:url.endsWith('/workspace')?fixture.workspace:fixture.reopened};
  await milestonePendingAuthorize(api,{key,path});
  await assert.rejects(milestonePendingAuthorize(api,{key:key+'x',path}));
  api.pendingCommandValues=()=>({...commandBody(fixture.update_command),foreign_source:fixture.other_project_id});await assert.rejects(milestonePendingAuthorize(api,{key,path}));
});
