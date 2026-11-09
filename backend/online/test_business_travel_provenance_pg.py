"""MFA/PostgreSQL replay, concurrent cash and actual restore of CRLF travel."""
import unittest
from unittest.mock import patch

import business_schema
from online import test_business_travel_pg as travel
import test_business_travel_provenance as transport


@unittest.skipUnless(travel.fixture.DSN,'Guarded disposable PostgreSQL fixture required')
class TravelOriginalTransportPostgres(unittest.TestCase):
    setUpClass=classmethod(transport.TravelOriginalTransport.setUpClass.__func__)
    windows_calculate=transport.TravelOriginalTransport.windows_calculate
    setUp=travel.TravelPostgres.setUp
    reopen=travel.TravelPostgres.reopen
    login=travel.TravelPostgres.login
    original_sources=travel.TravelPostgres.original_sources
    payment=travel.TravelPostgres.payment

    def call(self,method,path,*args,**kwargs):
        if method=='POST' and path=='/business/personnel/travel/settlements':
            with patch('business_travel_allowances.calculate',side_effect=self.windows_calculate):
                return travel.TravelPostgres.call(self,method,path,*args,**kwargs)
        return travel.TravelPostgres.call(self,method,path,*args,**kwargs)

    def workflow(self,*args,**kwargs):
        with patch('business_travel_allowances.calculate',side_effect=self.windows_calculate):
            return travel.TravelPostgres.workflow(self,*args,**kwargs)

    test_original_mfa_http_cash_private_boundary_and_restart=travel.TravelPostgres.test_actual_mfa_http_private_boundary_runtime_guards_and_restart
    test_actual_crlf_mixed_original_and_dump_restore_under_old_default=travel.TravelPostgres.test_v3_original_programme_http_actual_payment_and_dump_restore_under_v2_default

    def test_concurrent_claim_and_exact_cash_receipt_remain_valid_under_lf(self):
        with patch('business_travel_allowances.calculate',side_effect=self.windows_calculate):
            travel.TravelPostgres.test_two_actual_connections_one_daily_claim_and_exact_payment_receipt(self)
        self.assertTrue(business_schema.validate_integrity(self.office))
