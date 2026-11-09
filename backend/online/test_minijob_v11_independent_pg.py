"""Independent integrated PostgreSQL boundaries for the explicit v11 upgrade."""
from copy import deepcopy
import unittest

from business_payroll import Payroll, _sha, validate_integrity as validate_payroll
from business_payroll_facts import reference
from core import canonical
from online import test_business_payroll_individual_minijob_pg as existing

fixture = existing.fixture
req = fixture.request


@unittest.skipUnless(fixture.DSN, 'Own guarded disposable loopback PostgreSQL fixture required')
class MinijobV11IndependentPostgres(unittest.TestCase):
    setUp = existing.IndividualMinijobPostgres.setUp
    reopen = existing.IndividualMinijobPostgres.reopen
    login = existing.IndividualMinijobPostgres.login
    call = existing.IndividualMinijobPostgres.call
    workflow = existing.IndividualMinijobPostgres.workflow

    def test_explicit_upgrade_keeps_real_gkv_and_all_original_receipts(self):
        data = self.workflow(stop_before_upgrade=True)
        old = data['legacy']; command = data['case_command']
        self.assertFalse(old['plan']['can_calculate'])
        self.assertEqual(old['sources']['profiles'][0]['profile']['health_insurance'], 'statutory_other')
        self.call('POST', '/business/payroll/calculation-cases', dict(command, correction_reason=''), status=400)
        proposal = {key:deepcopy(command[key]) for key in (
            'employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        blocked = deepcopy(proposal)
        blocked['details']['individual_minijob_assessment']['actual_health_insurance'] = 'private'
        preview = self.call('POST', '/business/payroll/calculation-cases/preview', blocked).json
        self.assertFalse(preview['can_calculate'])
        self.call('POST', '/business/payroll/calculation-cases', req(**blocked,
            id=old['id'], revision=1, status='active', confirmed=True, preview_hash=preview['preview_hash'],
            correction_reason='Invalid private-insurance replacement must not convert GKV'), status=400)
        self.call('POST', '/business/payroll/calculation-cases/preview',
            dict(proposal, source_contract_version=2), status=400)
        accepted = self.call('POST', '/business/payroll/calculation-cases', command).json
        self.assertEqual(accepted['id'], old['id'])
        self.assertEqual(accepted['previous_hash'], old['content_hash'])
        self.assertEqual(accepted['sources']['profiles'], old['sources']['profiles'])
        self.assertEqual(accepted['sources']['identities'], old['sources']['identities'])
        self.assertEqual(self.call('POST', '/business/payroll/calculation-cases', data['legacy_command']).json, old)
        self.assertEqual(self.call('POST', '/business/payroll/calculation-cases', command).json, accepted)
        inputs = dict(source_schema_version=3, employee_id=data['employee']['id'],
                      calculation_case_ref=reference(accepted))
        run_preview = self.call('POST', '/business/payroll/preview', inputs).json
        calc = run_preview['calculation']
        self.assertEqual(calc['tax_parameters']['actual_health_insurance'], 'statutory_family')
        self.assertEqual(calc['tax_parameters']['technical_pap_parameters']['PKV'], 1)
        self.assertEqual(calc['tax_parameters']['technical_pap_parameters']['PKPV'], 0)
        self.assertEqual(calc['tax_parameters']['technical_pap_parameters']['KRV'], 0)
        self.assertEqual(calc['employee_contributions']['health_general'], 0)
        self.assertEqual(calc['employee_contributions']['pension'], 1800)
        self.assertEqual(calc['individual_wage_tax_minor'], 4866)
        run_command = req(**inputs, revision=0, confirmed=True,
            preview_hash=run_preview['preview_hash'], accepted_scope=calc['scope'])
        run = self.call('POST', '/business/payroll/runs', run_command).json
        pdf = self.call('GET', '/business/payroll/runs/' + run['id'] + '/pdf').data
        reverse = dict(data['legacy_command'], request_id=req()['request_id'], id=old['id'],
                       revision=2, correction_reason='Forbidden reverse contract change')
        self.call('POST', '/business/payroll/calculation-cases', reverse, status=400)
        self.reopen()
        self.assertEqual(self.call('POST', '/business/payroll/calculation-cases', data['legacy_command']).json, old)
        self.assertEqual(self.call('POST', '/business/payroll/runs', run_command).json, run)
        self.assertEqual(self.call('GET', '/business/payroll/runs/' + run['id'] + '/pdf?revision=1').data, pdf)
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_account_events WHERE kind='payment'").fetchone()[0], 0)

    def test_hash_valid_but_unreadable_old_run_blocks_upgrade_without_writing(self):
        data = self.workflow(stop_before_upgrade=True)
        old = data['legacy']
        # Intentionally damaged retained input, not a fabricated valid release.
        envelope = dict(id=req()['request_id'], kind='run', employee_id=data['employee']['id'], revision=1,
            previous_hash=None, identity_key=None, created_by=self.owner['id'], created_at=old['created_at'],
            pdf_sha256=None, payload={})
        with self.office.db:
            self.office.db.execute('INSERT INTO business_payroll_events '
                '(id,kind,employee_id,revision,previous_hash,identity_key,created_by,created_at,pdf_sha256,payload_json,content_hash) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                tuple(envelope[key] for key in ('id','kind','employee_id','revision','previous_hash','identity_key',
                    'created_by','created_at','pdf_sha256')) + (canonical({}), _sha(envelope)))
        row = self.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?', (envelope['id'],)).fetchone()
        self.assertEqual(Payroll(self.office)._event(row)['id'], envelope['id'])
        with self.assertRaises(ValueError):
            validate_payroll(self.office)
        count_before = self.office.db.execute('SELECT COUNT(*) FROM business_payroll_calculation_case_requests').fetchone()[0]
        self.call('POST', '/business/payroll/calculation-cases', data['case_command'], status=409)
        history = self.call('GET', '/business/payroll/calculation-cases/' + old['id'] + '/history').json['items']
        self.assertEqual(history, [old])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_events WHERE id=?',
            (envelope['id'],)).fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_calculation_case_requests').fetchone()[0], count_before)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?', (envelope['id'],)).fetchone()), dict(row))


if __name__ == '__main__':
    unittest.main()
