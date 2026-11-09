"""Actual factor-period MFA/HTTP, concurrent writers and cash/restore evidence."""
import unittest
from unittest.mock import patch

import business_schema
from online import test_business_payroll_periods_pg as periods
from payroll_factor_periods_2026 import FACTOR_PERIOD_SCOPE,FACTOR_PERIOD_RULE_VERSION

fixture=periods.fixture


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class FactorPeriodPostgres(unittest.TestCase):
    setUp=periods.PeriodPayrollPostgres.setUp
    reopen=periods.PeriodPayrollPostgres.reopen
    login=periods.PeriodPayrollPostgres.login
    call=periods.PeriodPayrollPostgres.call
    sources=periods.PeriodPayrollPostgres.sources
    profile=periods.PeriodPayrollPostgres.profile
    post=periods.PeriodPayrollPostgres.post
    body=periods.PeriodPayrollPostgres.body
    payload=periods.PeriodPayrollPostgres.payload

    def workflow(self,*_,**__):
        original=periods.profile
        def factor(*args,**kwargs):
            return dict(original(*args,**kwargs),tax_class=4,special_cases=['tax_factor'],tax_factor='0.753')
        # Only synthetic profile inputs vary. Requests, MFA, canonical evidence,
        # production calculations, bank originals and restore are actual code.
        with patch.object(periods,'profile',side_effect=factor):
            data=periods.PeriodPayrollPostgres.workflow(self,kind='regular',transition=False)
        self.assertEqual(data['run']['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        self.assertEqual(data['run']['calculation']['rule_version'],FACTOR_PERIOD_RULE_VERSION)
        return data

    def test_actual_factor_mfa_fresh_denial_original_pdf_and_restart(self):
        data=self.workflow();run=data['run']
        self.assertEqual(run['calculation']['gross_minor'],274194)
        self.assertEqual(run['calculation']['period_details']['tax_periods'][0]['tax_days'],17)
        pdf=self.call('GET','/business/payroll/runs/'+run['id']+'/pdf').data
        self.call('GET','/business/payroll/runs/'+run['id'],token=data['tech'],status=403)
        self.call('GET','/business/payroll/ledger?employee_id='+data['employee']['id']+'&year=2026',token=data['tech'],status=403)
        own=self.call('GET','/business/payroll/employee-statements/'+run['id'],token=data['tech']).json['statement']
        self.assertNotIn('verification_note',str(own));self.assertEqual(own['calculation']['scope'],FACTOR_PERIOD_SCOPE)
        self.reopen()
        self.assertEqual(self.call('POST','/business/payroll/runs',data['command']).json,run)
        self.assertEqual(self.call('GET','/business/payroll/runs/'+run['id']+'/pdf?revision=1').data,pdf)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_two_pg_connections_accept_only_one_factor_period_revision(self):
        periods.PeriodPayrollPostgres.test_two_pg_connections_accept_only_one_original_partial_revision(self)

    def test_factor_net_remittance_euer_bank_and_frozen_dump_restore(self):
        periods.PeriodPayrollPostgres.test_actual_partial_midijob_payment_euer_and_frozen_dump_restore(self)


if __name__=='__main__':unittest.main()
