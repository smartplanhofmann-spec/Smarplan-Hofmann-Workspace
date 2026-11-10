"""Regenerate narrow DTO/PDF fixtures using the unchanged production projector.

Inputs are previously recorded synthetic API runs, never handmade statement
amounts. Old runs, projector versions, original statement hashes and PDFs are
not rewritten by the client-reader repair.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from business_payroll_statements import package, project, render_pdf
from core import canonical


def generate():
    directory = Path(__file__).parent
    result = []
    for filename in ('payroll_factor_travel', 'individual_minijob_v11',
                     'payroll_factor_claims', 'payroll_factor_claim_travel',
                     'payroll_factor_transition'):
        raw = (directory / (filename + '.json')).read_bytes()
        fixture = json.loads(raw)
        if filename == 'individual_minijob_v11':
            cases = [(kind, fixture[kind]['run']) for kind in ('compulsory', 'exempt', 'migrated')]
        elif filename == 'payroll_factor_claim_travel':
            cases = [(case['kind'], case['run']) for case in fixture['cases']]
        else:
            cases = [('original', fixture['run'])]
            if 'correction_run' in fixture:
                cases.append(('correction', fixture['correction_run']))
            if 'hourly' in fixture:
                cases.append(('hourly', fixture['hourly']['run']))
        for kind, run in cases:
            statement = project(run)
            pdf = render_pdf(statement)
            result.append(dict(source_fixture=filename + '.json', kind=kind,
                source_fixture_sha256=hashlib.sha256(raw).hexdigest(),
                original_run_sha256=hashlib.sha256(canonical(run).encode()).hexdigest(),
                employee_id=run['employee_id'], statement=package(statement),
                pdf_base64=base64.b64encode(pdf).decode()))
    return dict(schema_version=1, synthetic_only=True,
                producer='unchanged business_payroll_statements.project/package/render_pdf',
                cases=result)


if __name__ == '__main__':
    data = generate()
    Path(__file__).with_name('payroll_statement_composites.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    for case in data['cases']:
        calculation = case['statement']['calculation']
        print(case['source_fixture'], case['kind'], calculation['rule_version'],
              calculation['gross_minor'], calculation['net_minor'],
              case['statement']['pdf_sha256'])
