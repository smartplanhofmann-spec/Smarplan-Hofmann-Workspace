import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollStatement,payrollStatementPage,payrollStatementBytes,payrollStatementRights} from '../payroll-statements.js';
const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_statements.json',import.meta.url))),copy=v=>JSON.parse(JSON.stringify(v)),employee=f.employee.id;
test('actual reduced v4 statement and deterministic PDF retain own values and explicit periods',async()=>{
 await payrollStatement(f.statement,employee);await payrollStatementPage(f.page,employee);await payrollStatementPage({employee_id:employee,can_export:true,statement:f.statement},employee,{detail:true,ref:f.statement.run_ref});
 assert.equal(f.statement.calculation.net_minor,31878);assert.equal(f.statement.period_summary.social_periods[0].days,17);
 const bytes=Buffer.from(f.pdf_base64,'base64');await payrollStatementBytes(new Blob([bytes]),f.statement);
 const changed=Buffer.from(bytes);changed[100]^=1;await assert.rejects(payrollStatementBytes(new Blob([changed]),f.statement));
});
test('private top-level and nested fields, foreign person, tampered revision and source hash are rejected',async()=>{
 for(const alter of[v=>v.source={},v=>v.calculation.profile={},v=>v.period_summary.social_periods[0].reason='private',v=>v.employee_id='f'.repeat(32),v=>v.run_ref.revision++,v=>v.employee_name='Changed historical name',v=>v.statement_hash='f'.repeat(64),v=>v.calculation.net_minor++]){const v=copy(f.statement);alter(v);await assert.rejects(payrollStatement(v,employee));}
 await assert.rejects(payrollStatementPage({...f.page,items:[f.statement,f.statement]},employee));
 await assert.rejects(payrollStatementPage({...f.page,employee_id:'f'.repeat(32)},employee));
});
test('incomplete legacy scope keeps unknown net and does not fabricate zero',async()=>{
 await payrollStatement(f.partial,f.partial.employee_id);assert.equal(f.partial.calculation.net_minor,null);
 const v=copy(f.partial);v.calculation.net_minor=0;await assert.rejects(payrollStatement(v,v.employee_id));
});
test('self permissions require current feature and matching employee identity; read does not imply foreign access',()=>{
 const caps={features:['payroll_employee_statements'],capabilities:['business_payroll'],permissions:['time.own']};
 assert.equal(payrollStatementRights(caps,f.employee,f.actor.id),true);assert.equal(payrollStatementRights(caps,f.employee,'f'.repeat(32)),false);
 assert.equal(payrollStatementRights({...caps,permissions:[]},f.employee,f.actor.id),false);assert.equal(payrollStatementRights({...caps,features:[]},f.employee,f.actor.id),false);
 assert.equal(payrollStatementRights({...caps,permissions:['personnel.read']},f.employee,'f'.repeat(32)),true);
});
