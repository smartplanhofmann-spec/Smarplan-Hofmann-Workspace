import test from 'node:test';
import assert from 'node:assert/strict';
import {salesMinor,salesValues,salesOfferPositions,salesPendingAuthorize} from '../sales.js';
import {OfficeApi} from '../office.js';

const customer='a'.repeat(32),actor='b'.repeat(32),opportunity='c'.repeat(32),project='d'.repeat(32),article='e'.repeat(32);
const caps=()=>({readonly:false,features:['sales_pipeline'],capabilities:['business_sales'],permissions:['contacts.read','contacts.write','projects.manage','finance.read','finance.write'],organization:{modules:{documents:{enabled:true}}}});
const body=()=>({customer_id:customer,inquiry_id:null,revision:0,title:'Synthetic installation',person_id:null,stage:'qualified',expected_net_minor:123456,probability_percent:50,responsible_id:actor,follow_up_on:null,expected_close_on:null,description:'Forecast only',closure_reason:''});

test('forecast values preserve cents and closing probabilities require explicit reasons',()=>{
  assert.equal(salesMinor('1234,56'),123456);assert.equal(salesMinor('0.01'),1);
  for(const value of ['1.234','-1','NaN','1e3','1,234.56'])assert.throws(()=>salesMinor(value));
  const values={title:'Synthetic',stage:'qualified',expected_net:'1234,56',probability_percent:50,responsible_id:actor};
  const result=salesValues(values,{customerId:customer});assert.equal(result.expected_net_minor,123456);assert.equal(result.inquiry_id,null);
  assert.throws(()=>salesValues({...values,stage:'won'},{customerId:customer}));
  assert.throws(()=>salesValues({...values,stage:'lost',probability_percent:0},{customerId:customer}));
  assert.equal(salesValues({...values,stage:'won',probability_percent:100,closure_reason:'Explicit signed agreement'},{customerId:customer}).probability_percent,100);
});
test('offer transfers only catalogue identity, revision and deliberate quantity',()=>{
  const items=[{id:article,revision:4,active:true,unit_price_net:'79.95'}];
  assert.deepEqual(salesOfferPositions([{article_id:article,quantity:'2,5',unit_price_net:'0.01'}],items),[{article_id:article,article_revision:4,quantity:'2.5'}]);
  for(const values of [[],[{article_id:article,quantity:'0'}],[{article_id:customer,quantity:'1'}]])assert.throws(()=>salesOfferPositions(values,items));
  assert.throws(()=>salesOfferPositions([{article_id:article,quantity:'1'}],[{...items[0],active:false}]));
});
test('pending create verifies fresh rights and original contact identity',async()=>{
  const reads=[],api={pendingCommandValues:()=>body(),get:async path=>{reads.push(path);return path.includes('capabilities')?caps():{customer_id:customer};}};
  await salesPendingAuthorize(api,{key:'sales-save-new-'+customer,path:'/business/sales/opportunities'});
  assert.deepEqual(reads,['/business/capabilities','/business/sales/options?customer_id='+customer]);
  api.get=async path=>path.includes('capabilities')?{...caps(),permissions:['contacts.read']}:{customer_id:customer};
  await assert.rejects(salesPendingAuthorize(api,{key:'sales-save-new-'+customer,path:'/business/sales/opportunities'}));
  api.get=async path=>path.includes('capabilities')?caps():{customer_id:actor};
  await assert.rejects(salesPendingAuthorize(api,{key:'sales-save-new-'+customer,path:'/business/sales/opportunities'}));
});
test('offer retry rejects a paused document module and revoked project rights',async()=>{
  const api={pendingCommandValues:()=>({revision:1}),get:async path=>path.includes('capabilities')?caps():{id:opportunity,links:[{kind:'project',project_id:project}]}};
  const operation={key:'sales-offer-'+opportunity,path:'/business/sales/opportunities/'+opportunity+'/offer'};
  await salesPendingAuthorize(api,operation);
  for(const scoped of [{...caps(),permissions:['contacts.read','contacts.write','projects.manage']},{...caps(),organization:{modules:{documents:{enabled:false}}}}]){
    api.get=async path=>path.includes('?project_id=')?scoped:path.includes('capabilities')?caps():{id:opportunity,links:[{kind:'project',project_id:project}]};
    await assert.rejects(salesPendingAuthorize(api,operation));
  }
});
test('lost create acknowledgement survives rights revocation and reuses exact request',async()=>{
  let permitted=true,lose=true;const sent=[];
  const api=new OfficeApi({fetcher:async (url,options)=>{
    if(options.method==='GET')return new Response(JSON.stringify(url.includes('capabilities')?{...caps(),permissions:permitted?caps().permissions:['contacts.read']}:{customer_id:customer}));
    sent.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('Synthetic lost ACK');}
    return new Response(JSON.stringify({...body(),id:opportunity,revision:1}));
  }});
  api.setToken('synthetic-sales-owner-token');
  await assert.rejects(api.mutate('sales-save-new-'+customer,'/business/sales/opportunities',body()));
  permitted=false;await assert.rejects(api.retry('sales-save-new-'+customer));assert.equal(sent.length,1);assert.equal(api.pendingCount,1);
  permitted=true;const recovered=await api.retry('sales-save-new-'+customer);assert.equal(recovered.id,opportunity);assert.deepEqual(sent[1],sent[0]);assert.equal(api.pendingCount,0);
});
