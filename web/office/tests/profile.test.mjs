import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi,accountingStatus,accountingPreparationProfile,accountingProfileAccess,accountingProfileState,accountingProfileEntry,accountingProfilePage,accountingProfilePreviewData,accountingProfilePreview,accountingProfileConfirmData,accountingProfileAuthorize,organizationCommandArea} from '../office.js';
const id=x=>x.repeat(32),hash=x=>x.repeat(64);
const flags={scope:'organization_profile',tax_status:'unconfigured',tax_result_available:false};
const profile=()=>({legal_form:'sole_proprietorship',accounting_method:'euer',vat_regime:null,vat_timing:null,vat_effective_from:null,bookkeeping_start:null});
const source=()=>({revision:0,state_hash:hash('a'),preparation_status:'unrecorded',current:null,writes_allowed:true,...flags});
const values=()=>({...profile(),vat_regime:'',vat_timing:'',vat_effective_from:'',bookkeeping_start:'',reason:' Explicit owner statement ',evidence_reference:' SYN-PROFILE-1 '});
const body=()=>accountingProfilePreviewData(source(),values());
const preview=()=>({...body(),preview_hash:hash('b'),...flags});
const entry=(revision=1)=>({id:id(revision===1?'b':'c'),revision,previous_state_hash:hash(revision===1?'a':'c'),profile:profile(),reason:body().reason,evidence_reference:body().evidence_reference,preview_hash:hash('b'),created_by:id('a'),created_at:'2026-11-03T12:00:00+00:00',...flags});
const caps=()=>({permissions:['accounting.read','finance.read','accounting.admin'],features:['accounting_prejournal','accounting_preparation_profile'],capabilities:['business_accounting','business_accounting_profile'],readonly:false});
const confirmed=()=>accountingProfileConfirmData(body(),preview(),true);
const confirmPath='/business/accounting/profile/confirm';

