"""Real cash-prefix and immutable-receipt checks for positive corrections."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from core import Problem
from business_personnel_workflow import _sha
from business_payroll_cash import TABLES
from payroll_cash_sources import calculated
from payroll_correction_remittances import current_observation, validate_observation
import test_business_payroll_cash as fixture


class CorrectionRemittanceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.PayrollCashTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.office = self.f.office
        self.data, self.run, self.identity, self.paid = self.f.case(regular=True)
        self.employee = self.run['employee_id']
        self.month = self.run['source']['month']
        self.calculation = self.run['calculation']

    def observe(self):
        return current_observation(self.office, self.employee, self.month, self.calculation)

    def validate(self, observation):
        return validate_observation(self.office, self.employee, self.month, self.calculation, observation)

    def remit(self):
        body = self.f.remittance(self.data, self.run, self.paid)
        return body, self.f.import_cash(body)

    def conflict(self, fn, *args):
        with self.assertRaises(Problem) as error:
            fn(*args)
        self.assertEqual(error.exception.status, 409)

    def unguard(self, table, operation='UPDATE'):
        rows = self.office.db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql LIKE ?",
                                      (table, '%BEFORE '+operation+'%')).fetchall()
        self.assertTrue(rows)
        for row in rows:
            self.office.db.execute('DROP TRIGGER "'+row['name'].replace('"','""')+'"')

    def test_real_adopted_remittance_sums_and_nonremittance_prefix(self):
        net = self.f.import_cash(self.f.body(self.paid))
        body, remittance = self.remit()
        value = self.observe()
        self.assertEqual(value['head_sequence'], 2)
        self.assertEqual(value['amounts'], calculated(self.calculation))
        self.assertEqual([entry['id'] for entry in value['entries']], [remittance['id']])
        self.assertNotEqual(value['entries'][0]['id'], net['id'])
        self.assertTrue(self.validate(value))

    def test_frozen_prefix_survives_later_real_net_batch_without_recursive_integrity(self):
        self.remit()
        value = self.observe()
        self.f.import_cash(self.f.body(self.paid))
        with patch('business_payroll_cash.validate_integrity', side_effect=AssertionError('must not recurse')):
            self.assertTrue(self.validate(value))
        self.assertEqual(self.observe()['head_sequence'], 2)

    def test_voided_relevant_batch_blocks_current_but_not_prior_observation(self):
        body, remittance = self.remit()
        value = self.observe()
        self.f.import_cash(dict(body, batch_id=remittance['id'], expected_revision=1,
            action='void', sources=[], settlement=None, correction_file_id=self.data['file']['id']))
        self.conflict(self.observe)
        self.assertTrue(self.validate(value))

    def test_actual_existing_above_corrected_component_is_not_silently_clamped(self):
        self.remit()
        value = self.observe()
        changed = deepcopy(self.calculation)
        changed['employee_tax_minor'] -= 1
        self.conflict(current_observation, self.office, self.employee, self.month, changed)
        self.conflict(validate_observation, self.office, self.employee, self.month, changed, value)

    def test_current_observation_revalidates_actual_source_original(self):
        self.remit()
        self.observe()
        with self.office.db:
            self.unguard('business_personnel_files')
            self.office.db.execute('UPDATE business_personnel_files SET original=? WHERE id=?',
                                   (b'Changed synthetic protected original', self.data['file']['id']))
        self.conflict(self.observe)

    def test_frozen_original_receipt_deletion_or_rewritten_hash_is_detected(self):
        self.remit()
        value = self.observe()
        with self.office.db:
            self.unguard('business_payroll_cash_requests', 'DELETE')
            self.office.db.execute('DELETE FROM business_payroll_cash_requests')
        self.conflict(self.validate, value)

    def test_global_prefix_gap_is_detected_even_for_unrelated_net(self):
        net = self.f.import_cash(self.f.body(self.paid))
        self.remit()
        value = self.observe()
        with self.office.db:
            self.unguard('business_payroll_cash_batches')
            self.office.db.execute('UPDATE business_payroll_cash_batches SET sequence=3 WHERE id=?', (net['id'],))
        self.conflict(self.validate, value)

    def test_scope_shape_boolean_and_rehashed_omission_are_rejected(self):
        self.remit()
        value = self.observe()
        self.conflict(validate_observation, self.office, 'f'*32, self.month, self.calculation, value)
        for mutate in (
                lambda v: v.update(head_sequence=True),
                lambda v: v.update(schema_version=True),
                lambda v: v['entries'][0].update(revision=True),
                lambda v: v['amounts'].update(employee_tax=True),
                lambda v: v.update(entries=[]),
                lambda v: v['amounts'].update(employee_tax=0)):
            changed = deepcopy(value)
            mutate(changed)
            changed['source_hash'] = _sha({key:item for key,item in changed.items() if key!='source_hash'})
            self.conflict(self.validate, changed)

    def test_absent_module_accepts_only_scoped_empty_partial_installation_blocks(self):
        for table in reversed(TABLES):
            self.office.db.execute('DROP TABLE '+table)
        value = self.observe()
        self.assertEqual(value['head_sequence'], 0)
        self.assertEqual(value['entries'], [])
        self.assertEqual(set(value['amounts'].values()), {0})
        self.assertTrue(self.validate(value))
        changed = deepcopy(value);changed['head_sequence'] = 1
        self.conflict(self.validate, changed)
        self.office.db.execute('CREATE TABLE '+TABLES[0]+'(id TEXT)')
        self.conflict(self.observe)
        self.conflict(self.validate, value)


if __name__ == '__main__':
    unittest.main()
