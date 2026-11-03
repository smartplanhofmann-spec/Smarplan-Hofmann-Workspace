"""Independent numeric BMF general machine annual table, Anlage 1 p39.

Values manually transcribed from the official PDF hosted by IHK München;
neither third-party calculator output nor this implementation generated them.
"""
import unittest
from core import Problem
from payroll_pap_2026 import calculate_standard_tax

# Columns gross euros, then annual LSt in euros for classes I through VI.
GENERAL_TABLE = '''
5000 0 0 0 0 372 558
7500 0 0 0 0 647 838
10000 0 0 0 0 922 1117
12500 0 0 0 0 1197 1397
15000 0 0 0 0 1472 1676
17500 51 0 0 51 1778 1956
20000 380 0 0 380 2234 2766
22500 782 32 0 782 3073 3604
25000 1251 359 0 1251 3911 4443
27500 1742 759 0 1742 4749 5281
30000 2248 1230 0 2248 5588 6120
32500 2767 1724 0 2767 6426 6952
35000 3300 2233 294 3300 7216 7682
37500 3847 2756 628 3847 7954 8436
40000 4407 3293 1000 4407 8720 9218
42500 4982 3843 1406 4982 9512 10030
45000 5570 4408 1850 5570 10334 10865
47500 6172 4987 2324 6172 11171 11703
50000 6788 5580 2810 6788 12010 12542
52500 7417 6186 3302 7417 12848 13380
55000 8060 6807 3802 8060 13687 14218
57500 8718 7442 4308 8718 14525 15057
60000 9389 8091 4822 9389 15364 15895
62500 10073 8754 5342 10073 16202 16734
65000 10772 9430 5870 10772 17040 17572
67500 11484 10121 6402 11484 17879 18410
70000 12220 10835 6952 12220 18729 19260
72500 13062 11647 7574 13062 19681 20213
75000 13922 12476 8206 13922 20633 21165
77500 14799 13323 8846 14799 21585 22117
80000 15694 14188 9496 15694 22538 23070
82500 16607 15071 10154 16607 23490 24022
85000 17538 15971 10822 17538 24443 24974
87500 18486 16890 11498 18486 25395 25927
90000 19438 17826 12182 19438 26347 26879
92500 20390 18777 12876 20390 27300 27831
95000 21343 19729 13580 21343 28252 28784
97500 22295 20682 14292 22295 29204 29736
100000 23248 21634 15012 23248 30157 30689
102500 24243 22629 15774 24243 31152 31684
105000 25293 23679 16590 25293 32202 32734
107500 26343 24729 17416 26343 33252 33784
110000 27393 25779 18252 27393 34302 34834
'''


def inputs(**changes):
    return dict(gross_minor=500000,period=2,tax_class=1,children_half_units=0,
        additional_health_percent='2.90',saxony=False,childless_surcharge=True,
        care_child_discounts=0,church_member=False,allowance_minor=0,addition_minor=0,**changes)


class PAP2026References(unittest.TestCase):
    def test_all_258_official_general_machine_annual_reference_values(self):
        count=0
        for line in GENERAL_TABLE.strip().splitlines():
            gross,*expected=map(int,line.split())
            for tax_class,value in enumerate(expected,1):
                with self.subTest(gross=gross,tax_class=tax_class):
                    data=inputs()
                    data.update(gross_minor=gross*100,period=1,tax_class=tax_class,childless_surcharge=tax_class!=2)
                    self.assertEqual(calculate_standard_tax(**data)['LSTLZZ'],value*100)
                    count+=1
        self.assertEqual(count,258)

    def test_official_monthly_distribution_and_solidarity_mitigation(self):
        # PAP p32: annual cents /12, truncated. Annual table gives 9389 euros.
        self.assertEqual(calculate_standard_tax(**inputs()),dict(LSTLZZ=78241,SOLZLZZ=0,BK=0))
        # p39 annual 90000/classVI=26879; p31 statutory mitigation rule.
        data=inputs();data.update(gross_minor=750000,tax_class=6,church_member=True)
        self.assertEqual(calculate_standard_tax(**data),dict(LSTLZZ=223991,SOLZLZZ=64745//10,BK=223991))

    def test_explicit_typed_and_consistent_parameters(self):
        for change in ({'gross_minor':True},{'period':3},{'additional_health_percent':'2.695'},
                {'tax_class':6,'children_half_units':1},{'tax_class':6,'addition_minor':1},
                {'childless_surcharge':True,'care_child_discounts':1}):
            with self.subTest(change=change),self.assertRaises(Problem):
                calculate_standard_tax(**{**inputs(),**change})


if __name__=='__main__':
    unittest.main()
