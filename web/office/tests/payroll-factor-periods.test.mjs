import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {payrollCalculation,payrollPreview,payrollRunValidator} from '../payroll.js';
import {payrollFactRunInput,payrollPeriodCalculation,PAYROLL_FACTOR_PERIOD_RULE} from '../payroll-facts.js';
import {payrollStatement} from '../payroll-statements.js';

const f=JSON.parse(fs.readFileSync(new URL('../../../app/test/fixtures/payroll_factor_periods_2026_workflow.json',import.meta.url)));
const copy=structuredClone;
test('actual factor-period sources retain actual dates, quotient, factor and completed scope',()=>{
  assert.deepEqual(payrollFactRunInput(f.period_case),f.inputs);
  payrollPreview(f.preview,f.inputs);
  const c=payrollCalculation(f.run.calculation),p=payrollPeriodCalculation(c);
  assert.equal(c.rule_version,PAYROLL_FACTOR_PERIOD_RULE);assert.equal(c.scope,'regular_standard_factor_period');
  assert.equal(c.gross_minor,274194);assert.equal(c.tax_parameters.tax_factor,'0.753');
  assert.equal(p.tax_periods[0].tax_days,17);assert.equal(p.social_periods[0].days,17);
  assert.equal(p.tax_calculation.inputs.gross_remainder_minor,1);
});
test('actual accepted correction binds tax deltas and preserves the original source',()=>{
  payrollRunValidator(f.command,f.preview)(f.run);
  payrollRunValidator(f.corrected_command,f.corrected_preview,f.run)(f.corrected_run);
  assert.equal(f.corrected_run.delta.net_minor,-f.corrected_run.delta.employee_tax_minor);
  assert.equal(f.run.calculation.tax_parameters.tax_factor,'0.753');
  assert.equal(f.corrected_run.calculation.tax_parameters.tax_factor,'0.900');
  const changed=copy(f.corrected_run);changed.delta.individual_wage_tax_minor++;
  assert.throws(()=>payrollRunValidator(f.corrected_command,f.corrected_preview,f.run)(changed));
});
test('employee statement permits own period amounts without private profiles or identity originals',async()=>{
  const statement=await payrollStatement(f.statement,f.employee.id);
  assert.equal(statement.period_summary.tax_periods[0].tax_days,17);
  assert.equal(statement.calculation.scope,'regular_standard_factor_period');
  assert.ok(!JSON.stringify(statement).includes('verification_note'));
  await assert.rejects(()=>payrollStatement(f.statement,'f'.repeat(32)));
});
test('different factor, profile or period rules cannot be substituted into a preview',()=>{
  const mutations=[p=>p.calculation.tax_parameters.tax_factor='0.900',
    p=>p.source.profile.profile.tax_factor='0.900',p=>p.source.period_case.plan.rule_version='de_2026_periods_pap_v4',
    p=>p.calculation.period_details.factor_parameters.profile_ref.id='f'.repeat(32)];
  for(const mutate of mutations){const altered=copy(f.preview);mutate(altered);assert.throws(()=>payrollPreview(altered,f.inputs));}
});
test('tax components, days, assessment and legacy rule substitution fail closed',()=>{
  const mutations=[c=>c.period_details.tax_calculation.component.LSTLZZ++,
    c=>c.period_details.tax_calculation.factor='0.900',c=>c.period_details.tax_calculation.inputs.tax_days++,
    c=>c.tax_parameters.church_assessment_minor++,c=>c.rule_version='de_2026_periods_pap_v4',
    c=>c.period_details.tax_periods[0].tax_days=30,c=>c.pap_version='old-version'];
  for(const mutate of mutations){const altered=copy(f.run.calculation);mutate(altered);assert.throws(()=>payrollCalculation(altered));}
});
