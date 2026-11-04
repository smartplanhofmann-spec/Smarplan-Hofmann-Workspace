import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {accountRecord,accountReceiptValidator,payrollAccountDetails,payrollAccountNoPaymentDue,payrollAccountPaymentStatus} from '../payroll-accounts.js';
import {payrollLedger} from '../payroll.js';
import {OfficeApi} from '../office.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_zero_account.json',import.meta.url)));
const sources={profiles:f.sources.profiles,runs:[f.run],identities:[f.identity]},ref=r=>r.id+'@'+r.revision;
const values=()=>({run_ref:ref(f.run),identity_ref:ref(f.identity),tax_free_payments_minor:'0.00',tax_free_basis:'',standard_case_confirmed:true});
test('actual fully bound source3 zero payable permits exactly no cash rows',()=>{
 assert.equal(payrollAccountNoPaymentDue(f.run),true);
 assert.deepEqual(payrollAccountDetails('payment',values(),sources,0),f.command.details);
 accountReceiptValidator(f.command,f.saved.source_file,null,{run:f.run,identity:f.identity})(f.saved);
 accountReceiptValidator(f.correction_body,f.corrected.source_file,f.saved,{run:f.run,identity:f.identity})(f.corrected);
 for(const r of f.history.items)accountRecord(r,f.employee.id,'payment');
 assert.throws(()=>payrollAccountDetails('payment',{...values(),standard_case_confirmed:false},sources,0));
 assert.throws(()=>payrollAccountDetails('payment',{...values(),paid_on_0:'2026-10-31',amount_0:'0',reference_0:'No fictitious cash'},sources,1));
});
test('old rules unknown zero incomplete plans and substituted original components never authorize no-payment evidence',()=>{
 for(const change of [r=>r.source.source_schema_version=1,r=>r.calculation.net_minor=null,r=>r.calculation.net_minor=1,r=>r.calculation.payroll_calculation_complete=false,r=>r.confirmed=false,r=>r.source.calculation_case.plan.plan_hash='f'.repeat(64),r=>r.source.calculation_case.sources.employee_id='f'.repeat(32)]){
  const r=structuredClone(f.run);change(r);
  assert.throws(()=>payrollAccountDetails('payment',values(),{...sources,runs:[r]},0));
 }
 const changed=structuredClone(f.saved);changed.sources.run.calculation.net_minor=1;
 assert.throws(()=>accountRecord(changed,f.employee.id,'payment'));
});
test('actual ledger zero status retains original payment reference and open statutory gaps',async()=>{
 const view=await payrollLedger(f.ledger,f.employee.id,2026),m=view.ledger.months[9];
 assert.equal(payrollAccountPaymentStatus(m,view.ledger.account_records,f.employee.id),'no_payment_due');
 assert.equal(m.wage_account.payable_minor,0);assert.deepEqual(m.wage_account.payments,[]);
 assert.equal(view.ledger.statutory_wage_account_complete,false);
 assert.ok(view.ledger.account_completeness_issues.includes('unpaid_statutory_marker_requires_evidence'));
 assert.ok(Buffer.from(f.ledger_pdf_base64,'base64').includes(Buffer.from('Keine Nettozahlung geschuldet')));
 for(const change of [m=>delete m.wage_account.payment_status,m=>m.wage_account.payment_status='payments_evidenced',m=>m.wage_account.payable_minor=1,m=>m.wage_account.payment_ref.revision=99,m=>m.wage_account.payments=[{paid_on:'2026-10-31',amount_minor:0,payment_reference:'invalid'}],m=>m.revision++]){
  const bad=structuredClone(m);change(bad);assert.throws(()=>payrollAccountPaymentStatus(bad,view.ledger.account_records,f.employee.id));
 }
});
test('zero declaration lost ACK retries original source and nonce after fresh private approval',async()=>{
 let approve=true,lose=true,wrong=false;const posts=[];
 const response=v=>new Response(JSON.stringify(v),{headers:{'Content-Type':'application/json'}});
 const api=new OfficeApi({fetcher:async(path,options)=>{
  if(options.method==='GET'){
   if(path.endsWith('/capabilities'))return response({features:['german_payroll_2026','payroll_wage_account'],capabilities:['business_payroll','business_payroll_accounts'],readonly:false,permissions:['personnel.read',...(approve?['personnel.approve']:[])]});
   if(path.includes('/payroll/runs?'))return response({employee_id:f.employee.id,items:[f.run]});
   if(path.includes('/payroll/account-records?'))return response({employee_id:f.employee.id,items:[f.identity,f.saved]});
   throw new Error(path);
  }
  posts.push(JSON.parse(options.body));if(lose){lose=false;throw new Error('accepted original reply lost');}
  const saved=structuredClone(f.saved);if(wrong)saved.sources.run.calculation.net_minor=1;return response(saved);
 }});
 api.setToken('synthetic-zero-account-private-owner-12345');const key='payroll-account-'+f.employee.id;
 await assert.rejects(api.mutate(key,'/business/payroll/account-records',f.command,{validate:accountReceiptValidator(f.command,f.saved.source_file,null,{run:f.run,identity:f.identity})}));
 approve=false;await assert.rejects(api.retry(key));assert.equal(posts.length,1);
 approve=true;wrong=true;await assert.rejects(api.retry(key));assert.equal(api.pendingCount,1);
 wrong=false;await api.retry(key);assert.equal(api.pendingCount,0);assert.equal(posts.length,3);assert.deepEqual(posts[0],posts[2]);assert.deepEqual(posts[0].details.payments,[]);
});
