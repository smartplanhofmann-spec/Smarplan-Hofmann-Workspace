"""Actual private travel journals and source-bound public reimbursements."""
import copy
from datetime import timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
import business_schema
from core import Problem,canonical
from business_accounting import Accounting
from business_travel_allowances import TravelAllowances,validate_integrity,_ref
from business_personnel_workflow import PersonnelWorkflow,_sha
import test_business_personnel_workflow as personnel_fixture
from test_business_planning import BusinessFixture,rid
from online.instance import bind
from online.storage import Storage
from travel_allowance_cash import record_payment,public_source,restore_horizon


class TravelWorkflowTests(BusinessFixture,unittest.TestCase):
    upload=personnel_fixture.PersonnelWorkflowTests.upload
    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_travel_allowances' not in names:
            patched=patch.object(business_schema,'MODULE_NAMES',names+('business_travel_allowances',));patched.start();self.addCleanup(patched.stop)
        self.prepare();self.now=self.now.replace(month=11,day=3)
        self.hr=PersonnelWorkflow(self.office,clock=lambda:self.now);self.api=TravelAllowances(self.office,clock=lambda:self.now)
        self.file=self.upload(purpose='expense_receipt',visible=True,actor=self.technician)
        self.home=self.save_site('home');self.place=self.save_site('external_fixed')
        self.instance=rid();self.key=Fernet.generate_key();self.storage=Storage(self.office,self.key,'travel.example.test',config={'server':{'path':str(Path(self.temporary.name)/'company')}})
        bind(self.office,self.instance,'travel.example.test',self.key,self.storage)
        self.account=Accounting(self.office,clock=lambda:self.now).create_account(self.owner,dict(request_id=rid(),confirmation=True,code='1200',name='Actual bank',kind='bank'))
    def save_site(self,kind):
        body=dict(request_id=rid(),employee_id=self.employee['id'],id=rid(),revision=0,status='active',correction_reason='',
            details=dict(name='Synthetic '+kind,kind=kind,address='Synthetic address',rate_id='de_2026',timezone='Europe/Berlin',
                effective_from='2026-01-01',effective_to=None,assignment_basis='Reviewed assignment evidence',regular_days_per_week=2,
                history_complete_from='2025-09-01',prior_visit_dates=[],source_file_ids=[self.file['id']]))
        return self.api.save_site(self.technician,body)['result']
    def trip_body(self,**changes):
        start='2026-10-26T08:00:00+01:00';end='2026-10-26T18:00:00+01:00'
        d=dict(purpose='Actual customer visit',project_id=self.project,departed_at=start,returned_at=end,timezone='Europe/Berlin',
            source_file_ids=[self.file['id']],home_site_ref=_ref(self.home),first_workplace_ref=None,
            segments=[dict(id=rid(),**{'from':start,'to':end},site_ref=_ref(self.place),activity='work',transport='ground',necessary_stopover=False)],
            overnights=[],meals=[],expense_refs=[],requested_meal_minor=1400,requested_lodging_minor=0,tax_choice='tax_free_only',private_intervals=[])
        d.update(changes)
        return dict(request_id=rid(),employee_id=self.employee['id'],id=rid(),revision=0,details=d,correction_reason='')
    def submitted(self):
        body=self.trip_body();draft=self.api.save_trip(self.technician,body)['result']
        submit=dict(request_id=rid(),employee_id=self.employee['id'],revision=draft['revision'],source_hash=self.api._basis(self.employee['id']),confirmed=True)
        return self.api.trip_action(self.technician,draft['id'],'submit',submit)['result']
    def approval(self,trip,**changes):
        body=dict(employee_id=self.employee['id'],trip_refs=[_ref(trip)],period_from='2026-10-26',period_to='2026-10-26',
            settlement_unit='trip',tax_choice='tax_free_only',requested_meal_minor=1400,requested_lodging_minor=0,correction_of=None,review_note='Originals and complete travel checked')
        body.update(changes);preview=self.api.preview(self.owner,body)
        return dict(body,id=rid(),request_id=rid(),revision=0,source_hash=preview['source_hash'],preview_hash=preview['preview_hash'],confirmed=True)
    def test_submission_across_clock_second_uses_one_original_event_timestamp(self):
        draft=self.api.save_trip(self.technician,self.trip_body())['result']
        command=dict(request_id=rid(),employee_id=self.employee['id'],revision=draft['revision'],
            source_hash=self.api._basis(self.employee['id']),confirmed=True)
        baseline=self.now
        ticks=iter(baseline+timedelta(seconds=i) for i in range(100))
        self.api.clock=lambda:next(ticks)
        accepted=self.api.trip_action(self.technician,draft['id'],'submit',command)
        submitted=accepted['result']
        self.assertEqual(submitted['submitted_at'],submitted['created_at'])
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.api.trip_action(self.technician,draft['id'],'submit',command),accepted)
        self.assertEqual(self.api._get('trip',draft['id'],1),draft)
    def payment(self,settlement,amount=1400,**changes):
        original=self.upload(marker=rid().encode())
        return dict(request_id=rid(),employee_id=self.employee['id'],id=rid(),revision=0,action='record',settlement_ref=_ref(settlement),
            instance_id=self.instance,account_id=self.account['id'],account_revision=self.account['revision'],kind='reimbursement',
            paid_on='2026-10-27',amount_minor=amount,reference='Bank '+rid(),reference_file_id=original['id'],
            source_hash=self.api._basis(self.employee['id']),correction_reason='',confirmed=True)|changes
    def test_own_trip_foreign_approval_exact_receipts_exports_and_actual_partial_cash(self):
        trip=self.submitted();body=self.approval(trip);receipt=self.api.approve(self.owner,body);settlement=receipt['result']
        self.assertEqual(self.api.approve(self.owner,body),receipt);self.assertEqual(self.api.status(self.owner,body['request_id']),receipt)
        self.assertEqual(settlement['calculation']['totals']['tax_free_minor'],1400)
        exported,mime=self.api.export(self.owner,settlement['id'],1,'json');self.assertEqual(mime,'application/json')
        self.assertEqual(_sha(exported),settlement['exports']['json']['sha256'])
        pdf,_=self.api.export(self.owner,settlement['id'],1,'pdf');self.assertTrue(pdf.startswith(b'%PDF-'))
        pay=self.payment(settlement,1000);accepted=record_payment(self.api,self.owner,pay)
        self.assertEqual(record_payment(self.api,self.owner,pay),accepted)
        public=public_source(self.office,accepted['target_id']);self.assertEqual(public['cash_movements'][0]['amount'],'10.00')
        self.assertNotIn(self.employee['name'],canonical(public));self.assertNotIn('customer visit',canonical(public))
        self.problem(409,lambda:record_payment(self.api,self.owner,self.payment(settlement,401)))
        remaining=record_payment(self.api,self.owner,self.payment(settlement,400))
        self.assertEqual(public_source(self.office,remaining['target_id'])['cash_movements'][0]['amount'],'4.00')
        self.assertTrue(validate_integrity(self.office));self.assertEqual(restore_horizon(self.office)['table_counts']['business_travel_payments'],2)
    def test_source_drift_self_approval_and_later_rights_do_not_rewrite_history(self):
        trip=self.submitted();body=self.approval(trip)
        self.upload(marker=b'new unrelated source')
        self.problem(409,lambda:self.api.approve(self.owner,body))
        body=self.approval(trip);accepted=self.api.approve(self.owner,body)
        # A second identity cannot claim an already settled employee day.
        self.problem(409,lambda:self.api.approve(self.owner,self.approval(trip)))
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner['id'],))
        self.problem(401,lambda:self.api.status(self.owner,body['request_id']))
        self.office.db.execute('UPDATE users SET active=1 WHERE id=?',(self.owner['id'],))
        self.assertEqual(self.api.status(self.owner,body['request_id']),accepted)
    def test_documentary_void_is_no_synthetic_refund_and_historical_original_remains(self):
        settlement=self.api.approve(self.owner,self.approval(self.submitted()))['result']
        body=self.payment(settlement);first=record_payment(self.api,self.owner,body)['result'];original=public_source(self.office,first['id'],1)
        correction=dict(body,request_id=rid(),revision=1,action='void',correction_reason='Duplicate transcription of a payment; no second money movement',source_hash=self.api._basis(self.employee['id']))
        void=record_payment(self.api,self.owner,correction)['result']
        self.assertEqual(void['status'],'void');self.assertEqual(public_source(self.office,first['id'])['cash_movements'],[])
        self.assertEqual(public_source(self.office,first['id'],1),original)
        self.assertTrue(validate_integrity(self.office))
    def test_immutable_guards_and_rehashed_false_calculation_are_detected(self):
        settlement=self.api.approve(self.owner,self.approval(self.submitted()))['result']
        with self.assertRaises(self.office.integrity_error):self.office.db.execute('DELETE FROM business_travel_settlements')
        self.office.db.execute('DROP TRIGGER business_travel_settlements_update_guard')
        row=self.api._row('settlement',settlement['id']);payload=json.loads(row['payload_json']);payload['calculation']['totals']['tax_free_minor']=999999
        self.office.db.execute('UPDATE business_travel_settlements SET payload_json=?,content_hash=? WHERE id=?',(canonical(payload),_sha(payload),settlement['id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)

