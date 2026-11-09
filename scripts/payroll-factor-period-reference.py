"""Offline independent PAP XML oracle for monthly/daily factor components.

Only controlled synthetic inputs. Expected values execute the pinned official
XML expressions in Java; the production factor-period module is not imported.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import random

spec=importlib.util.spec_from_file_location('factor_oracle',Path(__file__).with_name('payroll-factor-reference.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


def cases():
    base=dict(gross_minor=125003,lzz=4,tax_days=10,factor='0.753',tax_class=4,
        children_half_units=0,additional_health_percent='2.90',saxony=False,
        childless_surcharge=True,care_child_discounts=0,church_member=False)
    values=[]
    for lzz,days in ((2,30),(4,1),(4,3),(4,17),(4,31)):
        for gross in (0,1,37502,266667,500001,1500000):
            for factor in ('0.000','0.001','0.753','0.999'):
                values.append(dict(base,lzz=lzz,tax_days=days,gross_minor=gross,factor=factor))
    rng=random.Random(20261109)
    for _ in range(80):
        discounts=rng.randrange(5);lzz=rng.choice((2,4))
        values.append(dict(base,lzz=lzz,tax_days=30 if lzz==2 else rng.randrange(1,32),
            gross_minor=rng.randrange(1,1800001),factor=f'0.{rng.randrange(1000):03d}',
            children_half_units=rng.choice((0,1,2,3,4,8,20)),saxony=bool(rng.randrange(2)),
            childless_surcharge=bool(rng.randrange(2)) if discounts==0 else False,
            care_child_discounts=discounts,church_member=bool(rng.randrange(2)),
            additional_health_percent=rng.choice(('0.00','2.90','3.00','3.83','10.00'))))
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();inputs=cases();pap=[]
    for case in inputs:
        ordinary=dict(case,period=case['lzz'],gross_minor=case['gross_minor'] if case['lzz']==2 else case['gross_minor']//case['tax_days'])
        pap.append(oracle.pap_inputs(ordinary))
    expected=oracle.oracle(oracle.java_source(args.xml.read_bytes()),pap)
    rows=[]
    for case,result in zip(inputs,expected):
        component={key:int(result[key]) for key in ('LSTLZZ','SOLZLZZ','BK')}
        rows.append(dict(inputs=case,expected_component=component,
            expected_totals={key:value*(case['tax_days'] if case['lzz']==4 else 1) for key,value in component.items()}))
    args.output.write_text(json.dumps(dict(schema_version=1,xml_sha256=oracle.XML_SHA256,
        official_xml_url=oracle.OFFICIAL_XML,reviewed_mirror_url=oracle.XML_MIRROR,
        direct_official_xml_download=False,runtime_network=False,official_software_approval=False,cases=rows),indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),xml_sha256=oracle.XML_SHA256,production_kernel_imported=False)))


if __name__=='__main__':main()
