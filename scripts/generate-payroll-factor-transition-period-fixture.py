"""Create synthetic actual v16 API originals for both independent clients."""
import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))
from test_business_payroll_factor_transition_periods import FactorTransitionPeriodFixture
from business_payroll_statements import PayrollStatements


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
        default=ROOT / 'app/test/fixtures/payroll_factor_transition_period.json')
    args = parser.parse_args()
    rows = []
    for amount, name in ((100000, 'partial_low'), (200000, 'partial_factor_tax')):
        fixture = FactorTransitionPeriodFixture('runTest')
        fixture.monthly_amount = amount
        fixture.setUp()
        try:
            f = fixture.f
            sources = fixture.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10'))
            run = fixture.accepted()
            statements = PayrollStatements(f.office)
            own = statements.get(f.technician, run['id'])
            pdf = statements.export(f.technician, run['id'],
                dict(revision=str(run['revision']), statement_hash=own['statement']['statement_hash']))[0]
            rows.append(dict(name=name, monthly_amount_minor=amount, sources=sources,
                employee=f.employee, input=fixture.case_input, case_preview=fixture.case_preview,
                case_command=fixture.case_command, case=fixture.case, run_input=fixture.run_input,
                run_preview=fixture.run_preview, run_command=fixture.run_command, run=run,
                own=own, own_pdf_base64=base64.b64encode(pdf).decode('ascii')))
        finally:
            fixture.doCleanups()
    args.output.write_text(json.dumps(dict(schema_version=1, fixture_only=True,
        real_personnel_data=False, generated_from_actual_synthetic_api=True, cases=rows),
        ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'bytes': args.output.stat().st_size,
        'amounts': [{'name': r['name'], 'gross': r['run']['calculation']['gross_minor'],
            'tax': r['run']['calculation']['individual_wage_tax_minor'],
            'net': r['run']['calculation']['net_minor']} for r in rows]}))


if __name__ == '__main__':
    main()
