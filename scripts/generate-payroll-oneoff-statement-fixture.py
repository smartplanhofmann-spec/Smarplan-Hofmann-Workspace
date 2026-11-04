"""Generate reduced employee statements from actual accepted synthetic runs."""
import base64
import json
from pathlib import Path

from business_payroll_statements import PayrollStatements, render_pdf
from business_payroll_facts import reference
from test_business_payroll_statements_v6 import OneoffStatementTests
from test_business_payroll_oneoff_runs import OneoffRunWorkflow


def main():
    fixture = OneoffStatementTests('runTest'); fixture.setUp()
    march = OneoffRunWorkflow('runTest'); march.setUp()
    try:
        f = fixture.f; api = fixture.api
        statement = api.get(f.technician, fixture.run['id'])['statement']
        march.source = march.c.source(january=True, previous=True, bonus=200000)
        details = march.details() | dict(previous_annual_basis_ref=reference(march.source['previous_annual_basis']))
        command, _ = march.request(details); saved = march.api.save(march.f.owner, command)
        run = march.f.payroll.finalize(march.f.owner, march.command(saved))
        march_statement = PayrollStatements(march.f.office).get(march.f.technician, run['id'])['statement']
        output = dict(employee=f.employee, actor=f.technician, statement=statement,
            page=api.records(f.technician), history=api.get(f.technician, fixture.run['id'], history=True),
            previous=fixture.before, previous_pdf_base64=base64.b64encode(fixture.before_pdf).decode(),
            pdf_base64=base64.b64encode(render_pdf(statement)).decode(), march= march_statement)
        target = Path(__file__).resolve().parents[1] / 'app/test/fixtures/payroll_statements_v6.json'
        target.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n')
        print('Generated actual v6 employee statement, original v5, independent PDF and March-clause fixture:', target.name)
    finally:
        march.doCleanups(); fixture.doCleanups()


if __name__ == '__main__': main()
