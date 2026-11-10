"""Bounded read-only Qonto V2 changes, never a bank statement or cash posting.

Official contracts (retrieved 2026-11-10) and deliberate bounds are recorded in
docs/CRM_ERP_BANK_LIEFERANTEN_ANBINDUNGEN_2026-11-10.md. Only the selected
organization and one IBAN are projected; unknown provider fields stay private.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal, DecimalException
import hashlib
import json
import re
import uuid

from core import Problem, canonical
from business_bank_reconciliation import _iban
from online.integration_http import IntegrationHttp, integration_deadline

STATUSES = ('pending', 'declined', 'completed', 'reversed')
MAX_ITEMS = 1000
PER_PAGE = 100
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


def invalid():
    return Problem(503, 'Qonto liefert keinen eindeutig prüfbaren Umsatzstand. Es wurde nichts gebucht.')


def _id(value):
    if not isinstance(value, str):
        raise invalid()
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError()
    except ValueError:
        raise invalid() from None
    return value


def _text(value, maximum=200, *, nullable=False):
    if nullable and value is None:
        return None
    if (not isinstance(value, str) or len(value) > maximum or
            any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise invalid()
    return value


def _cents(value):
    if type(value) is not int or abs(value) > 999999999999999:
        raise invalid()
    return value


def _pair(row, key, *, nonnegative=False):
    cents = _cents(row.get(key + '_cents'))
    if nonnegative and cents < 0:
        raise invalid()
    if key in row:
        major = row[key]
        try:
            matches = type(major) in (int, Decimal) and Decimal(major).is_finite() and Decimal(major) * 100 == cents
        except DecimalException:
            matches = False
        if not matches:
            raise invalid()
    return cents


def _time(value, *, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})', value):
        raise invalid()
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError()
        return parsed
    except ValueError:
        raise invalid() from None


def window(start, end):
    """Explicit UTC instants and an exclusive upper bound, at most 31 days."""
    try:
        first, last = _time(start), _time(end)
        if not timedelta(0) < last - first <= timedelta(days=31):
            raise ValueError()
    except (Problem, ValueError, TypeError):
        raise Problem(400, 'Für den lesenden Qonto-Abruf einen Zeitraum von höchstens 31 Tagen mit Zeitzone wählen.') from None
    return first, last


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def authorization(token, auth_mode='oauth_access_token', login=None):
    """Exact Qonto header: API key is sign-in:key, not Basic or Bearer."""
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~+/-]{16,8192}={0,2}', token):
        raise Problem(409, 'Der serverseitige Qonto-Lesezugang muss erneuert werden.')
    if auth_mode == 'oauth_access_token' and login in (None, ''):
        return 'Bearer ' + token
    if (auth_mode == 'own_account_api_key' and isinstance(login, str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,199}', login)):
        return login + ':' + token
    raise Problem(409, 'Die serverseitige Qonto-Anmeldungsart muss geprüft werden.')


class QontoReader:
    def __init__(self, *, http=None):
        self.http = http or IntegrationHttp('qonto')

    def collect(self, *, token, organization_id, iban, updated_from, updated_to,
                auth_mode='oauth_access_token', login=None):
        first, last = window(updated_from, updated_to)
        _id(organization_id)
        iban = _iban(iban)
        header = authorization(token, auth_mode, login)
        sources = []
        size = 0

        def get(path, params=None):
            nonlocal size
            body, headers = self.http.raw(path, params=params, headers={'Authorization': header}, max_bytes=MAX_PAGE_BYTES)
            size += len(body)
            if size > MAX_TOTAL_BYTES:
                raise invalid()
            media = headers.get('content-type', '').split(';')[0].strip().lower()
            if media != 'application/json':
                raise invalid()
            try:
                value = json.loads(body.decode('utf-8'), parse_float=Decimal,
                                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError()), object_pairs_hook=_object)
                if not isinstance(value, dict):
                    raise ValueError()
            except (ValueError, UnicodeError, RecursionError):
                raise invalid() from None
            sources.append(dict(path=path, query=params or {}, bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
            return value

        def account():
            org = get('/v2/organization').get('organization')
            if not isinstance(org, dict) or org.get('id') != organization_id or not isinstance(org.get('bank_accounts'), list) or len(org['bank_accounts']) > 100:
                raise invalid()
            found = [a for a in org['bank_accounts'] if isinstance(a, dict) and a.get('iban') == iban]
            if len(found) != 1 or found[0].get('currency') != 'EUR' or found[0].get('status') != 'active':
                raise invalid()
            a = found[0]
            result = dict(iban=iban, name=_text(a.get('name')), balance_cents=_pair(a, 'balance'),
                          authorized_balance_cents=_pair(a, 'authorized_balance'), updated_at=a.get('updated_at'))
            _time(result['updated_at'])
            if a.get('id') is not None:
                result['remote_id'] = _id(a['id'])
            return dict(id=organization_id, name=_text(org.get('legal_name'))), result

        with integration_deadline():
            organization, before = account()
            rows, seen = [], set()
            expected_count = None
            remote_account = before.get('remote_id')
            page = 1
            while True:
                params = dict(iban=iban, **{'status[]': list(STATUSES)}, updated_at_from=updated_from,
                              updated_at_to=updated_to, sort_by='updated_at:asc', page=page, per_page=PER_PAGE)
                value = get('/v2/transactions', params)
                items, meta = value.get('transactions'), value.get('meta')
                if not isinstance(items, list) or len(items) > PER_PAGE or not isinstance(meta, dict):
                    raise invalid()
                for key in ('current_page', 'total_pages', 'total_count', 'per_page'):
                    if type(meta.get(key)) is not int:
                        raise invalid()
                count = meta['total_count']
                if not 0 <= count <= MAX_ITEMS or meta['current_page'] != page or meta['per_page'] != PER_PAGE:
                    raise invalid()
                total_pages = max(1, (count + PER_PAGE - 1) // PER_PAGE)
                if meta['total_pages'] not in ((0, 1) if count == 0 else (total_pages,)):
                    raise invalid()
                following = page + 1 if page < total_pages else None
                if (type(meta.get('next_page')) not in (int, type(None)) or type(meta.get('prev_page')) not in (int, type(None)) or
                        meta.get('next_page') != following or meta.get('prev_page') != (page - 1 if page > 1 else None)):
                    raise invalid()
                if expected_count is not None and expected_count != count:
                    raise Problem(409, 'Der Qonto-Umsatzstand hat sich während des Abrufs geändert. Bitte erneut lesen.')
                expected_count = count
                for item in items:
                    if not isinstance(item, dict):
                        raise invalid()
                    key = _id(item.get('id'))
                    account_id = _id(item.get('bank_account_id'))
                    if key in seen or (remote_account is not None and account_id != remote_account):
                        raise invalid()
                    remote_account = account_id
                    seen.add(key)
                    status, side = item.get('status'), item.get('side')
                    if status not in STATUSES or side not in ('credit', 'debit') or item.get('currency') != 'EUR' or item.get('is_external_transaction') is not False:
                        raise invalid()
                    amount = _pair(item, 'amount', nonnegative=True)
                    changed = _time(item.get('updated_at'))
                    if changed < first or changed > last:
                        raise invalid()
                    settled = item.get('settled_at')
                    _time(settled, nullable=True)
                    if status == 'completed' and settled is None:
                        raise invalid()
                    row = dict(id=key, transaction_id=_text(item.get('transaction_id')),
                               bank_account_id=account_id, amount_cents=amount,
                               signed_amount_cents=amount if side == 'credit' else -amount,
                               currency='EUR', status=status, side=side,
                               label=_text(item.get('label'), 2000), counterparty=_text(item.get('clean_counterparty_name'), 500, nullable=True),
                               reference=_text(item.get('reference'), 2000, nullable=True),
                               updated_at=item['updated_at'], settled_at=settled)
                    if changed < last:  # API boundary inclusiveness must not change our explicit window.
                        rows.append(row)
                if following is None:
                    break
                page = following
            if len(seen) != expected_count:
                raise invalid()
            after_org, after = account()
            if after_org['id'] != organization['id'] or after.get('remote_id', remote_account) != remote_account:
                raise invalid()
            rows.sort(key=lambda row: (_time(row['updated_at']), row['id']))
        payload = dict(schema_version=1, provider='qonto', read_only=True, organization=organization,
                       account_before=before, account_after=after, items=rows,
                       window=dict(updated_from=updated_from, updated_to=updated_to, upper_exclusive=True),
                       provider_rows=expected_count, source_pages=sources,
                       complete_statement=False, atomic_snapshot=False, financial_changes=False)
        return dict(payload, content_hash=hashlib.sha256(canonical(payload).encode()).hexdigest(),
                    read_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
