import test from 'node:test';
import assert from 'node:assert/strict';
import {assetOriginValues} from '../asset-provenance.js';

const id=letter=>letter.repeat(32);
const source=()=>({receipt_id:id('a'),line_index:2,document_accessible:true,document:{content_hash:'e'.repeat(64)},
  article:{id:id('b'),name:'Gerät',unit:'Stk.'},issues:[{id:id('c'),available_quantity:'2.0000'}]});
const values=()=>({name:' Gerät ',serial_number:' SYN-1 ',asset_type:' Pumpe ',location:' Raum ',notes:' Hinweis ',
  issue_movement_id:id('c'),quantity:'1,2500',confirmed:true});

test('a confirmed physical origin contains exact decimal quantity and only source references',()=>{
  const input=source(),snapshot=structuredClone(input),result=assetOriginValues(input,values());
  assert.deepEqual(result,{receipt_id:id('a'),line_index:2,issue_movement_id:id('c'),quantity:'1.2500',confirmed:true,
    asset:{name:'Gerät',serial_number:'SYN-1',asset_type:'Pumpe',location:'Raum',notes:'Hinweis'}});
  assert.deepEqual(input,snapshot);
  assert.equal('unit_cost_net' in result,false);
});
test('existing device uses its revision without silently creating another asset',()=>{
  const result=assetOriginValues(source(),values(),{id:id('d'),revision:7});
  assert.equal(result.asset_revision,7);assert.equal('asset' in result,false);
});
test('unavailable originals, unrelated issues and implicit confirmation cannot be submitted',()=>{
  for(const changed of [{document_accessible:false},{document:null},{issues:[{id:id('f')}]},{line_index:-1},{receipt_id:'wrong'}])
    assert.throws(()=>assetOriginValues({...source(),...changed},values()));
  for(const confirmed of [false,undefined,'true',1])assert.throws(()=>assetOriginValues(source(),{...values(),confirmed}));
});
test('quantities are positive exact strings and incomplete device identity is rejected',()=>{
  for(const quantity of ['0','0.0000','-1','1.12345','1e2','NaN'])assert.throws(()=>assetOriginValues(source(),{...values(),quantity}));
  for(const field of ['name','serial_number'])assert.throws(()=>assetOriginValues(source(),{...values(),[field]:' '}));
});
