"""Explicit preparation profile over real MFA routes and local restore tooling.

All records are synthetic. Migration tests preserve genuine prior C1/R1/C2/R2
rows, with the existing explicitly synthetic SQLite invoice archive fixture.
No real tax registration, authority lookup or production system is involved.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

from backend.backup import backup
import business_schema
from core import Office, Problem, canonical
from backend.restore import restore
from online import test_accounting_refunds_v2_http as refunds
from online import test_accounting_journey as journey

PREFIX = '/business/accounting/profile'
TABLES = ('business_accounting_profile_versions', 'business_accounting_profile_requests')
FLAGS = dict(scope='organization_profile', tax_status='unconfigured', tax_result_available=False)
STATE_FIELDS = {'revision', 'state_hash', 'preparation_status', 'current', 'writes_allowed'} | set(FLAGS)
ENTRY_FIELDS = {'profile', 'reason', 'evidence_reference', 'preview_hash', 'id', 'revision',
                'previous_state_hash', 'created_by', 'created_at'} | set(FLAGS)


def empty_profile(**changes):
    return dict(legal_form='sole_proprietorship', accounting_method='euer', vat_regime=None,
                vat_timing=None, vat_effective_from=None, bookkeeping_start=None) | changes


class AccountingProfileHTTPTests(unittest.TestCase):
    setUp = refunds.AccountingRefundsV2HTTPTests.setUp
    new_company = refunds.AccountingRefundsV2HTTPTests.new_company
    open_app = refunds.AccountingRefundsV2HTTPTests.open_app
    call = refunds.AccountingRefundsV2HTTPTests.call
    login = refunds.AccountingRefundsV2HTTPTests.login
    user = refunds.AccountingRefundsV2HTTPTests.user
    permission = refunds.AccountingRefundsV2HTTPTests.permission
    payment = refunds.AccountingRefundsV2HTTPTests.payment
    account_record = refunds.AccountingRefundsV2HTTPTests.account_record
    source = refunds.AccountingRefundsV2HTTPTests.source
    import_body = refunds.AccountingRefundsV2HTTPTests.import_body
    legacy_sources = refunds.AccountingRefundsV2HTTPTests.legacy_sources
    report = refunds.AccountingRefundsV2HTTPTests.report
    report_hash = staticmethod(refunds.AccountingRefundsV2HTTPTests.report_hash)
    require_reconciliation = refunds.AccountingRefundsV2HTTPTests.require_reconciliation
    imported_payment = refunds.AccountingRefundsV2HTTPTests.imported_payment
    synthetic_invoice = refunds.AccountingRefundsV2HTTPTests.synthetic_invoice
    assignment = refunds.AccountingRefundsV2HTTPTests.assignment
    component_command = refunds.AccountingRefundsV2HTTPTests.component_command
    origin_case = refunds.AccountingRefundsV2HTTPTests.origin_case
    imported_refund = refunds.AccountingRefundsV2HTTPTests.imported_refund
    refund_command = refunds.AccountingRefundsV2HTTPTests.refund_command
    receipt = refunds.AccountingRefundsV2HTTPTests.receipt
    released_origin = refunds.AccountingRefundsV2HTTPTests.released_origin
    capacity_command = refunds.AccountingRefundsV2HTTPTests.capacity_command
    reused_origin = refunds.AccountingRefundsV2HTTPTests.reused_origin
    r2_command = refunds.AccountingRefundsV2HTTPTests.r2_command
    rebound = refunds.AccountingRefundsV2HTTPTests.rebound

    def state(self, *, token='owner', company=None):
        value = self.call(company or self.company, PREFIX, token=token).json
        self.assertEqual(set(value), STATE_FIELDS)
        for key, expected in FLAGS.items():
            self.assertEqual(value[key], expected)
        return value

    def draft(self, *, profile=None, reason='Synthetic owner preparation statement', token='owner'):
        state = self.state(token=token)
        return dict(expected_revision=state['revision'], state_hash=state['state_hash'],
                    profile=empty_profile() if profile is None else profile,
                    reason=reason, evidence_reference='Synthetic owner statement only')

    def command(self, body=None, *, token='owner'):
        body = self.draft(token=token) if body is None else body
        preview = self.call(self.company, PREFIX + '/preview', body, token=token).json
        self.assertEqual(set(preview), set(body) | set(FLAGS) | {'preview_hash'})
        self.assertEqual({key: preview[key] for key in body}, body)
        self.assertEqual({key: preview[key] for key in FLAGS}, FLAGS)
        self.assertEqual(preview['preview_hash'], hashlib.sha256(canonical(
            {key: value for key, value in preview.items() if key != 'preview_hash'}).encode()).hexdigest())
        return journey.request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirmed(self, body=None, *, token='owner'):
        command = self.command(body, token=token)
        entry = self.call(self.company, PREFIX + '/confirm', command, token=token, status=201).json
        self.assertEqual(set(entry), ENTRY_FIELDS)
        return entry, command

    def database(self):
        return '\n'.join(self.company['office'].db.iterdump())

    @staticmethod
    def old_h6(horizon):
        return dict(schema_version=6, **{key: horizon[key] for key in
            ('prejournal', 'allocations', 'components', 'refunds', 'capacity', 'refunds_v2')})

    @staticmethod
    def old_financial_rows(office):
        names = [row[0] for row in office.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
                 if row[0].startswith('business_accounting') and row[0] not in TABLES
                 and not row[0].startswith(('business_accounting_opening_','business_accounting_asset_opening_','business_accounting_open_item_','business_accounting_year_opening_'))]
        return {name: sorted(canonical(dict(row)) for row in office.db.execute('SELECT * FROM '+name)) for name in names}

    def test_reads_and_preview_never_save_and_explicit_null_profile_changes_no_financial_history(self):
        office = self.company['office']
        original_status = self.call(self.company, '/business/accounting/status').json
        horizon = business_schema.financial_accounting_horizon(office)
        self.assertEqual(horizon['schema_version'], 15)
        self.assertEqual(horizon['profile']['table_counts'], {table: 0 for table in TABLES})
        before, rows = self.database(), self.old_financial_rows(office)
        state = self.state()
        self.assertEqual((state['revision'], state['preparation_status'], state['current']), (0, 'unrecorded', None))
        self.assertTrue(state['writes_allowed'])
        self.assertEqual(self.call(self.company, PREFIX+'/history').json,
                         dict(items=[], total=0, next_offset=None, scope='organization_profile'))
        command = self.command(self.draft(reason='  Synthetic owner declaration  '))
        self.assertEqual(self.database(), before)
        entry = self.call(self.company, PREFIX+'/confirm', command, status=201).json
        self.assertEqual(set(entry), ENTRY_FIELDS)
        self.assertEqual(entry['profile'], empty_profile())
        self.assertEqual(entry['reason'], '  Synthetic owner declaration  ')
        self.assertEqual((entry['revision'], entry['previous_state_hash']), (1, state['state_hash']))
        self.assertEqual(self.state()['current'], entry)
        self.assertEqual(self.state()['preparation_status'], 'recorded')
        self.assertEqual(self.call(self.company, '/business/accounting/status').json, original_status)
        self.assertEqual(self.old_financial_rows(office), rows)
        changed = business_schema.financial_accounting_horizon(office)
        self.assertEqual(self.old_h6(changed), self.old_h6(horizon))
        self.assertEqual(changed['profile']['table_counts'], {table: 1 for table in TABLES})
        self.assertNotEqual(changed['profile']['sha256'], horizon['profile']['sha256'])
        second, unused = self.confirmed(self.draft(profile=empty_profile(vat_regime='regular')))
        self.assertEqual(second['profile']['vat_timing'], None)
        self.assertEqual(second['revision'], 2)
        self.assertEqual(self.call(self.company, PREFIX+'/history?limit=1').json,
                         dict(items=[second], total=2, next_offset=1, scope='organization_profile'))
        self.assertEqual(self.call(self.company, PREFIX+'/history?limit=1&offset=1').json['items'], [entry])
        before = self.database()
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', command, status=201).json, entry)
        self.assertEqual(self.database(), before)

    def test_strict_profile_dto_wire_framing_and_nonstaff_tokens_cannot_create_a_version(self):
        body = self.draft(); command = self.command(body)
        before = self.database()
        for suffix in ('?project_id='+self.company['project'], '/history?limit=0', '/history?limit=101',
                       '/history?limit=1&limit=2', '/history?offset=-1', '/history?offset=100001', '/history?company_id=other'):
            self.call(self.company, PREFIX+suffix, status=400)
        for suffix in ('', '/history'):
            for payload in ({}, {'unknown': True}):
                self.call(self.company, PREFIX+suffix, payload, method='GET', status=400)
        self.call(self.company, PREFIX+'/preview?unused=1', body, status=400)
        self.call(self.company, PREFIX+'/confirm?limit=1&limit=2', command, status=400)
        self.call(self.company, PREFIX+'/confirm', method='GET', status=405)
        self.call(self.company, PREFIX, method='DELETE', status=405)
        for changes in ({'profile': None}, {'expected_revision': True}, {'unknown': 'x'},
                        {'reason': 'x\ny'}, {'reason': 'x\x7fy'}, {'reason': 'x\ud800'},
                        {'reason': ' '}, {'reason': 'x'*1001}, {'evidence_reference': 'x'*201}):
            self.call(self.company, PREFIX+'/preview', {**body, **changes}, status=400)
        for changes in ({'legal_form': 'corporation'}, {'accounting_method': 'double_entry'},
                        {'vat_regime': ''}, {'vat_regime': False}, {'vat_timing': 'cash'},
                        {'vat_regime': 'small_business', 'vat_timing': 'accrual'},
                        {'vat_effective_from': '2026-01-01'}, {'bookkeeping_start': '2026-02-30'},
                        {'bookkeeping_start': '2026-1-01'}, {'bookkeeping_start': '1899-12-31'},
                        {'bookkeeping_start': '2201-01-01'}, {'bookkeeping_start': False}):
            self.call(self.company, PREFIX+'/preview', {**body, 'profile': empty_profile(**changes)}, status=400)
        for changes in ({'confirmation': 1}, {'request_id': 'A'*32}, {'preview_hash': 'x'*64}):
            self.call(self.company, PREFIX+'/confirm', {**command, **changes}, status=400)
        self.assertEqual(self.database(), before)
        grant = self.call(self.company, '/offline/access/v2', {}, status=201).json
        offline = grant['token']
        offline_origin = grant['binding']['instance_id'] + ':' + grant['binding']['account_id']
        # A real accepted bound device reaches its normal project route before
        # accounting denial; a missing-origin rejection would not prove this ACL.
        self.call(self.company, '/projects', token=offline, offline_origin=offline_origin)
        for credential in (None, offline, 'SPPT_'+'s'*43, 'SPPI_'+'i'*43):
            for suffix, payload in (('', None), ('/history', None), ('/preview', body), ('/confirm', command)):
                self.call(self.company, PREFIX+suffix, payload, token=credential, offline_origin=offline_origin if credential == offline else None,
                          status=403 if credential == offline else (401, 403))
        self.assertEqual(self.state()['revision'], 0)

    def test_schema10_requires_exact_profile_inventory_even_empty_and_old_h6_cannot_unlock(self):
        office = self.company['office']; self.require_reconciliation(office)
        report = self.report(office)
        self.assertEqual(report['schema'], 16)
        self.assertEqual(set(report['accounting_horizon']), {'schema_version','prejournal','allocations',
                         'components','refunds','capacity','refunds_v2','profile','euer','payroll_cash','bank_reconciliation', 'travel_cash', 'opening_balances', 'historical_assets','opening_items','year_values'})
        invalid = [{**report, 'schema': 7, 'accounting_horizon': self.old_h6(report['accounting_horizon'])},
                   {**report, 'schema': 10}, {**report, 'schema': True}]
        for changes in ({'schema_version': True}, {'schema_version': 2}, {'sha256': '0'*64},
                        {'table_counts': {}}, {'table_counts': {name: True for name in TABLES}},
                        {'table_counts': {name: -1 for name in TABLES}},
                        {'table_counts': {**{name: 0 for name in TABLES}, 'future': 0}}, {'extra': None}):
            candidate=deepcopy(report); candidate['accounting_horizon']['profile'].update(changes); invalid.append(candidate)
        before = self.database()
        for candidate in invalid:
            with self.assertRaises((Problem, ValueError)):
                business_schema.reconcile_local_financial_restore(office,candidate,self.report_hash(candidate),application_stopped=True)
            self.assertEqual(self.database(),before)
        approved=business_schema.reconcile_local_financial_restore(office,report,self.report_hash(report),application_stopped=True)
        self.confirmed()
        before=self.database()
        self.assertEqual(business_schema.reconcile_local_financial_restore(office,report,self.report_hash(report),application_stopped=True),approved)
        self.assertEqual(self.database(),before)

    def test_genuine_h6_rows_and_schema7_receipt_survive_migration_but_cannot_release_a_new_restore(self):
        previous=tuple(spec for spec in business_schema.registry() if spec.name not in ('business_accounting_profile','business_accounting_euer', 'business_payroll_cash', 'business_bank_reconciliation', 'business_travel_allowances', 'business_accounting_openings', 'business_accounting_asset_openings', 'business_accounting_open_items','business_accounting_year_openings'))
        with patch.object(business_schema,'registry',return_value=previous):
            company=self.new_company('historical-profile'); account=self.account_record(company)
            with patch.object(self,'company',company),patch.object(self,'account',account):
                origin, returned, reused, bound=self.rebound()
                unused,event=self.receipt(origin['invoice'],'10.00')
                cpath,ccommand=self.capacity_command(event)
                centry=self.call(company,cpath+'/confirm',ccommand,status=201).json
            office=company['office']; rows=self.old_financial_rows(office)
            horizon=business_schema.financial_accounting_horizon(office)
            self.assertEqual(horizon['schema_version'],6)
            self.require_reconciliation(office); report=self.report(office)
            self.assertEqual(report['schema'],7)
            digest=self.report_hash(report)
            approved=business_schema.reconcile_local_financial_restore(office,report,digest,application_stopped=True)
        business_schema.ensure_schema(office); business_schema.ensure_schema(office)
        current=business_schema.financial_accounting_horizon(office)
        self.assertEqual(current['schema_version'],15)
        self.assertEqual(self.old_h6(current),horizon)
        self.assertEqual(current['profile']['table_counts'],{table:0 for table in TABLES})
        self.assertEqual(self.old_financial_rows(office),rows)
        self.assertEqual(self.state(company=company)['preparation_status'],'unrecorded')
        before='\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office,report,digest,application_stopped=True),approved)
        self.assertEqual('\n'.join(office.db.iterdump()),before)
        for path,command,entry in ((returned['path'],returned['command'],returned['entry']),
                (reused['path'],reused['command'],reused['entry']), (bound['path'],bound['command'],bound['entry']),
                (cpath,ccommand,centry)):
            self.assertEqual(self.call(company,path+'/confirm',command,status=201).json,entry)
        saved=backup(self.directory/'historical-profile.sqlite3',self.directory/'historical-profile-backup.sqlite3')
        restored=Office(restore(saved,self.directory/'historical-profile-restored.sqlite3')); self.addCleanup(restored.db.close)
        before='\n'.join(restored.db.iterdump())
        for stale in (report,{**report,'restore_id':business_schema.state(restored)['restore_id']}):
            with self.assertRaises((Problem,ValueError)):
                business_schema.reconcile_local_financial_restore(restored,stale,self.report_hash(stale),application_stopped=True)
            self.assertEqual('\n'.join(restored.db.iterdump()),before)
        self.assertTrue(business_schema.state(restored)['financial_reconciliation_required'])

    def test_real_restore_requires_schema10_cli_evidence_then_replays_old_and_pending_profile_commands(self):
        first,command=self.confirmed()
        second,second_command=self.confirmed(self.draft(profile=empty_profile(vat_regime='small_business',vat_effective_from='2026-01-01')))
        pending=self.command(self.draft(reason='Synthetic explicit third declaration'))
        office=self.company['office']; horizon=business_schema.financial_accounting_horizon(office)
        saved=backup(self.directory/'alpha.sqlite3',self.directory/'profile-backup.sqlite3')
        target=restore(saved,self.directory/'profile-restored.sqlite3')
        restored=Office(target); self.addCleanup(restored.db.close)
        company={**self.company,'office':restored}; self.open_app(company)
        company['token']=self.login(company,'owner@example.test','Synthetic-accounting-owner-password-123',advance=True)
        self.assertEqual(business_schema.financial_accounting_horizon(restored),horizon)
        self.assertFalse(self.state(company=company)['writes_allowed'])
        self.assertEqual(self.call(company,PREFIX+'/history').json['items'],[second,first])
        for request in (command,second_command,pending):
            response=self.call(company,PREFIX+'/confirm',request,status=409)
            self.assertNotIn('request_resolution',response.json)
        report=self.report(restored); evidence=self.directory/'profile-review.json'
        evidence.write_text(json.dumps(report,indent=2)+'\n'); evidence.chmod(0o600)
        office.db.close(); restored.db.close()
        script=Path(__file__).resolve().parents[2]/'scripts'/'reconcile-accounting-restore.py'
        args=[sys.executable,str(script),'--database',str(target)]
        before=hashlib.sha256(target.read_bytes()).hexdigest()
        inspected=subprocess.run(args+['--inspect'],capture_output=True,text=True,timeout=20)
        self.assertEqual(inspected.returncode,0,inspected.stderr)
        result=json.loads(inspected.stdout)
        self.assertEqual(result['evidence_schema'],16); self.assertEqual(result['accounting_horizon'],horizon)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),before)
        stale={**report,'schema':7,'accounting_horizon':self.old_h6(horizon)}
        old=self.directory/'profile-old-review.json'; old.write_text(json.dumps(stale)); old.chmod(0o600)
        rejected=subprocess.run(args+['--evidence',str(old),'--application-stopped'],capture_output=True,text=True,timeout=20)
        self.assertNotEqual(rejected.returncode,0); self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),before)
        accepted=subprocess.run(args+['--evidence',str(evidence),'--application-stopped'],capture_output=True,text=True,timeout=20)
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        replay=subprocess.run(args+['--evidence',str(evidence),'--application-stopped'],capture_output=True,text=True,timeout=20)
        self.assertEqual(replay.returncode,0,replay.stderr); self.assertEqual(json.loads(replay.stdout),json.loads(accepted.stdout))
        reopened=Office(target); self.addCleanup(reopened.db.close); company['office']=reopened; self.open_app(company)
        for original,entry in ((command,first),(second_command,second)):
            self.assertEqual(self.call(company,PREFIX+'/confirm',original,status=201).json,entry)
        self.assertEqual(self.call(company,PREFIX+'/confirm',pending,status=201).json['revision'],3)
        self.assertEqual(self.call(company,PREFIX+'/confirm',command,status=201).json,first)

    def test_partial_profile_installation_or_missing_dependency_fails_closed_without_read_repair(self):
        from business_accounting_profile import installed
        for corruption in ('one-table','marker','dependency'):
            with self.subTest(corruption=corruption):
                company=self.new_company('profile-corrupt-'+corruption); office=company['office']
                with office.db:
                    if corruption=='marker':
                        office.db.execute("DELETE FROM business_schema_migrations WHERE module='business_accounting_profile'")
                    else:
                        office.db.execute('DROP TABLE '+('business_accounting_profile_requests' if corruption=='one-table' else 'business_accounting_refunds_v2_requests'))
                before='\n'.join(office.db.iterdump())
                for operation in (installed,business_schema.financial_accounting_horizon):
                    with self.assertRaises((Problem,ValueError,RuntimeError)):
                        operation(office)
                self.assertEqual('\n'.join(office.db.iterdump()),before)

    def test_missing_historical_receipt_blocks_reads_and_exact_replay_without_terminal_resolution(self):
        unused,command=self.confirmed(); office=self.company['office']
        with office.db:
            office.db.execute('DROP TRIGGER business_accounting_profile_requests_delete_guard')
            office.db.execute('DELETE FROM business_accounting_profile_requests')
        before=self.database()
        self.call(self.company,PREFIX,status=409)
        self.call(self.company,PREFIX+'/history',status=409)
        response=self.call(self.company,PREFIX+'/confirm',command,status=409)
        self.assertNotIn('request_resolution',response.json)
        self.assertEqual(self.database(),before)


if __name__=='__main__':
    unittest.main()
