import test from 'node:test';
import assert from 'node:assert/strict';
import {OfficeApi} from '../office.js';
import {economicsAmount,economicsCents,economicsRights,economicsSummary,economicsSources,economicsPreviewInput,economicsPreview,economicsEntry,economicsConfirmation,economicsReviewInput} from '../project-economics.js';
const project='a'.repeat(32),receipt='b'.repeat(32),actor='c'.repeat(32),hash='d'.repeat(64);
const clone=value=>JSON.parse(JSON.stringify(value));
function source(changes={}){return {id:receipt,project_id:project,filename:'synthetic.pdf',media_type:'application/pdf',sha256:hash,revision:2,status:'reviewed',vendor:'Synthetischer Lieferant',invoice_number:'SYN-1',issue_date:'2026-11-03',net:'100.00',tax:'19.00',gross:'119.00',classification_revision:0,classification_status:'unclassified',latest_entry:null,...changes};}
function summary(){return {project_id:project,currency:'EUR',valuation_basis:'document_net',tax_result_available:false,budget:{revision:1,base_net:'200.00',approved_changes_net:'50.00',total_net:'250.00',remaining_net:'107.50'},costs:{material_net:'25.00',labor_net:'17.50',external_service_net:'60.00',machine_net:'0.00',other_net:'40.00',total_net:'142.50'},revenue:{invoiced_net:'300.00',credited_net:'20.00',revenue_net:'280.00',invoiced_gross:'357.00',credited_gross:'23.80'},payments:{receipts_gross:'100.00',refunds_gross:'10.00',net_inflow_gross:'90.00',open_gross:'243.20',supplier_outflows_gross:'30.00',cash_balance_gross:'60.00',complete:true},result:{document_net_contribution:'137.50',complete_for_recorded_sources:true,scope:'recorded_sources_only'},issues:[],sources:{material_movements:[],approved_times:[],receipt_allocations:[],documents:[],payment_allocations:[],supplier_payments:[]}};}
function checked(){const input=economicsPreviewInput(source(),project,{external_service:'60',other:'40'},'Leistung und Auslagen laut geprüftem Beleg.');const proof={receipt_id:receipt,project_id:project,filename:'synthetic.pdf',vendor:'Synthetischer Lieferant',invoice_number:'SYN-1',issue_date:'2026-11-03',net:'100.00',tax:'19.00',gross:'119.00',original_sha256:hash,review_sha256:hash,source_hash:hash};const preview={...clone(input),source:proof,previous_entry_id:null,preview_hash:hash};const entry={...clone(preview),id:'e'.repeat(32),revision:1,created_by:actor,created_at:'2026-11-03T10:00:00+00:00',entry_hash:hash};return {input,preview,entry};}

