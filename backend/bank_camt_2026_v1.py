"""Bounded camt.053.001.08 EUR statement projection; no cash creation.

Only the packaged, hash-pinned schema is trusted. The original XML remains the
source; projected entry identities never depend on a statement/page/row number.
"""
from datetime import datetime, time, timedelta
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import threading

from lxml import etree

from core import Problem
from business_bank_reconciliation import _iban, _line, _money, _cents
from business_operations import iso_date

CONTRACT = 'smartplan_bank_camt053_08_v1'
NAMESPACE = 'urn:iso:std:iso:20022:tech:xsd:camt.053.001.08'
SCHEMA_SHA256 = 'c3cfac080dc31476bde7444b05d00e1b23558d5e44529e58d0ad562e6013873d'
SCHEMA_PATH = Path(__file__).with_name('bank_formats') / 'camt053_v08' / 'camt.053.001.08.xsd'
MAX_FILE = 5 * 1024 * 1024
MAX_ENTRIES = 10000
_LOCK = threading.RLock()
_NS = {'b': NAMESPACE}


def _reject(message):
    raise Problem(400, 'CAMT-Auszug: '+message)


class _NoExternal(etree.Resolver):
    def resolve(self, url, public_id, context):
        _reject('externe Ressourcen sind nicht erlaubt.')


def _parser():
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
        dtd_validation=False, attribute_defaults=False, collect_ids=False,
        huge_tree=False, recover=False, strip_cdata=False)
    parser.resolvers.add(_NoExternal())
    return parser


@lru_cache(maxsize=1)
def _schema():
    raw = SCHEMA_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCHEMA_SHA256:
        raise Problem(500, 'Das festgelegte Bank-XML-Schema besteht die Integritätsprüfung nicht.')
    return etree.XMLSchema(etree.fromstring(raw, _parser()))


def _find(node, path):
    return node.find('/'.join('b:'+part for part in path.split('/')), _NS)


def _all(node, path):
    return node.findall('/'.join('b:'+part for part in path.split('/')), _NS)


def _text(node, path, *, required=False):
    value = _find(node, path)
    if value is None:
        if required: _reject('erforderliches Feld fehlt: '+path)
        return None
    return value.text or ''


