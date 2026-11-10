"""Independent pinned XML expectations, factor rounding and strict scope."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import importlib.util
import tempfile
from unittest.mock import patch

from core import Problem
from payroll_factor_oneoff_2026 import calculate_factor_one_off_tax
import payroll_factor_oneoff_2026 as factor_oneoff

VECTORS=json.loads((Path(__file__).parent/'testdata/factor_oneoff_reference_2026.json').read_text())


class FactorOneoffPapTests(unittest.TestCase):
    def test_new_provenance_and_result_are_identical_with_actual_crlf_source_copies(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);module=root/'factor_oneoff_copy.py';annual=root/'annual_copy.py'
            module.write_bytes(Path(factor_oneoff.__file__).read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            annual.write_bytes(Path(factor_oneoff.standard.__file__).read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
            spec=importlib.util.spec_from_file_location('factor_oneoff_crlf',module);loaded=importlib.util.module_from_spec(spec)
            with patch.object(factor_oneoff.standard,'__file__',str(annual)):spec.loader.exec_module(loaded)
            self.assertEqual(loaded.FACTOR_ONEOFF_PAP_HASH,factor_oneoff.FACTOR_ONEOFF_PAP_HASH)
            case=VECTORS['cases'][-1]['input']
            self.assertEqual(loaded.calculate_factor_one_off_tax(**case),calculate_factor_one_off_tax(**case))

    def test_all_independently_executed_xml_vectors_match_exact_sts_solzs_bks(self):
        self.assertEqual(len(VECTORS['cases']),344)
        self.assertFalse(VECTORS['production_kernel_imported'])
        for index,case in enumerate(VECTORS['cases']):
            with self.subTest(index=index):
                result=calculate_factor_one_off_tax(**case['input'])
                self.assertEqual({key:result[key] for key in ('STS','SOLZS','BKS')},case['expected'])

    def test_zero_other_pay_and_zero_factor_never_invent_tax(self):
        row=deepcopy(VECTORS['cases'][0]['input']);row.update(annual_pay_before_minor=10000000,one_off_minor=0,factor='0.753',church_member=True)
        self.assertEqual({key:calculate_factor_one_off_tax(**row)[key] for key in ('STS','SOLZS','BKS')},{'STS':0,'SOLZS':0,'BKS':0})
        row.update(one_off_minor=1000000,factor='0.000')
        self.assertEqual({key:calculate_factor_one_off_tax(**row)[key] for key in ('STS','SOLZS','BKS')},{'STS':0,'SOLZS':0,'BKS':0})

    def test_guards_refuse_unproved_tax_classes_factors_allowances_and_amounts(self):
        base=VECTORS['cases'][0]['input']
        changes=[dict(tax_class=value) for value in (True,1,3,5,'4')]
        changes += [dict(factor=value) for value in ('1.000','0.75','-0.500',0.753,'0.٧٥٣','')]
        changes += [dict(annual_pay_before_minor=value) for value in (True,-1,1.1,10**12+1)]
        changes += [dict(one_off_minor=value) for value in (True,-1,1.1,10**12+1)]
        changes += [dict(annual_pay_before_minor=10**12,one_off_minor=1),dict(annual_allowance_minor=1),dict(annual_addition_minor=1),dict(annual_allowance_minor=False),dict(church_member=1)]
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(Problem) as caught:calculate_factor_one_off_tax(**(base|change))
                self.assertEqual(caught.exception.status,400)


if __name__=='__main__':unittest.main()