test('profile access requires its negotiated feature and global admin, without prepare or finance.write',()=>{
  assert.deepEqual(accountingProfileAccess(caps(),null,source()),{available:true,read:true,admin:true});
  for(const permission of ['accounting.read','finance.read'])assert.equal(accountingProfileAccess({...caps(),permissions:caps().permissions.filter(value=>value!==permission)},null,source()).read,false);
  const readOnly={...caps(),permissions:['accounting.read','finance.read','accounting.prepare','finance.write'],project_permissions:['accounting.admin']};
  assert.deepEqual(accountingProfileAccess(readOnly,null,source()),{available:true,read:true,admin:false});
  for(const field of ['features','capabilities'])for(const removed of caps()[field])assert.equal(accountingProfileAccess({...caps(),[field]:caps()[field].filter(value=>value!==removed)},null,source()).available,false);
  for(const [cap,organization,value,online]of [[{...caps(),readonly:true},null,source(),true],[caps(),{modules:{finance:{enabled:false}}},source(),true],[caps(),null,{...source(),writes_allowed:false},true],[caps(),null,source(),false]])assert.deepEqual(accountingProfileAccess(cap,organization,value,online),{available:true,read:true,admin:false});
  assert.equal(organizationCommandArea('/accounting/profile/confirm'),'finance');
});
test('four unknown values remain null, while supported legal form and EÜR never imply tax configuration',()=>{
  assert.deepEqual(accountingPreparationProfile(profile()),profile());const data=body();assert.deepEqual(data.profile,profile());assert.equal('confirmation'in data,false);assert.equal('request_id'in data,false);
  for(const [key,value]of [['legal_form','corporation'],['accounting_method','balance_sheet'],['vat_regime','unknown'],['vat_timing',false],['vat_effective_from',''],['bookkeeping_start',undefined]])assert.throws(()=>accountingPreparationProfile({...profile(),[key]:value}));
  assert.throws(()=>accountingPreparationProfile({...profile(),tax_result_available:true}));const missing=profile();delete missing.bookkeeping_start;assert.throws(()=>accountingPreparationProfile(missing));
});
test('VAT dependencies are explicit and both date facts have no invented relative ordering',()=>{
  assert.equal(accountingPreparationProfile({...profile(),vat_regime:'regular'}).vat_timing,null);
  assert.equal(accountingPreparationProfile({...profile(),vat_regime:'small_business',vat_effective_from:'1900-01-01'}).vat_timing,null);
  for(const vat_timing of ['cash','accrual'])for(const vat_regime of [null,'small_business'])assert.throws(()=>accountingPreparationProfile({...profile(),vat_regime,vat_timing}));
  assert.throws(()=>accountingPreparationProfile({...profile(),vat_effective_from:'2026-01-01'}));
  for(const [vat_effective_from,bookkeeping_start]of [['2026-02-01','2025-12-31'],['2025-12-31','2026-02-01']])assert.equal(accountingPreparationProfile({...profile(),vat_regime:'regular',vat_timing:'cash',vat_effective_from,bookkeeping_start}).vat_timing,'cash');
});
test('profile dates are genuine calendar days within 1900 through 2200, with no implicit current day',()=>{
  for(const day of ['1900-01-01','2000-02-29','2200-12-31'])assert.equal(accountingPreparationProfile({...profile(),bookkeeping_start:day}).bookkeeping_start,day);
  for(const day of ['1899-12-31','2201-01-01','1900-02-29','2100-02-29','2026-02-30','2026-1-01','2026-11-03T00:00:00Z',0])assert.throws(()=>accountingPreparationProfile({...profile(),bookkeeping_start:day}));
});
test('reason and evidence preserve exact explicit text and reject empty or unsafe input',()=>{
  assert.equal(body().reason,' Explicit owner statement ');assert.equal(body().evidence_reference,' SYN-PROFILE-1 ');
  for(const field of ['reason','evidence_reference'])for(const value of ['',null,'  ','two\nlines','tab\tvalue','DEL\x7f','lone\ud800'])assert.throws(()=>accountingProfilePreviewData(source(),{...values(),[field]:value}));
  assert.throws(()=>accountingProfilePreviewData(source(),{...values(),reason:'a'.repeat(1001)}));assert.throws(()=>accountingProfilePreviewData(source(),{...values(),evidence_reference:'a'.repeat(201)}));
  assert.equal(accountingProfilePreviewData(source(),{...values(),reason:'a'.repeat(1000)}).reason.length,1000);
  assert.throws(()=>accountingProfilePreviewData({...source(),writes_allowed:false},values()));
});
test('profile state and immutable entries distinguish unrecorded and recorded, never configured',()=>{
  assert.equal(accountingProfileState(source()).current,null);
  assert.equal(accountingProfileState({...source(),revision:2,preparation_status:'recorded',current:entry(2)}).revision,2);
  for(const change of [{revision:true},{revision:-1},{revision:1},{current:entry()},{preparation_status:'configured'},{writes_allowed:'true'},{tax_status:'configured'},{tax_result_available:true},{scope:'authorized_sources'},{unexpected:1}])assert.throws(()=>accountingProfileState({...source(),...change}));
  for(const change of [{revision:0},{created_at:'2026-02-30T12:00:00+00:00'},{created_at:'2026-11-03T12:00:00+01:00'},{created_by:'person'},{previous_state_hash:'hash'},{tax_result_available:true},{reason:'\n'}])assert.throws(()=>accountingProfileEntry({...entry(),...change}));
  const old={profile_status:'unconfigured',tax_status:'unconfigured',tax_result_available:false,scope:'authorized_sources',writes_allowed:true};assert.equal(accountingStatus(old),old);assert.throws(()=>accountingStatus({...old,profile_status:'recorded'}));
});
test('history validates organization scope, distinct descending entries and genuine pagination',()=>{
  const page={items:[entry(2),entry()],total:2,next_offset:null,scope:'organization_profile'};assert.equal(accountingProfilePage(page),page);
  assert.equal(accountingProfilePage({...page,items:[entry(2)],next_offset:1}).next_offset,1);assert.equal(accountingProfilePage({...page,items:[]},100).items.length,0);
  for(const change of [{items:[entry(),entry(2)]},{items:[entry(),entry()]},{items:null},{total:-1},{next_offset:0},{next_offset:3},{scope:'authorized_sources'},{unexpected:true}])assert.throws(()=>accountingProfilePage({...page,...change}));
});
test('preview and explicit confirm bind the complete original facts, reason, reference and state',()=>{
  assert.equal(accountingProfilePreview(preview(),body()).profile.vat_regime,null);
  for(const change of [{expected_revision:1},{state_hash:hash('d')},{reason:body().reason.trim()},{evidence_reference:'OTHER'},{profile:{...profile(),vat_regime:'regular'}},{tax_result_available:true},{confirmation:true}])assert.throws(()=>accountingProfilePreview({...preview(),...change},body()));
  for(const confirmation of [false,'true',1,null])assert.throws(()=>accountingProfileConfirmData(body(),preview(),confirmation));
  const input=body(),confirmed=accountingProfileConfirmData(input,preview(),true);assert.notEqual(confirmed.profile,input.profile);assert.equal(confirmed.confirmation,true);assert.equal('request_id'in confirmed,false);input.profile.vat_regime='regular';assert.equal(confirmed.profile.vat_regime,null);
});
test('fresh metadata and own state authorize replay after later profile versions, with no source graph',async()=>{
  const paths=[],later={...source(),revision:2,preparation_status:'recorded',current:entry(2)};
  const api={get:async path=>{paths.push(path);return path==='/business/capabilities'?caps():later;}};
  assert.equal((await accountingProfileAuthorize(api,{write:true})).revision,2);assert.deepEqual(paths,['/business/capabilities','/business/accounting/profile']);
  for(const permissions of [['finance.read'],['accounting.read','finance.read','accounting.prepare','finance.write']])await assert.rejects(accountingProfileAuthorize({get:async path=>path.endsWith('/capabilities')?{...caps(),permissions}:source()},{write:true}),error=>error.status===403);
  await assert.rejects(accountingProfileAuthorize({get:async path=>path.endsWith('/capabilities')?caps():{...source(),writes_allowed:false}},{write:true}),error=>error.status===423);
  await assert.rejects(accountingProfileAuthorize(api,{write:true,online:false}),error=>error.status===0);
  assert.equal((await accountingProfileAuthorize({get:async path=>path.endsWith('/capabilities')?{...caps(),permissions:['accounting.read','finance.read']}:source()})).revision,0);
});
test('first and later denied profile confirms retain exact path, body and request id until accepted',async()=>{
  for(const first of [0,403,404]) {
    const calls=[];let status=first;
    const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(!status)throw new Error('Uncertain reply');return new Response(JSON.stringify(status===201?entry():{error:'Current gate'}),{status});}});api.setToken('synthetic-profile-session-only');
    await assert.rejects(api.mutate('profile',confirmPath,confirmed()));assert.equal(api.pendingCount,1);
    for(const denied of [403,404,409,423,500]){status=denied;await assert.rejects(api.retry('profile'));assert.equal(api.pendingCount,1);}
    await assert.rejects(api.mutate('profile',confirmPath,{...confirmed(),reason:'Changed'}),/unveränderte Eingabe/);
    status=201;assert.deepEqual(await api.retry('profile'),entry());assert.equal(api.pendingCount,0);for(const call of calls)assert.deepEqual(call,calls[0]);
  }
});
test('only exact marked conflict releases uncertain profile command and a new request gets a new id',async()=>{
  const calls=[];let resolution='unknown';
  const api=new OfficeApi({fetcher:async(_path,options)=>{calls.push(JSON.parse(options.body));return new Response(JSON.stringify({error:'Stale',request_resolution:resolution}),{status:409});}});api.setToken('synthetic-profile-session-only');
  await assert.rejects(api.mutate('profile',confirmPath,confirmed()));assert.equal(api.pendingCount,1);resolution='not_accepted';await assert.rejects(api.retry('profile'));assert.equal(api.pendingCount,0);assert.deepEqual(calls[0],calls[1]);
  await assert.rejects(api.mutate('profile',confirmPath,{...confirmed(),reason:'New reviewed reason'}));assert.notEqual(calls[1].request_id,calls[2].request_id);
});
test('preview has no pending command and late reply cannot cross logout or identity change',async()=>{
  const calls=[];let resolve;
  const api=new OfficeApi({fetcher:async(path,options)=>{calls.push({path,body:JSON.parse(options.body)});if(path.endsWith('/preview'))return new Response(JSON.stringify(preview()));return new Promise(done=>{resolve=done;});}});api.setToken('synthetic-first-profile-session');
  await api.post('/business/accounting/profile/preview',body());assert.equal(api.pendingCount,0);assert.equal('request_id'in calls[0].body,false);
  const pending=api.mutate('profile',confirmPath,confirmed());await Promise.resolve();assert.equal(api.pendingCount,1);api.setToken('synthetic-second-profile-session');resolve(new Response(JSON.stringify(entry()),{status:201}));await assert.rejects(pending);assert.equal(api.pendingCount,0);
});
