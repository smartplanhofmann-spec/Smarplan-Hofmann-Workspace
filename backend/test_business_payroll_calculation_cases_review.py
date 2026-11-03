"""Independent actual-source and acceptance checks of the new private v5 API."""
from copy import deepcopy
import json
import unittest

from business_foundation import BusinessFoundation
from business_payroll_entitlements import PayrollEntitlements
from business_payroll_facts import reference
import business_payroll_calculation_cases as cases
from business_personnel_workflow import _sha
from core import canonical, Problem
from test_business_payroll import rid
import test_business_payroll_calculation_cases as fixture


class IndependentCalculationCaseSourceReview(unittest.TestCase):
    setUp=fixture.CalculationCaseTests.setUp
    details=fixture.CalculationCaseTests.details
    request=fixture.CalculationCaseTests.request
    policy=fixture.CalculationCaseTests.policy
    actual_flat_travel=fixture.CalculationCaseTests.actual_flat_travel

    def unpaid(self,first='2026-10-20',last='2026-10-24'):
        f=self.f;api=PayrollEntitlements(f.office,clock=lambda:f.now)
        original=dict(id=f.data['file']['id'],revision=1,content_hash=f.data['file']['content_hash'])
        details=dict(case_key=rid(),employment_terms_ref=reference(self.base['sources']['employment_terms']),
            work_schedule_refs=[],preparation_refs=[],agreement_refs=[reference(f.data['agreement'])],
            sickness_history_ref=None,verification_note='Actual signed interruption for independent review',
            input=dict(**{'from':first,'to':last},employment_to=None,employment_continues=True,
                no_wage_claim=True,intervening_paid_days=[],evidence_refs=[original],exceptions=[]))
        request=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='unpaid_continuation',
                     details=details,source_file_ids=[original['id']])
        preview=api.preview(f.owner,request)
        return api.save(f.owner,dict(request,request_id=rid(),revision=0,status='active',
                                    confirmed=True,preview_hash=preview['preview_hash']))

    def test_existing_active_unpaid_claim_cannot_be_omitted_to_restore_full_wages(self):
        claim=self.unpaid()
        self.f.problem(409,lambda:self.request())
        details=self.details();details['entitlement_case_refs']=[reference(claim)]
        body,_=self.request(details);saved=self.api.save(self.f.owner,body)
        self.assertEqual(23342,saved['plan']['gross_minor'])

    def test_new_claim_stales_fresh_use_but_does_not_rewrite_already_accepted_case(self):
        body,_=self.request();saved=self.api.save(self.f.owner,body)
        self.unpaid()
        self.assertEqual(saved,self.api.save(self.f.owner,body))
        self.assertTrue(cases.validate_integrity(self.f.office))
        self.f.problem(409,lambda:self.api.resolve_calculation_case(
            self.f.owner,self.f.employee['id'],reference(saved)))

    def test_unrelated_future_month_fact_does_not_block_current_month(self):
        self.unpaid('2026-11-20','2026-11-24')
        body,_=self.request();saved=self.api.save(self.f.owner,body)
        self.assertEqual(33068,saved['plan']['gross_minor'])
        self.assertTrue(saved['plan']['can_calculate'])

    def test_policy_source_verification_checks_actual_acceptance_receipt(self):
        saved,_=self.policy();db=self.f.office.db
        row=dict(self.api._row(saved['id'],saved['revision']))
        payload=json.loads(row['payload_json']);sources=json.loads(row['sources_json'])
        payload['accepted_command']['request_id']=rid()
        envelope={key:value for key,value in row.items() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources,command_hash=_sha(
            ['calculation_fact.saved:travel_tax_policy',payload['accepted_command']]))
        db.execute('DROP TRIGGER business_payroll_calculation_case_events_update_guard')
        db.execute('UPDATE business_payroll_calculation_case_events SET payload_json=?,command_hash=?,content_hash=? WHERE id=?',
                   (canonical(payload),envelope['command_hash'],_sha(envelope),saved['id']))
        changed=self.api._get(saved['id'],saved['revision'])
        with self.assertRaises(ValueError):cases.validate_case_sources(self.f.office,changed)
        with self.assertRaises(ValueError):cases.validate_integrity(self.f.office)

    def test_known_status_cannot_be_substituted_for_documented_unknown_membership(self):
        settlement=self.actual_flat_travel();policy,_=self.policy(method='evidence')
        original=dict(id=self.f.data['file']['id'],revision=1,content_hash=self.f.data['file']['content_hash'])
        details=self.details();details.update(travel_settlement_refs=[reference(settlement)],
            flat_tax_decision=dict(policy_ref=reference(policy),record_on_finalize=True,
                church_membership_evidence=dict(kind='unknown_membership_general_rate',reference=original,church_tax=None),
                employee_deduction_file_ref=None,tax_certificate_file_ref=None,tax_certificate_issued_on=None))
        body,_=self.request(details);saved=self.api.save(self.f.owner,body)
        flat=saved['sources']['flat_travel_tax']
        self.assertEqual((100,5,8,113),tuple(flat['calculation'][key] for key in
            ('wage_tax_minor','solidarity_minor','church_tax_minor','statutory_employer_due_minor')))
        self.assertFalse(flat['recording_context']['actual_recorded'])
        changed=deepcopy(details);changed['flat_tax_decision']['church_membership_evidence']['church_tax']=False
        self.f.problem(400,lambda:self.request(changed))

    def test_fresh_approval_is_required_for_accepted_case_and_global_policy_replay(self):
        f=self.f;uid=f.office.add_user('calculation-review@example.test','Synthetic-calculation-review-123','technician')
        actor=dict(id=uid,email='calculation-review@example.test',role='technician')
        grants=BusinessFoundation(f.office)
        for permission in ('personnel.read','personnel.approve'):
            grants.save_grant(f.owner,dict(request_id=rid(),user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        body,_=self.request();saved=self.api.save(actor,body)
        _,policy_body=self.policy()
        # Create a separate non-overlapping employer decision as this delegate.
        request=deepcopy(policy_body);request['request_id']=rid()
        request['details'].update(filing_period_from='2026-07-01',filing_period_to='2026-09-30')
        preview=self.api.preview(actor,{key:request[key] for key in ('employee_id','employee_revision','kind',
            'rule_version','source_contract_version','details','source_file_ids')})
        request['preview_hash']=preview['preview_hash'];policy=self.api.save(actor,request)
        grants.save_grant(f.owner,dict(request_id=rid(),user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        self.assertEqual(saved,self.api.get(actor,saved['id']))
        self.assertEqual(policy,self.api.get(actor,policy['id']))
        f.problem(403,lambda:self.api.save(actor,body))
        f.problem(403,lambda:self.api.save(actor,request))


if __name__=='__main__':
    unittest.main()
