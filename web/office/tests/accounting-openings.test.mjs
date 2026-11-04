import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {OfficeApi} from '../office.js';
import {OPENING_PATH,openingMoney,openingOriginal,openingState,openingSources,openingInput,openingPreview,openingRecord,openingHistory,openingReceiptValidator,openingUploadValidator,openingLiquidity,openingPendingAuthorize} from '../accounting-openings.js';
const f=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_openings_2026.json',import.meta.url))),copy=v=>structuredClone(v);
const large=JSON.parse(readFileSync(new URL('../../../docs/fixtures/accounting_openings_large_balances_2026.json',import.meta.url)));
const clean=v=>{const b=copy(v);delete b.request_id;return b;};
const caps=()=>({readonly:false,features:['accounting_opening_balances'],capabilities:['business_accounting_openings'],permissions:['accounting.read','finance.read','bank.read','accounting.admin','accounting.prepare','finance.write'],organization:{modules:{finance:{enabled:true}}}});
test('actual original state, exact preview and accepted receipt remain bound to original account and profile',async()=>{
 await openingState(f.state_before);await openingState(f.state_after);await openingSources(f.sources,f.saved.account_id,f.state_before);
 const body=openingInput(f.state_before,f.sources,{source_kind:'original',source_id:f.original.id,at_start_of_day:true,amount:'1000,00',reason:f.preview_request.reason});
 assert.deepEqual(body,f.preview_request);await openingPreview(f.preview,body);await openingReceiptValidator(clean(f.command),f.preview,f.state_before)(f.saved);
 openingUploadValidator(clean(f.original_upload),{size:f.original.size,sha256:f.original.sha256})(f.original);
});
test('actual correction and void preserve original history and never create money or tax entries',async()=>{
 await openingState(f.state_after_correction);await openingState(f.state_after_void);await openingHistory(f.history_after_void,f.saved.account_id);
 for(const entry of[f.saved,f.correction,f.void]){await openingRecord(entry);assert.equal(entry.cash_flow_created,false);assert.equal(entry.tax_postings_created,false);}
 const body=openingInput(f.state_after_correction,null,{status:'void',reason:f.void_preview_request.reason},f.correction);assert.deepEqual(body,f.void_preview_request);
 const preview=copy(f.void);for(const k of['id','sequence','revision','previous_hash','created_by','created_at','content_hash'])delete preview[k];
 await openingReceiptValidator(clean(f.void_command),preview,f.state_after_correction)(f.void);
});
test('bank statement source uses its exact original balance and beginning-of-day boundary',async()=>{
 const b=f.bank;await openingState(b.state_before);await openingSources(b.sources,b.saved.account_id,b.state_before);await openingPreview(b.preview,b.preview_request);await openingRecord(b.saved);
 const chosen=b.sources.bank_statements.find(v=>v.source.statement_id===b.preview_request.source.statement_id&&v.source.balance_side===b.preview_request.source.balance_side);
 const body=openingInput(b.state_before,b.sources,{source_kind:'bank_statement',source_id:chosen.source.statement_id+':'+chosen.source.balance_side,reason:b.preview_request.reason});assert.deepEqual(body,b.preview_request);
 for(const mutate of[v=>v.source_proof.period_from='2025-12-31',v=>v.source_proof.amount='0.00',v=>v.source_proof.file_sha256='f'.repeat(64)]){const bad=copy(b.preview);mutate(bad);await assert.rejects(openingPreview(bad,b.preview_request));}
});
test('empty is not zero and fractional cents are rejected; explicit zero and signed bank balances are supported',()=>{
 assert.equal(openingMoney('0'),'0.00');assert.equal(openingMoney('-42,31'),'-42.31');
 for(const value of['',' ',null,'1e3','1.001','0,009','NaN','1.000,00','100000000000.00'])assert.throws(()=>openingMoney(value));
 const values={source_kind:'original',source_id:f.original.id,reason:'Actual original',at_start_of_day:true};assert.throws(()=>openingInput(f.state_before,f.sources,values));assert.throws(()=>openingInput(f.state_before,f.sources,{...values,amount:'0',at_start_of_day:false}));
});
test('exact original hashes, substituted account, profile, source and fabricated flags fail closed',async()=>{
 for(const mutate of[v=>v.account_id='f'.repeat(32),v=>v.account.revision++,v=>v.source.sha256='f'.repeat(64),v=>v.profile.profile.bookkeeping_start='2026-02-01',v=>v.amount='999.99',v=>v.cash_flow_created=true,v=>v.tax_postings_created=true,v=>v.balance_timing='end_of_day',v=>v.preview_hash='f'.repeat(64)]){const bad=copy(f.preview);mutate(bad);await assert.rejects(openingPreview(bad,f.preview_request));}
 const invalid=copy(f.saved);invalid.reason='Changed after acceptance';await assert.rejects(openingRecord(invalid));
 assert.throws(()=>openingOriginal({...f.original,account_id:'f'.repeat(32)},f.saved.account_id));
});
test('actual liquidity is original beginning plus actual movements; missing values never become zero or a complete total',async()=>{
 for(const key of['liquidity_before','liquidity','corrected_liquidity','void_liquidity'])await openingLiquidity(f[key],f[key].as_of);
 assert.equal(f.liquidity_before.known_balance_sum,null);assert.equal(f.liquidity_before.balance_total,null);assert.equal(f.void_liquidity.balance_total,null);
 for(const mutate of[v=>v.balance_total='0.00',v=>v.known_balance_sum='0.00',v=>v.accounts[0].inflows='999.00',v=>v.accounts[0].movements[0].account.id='f'.repeat(32),v=>v.accounts[0].balance='999.00',v=>v.complete_for_recorded_accounts=false]){const bad=copy(f.liquidity);mutate(bad);await assert.rejects(openingLiquidity(bad,bad.as_of));}
 await openingLiquidity(f.bank.liquidity,f.bank.liquidity.as_of);
 const forged=copy(f.bank.liquidity);forged.accounts[0].bank_connections[0].recorded_balance='999.00';forged.accounts[0].bank_connections[0].statement_balance='999.00';forged.accounts[0].bank_connections[0].matches=true;await assert.rejects(openingLiquidity(forged,forged.as_of));
 const duplicate=copy(f.bank.liquidity);duplicate.accounts[0].bank_connections.push(copy(duplicate.accounts[0].bank_connections[0]));await assert.rejects(openingLiquidity(duplicate,duplicate.as_of));
 const negativeCash=copy(f.bank.liquidity);negativeCash.accounts[0].account.kind='cash';negativeCash.accounts[0].bank_connections=[];await assert.rejects(openingLiquidity(negativeCash,negativeCash.as_of));negativeCash.accounts[0].issues=[{code:'cash_balance_negative'}];negativeCash.accounts[0].balance=null;Object.assign(negativeCash,{complete_for_recorded_accounts:false,known_account_count:0,known_balance_sum:null,balance_total:null});await openingLiquidity(negativeCash,negativeCash.as_of);
 const missing=copy(f.liquidity_before);missing.known_balance_sum='0.00';await assert.rejects(openingLiquidity(missing,missing.as_of));
});
test('original receipt remains frozen and asynchronous hash validation cannot silently accept a changed result',async()=>{
 const body=clean(f.command),proof=copy(f.preview),state=copy(f.state_before),validate=openingReceiptValidator(body,proof,state);body.amount='0.00';proof.amount='0.00';state.items.push(copy(f.saved));await validate(f.saved);
 const api=new OfficeApi({fetcher:async()=>new Response(JSON.stringify({...f.saved,amount:'0.00'}))});api.setToken('synthetic-opening-session');
 await assert.rejects(api.mutate('accounting-opening-confirm-'+f.saved.account_id,'/business'+OPENING_PATH+'/confirm',clean(f.command),{validate}));assert.equal(api.pendingCount,1);
});
test('accepted lost response keeps exact request, original validator and fresh permission/module gates',async()=>{
 const capability=caps(),posts=[],path='/business'+OPENING_PATH+'/confirm',key='accounting-opening-confirm-'+f.saved.account_id;
 let lose=true,replace=false;
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?capability:f.state_after));posts.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('Synthetic accepted response lost');}return new Response(JSON.stringify(replace?{...f.saved,amount:'0.00'}:f.saved));}});api.setToken('synthetic-opening-retry-session');
 await assert.rejects(api.mutate(key,path,clean(f.command),{validate:openingReceiptValidator(clean(f.command),f.preview,f.state_before)}));
 capability.permissions=capability.permissions.filter(p=>p!=='bank.read');await assert.rejects(api.retry(key),e=>e.status===403);capability.permissions.push('bank.read');capability.organization.modules.finance.enabled=false;await assert.rejects(api.retry(key),e=>e.status===423);assert.equal(posts.length,1);assert.equal(api.pendingCount,1);
 capability.organization.modules.finance.enabled=true;replace=true;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);replace=false;await api.retry(key);assert.equal(api.pendingCount,0);for(const command of posts)assert.deepEqual(command,posts[0]);
 await assert.rejects(openingPendingAuthorize(api,{key:'wrong',path}),e=>e.status===409);
});
test('asynchronous receipt completion after session replacement cannot clear the new pending operation',async()=>{
 let release,start;const started=new Promise(resolve=>start=resolve),held=new Promise(resolve=>release=resolve);
 const api=new OfficeApi({fetcher:async()=>new Response(JSON.stringify(f.saved))});api.setToken('synthetic-opening-old-session');const key='accounting-opening-confirm-'+f.saved.account_id,path='/business'+OPENING_PATH+'/confirm';
 const old=api.mutate(key,path,clean(f.command),{validate:async()=>{start();await held;}});await started;api.setToken('synthetic-opening-new-session');
 await assert.rejects(api.mutate(key,path,clean(f.command),{validate:()=>{throw new Error('Synthetic new unresolved response');}}));assert.equal(api.pendingCount,1);release();await assert.rejects(old);assert.equal(api.pendingCount,1);
});

