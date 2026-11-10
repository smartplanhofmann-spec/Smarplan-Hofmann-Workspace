"""Schema-valid synthetic bank originals and independently specified cent totals."""
from pathlib import Path
import hashlib
import unittest
from lxml import etree

from core import Problem
from bank_camt_2026_v1 import parse, SCHEMA_PATH, SCHEMA_SHA256, CONTRACT, NAMESPACE


def statement(*, entries=True):
    # Independently authored values: 100.00 + 125.00 - 25.00 = 200.00.
    return ('''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08"><BkToCstmrStmt>
<GrpHdr><MsgId>synthetic-message</MsgId><CreDtTm>2026-11-01T08:00:00+01:00</CreDtTm></GrpHdr>
<Stmt><Id>synthetic-statement</Id><FrToDt><FrDtTm>2026-10-01T00:00:00+02:00</FrDtTm><ToDtTm>2026-10-31T23:59:59+01:00</ToDtTm></FrToDt>
<Acct><Id><IBAN>DE89370400440532013000</IBAN></Id><Ccy>EUR</Ccy></Acct>
<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">100.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-10-01</Dt></Dt></Bal>
<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">CLOSING</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2026-10-31</Dt></Dt></Bal>
ENTRIES</Stmt></BkToCstmrStmt></Document>'''.replace('CLOSING', '200.00' if entries else '100.00').replace('ENTRIES', '''
<Ntry><NtryRef>reference-credit</NtryRef><Amt Ccy="EUR">125.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts><BookgDt><Dt>2026-10-05</Dt></BookgDt><ValDt><Dt>2026-10-05</Dt></ValDt><AcctSvcrRef>bank-credit-01</AcctSvcrRef><BkTxCd><Prtry><Cd>synthetic-credit</Cd></Prtry></BkTxCd><NtryDtls><TxDtls><RltdPties><Dbtr><Pty><Nm>Synthetische Müller GmbH</Nm></Pty></Dbtr></RltdPties><RmtInf><Ustrd>Rechnung R-100</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
<Ntry><NtryRef>reference-debit</NtryRef><Amt Ccy="EUR">25.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts><Cd>BOOK</Cd></Sts><BookgDt><Dt>2026-10-06</Dt></BookgDt><ValDt><Dt>2026-10-07</Dt></ValDt><AcctSvcrRef>bank-debit-02</AcctSvcrRef><BkTxCd><Prtry><Cd>synthetic-debit</Cd></Prtry></BkTxCd><NtryDtls><TxDtls><RltdPties><Cdtr><Pty><Nm>Synthetischer Lieferant</Nm></Pty></Cdtr></RltdPties><RmtInf><Ustrd>Einkauf E-200</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>''' if entries else '')).encode('utf-8')


class CamtStatementTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(Problem) as error: parse(data)
        self.assertEqual(error.exception.status, 400)

    def test_independent_original_is_schema_valid_and_has_exact_cent_projection(self):
        raw = statement()
        schema = etree.XMLSchema(etree.fromstring(SCHEMA_PATH.read_bytes()))
        schema.assertValid(etree.fromstring(raw))
        value = parse(raw)
        self.assertEqual(value['contract'], CONTRACT)
        self.assertEqual(value['opening_balance'], '100.00')
        self.assertEqual(value['closing_balance'], '200.00')
        self.assertEqual(value['period_from'], '2026-10-01')
        self.assertEqual(value['period_to'], '2026-10-31')
        self.assertEqual(value['rows'], [
            dict(line_number=1, transaction_id='camt08:bank-credit-01', booking_date='2026-10-05', value_date='2026-10-05', amount='125.00', currency='EUR', counterparty='Synthetische Müller GmbH', reference='Rechnung R-100'),
            dict(line_number=2, transaction_id='camt08:bank-debit-02', booking_date='2026-10-06', value_date='2026-10-07', amount='-25.00', currency='EUR', counterparty='Synthetischer Lieferant', reference='Einkauf E-200')])
        self.assertEqual(value['proof']['file_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), SCHEMA_SHA256)

    def test_zero_activity_is_explicit_and_no_transaction_is_fabricated(self):
        value = parse(statement(entries=False))
        self.assertEqual(value['rows'], [])
        self.assertEqual(value['opening_balance'], value['closing_balance'])

    def test_negative_booked_balances_are_not_available_balance_substitutes(self):
        raw = statement(entries=False).replace(b'100.00', b'20.00').replace(b'<CdtDbtInd>CRDT</CdtDbtInd>', b'<CdtDbtInd>DBIT</CdtDbtInd>')
        value = parse(raw)
        self.assertEqual(value['opening_balance'], '-20.00')
        self.assertEqual(value['closing_balance'], '-20.00')
        self.reject(raw.replace(b'OPBD', b'OPAV'))

    def test_bank_identifiers_are_stable_across_statement_rename_and_row_order(self):
        raw = statement()
        original = parse(raw)
        renamed = parse(raw.replace(b'synthetic-statement', b'other-statement'))
        self.assertEqual(original['rows'], renamed['rows'])
        self.reject(raw.replace(b'bank-debit-02', b'bank-credit-01'))
        self.reject(raw.replace(b'bank-credit-01', b'NOTPROVIDED'))

    def test_pending_partial_pages_and_multiple_statements_are_not_complete(self):
        raw = statement()
        self.reject(raw.replace(b'<Cd>BOOK</Cd>', b'<Cd>PDNG</Cd>', 1))
        for page in (b'<PgNb>2</PgNb><LastPgInd>true</LastPgInd>', b'<PgNb>1</PgNb><LastPgInd>false</LastPgInd>'):
            self.reject(raw.replace(b'</CreDtTm>', b'</CreDtTm><MsgPgntn>'+page+b'</MsgPgntn>'))
            self.reject(raw.replace(b'<Id>synthetic-statement</Id>', b'<Id>synthetic-statement</Id><StmtPgntn>'+page+b'</StmtPgntn>'))
        root = etree.fromstring(raw); ns = {'b': NAMESPACE}; message = root.find('b:BkToCstmrStmt', ns)
        message.append(etree.fromstring(etree.tostring(message.find('b:Stmt', ns))))
        self.reject(etree.tostring(root))

    def test_fractional_cents_foreign_currency_and_changed_balances_are_rejected(self):
        raw = statement()
        for old, new in ((b'>125.00<', b'>125.001<'), (b'Ccy="EUR"', b'Ccy="USD"'), (b'>200.00<', b'>201.00<')):
            self.reject(raw.replace(old, new, 1))

    def test_schema_and_identity_cannot_be_selected_by_the_document(self):
        raw = statement()
        self.reject(raw.replace(b'camt.053.001.08', b'camt.053.001.02'))
        self.reject(raw.replace(b'<Id>synthetic-statement</Id>', b'<Id>synthetic-statement</Id><Id>duplicate</Id>'))
        self.reject(raw.replace(b'<AcctSvcrRef>bank-credit-01</AcctSvcrRef>', b'').replace(b'<NtryRef>reference-credit</NtryRef>', b''))
        external_schema = raw.replace(b'<Document ', b'<Document xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08 https://example.invalid/evil.xsd" ')
        self.assertEqual(parse(external_schema)['rows'], parse(raw)['rows'])

    def test_dtd_entities_processing_instructions_and_invalid_encoding_are_blocked(self):
        raw = statement()
        self.reject(raw.replace(b'<Document ', b'<!DOCTYPE Document [<!ENTITY secret SYSTEM "file:///etc/passwd">]><Document ', 1))
        self.reject(raw.replace(b'<Document ', b'<?xml-stylesheet href="https://example.invalid/evil"?><Document ', 1))
        self.reject(raw.decode().encode('utf-16'))
        self.reject(raw.replace(b'encoding="UTF-8"', b'encoding="ISO-8859-1"'))
        self.reject(b'')
        self.reject(raw.replace(b'<Ustrd>Rechnung R-100</Ustrd>', b'<Ustrd>&unknown;</Ustrd>'))

    def test_explicit_exclusive_midnight_is_preserved_without_timezone_conversion(self):
        raw = statement().replace(b'2026-10-31T23:59:59+01:00', b'2026-11-01T00:00:00+01:00')
        self.assertEqual(parse(raw)['period_to'], '2026-10-31')
        self.reject(raw.replace(b'2026-11-01T00:00:00+01:00', b'2026-10-31T12:00:00+01:00'))

    def test_missing_or_ambiguous_booked_period_and_balances_do_not_get_guessed(self):
        root = etree.fromstring(statement());ns = {'b': NAMESPACE}
        s = root.find('b:BkToCstmrStmt/b:Stmt', ns)
        s.remove(s.find('b:FrToDt', ns));self.reject(etree.tostring(root))
        root = etree.fromstring(statement());s = root.find('b:BkToCstmrStmt/b:Stmt', ns)
        s.insert(3, etree.fromstring(etree.tostring(s.find('b:Bal', ns))))
        self.reject(etree.tostring(root))

    def test_statement_summary_is_checked_independently_of_the_balance_equation(self):
        raw = statement()
        summary = b'<TxsSummry><TtlNtries><NbOfNtries>2</NbOfNtries><Sum>150.00</Sum><TtlNetNtry><Amt>100.00</Amt><CdtDbtInd>CRDT</CdtDbtInd></TtlNetNtry></TtlNtries><TtlCdtNtries><NbOfNtries>1</NbOfNtries><Sum>125.00</Sum></TtlCdtNtries><TtlDbtNtries><NbOfNtries>1</NbOfNtries><Sum>25.00</Sum></TtlDbtNtries></TxsSummry>'
        raw = raw.replace(b'\n<Ntry>', summary+b'\n<Ntry>', 1)
        self.assertEqual(len(parse(raw)['rows']), 2)
        self.reject(raw.replace(b'<NbOfNtries>2</NbOfNtries>', b'<NbOfNtries>1</NbOfNtries>'))
        self.reject(raw.replace(b'<Sum>150.00</Sum>', b'<Sum>149.99</Sum>'))
        self.reject(raw.replace(b'<Amt>100.00</Amt>', b'<Amt>99.99</Amt>'))


if __name__ == '__main__': unittest.main()
