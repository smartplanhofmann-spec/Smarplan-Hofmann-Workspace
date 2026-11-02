import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {PortalClient,consumeInvitation,portalView,portalDecisionPayload} from '../portal.js';
const id=letter=>letter.repeat(32),hash=letter=>letter.repeat(64),key='SPPI_'+'k'.repeat(43),token='SPPT_'+'t'.repeat(43),expiry='2099-11-02T15:00:00+00:00';
const invitation={grant_id:id('b'),key};
const source=()=>({offer:{id:id('a'),number:'ANG-TEST',revision:2,content_hash:hash('c'),pdf_hash:hash('d'),title:'Synthetic offer',issue_date:'2026-11-02',due_date:'2026-11-20',currency:'EUR',intro:'<img src=x onerror=unsafe()>',notes:'Terms',
  buyer:{name:'Synthetic buyer',address_line:'Example 1'},issuer:{company_name:'Synthetic issuer',address_line:'Example 2',payment_terms:'Pay as agreed'},
  positions:[{index:0,description:'Synthetic work',quantity:'2',unit:'m',unit_price_net:'5.0000',price_base_quantity:'1',discount_percent:'0',tax_rate:'19',tax_category:'S',tax_exemption_reason:'',net:'10.00'}],
  totals:{net:'10.00',tax:'1.90',gross:'11.90',payable:'11.90',tax_breakdown:[{rate:'19',category:'S',reason:'',net:'10.00',tax:'1.90'}]}},expires_at:expiry,decision:null,actions_allowed:true,
  statements:{version:'offer-decision-v1',accepted:'Ich nehme dieses konkrete Angebot an.',declined:'Ich lehne dieses konkrete Angebot ab.'}});
const values={decision:'accepted',declared_name:' Synthetic buyer ',confirmation:true};
const receipt=(payload={...portalDecisionPayload(source(),values,id('e'))})=>({id:id('f'),offer_id:id('a'),grant_id:id('b'),principal_id:id('e'),decision:payload.decision,declared_name:payload.declared_name,
  statement_version:payload.statement_version,statement_text:source().statements[payload.decision],content_hash:payload.content_hash,pdf_hash:payload.pdf_hash,created_at:'2026-11-02T14:00:00+00:00'});
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
const opened=async handler=>{const client=new PortalClient((path,options)=>path.endsWith('/sessions')?Promise.resolve(json({token,expires_at:expiry},201)):handler(path,options));await client.open(invitation);return client;};

test('invitation fragment is removed before validation and never becomes a query parameter',()=>{
  const calls=[],history={replaceState:(...args)=>calls.push(args)};
  const location={pathname:'/office/portal.html',search:'',hash:'#grant='+id('b')+'&key='+key};
  assert.deepEqual(consumeInvitation(location,history),invitation);assert.deepEqual(calls,[[null,'','/office/portal.html']]);
  for(const hash of ['#key=invalid','#grant='+id('b')+'&key='+key+'&key='+key,'#grant='+id('b')+'&key='+key+'&customer=anything']){
    const before=calls.length;assert.throws(()=>consumeInvitation({...location,hash},history));assert.equal(calls.length,before+1);
  }
});

test('public view projects only buyer, issuer, sales positions and totals',()=>{
  const value=source();value.office_secret='hidden';value.offer.buyer.internal_notes='hidden';value.offer.issuer.smtp_password='hidden';
  Object.assign(value.offer.positions[0],{cost_price_net:'999.00',pricing_snapshot:{profit_net:'999.00'},time_sources:['private']});
  value.offer.totals.margin='999.00';value.offer.totals.tax_breakdown[0].staff_cost='999.00';
  const result=portalView(value);assert.equal(JSON.stringify(result).includes('hidden'),false);assert.equal(JSON.stringify(result).includes('999.00'),false);
  assert.equal(result.offer.intro,value.offer.intro);assert.equal(result.offer.positions[0].net,'10.00');
  assert.throws(()=>portalView({...source(),actions_allowed:'true'}));
});

test('accepted and declined envelopes bind the exact source and statement version',()=>{
  for(const decision of ['accepted','declined'])assert.deepEqual(portalDecisionPayload(source(),{...values,decision},id('e')),
    {request_id:id('e'),content_hash:hash('c'),pdf_hash:hash('d'),decision,declared_name:'Synthetic buyer',statement_version:'offer-decision-v1',confirmation:true});
  for(const confirmation of [false,'true',1,null])assert.throws(()=>portalDecisionPayload(source(),{...values,confirmation},id('e')));
  for(const declared_name of ['', ' ', 'a'.repeat(201), 'One\nTwo'])assert.throws(()=>portalDecisionPayload(source(),{...values,declared_name},id('e')));
});

