"""A real existing cash/EÜR source, preview and receipt; no opening-item setup."""
from pathlib import Path
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
from test_business_accounting_euer import EuerWorkflowTests

case = EuerWorkflowTests('runTest')
try:
    case.setUp()
    event = case.sale()
    payload = case.cash_payload(event)
    body = case.body('cash', payload)
    state = case.api.state(case.owner)
    sources = case.api.sources(case.owner)
    report = case.api.report(case.owner, 2026)
    journal = case.api.journal(case.owner)
    accounts = case.fixture.api.accounts(case.owner)
    preview = case.api.preview(case.owner, body)
    command = dict(body, request_id=uuid.uuid4().hex, preview_hash=preview['preview_hash'], confirmation=True)
    accepted = case.api.confirm(case.owner, command)
    assert case.api.confirm(case.owner, command) == accepted
    assert [(p['ledger'], p['category'], p['amount']) for p in accepted['postings']] == [
        ('euer', 'sales', '100.00'), ('euer', 'vat_collected', '19.00'), ('vat', 'output_vat', '19.00')]
    result = dict(synthetic=True, generated_by=Path(__file__).relative_to(ROOT).as_posix(),
                  operation='cash', event=event, payload=payload, body=body, state=state,
                  sources=sources, report=report, journal=journal, accounts=accounts,
                  preview=preview, command=command, accepted=accepted)
    if '--followups' in sys.argv:
        def followup(operation, values):
            body = case.body(operation, values)
            state = case.api.state(case.owner)
            sources = case.api.sources(case.owner)
            report = case.api.report(case.owner, 2026)
            journal = case.api.journal(case.owner)
            preview = case.api.preview(case.owner, body)
            command = dict(body, request_id=uuid.uuid4().hex, preview_hash=preview['preview_hash'], confirmation=True)
            receipt = case.api.confirm(case.owner, command)
            assert case.api.confirm(case.owner, command) == receipt
            return dict(result, operation=operation, body=body, state=state, sources=sources,
                        report=report, journal=journal, preview=preview, command=command, accepted=receipt)
        correction = followup('correct', dict(entry_id=accepted['id'], operation='cash', payload=payload))
        reversal = followup('reverse', dict(entry_id=correction['accepted']['id']))
        assert reversal['preview']['effect'] is None
        assert reversal['body']['payload'] == dict(entry_id=correction['accepted']['id'])
        result = dict(correction=correction, reversal=reversal)
        out = ROOT / 'web/office/tests/fixtures/accounting-euer-legacy-followups.json'
    else:
        out = ROOT / 'web/office/tests/fixtures/accounting-euer-legacy-context.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Real existing cash EÜR fixture created; original preview/accepted replay and 100/19/119 verified:', out)
finally:
    case.doCleanups()