def _stamp(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?', value):
            raise ValueError()
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if not 1900 <= result.year <= 2200: raise ValueError()
        return result
    except (TypeError, ValueError):
        _reject('vollständiger belegter Zeitpunkt erforderlich.')


def _day(node, path):
    choice = _find(node, path)
    if choice is None: _reject('Buchungs-, Wertstellungs- und Saldentage müssen belegt sein.')
    day, stamp = _text(choice, 'Dt'), _text(choice, 'DtTm')
    if day is not None:
        day=iso_date(day)
        if not 1900 <= int(day[:4]) <= 2200: _reject('belegter Kalendertag außerhalb des unterstützten Zeitraums.')
        return day
    return _stamp(stamp).date().isoformat()


def _amount(node):
    if node is None or node.get('Ccy') != 'EUR': _reject('nur ausdrücklich belegte EUR-Beträge unterstützt.')
    return _decimal(node.text)


def _decimal(raw):
    raw = (raw or '').strip()
    if not re.fullmatch(r'\+?\d{1,15}(?:\.\d{1,2})?', raw, re.ASCII):
        _reject('Betrag muss ohne Rundung in ganzen Cent darstellbar sein.')
    parts = raw.lstrip('+').split('.')
    minor = int(parts[0])*100 + int((parts[1] if len(parts) == 2 else '').ljust(2, '0'))
    _cents(_money(minor), signed=False)
    return minor


def _direction(node):
    value = _text(node, 'CdtDbtInd', required=True)
    if value not in ('CRDT', 'DBIT'): _reject('bekannte Soll-/Haben-Richtung erforderlich.')
    return 1 if value == 'CRDT' else -1


def _pagination(node, path):
    value = _find(node, path)
    if value is not None and (int(_text(value, 'PgNb')) != 1 or _text(value, 'LastPgInd') not in ('true', '1')):
        _reject('nur vollständige ungeteilte Auszüge unterstützt; keine Teilseite importieren.')


def _period(statement):
    first = _text(statement, 'FrToDt/FrDtTm', required=True)
    last = _text(statement, 'FrToDt/ToDtTm', required=True)
    start, end = _stamp(first), _stamp(last)
    if (start.tzinfo is None) != (end.tzinfo is None): _reject('einheitliche Zeitangaben erforderlich.')
    if start.time().replace(tzinfo=None) != time(0) or end <= start:
        _reject('vollständige Kalendertage als Auszugszeitraum erforderlich.')
    closing_day = end.date()
    if end.time().replace(tzinfo=None) == time(0):
        closing_day -= timedelta(days=1)  # Explicit exclusive next-day midnight.
    elif (end.hour, end.minute, end.second) != (23, 59, 59):
        _reject('Endgrenze muss Tagesende oder ausschließlich den nächsten Tagesbeginn belegen.')
    if not 0 <= (closing_day-start.date()).days <= 366: _reject('Auszugszeitraum umfasst höchstens367 Tage.')
    return start.date().isoformat(), closing_day.isoformat(), first, last


def _reference(entry, details):
    values = []
    for detail in details:
        values.extend(node.text or '' for node in _all(detail, 'RmtInf/Ustrd'))
        values.extend(node.text or '' for node in _all(detail, 'RmtInf/Strd/CdtrRefInf/Ref'))
    addition = _text(entry, 'AddtlNtryInf')
    if addition: values.append(addition)
    return _line(' | '.join(value for value in values if value), 'CAMT-Verwendungszweck', 2000, False)


def _summary(statement, rows):
    summary = _find(statement, 'TxsSummry')
    if summary is None: return
    # Per-code availability/subtotals require their own explicit projection.
    if _all(summary, 'TtlNtriesPerBkTxCd'):
        _reject('Bankcode-Untergruppen sind unter diesem Formatvertrag noch nicht unterstützt.')
    for kind, amounts in (
            ('TtlNtries', [_cents(row['amount']) for row in rows]),
            ('TtlCdtNtries', [_cents(row['amount']) for row in rows if _cents(row['amount']) > 0]),
            ('TtlDbtNtries', [_cents(row['amount']) for row in rows if _cents(row['amount']) < 0])):
        node = _find(summary, kind)
        if node is None: continue
        count, total = _text(node, 'NbOfNtries'), _text(node, 'Sum')
        if count is not None and int(count) != len(amounts): _reject('belegte Buchungsanzahl stimmt nicht mit den Bewegungen überein.')
        if total is not None and _decimal(total) != sum(abs(value) for value in amounts): _reject('belegte Buchungssumme stimmt nicht mit den Bewegungen überein.')
        net = _find(node, 'TtlNetNtry')
        if net is not None and _direction(net) * _decimal(_text(net, 'Amt', required=True)) != sum(amounts):
            _reject('belegte Nettobuchungssumme stimmt nicht mit den Bewegungen überein.')


def parse(original):
    if not isinstance(original, bytes) or not 1 <= len(original) <= MAX_FILE:
        _reject('Originaldatei benötigt1 Byte bis höchstens5 MiB.')
    try:
        original.decode('utf-8-sig')
        if b'<!DOCTYPE' in original or b'<!ENTITY' in original:
            _reject('DTD und Entitäten sind nicht erlaubt.')
        root = etree.fromstring(original, _parser())
    except (UnicodeError, etree.XMLSyntaxError, ValueError):
        _reject('gültiges UTF-8-XML ohne externe Ressourcen erforderlich.')
    if root.tag != '{'+NAMESPACE+'}Document':
        _reject('nur camt.053.001.08 wird unter diesem Vertrag unterstützt.')
    if root.getroottree().docinfo.encoding.upper().replace('-', '') != 'UTF8':
        _reject('die XML-Zeichencodierung muss UTF-8 sein.')
    if root.getroottree().docinfo.doctype: _reject('DTD sind nicht erlaubt.')
    if root.getroottree().xpath('//processing-instruction()'):
        _reject('Verarbeitungsanweisungen sind nicht erlaubt.')
    count = 0
    for node in root.iter():
        count += 1
        if count > 100000: _reject('zu viele XML-Elemente.')
        if sum(1 for _ in node.iterancestors()) > 64: _reject('XML-Verschachtelung überschreitet den erlaubten Umfang.')
    with _LOCK:
        if not _schema().validate(root):
            _reject('Datei entspricht nicht dem festgelegten lokalen Schema; keine Bankbewegung übernommen.')
    message = _find(root, 'BkToCstmrStmt')
    _pagination(message, 'GrpHdr/MsgPgntn')
    statements = _all(message, 'Stmt')
    if len(statements) != 1: _reject('genau ein vollständiger Kontoauszug pro Datei erforderlich.')
    statement = statements[0]
    _pagination(statement, 'StmtPgntn')
    iban = _iban(_text(statement, 'Acct/Id/IBAN', required=True))
    if _text(statement, 'Acct/Ccy') != 'EUR': _reject('Auszugskonto muss ausdrücklich in EUR geführt werden.')
    start, end, original_from, original_to = _period(statement)
    balances = {}
    for balance in _all(statement, 'Bal'):
        amount = _direction(balance) * _amount(_find(balance, 'Amt'))
        kind = _text(balance, 'Tp/CdOrPrtry/Cd')
        if kind in ('OPBD', 'CLBD'):
            if kind in balances: _reject('mehrdeutiger gebuchter Anfangs-/Endsaldo.')
            balances[kind] = (amount, _day(balance, 'Dt'))
    if set(balances) != {'OPBD', 'CLBD'}: _reject('gebuchter Anfangs- und Endsaldo erforderlich; verfügbare Salden genügen nicht.')
    if balances['OPBD'][1] != start or balances['CLBD'][1] != end:
        _reject('Saldentage stimmen nicht mit der belegten Auszugsperiode überein.')
    entries = _all(statement, 'Ntry')
    if len(entries) > MAX_ENTRIES: _reject('höchstens10.000 Kontobewegungen unterstützt.')
    rows, identities, sources = [], set(), []
    for index, entry in enumerate(entries, 1):
        if _text(entry, 'Sts/Cd') != 'BOOK': _reject('vorgemerkte, informative oder unbekannte Bewegungen sind kein vollständiger Buchungsauszug.')
        amount = _direction(entry) * _amount(_find(entry, 'Amt'))
        if not amount: _reject('Nullbeträge sind keine unterstützten Bankbewegungen.')
        bank_ref = _text(entry, 'AcctSvcrRef') or _text(entry, 'NtryRef')
        if not bank_ref or bank_ref.strip().upper() in ('NOTPROVIDED', 'NONREF', 'N/A', '/'):
            _reject('stabile Bankreferenz je Kontobewegung erforderlich; Zeilennummern sind keine Identität.')
        external_id = 'camt08:' + _line(bank_ref, 'Stabile Bankreferenz', 35)
        if external_id in identities: _reject('Bankreferenz kommt innerhalb der Datei mehrfach vor.')
        identities.add(external_id)
        booking, value = _day(entry, 'BookgDt'), _day(entry, 'ValDt')
        if not start <= booking <= end: _reject('Buchungstag liegt außerhalb der belegten Periode.')
        details = _all(entry, 'NtryDtls/TxDtls')
        party = ''
        if len(details) == 1:
            side = 'Dbtr' if amount > 0 else 'Cdtr'
            party = _text(details[0], 'RltdPties/'+side+'/Pty/Nm') or ''
        rows.append(dict(line_number=index, transaction_id=external_id, booking_date=booking,
            value_date=value, amount=_money(amount), currency='EUR',
            counterparty=_line(party, 'Gegenpartei', 500, False), reference=_reference(entry, details)))
        sources.append(dict(line_number=index, xml_line=entry.sourceline, bank_reference=bank_ref,
            entry_reference=_text(entry, 'NtryRef'), transaction_details=len(details),
            reversal=_text(entry, 'RvslInd') in ('true', '1')))
    opening, closing = balances['OPBD'][0], balances['CLBD'][0]
    _summary(statement, rows)
    if opening + sum(_cents(row['amount']) for row in rows) != closing:
        _reject('gebuchter Anfangssaldo plus Bewegungen stimmt nicht mit dem gebuchten Endsaldo überein.')
    return dict(contract=CONTRACT, iban=iban,
        statement_reference=_line(_text(statement, 'Id', required=True), 'Auszugsreferenz', 35),
        period_from=start, period_to=end, opening_balance=_money(opening), closing_balance=_money(closing), rows=rows,
        proof=dict(schema_sha256=SCHEMA_SHA256, namespace=NAMESPACE,
            file_sha256=hashlib.sha256(original).hexdigest(), message_id=_text(message, 'GrpHdr/MsgId'),
            original_period_from=original_from, original_period_to=original_to, entry_sources=sources))
