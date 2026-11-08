import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollFactor,payrollProfileFields,payrollProfileData,payrollCalculation,
  payrollPreview,payrollRunValidator,payrollExportBytes} from '../payroll.js';
import {payrollStatement} from '../payroll-statements.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_factor_2026_workflow.json',import.meta.url)));
function values(){const p=structuredClone(f.profile.profile);for(const key of ['has_children','u1_required','minijob_rv_exempt','pension_other_compulsory'])p[key]=String(p[key]);return {...p,special_cases:[],regular_tax_scope:'factor',transition_scope:'none',regular_annual_gross_minor:'60000',tax_allowance_monthly_minor:'0',tax_addition_monthly_minor:'0',tax_factor:'0,753',source_file_id:f.file.id,confirmed:true};}

test('factor input preserves three exact decimal places and never rounds a guessed value',()=>{
  assert.equal(payrollFactor('0,753'),'0.753');assert.equal(payrollFactor('0.000'),'0.000');
  for(const value of ['',null,0.753,'0.75','0.7539','1.000','-0.100'])assert.throws(()=>payrollFactor(value));
});
test('factor profile is explicit, documented and restored in the editor',()=>{
  const blank=payrollProfileFields([f.file]);assert.equal(blank.find(v=>v.name==='tax_factor').value,'');
  const existing=payrollProfileFields([f.file],f.profile);
  assert.equal(existing.find(v=>v.name==='regular_tax_scope').value,'factor');
  assert.equal(existing.find(v=>v.name==='tax_factor').value,'0.753');
  const body=payrollProfileData(f.employee,values(),[f.file]);assert.deepEqual(body.profile,f.profile.profile);
});
test('factor forms reject conflicting class, allowance, minijob, period and missing evidence',()=>{
  for(const change of [{tax_class:1},{tax_allowance_monthly_minor:'1'},
    {tax_addition_monthly_minor:'1'},{transition_scope:'monthly'},
    {employment_kind:'minijob',regular_tax_scope:'minijob'},
    {regular_tax_scope:'standard'},{tax_factor:''},{confirmed:false},{source_file_id:'f'.repeat(32)}]){
    assert.throws(()=>payrollProfileData(f.employee,{...values(),...change},[f.file]));
  }
});
test('factor calculation and preview bind the actual factor and retain checked net',()=>{
  assert.equal(payrollCalculation(f.run.calculation).net_minor,332342);
  payrollPreview(f.preview,f.inputs);
  const bad=structuredClone(f.preview);bad.calculation.tax_parameters.tax_factor='0.900';
  assert.throws(()=>payrollPreview(bad,f.inputs));
  for(const change of [{rule_version:'de_2026_standard_monthly_pap_v2'},
    {tax_parameters:{}},{employee_tax_minor:0}])assert.throws(()=>payrollCalculation({...f.run.calculation,...change}));
});
test('original and corrected factor receipts preserve exact tax delta and reject mixed versions',()=>{
  payrollRunValidator(f.command,f.preview)(f.run);
  payrollRunValidator(f.corrected_command,f.corrected_preview,f.run)(f.corrected_run);
  assert.equal(f.corrected_run.delta.employee_tax_minor,11508);
  assert.equal(f.corrected_run.delta.net_minor,-11508);
  const bad=structuredClone(f.corrected_run);bad.delta.individual_wage_tax_minor=0;
  assert.throws(()=>payrollRunValidator(f.corrected_command,f.corrected_preview,f.run)(bad));
});
test('factor employee statements admit only safe amounts and retain verified exports',async()=>{
  await payrollStatement(f.statement,f.employee.id);await payrollStatement(f.corrected_statement,f.employee.id);
  assert.equal(f.statement.calculation.net_minor,332342);
  assert.equal(f.statement.calculation.tax_parameters,undefined);
  await payrollExportBytes(new Blob([JSON.stringify(f.run)]),'json',f.run);
  await payrollExportBytes(new Blob([JSON.stringify(f.corrected_run)]),'json',f.corrected_run);
});
