"""Independent exact-rational DRV bases and pinned-XML daily factor vectors.

Only controlled inputs; no production payroll module is imported. Historical
parameters are not edited. Supply and verify the separately obtained XML.
"""
import argparse
from fractions import Fraction
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('factor_xml_oracle',
    Path(__file__).with_name('payroll-factor-reference.py'))
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def rounded(value):
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def social_expected(gross, days, *, saxony=False, childless=True, discounts=0, additional='2.90'):
    monthly = Fraction(gross * 30, days)
    lower, upper, factor = 60300, 200000, Fraction(6619, 10000)
    if monthly > upper:
        total, own, reduced = gross, gross, False
    elif monthly <= lower:
        total, own, reduced = rounded(monthly * factor * days / 30), 0, True
    else:
        base = factor * lower + (Fraction(upper, upper-lower) - Fraction(lower, upper-lower) * factor) * (monthly-lower)
        employee_base = Fraction(upper, upper-lower) * (monthly-lower)
        total, own, reduced = rounded(base * days / 30), rounded(employee_base * days / 30), True
    employee, employer = {}, {}
    rates = {'health_general': Fraction(73, 1000), 'health_additional': Fraction(additional) / 200,
             'pension': Fraction(93, 1000), 'unemployment': Fraction(13, 1000)}
    for name, rate in rates.items():
        employee[name] = rounded(own * rate)
        employer[name] = 2 * rounded(total * rate) - employee[name] if reduced else rounded(total * rate)
    theoretical = rounded(own * (Fraction(23, 1000) if saxony else Fraction(18, 1000)))
    employee['care'] = theoretical + (rounded(total * Fraction(6, 1000)) if childless else 0) - rounded(own * Fraction(discounts, 400))
    employer['care'] = (2 * rounded(total * Fraction(18, 1000)) - theoretical
                        if reduced else rounded(total * (Fraction(13, 1000) if saxony else Fraction(18, 1000))))
    return dict(total_assessment_minor=total, employee_assessment_minor=own,
                employee_contributions=employee, employer_contributions=employer,
                employer_levies=dict(u1=rounded(total * Fraction(2, 100)),
                    u2=rounded(total * Fraction(3, 1000)), insolvency=rounded(total * Fraction(15, 10000))))


def cases():
    rows = []
    for monthly in (60301, 70000, 100000, 199999, 200000):
        for days in (1, 3, 16, 17, 30):
            gross = rounded(Fraction(monthly * days, 30))
            for factor in ('0.000', '0.001', '0.753', '0.999'):
                for variant in ('childless_bw', 'church_bw', 'children_sn'):
                    childless = variant != 'children_sn'
                    rows.append(dict(monthly_minor=monthly, days=days, gross_minor=gross, factor=factor,
                        federal_state='SN' if variant == 'children_sn' else 'BW',
                        children_half_units=4 if variant == 'children_sn' else 0,
                        church_member=variant != 'childless_bw', childless_surcharge=childless,
                        care_child_discounts=2 if variant == 'children_sn' else 0,
                        additional_health_percent='2.90'))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs = cases()
    parameters = [oracle.pap_inputs(dict(row, gross_minor=row['gross_minor'] // row['days'],
        period=4, saxony=row['federal_state'] == 'SN')) for row in inputs]
    outputs = oracle.oracle(oracle.java_source(args.xml.read_bytes()), parameters)
    rows = []
    for row, out in zip(inputs, outputs):
        tax = {k: int(out[k]) * row['days'] for k in ('LSTLZZ', 'SOLZLZZ', 'BK')}
        social = social_expected(row['gross_minor'], row['days'], saxony=row['federal_state'] == 'SN',
            childless=row['childless_surcharge'], discounts=row['care_child_discounts'])
        church = tax['BK'] * (9 if row['federal_state'] == 'SN' else 8) // 100 if row['church_member'] else 0
        rows.append(dict(input=row, expected=dict(tax=tax, church_tax_minor=church, social=social,
            net_minor=row['gross_minor'] - sum(social['employee_contributions'].values()) - tax['LSTLZZ'] - tax['SOLZLZZ'] - church)))
    result = dict(schema_version=1, production_kernel_imported=False,
        xml_sha256=oracle.XML_SHA256, reviewed_mirror_url=oracle.XML_MIRROR,
        direct_official_xml_download=False, runtime_network=False, official_system_approval=False,
        contribution_oracle='EXACT_FRACTION_2026_DRV_FORMULAS_AND_CONTRACTUAL_30_DAY_RATIO_NO_PRODUCTION_IMPORT',
        cases=rows)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(cases=len(rows), production_kernel_imported=False, xml_sha256=oracle.XML_SHA256)))


if __name__ == '__main__':
    main()
