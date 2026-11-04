"""Opening balance registration, portable originals and exact restore scopes."""
from copy import deepcopy
from datetime import datetime, timezone
import base64
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

import business_api
import business_schema
from company_export_archive import Builder, _blob
from company_export_catalog import COLUMNS, policy
from core import Office, Problem, canonical


MODULE = 'business_accounting_openings'
TABLES = ('business_accounting_opening_originals',
          'business_accounting_opening_events',
          'business_accounting_opening_requests')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def report(office):
    horizon = business_schema.financial_accounting_horizon(office)
    return dict(schema=horizon['schema_version'] + 1,
                restore_id=business_schema.state(office)['restore_id'],
                reviewed_by='Synthetic opening balance reviewer',
                reviewed_at=datetime.now(timezone.utc).isoformat(),
                number_horizons=[], outbound_reconciled=True,
                accounting_horizon=horizon, accounting_reconciled=True,
                accounting_external_review=dict(reviewed_since_backup=True,
                    evidence_sha256='c' * 64, note='Synthetic independent opening source review'))


def require_review(office):
    with office.db:
        office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=1,restore_id=? '
                          'WHERE singleton=1', (uuid.uuid4().hex,))


class OpeningRegistrationTests(unittest.TestCase):
    def office(self, suffix='current'):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-opening-registration-')
        self.addCleanup(temporary.cleanup)
        office = Office(Path(temporary.name) / (suffix + '.db'))
        self.addCleanup(office.db.close)
        return office

    def test_explicit_catalog_covers_actual_columns_and_original_hash_without_personnel_access(self):
        import business_accounting_openings as module
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        for statement in module.schema_statements('BLOB'):
            db.execute(statement)
        for table in TABLES:
            self.assertEqual([row[1] for row in db.execute('PRAGMA table_info(' + table + ')')],
                             COLUMNS[table].split(','))
            item = policy(table)
            self.assertEqual(item['category'], 'financial')
            self.assertTrue(item['sensitive'])
            self.assertEqual(item['included'], not table.endswith('_requests'))
            self.assertIsNone(item['retention_days'])
            self.assertNotIn('personnel', item['source_access'])
        raw = b'%PDF-1.4\nSynthetic counted opening balance original\n%%EOF'
        builder = Builder()
        self.addCleanup(builder.zip.close)
        descriptor = _blob(builder, TABLES[0], 0, 'original',
                           dict(sha256=digest(raw), media_type='application/pdf'), raw)
        self.assertEqual(builder.zip.read(descriptor['$file']), raw)
        self.assertEqual(descriptor['sha256'], digest(raw))
        with self.assertRaises(Problem) as caught:
            _blob(builder, TABLES[0], 1, 'original', dict(sha256=digest(raw)), raw + b'changed')
        self.assertEqual(caught.exception.status, 409)

    def test_current_empty_scope_is_required_and_malformed_or_omitted_openings_never_unlock(self):
        office = self.office()
        require_review(office)
        evidence = report(office)
        self.assertEqual(evidence['schema'], 13)
        self.assertEqual(evidence['accounting_horizon']['schema_version'], 12)
        opening = evidence['accounting_horizon']['opening_balances']
        self.assertEqual(opening['table_counts'], dict.fromkeys(TABLES, 0))
        old = {key: value for key, value in evidence['accounting_horizon'].items()
               if key != 'opening_balances'}
        old['schema_version'] = 11
        encoded = canonical(old)
        business_schema._validate_financial_accounting_horizon(old, 12)
        self.assertEqual(canonical(old), encoded)
        invalid = [dict(evidence, schema=12, accounting_horizon=old)]
        for change in ('missing', 'extra', 'bool', 'negative', 'schema', 'hash'):
            bad = deepcopy(evidence)
            value = bad['accounting_horizon']['opening_balances']
            if change == 'missing': value['table_counts'].pop(TABLES[0])
            elif change == 'extra': value['table_counts']['future_table'] = 0
            elif change == 'bool': value['table_counts'][TABLES[0]] = True
            elif change == 'negative': value['table_counts'][TABLES[0]] = -1
            elif change == 'schema': value['schema_version'] = True
            else: value['sha256'] = 'changed'
            invalid.append(bad)
        before = '\n'.join(office.db.iterdump())
        for value in invalid:
            with self.subTest(schema=value['schema']), self.assertRaises(ValueError):
                business_schema.reconcile_local_financial_restore(office, value, digest(value), application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()), before)
        accepted = business_schema.reconcile_local_financial_restore(
            office, evidence, digest(evidence), application_stopped=True)
        self.assertTrue(accepted['reconciled'])
        self.assertEqual(business_schema.reconcile_local_financial_restore(
            office, evidence, digest(evidence), application_stopped=True), accepted)

    def test_actual_company_archive_contains_original_binding_and_excludes_technical_receipts(self):
        from business_accounting import Accounting
        from business_accounting_openings import OpeningBalances
        from company_export_archive import verify
        from test_business_company_handover import CompanyHandoverTests
        fixture = CompanyHandoverTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        account = Accounting(fixture.office).create_account(fixture.owner, dict(
            request_id=uuid.uuid4().hex, code='OPENING-EXPORT', name='Synthetic opening export account',
            kind='bank', confirmation=True))
        original = b'%PDF-1.4\nSynthetic financial opening source\n%%EOF'
        accepted = OpeningBalances(fixture.office).upload_original(fixture.owner, dict(
            request_id=uuid.uuid4().hex, account_id=account['id'], filename='opening-source.pdf',
            media_type='application/pdf', content_base64=base64.b64encode(original).decode()))
        _, raw, _ = fixture.archive()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            rows = fixture.rows(archive, TABLES[0])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['id'], accepted['id'])
            self.assertEqual(rows[0]['account_id'], account['id'])
            self.assertEqual(rows[0]['sha256'], digest(original))
            self.assertEqual(archive.read(rows[0]['original']['$file']), original)
            self.assertNotIn('data/' + TABLES[2] + '.jsonl', archive.namelist())
            inventory = json.loads(archive.read('manifest.json'))['inventory']
            source = next(row for row in inventory if row['table'] == TABLES[0])
            self.assertEqual(source['category'], 'financial')
            self.assertTrue(source['sensitive'])
        self.assertTrue(verify(raw, instance_id=fixture.instance)['valid'])

    def test_actual_additive_migration_keeps_approved_schema12_receipt_but_requires13_for_new_restore(self):
        old_registry = tuple(spec for spec in business_schema.registry() if spec.name != MODULE)
        with patch.object(business_schema, 'registry', return_value=old_registry):
            office = self.office('historical')
            require_review(office)
            evidence = report(office)
            self.assertEqual(evidence['schema'], 12)
            accepted = business_schema.reconcile_local_financial_restore(
                office, evidence, digest(evidence), application_stopped=True)
            old_horizon = business_schema.financial_accounting_horizon(office)
            original = canonical(old_horizon)
        business_schema.ensure_schema(office)
        business_schema.ensure_schema(office)
        current = business_schema.financial_accounting_horizon(office)
        previous = {key: value for key, value in current.items() if key != 'opening_balances'}
        previous['schema_version'] = 11
        self.assertEqual(canonical(previous), original)
        before = '\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(
            office, evidence, digest(evidence), application_stopped=True), accepted)
        self.assertEqual('\n'.join(office.db.iterdump()), before)
        require_review(office)
        stale = dict(evidence, restore_id=business_schema.state(office)['restore_id'])
        with self.assertRaises(ValueError):
            business_schema.reconcile_local_financial_restore(office, stale, digest(stale), application_stopped=True)
        self.assertTrue(business_schema.state(office)['financial_reconciliation_required'])
        current_report = report(office)
        self.assertTrue(business_schema.reconcile_local_financial_restore(
            office, current_report, digest(current_report), application_stopped=True)['reconciled'])

    def test_incomplete_financial_dependency_cannot_be_treated_as_absent_opening_scope(self):
        office = self.office()
        capabilities = business_schema.state(office)['read_capabilities']
        with patch.object(business_schema, 'state', return_value=dict(
                read_capabilities=[value for value in capabilities if value != 'business_travel_allowances'])):
            with self.assertRaises(ValueError):
                business_schema.financial_accounting_horizon(office)

    def test_routes_recheck_financial_rights_and_remain_unavailable_for_offline_or_disabled_finance(self):
        from business_foundation import BusinessFoundation
        from business_organization import Organization, NEEDS, MODULES, command_module
        office = self.office()
        owner = dict(id=office.add_user('owner@example.test', 'Synthetic-password-123', 'owner'))
        reader = dict(id=office.add_user('reader@example.test', 'Synthetic-password-123', 'technician'))
        base = '/business/accounting/opening-balances'
        reads = ('', '/sources', '/liquidity', '/accounts/' + 'a' * 32 + '/history', '/originals/' + 'a' * 32)
        writes = ('/originals', '/preview', '/confirm')
        for suffix in reads:
            self.assertEqual(business_api.methods(base + suffix), 'GET')
            self.assertTrue(business_api.strict_workflow_path(base + suffix))
        for suffix in writes:
            self.assertEqual(business_api.methods(base + suffix), 'POST')
            self.assertTrue(business_api.strict_workflow_path(base + suffix))
            self.assertEqual(command_module((base + suffix).removeprefix('/business'), MODULE), 'finance')
            with self.assertRaises(Problem) as caught:
                business_api.dispatch(office, owner, base + suffix, 'GET', {})
            self.assertEqual(caught.exception.status, 405)
        capabilities = business_api.dispatch(office, owner, '/business/capabilities', 'GET', {})[0]
        self.assertIn(MODULE, capabilities['capabilities'])
        self.assertIn('accounting_opening_balances', capabilities['features'])
        foundation = BusinessFoundation(office)
        for permission in ('accounting.read', 'finance.read'):
            foundation.save_grant(owner, dict(request_id=uuid.uuid4().hex, user_id=reader['id'],
                permission=permission, scope='*', effect='allow', revision=0))
        with self.assertRaises(Problem) as caught:
            business_api.dispatch(office, reader, base, 'GET', {})
        self.assertEqual(caught.exception.status, 403)
        foundation.save_grant(owner, dict(request_id=uuid.uuid4().hex, user_id=reader['id'],
            permission='bank.read', scope='*', effect='allow', revision=0))
        self.assertEqual(business_api.dispatch(office, reader, base, 'GET', {})[1], 200)
        for suffix in reads + writes:
            with self.assertRaises(Problem) as caught:
                business_api.dispatch(office, owner, base + suffix,
                    'POST' if suffix in writes else 'GET', {}, offline=True,
                    offline_capabilities=['time_events'])
            self.assertEqual(caught.exception.status, 403)
        organization = Organization(office)
        organization.save(owner, dict(request_id=uuid.uuid4().hex, revision=0, needs=dict(NEEDS),
            modules={key: dict(visible=None, enabled=key != 'finance') for key in MODULES}))
        self.assertEqual(business_api.dispatch(office, owner, base, 'GET', {})[1], 200)
        for suffix in writes:
            with self.assertRaises(Problem) as caught:
                business_api.dispatch(office, owner, base + suffix, 'POST', {})
            self.assertEqual(caught.exception.status, 423)


if __name__ == '__main__':
    unittest.main()
