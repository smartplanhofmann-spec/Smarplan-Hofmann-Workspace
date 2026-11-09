#!/usr/bin/env python3
"""Generate real accepted synthetic v11 sources for both client parsers."""
import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from business_payroll_facts import reference
from test_payroll_individual_minijob import IndividualMinijobFixture
from test_business_payroll import rid
from payroll_individual_minijob_2026 import RULES, SCOPE


def generate(*, pension_exempt=False, migrate=False):
    owner = unittest.TestCase('runTest')
    try:
        source = IndividualMinijobFixture(owner, pension_exempt=pension_exempt)
        f = source.f
        case_input, case_preview = source.preview()
        legacy, legacy_command = source.legacy_case() if migrate else (None, None)
        if legacy is None:
            case, case_command = source.save()
        else:
            case_command = source.upgrade_command(legacy)
            case = source.api.save(f.owner, case_command)
        run_input = dict(source_schema_version=3, employee_id=f.employee['id'], calculation_case_ref=reference(case))
        run_preview = f.payroll.preview(f.owner, run_input)
        run_command = dict(run_input, request_id=rid(), revision=0, confirmed=True,
            accepted_scope=SCOPE, preview_hash=run_preview['preview_hash'])
        run = f.payroll.finalize(f.owner, run_command)
        return dict(employee=f.employee, profile=source.data['profile'], preparation=source.data['preparation'],
            period=source.period, identity=source.identity, identity_command=source.identity_body,
            files=list(source.files.values()), sources=source.api.sources(f.owner, dict(employee_id=f.employee['id'], month='2026-10')),
            case_input=case_input, case_preview=case_preview, case=case, case_command=case_command,
            run_input=run_input, run_preview=run_preview, run=run, run_command=run_command,
            legacy_case=legacy, legacy_command=legacy_command)
    finally:
        owner.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'app/test/fixtures/individual_minijob_v11.json')
    args = parser.parse_args()
    result = dict(schema_version=1, synthetic=True, rules=RULES,
        compulsory=generate(), exempt=generate(pension_exempt=True), migrated=generate(migrate=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(str(args.output))


if __name__ == '__main__':
    main()
