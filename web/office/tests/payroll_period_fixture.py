"""Generate synthetic client contracts using actual private payroll fact commands."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend' / 'online')]
from test_business_payroll_facts import PayrollFactTests
import business_payroll_facts as facts
from payroll_periods_2026 import calculate_period_source
from test_business_payroll_periods import inputs, command as run_command, PayrollPeriodWorkflowTests


def fixture():
    test = PayrollFactTests()
    test.setUp()
    try:
        sources_before = test.api.sources(test.owner, {'employee_id': test.employee['id']})
        terms, terms_command = test.terms()
        sources = test.api.sources(test.owner, {'employee_id': test.employee['id']})
        details = test.period_details(terms)
        preview = test.api.preview(test.owner, test.preview_body(details))
        command = test.body('period_case', details, preview_hash=preview['preview_hash'])
        period = test.api.save(test.owner, command)
        run_input = inputs(test.employee['id'], period)
        run_preview = test.payroll.preview(test.owner, run_input)
        run_body = run_command(test.payroll, test.owner, run_input)
        run = test.payroll.finalize(test.owner, run_body)
        blocked_details = details | dict(entitlement_decisions=[dict(kind='sickness_continued_pay', source_absence_id=None,
            source_file_ids=[test.data['file']['id']], reason='Eigenständigen Anspruch noch berechnen', **{'from':'2026-10-20','to':'2026-10-21'})])
        blocked = test.api.preview(test.owner, test.preview_body(blocked_details))
        correction_body = test.body('period_case', details | dict(verification_note='Prüfvermerk belegt präzisiert'),
            id=period['id'], revision=1, correction_reason='Quellenvermerk präzisiert')
        correction_preview = test.api.preview(test.owner, test.preview_body(correction_body['details']))
        correction_body['preview_hash'] = correction_preview['preview_hash']
        corrected = test.api.save(test.owner, correction_body)
        corrected_run_input = inputs(test.employee['id'], corrected)
        corrected_run_preview = test.payroll.preview(test.owner, corrected_run_input)
        corrected_run_body = run_command(test.payroll, test.owner, corrected_run_input) | dict(id=run['id'], revision=1, correction_reason='Belegte Monatsfallquelle präzisiert')
        corrected_run = test.payroll.finalize(test.owner, corrected_run_body)
        ledger = test.payroll.ledger(test.owner, dict(employee_id=test.employee['id'], year='2026'))
        void_body = test.body('period_case', corrected['details'], id=corrected['id'], revision=2, status='void',
            correction_reason='Synthetische belegte Aufhebung', preview_hash=corrected['preview_hash'])
        void = test.api.save(test.owner, void_body)
        return dict(employee=test.employee, original=test.data, identity=test.identity, sources_before=sources_before,
            terms=terms, terms_command=terms_command, sources=sources, preview=preview, command=command, period=period,
            calculation=calculate_period_source(period['sources']), blocked=blocked,
            corrected_preview=correction_preview, corrected_command=correction_body, corrected=corrected,
            void_command=void_body, void=void, run_input=run_input, run_preview=run_preview, run_command=run_body, run=run,
            corrected_run_preview=corrected_run_preview, corrected_run_command=corrected_run_body, corrected_run=corrected_run, ledger=ledger)
    finally:
        test.tearDown(); test.doCleanups()


def regular_fixture(transition=False):
    case=PayrollPeriodWorkflowTests();case.setUp()
    try:
        case.regular(100000,transition_assessment=dict(status='within_transition_area',assessed_on='2026-01-01',regular_monthly_gross_minor=100000,forecast_months=12,foreseeable_one_off_payments=False,note='Synthetische belegte Prognose')) if transition else case.regular()
        f=case.f;fact,_,_=f.period();data=inputs(f.employee['id'],fact);preview=f.payroll.preview(f.owner,data);body=run_command(f.payroll,f.owner,data);run=f.payroll.finalize(f.owner,body)
        return dict(employee=f.employee,period=fact,inputs=data,preview=preview,command=body,run=run)
    finally:
        case.f.tearDown();case.doCleanups()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(fixture() | dict(regular=regular_fixture(),transition=regular_fixture(True)), ensure_ascii=False, sort_keys=True, indent=2) + '\n')
