"""Actual P4/Source3/schedule originals to an immutable annual U assessment."""
from copy import deepcopy
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_wage_interruptions as markers
from business_payroll_facts import reference
from business_payroll_entitlements import PayrollEntitlements
from business_foundation import BusinessFoundation
from business_personnel_workflow import _sha
from core import canonical
from test_business_payroll import rid
import test_business_payroll_calculations as calculation_fixture
import test_business_payroll_entitlements as entitlement_fixture


class WageInterruptionWorkflow(unittest.TestCase):
    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_wage_interruptions' not in names:names+=('business_payroll_wage_interruptions',)
        registry=patch.object(business_schema,'MODULE_NAMES',names);registry.start();self.addCleanup(registry.stop)
        self.c=calculation_fixture.CalculationPayrollWorkflow('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups);self.f=self.c.f
        self.api=markers.PayrollWageInterruptions(self.f.office,clock=lambda:self.f.now)

    def originals(self,lost_from='2026-10-20',lost_to='2026-10-26'):
        f=self.f;self.schedule=entitlement_fixture.PayrollEntitlementTests.schedule(f,'2026-10')
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        self.claim=None;claim_refs=[]
        if lost_from:
            details=dict(case_key=rid(),employment_terms_ref=reference(self.c.base['sources']['employment_terms']),work_schedule_refs=[],
                preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],sickness_history_ref=None,
                input=dict(**{'from':lost_from,'to':lost_to},employment_to=None,employment_continues=True,no_wage_claim=True,
                    intervening_paid_days=[],evidence_refs=[original],exceptions=[]),verification_note='Actual fully unpaid original period')
            api=PayrollEntitlements(f.office,clock=lambda:f.now)
            proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='unpaid_continuation',details=details,source_file_ids=[original['id']])
            preview=api.preview(f.owner,proposal)
            self.claim=api.save(f.owner,dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
            claim_refs=[reference(self.claim)]
        self.case,_=self.c.case(self.c.details()|dict(entitlement_case_refs=claim_refs))
        self.run=f.payroll.finalize(f.owner,self.c.command(self.case));self.paid=self.c.payment(self.run)
        return dict(year=2026,assessment_through='2026-10-31',employment_terms_refs=[reference(self.c.base['sources']['employment_terms'])],
            run_refs=[reference(self.run)],work_schedule_refs=[reference(self.schedule)],entitlement_case_refs=claim_refs,
            excluded_payments_reviewed=True,exception_review_file_refs=[original],excluded_payments=[],
            verification_note='All statutory sentence4 payments reviewed from protected actual employer original')

    def command(self,details,**changes):
        f=self.f;proposal=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind=markers.KIND,
            rule_version=markers.RULE_VERSION,source_contract_version=1,details=details,source_file_ids=[f.data['file']['id']])
        preview=self.api.preview(f.owner,proposal)
        return dict(proposal,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])|changes,preview

    def test_actual_five_workdays_bind_payroll_claim_schedule_original_and_receipt(self):
        f=self.f;details=self.originals();body,preview=self.command(details);saved=self.api.save(f.owner,body)
        self.assertTrue(preview['can_determine']);self.assertEqual(1,saved['plan']['number_u'])
        self.assertEqual(['2026-10-20','2026-10-21','2026-10-22','2026-10-23','2026-10-26'],saved['plan']['periods'][0]['qualifying_workdays'])
        self.assertNotIn('accepted_command',saved)
        self.assertEqual(saved,self.api.save(f.owner,body));self.assertEqual(saved,self.api.get(f.owner,saved['id']))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(1,ledger['recorded_wage_interruptions']['number_u'])
        self.assertEqual('current',ledger['recorded_wage_interruptions']['status'])
        self.assertNotIn('unpaid_statutory_marker_requires_evidence',ledger['account_completeness_issues'])
        for format_ in ('pdf','csv','json'):
            self.assertTrue(f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),format_)[0])
        self.assertEqual(0,f.office.db.execute('SELECT COUNT(*) FROM business_time_days').fetchone()[0])
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_known_zero_is_not_missing_and_missing_schedule_stays_blocked(self):
        details=self.originals(lost_to='2026-10-24');body,preview=self.command(details)
        self.assertEqual(0,preview['plan']['number_u']);self.assertTrue(preview['can_determine'])
        _,missing=self.command(details|dict(work_schedule_refs=[]))
        self.assertFalse(missing['can_determine']);self.assertIsNone(missing['plan']['number_u'])
        self.assertIn('work_schedule_missing',[v['code'] for v in missing['plan']['blockers']])

    def test_missing_active_claim_run_and_original_cannot_be_omitted(self):
        f=self.f;details=self.originals()
        for key in ('run_refs','entitlement_case_refs'):
            f.problem(409,lambda key=key:self.command(details|{key:[]}))
        changed=deepcopy(details);changed['exception_review_file_refs'][0]['content_hash']='0'*64
        f.problem(409,lambda:self.command(changed))
        f.problem(400,lambda:self.command(details|dict(excluded_payments_reviewed=False)))
        f.problem(400,lambda:self.command(details|dict(assessment_through='2026-12-31')))

    def test_explicit_statutory_exclusion_uses_actual_original_and_counts_no_u(self):
        details=self.originals();details['excluded_payments']=[dict(**{'from':'2026-10-20','to':'2026-10-26'},
            kind='qualification_benefit',evidence_refs=details['exception_review_file_refs'])]
        body,preview=self.command(details);saved=self.api.save(self.f.owner,body)
        self.assertEqual(0,saved['plan']['number_u']);self.assertEqual(0,preview['plan']['number_u'])
        ledger=self.f.payroll.ledger(self.f.owner,dict(employee_id=self.f.employee['id'],year='2026'))['ledger']
        self.assertEqual(0,ledger['recorded_wage_interruptions']['number_u'])
        self.assertIn('section41_sentence4_amount_evidence_missing',ledger['account_completeness_issues'])
        self.assertFalse(ledger['statutory_wage_account_complete'])
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_correction_void_pause_replay_and_fresh_read_approval(self):
        f=self.f;details=self.originals();body,_=self.command(details);saved=self.api.save(f.owner,body)
        changed,_=self.command(details|dict(verification_note='New actual original review'),id=saved['id'],revision=1,correction_reason='Original review corrected')
        current=self.api.save(f.owner,changed)
        void=changed|dict(request_id=rid(),revision=2,status='void',correction_reason='Actual assessment withdrawn')
        archived=self.api.save(f.owner,void)
        self.assertEqual([saved,current,archived],self.api.get(f.owner,saved['id'],True)['items'])
        f.pause();self.assertEqual(saved,self.api.save(f.owner,body));self.assertEqual(current,self.api.save(f.owner,changed))
        f.problem(423,lambda:self.api.save(f.owner,body|dict(request_id=rid())))
        with f.office.db:f.office.db.execute("UPDATE users SET role='accountant' WHERE id=?",(f.owner['id'],))
        for action in (lambda:self.api.save(f.owner,body),lambda:self.api.get(f.owner,saved['id'])):f.problem(403,action)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_request_nonce_cannot_be_changed_and_rehashed_without_actual_receipt(self):
        f=self.f;details=self.originals();body,_=self.command(details);saved=self.api.save(f.owner,body)
        f.problem(409,lambda:self.api.save(f.owner,body|dict(correction_reason='Changed accepted original')))
        row=dict(self.api._row(saved['id'],1));payload=json.loads(row['payload_json']);payload['accepted_command']['request_id']=rid()
        sources=json.loads(row['sources_json']);envelope={k:v for k,v in row.items() if k not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources);envelope['command_hash']=_sha(['wage_interruption.saved',payload['accepted_command']])
        f.office.db.execute('DROP TRIGGER business_payroll_wage_interruption_events_update_guard')
        f.office.db.execute('UPDATE business_payroll_wage_interruption_events SET payload_json=?,command_hash=?,content_hash=? WHERE id=?',
            (canonical(payload),envelope['command_hash'],_sha(envelope),saved['id']))
        with self.assertRaises(ValueError):markers.validate_sources(f.office,self.api._get(saved['id']))

    def test_private_route_contract_and_immutable_events(self):
        f=self.f;details=self.originals();body,_=self.command(details);saved=self.api.save(f.owner,body)
        source,status,_=markers.dispatch(f.office,f.owner,'/payroll/wage-interruptions/sources','GET',dict(_query=dict(employee_id=f.employee['id'],year='2026')))
        self.assertEqual(200,status);self.assertEqual([self.run],source['runs']);self.assertEqual([saved],source['assessments'])
        for table in markers.TABLES:
            with self.assertRaises(sqlite3.IntegrityError):f.office.db.execute('DELETE FROM '+table)
        f.problem(403,lambda:self.api.sources(f.technician,dict(employee_id=f.employee['id'],year='2026')))

    def test_new_actual_run_revision_marks_old_assessment_outdated_but_original_is_unchanged(self):
        f=self.f;details=self.originals();body,_=self.command(details);saved=self.api.save(f.owner,body)
        original=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',
            snapshot_hash=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']['snapshot_hash']),'json')[0]
        changed=f.payroll.finalize(f.owner,self.c.command(self.case,id=self.run['id'],revision=1,correction_reason='Actual reviewed run revision'))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual('outdated',ledger['recorded_wage_interruptions']['status'])
        self.assertIsNone(ledger['recorded_wage_interruptions']['number_u'])
        self.assertIn('unpaid_statutory_marker_requires_evidence',ledger['account_completeness_issues'])
        self.assertEqual(saved,self.api.save(f.owner,body));self.assertTrue(original)
        new_body,_=self.command(details|dict(run_refs=[reference(changed)]),id=saved['id'],revision=1,correction_reason='Actual corrected run bound')
        updated=self.api.save(f.owner,new_body)
        self.assertEqual([saved,updated],self.api.get(f.owner,saved['id'],True)['items'])
        self.assertEqual('current',f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']['recorded_wage_interruptions']['status'])
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
