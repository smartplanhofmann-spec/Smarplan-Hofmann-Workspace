"""Independent offline PAP XML vectors for the proposed factor/Midijob rule.

Only synthetic inputs; the production calculator is never imported. The old
developer oracle verifies the exact XML digest before executing its Java
expressions. The direct official XML download is not claimed.
"""
import argparse
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('factor_oracle',
    Path(__file__).with_name('payroll-factor-reference.py'))
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def cases():
    base = dict(period=2, tax_class=4, factor='0.753', children_half_units=0,
        additional_health_percent='2.90', saxony=False, childless_surcharge=True,
        care_child_discounts=0, church_member=False, allowance_minor=0, addition_minor=0)
    rows = [dict(base, gross_minor=gross, factor=factor)
        for gross in (60301, 70000, 80000, 100000, 120000, 140000, 160000, 180000, 200000)
        for factor in ('0.000', '0.753', '0.999')]
    rows += [dict(base, gross_minor=199999),
        dict(base, gross_minor=200000, factor='0.001'),
        dict(base, gross_minor=200000, church_member=True),
        dict(base, gross_minor=200000, saxony=True, church_member=True),
        dict(base, gross_minor=200000, saxony=True, childless_surcharge=False,
            care_child_discounts=4, children_half_units=4, church_member=True)]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = cases()
    expected = oracle.oracle(oracle.java_source(args.xml.read_bytes()),
        [oracle.pap_inputs(row) for row in rows])
    result = dict(schema_version=1, xml_sha256=oracle.XML_SHA256,
        official_xml_url=oracle.OFFICIAL_XML, reviewed_mirror_url=oracle.XML_MIRROR,
        direct_official_xml_download=False, production_kernel_imported=False,
        runtime_network=False, official_system_approval=False,
        cases=[dict(input=row, expected={key:int(value[key]) for key in ('LSTLZZ','SOLZLZZ','BK')})
               for row,value in zip(rows,expected)])
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),xml_sha256=oracle.XML_SHA256,
        production_kernel_imported=False)))


if __name__ == '__main__':
    main()