test('portal transport sends the invitation only in JSON and restricts the RAM bearer to portal routes',async()=>{
  const calls=[],client=new PortalClient(async(path,options)=>{calls.push({path,options});return path.endsWith('/sessions')?json({token,expires_at:expiry},201):json(source());});
  await client.open(invitation);await client.view();
  assert.equal(calls[0].path,'/api/v1/portal/sessions');assert.equal(calls[0].options.headers.Authorization,undefined);assert.deepEqual(JSON.parse(calls[0].options.body),invitation);
  assert.equal(calls[1].options.headers.Authorization,'Bearer '+token);
  for(const {path,options}of calls){assert.equal(path.includes(key),false);assert.equal(path.includes(token),false);assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');assert.equal(options.referrerPolicy,'no-referrer');assert.equal(options.cache,'no-store');}
  for(const path of ['https://elsewhere.test/offer','/business/documents','/offer?project=other','//offer'])await assert.rejects(client.request(path));
  const bad=new PortalClient(async()=>json({token:'OfficeBearer-'+'a'.repeat(50),expires_at:expiry},201));await assert.rejects(bad.open(invitation));assert.equal(bad.authenticated,false);
});

test('lost acknowledgement and temporary 423 retry one unchanged declaration',async()=>{
  const calls=[],client=await opened(async(path,options)=>{
    assert.equal(path,'/api/v1/portal/offer/decision');calls.push(JSON.parse(options.body));
    if(calls.length===1)throw new Error('Synthetic response loss');if(calls.length===2)return json({error:'paused'},423);return json(receipt(calls.at(-1)),201);
  });
  await assert.rejects(client.decide(source(),values),error=>error.status===0);assert.equal(client.pending,true);
  await assert.rejects(client.decide(source(),{...values,decision:'declined'}),/unveränderte Erklärung/);assert.equal(calls.length,1);
  await assert.rejects(client.decide(source(),values),error=>error.status===423);assert.equal(client.pending,true);
  assert.equal((await client.decide(source(),values)).decision,'accepted');assert.equal(client.pending,false);
  assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);
});

test('revocation clears RAM authorization and an actual conflicting decision is loaded explicitly',async()=>{
  let count=0;const revoked=await opened(async()=>{count++;return json({private_error:'not exposed'},403);});
  await assert.rejects(revoked.view(),error=>error.status===403&&!error.message.includes('private_error'));assert.equal(revoked.authenticated,false);
  await assert.rejects(revoked.view(),error=>error.status===401);assert.equal(count,1);
  const actual=receipt(),calls=[],conflict=await opened(async(path)=>{calls.push(path);return path.endsWith('/decision')?json({},409):json({...source(),decision:actual,actions_allowed:false});});
  await assert.rejects(conflict.decide(source(),values),error=>error.status===409);assert.equal(conflict.pending,false);
  assert.deepEqual((await conflict.view()).decision,actual);assert.deepEqual(calls,['/api/v1/portal/offer/decision','/api/v1/portal/offer']);
});

test('a late successful response after logout cannot restore an offer or bearer',async()=>{
  let resolve;const client=await opened(()=>new Promise(done=>resolve=done));const pending=client.view();client.clear();resolve(json(source()));
  await assert.rejects(pending,error=>error.status===401);assert.equal(client.authenticated,false);
});

test('unknown, oversized or mismatched acknowledgements do not confirm a decision',async()=>{
  for(const response of [()=>new Response('<html>private proxy details</html>',{status:200}),()=>json(source(),202),
    ()=>new Response('{}',{headers:{'Content-Length':'2000000'}})]){
    const client=await opened(response);await assert.rejects(client.view(),error=>!error.message.includes('private proxy'));
  }
  const client=await opened(async()=>json({...receipt(),pdf_hash:hash('e')},201));
  await assert.rejects(client.decide(source(),values),error=>error.status===502);assert.equal(client.pending,true);
});

test('PDF remains byte-identical and explicit logout clears the token even without an acknowledgement',async()=>{
  const original=Buffer.from('%PDF-1.7\nSynthetic original bytes'),calls=[];
  const client=await opened(async(path,options)=>{calls.push({path,options});if(path.endsWith('/logout'))throw new Error('Synthetic lost logout reply');return new Response(original,{headers:{'Content-Type':'application/pdf'}});});
  assert.deepEqual(Buffer.from(await (await client.pdf()).arrayBuffer()),original);
  await assert.rejects(client.logout());assert.equal(client.authenticated,false);assert.deepEqual(JSON.parse(calls[1].options.body),{});
});

test('customer assets never import the office shell or persist tokens and render text safely',async()=>{
  const [js,html]=await Promise.all([readFile(new URL('../portal.js',import.meta.url),'utf8'),readFile(new URL('../portal.html',import.meta.url),'utf8')]);
  assert.doesNotMatch(js,/\bimport\s|localStorage|sessionStorage|indexedDB|document\.cookie|innerHTML|insertAdjacentHTML|navigator\.clipboard/);
  assert.doesNotMatch(html,/office\.js|office\.css|https?:\/\/|onload=|onclick=/);assert.match(html,/name="referrer" content="no-referrer"/);
});
