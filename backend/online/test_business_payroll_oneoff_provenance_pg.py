"""Actual MFA, concurrent claims and restore of Windows v6/v7 originals."""
import unittest
from unittest.mock import patch

from online import test_business_payroll_oneoff_pg as oneoff
from online import test_business_payroll_multiple_pg as multiple
import test_business_payroll_oneoff_provenance as transport


class WindowsOriginalProducer:
    setUpClass = classmethod(transport.OneoffOriginalTransport.setUpClass.__func__)
    windows_calculate = transport.OneoffOriginalTransport.windows_calculate


@unittest.skipUnless(oneoff.fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class SingleOriginalPostgres(WindowsOriginalProducer, unittest.TestCase):
    setUp = oneoff.OneoffPayrollPostgres.setUp
    reopen = oneoff.OneoffPayrollPostgres.reopen
    login = oneoff.OneoffPayrollPostgres.login
    call = oneoff.OneoffPayrollPostgres.call
    sources = oneoff.OneoffPayrollPostgres.sources
    _actual_backup_restore = oneoff.OneoffPayrollPostgres._actual_backup_restore

    def workflow(self, **kwargs):
        with patch('business_payroll_oneoff_cases.calculate_oneoff_source', side_effect=self.windows_calculate):
            return oneoff.OneoffPayrollPostgres.workflow(self, **kwargs)

    test_concurrent_actual_original_claim_and_private_mfa_rights = oneoff.OneoffPayrollPostgres.test_two_real_finalize_writers_create_one_claim_consumption_with_private_mfa_acl
    test_actual_original_paid_annual_sources_pdf_and_dump_restore = oneoff.OneoffPayrollPostgres.test_actual_paid_source4_annual_projection_survives_backup_restore


@unittest.skipUnless(oneoff.fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class MultipleOriginalPostgres(WindowsOriginalProducer, unittest.TestCase):
    setUp = multiple.MultiplePayrollPostgres.setUp
    reopen = multiple.MultiplePayrollPostgres.reopen
    login = multiple.MultiplePayrollPostgres.login
    call = multiple.MultiplePayrollPostgres.call
    sources = multiple.MultiplePayrollPostgres.sources

    def workflow(self, **kwargs):
        with patch('business_payroll_multiple_cases.calculate_multiple_source', side_effect=self.windows_calculate):
            return multiple.MultiplePayrollPostgres.workflow(self, **kwargs)

    test_concurrent_actual_original_claim_and_private_mfa_rights = multiple.MultiplePayrollPostgres.test_two_actual_finalize_writers_one_atomic_claim_event_and_private_rights
    test_actual_original_paid_running_bonus_annual_sources_and_dump_restore = multiple.MultiplePayrollPostgres.test_paid_v5_separate_day_source5_and_compact_annual_originals_restore_exactly


if __name__ == '__main__':
    unittest.main()