test('exact cents preserve large totals and reject rounded or inferred amounts',()=>{
 assert.equal(economicsAmount('00012,4'),'12.40');assert.equal(economicsCents('999999999.99'),99999999999n);
 for(const value of ['0','-1','1.001','1e2','NaN','1000000000.00'])assert.throws(()=>economicsAmount(value));
 for(const value of [1,'1','1.0','1.001',null])assert.throws(()=>economicsCents(value));
});
test('project classification rights require both finance writing and approval without making reads writable',()=>{
 const caps={features:['project_economics'],capabilities:['business_project_economics'],active_capabilities:['business_project_economics'],permissions:['finance.read','finance.write','finance.approve'],readonly:false};
 assert.equal(economicsRights(caps).classify,true);
 assert.equal(economicsRights({...caps,permissions:['finance.read','finance.write']}).classify,false);
 assert.equal(economicsRights({...caps,permissions:['finance.read','finance.approve']}).review,true);
 assert.equal(economicsRights({...caps,readonly:true}).read,true);assert.equal(economicsRights({...caps,readonly:true}).capture,false);
 assert.equal(economicsRights({...caps,active_capabilities:[]}).classify,false);
 assert.equal(economicsRights(caps,{modules:{finance:{enabled:false}}}).classify,false);
 assert.equal(economicsRights({...caps,features:[]}).available,false);
});
test('net contribution and cash balance remain separate evidenced calculations',()=>{
 const value=summary();assert.equal(economicsSummary(value,project),value);assert.notEqual(value.result.document_net_contribution,value.payments.cash_balance_gross);
 for(const change of [v=>v.costs.total_net='242.50',v=>v.revenue.revenue_net='300.00',v=>v.payments.net_inflow_gross='100.00',v=>v.payments.cash_balance_gross='90.00',v=>v.budget.total_net='200.00']){const bad=summary();change(bad);assert.throws(()=>economicsSummary(bad,project));}
});
test('unknown costs suppress contribution and budget remaining rather than replacing them with zero',()=>{
 const value=summary();value.result.complete_for_recorded_sources=false;value.result.document_net_contribution=null;value.budget.remaining_net=null;value.issues=[{code:'receipt_unclassified',message:'Beleg noch nicht eingeordnet.'}];assert.equal(economicsSummary(value,project),value);
 for(const [key,path]of [['document_net_contribution','result'],['remaining_net','budget']]){const bad=clone(value);bad[path][key]='0.00';assert.throws(()=>economicsSummary(bad,project));}
});
test('unavailable supplier payments are explicitly null and cannot masquerade as a zero outflow',()=>{
 const value=summary();value.payments.complete=false;value.payments.supplier_outflows_gross=null;value.payments.cash_balance_gross=null;assert.equal(economicsSummary(value,project),value);
 value.payments.supplier_outflows_gross='0.00';assert.throws(()=>economicsSummary(value,project));
});
test('summary cannot change project, currency, valuation or tax meaning',()=>{
 for(const update of [{project_id:'f'.repeat(32)},{currency:'USD'},{valuation_basis:'cash'},{tax_result_available:true}])assert.throws(()=>economicsSummary({...summary(),...update},project));
 const value=summary();value.sources.approved_times=null;assert.throws(()=>economicsSummary(value,project));
});
test('whole receipt classification rejects partial, negative and duplicate category amounts',()=>{
 const original=source();assert.throws(()=>economicsPreviewInput(original,project,{other:'99.99'},'Grund'));
 assert.throws(()=>economicsPreviewInput(original,project,{other:'100',machine:'-1'},'Grund'));
 const complete=economicsPreviewInput(original,project,{other:'60',stock_material:'40'},'Beleg abgeglichen');
 assert.deepEqual(complete.allocations,[{category:'other',amount_net:'60.00'},{category:'stock_material',amount_net:'40.00'}]);
 const zero=source({net:'0.00',tax:'0.00',gross:'0.00'});assert.deepEqual(economicsPreviewInput(zero,project,{},'Nullbeleg geprüft').allocations,[]);
});
test('rejected receipts can only be explicitly excluded and a revision change is carried to preview',()=>{
 const rejected=source({status:'rejected',classification_revision:3});assert.throws(()=>economicsPreviewInput(rejected,project,{other:'100'},'Abgelehnt'));
 const value=economicsPreviewInput(rejected,project,{excluded:'100'},'Zurückgewiesener Beleg außerhalb Projektkosten');assert.equal(value.expected_revision,3);assert.equal(value.source_revision,2);
 assert.throws(()=>economicsPreviewInput(source({status:'needs_review'}),project,{other:'100'},'Ungeprüft'));
});
test('preview must retain full reviewed input and correction history is source bound',()=>{
 const {input,preview,entry}=checked();assert.equal(economicsPreview(preview,input),preview);assert.equal(economicsEntry(entry,project,receipt),entry);assert.equal(economicsConfirmation(entry,input,preview,actor),entry);
 const wrong=clone(preview);wrong.allocations[0].amount_net='50.00';assert.throws(()=>economicsPreview(wrong,input));
 for(const mutation of [v=>v.created_by='f'.repeat(32),v=>v.revision=2,v=>v.source_revision=3,v=>v.preview_hash='0'.repeat(64),v=>v.source.source_hash='0'.repeat(64)]){const bad=clone(entry);mutation(bad);assert.throws(()=>economicsConfirmation(bad,input,preview,actor));}
});
test('source lists reject cross-project references and duplicate receipts',()=>{
 assert.equal(economicsSources({items:[source()]},project).length,1);
 assert.throws(()=>economicsSources({items:[source(),source()]},project));assert.throws(()=>economicsSources({items:[source({project_id:'f'.repeat(32)})]},project));
 assert.throws(()=>economicsSources({items:[source({net:'99.99'})]},project));
});
test('receipt review verifies original amounts without inferring taxes or changing project binding',()=>{
 const values={vendor:' Firma ',invoice_number:' SYN-9 ',issue_date:'2026-11-03',net:'100',tax:'19',gross:'119',status:'reviewed',note:' geprüft '};
 const body=economicsReviewInput(source(),values);assert.equal(body.net,'100.00');assert.equal(body.tax,'19.00');assert.equal(body.revision,2);assert.equal(body.currency,'EUR');assert.equal('project_id' in body,false);
 assert.throws(()=>economicsReviewInput(source(),{...values,tax:''}));assert.throws(()=>economicsReviewInput(source(),{...values,gross:'120'}));
});
test('malformed acknowledgements retain the exact command and its validator through global retry',async()=>{
 const {input,preview,entry}=checked(),requests=[];let count=0;
 const api=new OfficeApi({fetcher:async(_path,options)=>{requests.push(JSON.parse(options.body));const result=clone(entry);if(++count<3)result.revision=9;return new Response(JSON.stringify(result),{status:200});}});api.setToken('synthetic-economics-owner-token');
 const body={...input,preview_hash:preview.preview_hash};await assert.rejects(api.mutate('classification','/business/project-economics/confirm',body,{validate:value=>economicsConfirmation(value,input,preview,actor)}));assert.equal(api.pendingCount,1);
 await assert.rejects(api.retry('classification'));assert.equal(api.pendingCount,1);
 await api.retry('classification');assert.equal(api.pendingCount,0);assert.deepEqual(requests[0],requests[1]);assert.deepEqual(requests[1],requests[2]);
});
test('uncertain confirmation remains unchanged across permission loss and opaque conflicts',async()=>{
 const {input,preview,entry}=checked(),requests=[],responses=[0,403,409,200];
 const api=new OfficeApi({fetcher:async(_path,options)=>{requests.push(JSON.parse(options.body));const status=responses.shift();if(!status)throw new Error('Lost real response');return new Response(JSON.stringify(status===200?entry:{error:'Current authorization or outcome unclear'}),{status});}});api.setToken('synthetic-economics-owner-token');
 const body={...input,preview_hash:preview.preview_hash};await assert.rejects(api.mutate('classification','/business/project-economics/confirm',body));
 for(let i=0;i<2;i++){await assert.rejects(api.retry('classification'));assert.equal(api.pendingCount,1);}
 await api.retry('classification');assert.equal(api.pendingCount,0);for(const request of requests)assert.deepEqual(request,requests[0]);
});
test('a proven not-accepted conflict permits a fresh preview and session changes discard memory',async()=>{
 const api=new OfficeApi({fetcher:async()=>new Response(JSON.stringify({error:'Receipt revision changed',request_resolution:'not_accepted'}),{status:409})});api.setToken('synthetic-economics-owner-token');await assert.rejects(api.mutate('classification','/business/project-economics/confirm',{}));assert.equal(api.pendingCount,0);
 api.fetcher=async()=>{throw new Error('Lost response');};await assert.rejects(api.mutate('classification','/business/project-economics/confirm',{}));assert.equal(api.pendingCount,1);api.clear();assert.equal(api.pendingCount,0);
});
test('original capture, receipt review and upload completion keep their nonce through a lost response and revoked rights',async()=>{
 for(const path of ['/business/finance/receipts','/business/finance/receipts/'+receipt,'/business/receipt-media','/business/receipt-media/'+receipt+'/complete']){
  const requests=[],responses=[0,403,409,200];const api=new OfficeApi({fetcher:async(_path,options)=>{requests.push(JSON.parse(options.body));const status=responses.shift();if(!status)throw new Error('Lost response');return new Response(JSON.stringify(status===200?{id:receipt}:{error:'Authorization or outcome unclear'}),{status});}});api.setToken('synthetic-economics-owner-token');
  await assert.rejects(api.mutate('original',path,{project_id:project}));await assert.rejects(api.retry('original'));await assert.rejects(api.retry('original'));assert.equal(api.pendingCount,1);await api.retry('original');assert.equal(api.pendingCount,0);for(const request of requests)assert.deepEqual(request,requests[0]);
 }
});

test('canonical server object key order does not change the approved allocation identity',()=>{
 const {input,preview,entry}=checked();preview.allocations=preview.allocations.map(({category,amount_net})=>({amount_net,category}));entry.allocations=entry.allocations.map(({category,amount_net})=>({amount_net,category}));assert.equal(economicsPreview(preview,input),preview);assert.equal(economicsConfirmation(entry,input,preview,actor),entry);
});
