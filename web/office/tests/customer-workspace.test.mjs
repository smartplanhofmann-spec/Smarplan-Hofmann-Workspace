import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {CustomerWorkspaceClient,WorkspaceError,consumeWorkspaceInvitation,workspaceView,workspaceUploadPayload,workspaceSHA256,WORKSPACE_UPLOAD_LIMIT} from '../customer-workspace.js';

const id=c=>c.repeat(32),grant=id('a'),project=id('b'),fileId=id('c'),uploadId=id('d');
const key='SPCI_'+'x'.repeat(43),token='SPCT_'+'y'.repeat(43),expiry='2099-01-01T12:00:00+00:00';
const invitation={grant_id:grant,key},original=new TextEncoder().encode('%PDF-1.7\nSynthetic original\n%%EOF');
const hash=await workspaceSHA256(original),file=()=>new File([original],'Original.pdf',{type:'application/pdf'});
const metadata=()=>({id:fileId,project_id:project,filename:'Original.pdf',media_type:'application/pdf',size:original.length,sha256:hash,created_at:'2026-11-03T12:00:00+00:00'});
const view=()=>({grant_id:grant,project:{id:project,name:'Synthetisches Projekt',customer:'Synthetischer Kunde'},publication:{id:id('e'),revision:1,title:'Freigegebener Stand',description:'Leistung <script> ist Text.',status_label:'Geplant',start_date:'2026-11-04',end_date:null,published_at:'2026-11-03T12:00:00+00:00'},files:[{...metadata(),title:'Freigegebenes Original'}],uploads:[],expires_at:expiry,uploads_allowed:true});
const receipt=body=>({...metadata(),id:uploadId,grant_id:grant,filename:body.filename,media_type:body.media_type,size:body.size,sha256:body.sha256,note:body.note,status:'received'});
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
async function opened(handler){const client=new CustomerWorkspaceClient((path,options)=>path.endsWith('/sessions')?Promise.resolve(json({token,expires_at:expiry},201)):path.endsWith('/workspace')?Promise.resolve(json(view())):handler(path,options));await client.open(invitation);await client.view();return client;}

test('project invitations remove secret fragments and query data before validation; offer tokens never work',()=>{
  const calls=[],history={replaceState:(...values)=>calls.push(values)},location={pathname:'/office/customer-workspace.html',search:'',hash:'#grant='+grant+'&key='+key};
  assert.deepEqual(consumeWorkspaceInvitation(location,history),invitation);assert.deepEqual(calls[0],[null,'',location.pathname]);
  for(const changes of [{hash:'#grant='+grant+'&key='+key+'&key='+key},{hash:'#grant='+grant+'&key=SPPI_'+'x'.repeat(43)},{search:'?key=secret'},{hash:'#grant=wrong&key='+key}]){const before=calls.length;assert.throws(()=>consumeWorkspaceInvitation({...location,...changes},history));assert.equal(calls.length,before+1);assert.equal(calls.at(-1)[2],location.pathname);}
});

test('public view retains only explicitly released information and rejects foreign or duplicate objects',()=>{
  const input=view();input.internal_margin='private';input.project.finance={net:'private'};input.publication.employee='private';input.files[0].source_id='private';
  const result=workspaceView(input,grant);assert.equal(JSON.stringify(result).includes('private'),false);assert.match(result.publication.description,/<script>/);
  for(const changes of [{grant_id:id('f')},{project:{...input.project,id:id('f')}},{files:[{...metadata(),project_id:id('f')}]},{files:[input.files[0],input.files[0]]},{uploads_allowed:'true'}])assert.throws(()=>workspaceView({...view(),...changes},grant,project));
});

