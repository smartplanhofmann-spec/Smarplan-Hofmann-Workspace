#!/usr/bin/env python3
"""Real accepted V11 boundary records for browser/native DTO compatibility."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from test_payroll_individual_minijob import IndividualMinijobFixture
from test_business_payroll import rid
from business_payroll_facts import reference


def generate(*, blocked=False):
    owner = unittest.TestCase('runTest')
    try:
        source = IndividualMinijobFixture(owner)
        details = deepcopy(source.details)
        assessment = details['individual_minijob_assessment']
        assessment['valid_from'] = '2026-01-01'
        assessment['valid_to'] = '2026-12-31'
        assessment['verification_note'] = 'Synthetic complete original\n\t' + '\U0001f600' * 1501
        if blocked:
            assessment['income_review_complete'] = False
        body, preview = source.preview(details=details)
        command = dict(body, request_id=rid(), revision=0, status='active', confirmed=True,
                       preview_hash=preview['preview_hash'])
        record = source.api.save(source.f.owner, command)
        inputs = dict(source_schema_version=3, employee_id=source.f.employee['id'],
                      calculation_case_ref=reference(record))
        return dict(employee_id=source.f.employee['id'], command=command, preview=preview,
                    record=record, run_input=inputs,
                    run_preview=source.f.payroll.preview(source.f.owner, inputs))
    finally:
        owner.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'app/test/fixtures/individual_minijob_client_boundaries.json')
    args = parser.parse_args()
    result = dict(schema_version=1, synthetic=True, covered=generate(), blocked=generate(blocked=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
