import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,portalAccess,portalGrantData,portalAdoptionData,portalIssuedLink,organizationCommandArea} from '../office.js';
const source={offer_id:'a'.repeat(32),project_id:'b'.repeat(32),source_revision:3,content_hash:'c'.repeat(64),pdf_hash:'d'.repeat(64)};
const item={kind:'offer',status:'final'},caps={features:['offer_portal'],readonly:false,permissions:['portal.manage','finance.read','finance.write','projects.manage']};
const values={recipient_name:' Synthetic customer ',recipient_email:'synthetic@example.test',expires_in_days:7,confirmation:true};
test('online feature and source-scoped rights govern portal actions; paused modules still allow revoke',()=>{
  assert.deepEqual(portalAccess(item,caps,null),{read:true,revoke:true,create:true,adopt:true});
  for(const [metadata,organization]of [[{...caps,readonly:true},null],[caps,{modules:{documents:{enabled:false}}}]])
    assert.deepEqual(portalAccess(item,metadata,organization),{read:true,revoke:true,create:false,adopt:false});
  for(const permission of ['portal.manage','finance.read'])assert.equal(portalAccess(item,{...caps,permissions:caps.permissions.filter(value=>value!==permission)},null).read,false);
  assert.equal(portalAccess(item,{...caps,features:[]},null).read,false);assert.equal(portalAccess({...item,status:'draft'},caps,null).read,false);
  for(const permission of ['finance.write','projects.manage'])assert.equal(portalAccess(item,{...caps,permissions:caps.permissions.filter(value=>value!==permission)},null).adopt,false);
  assert.equal(organizationCommandArea('/portal/grants'),'documents');assert.equal(organizationCommandArea('/portal/grants/id/revoke'),null);
});
test('grant and adoption require explicit confirmation of the exact source',()=>{
  assert.deepEqual(portalGrantData(source,values),{offer_id:source.offer_id,source_revision:3,content_hash:source.content_hash,pdf_hash:source.pdf_hash,...values,recipient_name:'Synthetic customer'});
  for(const changed of [{confirmation:false},{expires_in_days:0},{expires_in_days:31},{expires_in_days:1.5},{recipient_email:'bad'}])assert.throws(()=>portalGrantData(source,{...values,...changed}));
  const decision={id:'e'.repeat(32),offer_id:source.offer_id,decision:'accepted',content_hash:source.content_hash,pdf_hash:source.pdf_hash};
  assert.equal(portalAdoptionData(source,decision,true).decision_id,decision.id);
  for(const changed of [{decision:'declined'},{offer_id:'f'.repeat(32)},{pdf_hash:'f'.repeat(64)}])assert.throws(()=>portalAdoptionData(source,{...decision,...changed},true));
  assert.throws(()=>portalAdoptionData(source,decision,false));
});
test('only a real first-create result may display a matching HTTPS fragment link',()=>{
  const grant={id:'e'.repeat(32)},url='https://office.example.test/office/portal.html#grant='+grant.id+'&key=SPPI_'+'k'.repeat(43);
  assert.equal(portalIssuedLink({grant,link_available:true,portal_url:url},'office.example.test'),url);
  assert.equal(portalIssuedLink({grant,link_available:false},'office.example.test'),null);
  for(const portal_url of [url.replace('https:','http:'),url.replace('office.example.test','office.example.test:8443'),url.replace('office.example.test','wrong.example.test'),url.replace('portal.html','office.html'),url.replace('#','?'),url+'&key=duplicate'])
    assert.throws(()=>portalIssuedLink({grant,link_available:true,portal_url},'office.example.test'));
});
test('lost grant creation retries the same request and handles an unavailable one-time link without a second grant',async()=>{
  const calls=[],api=new OfficeApi({fetcher:async(path,options)=>{calls.push(JSON.parse(options.body));if(calls.length===1)throw new Error('Synthetic lost first link');return new Response(JSON.stringify({grant:{id:'e'.repeat(32)},link_available:false}),{status:201});}});
  api.setToken('Synthetic-office-session-only');const payload=portalGrantData(source,values);
  await assert.rejects(api.mutate('grant','/business/portal/grants',payload));
  const result=await api.retry('grant');assert.deepEqual(calls[0],calls[1]);assert.equal(result.link_available,false);assert.equal(portalIssuedLink(result,'office.example.test'),null);
});
