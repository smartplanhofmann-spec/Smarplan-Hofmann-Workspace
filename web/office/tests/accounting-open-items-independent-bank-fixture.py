"""Capture an existing real SQLite bank workflow without replacing domain methods."""
from copy import deepcopy
from pathlib import Path
import json
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from test_business_accounting_open_items import OpeningItemWorkflow
from business_accounting_open_items import public_source
from business_bank_reconciliation import BankReconciliation

captured = {'synthetic': True, 'generated_by': Path(__file__).relative_to(ROOT).as_posix()}
def capture(name):
    original = getattr(BankReconciliation, name)
    def run(self, actor, transaction_id, *args):
        result = original(self, actor, transaction_id, *args)
        captured[name] = deepcopy(result)
        if args:
            captured[name + '_command'] = deepcopy(args[0])
        if name == 'candidates':
            captured['payment_source'] = public_source(self.office, result['items'][0]['source']['source_id'])
        return result
    return run

case = OpeningItemWorkflow('test_real_bank_matching_and_liquidity_share_exact_single_money_source')
try:
    case.setUp()
    with patch.object(BankReconciliation, 'candidates', capture('candidates')), \
         patch.object(BankReconciliation, 'preview_match', capture('preview_match')), \
         patch.object(BankReconciliation, 'save_match', capture('save_match')):
        case.test_real_bank_matching_and_liquidity_share_exact_single_money_source()
    out = ROOT / 'web/office/tests/fixtures/accounting-open-items-independent-bank.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(captured, ensure_ascii=False, indent=2) + '\n')
    print('Real SQLite workflow passed; captured original candidate/preview/accepted/source:', out)
finally:
    case.doCleanups()
