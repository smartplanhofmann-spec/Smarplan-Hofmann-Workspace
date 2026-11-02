import test from 'node:test';
import assert from 'node:assert/strict';
import {PurchaseCatalog,OfficeApi} from '../office.js';

const article=(id,name='New stock article')=>({id,revision:2,code:'CAT-'+id,name,kind:'material',unit:'m',active:true});
const page=(items,total=items.length,next_offset=null)=>({items,total,next_offset});

test('purchasing catalogue requests the exact scope and page without retaining financial fields',async()=>{
  const calls=[],value={...article('a'),cost_price_net:'123.45',unit_price_net:'456.78',supplier_secret:'private'};
  const catalog=new PurchaseCatalog({enabled:true,projectId:'project-id',fetcher:async path=>{calls.push(new URL(path,'https://example.test'));return page([value]);}});
  await catalog.load('  Kabel & Teile  ');
  assert.equal(calls[0].pathname,'/business/purchasing/articles');
  assert.deepEqual(Object.fromEntries(calls[0].searchParams),{project_id:'project-id',query:'Kabel & Teile',limit:'25',offset:'0'});
  assert.deepEqual(catalog.choices(''),[article('a')]);
  assert.deepEqual(Object.keys(catalog.choices('')[0]).sort(),['active','code','id','kind','name','revision','unit']);
  catalog.setProject(null);await catalog.load('');
  assert.equal(calls[1].searchParams.has('project_id'),false);assert.equal(calls[1].searchParams.has('query'),false);
});

test('selected draft articles survive search and pagination without polluting other current results',async()=>{
  const saved=article('saved','Existing draft article'),calls=[];
  const catalog=new PurchaseCatalog({enabled:true,selected:[saved],fetcher:async path=>{
    const url=new URL(path,'https://example.test');calls.push(url);const offset=Number(url.searchParams.get('offset'));
    return url.searchParams.get('query')==='other'?page([article('other')]):offset===0?page([article('first')],2,1):page([article('second')],2);
  }});
  await catalog.load('first');assert.deepEqual(catalog.choices('saved').map(item=>item.id),['first','saved']);
  await catalog.load('first',true);assert.deepEqual(catalog.choices('saved').map(item=>item.id),['first','second','saved']);
  assert.equal(calls[1].searchParams.get('offset'),'1');
  await catalog.load('other');assert.deepEqual(catalog.choices('second').map(item=>item.id),['other','second']);
  assert.deepEqual(catalog.choices('saved').at(-1),saved);
  assert.deepEqual(catalog.choices('').map(item=>item.id),['other']);
});

test('changed query restarts pagination and late old scope results never replace current choices',async()=>{
  const waiting=[];
  const catalog=new PurchaseCatalog({enabled:true,projectId:'old',fetcher:path=>new Promise(resolve=>waiting.push({path,resolve}))});
  const old=catalog.load('old');catalog.setProject('new');const current=catalog.load('current');
  waiting[1].resolve(page([article('current')],2,1));assert.equal(await current,true);
  waiting[0].resolve(page([article('stale')]));assert.equal(await old,false);
  assert.deepEqual(catalog.choices('').map(item=>item.id),['current']);
  const changed=catalog.load('changed',true);assert.equal(new URL(waiting[2].path,'https://example.test').searchParams.get('offset'),'0');
  waiting[2].resolve(page([article('changed')]));await changed;
  assert.deepEqual(catalog.choices('').map(item=>item.id),['changed']);
});

test('legacy feature fallback remains local, filters physical active stock and retains draft choices',async()=>{
  const catalog=new PurchaseCatalog({enabled:false,fetcher:async()=>{throw new Error('Legacy server must not receive new endpoint');},
    items:[article('active','Cable'),{...article('inactive'),active:false},{...article('labor'),kind:'labor'}],selected:[article('historic')]});
  await catalog.load('CABLE');assert.deepEqual(catalog.choices('historic').map(item=>item.id),['active','historic']);
  await catalog.load('missing');assert.equal(catalog.total,0);assert.deepEqual(catalog.choices('historic').map(item=>item.id),['historic']);
});

test('invalid catalogue responses cannot replace reviewed choices or invent follow-up pages',async()=>{
  let response=page([article('reviewed')]);
  const catalog=new PurchaseCatalog({enabled:true,fetcher:async()=>response});await catalog.load('');
  for(const invalid of [page([article('x')],0),page([],2,0),page([],2,2),{items:[],total:'2',next_offset:null},page([{}])]){
    response=invalid;await assert.rejects(catalog.load('other'),error=>error.status===502);
    assert.deepEqual(catalog.choices('').map(item=>item.id),['reviewed']);
  }
});

test('catalogue searches leave an uncertain draft command unchanged for exact retry',async()=>{
  const requests=[];let mutationCount=0;
  const api=new OfficeApi({fetcher:async(path,options)=>{
    if(options.method==='POST'){requests.push(JSON.parse(options.body));if(++mutationCount===1)throw new Error('Lost acknowledgement');return new Response(JSON.stringify({id:'saved'}),{status:201});}
    return new Response(JSON.stringify(page([article('other')])));
  }});api.setToken('synthetic-memory-only');
  const draft={project_id:null,supplier_name:'Synthetic warehouse',status:'draft',items:[{article_id:'original',quantity:'2.0000'}]};
  await assert.rejects(api.mutate('draft','/business/inventory/orders',draft));
  const catalog=new PurchaseCatalog({enabled:true,fetcher:path=>api.get(path)});await catalog.load('other');
  assert.equal(api.pendingCount,1);await api.retry('draft');assert.deepEqual(requests[0],requests[1]);
  assert.deepEqual(requests[1].items,draft.items);
});
