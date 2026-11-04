import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {catalogAccess,catalogStatusAccess,catalogDecimal,catalogDatanormPrice,catalogRun,catalogChanges,catalogFile,CatalogContext} from '../catalog-imports.js';
import {OfficeApi} from '../office.js';
const id='a'.repeat(32),runId='b'.repeat(32),hash='c'.repeat(64);
const caps={capabilities:['business_adapters','business_catalog_imports'],permissions:['settings.manage','finance.read','finance.write'],readonly:false,features:['organization_modules'],organization:{modules:{documents:{enabled:true}}}};
const fixtures=JSON.parse(fs.readFileSync(new URL('./fixtures/catalog-import-previews.json',import.meta.url))).cases;
const row={code:'ART-1',name:'Original',unit:'ST',cost_price_net:'10.0000',unit_price_net:'20',tax_rate:'19'};
const run={id:runId,adapter_id:id,profile:'catalog_csv_v1',status:'staged',source_sha256:hash,rows:[row],result:{target_revisions:{}}};
test('catalog access requires current global settings and finance rights plus the original-storage module',()=>{
 assert.deepEqual(catalogAccess(caps),{read:true,write:true});
 for(const permission of ['settings.manage','finance.read'])assert.equal(catalogAccess({...caps,permissions:caps.permissions.filter(p=>p!==permission)}).read,false);
 assert.equal(catalogAccess({...caps,capabilities:['business_adapters']}).read,false);
 assert.equal(catalogAccess({...caps,permissions:caps.permissions.filter(p=>p!=='finance.write')}).write,false);
 assert.equal(catalogAccess({...caps,readonly:true}).write,false);
 assert.deepEqual(catalogAccess({...caps,organization:{modules:{documents:{enabled:false}}}}),{read:true,write:false});
 assert.equal(catalogAccess({...caps,organization:undefined}).write,false);
});
test('money remains exact, DATANORM unit basis rounds half up independently',()=>{
 assert.equal(catalogDatanormPrice({source_price_integer:'15005',price_basis:'100'},'0.01'),'1.5005');
 assert.equal(catalogDatanormPrice({source_price_integer:'15',price_basis:'10'},'0.0001'),'0.0002');
 assert.equal(catalogDatanormPrice({source_price_integer:'99999999999999',price_basis:'1000'},'0.01'),'1000000000.0000');
 for(const value of [null,'','-1','1e2','0.00001','01'])assert.throws(()=>catalogDecimal(value));
 assert.throws(()=>catalogDatanormPrice({source_price_integer:'1',price_basis:'100'},'0'));
});
for(const fixture of fixtures)test('actual backend preview contract: '+fixture.name,()=>{
 const changes=catalogChanges(fixture.run,fixture.mapping,fixture.preview);assert.equal(changes.length,fixture.run.rows.length);assert.equal(changes[0].action,fixture.preview.rows[0].action);
 if(fixture.name.includes('noop')){assert.equal(changes[0].kind,'same');assert.equal(changes[0].next.cost_known,false);assert.deepEqual(changes[0].differences,[]);}
});
test('server preview rejects changed original, mapping, target revision, price and a dishonest no-op',()=>{
 for(const fixture of fixtures){const clone=()=>structuredClone(fixture.preview);
  let broken=clone();broken.source_sha256='a'.repeat(64);assert.throws(()=>catalogChanges(fixture.run,fixture.mapping,broken));
  broken=clone();broken.price_mapping={extra:'1'};assert.throws(()=>catalogChanges(fixture.run,fixture.mapping,broken));
  broken=clone();broken.rows[0].revision=999;assert.throws(()=>catalogChanges(fixture.run,fixture.mapping,broken));
  broken=clone();broken.rows[0].after.cost_price_net='999';assert.throws(()=>catalogChanges(fixture.run,fixture.mapping,broken));
  if(fixture.preview.rows[0].action==='noop'){broken=clone();broken.rows[0].after.cost_known=true;assert.throws(()=>catalogChanges(fixture.run,fixture.mapping,broken),/unveränderte/);}
 }
});
test('ACK validation binds exact source, run, unique rows and profile',()=>{
 assert.equal(catalogRun(run,{adapterId:id,sourceHash:hash,runId}),run);
 for(const broken of [{...run,source_sha256:'d'.repeat(64)},{...run,adapter_id:runId},{...run,id:id},{...run,rows:[row,row]},{...run,status:'exported'},{...run,profile:'catalog_csv_v2'}])assert.throws(()=>catalogRun(broken,{adapterId:id,sourceHash:hash,runId}));
});
test('file reader retains CP850 bytes and rejects oversize or changed length',async()=>{
 const raw=new Uint8Array([65,59,78,59,132,13,10]);
 const result=await catalogFile({name:'Katalog.001',size:raw.length,arrayBuffer:async()=>raw.buffer});
 assert.deepEqual(Buffer.from(result.body.content_base64,'base64'),Buffer.from(raw));assert.equal(result.sha256.length,64);assert.equal(result.body.filename,'Katalog.001');
 for(const size of [0,2097153,NaN])await assert.rejects(catalogFile({size}));
 await assert.rejects(catalogFile({size:1,arrayBuffer:async()=>raw.buffer}),/Dateigröße/);
});
test('context invalidation never revives after background, next editor or same-state session stamp replacement',()=>{
 let stamp='session1/1';const context=new CatalogContext(()=>stamp),original=context.begin();assert.equal(context.current(original),true);context.invalidate();assert.equal(context.current(original),false);
 const next=context.begin();stamp='session2/1';assert.equal(context.current(next),false);const third=context.begin();context.begin();assert.equal(context.current(third),false);
});
function harness(){let lose=true,rights=structuredClone(caps),hook=null,reply=structuredClone(run);const posts=[],reads=[];
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='POST'){posts.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('accepted ACK lost');}return Response.json(reply);}reads.push(url);await hook?.();return Response.json(rights);}});api.setToken('synthetic-catalog-session-token');
 return {api,posts,reads,setRights(value){rights=value;},hook(value){hook=value;},reply(value){reply=value;}};
}
for(const [name,key,path,body]of [['import','catalog-import-'+id,`/business/adapters/${id}/import`,{filename:'Original.csv',content_base64:'eA=='}],['acceptance','catalog-apply-'+runId,`/business/adapters/imports/${runId}/apply`,{confirmed:true}],['configuration','catalog-create','/business/adapters',{name:'Synthetic catalog',profile:'catalog_csv_v1',enabled:true}]])test(`${name} retries exact original request_id after lost ACK and temporary rights withdrawal`,async()=>{
 const h=harness();await assert.rejects(h.api.mutate(key,path,body));h.setRights({...caps,permissions:[]});await assert.rejects(h.api.retry(key),/Finanzfreigabe/);assert.equal(h.posts.length,1);assert.equal(h.api.pendingCount,1);
 h.setRights(caps);await h.api.retry(key);assert.deepEqual(h.posts[0],h.posts[1]);assert.equal(h.api.pendingCount,0);assert.ok(h.reads.every(url=>url.endsWith('/business/capabilities')));
});
test('retry cannot post under another session established during authorization',async()=>{const h=harness(),key='catalog-import-'+id;await assert.rejects(h.api.mutate(key,`/business/adapters/${id}/import`,{content_base64:'eA=='}));h.hook(()=>h.api.setToken('synthetic-second-catalog-session'));await assert.rejects(h.api.retry(key));assert.equal(h.posts.length,1);});
test('uncertain 403,404,409 responses preserve pending import values instead of allocating another nonce',async()=>{for(const status of [403,404,409]){const posts=[];const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return Response.json(caps);posts.push(JSON.parse(options.body));return Response.json({error:'Unknown acceptance'},{status});}});api.setToken('synthetic-catalog-session-token');const key='catalog-import-'+id,path=`/business/adapters/${id}/import`;await assert.rejects(api.mutate(key,path,{content_base64:'eA=='}));assert.equal(api.pendingCount,1);await assert.rejects(api.retry(key));assert.deepEqual(posts[0],posts[1]);}});
test('malformed successful ACK retains original pending command and validator on retry',async()=>{const h=harness(),key='catalog-import-'+id,path=`/business/adapters/${id}/import`;await assert.rejects(h.api.mutate(key,path,{content_base64:'eA=='},{validate:value=>catalogRun(value,{sourceHash:hash})}));h.reply({...run,source_sha256:'e'.repeat(64)});await assert.rejects(h.api.retry(key),/Originaldatei/);assert.equal(h.api.pendingCount,1);h.reply(run);await h.api.retry(key);assert.deepEqual(h.posts[0],h.posts[2]);});

test('status-only settings access retains existing adapter status without exposing financial catalog history',()=>{const status={permissions:['settings.manage'],capabilities:['business_adapters']};assert.equal(catalogStatusAccess(status),true);assert.equal(catalogAccess(status).read,false);assert.equal(catalogStatusAccess({...status,permissions:[]}),false);});
test('catalog JSON expansion has an explicit 32 MiB ceiling without widening unrelated JSON paths',async()=>{
 let size=8*1024*1024;const api=new OfficeApi({fetcher:async()=>new Response('{}',{headers:{'Content-Type':'application/json','Content-Length':String(size)}})});api.setToken('synthetic-catalog-response-test');
 for(const path of [`/business/adapters/${id}/import`,`/business/adapters/imports/${runId}`,`/business/adapters/imports/${runId}/catalog-preview`,`/business/adapters/imports/${runId}/apply`])assert.deepEqual(await api.get(path),{});
 await assert.rejects(api.get('/business/articles'),/groß/);size=32*1024*1024+1;await assert.rejects(api.get(`/business/adapters/imports/${runId}/catalog-preview`),/groß/);
});
