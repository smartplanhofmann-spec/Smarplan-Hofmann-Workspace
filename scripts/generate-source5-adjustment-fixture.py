"""Accepted controlled mixed net originals for independent client proof checks."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'backend'))
from test_business_payroll_source5_adjustments import AdjustmentFixture


def main():
    f = AdjustmentFixture('runTest'); f.setUp()
    try:
        f.mixed_prefix()
        cases = []
        for label, amount in (('positive', 1500000), ('negative', 2000000), ('zero', 2000000)):
            details = f.adjust(amount, capture_sources=True)
            f.payment, payment_command = f.f.save_account(f.f.data, 'payment', details)
            cases.append(dict(label=label, employee=f.f.employee, files=[f.f.data['file']],
                initial_run=f.initial_run, initial_payment=f.initial_payment,
                prior_run=f.prior_run, prior_payment=f.prior_payment,
                run=f.run, run_input=f.adjustment_input, run_preview=f.preview,
                run_command=f.command, payment=f.payment, payment_command=payment_command,
                details=details, case=f.case, sources=f.adjustment_sources))
            print(label, f.run['revision'], f.run['settlement_transition']['net_delta_minor'], flush=True)
        value = dict(schema_version=1, scope='controlled repeated actual Source5 net adjustments', cases=cases)
        target = ROOT / 'app/test/fixtures/source5_adjustments.json'
        target.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        print(target.relative_to(ROOT), target.stat().st_size, 'bytes; actual accepted originals')
    finally:
        f.doCleanups()


if __name__ == '__main__':
    main()
