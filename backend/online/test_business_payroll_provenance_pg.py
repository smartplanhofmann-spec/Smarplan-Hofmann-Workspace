"""Actual MFA/PostgreSQL restart and dump/restore of CRLF v8 originals."""
import unittest
from unittest.mock import patch

from online import test_business_payroll_pg as payroll
import test_business_payroll_provenance as transport


@unittest.skipUnless(payroll.fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class FactorOriginalTransportPostgres(unittest.TestCase):
    setUpClass=classmethod(transport.FactorOriginalTransport.setUpClass.__func__)
    windows_calculate=transport.FactorOriginalTransport.windows_calculate
    setUp=payroll.FactorPayrollPostgres.setUp
    reopen=payroll.FactorPayrollPostgres.reopen
    login=payroll.FactorPayrollPostgres.login
    call=payroll.FactorPayrollPostgres.call

    def workflow(self):
        with patch('business_payroll._calculate_source',side_effect=self.windows_calculate):
            return payroll.FactorPayrollPostgres.workflow(self)

    test_cross_encoding_original_replay_mfa_statement_and_restart=payroll.FactorPayrollPostgres.test_factor_recalculation_and_narrow_employee_statement_survive_restart
    test_cross_encoding_actual_dump_restore_retains_all_original_hashes=payroll.PayrollPostgres.test_actual_backup_restore_recalculates_result_and_retains_pdf_sources_receipts
