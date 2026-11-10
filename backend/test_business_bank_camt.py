"""Full existing bank journal with XML originals, no invented cash or payments."""
import base64
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import io
import json
import unittest
import zipfile

from business_bank_camt import CamtBankReconciliation, DELIMITER, verify_projection
from business_bank_reconciliation import validate_integrity, TABLES
import test_business_bank_reconciliation as fixture
from test_bank_camt_2026_v1 import statement


class CamtBankTests(unittest.TestCase):
    req = fixture.BankTests.req
    error = fixture.BankTests.error
    account_body = fixture.BankTests.account_body
    file = fixture.BankTests.file
    import_body = fixture.BankTests.import_body
    save_statement = fixture.BankTests.save_statement

    def setUp(self):
        fixture.BankTests.setUp(self)
        self.camt = CamtBankReconciliation(self.office, clock=self.fixture.clock)

    def inspect_body(self):
        return dict(account_id=self.account['id'], account_revision=1,
            bank_revision=self.binding['revision'], filename='synthetic.xml',
            content_base64=base64.b64encode(statement()).decode())

    def body(self):
        data = self.inspect_body()
        inspected = self.camt.inspect(self.owner, data)
        return dict(inspected['suggested_body'], content_base64=data['content_base64'], complete_statement_confirmed=True)

    def save(self):
        body = self.body()
        preview = self.camt.preview_import(self.owner, body)
        self.assertTrue(preview['can_import'], preview['errors'])
        command = self.req(**body, preview_hash=preview['preview_hash'], confirmation=True)
        return self.camt.import_statement(self.owner, command), command

    def counts(self):
        return {table:self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in TABLES}

    def test_inspection_is_read_only_and_never_confirms_completeness_for_the_user(self):
        before = self.counts()
        inspected = self.camt.inspect(self.owner, self.inspect_body())
        self.assertEqual(inspected['suggested_body']['delimiter'], DELIMITER)
        self.assertNotIn('content_base64', inspected['suggested_body'])
        self.assertNotIn('complete_statement_confirmed', inspected['suggested_body'])
        self.assertIs(inspected['financial_changes'], False)
        self.assertIs(inspected['confirmation_required'], True)
        self.assertEqual(inspected['original_sha256'], hashlib.sha256(statement()).hexdigest())
        self.assertEqual(self.counts(), before)

    def test_import_retains_exact_xml_and_existing_journal_identity_and_integrity(self):
        saved, command = self.save()
        original, mime = self.bank.original(self.owner, saved['statement']['id'])
        self.assertEqual(original, statement())
        self.assertEqual(mime, 'application/xml; charset=utf-8')
        self.assertEqual(len(saved['lines']), 2)
        self.assertEqual(self.camt.import_statement(self.owner, command), saved)
        self.assertEqual(self.counts()['business_bank_transactions'], 2)
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_euer_entries').fetchone()[0], 0)

    def test_original_nonce_concurrently_creates_only_one_statement_and_no_duplicate_lines(self):
        body = self.body(); preview = self.camt.preview_import(self.owner, body)
        command = self.req(**body, preview_hash=preview['preview_hash'], confirmation=True)
        with ThreadPoolExecutor(2) as pool:
            values = list(pool.map(lambda _: self.camt.import_statement(self.owner, command), range(2)))
        self.assertEqual(values[0], values[1])
        counts = self.counts()
        self.assertEqual(counts['business_bank_statements'], 1)
        self.assertEqual(counts['business_bank_transactions'], 2)
        self.assertEqual(counts['business_bank_statement_lines'], 2)
        self.assertTrue(validate_integrity(self.office))

    def test_portable_company_archive_keeps_exact_xml_and_versioned_bank_projection(self):
        from company_export_archive import build, structure, verify
        saved, _ = self.save()
        instance = '1' * 32
        raw, manifest = build(self.office, instance_id=instance, export_id='2' * 32,
            created_at=self.camt.now(), created_by=self.owner['id'],
            reason='Synthetic XML original handover', inventory=structure(self.office))
        self.assertEqual(verify(raw, instance_id=instance)['instance_id'], instance)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows = [json.loads(line) for line in archive.read('data/business_bank_statements.jsonl').splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['id'], saved['statement']['id'])
            self.assertEqual(archive.read(row['original']['$file']), statement())
            self.assertEqual(json.loads(row['payload_json']), saved['statement']['payload'])
        self.assertTrue(manifest['complete_for_classified_database_business_records'])

    def test_canonical_ids_already_imported_from_csv_do_not_duplicate_xml_movements(self):
        from bank_camt_2026_v1 import parse
        rows = parse(statement())['rows']
        self.save_statement(rows, period_from='2026-10-01', period_to='2026-10-31',
            opening_balance='100.00', closing_balance='200.00')
        saved, _ = self.save()
        self.assertEqual(len(saved['lines']), 2)
        self.assertEqual(self.counts()['business_bank_transactions'], 2)
        self.assertEqual(self.counts()['business_bank_statements'], 2)
        self.assertTrue(validate_integrity(self.office))

    def test_foreign_iban_or_changed_original_period_and_balances_cannot_be_overridden(self):
        body = self.body(); before = self.counts()
        for key, value in [('opening_balance','0.00'), ('closing_balance','201.00'),
                ('period_from','2026-01-01'), ('statement_reference','Invented')]:
            self.error(409, self.camt.preview_import, self.owner, {**body, key:value})
        changed = statement().replace(b'DE89370400440532013000', b'DE12500105170648489890')
        self.error(409, self.camt.preview_import, self.owner,
            {**body, 'content_base64':base64.b64encode(changed).decode()})
        self.assertEqual(self.counts(), before)

    def test_changed_bytes_after_review_cannot_reuse_an_old_preview(self):
        body = self.body(); preview = self.camt.preview_import(self.owner, body)
        changed = statement().replace(b'Rechnung R-100', b'Rechnung R-101')
        command = self.req(**{**body, 'content_base64':base64.b64encode(changed).decode()}, preview_hash=preview['preview_hash'], confirmation=True)
        self.error(409, self.camt.import_statement, self.owner, command)
        self.assertEqual(self.counts()['business_bank_statements'], 0)

    def test_unknown_fields_and_stale_account_versions_do_not_create_archive_rows(self):
        body = self.body()
        self.error(400, self.camt.preview_import, self.owner, {**body, 'ignore_schema':True})
        self.error(409, self.camt.preview_import, self.owner, {**body, 'bank_revision':2})
        self.error(400, self.camt.inspect, self.owner, {**self.inspect_body(), 'filename':True})
        self.assertEqual(self.counts()['business_bank_statements'], 0)

    def test_stored_projection_checks_every_source_field_instead_of_trusting_a_hash_label(self):
        saved, _ = self.save()
        metadata = saved['statement']['payload']
        for key, value in [('camt',{}), ('rows',[]), ('closing_balance','201.00'),
                ('delimiter',';'), ('contract','unknown')]:
            modified = copy.deepcopy(metadata);modified[key] = value
            self.error(409, verify_projection, modified, statement())


if __name__ == '__main__': unittest.main()
