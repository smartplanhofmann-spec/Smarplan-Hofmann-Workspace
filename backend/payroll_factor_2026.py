"""Explicit class-IV factor profiles and source-bound full-month payroll.

Existing contribution/monthly rules remain available under their old versions.
The new profile is opt-in and does not relax insurance, age or source blockers.
Partial months, midijobs and exceptional pay retain their separate blockers.
"""
from decimal import Decimal
import hashlib
import json
import re

from core import Problem
from payroll_de_2026 import FULL_RULES, FULL_RULES_SHA256, FULL_RULE_VERSION
from payroll_pap_factor_2026 import (calculate_standard_factor_tax,
    FACTOR_PAP_VERSION, FACTOR_PAP_SHA256, FACTOR_PAP_PROVENANCE)


FACTOR_RULE_VERSION = 'de_2026_standard_factor_monthly_v8'
FACTOR_RULES = dict(FULL_RULES, version=FACTOR_RULE_VERSION,
    standard_rules_sha256=FULL_RULES_SHA256, pap_version=FACTOR_PAP_VERSION,
    pap_provenance_sha256=FACTOR_PAP_SHA256,
    scope='regular_standard_factor_monthly', factor_from='EXPLICIT_EFFECTIVE_VERIFIED_PROFILE',
    factor_derived_from_household_income=False, additional_allowances_supported=False,
    partial_month_supported=False, transition_supported=False, oneoff_supported=False)
FACTOR_RULES_SHA256 = hashlib.sha256(json.dumps(FACTOR_RULES,
    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def normalize_factor_profile(value):
    from payroll_de_2026 import normalize_profile
    if not isinstance(value, dict) or 'tax_factor' not in value:
        raise Problem(400, 'Der Faktor-Regelstand benötigt einen ausdrücklich belegten Faktor.')
    factor = value['tax_factor']
    if not isinstance(factor, str) or not re.fullmatch(r'0\.[0-9]{3}', factor):
        raise Problem(400, 'Den eingetragenen ELStAM-Faktor mit genau drei Nachkommastellen und kleiner als eins erfassen.')
    result = normalize_profile({k:v for k,v in value.items() if k != 'tax_factor'})
    if (result['employment_kind'] != 'regular' or result['tax_class'] != 4
            or 'tax_factor' not in result['special_cases']
            or result.get('tax_allowance_monthly_minor') != 0
            or result.get('tax_addition_monthly_minor') != 0
            or 'transition_assessment' in result):
        raise Problem(400, 'Der begrenzte Faktorfall benötigt reguläre Steuerklasse IV, den ausdrücklich markierten Faktorfall und bestätigte null Frei-/Hinzurechnungsbeträge ohne Übergangsbereich.')
    return dict(result, tax_factor=factor)


def calculate_factor(profile, month, gross_minor, *, full_month_confirmed,
                     source_issues=()):
    from payroll_de_2026 import calculate
    p = normalize_factor_profile(profile)
    base = {k:v for k,v in p.items() if k != 'tax_factor'}
    base['special_cases'] = [code for code in p['special_cases'] if code != 'tax_factor']
    result = calculate(base, month, gross_minor, full_month_confirmed=full_month_confirmed,
                       source_issues=source_issues, rule_version=FULL_RULE_VERSION)
    result.update(rule_version=FACTOR_RULE_VERSION, rules_sha256=FACTOR_RULES_SHA256,
                  pap_version=FACTOR_PAP_VERSION, pap_provenance_sha256=FACTOR_PAP_SHA256)
    result['tax_parameters']['tax_factor'] = p['tax_factor']
    if not result['payroll_calculation_complete']:
        return result
    tax = calculate_standard_factor_tax(gross_minor=gross_minor, period=2,
        tax_class=4, factor=p['tax_factor'], children_half_units=p['tax_children_half_units'],
        additional_health_percent=format(Decimal(p['health_additional_percent']), '.2f'),
        saxony=p['federal_state']=='SN', childless_surcharge=result['care_childless_surcharge'],
        care_child_discounts=result['care_discount_children'], church_member=p['church_tax']!='none',
        allowance_minor=0, addition_minor=0)
    church = tax['BK'] * int(result['tax_parameters']['church_tax_percent']) // 100
    employee_tax = tax['LSTLZZ'] + tax['SOLZLZZ'] + church
    net = gross_minor - result['employee_social_total_minor'] - employee_tax
    result.update(scope='regular_standard_factor_monthly',
        tax_method='individual_bmf_pap_2026_factor', individual_wage_tax_minor=tax['LSTLZZ'],
        solidarity_minor=tax['SOLZLZZ'], church_tax_minor=church, employee_tax_minor=employee_tax,
        net_minor=net, payout_minor=max(0, net), employee_additional_payment_minor=max(0, -net))
    result['tax_parameters']['church_assessment_minor'] = tax['BK']
    return result
