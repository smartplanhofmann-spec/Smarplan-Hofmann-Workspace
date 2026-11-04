import test from 'node:test';
import assert from 'node:assert/strict';
import {loadInventoryArticleRefs} from '../office.js';
const id=n=>n.toString(16).padStart(32,'0');
const item=n=>({id:id(n),revision:1,code:'M'+n,name:'Material '+n,unit:'Stk.',active:true});
test('all price-free pages retain project scope and advancing cursors',async()=>{
  const calls=[];
  const values=await loadInventoryArticleRefs(async path=>{
    const url=new URL(path,'https://example.test');calls.push(url);
    const after=url.searchParams.get('after');
    return after?{items:[item(2)],has_more:false,next_after:null}:{items:[item(1)],has_more:true,next_after:id(1)};
  },{projectId:id(99)});
  assert.deepEqual(values,[item(1),item(2)]);assert.equal(calls.length,2);
  assert.ok(calls.every(url=>url.pathname==='/inventory/articles'&&url.searchParams.get('project_id')===id(99)&&url.searchParams.get('limit')==='200'));
  assert.equal(calls[1].searchParams.get('after'),id(1));
});
test('unknown price fields, unordered pages and broken continuation are not used as an article list',async()=>{
  for(const reply of [{items:[{...item(1),unit_price_net:'12.00'}],has_more:false,next_after:null},
      {items:[item(2),item(1)],has_more:false,next_after:null},
      {items:[],has_more:true,next_after:id(1)},
      {items:[item(1)],has_more:true,next_after:id(2)},
      {items:[item(1)],has_more:false,next_after:id(1)}]) {
    await assert.rejects(loadInventoryArticleRefs(async()=>reply));
  }
});
test('revoked or changed workspace rejects a pending page before another request',async()=>{
  let current=true,calls=0;
  await assert.rejects(loadInventoryArticleRefs(async()=>{calls++;current=false;return {items:[item(1)],has_more:true,next_after:id(1)};}, {isCurrent:()=>current}),/Arbeitsbereich/);
  assert.equal(calls,1);
  const denied=new Error('403');
  await assert.rejects(loadInventoryArticleRefs(async()=>{throw denied;}),error=>error===denied);
});
