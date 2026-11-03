"""Public, original-bound travel cash for EÜR; no payroll or payment execution.

Private travel records are reconstructed by travel_allowance_cash.  This adapter
only classifies actual cash movements and keeps their historical revisions.
"""

import re

from business_operations import identifier
from core import Problem


def prepare(api, actor, payload, ledger, historical):
    # Imported lazily to keep the financial and private domain dependency acyclic.
    from business_accounting_euer import _account, _amount, _hash, _posting, _shape
    from travel_allowance_cash import financial_access, public_source

    _shape(payload, 'payment_id revision source_hash accounts')
    identifier(payload['payment_id'])
    _hash(payload['source_hash'])
    if (type(payload['revision']) is not int or payload['revision'] < 1
            or not isinstance(payload['accounts'], dict)):
        raise Problem(400, 'Positive Reisezahlungsrevision und geprüfte Kontenzuordnung erforderlich.')
    financial_access(api.office, actor)
    source = historical or public_source(api.office, payload['payment_id'], payload['revision'])
    if (source['id'] != payload['payment_id'] or source['revision'] != payload['revision']
            or source['source_hash'] != payload['source_hash']):
        raise Problem(409, 'Genau passende öffentliche Reisezahlungsquelle erforderlich.')
    if not historical and public_source(api.office, source['id']) != source:
        raise Problem(409, 'Reisezahlungsnachweis wurde geändert; aktuelle Fassung prüfen.')

    categories = {key for movement in source['cash_movements'] for key in movement['categories']}
    if not categories <= {'travel_allowance'} or set(payload['accounts']) != categories:
        raise Problem(400, 'Jede belegte Reisekostenerstattung genau einem geprüften SKR04-Konto zuordnen.')
    for account in payload['accounts'].values():
        _account(account)
    target = 'travel_cash:' + source['id']
    postings = []
    for movement in source['cash_movements']:
        sign = -1 if movement['direction'] == 'out' else 1
        for category, amount in movement['categories'].items():
            postings.append(_posting('euer', category, sign * _amount(amount, True),
                                     movement['date'], payload['accounts'][category], target))
    return source, target, postings, dict(
        date=source['date'], cash_dates=sorted({item['date'] for item in source['cash_movements']}),
        status=source['status'])


def catalog(api, actor, ledger):
    from travel_allowance_cash import financial_access, installed, public_source

    items, issues, movements = [], [], []
    if not installed(api.office):
        return items, issues, movements
    # This check is deliberately independent of personnel access.
    financial_access(api.office, actor)
    for row in api.office.db.execute('SELECT DISTINCT id FROM business_travel_payments ORDER BY id'):
        source = public_source(api.office, row['id'])
        current = ledger['active'].get('travel_cash:' + source['id'])
        reasons = []
        if not current and source['status'] != 'void':
            reasons.append('travel_cash_classification_missing')
        if current and current['effect']['source']['source_hash'] != source['source_hash']:
            reasons.append('travel_cash_source_changed')
        items.append(dict(kind='travel_cash', id=source['id'], date=source['date'],
                          source=source, current=current, reasons=reasons))
        for movement in source['cash_movements']:
            movements.append(dict(source_kind='travel_cash', source_id=movement['id'],
                                  account=movement['account'], date=movement['date'],
                                  direction=movement['direction'], amount=movement['amount'],
                                  source_path=source['source_path']))
        dates = {item['date'] for item in source['cash_movements']} or {source['date']}
        if current:
            dates.update(api._effect_dates(current['effect']))
        issues.extend(dict(code=code, source_id=source['id'], date=day,
                           source_path=source['source_path'])
                      for code in reasons for day in sorted(dates))
    return items, issues, movements


def verify_bank_source(office, source):
    """Return the exact original cash identity for an existing bank allocation."""
    from travel_allowance_cash import public_source

    reference = re.fullmatch(
        r'/personnel/travel/financial/([a-f0-9]{32})\?revision=([1-9][0-9]*)',
        source['source_path'])
    if not reference:
        raise ValueError('Invalid travel bank source path')
    original = public_source(office, reference[1], int(reference[2]))
    movement = next((item for item in original['cash_movements']
                     if item['id'] == source['source_id']), None)
    if (movement is None or original['source_hash'] != source['origin_hash']
            or original['source_path'] != source['source_path']):
        raise ValueError('Missing original travel bank cash snapshot')
    return {key: movement[key] for key in ('account', 'date', 'direction', 'amount')}
