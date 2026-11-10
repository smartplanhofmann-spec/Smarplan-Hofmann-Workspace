"""V15 arithmetic uses genuinely accepted factor/P4 and V2 annual originals."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core import Problem
from payroll_factor_oneoff_composition_2026 import calculate_source,calculation_matches,RULE_VERSION
from payroll_factor_annual_basis_2026 import build_plan as annual_plan
import payroll_factor_claims_2026 as running
import test_business_payroll_factor_annual_basis as original


class FactorOneoffCompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.FactorAnnualTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.composition_source()

    def calculate(self,source=None,**changes):
        return calculate_source(source or self.source,**(dict(rule_version=RULE_VERSION,source_contract_version=2)|changes))

    def test_actual_originals_add_exact_other_tax_and_social_without_retaxing_running_wage(self):
        result=self.calculate();base=running.calculate_source(self.source['running_calculation_case']['sources'])
        self.assertTrue(result['payroll_calculation_complete']);self.assertEqual(result['scope'],'regular_standard_factor_claims_oneoff')
        self.assertEqual(result['gross_minor'],base['gross_minor']+50000)
        self.assertEqual(result['running_calculation'],base)
        extra=result['one_off_details'];self.assertEqual(extra['amount_minor'],50000)
        self.assertGreater(extra['tax']['STS'],0);self.assertGreater(extra['tax']['SOLZS'],0)
        proof=json.loads((Path(__file__).parent/'testdata/factor_oneoff_composition_tax_reference_2026.json').read_text())
        expected=next(item['expected'] for item in proof['cases'] if item['pap_input']['JRE4']==13419355 and item['pap_input']['f']=='0.753' and item['pap_input']['R']==0)
        self.assertEqual({key:extra['tax'][key] for key in ('STS','SOLZS','BKS')},expected)
        self.assertEqual(extra['annual_pay_before_minor'],13419355)
        self.assertEqual(result['individual_wage_tax_minor'],base['individual_wage_tax_minor']+extra['tax']['STS'])
        self.assertEqual(result['net_minor'],result['gross_minor']-result['employee_social_total_minor']-result['employee_tax_minor'])
        self.assertEqual(result['payout_minor']-base['payout_minor'],50000-extra['social']['employee_total_minor']-extra['tax']['STS']-extra['tax']['SOLZS']-extra['church_tax_minor'])
        self.assertEqual(self.source['running_calculation_case']['sources']['profiles'][0]['profile']['tax_factor'],'0.753')
        self.assertFalse(extra['actual_payment_created'])

    def test_wrong_versions_and_foreign_bound_originals_never_select_a_latest_rule(self):
        for changes in (dict(rule_version='latest'),dict(source_contract_version=True),dict(source_contract_version=1)):
            with self.subTest(changes=changes):
                with self.assertRaises(Problem):self.calculate(**changes)
        for mutate in (lambda v:v['running_calculation_case'].__setitem__('rule_version','de_2026_running_segments_v5'),lambda v:v['current_annual_basis']['details'].__setitem__('current_calculation_case_ref',None),lambda v:v['annual_tax_forecast']['sources'].__setitem__('annual_source_contract',{'version':True,'rule_version':'latest'})):
            value=deepcopy(self.source);mutate(value)
            with self.assertRaises(Problem):self.calculate(value)

    def test_rehashed_annual_projection_cannot_invent_current_factor_social_room(self):
        value=deepcopy(self.source);basis=value['current_annual_basis'];basis['sources']['internal_periods'][0]['periods'][0]['branches']['health']['contributed_minor']-=1
        basis['plan']=annual_plan(basis['sources'])
        value['annual_tax_forecast']['sources']['annual_basis']=deepcopy(basis)
        value['annual_tax_forecast']['plan']=annual_plan(value['annual_tax_forecast']['sources'])
        with self.assertRaises(Problem) as caught:self.calculate(value)
        self.assertEqual(caught.exception.status,409)

    def test_actual_crlf_module_execution_preserves_exact_original_and_rejects_cent_or_unknown_hash(self):
        original=self.calculate()
        with tempfile.TemporaryDirectory(prefix='factor-oneoff-original-crlf-') as folder:
            root=Path(folder)
            for path in Path(__file__).parent.glob('*.py'):
                if not path.name.startswith('test'):
                    (root/path.name).write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            code=('import json,sys;sys.path.insert(0,sys.argv[1]);'
                'from payroll_factor_oneoff_composition_2026 import calculate_source,calculation_matches;'
                'd=json.load(sys.stdin);r=calculate_source(d["source"]);'
                'assert r!=d["original"];assert r["net_minor"]==d["original"]["net_minor"];'
                'assert calculation_matches(d["source"],r,d["original"]);print(json.dumps(r))')
            checked=subprocess.run([sys.executable,'-I','-B','-c',code,str(root)],input=json.dumps(dict(source=self.source,original=original)),text=True,capture_output=True,check=True,timeout=60,cwd=root,env={'PATH':os.environ.get('PATH',''),'LANG':'C.UTF-8'})
            transported=json.loads(checked.stdout)
        self.assertTrue(calculation_matches(self.source,original,transported))
        frozen=deepcopy(transported)
        for path in (('net_minor',),('rules_sha256',),('one_off_details','tax','pap_hash'),('one_off_details','social','rules_hash'),('one_off_details','assignment','source_hash')):
            changed=deepcopy(transported);node=changed
            for key in path[:-1]:node=node[key]
            node[path[-1]]=node[path[-1]]+1 if isinstance(node[path[-1]],int) else '0'*64
            self.assertFalse(calculation_matches(self.source,original,changed))
        self.assertEqual(transported,frozen)


if __name__=='__main__':unittest.main()
