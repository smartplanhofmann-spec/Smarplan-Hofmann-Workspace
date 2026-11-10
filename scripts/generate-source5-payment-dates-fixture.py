"""Generate synthetic, actually accepted V3 payment originals for both clients."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))
from test_business_payroll_payment_dates import PositivePaymentDateWorkflow


def main():
    fixture = PositivePaymentDateWorkflow('runTest')
    fixture.setUp()
    try:
        original, prior = fixture.first()
        cases = []
        for amount, date in ((1500000, '2026-11-01'), (1000000, '2026-11-02')):
            run = fixture.correction(amount)
            details = fixture.later_details(date)
            payment, command = fixture.f.save_account(fixture.f.data, 'payment', details)
            cases.append(deepcopy(dict(prior_payment=prior, run=run, details=details,
                payment=payment, command=command)))
            fixture.payment = prior = payment
        value = dict(schema_version=1, scope='synthetic positive actual 2026 transfers; original gross receipt unchanged',
            employee=fixture.f.employee, evidence_file=fixture.f.data['file'], original_run=original, cases=cases)
        target = ROOT / 'app/test/fixtures/source5_payment_dates.json'
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(str(target.relative_to(ROOT)), target.stat().st_size, 'bytes, two accepted successive V3 originals')
    finally:
        fixture.doCleanups()


if __name__ == '__main__':
    main()