test('asynchronous receipt completion cannot clear a replacement operation in the same session',async()=>{
 let release,start,posts=0;const started=new Promise(resolve=>start=resolve),held=new Promise(resolve=>release=resolve);
 const api=new OfficeApi({fetcher:async(url,options)=>{if(options.method==='GET')return new Response(JSON.stringify(url.includes('/capabilities')?caps():f.state_after));posts++;if(posts===2)return new Response(JSON.stringify({error:'Synthetic explicit nonacceptance',request_resolution:'not_accepted'}),{status:409});return new Response(JSON.stringify(f.saved));}});api.setToken('synthetic-opening-same-session');const key='accounting-opening-confirm-'+f.saved.account_id,path='/business'+OPENING_PATH+'/confirm';
 const old=api.mutate(key,path,clean(f.command),{validate:async()=>{start();await held;}});await started;await assert.rejects(api.retry(key),e=>e.status===409&&e.requestResolution==='not_accepted');assert.equal(api.pendingCount,0);
 await assert.rejects(api.mutate(key,path,clean(f.command),{validate:()=>{throw new Error('Synthetic replacement unresolved response');}}));const replacement=api.pendingCommandValues(key,path);assert.equal(api.pendingCount,1);release();await assert.rejects(old);assert.equal(api.pendingCount,1);assert.deepEqual(api.pendingCommandValues(key,path),replacement);assert.equal(posts,3);
});

test('actual accepted maximum individual beginnings retain exact larger positive and negative recorded balances',async()=>{
 for(const [kind,expected] of [['positive','100000000118.99'],['negative','-100000000059.49']]){
  const actual=large[kind];await openingRecord(actual.saved);await openingState(actual.state);const v=await openingLiquidity(actual.liquidity,actual.liquidity.as_of);assert.equal(v.accounts[0].balance,expected);assert.equal(v.known_balance_sum,expected);assert.equal(v.balance_total,expected);
  const wrong=copy(v);wrong.accounts[0].balance=wrong.accounts[0].calculated_balance='0.00';await assert.rejects(openingLiquidity(wrong,wrong.as_of));
 }
 for(const invalid of ['100000000000.00','-100000000000.00'])assert.throws(()=>openingMoney(invalid));
});
