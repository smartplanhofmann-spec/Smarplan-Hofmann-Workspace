"""Exact immutable v6/v7 originals with independent CRLF kernel execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import business_schema
from core import canonical
from oneoff_provenance_compat import calculation_matches
import payroll_oneoff_composition_2026 as single
import payroll_multiple_oneoff_2026 as multiple
import oneoff_provenance_compat as compatibility
import test_business_payroll_oneoff_runs as source4
import test_business_payroll_multiple as source5
import test_business_payroll_oneoff_annual as annual_workflow


class OneoffOriginalTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copied=tempfile.TemporaryDirectory(prefix='oneoff-original-crlf-')
        cls.root=Path(cls.copied.name);cls.addClassCleanup(cls.copied.cleanup)
        for item in Path(__file__).resolve().parent.glob('*.py'):
            if not item.name.startswith('test'):
                (cls.root/item.name).write_bytes(item.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))

    def fixture4(self):
        f=source4.OneoffRunWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups);return f

    def fixture5(self):
        f=source5.MultipleWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups);return f

    def windows_calculate(self,snapshot,*,rule_version,source_contract_version):
        code=('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from payroll_oneoff_composition_2026 import calculate_oneoff_source;'
            'from payroll_multiple_oneoff_2026 import calculate_multiple_source;d=json.load(sys.stdin);'
            'f=calculate_oneoff_source if d["rule_version"]=="de_2026_oneoff_composition_v6" else calculate_multiple_source;'
            'print(json.dumps(f(d["snapshot"],rule_version=d["rule_version"],source_contract_version=d["source_contract_version"])))')
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],text=True,
            input=json.dumps(dict(snapshot=snapshot,rule_version=rule_version,source_contract_version=source_contract_version)),
            capture_output=True,check=True,timeout=60,cwd=self.root,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
        return json.loads(result.stdout)

    def test_v6_and_march_clause_reproduce_exact_independent_crlf_metadata(self):
        for parameters in ({},{'january':True,'previous':True,'bonus':600000}):
            with self.subTest(parameters=parameters):
                f=self.fixture4();snapshot=f.c.source(**parameters)
                current=single.calculate_oneoff_source(snapshot,rule_version=single.ONEOFF_RULE_VERSION,source_contract_version=1)
                old=self.windows_calculate(snapshot,rule_version=single.ONEOFF_RULE_VERSION,source_contract_version=1)
                self.assertNotEqual(current['rules_sha256'],old['rules_sha256'])
                self.assertEqual(current['net_minor'],old['net_minor'])
                if parameters.get('previous'):
                    self.assertEqual(old['one_off_details']['assignment']['social_year'],2025)
                self.assertTrue(calculation_matches(snapshot,current,old))
                frozen=canonical(old)
                for section,key in ((None,'rules_sha256'),('social','rules_hash'),('tax','pap_hash'),('assignment','source_hash')):
                    changed=json.loads(frozen)
                    if section:changed['one_off_details'][section][key]='0'*64
                    else:changed[key]='0'*64
                    self.assertFalse(calculation_matches(snapshot,current,changed))
                changed=json.loads(frozen);changed['net_minor']+=1
                self.assertFalse(calculation_matches(snapshot,current,changed))
                changed=json.loads(frozen);changed['one_off_details']['tax']['pap_hash']=current['one_off_details']['tax']['pap_hash']
                self.assertFalse(calculation_matches(snapshot,current,changed))
                self.assertEqual(canonical(old),frozen)

    def test_v7_single_original_and_month_group_keep_their_dependent_hashes(self):
        f=self.fixture5();snapshot=f.source
        current=multiple.calculate_multiple_source(snapshot,rule_version=multiple.MULTIPLE_RULE_VERSION,source_contract_version=1)
        old=self.windows_calculate(snapshot,rule_version=multiple.MULTIPLE_RULE_VERSION,source_contract_version=1)
        self.assertNotEqual(current,old);self.assertEqual(current['net_minor'],old['net_minor'])
        self.assertTrue(calculation_matches(snapshot,current,old))
        for path in (('social_month_group','source_hash'),('single_original_calculation','rules_sha256')):
            changed=json.loads(canonical(old));changed['multiple_one_off_details'][path[0]][path[1]]='0'*64
            self.assertFalse(calculation_matches(snapshot,current,changed))

    def test_unresolved_v7_multiple_claims_remain_blocked_with_exact_old_hashes(self):
        f=self.fixture5();snapshot=json.loads(canonical(f.source))
        f.c.additional(snapshot,64860)
        current=multiple.calculate_multiple_source(snapshot,rule_version=multiple.MULTIPLE_RULE_VERSION,source_contract_version=1)
        old=self.windows_calculate(snapshot,rule_version=multiple.MULTIPLE_RULE_VERSION,source_contract_version=1)
        self.assertFalse(current['payroll_calculation_complete']);self.assertIsNone(current['net_minor'])
        self.assertTrue(calculation_matches(snapshot,current,old))

    def test_lf_originals_remain_exactly_readable_under_crlf_modules(self):
        single_fixture=self.fixture4();multiple_fixture=self.fixture5()
        for snapshot,module,function,version in (
                (single_fixture.c.source(),'payroll_oneoff_composition_2026','calculate_oneoff_source',single.ONEOFF_RULE_VERSION),
                (multiple_fixture.source,'payroll_multiple_oneoff_2026','calculate_multiple_source',multiple.MULTIPLE_RULE_VERSION)):
            with self.subTest(version=version):
                calculate=single.calculate_oneoff_source if version==single.ONEOFF_RULE_VERSION else multiple.calculate_multiple_source
                original=calculate(snapshot,rule_version=version,source_contract_version=1)
                code=('import json,sys;sys.path.insert(0,sys.argv[1]);from '+module+' import '+function+' as calculate;'
                    'from oneoff_provenance_compat import calculation_matches;d=json.load(sys.stdin);'
                    'c=calculate(d["source"],rule_version=d["version"],source_contract_version=1);'
                    'assert c!=d["original"];assert calculation_matches(d["source"],c,d["original"]);'
                    'd["original"]["net_minor"]+=1;assert not calculation_matches(d["source"],c,d["original"])')
                subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],
                    input=json.dumps(dict(source=snapshot,version=version,original=original)),
                    text=True,capture_output=True,check=True,timeout=60,cwd=self.root,
                    env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})

    def test_metadata_prefilter_preserves_exact_bruteforce_acceptance(self):
        f4=self.fixture4();f5=self.fixture5()
        for snapshot,calculate,version,rebuild in (
                (f4.c.source(),single.calculate_oneoff_source,single.ONEOFF_RULE_VERSION,compatibility._single_variant),
                (f5.source,multiple.calculate_multiple_source,multiple.MULTIPLE_RULE_VERSION,compatibility._multiple_variant)):
            current=calculate(snapshot,rule_version=version,source_contract_version=1)
            old=self.windows_calculate(snapshot,rule_version=version,source_contract_version=1)
            cases=[current,old]
            bad=json.loads(canonical(old));bad['net_minor']+=1;cases.append(bad)
            bad=json.loads(canonical(old))
            if version==single.ONEOFF_RULE_VERSION:
                bad['rules_sha256']='0'*64
            else:
                bad['multiple_one_off_details']['single_original_calculation']['rules_sha256']='0'*64
            cases.append(bad)
            bad=json.loads(canonical(old))
            part=bad if version==single.ONEOFF_RULE_VERSION else bad['multiple_one_off_details']['single_original_calculation']
            part['one_off_details']['tax']['pap_hash']=current['one_off_details']['tax']['pap_hash'] if version==single.ONEOFF_RULE_VERSION else current['multiple_one_off_details']['single_original_calculation']['one_off_details']['tax']['pap_hash']
            cases.append(bad)
            for index,original in enumerate(cases):
                expected=current==original or any(rebuild(current,snapshot,variant)==original
                    for variant in compatibility._trusted_variants())
                with self.subTest(rule=version,case=index):
                    self.assertEqual(calculation_matches(snapshot,current,original),expected)

    def test_actual_source4_case_run_receipts_pdf_and_integrity_survive_native_read(self):
        f=self.fixture4()
        with patch('business_payroll_oneoff_cases.calculate_oneoff_source',side_effect=self.windows_calculate):
            case,body=f.workflow()
        command=f.command(case);run=f.f.payroll.finalize(f.f.owner,command)
        pdf=f.f.payroll.export(f.f.owner,run['id'],'pdf')[0]
        self.assertEqual(f.api.save(f.f.owner,body),case)
        self.assertEqual(f.f.payroll.finalize(f.f.owner,command),run)
        self.assertEqual(f.f.payroll.export(f.f.owner,run['id'],'pdf')[0],pdf)
        from business_payroll import _calculate_source
        frozen=canonical(run['source']);copy=_calculate_source(run['source'],rule_version=single.ONEOFF_RULE_VERSION)
        copy['net_minor']+=1
        self.assertEqual(canonical(run['source']),frozen)
        self.assertTrue(business_schema.validate_integrity(f.f.office))

    def test_actual_source5_paid_running_and_new_bonus_reach_cash_euer_once(self):
        f=self.fixture5()
        with patch('business_payroll_multiple_cases.calculate_multiple_source',side_effect=self.windows_calculate):
            state=f.paid_upgrade(cash=True)
        self.assertEqual(state['payment']['sources']['single_payment_plan']['composition_hash'],multiple.sha(state['run']['calculation']))
        self.assertEqual(f.f.payroll.finalize(f.f.owner,state['body']),state['run'])
        self.assertTrue(business_schema.validate_integrity(f.f.office))

    def test_actual_crlf_source4_prior_months_remain_usable_in_later_annual_basis(self):
        f=annual_workflow.OneoffAnnualWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups)
        with patch('business_payroll_oneoff_cases.calculate_oneoff_source',side_effect=self.windows_calculate):
            f.test_three_actual_bonuses_keep_tax_and_social_room_and_bounded_sources()
        self.assertTrue(business_schema.validate_integrity(f.f.office))
