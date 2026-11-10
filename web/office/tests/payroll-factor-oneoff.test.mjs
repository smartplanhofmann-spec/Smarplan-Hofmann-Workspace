import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollOneOffCalculation,payrollOneOffCaseRecord,payrollOneOffCaseSources,payrollOneOffSource,verifyFactorOneOffCase,verifyFactorOneOffRun,payrollOneOffCaseInput,payrollOneOffCasePreview,payrollOneOffCasesPendingAuthorize} from '../payroll-oneoff-cases.js';
import {payrollPreview,payrollRunValidator} from '../payroll.js';
import {OfficeApi} from '../office.js';
import {accountRecord} from '../payroll-accounts.js';
import {payrollOneOffCaseValidator} from '../payroll-oneoff-cases.js';
import {payrollAnnualRecord,payrollAnnualSources} from '../payroll-annual-basis.js';
import {payrollStatement,payrollStatementBytes,payrollStatementHash} from '../payroll-statements.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_factor_oneoff.json',import.meta.url))),id=f.employee.id;
const copy=v=>JSON.parse(JSON.stringify(v));
const order=v=>Array.isArray(v)?v.map(order):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,order(v[k])])):v;
async function rehash(v){const{statement_hash,pdf_sha256,pdf_size,...base}=v;v.statement_hash=await payrollStatementHash(new TextEncoder().encode(JSON.stringify(order(base))));return v;}

test('actual protected factor/P4/V2/V15 originals bind one run without rewriting the monthly source',async()=>{
 payrollAnnualSources(f.annual_sources,id);payrollAnnualRecord(f.source.current_annual_basis,id,'annual_basis');payrollAnnualRecord(f.source.annual_tax_forecast,id,'annual_tax_forecast');
 payrollOneOffCaseSources(f.case_sources,id,'2026-10');payrollOneOffCaseRecord(f.case,id);payrollOneOffCalculation(f.run.calculation);payrollOneOffSource(f.run_preview,f.run_input);
 await verifyFactorOneOffCase(f.case);await verifyFactorOneOffRun(f.run_preview);assert.deepEqual(f.run.calculation.running_calculation,f.case.plan.running_calculation);assert.ok(f.run.calculation.one_off_details.tax.STS>0);assert.ok(f.run.calculation.one_off_details.tax.SOLZS>0);
});

test('changed factor, borrowed versions, annual identity and one cent tax edits are rejected',()=>{
 for(const change of [v=>v.rule_version='latest',v=>v.source_contract_version=1,v=>v.plan.one_off_details.tax_factor='0.754',v=>v.plan.one_off_details.tax.STS++,v=>v.plan.running_calculation.rule_version='de_2026_segments_entitlements_v5',v=>v.sources.calculation_source.current_annual_basis.sources.annual_source_contract.version=true,v=>v.sources.calculation_source.annual_tax_forecast.plan.factor_profile_ref.content_hash='0'.repeat(64)]){
  const v=copy(f.case);change(v);assert.throws(()=>payrollOneOffCaseRecord(v,id));
 }
});

test('explicit factor input, preview and actual finalized receipt pass the shared payroll entry',async()=>{
 const c=f.source,values={month:'2026-10',running_calculation_case_id:c.running_calculation_case.id,one_off_earning_id:c.one_off_earning.id,current_annual_basis_id:c.current_annual_basis.id,previous_annual_basis_id:'',annual_tax_forecast_id:c.annual_tax_forecast.id,source_file_ids:f.case.source_file_ids,verification_note:f.case.details.verification_note};
 const input=payrollOneOffCaseInput(id,f.case_sources,values,null,{factorMode:true});
 assert.equal(input.rule_version,f.case.rule_version);assert.deepEqual(input.details,f.case.details);
 payrollOneOffCasePreview(f.case_preview,input);await verifyFactorOneOffCase(f.case_preview);
 await payrollPreview(f.run_preview,f.run_input);await payrollRunValidator(f.run_command,f.run_preview)(f.run);
 accountRecord(f.payment,id,'payment');
 const calls=[],key='payroll-factor-oneoff-cases-'+id,path='/business/payroll/one-off-cases/factor-v15';let allowed=true;
 const api={pendingCommandValues:()=>f.case_command,get:async value=>{calls.push(value);return value==='/business/capabilities'?{features:['payroll_oneoff_cases',...(allowed?['payroll_factor_oneoff']:[])],capabilities:['business_payroll_oneoff_cases'],permissions:['personnel.read','personnel.approve'],readonly:false,organization:{modules:{personnel:{enabled:true}}}}:f.case_sources;}};
 assert.equal(await payrollOneOffCasesPendingAuthorize(api,{key,path}),true);assert.ok(calls.some(value=>value.startsWith(path+'/sources?')));
 allowed=false;await assert.rejects(payrollOneOffCasesPendingAuthorize(api,{key,path}),error=>error.status===403);
 await assert.rejects(payrollOneOffCasesPendingAuthorize(api,{key:'payroll-oneoff-cases-'+id,path}));
});

test('own schema5 statement and PDF reveal only allowed amounts and keep the exact rule/scope pair',async()=>{
 await payrollStatement(f.statement,id);await payrollStatementBytes(new Blob([Buffer.from(f.pdf_base64,'base64')]),f.statement);
 for(const change of [v=>v.schema_version=3,v=>v.calculation.scope='regular_standard_oneoff',v=>v.calculation.rule_version='de_2026_oneoff_composition_v6',v=>v.one_off_summary.tax_factor='0.753',v=>v.source={},v=>v.calculation.net_minor++]){
  const v=copy(f.statement);change(v);await rehash(v);await assert.rejects(payrollStatement(v,id));
 }
});

test('actual OfficeApi routes a lost factor receipt through fresh factor permissions and repeats the unchanged nonce',async()=>{
 const posts=[],key='payroll-factor-oneoff-cases-'+id,path='/business/payroll/one-off-cases/factor-v15';let allowed=true,enabled=true;
 const api=new OfficeApi({fetcher:async(url,options)=>{
  if(options.method==='GET')return new Response(JSON.stringify(url.endsWith('/capabilities')?{features:['payroll_oneoff_cases',...(enabled?['payroll_factor_oneoff']:[])],capabilities:['business_payroll_oneoff_cases'],permissions:['personnel.read',...(allowed?['personnel.approve']:[])],readonly:false,organization:{modules:{personnel:{enabled:false}}}}:{...f.case_sources,writes_enabled:false}));
  posts.push(JSON.parse(options.body));if(posts.length===1)throw Error('Controlled successful factor response lost');return new Response(JSON.stringify(f.case));
 }});api.setToken('synthetic-factor-oneoff-real-router');const body=copy(f.case_command);delete body.request_id;
 await assert.rejects(api.mutate(key,path,body,{validate:payrollOneOffCaseValidator(body,null,f.case_preview)}));
 allowed=false;await assert.rejects(api.retry(key),error=>error.status===403);assert.equal(posts.length,1);
 allowed=true;enabled=false;await assert.rejects(api.retry(key),error=>error.status===403);assert.equal(posts.length,1);
 enabled=true;assert.deepEqual(await api.retry(key),f.case);assert.deepEqual(posts[0],posts[1]);assert.equal(api.pendingCount,0);
});
