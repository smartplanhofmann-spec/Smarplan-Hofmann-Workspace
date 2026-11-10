"""Independent offline PAP 2026 factor/other-payment reference vectors.

Only synthetic inputs. The pinned XML's own decimal expressions execute in
Java; no production payroll module is imported. This is no official approval.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import random

spec=importlib.util.spec_from_file_location('factor_oracle',Path(__file__).with_name('payroll-factor-reference.py'))
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)


def cases():
    base=dict(tax_class=4,factor='0.753',children_half_units=0,
        additional_health_percent='2.90',saxony=False,childless_surcharge=True,
        care_child_discounts=0,church_member=False,annual_allowance_minor=0,annual_addition_minor=0)
    rows=[dict(base,annual_pay_before_minor=annual,one_off_minor=extra,factor=factor)
        for annual in (0,1,1000000,6000000,8750000,10000000,20000000,10**12-250000)
        for extra in (0,1,99,100,99999,100000,250000)
        for factor in ('0.000','0.001','0.753','0.999')]
    rng=random.Random(2026111015)
    for _ in range(120):
        discount=rng.randrange(5)
        rows.append(dict(base,annual_pay_before_minor=rng.randrange(1,60000001),
            one_off_minor=rng.randrange(1,20000001),factor=f'0.{rng.randrange(1000):03d}',
            children_half_units=rng.choice((0,1,2,3,4,8,20)),
            additional_health_percent=rng.choice(('0','2.90','3.29','20')),
            saxony=bool(rng.randrange(2)),childless_surcharge=not discount,
            care_child_discounts=discount,church_member=bool(rng.randrange(2))))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();rows=cases()
    pap=[dict(af=1,f=row['factor'],LZZ=2,RE4=row['annual_pay_before_minor']//12,
        JRE4=row['annual_pay_before_minor'],SONSTB=row['one_off_minor'],STKL=4,
        ZKF=str(row['children_half_units']/2),KVZ=row['additional_health_percent'],
        PVS=int(row['saxony']),PVZ=int(row['childless_surcharge']),PVA=row['care_child_discounts'],R=int(row['church_member'])) for row in rows]
    values=oracle.oracle(oracle.java_source(args.xml.read_bytes()),pap)
    proof=dict(schema_version=1,xml_sha256=oracle.XML_SHA256,official_xml_url=oracle.OFFICIAL_XML,
        reviewed_mirror_url=oracle.XML_MIRROR,direct_official_xml_download=False,
        production_kernel_imported=False,runtime_network=False,official_system_approval=False,
        cases=[dict(input=row,pap_input=inputs,expected={key:int(value[key]) for key in ('STS','SOLZS','BKS')}) for row,inputs,value in zip(rows,pap,values)])
    args.output.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),xml_sha256=oracle.XML_SHA256,production_kernel_imported=False)))


if __name__=='__main__':main()