test('upload payload binds exact bytes and preserves a safe filename with normalized explicit note',async()=>{
  const result=await workspaceUploadPayload(file(),'  Synthetischer Hinweis  ',id('f'));
  assert.deepEqual(result,{request_id:id('f'),filename:'Original.pdf',media_type:'application/pdf',size:original.length,sha256:hash,content_base64:Buffer.from(original).toString('base64'),note:'Synthetischer Hinweis'});
  await assert.rejects(workspaceUploadPayload(new File([],'empty.pdf',{type:'application/pdf'}),'',id('f')));
  await assert.rejects(workspaceUploadPayload(new File([original],'../private.pdf',{type:'application/pdf'}),'',id('f')));
  await assert.rejects(workspaceUploadPayload(new File([original],'active.svg',{type:'image/svg+xml'}),'',id('f')));
  await assert.rejects(workspaceUploadPayload({name:'too.pdf',type:'application/pdf',size:WORKSPACE_UPLOAD_LIMIT+1,arrayBuffer:()=>{throw new Error('Must not load oversized file');}},'',id('f')));
  await assert.rejects(workspaceUploadPayload({name:'changed.pdf',type:'application/pdf',size:9,arrayBuffer:async()=>original.buffer},'',id('f')));
});

test('transport sends distinct bearer only to bounded customer workspace routes without cookies or redirects',async()=>{
  const calls=[],client=new CustomerWorkspaceClient(async(path,options)=>{calls.push({path,options});return path.endsWith('/sessions')?json({token,expires_at:expiry},201):json(view());});
  await client.open(invitation);await client.view();
  assert.equal(calls[0].options.headers.Authorization,undefined);assert.deepEqual(JSON.parse(calls[0].options.body),invitation);assert.equal(calls[1].options.headers.Authorization,'Bearer '+token);
  for(const {path,options} of calls){assert.ok(path.startsWith('/api/v1/customer-workspace/'));assert.ok(!path.includes(key)&&!path.includes(token));assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');assert.equal(options.referrerPolicy,'no-referrer');assert.equal(options.cache,'no-store');}
  for(const path of ['/business/documents','/portal/offer','https://other.test/workspace','//workspace','/workspace?project_id='+project])await assert.rejects(client.request(path));
  const old=new CustomerWorkspaceClient(async()=>json({token:'SPPT_'+'y'.repeat(43),expires_at:expiry},201));await assert.rejects(old.open(invitation));assert.equal(old.authenticated,false);
});

test('lost upload response and module pause retain exactly one unchanged command',async()=>{
  const calls=[],client=await opened(async(path,options)=>{assert.equal(path,'/api/v1/customer-workspace/uploads');const body=JSON.parse(options.body);calls.push(body);if(calls.length===1)throw new Error('Synthetic lost commit acknowledgement');if(calls.length===2)return json({},423);return json(receipt(body),201);});
  await assert.rejects(client.upload(file(),'Original hint'),error=>error.status===0);assert.equal(client.pending,true);
  await assert.rejects(client.upload(file(),'Changed hint'),error=>error.status===409);assert.equal(calls.length,1);
  await assert.rejects(client.retryUpload(),error=>error.status===423);assert.equal(client.pending,true);
  assert.equal((await client.retryUpload()).status,'received');assert.equal(client.pending,false);assert.deepEqual(calls[0],calls[1]);assert.deepEqual(calls[1],calls[2]);
});

test('a validation rejection allows a corrected upload without retaining uncertain data',async()=>{
  const calls=[],client=await opened(async(path,options)=>{const body=JSON.parse(options.body);calls.push(body);return calls.length===1?json({},400):json(receipt(body),201);});
  await assert.rejects(client.upload(file(),'First'),error=>error.status===400);assert.equal(client.pending,false);await client.upload(file(),'Corrected');assert.notEqual(calls[0].request_id,calls[1].request_id);
});

test('unknown or mismatched upload receipts never report success or discard original command',async()=>{
  for(const change of [{sha256:'f'.repeat(64)},{project_id:id('f')},{grant_id:id('f')},{note:'Changed'},{size:original.length+1},{filename:'Different.pdf'},{status:'approved'}]){
    const client=await opened(async(path,options)=>json({...receipt(JSON.parse(options.body)),...change},201));await assert.rejects(client.upload(file(),'Original'),error=>error.status===502);assert.equal(client.pending,true);
  }
});

test('revocation clears current credentials and private pending upload from memory',async()=>{
  let calls=0;const client=await opened(async()=>{calls++;if(calls===1)throw new Error('Lost response');return json({private_detail:'hidden'},403);});
  await assert.rejects(client.upload(file(),'Private hint'));assert.equal(client.pending,true);
  await assert.rejects(client.retryUpload(),error=>error.status===403&&!error.message.includes('hidden'));assert.equal(client.pending,false);assert.equal(client.authenticated,false);
  await assert.rejects(client.view(),error=>error.status===401);assert.equal(calls,2);
});

test('late receipt after explicit session clear cannot confirm or restore private data',async()=>{
  let resolve,captured;const client=await opened((path,options)=>{captured=JSON.parse(options.body);return new Promise(done=>resolve=done);});
  const operation=client.upload(file(),'Late');while(!resolve)await new Promise(done=>setTimeout(done,0));client.clear();resolve(json(receipt(captured),201));await assert.rejects(operation,error=>error.status===401);assert.equal(client.authenticated,false);assert.equal(client.pending,false);
});

test('download verifies released size, media type, project and hash before producing an original Blob',async()=>{
  const client=await opened(async()=>new Response(original,{headers:{'Content-Type':'application/pdf'}}));
  assert.deepEqual(Buffer.from(await (await client.download(metadata())).arrayBuffer()),Buffer.from(original));
  await assert.rejects(client.download({...metadata(),project_id:id('f')}));
  for(const response of [()=>new Response(original,{headers:{'Content-Type':'image/png'}}),()=>new Response(new Uint8Array(original.length),{headers:{'Content-Type':'application/pdf'}}),()=>new Response(original.slice(0,-1),{headers:{'Content-Type':'application/pdf'}})]){
    const corrupt=await opened(response);await assert.rejects(corrupt.download(metadata()),error=>error.status===502);
  }
});

test('own upload original uses own upload path and rejects another grant',async()=>{
  let lastPath;const client=await opened(async path=>{lastPath=path;return new Response(original,{headers:{'Content-Type':'application/pdf'}});});
  const row=receipt(await workspaceUploadPayload(file(),'note',id('f')));await client.download(row,{upload:true});assert.equal(lastPath,'/api/v1/customer-workspace/uploads/'+uploadId+'/content');
  await assert.rejects(client.download({...row,grant_id:id('f')},{upload:true}));
});

test('malformed, oversized, wrong-status and untrusted HTML responses stay closed',async()=>{
  for(const response of [()=>new Response('<html>private proxy detail</html>',{status:200}),()=>json(view(),202),()=>new Response('{}',{headers:{'Content-Type':'application/json','Content-Length':'99999999'}}),()=>new Response(new Uint8Array([255,254]),{headers:{'Content-Type':'application/json'}})]){
    const client=new CustomerWorkspaceClient((path)=>path.endsWith('/sessions')?Promise.resolve(json({token,expires_at:expiry},201)):Promise.resolve(response()));await client.open(invitation);await assert.rejects(client.view(),error=>error instanceof WorkspaceError&&!error.message.includes('private proxy'));
  }
});

test('logout clears the bearer even when its acknowledgement is lost',async()=>{
  const client=await opened(async()=>{throw new Error('Synthetic lost logout response');});await assert.rejects(client.logout());assert.equal(client.authenticated,false);assert.equal(client.pending,false);
});

test('customer assets stay isolated, project content is text and credentials are never persisted',async()=>{
  const source=await readFile(new URL('../customer-workspace.js',import.meta.url),'utf8');
  assert.ok(!/localStorage|sessionStorage|indexedDB|innerHTML|insertAdjacentHTML|document\.cookie|serviceWorker/.test(source));
  assert.ok(!/from ['"]\.\/office\.js/.test(source));assert.match(source,/document\.createTextNode/);assert.match(source,/beforeunload/);assert.match(source,/Eingegangen · interne Übernahme ausstehend/);
  const html=await readFile(new URL('../customer-workspace.html',import.meta.url),'utf8');assert.ok(!/https?:\/\//.test(html));assert.match(html,/name="referrer" content="no-referrer"/);assert.match(html,/customer-workspace\.js/);
});
